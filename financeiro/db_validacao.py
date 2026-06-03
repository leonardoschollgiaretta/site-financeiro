"""
db_validacao.py — Helper de validação compartilhado entre coletores.

Regra: um (ticker, tipo, ano) só pode ser recoletado se:
  - O TIPO não estiver marcado como VALIDADO  (kind='tipo', valor=tipo)
  - E o ANO  não estiver marcado como VALIDADO (kind='ano',  valor=str(ano))

Se qualquer um dos dois estiver validado, o coletor pula aquela combinação.
coletor_fechamento (preco_atual) é sempre ignorado — nunca bloqueado.
"""


def is_validado(conn, ticker, tipo, ano):
    """
    Retorna True se esta combinação deve ser pulada.
    tipo: 'dre' | 'balanco' | 'fluxo' | 'dividendos' | 'acoes' | 'precos'
    ano : int
    """
    r = conn.execute(
        "SELECT 1 FROM validacoes WHERE ticker=? AND kind='tipo' AND valor=?",
        (ticker, tipo)
    ).fetchone()
    if r:
        return True
    r = conn.execute(
        "SELECT 1 FROM validacoes WHERE ticker=? AND kind='ano' AND valor=?",
        (ticker, str(ano))
    ).fetchone()
    return bool(r)
