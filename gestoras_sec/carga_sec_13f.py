"""
Carga de 13F-HR (Information Table) da SEC para gestoras_sec.db.

Para cada CIK em gestoras_curadas.json, busca os filings 13F-HR de cada trimestre
informado, baixa o XML da Information Table, parseia e insere no banco.

Uso:
    python carga_sec_13f.py 2025Q2 2025Q3 2025Q4 2026Q1   # trimestres
    python carga_sec_13f.py --ultimos 4                   # últimos 4 trimestres
    python carga_sec_13f.py 2026Q1                        # 1 trimestre só

Respeita:
- User-Agent identificado (obrigatório pela SEC)
- Rate limit: 5 req/s (folgado vs limite SEC = 10/s)
- Cache local em cache_sec/ (não rebaixa o que já tem)
"""
import os, sys, json, time, sqlite3, urllib.request, urllib.error, re
import xml.etree.ElementTree as ET
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'gestoras_sec.db')
CACHE = os.path.join(BASE, 'cache_sec')
GESTORAS_JSON = os.path.join(BASE, 'gestoras_curadas.json')
os.makedirs(CACHE, exist_ok=True)

USER_AGENT = 'Leonardo Giaretta leonardo@anelempreendimentos.com.br'
MIN_INTERVAL = 0.20  # seg entre requests => 5 req/s
_last_req = [0.0]

def http_get(url, binary=False):
    """GET com rate limit e User-Agent."""
    dt = time.time() - _last_req[0]
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept-Encoding': 'gzip, deflate',
        'Host': 'www.sec.gov',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            enc = r.headers.get('Content-Encoding','')
            if 'gzip' in enc:
                import gzip; data = gzip.decompress(data)
            elif 'deflate' in enc:
                import zlib; data = zlib.decompress(data)
            _last_req[0] = time.time()
            return data if binary else data.decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        _last_req[0] = time.time()
        raise

def get_cache(name, fetch_fn):
    """fetch_fn() -> str. Cacheia por nome."""
    path = os.path.join(CACHE, name)
    if os.path.exists(path):
        return open(path, encoding='utf-8', errors='replace').read()
    data = fetch_fn()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data)
    return data

def baixar_form_idx(trim_yyyy_q):
    """trim_yyyy_q tipo '2026Q1'. Retorna conteúdo do form.idx."""
    yyyy, q = trim_yyyy_q[:4], trim_yyyy_q[4:]
    name = f'form_idx_{trim_yyyy_q}.txt'
    return get_cache(name, lambda: http_get(
        f'https://www.sec.gov/Archives/edgar/full-index/{yyyy}/QTR{q[1:]}/form.idx'
    ))

def parse_idx_13f(txt):
    """Retorna {cik: [(accession, date, filename)]}."""
    linhas = txt.splitlines()
    header_idx = None
    for i, l in enumerate(linhas):
        if 'Form Type' in l and 'Company Name' in l and 'CIK' in l:
            header_idx = i; break
    if header_idx is None: return {}
    header = linhas[header_idx]
    pos = {
        'form':    header.index('Form Type'),
        'company': header.index('Company Name'),
        'cik':     header.index('CIK'),
        'date':    header.index('Date Filed'),
        'file':    header.index('File Name'),
    }
    out = {}
    for l in linhas[header_idx+2:]:
        if not l.strip(): continue
        form = l[pos['form']:pos['company']].strip()
        if form != '13F-HR': continue
        cik  = l[pos['cik']:pos['date']].strip()
        date = l[pos['date']:pos['file']].strip()
        fn   = l[pos['file']:].strip()
        # accession: extrai do filename ex: edgar/data/1067983/0001193125-26-054580.txt
        m = re.search(r'(\d{10}-\d{2}-\d{6})', fn)
        accession = m.group(1) if m else None
        out.setdefault(cik, []).append((accession, date, fn))
    return out

def baixar_lista_filing(cik, accession):
    """Lista os arquivos do filing. Retorna lista de nomes."""
    acc_no_dash = accession.replace('-','')
    url = f'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR'
    # Vamos pelo caminho direto: index.json do filing
    url = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/'
    name = f'list_{cik}_{accession}.html'
    html = get_cache(name, lambda: http_get(url))
    # encontra links pra .xml
    arquivos = re.findall(r'href="([^"]+\.xml)"', html)
    # filtra: o que tem 'infor' (informationtable) ou 'table' no nome tipicamente
    return [a.split('/')[-1] for a in arquivos]

def baixar_info_table(cik, accession, xml_name):
    acc_no_dash = accession.replace('-','')
    url = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/{xml_name}'
    name = f'it_{cik}_{accession}_{xml_name}'
    return get_cache(name, lambda: http_get(url))

def parse_information_table(xml_txt):
    """Parsea um XML de informationTable. Retorna lista de dicts."""
    # remove processing instructions (xml-stylesheet etc) que podem confundir
    xml_txt = re.sub(r'<\?xml-stylesheet[^?]*\?>', '', xml_txt)
    # remove TODOS os xmlns (default e com prefixo) — ilimitado
    xml_txt = re.sub(r'\sxmlns(:\w+)?="[^"]*"', '', xml_txt)
    # remove prefixos de namespace nas tags (caso existam) — <ns1:infoTable> -> <infoTable>
    xml_txt = re.sub(r'<(/?)\w+:', r'<\1', xml_txt)
    # remove atributos com prefixo (ex xsi:schemaLocation="...")
    xml_txt = re.sub(r'\s\w+:\w+="[^"]*"', '', xml_txt)
    try:
        root = ET.fromstring(xml_txt)
    except ET.ParseError as e:
        return []
    out = []
    for it in root.findall('.//infoTable'):
        d = {}
        d['nameOfIssuer'] = (it.findtext('nameOfIssuer') or '').strip()
        d['titleOfClass'] = (it.findtext('titleOfClass') or '').strip()
        d['cusip']        = (it.findtext('cusip') or '').strip()
        try: d['value']   = float(it.findtext('value') or 0)
        except: d['value'] = None
        shrs = it.find('shrsOrPrnAmt')
        if shrs is not None:
            try: d['shares']    = float(shrs.findtext('sshPrnamt') or 0)
            except: d['shares'] = None
            d['share_type']     = (shrs.findtext('sshPrnamtType') or '').strip()
        d['putCall']      = (it.findtext('putCall') or '').strip()
        d['investmentDiscretion'] = (it.findtext('investmentDiscretion') or '').strip()
        out.append(d)
    return out

def criar_schema(conn):
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS gestoras (
        cik          TEXT PRIMARY KEY,
        apelido      TEXT,
        categoria    TEXT,
        nome_sec     TEXT
    );

    CREATE TABLE IF NOT EXISTS filings_13f (
        accession    TEXT PRIMARY KEY,
        cik          TEXT NOT NULL,
        trimestre    TEXT NOT NULL,           -- ex: 2026Q1 (referencia ao quarter dos dados)
        data_filing  TEXT,                    -- data em que filou
        xml_name     TEXT,
        n_holdings   INTEGER,
        valor_total  REAL,
        carregado_em TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_fil_cik ON filings_13f(cik);
    CREATE INDEX IF NOT EXISTS idx_fil_trim ON filings_13f(trimestre);

    CREATE TABLE IF NOT EXISTS holdings (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        accession      TEXT NOT NULL,
        cik            TEXT NOT NULL,
        trimestre      TEXT NOT NULL,
        cusip          TEXT,
        name_of_issuer TEXT,
        title_of_class TEXT,
        value_usd      REAL,                  -- value reportado (em milhares de USD pré 2023, em USD pós 2023)
        shares         REAL,
        share_type     TEXT,
        put_call       TEXT,
        discretion     TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_h_cik     ON holdings(cik);
    CREATE INDEX IF NOT EXISTS idx_h_trim    ON holdings(trimestre);
    CREATE INDEX IF NOT EXISTS idx_h_cusip   ON holdings(cusip);
    CREATE INDEX IF NOT EXISTS idx_h_issuer  ON holdings(name_of_issuer);
    ''')
    conn.commit()

def trim_para_filing_period(trim):
    """Dados Q1/2026 (referência 31/mar/2026) são filados em maio. Mas a SEC datim_filing
    é mais tarde. Para descobrir em qual quarter de filing eles aparecem:
       Dados Qx do ano Y -> filados no Q(x+1) do ano Y (deadline 45 dias).
       Q1 -> filings em Apr-May -> aparecem em form.idx Q2.
       Q4 -> filings em Jan-Feb do ano seguinte -> Q1.
    """
    y, q = int(trim[:4]), int(trim[5])
    if q == 4: return f'{y+1}Q1'
    return f'{y}Q{q+1}'

def proximo_trim(trim):
    y, q = int(trim[:4]), int(trim[5])
    if q == 4: return f'{y+1}Q1'
    return f'{y}Q{q+1}'

def trim_anterior(trim):
    y, q = int(trim[:4]), int(trim[5])
    if q == 1: return f'{y-1}Q4'
    return f'{y}Q{q-1}'

def carregar_trimestre(conn, trim_dados, gestoras):
    """Para cada gestora, busca filing referente a trim_dados.
    O filing aparece no quarter SEGUINTE no form.idx (deadline 45 dias)."""
    trim_filing = trim_para_filing_period(trim_dados)
    print(f'\n>>> Trimestre de dados: {trim_dados} (procurando filings no índice {trim_filing})')

    # Baixa o índice (cache se já tiver)
    try:
        idx_txt = baixar_form_idx(trim_filing)
    except Exception as e:
        print(f'  ! erro baixando índice {trim_filing}: {e}'); return
    filings_por_cik = parse_idx_13f(idx_txt)
    print(f'  índice tem {sum(len(v) for v in filings_por_cik.values()):,} 13F-HR ({len(filings_por_cik):,} CIKs distintos)')

    # Marca todas as gestoras na tabela
    cur = conn.cursor()
    for g in gestoras:
        cur.execute('''INSERT OR REPLACE INTO gestoras (cik, apelido, categoria, nome_sec)
                       VALUES (?,?,?,?)''',
                    (g['cik'].lstrip('0') or g['cik'], g['apelido'], g['categoria'], g['nome_sec']))
    conn.commit()

    ok = 0; falha = 0; ja_tem = 0
    for g in gestoras:
        cik = g['cik'].lstrip('0') or g['cik']
        candidatos = filings_por_cik.get(cik) or filings_por_cik.get(g['cik']) or []
        if not candidatos:
            print(f'  [-] {g["apelido"]:30s} (CIK {cik}): sem filing em {trim_filing}'); falha += 1; continue
        # Pega o mais recente (último em ordem alfabética do accession)
        candidatos.sort(reverse=True)
        accession, date_filed, fn = candidatos[0]
        # idempotência: se já carregado, pula
        cur.execute('SELECT 1 FROM filings_13f WHERE accession=?', (accession,))
        if cur.fetchone():
            ja_tem += 1
            continue
        try:
            arquivos = baixar_lista_filing(cik, accession)
            # heurística: nome contém 'infor' ou 'table' ou é o único xml
            xml_candidatos = [a for a in arquivos if 'infor' in a.lower() or 'table' in a.lower()]
            if not xml_candidatos: xml_candidatos = arquivos
            if not xml_candidatos:
                print(f'  [x] {g["apelido"]:30s}: sem XML no filing'); falha += 1; continue
            # geralmente o info table é o último XML grande; tenta o último primeiro
            holdings_total = []
            xml_usado = None
            for xname in xml_candidatos:
                try:
                    xml_txt = baixar_info_table(cik, accession, xname)
                except Exception as e:
                    continue
                holds = parse_information_table(xml_txt)
                if holds:
                    holdings_total = holds
                    xml_usado = xname
                    break
            if not holdings_total:
                print(f'  [x] {g["apelido"]:30s}: parse zerado'); falha += 1; continue

            # Insere
            cur.execute('''INSERT INTO filings_13f
                (accession, cik, trimestre, data_filing, xml_name, n_holdings, valor_total, carregado_em)
                VALUES (?,?,?,?,?,?,?,?)''',
                (accession, cik, trim_dados, date_filed, xml_usado,
                 len(holdings_total),
                 sum((h.get('value') or 0) for h in holdings_total),
                 datetime.now().isoformat(timespec='seconds')))
            cur.executemany('''INSERT INTO holdings
                (accession, cik, trimestre, cusip, name_of_issuer, title_of_class,
                 value_usd, shares, share_type, put_call, discretion)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                [(accession, cik, trim_dados, h.get('cusip'), h.get('nameOfIssuer'),
                  h.get('titleOfClass'), h.get('value'), h.get('shares'),
                  h.get('share_type'), h.get('putCall'), h.get('investmentDiscretion'))
                 for h in holdings_total])
            conn.commit()
            print(f'  [v] {g["apelido"]:30s}: {len(holdings_total):,} holdings | total US$ {sum((h.get("value") or 0) for h in holdings_total)/1e6:,.0f} mi')
            ok += 1
        except Exception as e:
            print(f'  [x] {g["apelido"]:30s}: erro {type(e).__name__}: {e}')
            falha += 1
    print(f'  resumo {trim_dados}: ok={ok}, falha={falha}, já-tinha={ja_tem}')

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    if args[0] == '--ultimos':
        n = int(args[1])
        # último trimestre publicado: o filing mais recente é Q1/26 (publicado em Q2/26)
        # Mas se hoje é mai/26 ainda estamos em Q2/26, então o filing mais recente publicado é Q1/26
        atual = '2026Q1'
        trims = [atual]
        for _ in range(n-1):
            atual = trim_anterior(atual); trims.insert(0, atual)
    else:
        # Aceita "2026Q1" ou "2026 Q1"
        trims = [a.replace(' ','').upper() for a in args]

    print(f'Trimestres de dados a processar: {trims}')

    if not os.path.exists(GESTORAS_JSON):
        print(f'! {GESTORAS_JSON} não existe. Rode antes: python descobrir_ciks.py')
        return
    gestoras = json.load(open(GESTORAS_JSON, encoding='utf-8'))
    print(f'Gestoras curadas: {len(gestoras)}')

    conn = sqlite3.connect(DB)
    criar_schema(conn)

    for trim in trims:
        carregar_trimestre(conn, trim, gestoras)

    # Resumo
    cur = conn.cursor()
    print(f'\n=== Resumo do banco ({DB}) ===')
    cur.execute('''SELECT trimestre, COUNT(*) n_filings, SUM(n_holdings) n_holdings, SUM(valor_total)
                   FROM filings_13f GROUP BY trimestre ORDER BY trimestre''')
    print(f'{"Trim":>8} {"Filings":>10} {"Holdings":>12} {"Valor total (US$ bi)":>22}')
    print('-'*60)
    for t, nf, nh, vt in cur.fetchall():
        print(f'{t:>8} {nf:>10,} {(nh or 0):>12,} {((vt or 0)/1e9):>22,.1f}')

if __name__ == '__main__':
    main()
