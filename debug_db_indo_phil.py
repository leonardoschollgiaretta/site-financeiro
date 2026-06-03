"""
DEBUG isolado — inspeciona vessels.db para destinos Indonesia/Philippines.
Confere variações de nome, cobertura por ano/mês e totais. Só leitura.
"""
import os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "Weekly report", "vessels.db")

conn = sqlite3.connect(DB)
c = conn.cursor()

print(f"DB: {DB}")
print("Total embarques:", c.execute("SELECT COUNT(*) FROM embarques").fetchone()[0])

print("\n=== destinos (discharge) que contêm indo/phil/filip ===")
for r in c.execute("""
    SELECT discharge, COUNT(*), SUM(quantity_mt)
    FROM embarques
    WHERE LOWER(discharge) LIKE '%indo%' OR LOWER(discharge) LIKE '%phil%'
       OR LOWER(discharge) LIKE '%filip%'
    GROUP BY discharge ORDER BY 2 DESC
"""):
    print(f"   {r[0]!r:20} | {r[1]} linhas | {r[2] or 0:,} mt")

print("\n=== cobertura por ano (via bl_date e eta) ===")
for campo in ("bl_date", "eta"):
    print(f"  -- usando {campo} --")
    for r in c.execute(f"""
        SELECT discharge, substr({campo},1,4) AS ano, COUNT(*), SUM(quantity_mt)
        FROM embarques
        WHERE (LOWER(discharge) LIKE '%indo%' OR LOWER(discharge) LIKE '%phil%' OR LOWER(discharge) LIKE '%filip%')
        GROUP BY discharge, ano ORDER BY discharge, ano
    """):
        print(f"     {r[0]:12} {r[1]}: {r[2]:>4} emb | {r[3] or 0:>12,} mt")

print("\n=== meses presentes por ano (preferindo bl_date, senão eta) ===")
for r in c.execute("""
    SELECT discharge,
           substr(COALESCE(NULLIF(bl_date,''), eta),1,4) AS ano,
           substr(COALESCE(NULLIF(bl_date,''), eta),6,2) AS mes,
           COUNT(*), SUM(quantity_mt)
    FROM embarques
    WHERE (LOWER(discharge) LIKE '%indo%' OR LOWER(discharge) LIKE '%phil%' OR LOWER(discharge) LIKE '%filip%')
    GROUP BY discharge, ano, mes ORDER BY discharge, ano, mes
"""):
    print(f"   {r[0]:12} {r[1]}-{r[2]}: {r[3]:>3} emb | {r[4] or 0:>11,} mt")

print("\n=== por commodity ===")
for r in c.execute("""
    SELECT discharge, commodity,
           substr(COALESCE(NULLIF(bl_date,''), eta),1,4) AS ano,
           COUNT(*), SUM(quantity_mt)
    FROM embarques
    WHERE (LOWER(discharge) LIKE '%indo%' OR LOWER(discharge) LIKE '%phil%' OR LOWER(discharge) LIKE '%filip%')
    GROUP BY discharge, commodity, ano ORDER BY discharge, ano, 5 DESC
"""):
    print(f"   {r[0]:12} {r[2]} {r[1]:<14} {r[3]:>3} emb | {r[4] or 0:>11,} mt")

conn.close()
