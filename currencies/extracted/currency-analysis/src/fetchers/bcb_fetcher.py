"""
Fetcher para Banco Central do Brasil (PTAX).

Vantagens:
- Cotações oficiais (PTAX) usadas pelo governo brasileiro
- Histórico longo e gratuito
- Sem necessidade de chave

Códigos SGS úteis:
- 1: USD venda
- 21619: EUR venda
- 21621: CHF venda
- 21620: GBP venda
"""

from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import requests


RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SGS_CODES = {
    "USD": 1,
    "EUR": 21619,
    "GBP": 21620,
    "CHF": 21621,
}


def fetch_ptax(
    currency: str = "USD",
    start_date: str | None = None,
    end_date: str | None = None,
    years_back: int = 5,
    save: bool = True,
) -> pd.DataFrame:
    """
    Busca série PTAX do Banco Central.

    Args:
        currency: USD, EUR, GBP, CHF
        start_date: 'dd/mm/yyyy' (se None, usa years_back)
        end_date: 'dd/mm/yyyy' (default: hoje)
        years_back: quantos anos pra trás se start_date não informado
        save: salva CSV em data/raw/

    Returns:
        DataFrame com colunas date, value
    """
    if currency not in SGS_CODES:
        raise ValueError(f"Moeda {currency} não suportada. Opções: {list(SGS_CODES)}")

    code = SGS_CODES[currency]

    if end_date is None:
        end_date = datetime.now().strftime("%d/%m/%Y")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365 * years_back)).strftime("%d/%m/%Y")

    url = (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
        f"?formato=json&dataInicial={start_date}&dataFinal={end_date}"
    )

    print(f"Buscando PTAX {currency} de {start_date} a {end_date}...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    df = pd.DataFrame(response.json())
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"])
    df = df.rename(columns={"data": "date", "valor": "value"}).set_index("date")

    if save:
        timestamp = datetime.now().strftime("%Y%m%d")
        path = RAW_DIR / f"ptax_{currency}_BRL_{timestamp}.csv"
        df.to_csv(path)
        print(f"Salvo em: {path}")

    return df


if __name__ == "__main__":
    df = fetch_ptax("USD", years_back=2)
    print(df.tail())
    print(f"\n{len(df)} observações")
