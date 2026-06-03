"""
fix_escala_unidades.py -- Corrige escala/dados de tickers BR identificados
no diagnostico (check_escala_unidades.py + inspecao manual).

JA APLICADO em 2026-05-10:

  1) Grupo A: dividir acoes_total / 1000
       RENT3, RAPT3, RAPT4, AMAR3, SHOW3

  2) Grupo B: dividir financeiros monetarios / 1000
       VIVA3, HAGA3, HAGA4, PTNT3, PTNT4, MTSA4

  3) Linha 2025 quebrada -> DELETE
       NEXP3, VIVR3

Pendente: ver fix_acoes_free.py (acoes_free desses mesmos 5 tickers do
grupo A tambem precisa /1000, foi esquecido neste script).
"""
import os
import sqlite3
import shutil
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

GRUPO_A_ACOES = ["RENT3", "RAPT3", "RAPT4", "AMAR3", "SHOW3"]
GRUPO_B_FIN   = ["VIVA3", "HAGA3", "HAGA4", "PTNT3", "PTNT4", "MTSA4"]
LINHAS_2025_QUEBRADAS = ["NEXP3", "VIVR3"]

CAMPOS_FIN = [
    "receita_liquida", "lucro_bruto", "lucro_liquido",
    "patrimonio_liquido", "divida_bruta", "divida_liquida",
    "fco", "fci", "fcf_financiamento", "capex", "fcl",
]


def backup_db():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = f"{DB}.bak_{ts}"
    shutil.copy2(DB, dst)
    print(f"Backup criado: {dst}")
    return dst


def dry_run(conn):
    print("\n" + "=" * 80)
    print("DRY-RUN (nada foi gravado ainda)")
    print("=" * 80)

    print("\n[1] acoes_total /= 1000 em:")
    for t in GRUPO_A_ACOES:
        row = conn.execute(
            "SELECT acoes_total FROM empresas WHERE ticker=?", (t,)
        ).fetchone()
        atual = row[0] if row else None
        novo = (atual / 1000) if atual else None
        print(f"  {t:<8} {atual!s:>20}  ->  {novo!s:>20}")

    print("\n[2] Financeiros /= 1000 em (mostra so receita 2025 como amostra):")
    for t in GRUPO_B_FIN:
        row = conn.execute(
            "SELECT receita_liquida FROM financeiros_anuais "
            "WHERE ticker=? AND ano=(SELECT MAX(ano) FROM financeiros_anuais WHERE ticker=?)",
            (t, t)
        ).fetchone()
        atual = row[0] if row else None
        novo = (atual / 1000) if atual else None
        n_linhas = conn.execute(
            "SELECT COUNT(*) FROM financeiros_anuais WHERE ticker=?", (t,)
        ).fetchone()[0]
        print(f"  {t:<8} receita atual: {atual!s:>20} -> {novo!s:>20}  "
              f"({n_linhas} linhas serao afetadas)")

    print("\n[3] DELETE da linha 2025 em:")
    for t in LINHAS_2025_QUEBRADAS:
        row = conn.execute(
            "SELECT receita_liquida, lucro_liquido FROM financeiros_anuais "
            "WHERE ticker=? AND ano=2025",
            (t,)
        ).fetchone()
        if row:
            print(f"  {t:<8} receita_2025={row[0]!s:>15}  lucro_2025={row[1]!s:>15}")
        else:
            print(f"  {t:<8} (sem linha 2025, nada a fazer)")


def aplicar(conn):
    cur = conn.cursor()

    # 1) acoes_total /= 1000
    for t in GRUPO_A_ACOES:
        cur.execute(
            "UPDATE empresas SET acoes_total = acoes_total / 1000.0 "
            "WHERE ticker=? AND acoes_total IS NOT NULL",
            (t,)
        )
    print(f"[1] acoes_total atualizado em {len(GRUPO_A_ACOES)} tickers.")

    # 2) Financeiros /= 1000
    set_clause = ", ".join(
        f"{c} = {c} / 1000.0" for c in CAMPOS_FIN
    )
    placeholders = ",".join("?" * len(GRUPO_B_FIN))
    cur.execute(
        f"UPDATE financeiros_anuais SET {set_clause} "
        f"WHERE ticker IN ({placeholders})",
        GRUPO_B_FIN
    )
    print(f"[2] {cur.rowcount} linhas de financeiros divididas por 1000.")

    # 3) DELETE linha 2025
    placeholders = ",".join("?" * len(LINHAS_2025_QUEBRADAS))
    cur.execute(
        f"DELETE FROM financeiros_anuais "
        f"WHERE ano=2025 AND ticker IN ({placeholders})",
        LINHAS_2025_QUEBRADAS
    )
    print(f"[3] {cur.rowcount} linhas 2025 removidas.")

    conn.commit()


def main():
    backup_db()
    conn = sqlite3.connect(DB)

    dry_run(conn)

    resp = input("\nAplicar UPDATEs e DELETEs? (digite SIM): ").strip()
    if resp != "SIM":
        print("Cancelado. Nada foi gravado.")
        conn.close()
        return

    aplicar(conn)
    conn.close()
    print("\nConcluido.")


if __name__ == "__main__":
    main()
