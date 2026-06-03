import requests

BASE   = "https://www.investsite.com.br"
TICKER = "GRND3"
ANO    = "2020"
PARAMS = f"cod_negociacao={TICKER}&ano_dem={ANO}&mes_dia_dem=1231&consolid=2&tipocontabil=2"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

candidatos = [
    "demonstracao_fluxo_caixa.php",
    "demonstracao_fluxo_caixa_indireto.php",
    "fluxo_caixa.php",
    "fluxo_caixa_indireto.php",
    "dfc.php",
    "demonstracao_fc.php",
    "dfc_indireto.php",
]

for nome in candidatos:
    url = f"{BASE}/{nome}?{PARAMS}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        icon = "✅" if resp.status_code == 200 else "❌"
        tamanho = len(resp.text)
        print(f"{icon} [{resp.status_code}] {nome} ({tamanho} bytes)")
        if resp.status_code == 200 and tamanho > 1000:
            # Mostra um pedaço do HTML pra confirmar que tem dados
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            tabs = soup.find_all("table")
            print(f"     Tabelas: {len(tabs)}")
            if tabs:
                linhas = tabs[0].find_all("tr")
                for l in linhas[:4]:
                    cols = [td.get_text(strip=True) for td in l.find_all(["td","th"])]
                    if any(cols): print(f"     {cols}")
    except Exception as e:
        print(f"💥 {nome} → {e}")
