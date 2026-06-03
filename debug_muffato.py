"""
DEBUG isolado — acesso aos demonstrativos financeiros do Grupo Muffato.
Não toca em fundos_cvm nem no resto do projeto. Só investiga a página e
lista os arquivos (PDF/Excel) de demonstrativos disponíveis.

Uso:
    python debug_muffato.py            # lista os links encontrados
    python debug_muffato.py baixar     # baixa os arquivos em ./muffato_dem/
"""
import os, re, sys, urllib.request, urllib.parse

URL = "https://www.grupomuffato.com.br/demonstrativo-financeiros"
BASE = "https://www.grupomuffato.com.br"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muffato_dem")


def get_html(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    # tenta utf-8, cai pra latin-1
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extrair_links(html):
    """Retorna lista de (texto, url_absoluta) para hrefs de interesse."""
    achados = []
    # captura href e o texto entre <a ...>texto</a>
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                         html, re.IGNORECASE | re.DOTALL):
        href = m.group(1).strip()
        texto = re.sub(r"<[^>]+>", " ", m.group(2))
        texto = re.sub(r"\s+", " ", texto).strip()
        achados.append((texto, urllib.parse.urljoin(BASE, href)))
    # também pega hrefs soltos que apontem para arquivos
    for m in re.finditer(r'href=["\']([^"\']+\.(?:pdf|xlsx?|zip|csv))["\']',
                         html, re.IGNORECASE):
        href = urllib.parse.urljoin(BASE, m.group(1).strip())
        if href not in [u for _, u in achados]:
            achados.append(("(href solto)", href))
    return achados


def main():
    print(f">>> Baixando página: {URL}")
    html = get_html(URL)
    print(f"    HTML recebido: {len(html):,} chars\n")

    links = extrair_links(html)
    print(f"=== {len(links)} links totais na página ===\n")

    # filtra os que parecem demonstrativos / arquivos
    padrao = re.compile(r"(\.pdf|\.xls|\.xlsx|\.zip|\.csv|demonstr|balanc|relat|itr|dfp)",
                        re.IGNORECASE)
    interessantes = [(t, u) for t, u in links if padrao.search(t) or padrao.search(u)]

    if not interessantes:
        print("Nenhum link de arquivo/demonstrativo encontrado por padrão.")
        print("Os documentos podem ser carregados via JavaScript (não no HTML estático).")
        print("\nMostrando TODOS os links para inspeção manual:\n")
        for t, u in links:
            print(f"  [{t[:45]:45}] {u}")
        return

    print("=== LINKS DE DEMONSTRATIVOS / ARQUIVOS ===\n")
    for t, u in interessantes:
        print(f"  • {t[:60]}")
        print(f"    {u}\n")

    if len(sys.argv) > 1 and sys.argv[1] == "baixar":
        os.makedirs(OUT_DIR, exist_ok=True)
        print(f"\n>>> Baixando arquivos em {OUT_DIR}")
        for t, u in interessantes:
            if not re.search(r"\.(pdf|xlsx?|zip|csv)$", u, re.IGNORECASE):
                continue
            nome = os.path.basename(urllib.parse.urlparse(u).path)
            dest = os.path.join(OUT_DIR, nome)
            try:
                req = urllib.request.Request(u, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                    f.write(r.read())
                print(f"  ok  {nome} ({os.path.getsize(dest):,} bytes)")
            except Exception as e:
                print(f"  ERRO {nome}: {e}")


if __name__ == "__main__":
    main()
