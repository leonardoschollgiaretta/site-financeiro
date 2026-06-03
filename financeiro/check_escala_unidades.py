"""
check_escala_unidades.py -- Detecta tickers com financeiros possivelmente
gravados em escala errada (ex: milhares em vez de unidades).

Logica: compara mkt_cap (preco * acoes_total) com receita_liquida.
Em geral, P/Receita fica entre 0,1x e 30x. Se sair MUITO disso (ratio > 100x
ou < 0,001x), e candidato a unidade errada.

Uso: python financeiro/check_escala_unidades.py
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

PRIORIDADE = ["investsite", "statusinvest", "yfinance", "manual"]


def melhor_receita(conn, ticker, ano):
    for fonte in PRIORIDADE:
        r = conn.execute(
            "SELECT receita_liquida FROM financeiros_anuais "
            "WHERE ticker=? AND ano=? AND fonte=?",
            (ticker, ano, fonte)
        ).fetchone()
        if r and r[0] is not None:
            return float(r[0]), fonte
    return None, None


def main():
    conn = sqlite3.connect(DB)
    ano_ref = conn.execute(
        "SELECT MAX(ano) FROM financeiros_anuais"
    ).fetchone()[0]
    print(f"Ano-base: {ano_ref}\n")

    tickers = [r[0] for r in conn.execute(
        "SELECT ticker FROM empresas "
        "WHERE moeda='BRL' "
        "AND (considerar IS NULL OR considerar != 'DESCONSIDERAR') "
        "ORDER BY ticker"
    ).fetchall()]

    suspeitos_alto = []   # mkt/receita > 100  -> financeiros provavelmente em milhares
    suspeitos_baixo = []  # mkt/receita < 0.01 -> financeiros provavelmente em mais que reais

    for t in tickers:
        emp = conn.execute(
            "SELECT acoes_total FROM empresas WHERE ticker=?", (t,)
        ).fetchone()
        pa = conn.execute(
            "SELECT preco FROM preco_atual WHERE ticker=?", (t,)
        ).fetchone()
        acoes = float(emp[0]) if emp and emp[0] else None
        preco = float(pa[0]) if pa and pa[0] else None
        if not acoes or not preco:
            continue
        mkt = preco * acoes

        rec, fonte = melhor_receita(conn, t, ano_ref)
        if not rec or rec == 0:
            continue
        ratio = mkt / rec

        if ratio > 100:
            suspeitos_alto.append((t, fonte, mkt, rec, ratio))
        elif ratio < 0.01:
            suspeitos_baixo.append((t, fonte, mkt, rec, ratio))

    conn.close()

    print("=" * 80)
    print("SUSPEITOS: mkt_cap >> receita  (financeiros podem estar em MILHARES)")
    print("=" * 80)
    if not suspeitos_alto:
        print("(nenhum)")
    else:
        suspeitos_alto.sort(key=lambda x: -x[4])
        print(f"{'Ticker':<10}{'Fonte':<14}{'Mkt Cap':>18}{'Receita':>18}{'Ratio':>10}")
        for t, fonte, mkt, rec, ratio in suspeitos_alto:
            print(f"{t:<10}{fonte or '-':<14}{mkt:>18,.0f}{rec:>18,.0f}{ratio:>10,.1f}x")

    print()
    print("=" * 80)
    print("SUSPEITOS: mkt_cap << receita  (anomalia inversa)")
    print("=" * 80)
    if not suspeitos_baixo:
        print("(nenhum)")
    else:
        suspeitos_baixo.sort(key=lambda x: x[4])
        print(f"{'Ticker':<10}{'Fonte':<14}{'Mkt Cap':>18}{'Receita':>18}{'Ratio':>10}")
        for t, fonte, mkt, rec, ratio in suspeitos_baixo:
            print(f"{t:<10}{fonte or '-':<14}{mkt:>18,.0f}{rec:>18,.0f}{ratio:>12,.5f}x")


if __name__ == "__main__":
    main()
