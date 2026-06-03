"""
db_utils.py — Funções compartilhadas de acesso ao banco
"""
from datetime import datetime


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def upsert_financeiro(conn, ticker, ano, fonte, campos):
    """
    Insere ou atualiza campos em financeiros_anuais.
    Sempre registra atualizado_em com o momento atual.
    """
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO financeiros_anuais (ticker, ano, fonte, atualizado_em)
        VALUES (?, ?, ?, ?)
    """, (ticker, ano, fonte, agora()))

    campos["atualizado_em"] = agora()
    for coluna, valor in campos.items():
        if valor is not None:
            c.execute(f"""
                UPDATE financeiros_anuais SET {coluna} = ?
                WHERE ticker = ? AND ano = ? AND fonte = ?
            """, (valor, ticker, ano, fonte))
