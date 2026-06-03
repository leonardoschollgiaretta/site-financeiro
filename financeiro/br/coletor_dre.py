"""
Coletor DRE — Ações Brasileiras
Fonte: Investsite.com.br (dados CVM oficiais)
Campos: receita_liquida, custo_receita, lucro_bruto, despesas_operacionais,
        ebit, receitas_financeiras, despesas_financeiras, resultado_financeiro,
        ebt, ir_csll, lucro_liquido
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
PAGINA = "demonstracao_resultado.php"

ANOS_REF = [2022, 2025]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": BASE,
}

MAPA = {
    "3.01":    "receita_liquida",
    "3.02":    "custo_receita",
    "3.03":    "lucro_bruto",
    "3.04":    "despesas_operacionais",
    "3.05":    "ebit",
    "3.06.01": "receitas_financeiras",
    "3.06.02": "despesas_financeiras",
    "3.06":    "resultado_financeiro",
    "3.07":    "ebt",
    "3.08":    "ir_csll",
    "3.11":    "lucro_liquido",
}


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
    for linha in linhas[1:]:
        cols = [td.get_text(strip=True) for td in linha.find_all(["td", "th"])]
        if len(cols) < 3:
            continue
        codigo = cols[0].strip()
        if codigo not in MAPA:
            continue
        for idx_col, ano in anos_cols:
            if idx_col < len(cols):
                val = parse_valor(cols[idx_col])
                resultado.setdefault(ano, {})[codigo] = val

    return resultado


def upsert(conn, ticker, ano, campos):
    upsert_financeiro(conn, ticker, ano, FONTE, campos)


def coletar(ticker):
    print(f"  📊 DRE {ticker}...")
    conn = sqlite3.connect(DB)

    for ano_ref in ANOS_REF:
        dados = extrair_tabela(ticker, ano_ref)
        if not dados:
            continue

        gravados = []
        pulados  = []

        for ano, codigos in sorted(dados.items()):
            if is_validado(conn, ticker, "dre", ano):
                pulados.append(ano)
                continue
            mapa = {MAPA[cod]: val for cod, val in codigos.items() if cod in MAPA and val is not None}
            if mapa:
                upsert(conn, ticker, ano, mapa)
                rec = codigos.get("3.01")
                luc = codigos.get("3.11")
                sga = codigos.get("3.04")
                luc_txt = f" | Lucro: R$ {luc:,.0f}" if luc else ""
                sga_txt = f" | SG&A: R$ {sga:,.0f}" if sga else ""
                print(f"     {ano} → Receita: R$ {rec:,.0f}{luc_txt}{sga_txt}" if rec else f"     {ano} → sem receita")
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
    banco.criar_banco()

    import pandas as pd
    TICKERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tickers.xlsx")
    df = pd.read_excel(TICKERS_FILE, sheet_name="Tickers", header=2)
    df.columns = [c.strip() for c in df.columns]
    tickers = [str(t).strip().upper() for t in df.get("TICKER_BR", []) if pd.notna(t) and str(t).strip()]

    print(f"  {len(tickers)} ticker(s) encontrados em tickers.xlsx\n")
    for t in tickers:
        try:
            coletar(t)
        except Exception as e:
            print(f"  ❌ {t} — erro: {e}")
    print("\n✅ DRE BR finalizado!")
