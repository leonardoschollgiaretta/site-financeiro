"""
Coletor Dividendos -- Acoes Americanas
Fonte: yfinance

Armazena cada pagamento individualmente em dividendos_pagamentos
(mesmo padrao do BR — agrupamento por ano fica para o relatorio).

yfinance retorna uma Series com index=data e value=valor por acao em USD.
Nao temos data_com / data_pgto separados (o yfinance da apenas a ex-dividend
date), entao usamos a mesma data para data_com e data_pgto.
Tipo: sempre 'Dividendo' (nao ha distincao de JCP nos EUA).
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
    print(f"  💰 Dividendos {ticker}...")
    try:
        acao = yf.Ticker(ticker)
        divs = acao.dividends
    except Exception as e:
        print(f"     ❌ Erro yfinance: {e}")
        return

    if divs is None or len(divs) == 0:
        print(f"     ℹ️  Sem historico de dividendos (ex: TSLA, META, GOOGL)")
        return

    conn = sqlite3.connect(DB)

    if is_validado(conn, ticker, "dividendos", 0):
        print(f"     Dividendos validados, pulando")
        conn.close()
        return

    try:
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
    except (TypeError, AttributeError):
        divs.index = pd.to_datetime(divs.index)

    por_ano = {}
    for data, valor in divs.items():
        ano = int(data.year)
        if is_validado(conn, ticker, "dividendos", ano):
            continue
        data_iso = data.strftime("%Y-%m-%d")
        por_ano.setdefault(ano, []).append((data_iso, float(valor)))

    inseridos = 0
    for ano, items in por_ano.items():
        conn.execute(
            "DELETE FROM dividendos_pagamentos WHERE ticker=? AND substr(data_com,1,4)=?",
            (ticker, str(ano))
        )
        for data_iso, valor in items:
            conn.execute("""
                INSERT INTO dividendos_pagamentos
                    (ticker, data_com, data_pgto, tipo, valor, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticker, data_iso, data_iso, "Dividendo", valor, agora()))
            inseridos += 1

    conn.commit()

    conn.execute(
        "UPDATE empresas SET dividendos_coletados_em=? WHERE ticker=?",
        (agora(), ticker)
    )
    conn.commit()
    conn.close()

    print(f"     ✅ {inseridos} pagamento(s) gravados no banco")
    _resumo(ticker)


def _resumo(ticker):
    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT substr(data_com, 1, 4) as ano,
               SUM(valor)              as total
        FROM dividendos_pagamentos
        WHERE ticker=?
        GROUP BY ano
        ORDER BY ano
    """, (ticker,)).fetchall()
    conn.close()
    for ano, total in rows:
        print(f"     {ano}  $ {total:.4f}/acao")


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
    print("\n✅ Dividendos US finalizado!")
