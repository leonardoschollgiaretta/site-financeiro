"""
coletor_fechamento.py -- Fechamento do dia anterior para tickers US no banco.
Atualiza a tabela preco_atual com o ultimo fechamento disponivel via yfinance.

Diferencas vs BR:
  - Ticker sem sufixo (.SA so vale para B3)
  - Filtra empresas com moeda='USD' (ou diferente de 'BRL')
"""
import sqlite3
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yfinance as yf
from db_utils import agora

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")


def buscar_tickers_us():
    """Tickers US ativos (exclui empresas marcadas como DESCONSIDERAR)."""
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """SELECT ticker FROM empresas
           WHERE moeda != 'BRL'
             AND (considerar IS NULL OR considerar != 'DESCONSIDERAR')
           ORDER BY ticker"""
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def coletar_fechamento(ticker):
    try:
        acao = yf.Ticker(ticker)
        hist = acao.history(period="5d")
        if hist.empty or len(hist) < 1:
            print(f"  ⚠️  {ticker} — sem historico")
            return None

        ultimo   = hist.iloc[-1]
        anterior = hist.iloc[-2] if len(hist) >= 2 else None

        preco     = round(float(ultimo["Close"]), 2)
        data_fech = str(hist.index[-1].date())
        variacao  = None
        if anterior is not None:
            variacao = round((preco - float(anterior["Close"])) / float(anterior["Close"]) * 100, 2)

        return preco, data_fech, variacao

    except Exception as e:
        print(f"  ❌ {ticker} — erro: {e}")
        return None


def salvar(ticker, preco, data_fech, variacao):
    conn = sqlite3.connect(DB)
    conn.execute("""
        INSERT OR REPLACE INTO preco_atual (ticker, preco, data_fechamento, variacao_pct, atualizado_em)
        VALUES (?, ?, ?, ?, ?)
    """, (ticker, preco, data_fech, variacao, agora()))
    conn.commit()
    conn.close()


def rodar():
    import banco
    banco.criar_banco()

    tickers = buscar_tickers_us()
    if not tickers:
        print("⚠️  Nenhum ticker US no banco.")
        return

    print(f"\n📈 Atualizando fechamento de {len(tickers)} ticker(s) US...\n")
    ok, erro = 0, 0

    for ticker in tickers:
        resultado = coletar_fechamento(ticker)
        if resultado:
            preco, data_fech, variacao = resultado
            salvar(ticker, preco, data_fech, variacao)
            var_txt = f"  {variacao:+.2f}%" if variacao is not None else ""
            print(f"  ✅ {ticker:<8} $ {preco:.2f}{var_txt}  [{data_fech}]")
            ok += 1
        else:
            erro += 1

    print(f"\n  Concluido: {ok} OK | {erro} erro(s)")


if __name__ == "__main__":
    rodar()
