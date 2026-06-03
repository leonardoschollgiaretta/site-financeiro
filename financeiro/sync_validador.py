"""
sync_validador.py — Sincroniza validador.xlsx → banco de dados.

Lê o arquivo validador.xlsx e atualiza:
  - tabela validacoes  (quais ticker/tipo/ano estão travados)
  - campo  considerar  em empresas

Chamado automaticamente no início do run_all.py.
Pode ser rodado isoladamente: python sync_validador.py
"""
import sqlite3
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")
ARQUIVO  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validador.xlsx")

TIPOS = ["DRE", "Balanco", "Fluxo", "Dividendos", "Acoes", "Precos"]
ANOS  = [2025, 2024, 2023, 2022, 2021, 2020]

# Mapeamento nome coluna Excel → valor salvo no banco
TIPO_MAP = {
    "DRE":       "dre",
    "Balanco":   "balanco",
    "Fluxo":     "fluxo",
    "Dividendos":"dividendos",
    "Acoes":     "acoes",
    "Precos":    "precos",
}


def _processar_aba(df, conn):
    """Processa uma aba do validador. Retorna (atualizados, validacoes)."""
    df.columns = [str(c).strip() for c in df.columns]
    df = df.fillna("")

    if "Ticker" not in df.columns:
        return 0, 0

    atualizados = 0
    validacoes  = 0

    for _, row in df.iterrows():
        ticker = str(row.get("Ticker", "")).strip().upper()
        if not ticker:
            continue

        # Atualiza campo considerar em empresas
        considerar = str(row.get("CONSIDERAR?", "")).strip()
        if considerar:
            conn.execute(
                "UPDATE empresas SET considerar=? WHERE ticker=?",
                (considerar, ticker)
            )
            atualizados += 1

        # Valida tipos
        for col_nome, tipo_val in TIPO_MAP.items():
            val = str(row.get(col_nome, "")).strip().upper()
            if val == "VALIDADO":
                conn.execute(
                    "INSERT OR IGNORE INTO validacoes (ticker, kind, valor) VALUES (?,?,?)",
                    (ticker, "tipo", tipo_val)
                )
                validacoes += 1

        # Valida anos (so processa anos que existem como coluna na aba —
        # aba BR tem 6 anos, aba US tem 4, e o get() retorna "" pros ausentes)
        for ano in ANOS:
            val = str(row.get(str(ano), "")).strip().upper()
            if val == "VALIDADO":
                conn.execute(
                    "INSERT OR IGNORE INTO validacoes (ticker, kind, valor) VALUES (?,?,?)",
                    (ticker, "ano", str(ano))
                )
                validacoes += 1

    return atualizados, validacoes


def sincronizar():
    if not os.path.exists(ARQUIVO):
        print(f"  ⚠️  validador.xlsx não encontrado — sync ignorado")
        return

    try:
        xls = pd.ExcelFile(ARQUIVO)
    except Exception as e:
        print(f"  ❌ Erro ao abrir validador.xlsx: {e}")
        return

    abas_alvo = [n for n in xls.sheet_names if n in ("Validador", "Validador US")]
    if not abas_alvo:
        print("  ❌ Nenhuma aba 'Validador' ou 'Validador US' encontrada")
        return

    conn = sqlite3.connect(DB)

    # Limpa todas as validacoes atuais — vai reescrever do zero (a partir das 2 abas)
    conn.execute("DELETE FROM validacoes")

    atualizados_total = 0
    validacoes_total  = 0

    for aba in abas_alvo:
        try:
            df = pd.read_excel(ARQUIVO, sheet_name=aba, header=2, dtype=str)
        except Exception as e:
            print(f"  ⚠️  Erro lendo aba '{aba}': {e}")
            continue

        a, v = _processar_aba(df, conn)
        atualizados_total += a
        validacoes_total  += v
        print(f"     [{aba}] {a} tickers | {v} validacoes")

    conn.commit()
    conn.close()

    print(f"  ✅ Sync validador: {atualizados_total} tickers | {validacoes_total} validacoes gravadas")


if __name__ == "__main__":
    import banco
    banco.criar_banco()
    sincronizar()
