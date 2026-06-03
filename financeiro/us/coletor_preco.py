"""
Coletor Precos Anuais -- Acoes Americanas
Fonte: yfinance
Campos: preco_min, preco_max, preco_medio por ano

Diferencas vs BR:
  - Ticker sem sufixo (.SA so vale para B3)
  - Valores em USD
"""
import sqlite3
import os
import sys
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yfinance as yf
import pandas as pd
from db_utils import agora
from db_validacao import is_validado

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")

ANO_INICIO = 2020


def coletar(ticker):
    print(f"  Precos {ticker}...")
    hoje = date.today().isoformat()
    try:
        acao = yf.Ticker(ticker)
        hist = acao.history(start=f"{ANO_INICIO}-01-01", end=hoje)
        if hist.empty:
            print(f"     ⚠️  Sem historico")
            return
    except Exception as e:
        print(f"     ❌ Erro yfinance: {e}")
        return

    hist.index = pd.to_datetime(hist.index)
    hist["ano"] = hist.index.year

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    for ano, grupo in hist.groupby("ano"):
        if is_validado(conn, ticker, "precos", ano):
            print(f"     {ano}: validado, pulando")
            continue
        pmin   = round(float(grupo["Low"].min()), 2)
        pmax   = round(float(grupo["High"].max()), 2)
        pmedio = round(float(grupo["Close"].mean()), 2)

        c.execute("""
            INSERT OR REPLACE INTO precos_anuais (ticker, ano, preco_min, preco_max, preco_medio, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker, ano, pmin, pmax, pmedio, agora()))
        print(f"     {ano} → Min: $ {pmin} | Max: $ {pmax} | Medio: $ {pmedio}")

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
    print("\n✅ Precos US finalizado!")
