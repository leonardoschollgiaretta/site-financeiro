"""
banco.py -- Cria/atualiza o schema do SQLite (cambio.db).

Tabelas:
  - cotacoes:        cotacao diaria por par
  - janelas:         pre-calculo de janelas para cada par
  - meta:            chave-valor (ultima_atualizacao, ultima_calc_janelas, etc.)
"""
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "data" / "cambio.db"


def criar_banco():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Cotacoes diarias
    c.execute("""
        CREATE TABLE IF NOT EXISTS cotacoes (
            par   TEXT NOT NULL,
            data  TEXT NOT NULL,
            preco REAL NOT NULL,
            PRIMARY KEY (par, data)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_cotacoes_par_data ON cotacoes(par, data)")

    # Janelas pre-calculadas
    # Para cada par, data_ini, tamanho_base: var_base + var_seg em multiplos horizontes
    c.execute("""
        CREATE TABLE IF NOT EXISTS janelas (
            par             TEXT NOT NULL,
            data_ini        TEXT NOT NULL,
            tamanho_base    INTEGER NOT NULL,
            preco_ini       REAL NOT NULL,
            preco_fim_base  REAL NOT NULL,
            var_base_pct    REAL NOT NULL,
            var_seg_5       REAL,
            var_seg_10      REAL,
            var_seg_21      REAL,
            var_seg_63      REAL,
            PRIMARY KEY (par, data_ini, tamanho_base)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_janelas_par_t ON janelas(par, tamanho_base)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_janelas_var ON janelas(par, var_base_pct)")

    # Meta: chave/valor
    c.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"Banco pronto: {DB_PATH}")


def conectar():
    return sqlite3.connect(DB_PATH)


if __name__ == "__main__":
    criar_banco()
