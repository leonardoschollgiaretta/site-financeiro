"""
Fetcher para Yahoo Finance via yfinance.

Pares mais usados:
- USDBRL=X (Dolar/Real)
- EURBRL=X (Euro/Real)
- CHFBRL=X (Franco Suiço/Real)
- EURUSD=X (Euro/Dolar)
- GBPUSD=X (Libra/Dolar)
"""

from pathlib import Path
from datetime import datetime
import pandas as pd
import yfinance as yf


RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def fetch_currency_history(
    ticker: str,
    period: str = "5y",
    interval: str = "1d",
    save: bool = True,
) -> pd.DataFrame:
    """
    Busca histórico de uma moeda no Yahoo Finance.

    Args:
        ticker: ex. "USDBRL=X", "EURUSD=X"
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        save: se True, salva CSV em data/raw/

    Returns:
        DataFrame com colunas Open, High, Low, Close, Volume
    """
    print(f"Buscando {ticker} ({period}, {interval})...")
    df = yf.download(ticker, period=period, interval=interval, progress=False)

    if df.empty:
        raise ValueError(f"Sem dados retornados para {ticker}")

    # yfinance às vezes retorna MultiIndex nas colunas; achata
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.index.name = "date"

    if save:
        clean_ticker = ticker.replace("=X", "").replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d")
        path = RAW_DIR / f"{clean_ticker}_{period}_{timestamp}.csv"
        df.to_csv(path)
        print(f"Salvo em: {path}")

    return df


def fetch_multiple(tickers: list[str], period: str = "5y") -> dict[str, pd.DataFrame]:
    """
    Busca várias moedas de uma vez.

    Returns:
        dict {ticker: DataFrame}
    """
    return {t: fetch_currency_history(t, period=period) for t in tickers}


if __name__ == "__main__":
    # Teste rápido
    df = fetch_currency_history("USDBRL=X", period="1y")
    print(df.tail())
