"""
Detecta tickers BR onde acoes_free e acoes_total estao em escalas diferentes
(diferenca > 100x sugere unidade errada em uma das duas colunas).
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

conn = sqlite3.connect(DB)
rows = conn.execute("""
    SELECT ticker, acoes_free, acoes_total
    FROM empresas
    WHERE moeda='BRL'
      AND (considerar IS NULL OR considerar != 'DESCONSIDERAR')
      AND acoes_free IS NOT NULL
      AND acoes_total IS NOT NULL
      AND acoes_free > 0
      AND acoes_total > 0
""").fetchall()
conn.close()

# Free deveria ser <= total. Razao saudavel: 0.05 a 1.0
# Razao > 10 ou < 0.001 indica escala diferente
suspeitos = []
for t, free, total in rows:
    razao = free / total
    if razao > 10 or razao < 0.001:
        suspeitos.append((t, free, total, razao))

print(f"{'Ticker':<10}{'acoes_free':>20}{'acoes_total':>20}{'free/total':>14}")
print("-" * 64)
if not suspeitos:
    print("(nenhum suspeito)")
else:
    suspeitos.sort(key=lambda x: -x[3])
    for t, free, total, razao in suspeitos:
        print(f"{t:<10}{free:>20,.0f}{total:>20,.0f}{razao:>14,.2f}x")
