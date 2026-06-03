"""
Consulta no terminal — quem detém um papel (por CUSIP, ticker em CUSIP nem sempre, ou nome).

Como não temos CUSIP→ticker resolvido, o filtro é por NAME OF ISSUER (texto livre).

Uso:
    python consulta_papel.py APPLE           # busca por nome (case-insensitive, substring)
    python consulta_papel.py 037833100       # busca por CUSIP exato
    python consulta_papel.py APPLE --top 20  # limita exibição
    python consulta_papel.py --ranking       # top 30 papeis mais detidos
"""
import os, sys, sqlite3, argparse

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'gestoras_sec.db')

def fmt(v):
    if v is None: return '       —'
    try:
        v = float(v)
        if abs(v) >= 1e9: return f'US$ {v/1e9:7.2f} bi'
        if abs(v) >= 1e6: return f'US$ {v/1e6:7.2f} mi'
        if abs(v) >= 1e3: return f'US$ {v/1e3:7.2f} k '
        return f'US$ {v:9.0f}'
    except: return '       —'

def ultimo_trim(conn):
    return conn.cursor().execute('SELECT MAX(trimestre) FROM filings_13f').fetchone()[0]

def detectar_modo(termo):
    """CUSIP tem 9 caracteres alfanuméricos com mistura de letras E dígitos."""
    s = termo.strip().lstrip('﻿').replace(' ','').upper()
    if len(s) == 9 and s.isalnum() and any(c.isdigit() for c in s):
        return 'cusip', s
    return 'name', s

def query(conn, termo, trim=None, top=None):
    trim = trim or ultimo_trim(conn)
    modo, valor = detectar_modo(termo)
    cur = conn.cursor()
    if modo == 'cusip':
        cur.execute('''
            SELECT h.cik, g.apelido, g.categoria, h.name_of_issuer,
                   h.title_of_class, h.cusip, h.value_usd, h.shares, h.share_type, h.put_call
            FROM holdings h LEFT JOIN gestoras g ON g.cik=h.cik
            WHERE h.cusip=? AND h.trimestre=?
            ORDER BY h.value_usd DESC
        ''', (valor, trim))
    else:
        cur.execute('''
            SELECT h.cik, g.apelido, g.categoria, h.name_of_issuer,
                   h.title_of_class, h.cusip, h.value_usd, h.shares, h.share_type, h.put_call
            FROM holdings h LEFT JOIN gestoras g ON g.cik=h.cik
            WHERE UPPER(h.name_of_issuer) LIKE ? AND h.trimestre=?
            ORDER BY h.value_usd DESC
        ''', (f'%{valor}%', trim))
    return cur.fetchall(), modo, valor, trim

def ranking(conn, trim=None):
    trim = trim or ultimo_trim(conn)
    return conn.cursor().execute('''
        SELECT name_of_issuer, cusip,
               COUNT(DISTINCT cik) n_gest,
               SUM(value_usd) total
        FROM holdings WHERE trimestre=? AND name_of_issuer IS NOT NULL
        GROUP BY name_of_issuer, cusip
        ORDER BY n_gest DESC, total DESC LIMIT 30
    ''', (trim,)).fetchall()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('termo', nargs='?')
    p.add_argument('--top', type=int)
    p.add_argument('--trim', help='trimestre AAAAQn (padrão: mais recente)')
    p.add_argument('--ranking', action='store_true')
    args = p.parse_args()

    if not os.path.exists(DB): print(f'Banco não encontrado: {DB}'); return
    conn = sqlite3.connect(DB)

    if args.ranking:
        rows = ranking(conn, args.trim)
        trim = args.trim or ultimo_trim(conn)
        print(f'\n=== Top 30 papéis por nº de gestoras detentoras ({trim}) ===')
        print(f'{"#":>3} {"Nome":50s} {"CUSIP":>10s} {"Gest.":>5s} {"Total":>16s}')
        print('-'*95)
        for i, (n, c, ng, tot) in enumerate(rows, 1):
            print(f'{i:>3} {(n or "")[:50]:50s} {(c or "—"):>10s} {ng:>5d} {fmt(tot):>16s}')
        return

    if not args.termo:
        p.print_help(); return

    rows, modo, valor, trim = query(conn, args.termo, trim=args.trim, top=args.top)
    if not rows:
        print(f'Nenhuma posição encontrada ({modo}={valor}, trim={trim}).'); return
    print(f'\n=== {len(rows)} posições — busca por {modo}: "{valor}" em {trim} ===')
    print(f'{"#":>3} {"Gestora":30s} {"Categ.":15s} {"Nome papel":35s} {"CUSIP":>10s} {"Classe":12s} {"Quant.":>14s} {"Valor":>16s}')
    print('-'*145)
    show = rows if args.top is None else rows[:args.top]
    total = 0
    for i, r in enumerate(show, 1):
        cik, ap, cat, nm, toc, cu, vl, sh, st, pc = r
        ap = (ap or f'CIK {cik}')[:30]
        cat = (cat or '')[:15]
        nm = (nm or '')[:35]
        toc = (toc or '')[:12]
        total += (vl or 0)
        print(f'{i:>3} {ap:30s} {cat:15s} {nm:35s} {(cu or "—"):>10s} {toc:12s} {(sh or 0):14,.0f} {fmt(vl):>16s}')
    print('-'*145)
    tot_geral = sum((r[6] or 0) for r in rows)
    print(f'Total exibido: {fmt(total)}    Total geral ({len(rows)} posições): {fmt(tot_geral)}')

if __name__ == '__main__':
    main()
