"""Mostra valores brutos do banco para VIVA3 e NEXP3 (validacao da escala)."""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

CAMPOS = [
    "receita_liquida", "lucro_bruto", "lucro_liquido",
    "patrimonio_liquido", "divida_bruta", "divida_liquida",
    "fco", "capex", "fcl",
]


def fmt(v):
    if v is None:
        return "-"
    return f"{float(v):>20,.0f}"


def mostrar(ticker, conn):
    print(f"\n{'='*100}")
    print(f"  {ticker}")
    print(f"{'='*100}")
    rows = conn.execute(
        f"SELECT ano, fonte, {', '.join(CAMPOS)} "
        f"FROM financeiros_anuais WHERE ticker=? ORDER BY ano DESC, fonte",
        (ticker,)
    ).fetchall()
    if not rows:
        print("  (sem dados)")
        return
    print(f"  {'ano':<6}{'fonte':<14}" + "".join(f"{c[:14]:>16}" for c in CAMPOS))
    for row in rows:
        ano, fonte = row[0], row[1]
        vals = row[2:]
        print(f"  {ano:<6}{fonte or '-':<14}" + "".join(
            f"{(float(v) if v is not None else 0):>16,.0f}" if v is not None else f"{'-':>16}"
            for v in vals
        ))

    # Mkt cap pra referência
    emp = conn.execute("SELECT acoes_total FROM empresas WHERE ticker=?", (ticker,)).fetchone()
    pa = conn.execute("SELECT preco FROM preco_atual WHERE ticker=?", (ticker,)).fetchone()
    if emp and emp[0] and pa and pa[0]:
        mkt = float(emp[0]) * float(pa[0])
        print(f"\n  Mkt cap atual (preco x acoes_total): {mkt:,.0f}")


def main():
    tickers = [
        # Grupo A (mkt >> receita): suspeita de financeiros em milhares OU dado quebrado
        "NEXP3", "RENT3", "VIVR3", "AMAR3", "SHOW3", "RAPT3", "RAPT4",
        # Grupo B (mkt << receita): suspeita de financeiros em escala 1000x maior
        "HAGA4", "PTNT3", "MTSA4", "PTNT4", "HAGA3", "VIVA3",
    ]
    conn = sqlite3.connect(DB)
    for t in tickers:
        mostrar(t, conn)
    conn.close()


if __name__ == "__main__":
    main()
