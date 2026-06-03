"""
Consulta o banco fundos_cvm.db.

Uso:
    python consulta_fundos.py PETR4                 # fundos que detêm PETR4 (ordenado por valor)
    python consulta_fundos.py PETR4 --top 20        # limita a 20 fundos
    python consulta_fundos.py PETR4 --excel         # exporta para Excel
    python consulta_fundos.py --fundo 36352539      # carteira de um fundo (busca por CNPJ parcial)
    python consulta_fundos.py --fundo "REAL INVESTOR" # busca por nome
    python consulta_fundos.py --ranking              # top 30 ações mais detidas
    python consulta_fundos.py --gestoras PETR4       # agrupado por gestora (heurística pelo nome)
"""
import sqlite3, sys, os, argparse, re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'fundos_cvm.db')

def fmt_brl(v):
    if v is None: return '         -'
    if abs(v) >= 1e9: return f'R$ {v/1e9:7.2f} bi'
    if abs(v) >= 1e6: return f'R$ {v/1e6:7.2f} mi'
    if abs(v) >= 1e3: return f'R$ {v/1e3:7.2f} k '
    return f'R$ {v:9.2f}'

def fmt_pct(v):
    if v is None: return '   -  '
    return f'{v*100:5.2f}%'

def ultimo_periodo(conn):
    return conn.execute('SELECT MAX(periodo) FROM posicoes_acoes').fetchone()[0]

def query_ativo(conn, ticker, top=None, excel=False, periodo=None):
    cur = conn.cursor()
    periodo = periodo or ultimo_periodo(conn)
    sql = '''
    SELECT p.cnpj_fundo, f.denominacao, f.tp_fundo_classe,
           p.qt_pos_final, p.vl_mercado, f.patrimonio_liq,
           CASE WHEN f.patrimonio_liq>0 THEN p.vl_mercado*1.0/f.patrimonio_liq END as pct_pl,
           p.tp_ativo, p.ds_ativo
    FROM posicoes_acoes p
    LEFT JOIN fundos f ON f.cnpj = p.cnpj_fundo AND f.periodo = p.periodo
    WHERE p.cd_ativo = ? AND p.periodo = ?
    ORDER BY p.vl_mercado DESC
    '''
    rows = cur.execute(sql, (ticker.upper(), periodo)).fetchall()
    if not rows:
        print(f'Nenhum fundo encontrado para {ticker} em {periodo}.')
        return
    print(f'\n=== Fundos com posição em {ticker.upper()} ({len(rows)} fundos) — período {periodo} ===')
    print(f'{"#":>3} {"CNPJ":18s} {"Tipo":15s} {"Denominação":58s} {"Quant.":>14s} {"Valor":>15s} {"% do PL":>8s}')
    print('-'*135)
    total_val = 0
    show = rows if top is None else rows[:top]
    for i, r in enumerate(show, 1):
        cnpj, denom, tipo, qt, vl, pl, pct, tpat, ds = r
        denom = (denom or '')[:57]
        tipo = (tipo or '')[:15]
        total_val += (vl or 0)
        print(f'{i:>3} {cnpj:18s} {tipo:15s} {denom:58s} {(qt or 0):14,.0f} {fmt_brl(vl):>15s} {fmt_pct(pct):>8s}')
    # totalizador real (todas as linhas)
    tot_geral = sum((r[4] or 0) for r in rows)
    print('-'*135)
    print(f'Total exibido: {fmt_brl(total_val):>15s}    Total geral ({len(rows)} fundos): {fmt_brl(tot_geral)}')
    if excel:
        export_excel(rows, f'fundos_com_{ticker.upper()}')

def query_fundo(conn, termo, periodo=None):
    cur = conn.cursor()
    periodo = periodo or ultimo_periodo(conn)
    # tenta CNPJ
    cnpj_clean = re.sub(r'\D','', termo)
    if cnpj_clean and len(cnpj_clean) >= 6:
        cur.execute("""SELECT cnpj, denominacao, patrimonio_liq FROM fundos
                       WHERE periodo=? AND REPLACE(REPLACE(REPLACE(cnpj,'.',''),'/',''),'-','') LIKE ?""",
                    (periodo, f'%{cnpj_clean}%'))
        fundos = cur.fetchall()
        if not fundos:
            cur.execute("SELECT cnpj, denominacao, patrimonio_liq FROM fundos WHERE periodo=? AND UPPER(denominacao) LIKE ?",
                        (periodo, f'%{termo.upper()}%'))
            fundos = cur.fetchall()
    else:
        cur.execute("SELECT cnpj, denominacao, patrimonio_liq FROM fundos WHERE periodo=? AND UPPER(denominacao) LIKE ?",
                    (periodo, f'%{termo.upper()}%'))
        fundos = cur.fetchall()

    if not fundos:
        print(f'Nenhum fundo encontrado para "{termo}".')
        return
    if len(fundos) > 1:
        print(f'\nEncontrei {len(fundos)} fundos. Mostrando os primeiros 20:')
        for cnpj, denom, pl in fundos[:20]:
            print(f'  {cnpj}  PL={fmt_brl(pl)}  {denom}')
        print('\nRefine o termo de busca para selecionar 1 fundo.')
        return
    cnpj, denom, pl = fundos[0]
    print(f'\n=== Carteira de ações ===')
    print(f'Fundo: {denom}')
    print(f'CNPJ : {cnpj}   PL: {fmt_brl(pl)}')
    cur.execute('''SELECT cd_ativo, ds_ativo, tp_ativo, qt_pos_final, vl_mercado
                   FROM posicoes_acoes WHERE cnpj_fundo=? AND periodo=?
                   ORDER BY vl_mercado DESC''', (cnpj, periodo))
    pos = cur.fetchall()
    if not pos:
        print('Sem posições em ações neste período.')
        return
    print(f'{"#":>3} {"Ticker":8s} {"Tipo":20s} {"Descrição":40s} {"Quant.":>14s} {"Valor":>15s} {"% PL":>7s}')
    print('-'*115)
    total = 0
    for i, (cod, ds, tp, qt, vl) in enumerate(pos, 1):
        pct = (vl/pl) if pl else None
        total += (vl or 0)
        print(f'{i:>3} {cod:8s} {(tp or "")[:20]:20s} {(ds or "")[:40]:40s} {(qt or 0):14,.0f} {fmt_brl(vl):>15s} {fmt_pct(pct):>7s}')
    print('-'*115)
    print(f'Total em ações: {fmt_brl(total)}   ({fmt_pct(total/pl) if pl else "-"} do PL)')

def ranking(conn):
    cur = conn.cursor()
    cur.execute('SELECT MAX(periodo) FROM posicoes_acoes')
    p = cur.fetchone()[0]
    cur.execute('''SELECT cd_ativo, COUNT(DISTINCT cnpj_fundo) c, SUM(vl_mercado) v
                   FROM posicoes_acoes WHERE periodo=? GROUP BY cd_ativo
                   ORDER BY c DESC LIMIT 30''', (p,))
    print(f'\n=== Top 30 ações por nº de fundos detentores ({p}) ===')
    print(f'{"#":>3} {"Ticker":8s} {"Fundos":>7s} {"Valor agregado":>20s}')
    print('-'*45)
    for i, (cod, c, v) in enumerate(cur.fetchall(), 1):
        print(f'{i:>3} {cod:8s} {c:>7d} {fmt_brl(v):>20s}')

def gestoras(conn, ticker, periodo=None):
    """Heurística: extrai primeira(s) palavra(s) da denominação como 'gestora'."""
    cur = conn.cursor()
    periodo = periodo or ultimo_periodo(conn)
    cur.execute('''SELECT f.denominacao, p.vl_mercado
                   FROM posicoes_acoes p JOIN fundos f
                     ON f.cnpj=p.cnpj_fundo AND f.periodo=p.periodo
                   WHERE p.cd_ativo=? AND p.periodo=?''', (ticker.upper(), periodo))
    from collections import defaultdict
    agg = defaultdict(lambda: [0,0.0])
    for denom, vl in cur.fetchall():
        if not denom: continue
        # primeiras 2 palavras como proxy de gestora/marca
        chave = ' '.join(denom.split()[:2])
        agg[chave][0] += 1; agg[chave][1] += (vl or 0)
    print(f'\n=== Top 25 "gestoras" (proxy = 2 primeiras palavras do nome do fundo) com {ticker.upper()} ===')
    print(f'{"Gestora (proxy)":40s} {"Fundos":>7s} {"Valor agregado":>20s}')
    print('-'*75)
    for k, (c, v) in sorted(agg.items(), key=lambda x:-x[1][1])[:25]:
        print(f'{k[:40]:40s} {c:>7d} {fmt_brl(v):>20s}')

def export_excel(rows, nome):
    try:
        from openpyxl import Workbook
    except ImportError:
        print('(openpyxl não instalado — pulando export Excel)'); return
    wb = Workbook(); ws = wb.active; ws.title = nome[:30]
    ws.append(['CNPJ','Denominação','Tipo','Quantidade','Valor (R$)','PL (R$)','% PL','Tipo ativo','Descrição'])
    for r in rows:
        cnpj, denom, tipo, qt, vl, pl, pct, tpat, ds = r
        ws.append([cnpj, denom, tipo, qt, vl, pl, (pct*100 if pct else None), tpat, ds])
    out = os.path.join(BASE, 'outputs', f'{nome}_{datetime.now():%Y%m%d_%H%M}.xlsx')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wb.save(out); print(f'Excel salvo: {out}')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('ticker', nargs='?', help='ticker da ação (PETR4, VALE3...)')
    p.add_argument('--top', type=int, help='limitar exibição')
    p.add_argument('--excel', action='store_true')
    p.add_argument('--fundo', help='buscar carteira de um fundo (CNPJ ou nome)')
    p.add_argument('--ranking', action='store_true')
    p.add_argument('--gestoras', help='agrupar por gestora (proxy) para um ticker')
    p.add_argument('--periodo', help='período AAAAMM (padrão: mais recente)')
    args = p.parse_args()

    if not os.path.exists(DB):
        print(f'Banco não encontrado: {DB}\nRode primeiro: python carga_cvm_cda.py')
        return
    conn = sqlite3.connect(DB)

    if args.ranking: ranking(conn); return
    if args.gestoras: gestoras(conn, args.gestoras, periodo=args.periodo); return
    if args.fundo: query_fundo(conn, args.fundo, periodo=args.periodo); return
    if args.ticker: query_ativo(conn, args.ticker, top=args.top, excel=args.excel, periodo=args.periodo); return
    p.print_help()

if __name__ == '__main__':
    main()
