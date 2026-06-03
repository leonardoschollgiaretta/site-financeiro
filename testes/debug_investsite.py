import requests
from bs4 import BeautifulSoup

BASE = "https://www.investsite.com.br"
TICKER = "GRND3"
ANO = "2020"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": BASE,
}

urls = {
    "Balanço Passivo": f"{BASE}/balanco_patrimonial_passivo.php?cod_negociacao={TICKER}&ano_dem={ANO}&mes_dia_dem=1231&consolid=2&tipocontabil=2",
    "Balanço Ativo":   f"{BASE}/balanco_patrimonial_ativo.php?cod_negociacao={TICKER}&ano_dem={ANO}&mes_dia_dem=1231&consolid=2&tipocontabil=2",
    "DRE":             f"{BASE}/demonstracao_resultado.php?cod_negociacao={TICKER}&ano_dem={ANO}&mes_dia_dem=1231&consolid=2&tipocontabil=2",
    "Fluxo de Caixa":  f"{BASE}/demonstracao_fluxo_caixa.php?cod_negociacao={TICKER}&ano_dem={ANO}&mes_dia_dem=1231&consolid=2&tipocontabil=2",
}

for nome, url in urls.items():
    print(f"\n{'='*60}")
    print(f"=== {nome} ===")
    print(f"URL: {url}")
    resp = requests.get(url, headers=headers, timeout=15)
    print(f"Status: {resp.status_code}")

    if resp.status_code != 200:
        print("❌ Falhou")
        continue

    soup = BeautifulSoup(resp.text, "html.parser")

    # Tenta achar tabelas
    tabelas = soup.find_all("table")
    print(f"Tabelas encontradas: {len(tabelas)}")

    for i, tab in enumerate(tabelas[:3]):  # mostra até 3 tabelas
        linhas = tab.find_all("tr")
        print(f"\n  Tabela {i+1} — {len(linhas)} linhas:")
        for linha in linhas[:8]:  # mostra até 8 linhas por tabela
            cols = [td.get_text(strip=True) for td in linha.find_all(["td", "th"])]
            if any(cols):
                print(f"    {cols}")
