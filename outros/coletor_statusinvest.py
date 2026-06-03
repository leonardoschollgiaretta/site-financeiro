import requests
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

def get_session():
    session = requests.Session()
    session.get("https://statusinvest.com.br/acoes/grnd3", headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    })
    return session

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://statusinvest.com.br/acoes/grnd3",
    "Origin": "https://statusinvest.com.br",
}

def parse_valor(texto):
    """Converte '2.584,34 M' ou '1,23 B' para float em reais"""
    if not texto or texto in ["-", "", "N/A"]:
        return None
    texto = str(texto).strip()
    multiplicador = 1
    if texto.endswith(" M"):
        multiplicador = 1_000_000
        texto = texto[:-2]
    elif texto.endswith(" B"):
        multiplicador = 1_000_000_000
        texto = texto[:-2]
    elif texto.endswith(" K"):
        multiplicador = 1_000
        texto = texto[:-2]
    try:
        texto = texto.replace(".", "").replace(",", ".")
        return float(texto) * multiplicador
    except:
        return None

def extrair_endpoint(session, ticker, endpoint, nome_dados, extra_data=None):
    """Função genérica para buscar qualquer endpoint do Status Invest"""
    payload = {"code": ticker}
    if extra_data:
        payload.update(extra_data)
    resp = session.post(
        f"https://statusinvest.com.br/acao/{endpoint}",
        data=payload,
        headers=HEADERS_API
    )
    if resp.status_code != 200:
        print(f"  ❌ {nome_dados}: Erro HTTP {resp.status_code}")
        return {}
    data = resp.json()
    if not data.get("success"):
        print(f"  ❌ {nome_dados}: API retornou success=false")
        return {}
    return data["data"]

def extrair_tabela(payload):
    """
    Extrai dados de qualquer tabela do Status Invest.
    Lê os anos reais do cabeçalho da tabela e filtra colunas
    de valor ignorando AH (%) e AV (%) pelo campo 'symbol'.
    """
    import re
    grid = payload.get("grid", [])
    resultado = {}

    # Passo 1: lê anos reais do header da tabela
    anos_header = []
    for row in grid:
        if not row.get("isHeader"):
            continue
        for col in row["columns"][1:]:           # pula col[0] = "#"
            val = str(col.get("value", ""))
            match = re.search(r'\b(20\d{2}|19\d{2})\b', val)
            if match:
                anos_header.append(int(match.group(1)))
        break  # só o primeiro header

    if not anos_header:
        print("  ⚠️  Nenhum ano encontrado no cabeçalho")
        return {}

    # Passo 2: extrai valores das linhas de dados
    for row in grid:
        if row.get("isHeader"):
            continue
        cols = row["columns"]
        nome = cols[0].get("value", "")

        # Filtra apenas colunas de valor real (exclui AH e AV que têm symbol="%")
        cols_val = [c for c in cols[1:] if c.get("symbol", "") != "%"]
        # Primeira coluna filtrada = "Últ. 12M" → ignora
        cols_anos = cols_val[1:]

        for i, ano in enumerate(anos_header):
            if i >= len(cols_anos):
                break
            valor_texto = cols_anos[i].get("value", "")
            valor = parse_valor(valor_texto)
            if ano not in resultado:
                resultado[ano] = {}
            resultado[ano][nome] = valor

    return resultado

def extrair_balanco(session, ticker):
    """
    Balanço usa GET com parâmetros na URL (diferente do DRE que usa POST).
    Retorna dict: {ano: {campo: valor}}
    """
    url = "https://statusinvest.com.br/acao/getativos"
    params = {
        "code": ticker.lower(),
        "type": "0",
        "futureData": "false",
        "range.min": "2008",
        "range.max": "2025",
        "asChart": "true",
    }
    headers_get = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://statusinvest.com.br/acoes/{ticker.lower()}",
    }
    resp = session.get(url, params=params, headers=headers_get)
    if resp.status_code != 200:
        print(f"  ❌ Balanço: Erro HTTP {resp.status_code}")
        return {}
    try:
        data = resp.json()
    except:
        print(f"  ❌ Balanço: resposta inválida")
        return {}

    # Resposta: {"success":true,"data":{"years":[...],"grid":[],"chart":[...]}}
    payload = data.get("data", data)
    anos = payload.get("years", [])
    chart = payload.get("chart", [])

    resultado = {}
    for serie in chart:
        item = serie.get("item", {})
        nome = item.get("name", item.get("key", ""))
        values = item.get("values", [])  # lista alinhada com anos[]

        for i, val in enumerate(values):
            if i < len(anos) and val is not None:
                ano = anos[i]
                if ano not in resultado:
                    resultado[ano] = {}
                resultado[ano][nome] = val  # já vem em reais completos

    if not resultado:
        print(f"  ⚠️ Balanço: sem dados ou formato inesperado")
        print(f"     Preview: {resp.text[:300]}")
    return resultado

def upsert_financeiro(c, ticker, ano, fonte, campos):
    """INSERT OR REPLACE inteligente — só atualiza colunas que vieram preenchidas"""
    c.execute("""
        INSERT OR IGNORE INTO financeiros_anuais (ticker, ano, fonte)
        VALUES (?, ?, ?)
    """, (ticker, ano, fonte))
    for coluna, valor in campos.items():
        if valor is not None:
            c.execute(f"""
                UPDATE financeiros_anuais SET {coluna} = ?
                WHERE ticker = ? AND ano = ? AND fonte = ?
            """, (valor, ticker, ano, fonte))

def salvar_dre(ticker, dados):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for ano, campos in dados.items():
        mapa = {
            "receita_liquida":  campos.get("Receita Líquida - (R$)"),
            "lucro_bruto":      campos.get("Lucro Bruto - (R$)"),
            "ebitda":           campos.get("EBITDA - (R$)"),
            "ebit":             campos.get("EBIT - (R$)"),
            "lucro_liquido":    campos.get("Lucro Líquido - (R$)"),
            "desp_financeiras": campos.get("Despesas Financeiras - (R$)"),
            "ir_csll":          campos.get("IR e CSLL - (R$)"),
        }
        if any(v is not None for v in mapa.values()):
            upsert_financeiro(c, ticker, ano, "statusinvest", mapa)
    conn.commit()
    conn.close()

def salvar_balanco(ticker, dados):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for ano, campos in dados.items():
        mapa = {
            "ativo_total":        campos.get("Ativo Total - (R$)"),
            "ativo_circulante":   campos.get("Ativo Circulante - (R$)"),
            "caixa":              campos.get("Caixa e Equivalentes de Caixa - (R$)"),
            "contas_receber":     campos.get("Contas a Receber - (R$)"),
            "estoques":           campos.get("Estoque - (R$)"),
            "patrimonio_liquido": campos.get("Patrimônio Líquido Consolidado - (R$)"),
        }
        if any(v is not None for v in mapa.values()):
            upsert_financeiro(c, ticker, ano, "statusinvest", mapa)
    conn.commit()
    conn.close()

def salvar_fc(ticker, dados):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for ano, campos in dados.items():
        mapa = {
            "fco": campos.get("Caixa Líquido Atividades Operacionais - (R$)"),
            "fci": campos.get("Caixa Líquido Atividades de Investimento - (R$)"),
            "fcf": campos.get("Fluxo de Caixa Livre - (R$)"),
            "fcf_financiamento": campos.get("Caixa Líquido Atividades de Financiamento - (R$)"),
        }
        if any(v is not None for v in mapa.values()):
            upsert_financeiro(c, ticker, ano, "statusinvest", mapa)
    conn.commit()
    conn.close()

def coletar_empresa(ticker, session):
    print(f"\n📊 Coletando {ticker} do Status Invest...")

    # --- DRE ---
    payload_dre = extrair_endpoint(session, ticker, "getdre", "DRE")
    if payload_dre:
        dre = extrair_tabela(payload_dre)
        if dre:
            print(f"  ✅ DRE: {len(dre)} anos ({min(dre.keys())}-{max(dre.keys())})")
            ano_rec = max(dre.keys())
            receita = dre[ano_rec].get("Receita Líquida - (R$)")
            lucro   = dre[ano_rec].get("Lucro Líquido - (R$)")
            print(f"     {ano_rec} → Receita: R$ {receita:,.0f}" if receita else f"     {ano_rec} → Receita: N/A")
            print(f"     {ano_rec} → Lucro:   R$ {lucro:,.0f}"   if lucro   else f"     {ano_rec} → Lucro:   N/A")
            salvar_dre(ticker, dre)
        else:
            print("  ⚠️ DRE: sem dados")

    # --- Balanço Patrimonial (GET com parâmetros) ---
    bp_raw = extrair_balanco(session, ticker)
    if bp_raw:
        print(f"  ✅ Balanço: {len(bp_raw)} anos")
        salvar_balanco(ticker, bp_raw)

    # --- Fluxo de Caixa ---
    payload_fc = extrair_endpoint(session, ticker, "getfluxocaixa", "Fluxo de Caixa")
    if payload_fc:
        fc = extrair_tabela(payload_fc)
        if fc:
            print(f"  ✅ Fluxo de Caixa: {len(fc)} anos")
            salvar_fc(ticker, fc)
        else:
            print("  ⚠️ Fluxo de Caixa: sem dados")

if __name__ == "__main__":
    import banco
    banco.criar_banco()

    session = get_session()
    print(f"🔗 Sessão iniciada. Cookies: {dict(session.cookies)}")

    tickers = ["GRND3", "ITSA4", "PETR4", "VALE3"]

    for ticker in tickers:
        coletar_empresa(ticker, session)

    print("\n✅ Coleta Status Invest finalizada!")
