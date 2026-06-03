"""
Carga de companyfacts.json da SEC para o banco empresas_us.db.

Estratégia:
  1. Baixa companyfacts.json e submissions.json por CIK (com cache local).
  2. Insere TODOS os fatos brutos na tabela xbrl_fatos (para auditoria).
  3. Deriva o trimestre isolado (Q) — desempacotando os cumulativos YTD.
  4. Mapeia conceitos XBRL para colunas do schema BR-like (DRE, BP, DFC).
  5. Popula financeiros_trimestrais com os últimos N anos.

Uso:
    python carga_sec_companyfacts.py AAPL MSFT GOOG NVDA BRK.B   # tickers
    python carga_sec_companyfacts.py --cik 0000320193            # CIK direto
    python carga_sec_companyfacts.py --arquivo tickers.txt        # tickers em arquivo
    python carga_sec_companyfacts.py --anos 5                    # janela hist (default 5)
"""
import os, sys, json, time, sqlite3, urllib.request, urllib.error, argparse
from datetime import datetime, date

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'empresas_us.db')
CACHE = os.path.join(BASE, 'cache_xbrl')
os.makedirs(CACHE, exist_ok=True)

USER_AGENT = 'Leonardo Giaretta leonardo@anelempreendimentos.com.br'
MIN_INTERVAL = 0.15  # ~6 req/s
_last_req = [0.0]

# Cache CIK <-> ticker (lazy, baixa de tickers.json da SEC quando precisar)
_cik_map = None

def http_get(url, host='data.sec.gov'):
    dt = time.time() - _last_req[0]
    if dt < MIN_INTERVAL: time.sleep(MIN_INTERVAL - dt)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Host': host})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            _last_req[0] = time.time()
            return data
    except urllib.error.HTTPError as e:
        _last_req[0] = time.time()
        raise

def cached(name, url, host='data.sec.gov'):
    path = os.path.join(CACHE, name)
    if os.path.exists(path):
        return open(path, 'rb').read()
    data = http_get(url, host=host)
    open(path, 'wb').write(data)
    return data

def baixar_cik_map():
    """Tabela ticker -> CIK da SEC. ~10k empresas."""
    global _cik_map
    if _cik_map is not None: return _cik_map
    data = cached('company_tickers.json',
                  'https://www.sec.gov/files/company_tickers.json',
                  host='www.sec.gov')
    raw = json.loads(data)
    _cik_map = {}
    for _, item in raw.items():
        tk = item['ticker'].upper()
        cik = f'{int(item["cik_str"]):010d}'
        _cik_map[tk] = (cik, item.get('title',''))
    return _cik_map

def resolver_para_cik(termo):
    """Recebe ticker ou CIK; devolve CIK em formato '0000320193'."""
    s = termo.strip().upper()
    if s.isdigit():
        return f'{int(s):010d}'
    m = baixar_cik_map()
    if s in m: return m[s][0]
    # tenta sem ponto (BRK.B -> BRKB ou BRK-B)
    for v in (s.replace('.',''), s.replace('.','-')):
        if v in m: return m[v][0]
    return None

# ────────────────────────────────────────────────────────────────────────────
# Mapa XBRL US-GAAP → coluna do schema
# Ordem importa: tenta o primeiro; se não tiver, cai no próximo (alias).
# ────────────────────────────────────────────────────────────────────────────
MAPA = {
    # DRE
    'receita_liquida': ['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax',
                        'SalesRevenueNet','SalesRevenueGoodsNet'],
    'custo_receita':   ['CostOfRevenue','CostOfGoodsAndServicesSold','CostOfGoodsSold'],
    'lucro_bruto':     ['GrossProfit'],
    'sg_a':            ['SellingGeneralAndAdministrativeExpense','GeneralAndAdministrativeExpense'],
    'r_e_d':           ['ResearchAndDevelopmentExpense'],
    'despesas_operacionais': ['OperatingExpenses'],
    'depreciacao_amortizacao': ['DepreciationDepletionAndAmortization',
                                 'DepreciationAndAmortization','Depreciation'],
    'ebit':            ['OperatingIncomeLoss'],
    'despesas_financeiras': ['InterestExpense'],
    'receitas_financeiras': ['InterestAndDividendIncomeOperating','InvestmentIncomeInterest'],
    'ir_csll':         ['IncomeTaxExpenseBenefit'],
    'ebt':             ['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
                        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments'],
    'lucro_liquido':   ['NetIncomeLoss','ProfitLoss'],

    # Balanço Ativo
    'ativo_total':         ['Assets'],
    'ativo_circulante':    ['AssetsCurrent'],
    'caixa':               ['CashAndCashEquivalentsAtCarryingValue','Cash'],
    'investimentos_cp':    ['ShortTermInvestments','MarketableSecuritiesCurrent'],
    'contas_receber':      ['AccountsReceivableNetCurrent','ReceivablesNetCurrent'],
    'estoques':            ['InventoryNet','Inventory'],
    'ativo_nao_circulante':['AssetsNoncurrent'],
    'investimentos':       ['LongTermInvestments','MarketableSecuritiesNoncurrent'],
    'imobilizado':         ['PropertyPlantAndEquipmentNet'],
    'intangivel':          ['IntangibleAssetsNetExcludingGoodwill','FiniteLivedIntangibleAssetsNet'],
    'goodwill':            ['Goodwill'],

    # Balanço Passivo
    'passivo_total':           ['Liabilities'],
    'passivo_circulante':      ['LiabilitiesCurrent'],
    'fornecedores':            ['AccountsPayableCurrent'],
    'emprestimos_cp':          ['LongTermDebtCurrent','ShortTermBorrowings','CommercialPaper'],
    'passivo_nao_circulante':  ['LiabilitiesNoncurrent'],
    'emprestimos_lp':          ['LongTermDebtNoncurrent','LongTermDebt'],
    'capital_social':          ['CommonStocksIncludingAdditionalPaidInCapital','CommonStockValue'],
    'lucros_acumulados':       ['RetainedEarningsAccumulatedDeficit'],
    'patrimonio_liquido':      ['StockholdersEquity','StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],

    # Fluxo de Caixa
    'fco':                ['NetCashProvidedByUsedInOperatingActivities'],
    'fci':                ['NetCashProvidedByUsedInInvestingActivities'],
    'fcf_financiamento':  ['NetCashProvidedByUsedInFinancingActivities'],
    'capex':              ['PaymentsToAcquirePropertyPlantAndEquipment',
                           'PaymentsToAcquireProductiveAssets'],
    'aquisicoes':         ['PaymentsToAcquireBusinessesNetOfCashAcquired'],
    'venda_ativos':       ['ProceedsFromSaleOfPropertyPlantAndEquipment'],
    'captacoes':          ['ProceedsFromIssuanceOfLongTermDebt','ProceedsFromIssuanceOfDebt'],
    'pagamento_dividas':  ['RepaymentsOfLongTermDebt','RepaymentsOfDebt'],
    'recompra_acoes':     ['PaymentsForRepurchaseOfCommonStock','PaymentsForRepurchaseOfEquity'],
    'dividendos_pagos':   ['PaymentsOfDividendsCommonStock','PaymentsOfDividends'],
    'caixa_final':        ['CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'],
}

# Conceitos de PERÍODO (DRE/DFC) vs INSTANT (BP)
INSTANT_FIELDS = {'ativo_total','ativo_circulante','caixa','investimentos_cp','contas_receber',
                  'estoques','ativo_nao_circulante','investimentos','imobilizado','intangivel',
                  'goodwill','passivo_total','passivo_circulante','fornecedores','emprestimos_cp',
                  'passivo_nao_circulante','emprestimos_lp','capital_social','lucros_acumulados',
                  'patrimonio_liquido','caixa_final'}

def duracao_dias(start, end):
    if not start or not end: return None
    try:
        s = date.fromisoformat(start); e = date.fromisoformat(end)
        return (e - s).days
    except: return None

def classifica_periodo(fato, fiscal_year_end_mmdd=None):
    """Classifica o fato em (tipo_periodo, label_trim).
    Usa SÓ a duração — ignora fp (Apple e outros usam fp=FY em fatos comparativos no 10-K).
    O label do trimestre é derivado do END date e do fiscal_year_end.

    Retorna (tipo, label) ou (None, None).
    """
    start = fato.get('start'); end = fato.get('end')
    dur = duracao_dias(start, end)
    if dur is None or end is None: return None, None
    if 80 <= dur <= 100:    tipo = 'Q'
    elif 170 <= dur <= 200: tipo = 'YTD6'
    elif 260 <= dur <= 290: tipo = 'YTD9'
    elif 350 <= dur <= 380: tipo = 'FY'
    else: return None, None

    if tipo == 'FY': return 'FY', 'FY'

    # Trimestre relativo ao ano fiscal:
    # Se end for ~3 meses depois do FYE anterior → Q1
    # ~6 meses → Q2, ~9 → Q3, ~12 → Q4 (mas Q4 não usa essa lógica, usa FY-YTD9)
    if not fiscal_year_end_mmdd:
        # heurística: usa mês calendário
        m = int(end[5:7])
        return tipo, {1:'Q1',2:'Q1',3:'Q1',4:'Q2',5:'Q2',6:'Q2',
                      7:'Q3',8:'Q3',9:'Q3',10:'Q4',11:'Q4',12:'Q4'}[m]
    # Com FYE conhecido (ex: '0926' = 26/09):
    try:
        fy_m = int(fiscal_year_end_mmdd[:2]); fy_d = int(fiscal_year_end_mmdd[2:])
    except: fy_m, fy_d = 12, 31
    end_m = int(end[5:7]); end_d = int(end[8:10])
    # Meses desde o FYE anterior (assume ano com 12M; mod 12)
    months_since = (end_m - fy_m) % 12
    if months_since == 0:  # bem em cima do FYE → final do FY
        return 'FY', 'FY'
    # Q1≈3, Q2≈6, Q3≈9, Q4≈12 (com tolerância de ±1 mês)
    if 1 <= months_since <= 4:   return tipo, 'Q1'
    if 4 <= months_since <= 7:   return tipo, 'Q2'
    if 7 <= months_since <= 10:  return tipo, 'Q3'
    return tipo, 'Q4'

def extrai_fatos(doc_facts, cik):
    """Itera todos os fatos US-GAAP, retorna lista p/ tabela xbrl_fatos."""
    out = []
    for taxonomia, conceitos in doc_facts.items():
        for conceito, info in conceitos.items():
            for unidade, lista in (info.get('units') or {}).items():
                for f in lista:
                    out.append((
                        cik, conceito, taxonomia, unidade,
                        f.get('fy'), f.get('fp'),
                        f.get('start'), f.get('end'),
                        f.get('val'), f.get('form'),
                        f.get('frame'), f.get('accession'), f.get('filed'),
                    ))
    return out

def melhor_alias(usgaap, nomes, ano_corte=None):
    """Dentre uma lista de conceitos, devolve o que tem MAIS fatos recentes.
    Se ano_corte for fornecido, conta só fatos com fy >= ano_corte.
    Se nenhum tiver fatos recentes, cai pra o primeiro com qualquer dado."""
    melhor = (None, None, -1)
    for n in nomes:
        info = usgaap.get(n)
        if not info: continue
        units = info.get('units') or {}
        # conta fatos recentes em USD
        score = 0
        for u, lista in units.items():
            if u != 'USD' and u != 'shares': continue
            for f in lista:
                fy = f.get('fy')
                if ano_corte is None or (fy and fy >= ano_corte):
                    score += 1
        if score > melhor[2]:
            melhor = (n, info, score)
    if melhor[0] and melhor[2] > 0: return melhor[0], melhor[1]
    # fallback: primeiro com qualquer dado
    for n in nomes:
        info = usgaap.get(n)
        if info and (info.get('units') or {}): return n, info
    return None, None

def derivar_fy_real(end_iso, fiscal_year_end_mmdd):
    """Dada uma data 'YYYY-MM-DD' e o FYE 'MMDD', deriva o fiscal year REAL dos dados.
    Ex: Apple FYE=0926 (26/set). Data 2023-09-30 -> FY2023 (já no FY novo).
         Data 2025-12-28 -> FY2026 (3 meses dentro do FY2026).
    Regra: se mes-end >= fy_mes (com tolerância de até 5 dias antes), pertence ao FY=ano calendar.
           senão, pertence ao FY=ano calendar (porque já é do ano fiscal novo).
    Simplificado: FY = ano calendário do END se end_mes >= fy_mes (ou bem próximo).
                  senão, FY = ano calendário + 1.
    """
    if not end_iso: return None
    try:
        y = int(end_iso[:4]); m = int(end_iso[5:7]); d = int(end_iso[8:10])
    except: return None
    fye = fiscal_year_end_mmdd or '1231'
    fy_m = int(fye[:2])
    # FY é o ano em que o FYE cai. Tolerância por MÊS (datas exatas variam ±5 dias
    # porque empresas como Apple fecham na sexta-feira mais próxima de 30/set).
    # Se end está EM mês > fy_m → próximo FY (y+1).
    # Se end está EM mês <= fy_m → FY é o ano y (que termina nesse y).
    if m > fy_m: return y + 1
    return y

def converter_para_trimestres(usgaap, anos_recentes, cik, fiscal_year_end=None):
    """Para cada fato, deriva (fy_real, trim_label) a partir de end+FYE (ignorando o
    campo 'fy' do XBRL, que se refere ao ano do FILING, não dos dados).
    Retorna (registros, meta)."""
    registros = {}  # (fy, trim, tipo) -> dict
    meta = {}

    for col, aliases in MAPA.items():
        conc_nome, info = melhor_alias(usgaap, aliases, ano_corte=anos_recentes)
        if not info: continue
        for u, lista in (info.get('units') or {}).items():
            if u != 'USD': continue
            for f in lista:
                end = f.get('end')
                if not end: continue
                fy_real = derivar_fy_real(end, fiscal_year_end)
                if not fy_real or fy_real < anos_recentes: continue
                if col in INSTANT_FIELDS:
                    # Classifica pelo mês do end vs fye
                    fye = fiscal_year_end or '1231'
                    fy_m = int(fye[:2]); end_m = int(end[5:7])
                    months_since = (end_m - fy_m) % 12
                    if   months_since == 0:                  labels = ['FY','Q4']  # FYE = também Q4
                    elif 1 <= months_since <= 4:             labels = ['Q1']
                    elif 4 <= months_since <= 7:             labels = ['Q2']
                    elif 7 <= months_since <= 10:            labels = ['Q3']
                    else:                                     labels = ['Q4']
                    for label in labels:
                        key = (fy_real, label, 'INST')
                        if key not in meta or (f.get('form')=='10-K' and meta[key].get('form')!='10-K'):
                            meta[key] = {'start': None, 'end': end, 'form': f.get('form')}
                        registros.setdefault(key, {})[col] = f['val']
                else:
                    tipo, label = classifica_periodo(f, fiscal_year_end)
                    if not tipo: continue
                    # Ignora fatos Q4 diretos — Q4 sempre derivado de FY - YTD9
                    if label == 'Q4' and tipo == 'Q': continue
                    key = (fy_real, label, tipo)
                    if key not in meta or (f.get('form')=='10-K' and meta[key].get('form')=='10-Q'):
                        meta[key] = {'start': f.get('start'), 'end': f.get('end'), 'form': f.get('form')}
                    registros.setdefault(key, {})[col] = f['val']
    return registros, meta

def merge_trimestres(registros, meta):
    """Consolida em registros por (fy, trim).
    - Período: para cada coluna, primeiro tenta o trimestre isolado 'Q'.
      Se faltar, deriva do YTD subtraindo o YTD anterior. (Ex: Q3 = YTD9 - YTD6.)
      Para Q4 derivado: FY - YTD9.
    - INSTANT: pega direto.
    """
    # Indexa: fy -> {(trim, tipo): registro}
    fy_bag = {}
    for (fy, trim, tipo), r in registros.items():
        if tipo == 'INST': continue
        fy_bag.setdefault(fy, {})[(trim, tipo)] = r

    consolidado = {}
    for fy, bag in fy_bag.items():
        for trim in ['Q1','Q2','Q3','Q4','FY']:
            out = {}
            out_source = {}  # debug: de onde veio cada coluna

            # 1) tenta o tipo principal
            principal = ('FY','FY') if trim=='FY' else (trim,'Q')
            if principal in bag:
                for c, v in bag[principal].items():
                    out[c] = v; out_source[c] = principal

            # 2) deriva por subtração de YTD para colunas que faltarem
            if trim != 'FY':
                deriv_map = {
                    'Q1': [('Q1','YTD6'), None],            # não dá pra derivar Q1 sozinho
                    'Q2': [('Q2','YTD6'), ('Q1','Q')],      # Q2 = YTD6 - Q1
                    'Q3': [('Q3','YTD9'), ('Q2','YTD6')],   # Q3 = YTD9 - YTD6
                    'Q4': [('FY','FY'),   ('Q3','YTD9')],   # Q4 = FY - YTD9
                }
                ytd_key, sub_key = deriv_map[trim]
                if ytd_key in bag:
                    ytd_vals = bag[ytd_key]
                    if sub_key is None:
                        # Q1: YTD3 ≡ Q1 (mas isso já cairia em principal)
                        for c, v in ytd_vals.items():
                            if c not in out and v is not None:
                                out[c] = v; out_source[c] = ytd_key
                    elif sub_key in bag:
                        sub_vals = bag[sub_key]
                        for c, vy in ytd_vals.items():
                            if c in out: continue       # já tem do principal
                            vs = sub_vals.get(c)
                            if vy is None or vs is None: continue
                            out[c] = vy - vs
                            out_source[c] = ('DERIV', ytd_key, sub_key)

            # 3) adiciona INSTANT (BP)
            inst = registros.get((fy, trim, 'INST'))
            if inst:
                for c, v in inst.items(): out[c] = v

            if not out: continue

            # 4) calcula meta corretamente
            m_p = meta.get((fy, trim, 'Q' if trim != 'FY' else 'FY'), {})
            m_i = meta.get((fy, trim, 'INST'), {})
            # Para Q4 sintético: start = end do YTD9 do mesmo fy; end = end do FY
            if trim == 'Q4' and not m_p:
                m_fy = meta.get((fy, 'FY', 'FY'), {})
                m_y9 = meta.get((fy, 'Q3', 'YTD9'), {})
                m_p = {
                    'start': m_y9.get('end'),
                    'end':   m_fy.get('end'),
                    'form':  m_fy.get('form'),
                }
            m = {
                'start': m_p.get('start') or m_i.get('end'),
                'end':   m_p.get('end')   or m_i.get('end'),
                'form':  m_p.get('form')  or m_i.get('form'),
            }

            tipo_p = 'FY' if trim == 'FY' else 'Q'
            consolidado[(fy, trim)] = (tipo_p, m, out)
    return consolidado

def calcular_derivados(d):
    """Adiciona ebitda, divida_bruta, divida_liquida, fcl, etc."""
    ebit = d.get('ebit'); da = d.get('depreciacao_amortizacao')
    if ebit is not None and da is not None: d['ebitda'] = ebit + da
    ecp = d.get('emprestimos_cp') or 0; elp = d.get('emprestimos_lp') or 0
    if d.get('emprestimos_cp') is not None or d.get('emprestimos_lp') is not None:
        d['divida_bruta'] = ecp + elp
        caixa = d.get('caixa')
        if caixa is not None:
            d['divida_liquida'] = d['divida_bruta'] - caixa
    if d.get('fco') is not None and d.get('capex') is not None:
        d['fcl'] = d['fco'] - d['capex']
    return d

def carregar_empresa(conn, cik):
    """Baixa e processa 1 CIK."""
    cik_pad = f'{int(cik):010d}'
    print(f'\n>>> CIK {cik_pad}')
    try:
        sub_raw = cached(f'submissions_{cik_pad}.json',
                         f'https://data.sec.gov/submissions/CIK{cik_pad}.json')
        cf_raw  = cached(f'companyfacts_{cik_pad}.json',
                         f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_pad}.json')
    except urllib.error.HTTPError as e:
        print(f'  ! HTTP {e.code}: {e.reason}'); return False
    sub = json.loads(sub_raw); cf = json.loads(cf_raw)

    nome = sub.get('name'); sic = sub.get('sic'); sic_d = sub.get('sicDescription')
    tickers = sub.get('tickers') or []; exch = sub.get('exchanges') or []
    fyend = sub.get('fiscalYearEnd'); cat = sub.get('category')
    setor = setor_por_sic(sic)
    cur = conn.cursor()
    cur.execute('''
        INSERT OR REPLACE INTO empresas (cik, ticker, ticker_alt, nome, sic, sic_descricao,
                                          setor, exchange, fiscal_year_end, category,
                                          atualizado_em)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ''', (cik_pad, tickers[0] if tickers else None,
          '|'.join(tickers[1:]) if len(tickers)>1 else None,
          nome, sic, sic_d, setor,
          '|'.join(exch) if exch else None, fyend, cat,
          datetime.now().isoformat(timespec='seconds')))
    print(f'  empresa: {nome} ({tickers}) | SIC {sic} {sic_d}')

    # xbrl_fatos cru
    usgaap = (cf.get('facts') or {}).get('us-gaap') or {}
    n_fatos = sum(len(lst) for c in usgaap.values() for lst in (c.get('units') or {}).values())
    print(f'  us-gaap conceitos: {len(usgaap)} | total fatos: {n_fatos:,}')

    # Insere fatos crus (apaga e reinsere para este CIK)
    cur.execute('DELETE FROM xbrl_fatos WHERE cik=?', (cik_pad,))
    fatos = extrai_fatos(cf.get('facts') or {}, cik_pad)
    cur.executemany('''INSERT OR REPLACE INTO xbrl_fatos
        (cik, conceito, taxonomia, unidade, fy, fp, data_inicio, data_fim, valor, form, frame, accession, filed)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', fatos)
    conn.commit()

    # Converte para trimestres
    ano_corte = datetime.now().year - 5
    regs, meta = converter_para_trimestres(usgaap, ano_corte, cik_pad, fiscal_year_end=fyend)
    consolidado = merge_trimestres(regs, meta)
    print(f'  trimestres consolidados: {len(consolidado)}')

    # Insere
    cur.execute('DELETE FROM financeiros_trimestrais WHERE cik=?', (cik_pad,))
    cols_extra = ['ebitda','divida_bruta','divida_liquida','fcl']
    todas_cols = sorted(set(MAPA.keys()) | set(cols_extra))
    base_cols = ['cik','ano','trimestre','tipo_periodo','data_inicio','data_fim','form',
                 'fonte','atualizado_em']
    all_cols = base_cols + todas_cols
    placeholders = ','.join(['?']*len(all_cols))
    sql = f"INSERT INTO financeiros_trimestrais ({','.join(all_cols)}) VALUES ({placeholders})"

    agora = datetime.now().isoformat(timespec='seconds')
    rows = []
    for (fy, trim), (tipo, m, d) in consolidado.items():
        d = calcular_derivados(dict(d))
        rows.append([cik_pad, fy, trim, tipo,
                     m.get('start'), m.get('end'), m.get('form'),
                     'sec-xbrl', agora] +
                    [d.get(c) for c in todas_cols])
    cur.executemany(sql, rows)
    conn.commit()
    print(f'  inseridos: {len(rows)} registros em financeiros_trimestrais')
    return True

# Mapeamento SIC → setor (simplificado, agrupando por divisão SIC)
def setor_por_sic(sic):
    if not sic: return None
    try: s = int(sic)
    except: return None
    if 100  <= s <= 999:  return 'Agricultura'
    if 1000 <= s <= 1499: return 'Mineração'
    if 1500 <= s <= 1799: return 'Construção'
    if 2000 <= s <= 3999:
        if 2800 <= s <= 2899: return 'Química'
        if 2911 <= s <= 2999: return 'Petróleo & Refino'
        if 3500 <= s <= 3599: return 'Industrial Machinery'
        if 3570 <= s <= 3579: return 'Computer Hardware'
        if 3674 <= s <= 3674: return 'Semicondutores'
        if 3711 <= s <= 3799: return 'Automotive'
        return 'Manufatura'
    if 4000 <= s <= 4999:
        if 4810 <= s <= 4899: return 'Telecom'
        if 4900 <= s <= 4999: return 'Utilities'
        return 'Transportes'
    if 5000 <= s <= 5199: return 'Wholesale'
    if 5200 <= s <= 5999: return 'Retail'
    if 6000 <= s <= 6199: return 'Bancos'
    if 6200 <= s <= 6299: return 'Brokerage'
    if 6300 <= s <= 6499: return 'Seguros'
    if 6500 <= s <= 6799: return 'Real Estate / REITs'
    if 7000 <= s <= 8999:
        if 7370 <= s <= 7379: return 'Software / IT Services'
        if 8000 <= s <= 8099: return 'Healthcare Services'
        return 'Serviços'
    if 2830 <= s <= 2839: return 'Farmacêutica'
    return f'SIC {s}'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('tickers', nargs='*', help='tickers ou CIKs')
    p.add_argument('--arquivo', help='arquivo com 1 ticker por linha')
    p.add_argument('--anos', type=int, default=5)
    args = p.parse_args()

    tickers = list(args.tickers)
    if args.arquivo:
        with open(args.arquivo, encoding='utf-8') as f:
            tickers += [l.strip() for l in f if l.strip() and not l.startswith('#')]
    if not tickers:
        print(__doc__); return

    print(f'Tickers/CIKs a processar: {len(tickers)}')
    conn = sqlite3.connect(DB)
    ok = 0; falha = 0; nao_resolvido = []
    for t in tickers:
        cik = resolver_para_cik(t)
        if not cik:
            print(f'  [?] {t}: ticker não resolvido para CIK'); nao_resolvido.append(t); falha += 1; continue
        try:
            if carregar_empresa(conn, cik): ok += 1
            else: falha += 1
        except Exception as e:
            print(f'  [x] {t} (CIK {cik}): erro {type(e).__name__}: {e}'); falha += 1

    print(f'\n=== Resumo ===')
    print(f'  ok: {ok}  |  falha: {falha}')
    if nao_resolvido: print(f'  não resolvidos: {nao_resolvido}')

    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM empresas'); n_emp = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM financeiros_trimestrais'); n_fin = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM xbrl_fatos'); n_fa = cur.fetchone()[0]
    print(f'\nBanco: {DB}')
    print(f'  empresas:               {n_emp:,}')
    print(f'  financeiros_trim:       {n_fin:,}')
    print(f'  xbrl_fatos (auditoria): {n_fa:,}')

if __name__ == '__main__':
    main()
