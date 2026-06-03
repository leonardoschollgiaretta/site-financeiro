"""
carteiras.py — salvar/carregar carteiras do simulador (sem login).

Persiste em site/carteiras_salvas/carteiras.json (arquivo local, gravável).
Não toca nos bancos (que são read-only). Cada carteira = nome -> {ticker: peso%}.
"""
import json
import os

SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(SITE_DIR, "carteiras_salvas")
ARQ = os.path.join(PASTA, "carteiras.json")


def _carregar_tudo():
    if not os.path.exists(ARQ):
        return {}
    try:
        with open(ARQ, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _salvar_tudo(d):
    os.makedirs(PASTA, exist_ok=True)
    with open(ARQ, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def listar():
    """Nomes das carteiras salvas."""
    return sorted(_carregar_tudo().keys())


def salvar(nome, pesos):
    """Salva/atualiza uma carteira. pesos = {ticker: peso_percentual}."""
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Dê um nome à carteira.")
    d = _carregar_tudo()
    d[nome] = {tk: float(p) for tk, p in pesos.items()}
    _salvar_tudo(d)


def carregar(nome):
    """Retorna {ticker: peso} de uma carteira salva, ou None."""
    return _carregar_tudo().get(nome)


def excluir(nome):
    d = _carregar_tudo()
    if nome in d:
        del d[nome]
        _salvar_tudo(d)
