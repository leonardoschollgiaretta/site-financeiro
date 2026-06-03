"""
fix_acoes_free.py -- Corrige acoes_free dos 5 tickers do grupo A.

No fix_escala_unidades.py original, dividi acoes_total / 1000 mas esqueci
acoes_free, que tambem estava em milhares. O ranking usa acoes_free para
calcular mkt_cap, entao P/L e P/VP sairam absurdos (ex: RENT3 com P/VP=2071
em vez de ~2,1).

Confirmado por check_acoes_free.py: free/total ~= 1000x nesses 5 tickers.

Faz backup, mostra dry-run, pede confirmacao.
"""
import os
import sqlite3
import shutil
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")
TICKERS = ["RENT3", "RAPT3", "RAPT4", "AMAR3", "SHOW3"]


def backup_db():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = f"{DB}.bak_{ts}"
    shutil.copy2(DB, dst)
    print(f"Backup: {dst}")


def main():
    backup_db()
    conn = sqlite3.connect(DB)

    print("\nDRY-RUN (acoes_free /= 1000):\n")
    print(f"  {'Ticker':<8}{'free atual':>22}{'free novo':>22}"
          f"{'total (referencia)':>22}")
    for t in TICKERS:
        row = conn.execute(
            "SELECT acoes_free, acoes_total FROM empresas WHERE ticker=?", (t,)
        ).fetchone()
        if not row:
            continue
        free, total = row
        novo = (free / 1000) if free else None
        print(f"  {t:<8}{free!s:>22}{novo!s:>22}{total!s:>22}")

    resp = input("\nAplicar? (digite SIM): ").strip()
    if resp != "SIM":
        print("Cancelado.")
        conn.close()
        return

    cur = conn.cursor()
    placeholders = ",".join("?" * len(TICKERS))
    cur.execute(
        f"UPDATE empresas SET acoes_free = acoes_free / 1000.0 "
        f"WHERE ticker IN ({placeholders}) AND acoes_free IS NOT NULL",
        TICKERS
    )
    print(f"\n{cur.rowcount} linhas atualizadas.")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
