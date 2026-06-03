"""
debug_acoes.py — Testa diferentes endpoints do Investsite para achar numero de acoes.
Uso: python financeiro/br/debug_acoes.py
"""
import requests
import json
import re
from bs4 import BeautifulSoup

BASE = "https://www.investsite.com.br"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "application/json, text/html, */*",
    "Referer": BASE,
}

TICKER = "GRND3"   # altere para testar outro

# Parametros padrao usados pelos outros coletores
PARAMS_BASE = "?cod_negociacao={ticker}&ano_dem=2025&mes_dia_dem=1231&consolid=2&tipocontabil=2"


def tentar(label, url):
    print(f"\n{'='*60}")
    print(f"  [{label}]")
    print(f"  URL: {url}")
    print(f"{'='*60}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  Status: {resp.status_code}  |  Tamanho: {len(resp.text)} chars")
        if resp.status_code != 200:
            print("  !! Nao retornou 200")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        keywords = [
            "ações", "acoes", "quantidade", "total de ações", "qtd",
            "free float", "n° ações", "on+pn", "papeis", "papéis",
            "ordinarias", "ordinárias", "preferenci"
        ]
        encontrados = []
        for tag in soup.find_all(text=True):
            t = tag.strip()
            tl = t.lower()
            if any(k in tl for k in keywords) and 2 < len(t) < 400:
                encontrados.append(t)

        if encontrados:
            print("  >> Texto relevante encontrado:")
            for t in encontrados[:40]:
                print(f"     {t}")
        else:
            print("  (sem keywords) — primeiros 2000 chars:")
            print(resp.text[:2000])

    except Exception as e:
        print(f"  ERRO: {e}")


# ── Paginas .php a testar (mesmo padrao dos outros coletores) ─────────────────
p = PARAMS_BASE.format(ticker=TICKER)

def extrair_total(url):
    """Busca o 'Total (Exceto Tesouraria)' da pagina de quantidade de acoes."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return f"STATUS {resp.status_code}"
    soup = BeautifulSoup(resp.text, "html.parser")
    tabelas = soup.find_all("table")
    if len(tabelas) < 3:
        return "sem tabela"
    # Tabela 2, linha Total (ultima linha)
    rows = tabelas[2].find_all("tr")
    for tr in reversed(rows):
        cols = [td.get_text(strip=True) for td in tr.find_all(["td","th"])]
        if len(cols) >= 2 and cols[1]:
            return f"{cols[0]} = {cols[1]}"
    return "sem dados"


# Testa sem parametro de ano (snapshot atual)
print("\nTeste sem ano (snapshot atual):")
url_base = f"{BASE}/quantidade_acoes.php?cod_negociacao={TICKER}"
print(f"  {url_base}")
print(f"  -> {extrair_total(url_base)}")

# Testa com parametros de ano (mesmo padrao dos outros coletores)
print(f"\nTeste com parametro ano_dem (mesmo padrao DRE/Balanco):")
for ano in [2025, 2024, 2023, 2022, 2021, 2020]:
    url = f"{BASE}/quantidade_acoes.php?cod_negociacao={TICKER}&ano_dem={ano}&mes_dia_dem=1231&consolid=2&tipocontabil=2"
    resultado = extrair_total(url)
    print(f"  {ano} -> {resultado}")

# Testa so com cod_negociacao e ano_dem (sem os outros params)
print(f"\nTeste com apenas ano_dem:")
for ano in [2025, 2022, 2020]:
    url = f"{BASE}/quantidade_acoes.php?cod_negociacao={TICKER}&ano_dem={ano}"
    resultado = extrair_total(url)
    print(f"  {ano} -> {resultado}")

print("\n\nDone.")
