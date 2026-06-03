"""Extrai dados do banco para as 6 empresas alvo, salva em JSON."""
import sqlite3, os, json
from collections import defaultdict

DB = os.path.join(os.path.dirname(__file__), 'financeiro.db')
OUT = os.path.join(os.path.dirname(__file__), 'outputs', 'analise_eletricas_dados.json')
os.makedirs(os.path.dirname(OUT), exist_ok=True)

ALVOS = ['ISAE4','CMIG4','TAEE4','CPLE3','SAPR4','SBSP3']
ANOS = [2021, 2022, 2023, 2024, 2025]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

dados = {}

for tk in ALVOS:
    info = {'ticker': tk}
    cur.execute("SELECT nome, setor, ticker_on, ticker_pn, acoes_total, acoes_free FROM empresas WHERE ticker=?", (tk,))
    r = cur.fetchone()
    if r:
        info['empresa'] = dict(r)
    # Financeiros — tenta tk; se vazio, tenta variantes
    variantes_fin = [tk]
    if tk == 'SAPR4': variantes_fin += ['SAPR3','SAPR11']
    if tk == 'SBSP3': variantes_fin += ['SBSP4']
    if tk == 'CPLE3': variantes_fin += ['CPLE6','CPLE11']
    fin = {}
    ticker_fin = None
    for v in variantes_fin:
        cur.execute("SELECT * FROM financeiros_anuais WHERE ticker=? AND ano IN (2020,2021,2022,2023,2024,2025) ORDER BY ano", (v,))
        rows = cur.fetchall()
        if rows:
            ticker_fin = v
            for row in rows:
                d = dict(row)
                if d['ano'] == 0: continue
                fin[d['ano']] = d
            break
    info['ticker_financeiros'] = ticker_fin
    info['financeiros'] = fin

    # Preços anuais
    precos = {}
    for v in [tk] + ([] if tk not in ('CPLE3','SAPR4','SBSP3') else (['CPLE6'] if tk=='CPLE3' else ['SAPR11'] if tk=='SAPR4' else ['SBSP4'])):
        cur.execute("SELECT * FROM precos_anuais WHERE ticker=? AND ano IN (2021,2022,2023,2024,2025) ORDER BY ano", (v,))
        rows = cur.fetchall()
        if rows:
            for row in rows:
                d = dict(row)
                precos[d['ano']] = d
            info['ticker_precos'] = v
            break
    info['precos'] = precos

    # Preço atual
    cur.execute("SELECT * FROM preco_atual WHERE ticker=?", (tk,))
    r = cur.fetchone()
    info['preco_atual'] = dict(r) if r else None

    # Dividendos por ano (soma)
    divs = defaultdict(float)
    cur.execute("SELECT data_com, valor, tipo FROM dividendos_pagamentos WHERE ticker=? AND data_com IS NOT NULL", (tk,))
    for r in cur.fetchall():
        try:
            ano = int(str(r['data_com'])[:4])
            if 2021 <= ano <= 2025:
                divs[ano] += float(r['valor'] or 0)
        except: pass
    info['dividendos_por_ano'] = dict(divs)

    # Ações por ano (para calcular DPA, lucro/ação)
    acoes = {}
    cur.execute("SELECT ano, acoes_total FROM acoes_anuais WHERE ticker=? AND ano IN (2021,2022,2023,2024,2025)", (tk,))
    for r in cur.fetchall():
        acoes[r['ano']] = r['acoes_total']
    info['acoes_por_ano'] = acoes

    dados[tk] = info

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(dados, f, ensure_ascii=False, indent=2, default=str)

# Resumo rápido
print(f"Salvo em: {OUT}\n")
for tk, info in dados.items():
    nome = info.get('empresa',{}).get('nome','?')
    setor = info.get('empresa',{}).get('setor','?')
    anos_fin = sorted(info['financeiros'].keys())
    anos_prc = sorted(info['precos'].keys())
    anos_div = sorted(info['dividendos_por_ano'].keys())
    print(f"{tk} ({nome} | {setor})")
    print(f"  fin ({info['ticker_financeiros']}): {anos_fin}")
    print(f"  precos ({info.get('ticker_precos')}): {anos_prc}")
    print(f"  divs: {anos_div}")
    pa = info.get('preco_atual')
    print(f"  preco atual: {pa['preco'] if pa else 'N/D'}")
