"""
Coletor Fluxo de Caixa — Ações Brasileiras
Fonte: Investsite.com.br (dados CVM oficiais)
Campos: fco, fci, fcf_financiamento, capex, venda_ativos, aquisicoes,
        captacoes, pagamento_dividas, recompra_acoes, dividendos_pagos,
        variacao_caixa, caixa_inicial, caixa_final, depreciacao_amortizacao, fcl

Nota: Códigos CVM de sub-itens (6.0x.xx) variam por empresa — os códigos
      abaixo cobrem os padrões mais comuns. Itens sem código correspondente
      ficarão em branco e não prejudicam a coleta dos totais (6.01/6.02/6.03).
"""
import requests
import sqlite3
import os
import re
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bs4 import BeautifulSoup
from db_utils import upsert_financeiro
from db_validacao import is_validado

DB     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")
BASE   = "https://www.investsite.com.br"
FONTE  = "investsite"
PAGINA = "fluxo_caixa.php"

ANOS_REF = [2022, 2025]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": BASE,
}

# Códigos CVM → coluna do banco
# Totais (padronizados pela CVM):
MAPA = {
    "6.01": "fco",
    "6.02": "fci",
    "6.03": "fcf_financiamento",
    # Sub-itens FCO — D&A costuma aparecer em sub-níveis de 6.01
    # Tentamos os códigos mais comuns; empresas podem usar outros
    "6.01.01.02": "depreciacao_amortizacao",
    "6.01.02":    "depreciacao_amortizacao",   # alternativa frequente
    # Sub-itens FCI
    "6.02.01": "capex",           # Aquisição de imobilizado / CAPEX
    "6.02.02": "venda_ativos",    # Alienação / venda de ativos
    "6.02.03": "aquisicoes",      # Aquisições de empresas / participações
    # Sub-itens FCF
    "6.03.01": "captacoes",
    "6.03.02": "pagamento_dividas",
    "6.03.03": "recompra_acoes",
    "6.03.04": "dividendos_pagos",
    # Variação e saldos de caixa
    "6.04": "variacao_caixa",
    "6.05": "caixa_inicial",
    "6.06": "caixa_final",
}

# Para campos que podem ter múltiplos códigos candidatos,
# só salvamos o primeiro valor encontrado (set abaixo controla isso)
CAMPO_UNICO = {"depreciacao_amortizacao"}


def parse_valor(texto):
    if not texto or texto.strip() in ["-", "", "0"]:
        return None
    try:
        return float(texto.replace(".", "").replace(",", ".").strip()) * 1000
    except:
        return None


def extrair_tabela(ticker, ano_ref):
    url = f"{BASE}/{PAGINA}?cod_negociacao={ticker}&ano_dem={ano_ref}&mes_dia_dem=1231&consolid=2&tipocontabil=2"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}
    except Exception as e:
        print(f"    ❌ Erro de conexão: {e}")
        return {}

    soup   = BeautifulSoup(resp.text, "html.parser")
    tab    = soup.find("table")
    if not tab:
        return {}

    linhas = tab.find_all("tr")
    if not linhas:
        return {}

    cabecalho = [td.get_text(strip=True) for td in linhas[0].find_all(["th", "td"])]
    anos_cols = []
    for i, txt in enumerate(cabecalho):
        match = re.findall(r'\d{4}', txt)
        if match:
            anos_cols.append((i, int(match[-1])))

    resultado = {}
    ja_salvos = {}   # {(ano, campo): True} — evita sobrescrever campos únicos

    for linha in linhas:
        cols = [td.get_text(strip=True) for td in linha.find_all(["td", "th"])]
        if len(cols) < 3:
            continue
        codigo = cols[0].strip()
        if codigo not in MAPA:
            continue

        campo = MAPA[codigo]
        for idx_col, ano in anos_cols:
            if idx_col >= len(cols):
                continue
            chave = (ano, campo)
            # Para campos únicos: só usa o primeiro código que retornar valor
            if campo in CAMPO_UNICO and chave in ja_salvos:
                continue
            val = parse_valor(cols[idx_col])
            resultado.setdefault(ano, {})[campo] = val
            if campo in CAMPO_UNICO and val is not None:
                ja_salvos[chave] = True

    return resultado


def upsert(conn, ticker, ano, campos):
    upsert_financeiro(conn, ticker, ano, FONTE, campos)


def coletar(ticker):
    print(f"  💸 Fluxo de Caixa {ticker}...")
    conn = sqlite3.connect(DB)

    for ano_ref in ANOS_REF:
        dados = extrair_tabela(ticker, ano_ref)
        if not dados:
            continue

        gravados = []
        pulados  = []

        for ano, campos in sorted(dados.items()):
            if is_validado(conn, ticker, "fluxo", ano):
                pulados.append(ano)
                continue
            mapa = {campo: val for campo, val in campos.items() if val is not None}
            if mapa:
                upsert(conn, ticker, ano, mapa)

                # Calcula FCL = FCO + CAPEX
                fco   = mapa.get("fco")
                capex = mapa.get("capex")
                if fco is not None and capex is not None:
                    upsert(conn, ticker, ano, {"fcl": fco + capex})

                da = mapa.get("depreciacao_amortizacao")
                capex_txt = f" | CAPEX: R$ {capex:,.0f}" if capex else ""
                da_txt    = f" | D&A: R$ {da:,.0f}"      if da    else ""
                print(f"     {ano} → FCO: R$ {fco:,.0f}{capex_txt}{da_txt}" if fco else f"     {ano} → sem FCO")
                gravados.append(ano)

        if pulados:
            print(f"     ({ano_ref}) validado, pulando anos: {sorted(pulados)}")
        if gravados:
            print(f"     ({ano_ref}) gravados: {sorted(gravados)}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import banco
 