"""
A partir do form.idx de um trimestre, descobre os CIKs das gestoras famosas
fazendo matching de nome. Salva em gestoras_curadas.json.
"""
import os, json, re, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
USER_AGENT = 'Leonardo Giaretta leonardo@anelempreendimentos.com.br'
OUT = os.path.join(BASE, 'gestoras_curadas.json')
CACHE_IDX = os.path.join(BASE, '_cache_form_idx_2026Q1.txt')

# Lista de gestoras famosas — substrings que casam o nome registrado na SEC.
# Cada entrada: (apelido, [substrings para procurar], categoria)
# Vou ser generoso nos termos e depois deduplicar.
GESTORAS = [
    # Mega passivos / asset managers
    ('BlackRock',             ['BLACKROCK INC'],                          'asset_manager'),
    ('Vanguard',              ['VANGUARD GROUP INC'],                     'asset_manager'),
    ('State Street',          ['STATE STREET CORP'],                      'asset_manager'),
    ('Fidelity / FMR',        ['FMR LLC'],                                'asset_manager'),
    ('Capital Group',         ['CAPITAL RESEARCH GLOBAL INVESTORS',
                               'CAPITAL WORLD INVESTORS',
                               'CAPITAL INTERNATIONAL INVESTORS'],        'asset_manager'),
    ('T. Rowe Price',         ['PRICE T ROWE ASSOCIATES'],                'asset_manager'),
    ('Wellington Management', ['WELLINGTON MANAGEMENT GROUP LLP',
                               'WELLINGTON MANAGEMENT COMPANY'],           'asset_manager'),
    ('Invesco',               ['INVESCO LTD'],                            'asset_manager'),
    ('Franklin Resources',    ['FRANKLIN RESOURCES INC'],                 'asset_manager'),
    ('Northern Trust',        ['NORTHERN TRUST CORP'],                    'asset_manager'),
    ('Goldman Sachs Group',   ['GOLDMAN SACHS GROUP INC'],                'bank_im'),
    ('Morgan Stanley',        ['MORGAN STANLEY'],                         'bank_im'),
    ('JPMorgan Chase',        ['JPMORGAN CHASE & CO'],                    'bank_im'),
    ('Bank of America',       ['BANK OF AMERICA CORP /DE/'],              'bank_im'),
    ('Wells Fargo',           ['WELLS FARGO & COMPANY/MN'],               'bank_im'),
    ('Citigroup',             ['CITIGROUP INC'],                          'bank_im'),
    ('UBS',                   ['UBS GROUP AG',
                               'UBS ASSET MANAGEMENT AMERICAS'],          'bank_im'),
    ('Deutsche Bank',         ['DEUTSCHE BANK AG\\'],                     'bank_im'),

    # Soberanos / pension
    ('Norges Bank',           ['NORGES BANK'],                            'sovereign'),
    # ('GIC' não tem 13F-HR direto — investe via subsidiárias)
    # ('Greenlight Capital' não tem 13F-HR no Q1/26)
    # ('Sequoia Fund / Ruane Cunniff' não tem 13F-HR no Q1/26)
    ('CPP Investments',       ['CANADA PENSION PLAN INVESTMENT BOARD'],   'pension'),

    # Hedge funds — value/long-only conhecidos
    ('Berkshire Hathaway',    ['BERKSHIRE HATHAWAY INC'],                 'hf_value'),
    ('Baillie Gifford',       ['BAILLIE GIFFORD & CO'],                   'hf_growth'),
    ('Tiger Global',          ['TIGER GLOBAL MANAGEMENT'],                'hf_growth'),
    ('Coatue Management',     ['COATUE MANAGEMENT LLC'],                  'hf_growth'),
    ('Lone Pine Capital',     ['LONE PINE CAPITAL LLC'],                  'hf_growth'),
    ('Viking Global',         ['VIKING GLOBAL INVESTORS LP'],             'hf_growth'),
    ('Maverick Capital',      ['MAVERICK CAPITAL LTD'],                   'hf_growth'),
    ('Whale Rock Capital',    ['WHALE ROCK CAPITAL MANAGEMENT'],          'hf_growth'),
    ('D1 Capital',            ['D1 CAPITAL PARTNERS'],                    'hf_growth'),
    ('Pershing Square',       ['PERSHING SQUARE CAPITAL MANAGEMENT'],     'hf_activist'),
    ('Third Point',           ['THIRD POINT LLC'],                        'hf_activist'),
    ('Elliott Management',    ['ELLIOTT INVESTMENT MANAGEMENT',
                               'ELLIOTT MANAGEMENT CORP'],                'hf_activist'),
    ('ValueAct Capital',      ['VALUEACT HOLDINGS'],                      'hf_activist'),
    ('Trian Fund',            ['TRIAN FUND MANAGEMENT'],                  'hf_activist'),
    ('Starboard Value',       ['STARBOARD VALUE LP'],                     'hf_activist'),

    # Hedge funds — quant/multi-strategy
    ('Bridgewater',           ['BRIDGEWATER ASSOCIATES'],                 'hf_macro'),
    ('Citadel',               ['CITADEL ADVISORS LLC'],                   'hf_multistrat'),
    ('Renaissance Technologies',['RENAISSANCE TECHNOLOGIES LLC'],         'hf_quant'),
    ('Two Sigma',             ['TWO SIGMA INVESTMENTS',
                               'TWO SIGMA ADVISERS'],                     'hf_quant'),
    ('Millennium Management', ['MILLENNIUM MANAGEMENT LLC'],              'hf_multistrat'),
    ('AQR Capital',           ['AQR CAPITAL MANAGEMENT'],                 'hf_quant'),
    ('Point72',               ['POINT72 ASSET MANAGEMENT'],               'hf_multistrat'),
    ('DE Shaw',               ['D. E. SHAW & CO',
                               'D E SHAW & CO'],                          'hf_quant'),
    ('Balyasny',              ['BALYASNY ASSET MANAGEMENT'],              'hf_multistrat'),
    ('ExodusPoint',           ['EXODUSPOINT CAPITAL MANAGEMENT'],         'hf_multistrat'),
    ('Marshall Wace',         ['MARSHALL WACE'],                          'hf_quant'),
    ('Man Group',             ['MAN GROUP PLC'],                          'hf_quant'),

    # Famosos individuais / boutique
    ('ARK Invest',            ['^ARK INVESTMENT MANAGEMENT'],             'thematic'),
    ('Gotham (Greenblatt)',   ['GOTHAM ASSET MANAGEMENT'],                'hf_value'),
    # ('Greenlight (Einhorn)' — não fez filing 13F-HR no Q1/26)
    ('Appaloosa (Tepper)',    ['APPALOOSA LP',
                               'APPALOOSA MANAGEMENT'],                   'hf_value'),
    ('Soros Fund',            ['SOROS FUND MANAGEMENT LLC'],              'hf_macro'),
    ('Duquesne (Druckenmiller)',['DUQUESNE FAMILY OFFICE'],               'family_office'),
    ('Polen Capital',         ['POLEN CAPITAL MANAGEMENT'],               'hf_growth'),
    # ('Sequoia Fund / Ruane Cunniff' — não fez filing 13F-HR no Q1/26)
    ('Davis Selected',        ['DAVIS SELECTED ADVISERS'],                'hf_value'),
    ('Dodge & Cox',           ['DODGE & COX'],                            'hf_value'),
]

def baixar_idx(trim='2026/QTR1'):
    if os.path.exists(CACHE_IDX):
        print(f'Usando cache: {CACHE_IDX}')
        return open(CACHE_IDX, encoding='latin-1').read()
    url = f'https://www.sec.gov/Archives/edgar/full-index/{trim}/form.idx'
    print(f'Baixando {url}')
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept-Encoding':'identity'})
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode('latin-1')
    open(CACHE_IDX, 'w', encoding='latin-1').write(txt)
    return txt

def parse_idx_13f(txt):
    """Retorna lista de (cik, nome, date, filename) só dos 13F-HR."""
    linhas = txt.splitlines()
    # Acha a linha de cabeçalho ('Form Type ... Company Name ... CIK ...')
    header_idx = None
    for i, l in enumerate(linhas):
        if 'Form Type' in l and 'Company Name' in l and 'CIK' in l:
            header_idx = i; break
    if header_idx is None:
        raise RuntimeError('cabeçalho não encontrado no form.idx')
    header = linhas[header_idx]
    # posições por busca no cabeçalho
    pos = {
        'form':    header.index('Form Type'),
        'company': header.index('Company Name'),
        'cik':     header.index('CIK'),
        'date':    header.index('Date Filed'),
        'file':    header.index('File Name'),
    }
    inicio = header_idx + 2  # pula header + linha de '----'
    out = []
    for l in linhas[inicio:]:
        if not l.strip(): continue
        form = l[pos['form']:pos['company']].strip()
        if form != '13F-HR':
            continue
        comp = l[pos['company']:pos['cik']].strip()
        cik  = l[pos['cik']:pos['date']].strip()
        date = l[pos['date']:pos['file']].strip()
        fn   = l[pos['file']:].strip()
        out.append((cik, comp.upper(), date, fn))
    return out

def normaliza(s):
    """uppercase + remove pontuação + colapsa espaços para matching frouxo."""
    return re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9 ]', ' ', s.upper())).strip()

def main():
    txt = baixar_idx()
    todas_13f = parse_idx_13f(txt)
    print(f'Total 13F-HR no Q1/2026: {len(todas_13f):,}')
    # pre-normaliza
    todas_13f_n = [(cik, nome, date, fn, normaliza(nome)) for cik, nome, date, fn in todas_13f]

    # Faz matching
    resultado = []
    nao_achados = []
    for apelido, substrings, categoria in GESTORAS:
        candidatos = []
        for cik, nome, date, fn, nome_n in todas_13f_n:
            for s in substrings:
                if s.startswith('^'):
                    if nome_n.startswith(normaliza(s[1:])):
                        candidatos.append((cik, nome, date, fn)); break
                else:
                    if normaliza(s) in nome_n:
                        candidatos.append((cik, nome, date, fn)); break
        # deduplica por CIK
        ciks_vistos = {}
        for c, n, d, f in candidatos:
            if c not in ciks_vistos: ciks_vistos[c] = (n, d, f)
        if not ciks_vistos:
            nao_achados.append(apelido)
            print(f'  ! NÃO ACHADO: {apelido}')
            continue
        # Se mais de 1 CIK casa, mostra todos
        for cik, (n, d, f) in ciks_vistos.items():
            resultado.append({
                'apelido': apelido, 'categoria': categoria,
                'cik': cik, 'nome_sec': n, 'date_q1_26': d, 'filing_q1_26': f
            })
        if len(ciks_vistos) > 1:
            print(f'  (!){apelido}: {len(ciks_vistos)} CIKs encontrados:')
            for c, (n, _, _) in ciks_vistos.items():
                print(f'      CIK {c}  {n[:70]}')

    print(f'\nResumo:')
    print(f'  gestoras com 1+ CIK: {len({r["apelido"] for r in resultado})}')
    print(f'  total de CIKs:       {len(resultado)}')
    print(f'  não achados:         {len(nao_achados)}: {nao_achados}')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f'\nSalvo em: {OUT}')

if __name__ == '__main__':
    main()
