"""
Carga do CDA-FI (Composição de Carteira de Fundos) da CVM para fundos_cvm.db.
Foca em posições em AÇÕES (BLC_4 com TP_APLIC = 'Ações'), e guarda PL do fundo
para % do PL calculado. Suporta múltiplos períodos.

Uso:
    python carga_cvm_cda.py                       # processa o último mês baixado
    python carga_cvm_cda.py 202604                # processa mês específico (baixa se faltar)
    python carga_cvm_cda.py 202505 202604         # range (inclusivo) de meses AAAAMM
    python carga_cvm_cda.py --ultimos 12          # últimos N meses até o último publicado
"""
import os, sys, csv, sqlite3, glob, zipfile, urllib.request, urllib.error
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
CVM_DIR = os.path.join(BASE, 'cvm_cda')
DB = os.path.join(BASE, 'fundos_cvm.db')

os.makedirs(CVM_DIR, exist_ok=True)
csv.field_size_limit(10_000_000)

def baixar_mes(periodo):
    """periodo formato AAAAMM. Retorna True se OK, False se 404."""
    url = f'https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_{periodo}.zip'
    zip_path = os.path.join(CVM_DIR, f'cda_fi_{periodo}.zip')
    if not os.path.exists(zip_path):
        print(f'  baixando {url}')
        try:
            urllib.request.urlretrieve(url, zip_path)
        except urllib.error.HTTPError as e:
            print(f'  ! HTTP {e.code} — {periodo} indisponível')
            if os.path.exists(zip_path): os.remove(zip_path)
            return False
    # Extrai
    blc4 = os.path.join(CVM_DIR, f'cda_fi_BLC_4_{periodo}.csv')
    if not os.path.exists(blc4):
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(CVM_DIR)
    return True

def detectar_periodos_baixados():
    arquivos = glob.glob(os.path.join(CVM_DIR, 'cda_fi_BLC_4_*.csv'))
    return sorted({os.path.basename(a).replace('cda_fi_BLC_4_','').replace('.csv','') for a in arquivos})

def proximo_mes(periodo):
    a = int(periodo[:4]); m = int(periodo[4:6]); m += 1
    if m == 13: a += 1; m = 1
    return f'{a:04d}{m:02d}'

def mes_anterior(periodo):
    a = int(periodo[:4]); m = int(periodo[4:6]); m -= 1
    if m == 0: a -= 1; m = 12
    return f'{a:04d}{m:02d}'

def range_meses(ini, fim):
    out = []; cur = ini
    while cur <= fim:
        out.append(cur); cur = proximo_mes(cur)
    return out

def descobrir_ultimo_publicado():
    """Tenta o mês mais provável (mês corrente - 1 ou -2) e desce até achar."""
    hoje = datetime.now()
    cand = f'{hoje.year:04d}{hoje.month:02d}'
    for _ in range(6):
        cand = mes_anterior(cand)
        url = f'https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_{cand}.zip'
        try:
            req = urllib.request.Request(url, method='HEAD')
            urllib.request.urlopen(req, timeout=10)
            return cand
        except: pass
    return None

def criar_schema(conn):
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS fundos (
        cnpj             TEXT NOT NULL,
        dt_compt         TEXT NOT NULL,
        periodo          TEXT NOT NULL,   -- AAAAMM
        denominacao      TEXT,
        tp_fundo_classe  TEXT,
        patrimonio_liq   REAL,
        PRIMARY KEY (cnpj, periodo)
    );
    CREATE INDEX IF NOT EXISTS idx_fundos_periodo ON fundos(periodo);
    CREATE INDEX IF NOT EXISTS idx_fundos_denom   ON fundos(denominacao);

    CREATE TABLE IF NOT EXISTS posicoes_acoes (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj_fundo       TEXT NOT NULL,
        periodo          TEXT NOT NULL,   -- AAAAMM
        dt_compt         TEXT,
        cd_ativo         TEXT,
        ds_ativo         TEXT,
        cd_isin          TEXT,
        tp_ativo         TEXT,
        tp_negoc         TEXT,
        qt_pos_final     REAL,
        vl_mercado       REAL,
        vl_custo         REAL,
        emissor_ligado   TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_pos_cnpj    ON posicoes_acoes(cnpj_fundo);
    CREATE INDEX IF NOT EXISTS idx_pos_ativo   ON posicoes_acoes(cd_ativo);
    CREATE INDEX IF NOT EXISTS idx_pos_periodo ON posicoes_acoes(periodo);
    CREATE INDEX IF NOT EXISTS idx_pos_ativo_periodo ON posicoes_acoes(cd_ativo, periodo);
    ''')
    conn.commit()

def carregar_pl(conn, periodo):
    fp = os.path.join(CVM_DIR, f'cda_fi_PL_{periodo}.csv')
    if not os.path.exists(fp):
        print(f'  ! PL não encontrado para {periodo}')
        return 0
    cur = conn.cursor()
    cur.execute('DELETE FROM fundos WHERE periodo=?', (periodo,))
    batch = []
    with open(fp, encoding='latin-1') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            cnpj = (row.get('CNPJ_FUNDO_CLASSE') or row.get('CNPJ_FUNDO') or '').strip()
            if not cnpj: continue
            try: pl = float(row.get('VL_PATRIM_LIQ') or 0)
            except: pl = None
            batch.append((cnpj, (row.get('DT_COMPTC') or '').strip(), periodo,
                          (row.get('DENOM_SOCIAL') or '').strip(),
                          (row.get('TP_FUNDO_CLASSE') or '').strip(), pl))
            if len(batch) >= 5000:
                cur.executemany('INSERT OR REPLACE INTO fundos VALUES (?,?,?,?,?,?)', batch)
                batch = []
    if batch:
        cur.executemany('INSERT OR REPLACE INTO fundos VALUES (?,?,?,?,?,?)', batch)
    conn.commit()
    cur.execute('SELECT COUNT(*) FROM fundos WHERE periodo=?', (periodo,))
    return cur.fetchone()[0]

def carregar_acoes(conn, periodo):
    fp = os.path.join(CVM_DIR, f'cda_fi_BLC_4_{periodo}.csv')
    if not os.path.exists(fp):
        print(f'  ! BLC_4 não encontrado para {periodo}')
        return 0
    cur = conn.cursor()
    cur.execute('DELETE FROM posicoes_acoes WHERE periodo=?', (periodo,))
    conn.commit()
    n_lidas = 0; n_inseridas = 0; batch = []
    with open(fp, encoding='latin-1') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            n_lidas += 1
            tp_aplic = (row.get('TP_APLIC') or '').strip().lower()
            if tp_aplic not in ('ações','acoes','ação','acao'):
                continue
            cnpj = (row.get('CNPJ_FUNDO_CLASSE') or row.get('CNPJ_FUNDO') or '').strip()
            cd_ativo = (row.get('CD_ATIVO') or '').strip().upper()
            if not cd_ativo: continue
            try: qt = float(row.get('QT_POS_FINAL') or 0)
            except: qt = None
            try: vl = float(row.get('VL_MERC_POS_FINAL') or 0)
            except: vl = None
            try: vc = float(row.get('VL_CUSTO_POS_FINAL') or 0)
            except: vc = None
            batch.append((cnpj, periodo, (row.get('DT_COMPTC') or '').strip(),
                          cd_ativo, (row.get('DS_ATIVO') or '').strip(),
                          (row.get('CD_ISIN') or '').strip(),
                          (row.get('TP_ATIVO') or '').strip(),
                          (row.get('TP_NEGOC') or '').strip(),
                          qt, vl, vc, (row.get('EMISSOR_LIGADO') or '').strip()))
            if len(batch) >= 5000:
                cur.executemany('''INSERT INTO posicoes_acoes
                    (cnpj_fundo, periodo, dt_compt, cd_ativo, ds_ativo, cd_isin, tp_ativo,
                     tp_negoc, qt_pos_final, vl_mercado, vl_custo, emissor_ligado)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', batch)
                n_inseridas += len(batch); batch = []
    if batch:
        cur.executemany('''INSERT INTO posicoes_acoes
            (cnpj_fundo, periodo, dt_compt, cd_ativo, ds_ativo, cd_isin, tp_ativo,
             tp_negoc, qt_pos_final, vl_mercado, vl_custo, emissor_ligado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', batch)
        n_inseridas += len(batch)
    conn.commit()
    print(f'  lidas: {n_lidas:,} | inseridas (ações): {n_inseridas:,}')
    return n_inseridas

def processar(periodo, conn):
    print(f'\n>>> {periodo}')
    ok = baixar_mes(periodo)
    if not ok: return False
    np = carregar_pl(conn, periodo)
    print(f'  fundos com PL: {np:,}')
    carregar_acoes(conn, periodo)
    return True

def migracao_legacy(conn):
    """Se o schema antigo (sem 'periodo') existir, faz migração simples."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fundos'")
    if not cur.fetchone(): return
    cur.execute("PRAGMA table_info(fundos)")
    cols = [c[1] for c in cur.fetchall()]
    if 'periodo' in cols: return
    print('Migrando schema antigo: descartando tabelas legadas...')
    cur.executescript('DROP TABLE IF EXISTS posicoes_acoes; DROP TABLE IF EXISTS fundos;')
    conn.commit()

def main():
    args = sys.argv[1:]
    periodos = []

    if not args:
        ja = detectar_periodos_baixados()
        if ja:
            periodos = [ja[-1]]
            print(f'Nenhum período passado. Reprocessando o último já baixado: {ja[-1]}')
        else:
            ult = descobrir_ultimo_publicado()
            if not ult:
                print('Não consegui descobrir o último período. Passe AAAAMM.')
                return
            periodos = [ult]
    elif args[0] == '--ultimos':
        n = int(args[1])
        ult = descobrir_ultimo_publicado()
        if not ult:
            print('Não consegui descobrir o último período.')
            return
        cur = ult
        for _ in range(n):
            periodos.insert(0, cur); cur = mes_anterior(cur)
    elif len(args) == 2 and all(len(a)==6 and a.isdigit() for a in args):
        periodos = range_meses(args[0], args[1])
    else:
        for a in args:
            if len(a)==6 and a.isdigit(): periodos.append(a)
            else: print(f'Ignorando arg inválido: {a}')

    print(f'Vou processar {len(periodos)} período(s): {periodos}')

    conn = sqlite3.connect(DB)
    migracao_legacy(conn)
    criar_schema(conn)

    ok = 0
    for p in periodos:
        if processar(p, conn): ok += 1

    # Resumo
    cur = conn.cursor()
    print(f'\n=== Resumo do banco ({DB}) ===')
    cur.execute('SELECT periodo, COUNT(DISTINCT cnpj_fundo), COUNT(*) FROM posicoes_acoes GROUP BY periodo ORDER BY periodo')
    print(f'{"Período":>8} {"Fundos":>8} {"Posições":>10}')
    print('-'*32)
    for p, nf, np in cur.fetchall():
        print(f'{p:>8} {nf:>8,} {np:>10,}')
    print(f'\nProcessados com sucesso: {ok}/{len(periodos)}')

if __name__ == '__main__':
    main()
