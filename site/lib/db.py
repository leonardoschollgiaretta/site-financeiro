"""
db.py — conexões SOMENTE LEITURA com as cópias dos bancos em site/data/.

Usa o modo read-only do SQLite (URI 'file:...?mode=ro'): mesmo que algum
código tente escrever, o banco recusa. Camada de proteção extra além de
o site já apontar para a cópia (não para os originais).
"""
import os
import sqlite3

SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SITE_DIR, "data")

FUNDOS_DB = os.path.join(DATA_DIR, "fundos_cvm.db")
FINANCEIRO_DB = os.path.join(DATA_DIR, "financeiro.db")


def conectar_ro(caminho):
    """Abre o banco em modo somente leitura. Lança erro claro se faltar."""
    if not os.path.exists(caminho):
        raise FileNotFoundError(
            f"Banco não encontrado: {caminho}\n"
            "Rode antes:  python site/atualizar_dados.py"
        )
    uri = f"file:{caminho}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def conn_fundos():
    return conectar_ro(FUNDOS_DB)


def conn_financeiro():
    return conectar_ro(FINANCEIRO_DB)


def info_atualizacao(caminho):
    """Retorna data de modificação do arquivo do banco (para mostrar no site)."""
    if not os.path.exists(caminho):
        return None
    from datetime import datetime
    return datetime.fromtimestamp(os.path.getmtime(caminho))
