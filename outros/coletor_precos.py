import yfinance as yf
import sqlite3
import os
import pandas as pd

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

def coletar_precos(ticker):
    """Busca histórico de preços via yfinance e agrupa por ano"""
    ticker_yf = ticker if ticker.endswith(".SA") else ticker + ".SA"
    acao = yf.Ticker(ticker_yf)
    hist = acao.history(period="max")

    if hist is None or hist.empty:
        return {}

    # Corrige timezone se necessário
    try:
        hist.index = hist.index.tz_localize(None)
    except:
        hist.index = pd.to_datetime(hist.index).tz_localize(None)

    hist["ano"] = hist.index.year

    por_ano = {}
    for ano, grupo in hist.groupby("ano"):
        por_ano[ano] = {
            "preco_min":   round(grupo["Low"].min(), 4),
            "preco_max":   round(grupo["High"].max(), 4),
            "preco_medio": round(grupo["Close"].mean(), 4),
        }

    return por_ano

def salvar_precos(ticker, por_ano):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for ano, vals in por_ano.items():
        c.execute("""
            INSERT OR REPLACE INTO precos_anuais
            (ticker, ano, fonte, preco_min, preco_max, preco_medio)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker, ano, "yfinance",
              vals["preco_min"], vals["preco_max"], vals["preco_medio"]))
    conn.commit()
    conn.close()

def coletar_empresa(ticker):
    print(f"\n📈 Coletando preços {ticker}...")
    precos = coletar_precos(ticker)

    if precos:
        anos = sorted(precos.keys())
        print(f"  ✅ {len(precos)} anos ({min(anos)}-{max(anos)})")
        for ano in anos[-5:]:
            p = precos[ano]
            print(f"     {ano}: min R${p['preco_min']:.2f} | max R${p['preco_max']:.2f} | médio R${p['preco_medio']:.2f}")
        salvar_precos(ticker, precos)
    else:
        print("  ⚠️ Sem dados de preços")

if __name__ == "__main__":
    import banco
    banco.criar_banco()

    tickers = ["GRND3", "ITSA4", "PETR4", "VALE3"]

    for ticker in tickers:
        coletar_empresa(ticker)

    print("\n✅ Coleta de preços finalizada!")
