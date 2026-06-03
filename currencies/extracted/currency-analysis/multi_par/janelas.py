"""
janelas.py -- Pre-calcula a tabela de janelas para um par especifico.

Logica:
  Para cada data_ini (data com cotacao) e cada tamanho_base (5..50):
    - preco_ini       = cotacao em data_ini
    - preco_fim_base  = cotacao em (data_ini + tamanho_base - 1) [pregoes]
    - var_base_pct    = (preco_fim_base / preco_ini - 1) * 100
    - var_seg_X       = (cotacao em (data_fim_base + X) / preco_fim_base - 1) * 100
                        para X em [5, 10, 21, 63]

Janelas onde nao da pra calcular (final da serie) sao puladas.
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banco import conectar


TAMANHOS_BASE = list(range(5, 51))  # 5 a 50 dias
HORIZONTES = [5, 10, 21, 63]        # quantos dias depois projetar


def carregar_cotacoes(conn, par):
    """Retorna lista [(data, preco), ...] ordenada por data."""
    rows = conn.execute(
        "SELECT data, preco FROM cotacoes WHERE par=? ORDER BY data",
        (par,)
    ).fetchall()
    return rows


def calcular_janelas(par, conn=None):
    """Recalcula todas as janelas do par. Apaga e recria."""
    fechar_no_fim = False
    if conn is None:
        conn = conectar()
        fechar_no_fim = True

    print(f"  calculando janelas de {par}...")
    rows = carregar_cotacoes(conn, par)
    if len(rows) < max(TAMANHOS_BASE) + max(HORIZONTES) + 1:
        print(f"  poucos dados ({len(rows)} cotacoes). Pulando.")
        if fechar_no_fim:
            conn.close()
        return 0

    # Indexa: data -> idx, lista de precos paralela
    datas  = [r[0] for r in rows]
    precos = [r[1] for r in rows]
    n = len(datas)

    # Apaga janelas antigas do par
    conn.execute("DELETE FROM janelas WHERE par=?", (par,))
    conn.commit()

    # Gera janelas
    batch = []
    BATCH_SIZE = 5000
    total = 0

    max_horizonte = max(HORIZONTES)

    for i in range(n):
        for T in TAMANHOS_BASE:
            j_fim_base = i + T - 1
            if j_fim_base >= n:
                break  # nao tem dados ate o fim do base

            # Calcula var_base
            preco_ini = precos[i]
            preco_fim_base = precos[j_fim_base]
            if preco_ini <= 0:
                continue
            var_base = (preco_fim_base / preco_ini - 1) * 100

            # Calcula var_seg para cada horizonte (None se passar do fim)
            vars_seg = []
            for h in HORIZONTES:
                j_fim_seg = j_fim_base + h
                if j_fim_seg >= n:
                    vars_seg.append(None)
                else:
                    if preco_fim_base <= 0:
                        vars_seg.append(None)
                    else:
                        vars_seg.append(
                            (precos[j_fim_seg] / preco_fim_base - 1) * 100
                        )

            # Se TODOS os var_seg sao None, nao adianta gravar
            if all(v is None for v in vars_seg):
                continue

            batch.append((
                par, datas[i], T, preco_ini, preco_fim_base, var_base,
                vars_seg[0], vars_seg[1], vars_seg[2], vars_seg[3],
            ))

            if len(batch) >= BATCH_SIZE:
                conn.executemany("""
                    INSERT INTO janelas (
                        par, data_ini, tamanho_base, preco_ini, preco_fim_base,
                        var_base_pct, var_seg_5, var_seg_10, var_seg_21, var_seg_63
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """, batch)
                conn.commit()
                total += len(batch)
                batch = []

    # Resto do batch
    if batch:
        conn.executemany("""
            INSERT INTO janelas (
                par, data_ini, tamanho_base, preco_ini, preco_fim_base,
                var_base_pct, var_seg_5, var_seg_10, var_seg_21, var_seg_63
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()
        total += len(batch)

    # Atualiza meta
    conn.execute(
        "INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?)",
        (f"ultima_calc_{par}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

    print(f"  {total:,} janelas gravadas para {par}")

    if fechar_no_fim:
        conn.close()
    return total


def janelas_atualizadas(par, conn=None):
    """
    Retorna True se as janelas do par estao atualizadas em relacao as cotacoes.
    Compara a ultima data de cotacoes vs ultimo dia coberto pelas janelas.
    """
    fechar_no_fim = False
    if conn is None:
        conn = conectar()
        fechar_no_fim = True

    ult_cot = conn.execute(
        "SELECT MAX(data) FROM cotacoes WHERE par=?", (par,)
    ).fetchone()[0]
    ult_jan = conn.execute(
        "SELECT MAX(data_ini) FROM janelas WHERE par=?", (par,)
    ).fetchone()[0]

    if fechar_no_fim:
        conn.close()

    if ult_cot is None:
        return False  # nao tem cotacoes
    if ult_jan is None:
        return False  # nao tem janelas

    # Tolera defasagem de ate (max_tamanho + max_horizonte) dias
    # porque janelas mais recentes podem nao ter horizontes suficientes
    folga = max(TAMANHOS_BASE) + max(HORIZONTES)
    ult_cot_dt = datetime.strptime(ult_cot, "%Y-%m-%d")
    ult_jan_dt = datetime.strptime(ult_jan, "%Y-%m-%d")
    delta = (ult_cot_dt - ult_jan_dt).days
    return delta <= folga


if __name__ == "__main__":
    # Recalcula janelas de todos os pares
    from coletar import PARES
    conn = conectar()
    for par in PARES:
        calcular_janelas(par, conn)
    conn.close()
