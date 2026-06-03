"""
Coletor Balanco Patrimonial -- Acoes Americanas
Fonte: yfinance (balance_sheet)

Ativo:  ativo_total, ativo_circulante, caixa, contas_receber, estoques,
        ativo_nao_circulante, investimentos, imobilizado, intangivel
Passivo: passivo_circulante, fornecedores, emprestimos_cp,
         passivo_nao_circulante, emprestimos_lp, debentures,
         capital_social, reservas_lucro, lucros_acumulados, patrimonio_liquido,
         divida_bruta, divida_liquida

Diferencas vs BR:
  - Valores em USD, em unidade absoluta (NAO multiplicar por 1000).
  - GAAP americano nao separa debentures dos emprestimos LP — gravamos tudo
    em emprestimos_lp e deixamos debentures NULL.
  - Caixa: yfinance ja consolida 'Cash And Cash Equivalents And Short Term
    Investments' que equivale a caixa + aplicacoes financeiras CP do BR.
  - Divida bruta e liquida vem direto do yfinance ('Total Debt', 'Net Debt'),
    nao precisa calcular.
"""
import sqlite3
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yfinance as yf
import pandas as pd
from db_utils import upsert_financeiro
from db_validacao import is_validado

DB    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")
FONTE = "yfinance"

MAPA = {
    "ativo_total":            ["Total Assets"],
    "ativo_circulante":       ["Current Assets"],
    "caixa":                  ["Cash Cash Equivalents And Short Term Investments",
                               "Cash And Cash Equivalents"],
    "contas_receber":         ["Accounts Receivable", "Receivables", "Net Receivables"],
    "estoques":               ["Inventory"],
    "ativo_nao_circulante":   ["Total Non Current Assets"],
    "investimentos":          ["Investments And Advances",
                               "Long Term Equity Investment"],
    "imobilizado":            ["Net PPE", "Gross PPE"],
    "intangivel":             ["Goodwill And Other Intangible Assets",
                               "Other Intangible Assets",
                               "Goodwill"],

    "passivo_circulante":     ["Current Liabilities"],
    "fornecedores":           ["Accounts Payable", "Payables"],
    "emprestimos_cp":         ["Current Debt", "Current Debt And Capital Lease Obligation"],
    "passivo_nao_circulante": ["Total Non Current Liabilities Net Minority Interest"],
    "emprestimos_lp":         ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],

    "capital_social":         ["Common Stock", "Capital Stock"],
    "reservas_lucro":         ["Additional Paid In Capital"],
    "lucros_acumulados":      ["Retained Earnings"],
    "patrimonio_liquido":     ["Stockholders Equity",
                               "Common Stock Equity",
                               "Total Equity Gross Minority Interest"],

    "divida_bruta":           ["Total Debt"],
    "divida_liquida":         ["Net Debt"],
}


def _val(df, col, nomes):
    for nome in nomes:
        if nome in df.index:
            v = df.loc[nome, col]
            if pd.notna(v):
                return float(v)
    return None


def coletar(ticker):
    print(f"  🏦 Balanco {ticker}...")
    try:
        acao = yf.Ticker(ticker)
        bal = acao.balance_sheet
    except Exception as e:
        print(f"     ❌ Erro yfinance: {e}")
        return

    if bal is None or bal.empty:
        print(f"     ⚠️  Sem dados de balanco")
        return

    conn = sqlite3.connect(DB)

    gravados = []
    pulados  = []

    for col in bal.columns:
        ano = int(col.year)
        if is_validado(conn, ticker, "balanco", ano):
            pulados.append(ano)
            continue

        mapa = {}
        for coluna_db, nomes in MAPA.items():
            v = _val(bal, col, nomes)
            if v is not None:
                mapa[coluna_db] = v

        # Fallback: se yfinance nao entregou divida_liquida mas temos bruta + caixa
        if "divida_liquida" not in mapa:
            db = mapa.get("divida_bruta")
            cx = mapa.get("caixa")
            if db is not None and cx is not None:
                mapa["divida_liquida"] = db - cx

        if mapa:
            upsert_financeiro(conn, ticker, ano, FONTE, mapa)
            pl = mapa.get("patrimonio_liquido")
            at = mapa.get("ativo_total")
            pl_txt = f" | PL: $ {pl:,.0f}" if pl else ""
            print(f"     {ano} → Ativo: $ {at:,.0f}{pl_txt}" if at else f"     {ano} → sem ativo total")
            gravados.append(ano)

    if pulados:
        print(f"     validado, pulando anos: {sorted(pulados)}")
    if gravados:
        print(f"     gravados: {sorted(gravados)}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    import banco
    banco.criar_banco()

    TICKERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tickers.xlsx")
    df = pd.read_excel(TICKERS_FILE, sheet_name="Tickers", header=2)
    df.columns = [c.strip() for c in df.columns]
    tickers = [str(t).strip().upper() for t in df.get("TICKER_US", []) if pd.notna(t) and str(t).strip()]

    print(f"  {len(tickers)} ticker(s) US encontrados em tickers.xlsx\n")
    for t in tickers:
        try:
            coletar(t)
        except Exception as e:
            print(f"  ❌ {t} — erro: {e}")
    print("\n✅ Balanco US finalizado!")
