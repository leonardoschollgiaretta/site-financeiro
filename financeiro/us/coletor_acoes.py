"""
Coletor Quantidade de Acoes -- Acoes Americanas
Fonte: yfinance

Diferencas vs BR:
  - Empresas americanas geralmente tem apenas uma classe de acao negociada
    (ou classes A/B/C como GOOGL/GOOG, mas tratadas como tickers separados).
  - Nao ha distincao ON/PN nem tesouraria/free explicita no yfinance gratuito.
  - Usamos 'sharesOutstanding' do .info como total e gravamos como acoes_on.
  - Para historico anual, yfinance expoe 'get_shares_full()' (quando disponivel).

Campos preenchidos: acoes_on (total), acoes_total (igual a acoes_on).
Nao preenchemos acoes_pn / tesouraria / free (ficam NULL).
"""
import sqlite3
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yfinance as yf
import pandas as pd
from db_utils import agora
from db_validacao import is_validado

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")


def coletar(ticker):
    print(f"  Acoes {ticker}...")
    try:
        acao = yf.Ticker(ticker)
        info = acao.info or {}
    except Exception as e:
        print(f"     ❌ Erro yfinance: {e}")
        return

    snap_total = info.get("sharesOutstanding")
    if snap_total is None:
        print(f"     ⚠️  sharesOutstanding nao disponivel")
        return
    snap_total = int(snap_total)

    historico = {}
    try:
        shares_full = acao.get_shares_full(start="2019-01-01")
        if shares_full is not None and not shares_full.empty:
            shares_full.index = pd.to_datetime(shares_full.index).tz_localize(None)
            shares_full = shares_full.sort_index()
            for ano, grupo in shares_full.groupby(shares_full.index.year):
                historico[int(ano)] = int(grupo.iloc[-1])
    except Exception as e:
        print(f"     ℹ️  Historico anual indisponivel ({e}) — usando snapshot")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    if historico:
        for ano, total in historico.items():
            if is_validado(conn, ticker, "acoes", ano):
                print(f"     {ano}: validado, pulando")
                continue
            c.execute("""
                INSERT OR REPLACE INTO acoes_anuais
                    (ticker, ano, acoes_on, acoes_pn, acoes_total, acoes_tesouraria, acoes_free, atualizado_em)
                VALUES (?, ?, ?, NULL, ?, NULL, ?, ?)
            """, (ticker, ano, total, total, total, agora()))
            print(f"     {ano}: Total = {total:,}")
    else:
        from datetime import datetime
        ano_atual = datetime.now().year
        if not is_validado(conn, ticker, "acoes", ano_atual):
            c.execute("""
                INSERT OR REPLACE INTO acoes_anuais
                    (ticker, ano, acoes_on, acoes_pn, acoes_total, acoes_tesouraria, acoes_free, atualizado_em)
                VALUES (?, ?, ?, NULL, ?, NULL, ?, ?)
            """, (ticker, ano_atual, snap_total, snap_total, snap_total, agora()))
            print(f"     {ano_atual} (snapshot): Total = {snap_total:,}")

    c.execute("""
        UPDATE empresas SET
            acoes_on             = ?,
            acoes_pn             = NULL,
            acoes_total          = ?,
            acoes_tesouraria     = NULL,
            acoes_free           = ?,
            ticker_on            = ?,
            ticker_pn            = NULL,
            acoes_atualizadas_em = ?
        WHERE ticker = ?
    """, (snap_total, snap_total, snap_total, ticker, agora(), ticker))

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
    print("\n✅ Acoes US finalizado!")
