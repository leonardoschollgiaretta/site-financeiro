"""Comexstat: importacoes BR de rocha fosfatica (NCM 2510) por pais.

Estrategia: baixa CSVs anuais brutos do MDIC (governo BR) e filtra NCM 2510.
Sem rate limit, sem API. URL base:
  https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/IMP_{YYYY}.csv

Tambem baixa tabelas auxiliares pra decodificar codigo de pais.

Output:
  data/comex_br_2510_raw.csv     -> linhas brutas filtradas (ano, mes, NCM, pais)
  data/comex_br_2510_resumo.csv  -> agregado por ano+pais (KG e USD FOB)
"""
from __future__ import annotations
import os, io, time
from pathlib import Path
import requests
import urllib3
import pandas as pd

# balanca.economia.gov.br tem SSL com cert nao reconhecido pelo certifi/Anaconda.
# Como eh site oficial do governo BR, desabilitamos verify para esses requests.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data"
OUT_DIR.mkdir(exist_ok=True)
CACHE_DIR = ROOT / "_cache"
CACHE_DIR.mkdir(exist_ok=True)

BASE = "https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm"
PAIS_URL = "https://balanca.economia.gov.br/balanca/bd/tabelas/PAIS.csv"

ANOS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
NCM_PREFIX = "2510"  # captulo: rocha fosfatica

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/csv,application/csv,text/plain,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/base-de-dados-bruta",
}


def baixar(url: str, dest: Path, tentativas: int = 3) -> Path:
    """Baixa via curl (mais robusto que requests para CSVs gigantes do MDIC).

    O servidor MDIC corta conexoes anonimas Python/requests grandes. O curl
    do Windows lida bem com HTTP/1.1 keep-alive longo e retry continue.
    """
    import subprocess
    if dest.exists() and dest.stat().st_size > 1024:
        print(f"  [cache] {dest.name} ({dest.stat().st_size//1024} KB)")
        return dest
    for t in range(1, tentativas + 1):
        print(f"  curl {url} (tentativa {t}/{tentativas})...")
        # -k ignora cert SSL; -L segue redirect; --retry refaz conexao se cair
        cmd = [
            "curl", "-k", "-L", "-s", "-S",
            "--retry", "5", "--retry-delay", "3",
            "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36",
            "--connect-timeout", "30",
            "--max-time", "600",
            "-o", str(dest),
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=700)
        if res.returncode == 0 and dest.exists() and dest.stat().st_size > 1024:
            print(f"  -> {dest.name} ({dest.stat().st_size//1024} KB)")
            return dest
        print(f"    falha rc={res.returncode}: {res.stderr[:200]}")
        time.sleep(3 * t)
    raise RuntimeError(f"Falha apos {tentativas} tentativas: {url}")


def carregar_paises() -> pd.DataFrame:
    """Tabela CO_PAIS -> NO_PAIS (e NO_PAIS_ING)."""
    f = baixar(PAIS_URL, CACHE_DIR / "PAIS.csv")
    df = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)
    # Colunas tipicas: CO_PAIS, CO_PAIS_ISON3, CO_PAIS_ISOA3, NO_PAIS, NO_PAIS_ING
    return df[["CO_PAIS", "NO_PAIS", "NO_PAIS_ING"]].copy()


def carregar_ano(ano: int) -> pd.DataFrame:
    """Baixa CSV anual e filtra NCM 2510*."""
    url = f"{BASE}/IMP_{ano}.csv"
    f = baixar(url, CACHE_DIR / f"IMP_{ano}.csv")
    # Layout: CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB;VL_FRETE;VL_SEGURO
    df = pd.read_csv(f, sep=";", encoding="latin-1", dtype={"CO_NCM": str, "CO_PAIS": str})
    df = df[df["CO_NCM"].str.startswith(NCM_PREFIX)].copy()
    print(f"  ano {ano}: {len(df):,} linhas filtradas (NCM {NCM_PREFIX})")
    return df


def main():
    print("=== Comexstat: importacoes BR de NCM 2510 (rocha fosfatica) ===\n")

    paises = carregar_paises()
    print(f"  paises carregados: {len(paises)}\n")

    dfs = []
    for ano in ANOS:
        try:
            dfs.append(carregar_ano(ano))
        except requests.HTTPError as e:
            print(f"  !! ano {ano}: HTTP {e.response.status_code if e.response else '?'} - pulando")
        except Exception as e:
            print(f"  !! ano {ano}: {e}")
        time.sleep(0.5)

    if not dfs:
        print("Nenhum dado carregado!")
        return

    df = pd.concat(dfs, ignore_index=True)
    # Junta nome do pais
    df = df.merge(paises, on="CO_PAIS", how="left")

    # Converte numericos
    for col in ["QT_ESTAT", "KG_LIQUIDO", "VL_FOB", "VL_FRETE", "VL_SEGURO"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Salva raw
    out_raw = OUT_DIR / "comex_br_2510_raw.csv"
    df.to_csv(out_raw, index=False, encoding="utf-8-sig", sep=";")
    print(f"\n  raw -> {out_raw} ({len(df):,} linhas)")

    # Resumo por ano + pais
    resumo = (df.groupby(["CO_ANO", "CO_PAIS", "NO_PAIS"], as_index=False)
                .agg(KG_LIQUIDO=("KG_LIQUIDO", "sum"),
                     VL_FOB_USD=("VL_FOB", "sum"),
                     N_NCMS=("CO_NCM", "nunique"))
                .sort_values(["CO_ANO", "VL_FOB_USD"], ascending=[False, False]))
    # Tonelagem em ton
    resumo["TON"] = (resumo["KG_LIQUIDO"] / 1000).round(0)
    # USD por tonelada (evita div por zero)
    ton_safe = resumo["TON"].replace(0, pd.NA).astype("Float64")
    resumo["USD_TON"] = (resumo["VL_FOB_USD"] / ton_safe).astype("Float64").round(2)

    out_res = OUT_DIR / "comex_br_2510_resumo.csv"
    resumo.to_csv(out_res, index=False, encoding="utf-8-sig", sep=";")
    print(f"  resumo -> {out_res} ({len(resumo):,} linhas)")

    # Print Top 10 do ano mais recente
    ano_max = df["CO_ANO"].max()
    print(f"\n=== TOP IMPORTACOES BR DE 2510 EM {ano_max} ===")
    top = resumo[resumo["CO_ANO"] == ano_max].head(15)
    for _, r in top.iterrows():
        print(f"  {r['NO_PAIS']:<25}  TON: {r['TON']:>12,.0f}  USD FOB: {r['VL_FOB_USD']:>15,.0f}  USD/ton: {r['USD_TON']:>7}")

    # Total
    total = resumo[resumo["CO_ANO"] == ano_max].agg({"TON": "sum", "VL_FOB_USD": "sum"})
    print(f"\n  TOTAL BR {ano_max}: TON {total['TON']:,.0f}  | FOB USD {total['VL_FOB_USD']:,.0f}")

    # Egito especifico (codigo: 379)
    print(f"\n=== EGITO (todos anos) ===")
    egito = resumo[resumo["NO_PAIS"].str.contains("Egito", case=False, na=False)]
    for _, r in egito.iterrows():
        print(f"  {r['CO_ANO']}  TON: {r['TON']:>12,.0f}  USD FOB: {r['VL_FOB_USD']:>15,.0f}")


if __name__ == "__main__":
    main()
