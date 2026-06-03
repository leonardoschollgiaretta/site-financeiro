"""
Estatística descritiva para séries de câmbio.

Foco em:
- Tendência central (média, mediana, moda)
- Dispersão (desvio padrão, IQR)
- Volatilidade (anualizada, rolling)
- Retornos (log e simples)
"""

import numpy as np
import pandas as pd


def add_returns(df: pd.DataFrame, price_col: str = "Close") -> pd.DataFrame:
    """
    Adiciona colunas de retornos.

    Args:
        df: DataFrame com coluna de preço
        price_col: nome da coluna de preço

    Returns:
        DataFrame com colunas extras: simple_return, log_return
    """
    df = df.copy()
    df["simple_return"] = df[price_col].pct_change()
    df["log_return"] = np.log(df[price_col] / df[price_col].shift(1))
    return df


def descriptive_stats(series: pd.Series) -> pd.Series:
    """
    Estatísticas descritivas básicas + assimetria e curtose.
    """
    return pd.Series({
        "count": series.count(),
        "mean": series.mean(),
        "median": series.median(),
        "std": series.std(),
        "min": series.min(),
        "max": series.max(),
        "q25": series.quantile(0.25),
        "q75": series.quantile(0.75),
        "iqr": series.quantile(0.75) - series.quantile(0.25),
        "skew": series.skew(),
        "kurtosis": series.kurtosis(),
    })


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Volatilidade anualizada (assume 252 dias úteis).

    Para dados diários: 252
    Para dados semanais: 52
    Para dados mensais: 12
    """
    return returns.std() * np.sqrt(periods_per_year)


def rolling_volatility(
    returns: pd.Series,
    window: int = 30,
    periods_per_year: int = 252,
) -> pd.Series:
    """
    Volatilidade móvel anualizada.
    """
    return returns.rolling(window).std() * np.sqrt(periods_per_year)


def drawdown(prices: pd.Series) -> pd.DataFrame:
    """
    Calcula drawdown da série de preços.

    Returns:
        DataFrame com colunas: price, peak, drawdown
    """
    peak = prices.cummax()
    dd = (prices - peak) / peak
    return pd.DataFrame({"price": prices, "peak": peak, "drawdown": dd})


def summary_report(df: pd.DataFrame, price_col: str = "Close") -> dict:
    """
    Relatório completo de uma série de câmbio.

    Returns:
        dict com todas as estatísticas
    """
    df = add_returns(df, price_col)
    log_ret = df["log_return"].dropna()

    return {
        "preco": descriptive_stats(df[price_col]),
        "retorno_log": descriptive_stats(log_ret),
        "volatilidade_anualizada": annualized_volatility(log_ret),
        "max_drawdown": drawdown(df[price_col])["drawdown"].min(),
        "periodo": f"{df.index.min().date()} a {df.index.max().date()}",
        "n_observacoes": len(df),
    }
