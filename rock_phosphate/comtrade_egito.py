"""UN Comtrade: exportacoes do Egito de rocha fosfatica (HS 2510) por destino.

Endpoint publico (sem chave):
  https://comtradeapi.un.org/public/v1/preview/C/A/HS?...

Limite anonimo: 100 calls/dia, max 500 linhas por call.
Para mais que isso, registre em https://uncomtrade.org/ e use ?subscription-key=...

Output:
  data/comtrade_eg_2510.csv  - 1 linha por ano+destino
"""
from __future__ import annotations
import os, time
from pathlib import Path
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(exist_ok=True)

# UN Comtrade Public API
URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

# Egypt reporter code = 818
EGYPT_CODE = 818
HS_CODE = "2510"  # rocha fosfatica
ANOS = [2020, 2021, 2022, 2023, 2024, 2025]

HEADERS = {"User-Agent": "Mozilla/5.0 (data analysis)"}


def fetch_ano(ano: int) -> pd.DataFrame:
    """Busca exportacoes do Egito por destino para HS 2510 em um ano."""
    params = {
        "reporterCode": EGYPT_CODE,
        "period": ano,
        "flowCode": "X",       # X = Export
        "cmdCode": HS_CODE,
        "partnerCode": "all",  # todos paises destino
        "partner2Code": "0",
        "customsCode": "C00",
        "motCode": "0",
        "maxRecords": 500,
        "format": "JSON",
    }
    r = requests.get(URL, params=params, headers=HEADERS, timeout=60)
    print(f"  {ano}: status {r.status_code}")
    if r.status_code != 200:
        print(f"    body: {r.text[:300]}")
        return pd.DataFrame()
    js = r.json()
    data = js.get("data", [])
    if not data:
        print(f"    sem dados pra {ano}")
        return pd.DataFrame()
    df = pd.DataFrame(data)
    return df


def main():
    print("=== UN Comtrade: exportacoes Egito de HS 2510 ===\n")

    dfs = []
    for ano in ANOS:
        try:
            df = fetch_ano(ano)
            if not df.empty:
                dfs.append(df)
            time.sleep(2)  # gentil com o servidor
        except Exception as e:
            print(f"  !! ano {ano}: {e}")

    if not dfs:
        print("Nenhum dado coletado.")
        return

    df = pd.concat(dfs, ignore_index=True)
    # Seleciona colunas-chave (UN Comtrade tem ~40 colunas, foco no essencial)
    cols_keep = [
        "refPeriodId", "refYear", "reporterDesc", "flowDesc",
        "partnerCode", "partnerDesc", "cmdCode", "cmdDesc",
        "qtyUnitCode", "qtyUnitAbbr", "qty", "netWgt", "grossWgt",
        "cifvalue", "fobvalue", "primaryValue",
    ]
    cols_keep = [c for c in cols_keep if c in df.columns]
    df = df[cols_keep].copy()

    out = OUT_DIR / "comtrade_eg_2510.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig", sep=";")
    print(f"\n  -> {out} ({len(df):,} linhas)")

    # Top destinos do ultimo ano
    ano_max = df["refYear"].max() if "refYear" in df.columns else None
    if ano_max:
        d = df[df["refYear"] == ano_max].sort_values("primaryValue", ascending=False).head(15)
        print(f"\n=== TOP 15 destinos exportacao Egito HS 2510 em {ano_max} ===")
        for _, r in d.iterrows():
            usd = r.get("primaryValue", 0)
            ton = (r.get("netWgt", 0) or 0) / 1000
            print(f"  {r.get('partnerDesc','?'):<25}  TON: {ton:>10,.0f}  USD: {usd:>15,.0f}")


if __name__ == "__main__":
    main()
