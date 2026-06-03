"""
coletar.py -- Coleta diaria de cotacoes dos pares definidos em PARES.

Comportamento (modo (a)):
  - Verifica a ultima data ja gravada no banco para cada par
  - Baixa do Yahoo apenas do dia seguinte ate hoje
  - Se for primeira execucao para um par, baixa 10 anos

Uso:
  python multi_par/coletar.py

Pode rodar 1x por dia.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banco import criar_banco, conectar


# Mapeamento: nome curto -> ticker do Yahoo
PARES = {
    "USDBRL": "USDBRL=X",
    "USDCHF": "USDCHF=X",
    "USDCNY": "USDCNY=X",
    "EURUSD": "EURUSD=X",
    "CNYBRL": "CNYBRL=X",
}

PERIODO_INICIAL = "10y"   # primeira coleta


def ultima_data(conn, par):
    """Retorna a ultima data (str) ja gravada no banco para o par. None se vazio."""
    row = conn.execute(
        "SELECT MAX(data) FROM cotacoes WHERE par=?", (par,)
    ).fetchone()
    return row[0] if row and row[0] else None


def baixar_yahoo(ticker, start=None, period=None):
    """Baixa cotacoes do Yahoo. Se start informado, usa start->hoje. Senao usa period."""
    try:
        if start:
            df = yf.download(ticker, start=start, progress=False, auto_adjust=False)
        else:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=False)
    except Exception as e:
        print(f"    erro yfinance: {e}")
        return None

    if df is None or df.empty:
        return None

    # yfinance pode retornar MultiIndex nas colunas
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Normaliza
    df = df[["Close"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def gravar_cotacoes(conn, par, df):
    """Grava ou atualiza cotacoes (INSERT OR REPLACE)."""
    if df is None or df.empty:
        return 0
    rows = []
    for idx, row in df.iterrows():
        data_str = idx.strftime("%Y-%m-%d")
        preco = float(row["Close"])
        rows.append((par, data_str, preco))
    conn.executemany(
        "INSERT OR REPLACE INTO cotacoes (par, data, preco) VALUES (?, ?, ?)",
        rows
    )
    conn.commit()
    return len(rows)


def coletar_par(conn, par, ticker):
    print(f"\n[{par}]  ticker={ticker}")
    ult = ultima_data(conn, par)

    if ult is None:
        print(f"  primeira coleta -> baixando {PERIODO_INICIAL}")
        df = baixar_yahoo(ticker, period=PERIODO_INICIAL)
    else:
        # Comeca um dia apos a ultima data
        ult_dt = datetime.strptime(ult, "%Y-%m-%d")
        proximo = (ult_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        hoje = datetime.now().strftime("%Y-%m-%d")
        if proximo > hoje:
            print(f"  ja atualizado (ultimo dia: {ult})")
            return 0
        print(f"  ultimo dia: {ult}  -> baixando de {proximo} ate hoje")
        df = baixar_yahoo(ticker, start=proximo)

    if df is None or df.empty:
        print(f"  sem dados novos")
        return 0

    n = gravar_cotacoes(conn, par, df)
    print(f"  {n} cotacao(es) gravada(s)")
    return n


def atualizar_meta(conn, chave, valor):
    conn.execute(
        "INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?)",
        (chave, valor)
    )
    conn.commit()


def main():
    print("=" * 60)
    print("  COLETA DIARIA DE COTACOES")
    print("=" * 60)

    criar_banco()
    conn = conectar()

    total = 0
    for par, ticker in PARES.items():
        try:
            total += coletar_par(conn, par, ticker)
        except Exception as e:
            print(f"  ERRO em {par}: {e}")

    atualizar_meta(conn, "ultima_coleta", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    conn.close()

    print(f"\n{total} cotacao(es) novas no total.")
    print("=" * 60)


if __name__ == "__main__":
    main()
