import yfinance as yf
import sqlite3
import os
from collections import defaultdict

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

def coletar_dividendos(ticker):
    """Busca histórico de dividendos via yfinance e agrupa por ano"""
    ticker_yf = ticker if ticker.endswith(".SA") else ticker + ".SA"
    acao = yf.Ticker(ticker_yf)
    divs = acao.dividends

    if divs is None or len(divs) == 0:
        return {}

    por_ano = defaultdict(float)
    for data, valor in divs.items():
        try:
            ano = data.year
        except:
            ano = int(str(data)[:4])
        por_ano[ano] += float(valor)

    return dict(por_ano)

def salvar_dividendos(ticker, por_ano):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for ano, total in por_ano.items():
        c.execute("""
            INSERT OR REPLACE INTO dividendos_anuais
            (ticker, ano, fonte, dividendo_por_acao)
            VALUES (?, ?, ?, ?)
        """, (ticker, ano, "yfinance", total))
    conn.commit()
    conn.close()

def coletar_empresa(ticker):
    print(f"\n💰 Coletando dividendos {ticker}...")
    divs = coletar_dividendos(ticker)

    if divs:
        anos = sorted(divs.keys())
        print(f"  ✅ {len(divs)} anos ({min(anos)}-{max(anos)})")
        for ano in anos[-5:]:  # mostra últimos 5
            print(f"     {ano}: R$ {divs[ano]:.4f} por ação")
        salvar_dividendos(ticker, divs)
    else:
        print("  ⚠️ Sem dados de dividendos")

if __name__ == "__main__":
    import banco
    banco.criar_banco()

    tickers = ["GRND3", "ITSA4", "PETR4", "VALE3"]

    for ticker in tickers:
        coletar_empresa(ticker)

    print("\n✅ Coleta de dividendos finalizada!")
