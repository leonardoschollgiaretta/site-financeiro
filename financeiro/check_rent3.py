"""Diagnostico do P/VP do RENT3."""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

conn = sqlite3.connect(DB)

print("=" * 70)
print("RENT3 - componentes do P/VP")
print("=" * 70)

emp = conn.execute(
    "SELECT acoes_free, acoes_total FROM empresas WHERE ticker='RENT3'"
).fetchone()
pa = conn.execute(
    "SELECT preco, data_fechamento FROM preco_atual WHERE ticker='RENT3'"
).fetchone()
fin = conn.execute(
    "SELECT ano, fonte, patrimonio_liquido, lucro_liquido "
    "FROM financeiros_anuais WHERE ticker='RENT3' ORDER BY ano DESC, fonte"
).fetchall()

print(f"\nacoes_free  = {emp[0]:,}" if emp and emp[0] else "acoes_free  = -")
print(f"acoes_total = {emp[1]:,}" if emp and emp[1] else "acoes_total = -")
print(f"preco       = {pa[0]} (data: {pa[1]})" if pa else "preco       = -")

print("\nfinanceiros (ano, fonte, PL, LL):")
for row in fin:
    pl = f"{row[2]:,}" if row[2] is not None else "-"
    ll = f"{row[3]:,}" if row[3] is not None else "-"
    print(f"  {row[0]} {row[1]:<14} PL={pl:>20}  LL={ll:>20}")

# Calcula P/VP usando acoes_free (como faz o calcular_indicadores_ticker)
if emp and pa and fin:
    acoes_free = float(emp[0]) if emp[0] else None
    acoes_total = float(emp[1]) if emp[1] else None
    preco = float(pa[0]) if pa[0] else None
    pl_ultimo = next((float(r[2]) for r in fin if r[2] is not None), None)

    print("\n--- calculo P/VP ---")
    if acoes_free and preco and pl_ultimo:
        mkt_free = preco * acoes_free
        pvp_free = mkt_free / pl_ultimo
        print(f"mkt_cap (preco x acoes_FREE)  = {mkt_free:,.0f}")
        print(f"P/VP (com acoes_free)         = {pvp_free:.2f}")
    if acoes_total and preco and pl_ultimo:
        mkt_total = preco * acoes_total
        pvp_total = mkt_total / pl_ultimo
        print(f"mkt_cap (preco x acoes_TOTAL) = {mkt_total:,.0f}")
        print(f"P/VP (com acoes_total)        = {pvp_total:.2f}")
    print(f"PL ultimo                      = {pl_ultimo:,.0f}")

conn.close()
