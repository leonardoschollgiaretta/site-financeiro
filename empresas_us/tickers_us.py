"""
Scraping da Wikipedia para obter constituintes do S&P 500 e Nasdaq 100.
Gera tickers_us.json com a união (~550 únicas).

Wikipedia mantém tabelas HTML estáticas (sem JS pesado) com a lista atual.
"""
import os, json, urllib.request, re

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'tickers_us.json')

UA = 'Mozilla/5.0 (Leonardo Giaretta leonardo@anelempreendimentos.com.br)'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8', errors='replace')

def parse_tabela(html):
    """Parse de tabelas wiki. Procura A tabela com lista de tickers (>= 90 linhas,
    primeira coluna é ticker tipo 'AAPL'). Retorna (ticker, nome, setor)."""
    out = []
    def limpa(s):
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(r'&nbsp;', ' ', s)
        s = re.sub(r'&amp;', '&', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s
    tabelas = re.findall(r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
                          html, re.DOTALL)
    melhor = []
    for tab in tabelas:
        linhas = re.findall(r'<tr[^>]*>(.*?)</tr>', tab, re.DOTALL)
        if len(linhas) < 50: continue        # tabelas pequenas (recordes etc.)
        candidatos = []
        for ln in linhas[1:]:
            cels = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', ln, re.DOTALL)
            if len(cels) < 2: continue
            cels = [limpa(c) for c in cels]
            tk = cels[0]
            if not tk or not re.match(r'^[A-Z][A-Z.\-]{0,5}$', tk): continue
            nome = cels[1] if len(cels) > 1 else ''
            setor = cels[2] if len(cels) > 2 else ''
            candidatos.append((tk, nome, setor))
        if len(candidatos) > len(melhor):
            melhor = candidatos
    return melhor

def get_sp500():
    print('Baixando S&P 500...')
    html = fetch('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    tickers = parse_tabela(html)
    print(f'  S&P 500: {len(tickers)} empresas')
    return tickers

def get_nasdaq100():
    print('Baixando Nasdaq 100...')
    html = fetch('https://en.wikipedia.org/wiki/Nasdaq-100')
    tickers = parse_tabela(html)
    print(f'  Nasdaq 100: {len(tickers)} empresas')
    return tickers

def main():
    sp500 = get_sp500()
    nasd  = get_nasdaq100()
    # União por ticker
    visto = {}
    for tk, nm, sec in sp500:
        visto[tk] = {'ticker': tk, 'nome': nm, 'setor': sec, 'indice': 'SP500'}
    for tk, nm, sec in nasd:
        if tk in visto:
            visto[tk]['indice'] = 'SP500+NASD100'
        else:
            visto[tk] = {'ticker': tk, 'nome': nm, 'setor': sec, 'indice': 'NASD100'}
    todos = sorted(visto.values(), key=lambda x: x['ticker'])
    print(f'\nUnião única: {len(todos)} empresas')
    print(f'  só S&P 500:          {sum(1 for t in todos if t["indice"]=="SP500")}')
    print(f'  só Nasdaq 100:       {sum(1 for t in todos if t["indice"]=="NASD100")}')
    print(f'  ambos:               {sum(1 for t in todos if t["indice"]=="SP500+NASD100")}')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    print(f'\nSalvo em: {OUT}')

    # Salva também um .txt simples para usar com --arquivo da carga
    txt_out = os.path.join(BASE, 'tickers_us.txt')
    with open(txt_out, 'w', encoding='utf-8') as f:
        f.write('# S&P 500 + Nasdaq 100\n')
        for t in todos:
            f.write(f'{t["ticker"]}\n')
    print(f'Salvo em: {txt_out}')

if __name__ == '__main__':
    main()
