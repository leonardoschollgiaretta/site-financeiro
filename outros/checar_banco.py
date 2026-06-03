import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")
conn = sqlite3.connect(DB)
c = conn.cursor()

print("=== EMPRESAS CADASTRADAS ===")
c.execute("SELECT ticker, nome, bolsa, moeda FROM empresas ORDER BY moeda, ticker")
for r in c.fetchall():
    print(f"  {r[0]:6} | {r[3]} | {r[2]:8} | {r[1]}")

print("\n=== DADOS FINANCEIROS POR EMPRESA ===")
c.execute("""SELECT ticker, COUNT(DISTINCT ano), MIN(ano), MAX(ano)
             FROM financeiros_anuais GROUP BY ticker ORDER BY ticker""")
for r in c.fetchall():
    print(f"  {r[0]:6} | {r[1]} anos ({r[2]}-{r[3]})")

print("\n=== AMOSTRA AAPL 2024 ===")
c.execute("""SELECT receita_liquida, lucro_liquido, ativo_total, patrimonio_liquido, fco
             FROM financeiros_anuais WHERE ticker='AAPL' AND ano=2024""")
r = c.fetchone()
if r:
    print(f"  Receita:     USD {r[0]/1e9:.1f}B" if r[0] else "  Receita: N/A")
    print(f"  Lucro:       USD {r[1]/1e9:.1f}B" if r[1] else "  Lucro: N/A")
    print(f"  Ativo Total: USD {r[2]/1e9:.1f}B" if r[2] else "  Ativo: N/A")
    print(f"  Patrim. Liq: USD {r[3]/1e9:.1f}B" if r[3] else "  PL: N/A")
    print(f"  FCO:         USD {r[4]/1e9:.1f}B" if r[4] else "  FCO: N/A")

conn.close()
