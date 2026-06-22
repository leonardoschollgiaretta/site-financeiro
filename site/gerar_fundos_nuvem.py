# -*- coding: utf-8 -*-
"""
gerar_fundos_nuvem.py — cria uma versão REDUZIDA do fundos_cvm.db para o deploy
na nuvem (cabe no GitHub). Estratégia:

  • os TOP 500 fundos por valor médio investido em ações  -> TODOS os meses
  • os demais fundos                                       -> só meses "intercalados"
    (a cada 4 meses, a partir do mais recente)

Saída: site/dados_nuvem/fundos_cvm.db  (~77 MB)
Rodar quando quiser atualizar a fatia da nuvem:
    python site/gerar_fundos_nuvem.py
"""
import os
import sqlite3

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(SITE_DIR)
ORIGEM = os.path.join(RAIZ, "fundos_cvm", "fundos_cvm.db")
DESTINO = os.path.join(SITE_DIR, "dados_nuvem", "fundos_cvm.db")

TOP_N = 500            # fundos com histórico completo
PASSO_MESES = 4        # demais fundos: 1 a cada PASSO_MESES


def main():
    if not os.path.exists(ORIGEM):
        print(f"Origem não encontrada: {ORIGEM}")
        return
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    if os.path.exists(DESTINO):
        os.remove(DESTINO)

    src = sqlite3.connect(ORIGEM)
    src.row_factory = sqlite3.Row

    periodos = [r[0] for r in src.execute(
        "SELECT DISTINCT periodo FROM posicoes_acoes ORDER BY periodo")]
    intercalados = sorted(periodos[::-1][::PASSO_MESES])
    top = [r[0] for r in src.execute(
        "SELECT cnpj_fundo FROM posicoes_acoes "
        "GROUP BY cnpj_fundo ORDER BY AVG(vl_mercado) DESC LIMIT ?", (TOP_N,))]

    print(f"Períodos: {periodos}")
    print(f"Intercalados (resto): {intercalados}")
    print(f"Top {len(top)} fundos com histórico completo.")

    novo = sqlite3.connect(DESTINO)
    novo.execute("ATTACH DATABASE ? AS src", (ORIGEM,))
    ph_top = ",".join("?" * len(top))
    ph_per = ",".join("?" * len(intercalados))

    # nome da coluna de CNPJ do fundo em cada tabela (fundos usa 'cnpj')
    col_cnpj = {"fundos": "cnpj", "posicoes_acoes": "cnpj_fundo"}

    for t in ("fundo_id", "fundos", "posicoes_acoes"):
        sql = src.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0]
        novo.execute(sql)
        if t == "fundo_id":
            novo.execute(f"INSERT INTO {t} SELECT * FROM src.{t}")
        else:
            cc = col_cnpj[t]
            # top500: todos os meses ; resto: só intercalados
            novo.execute(
                f"""INSERT INTO {t} SELECT * FROM src.{t}
                    WHERE {cc} IN ({ph_top})
                       OR periodo IN ({ph_per})""",
                top + intercalados)
        n = novo.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n:,} linhas")

    # recria os índices do original (performance no site)
    for (sql,) in src.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
        try:
            novo.execute(sql)
        except Exception:
            pass

    novo.commit()
    novo.execute("VACUUM")
    novo.close()
    src.close()
    mb = os.path.getsize(DESTINO) / 1024 / 1024
    print(f"\nOK -> {DESTINO}  ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
