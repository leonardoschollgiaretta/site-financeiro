import requests
import sqlite3
import os
from bs4 import BeautifulSoup

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")
BASE = "https://www.investsite.com.br"
FONTE = "investsite"

# Anos de referência: cada request traz 3 anos (ex: 2022 → 2020,2021,2022)
ANOS_REF = [2022, 2025]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": BASE,
}

# Mapeamento: código CVM → coluna do banco
MAP_DRE = {
    "3.01": "receita_liquida",
    "3.02": "custo_receita",
    "3.03": "lucro_bruto",
    "3.05": "ebit",
    # 3.08 = Imposto de Renda e CSLL (ERRADO)
    # 3.09 = Resultado das Operações Continuadas
    # 3.11 = Lucro/Prejuízo do Período (correto — último nível do DRE)
    "3.11": "lucro_liquido",
}

MAP_ATIVO = {
    "1":       "ativo_total",
    "1.01":    "ativo_circulante",
    # 1.01.01 = Caixa e Equivalentes + 1.01.02 = Aplicações Financeiras → caixa total
    "1.01.01": "caixa",   # somado com 1.01.02 em salvar_ativo()
    "1.01.03": "contas_receber",
    "1.01.04": "estoques",
}

MAP_PASSIVO = {
    "2.03":    "patrimonio_liquido",
}

MAP_FC = {
    "6.01": "fco",
    "6.02": "fci",
    "6.03": "fcf_financiamento",
}

def parse_valor(texto):
    """Converte '1.896.785' (R$ mil) para float em reais"""
    if not texto or texto in ["-", "", "0"]:
        return None
    try:
        limpo = texto.replace(".", "").replace(",", ".").strip()
        return float(limpo) * 1000  # vem em R$ mil
    except:
        return None

def extrair_tabela(ticker, pagina, ano_ref):
    """Faz request e retorna dict {ano: {codigo: valor}}"""
    url = f"{BASE}/{pagina}?cod_negociacao={ticker}&ano_dem={ano_ref}&mes_dia_dem=1231&consolid=2&tipocontabil=2"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}
    except Exception as e:
        print(f"    ❌ Erro: {e}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    tab  = soup.find("table")
    if not tab:
        return {}

    linhas = tab.find_all("tr")
    if not linhas:
        return {}

    # Linha 0 = cabeçalho — extrai os anos das colunas
    cabecalho = [td.get_text(strip=True) for td in linhas[0].find_all(["th","td"])]
    # Colunas de valor estão nas posições 2, 4, 6 (pula % nos índices 3,5,7)
    anos_cols = []
    for i, txt in enumerate(cabecalho):
        # Extrai ano de textos como "31/12/2020(R$ mil)" ou "01/01/2020 a 31/12/2020(R$ mil)"
        import re
        match = re.findall(r'\d{4}', txt)
        if match:
            anos_cols.append((i, int(match[-1])))  # pega o último ano do texto

    resultado = {}  # {ano: {codigo: valor}}
    for linha in linhas[1:]:
        cols = [td.get_text(strip=True) for td in linha.find_all(["td","th"])]
        if len(cols) < 3:
            continue
        codigo = cols[0].strip()
        for idx_col, ano in anos_cols:
            if idx_col < len(cols):
                val = parse_valor(cols[idx_col])
                if ano not in resultado:
                    resultado[ano] = {}
                resultado[ano][codigo] = val

    return resultado

def upsert_financeiro(c, ticker, ano, campos):
    c.execute("""
        INSERT OR IGNORE INTO financeiros_anuais (ticker, ano, fonte)
        VALUES (?, ?, ?)
    """, (ticker, ano, FONTE))
    for coluna, valor in campos.items():
        if valor is not None:
            c.execute(f"""
                UPDATE financeiros_anuais SET {coluna} = ?
                WHERE ticker = ? AND ano = ? AND fonte = ?
            """, (valor, ticker, ano, FONTE))

def salvar(ticker, dados_brutos, mapeamento, conn):
    c = conn.cursor()
    for ano, codigos in dados_brutos.items():
        mapa = {}
        for codigo, coluna in mapeamento.items():
            if codigo in codigos and codigos[codigo] is not None:
                mapa[coluna] = codigos[codigo]
        if mapa:
            upsert_financeiro(c, ticker, ano, mapa)

def salvar_ativo(ticker, dados_brutos, conn):
    """Salva ativo com lógica especial: caixa = 1.01.01 + 1.01.02"""
    c = conn.cursor()
    for ano, codigos in dados_brutos.items():
        mapa = {}
        for codigo, coluna in MAP_ATIVO.items():
            if codigo in codigos and codigos[codigo] is not None:
                mapa[coluna] = codigos[codigo]

        # Soma Aplicações Financeiras (1.01.02) ao caixa se disponível
        aplic = codigos.get("1.01.02")
        if aplic is not None:
            caixa_base = mapa.get("caixa", 0) or 0
            mapa["caixa"] = caixa_base + aplic

        if mapa:
            upsert_financeiro(c, ticker, ano, mapa)

def coletar_empresa(ticker):
    print(f"\n📋 Coletando {ticker} via Investsite...")
    conn = sqlite3.connect(DB)

    for ano_ref in ANOS_REF:
        # DRE
        dre = extrair_tabela(ticker, "demonstracao_resultado.php", ano_ref)
        if dre:
            anos = sorted(dre.keys())
            salvar(ticker, dre, MAP_DRE, conn)
            print(f"  ✅ DRE ({ano_ref}): anos {anos}")
            # Mostra amostra
            for ano in anos:
                rec = dre[ano].get("3.01")
                luc = dre[ano].get("3.08")
                if rec:
                    print(f"     {ano} → Receita: R$ {rec:,.0f} | Lucro: R$ {luc:,.0f}" if luc else f"     {ano} → Receita: R$ {rec:,.0f}")

        # Balanço Ativo
        ativo = extrair_tabela(ticker, "balanco_patrimonial_ativo.php", ano_ref)
        if ativo:
            salvar_ativo(ticker, ativo, conn)
            anos = sorted(ativo.keys())
            print(f"  ✅ Balanço Ativo ({ano_ref}): anos {anos}")
            for ano in anos:
                ac = ativo[ano].get("1.01")
                cx = (ativo[ano].get("1.01.01") or 0) + (ativo[ano].get("1.01.02") or 0)
                if ac:
                    print(f"     {ano} → Ativo Circ: R$ {ac:,.0f} | Caixa+Aplic: R$ {cx:,.0f}")

        # Balanço Passivo
        passivo = extrair_tabela(ticker, "balanco_patrimonial_passivo.php", ano_ref)
        if passivo:
            salvar(ticker, passivo, MAP_PASSIVO, conn)
            anos = sorted(passivo.keys())
            print(f"  ✅ Balanço Passivo ({ano_ref}): anos {anos}")

        # Fluxo de Caixa
        fc = extrair_tabela(ticker, "fluxo_caixa.php", ano_ref)
        if fc:
            salvar(ticker, fc, MAP_FC, conn)
            anos = sorted(fc.keys())
            print(f"  ✅ Fluxo de Caixa ({ano_ref}): anos {anos}")
            for ano in anos:
                fco = fc[ano].get("6.01")
                if fco:
                    print(f"     {ano} → FCO: R$ {fco:,.0f}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    import banco
    banco.criar_banco()

    tickers = ["GRND3", "ITSA4", "PETR4", "VALE3", "SAPR4"]

    for ticker in tickers:
        coletar_empresa(ticker)

    print("\n✅ Coleta Investsite finalizada!")
