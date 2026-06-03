"""
Coletor Fluxo de Caixa -- Acoes Americanas
Fonte: yfinance (cashflow)

Campos: fco, fci, fcf_financiamento, capex, venda_ativos, aquisicoes,
        captacoes, pagamento_dividas, recompra_acoes, dividendos_pagos,
        variacao_caixa, caixa_inicial, caixa_final, fcl

Diferencas vs BR:
  - Valores em USD, em unidade absoluta (NAO multiplicar por 1000).
  - FCL ja vem do yfinance ('Free Cash Flow') — usamos direto quando disponivel,
    senao calculamos como fco + capex (capex eh negativo).
  - Capex no yfinance ja vem com sinal negativo (saida de caixa), igual ao BR.
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
    "fco":               ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "fci":               ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"],
    "fcf_financiamento": ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"],

    "capex":             ["Capital Expenditure", "Net PPE Purchase And Sale"],
    "venda_ativos":      ["Sale Of Investment", "Sale Of Business"],
    "aquisicoes":        ["Purchase Of Business", "Net Business Purchase And Sale"],

    "captacoes":         ["Issuance Of Debt", "Long Term Debt Issuance"],
    "pagamento_dividas": ["Repayment Of Debt", "Long Term Debt Payments"],
    "recompra_acoes":    ["Repurchase Of Capital Stock", "Common Stock Payments"],
    "dividendos_pagos":  ["Cash Dividends Paid", "Common Stock Dividend Paid"],

    "variacao_caixa":    ["Changes In Cash", "Change In Cash"],
    "caixa_inicial":     ["Beginning Cash Position"],
    "caixa_final":       ["End Cash Position"],

    "fcl":               ["Free Cash Flow"],
}


def _val(df, col, nomes):
    for nome in nomes:
        if nome in df.index:
            v = df.loc[nome, col]
            if pd.notna(v):
                return float(v)
    return None


def coletar(ticker):
    print(f"  💸 Fluxo de Caixa {ticker}...")
    try:
        acao = yf.Ticker(ticker)
        cf = acao.cashflow
    except Exception as e:
        print(f"     ❌ Erro yfinance: {e}")
        return

    if cf is None or cf.empty:
        print(f"     ⚠️  Sem dados de fluxo de caixa")
        return

    conn = sqlite3.connect(DB)

    gravados = []
    pulados  = []

    for col in cf.columns:
        ano = int(col.year)
        if is_validado(conn, ticker, "fluxo", ano):
            pulados.append(ano)
            continue

        mapa = {}
        for coluna_db, nomes in MAPA.items():
            v = _val(cf, col, nomes)
            if v is not None:
                mapa[coluna_db] = v

        # Fallback FCL
        if "fcl" not in mapa:
            fco   = mapa.get("fco")
            capex = mapa.get("capex")
            if fco is not None and capex is not None:
                mapa["fcl"] = fco + capex

        if mapa:
            upsert_financeiro(conn, ticker, ano, FONTE, mapa)
            fco   = mapa.get("fco")
            capex = mapa.get("capex")
            capex_txt = f" | CAPEX: $ {capex:,.0f}" if capex else ""
            print(f"     {ano} → FCO: $ {fco:,.0f}{capex_txt}" if fco else f"     {ano} → sem FCO")
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
    print("\n✅ Fluxo US finalizado!")
