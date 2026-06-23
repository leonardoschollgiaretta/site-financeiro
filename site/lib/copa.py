"""
copa.py — dados e estrutura do bracket da Copa do Mundo 2026 (48 times, 12 grupos).

Lê os 12 grupos (A–L, 4 times cada) do bolao.db. A estrutura do mata-mata
(Round of 32 → Final) segue o chaveamento oficial da FIFA 2026: os 2 primeiros
de cada grupo + 8 melhores terceiros = 32 times.

A página de simulação usa SLOTS textuais ('1A', '2B', '3CDFGH', ...). Cabe ao
usuário definir a ordem de cada grupo e quais terceiros entram em cada vaga.
"""
import os
import sqlite3

_SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RAIZ = os.path.dirname(_SITE_DIR)
# local: bolao_copa/bolao.db. Na nuvem (sem essa pasta): site/dados_nuvem/bolao.db.
_BOLAO_LOCAL = os.path.join(_RAIZ, "bolao_copa", "bolao.db")
_BOLAO_NUVEM = os.path.join(_SITE_DIR, "dados_nuvem", "bolao.db")
_BOLAO_DB = _BOLAO_LOCAL if os.path.exists(_BOLAO_LOCAL) else _BOLAO_NUVEM


def grupos():
    """{ 'A': [time1..time4], ... } lido do bolao.db. Vazio se não houver banco."""
    if not os.path.exists(_BOLAO_DB):
        return {}
    out = {}
    with sqlite3.connect(_BOLAO_DB) as c:
        try:
            rows = c.execute(
                "SELECT DISTINCT grupo, time_casa, time_fora "
                "FROM jogos WHERE fase='grupos'").fetchall()
        except Exception:
            return {}
    for grupo, casa, fora in rows:
        out.setdefault(grupo, set()).update([casa, fora])
    return {g: sorted(t) for g, t in sorted(out.items())}


def data_ultimo_resultado():
    """Data (str AAAA-MM-DD) do jogo mais recente COM placar — a 'data dos
    resultados' carregados. None se nenhum jogo tem resultado."""
    if not os.path.exists(_BOLAO_DB):
        return None
    with sqlite3.connect(_BOLAO_DB) as c:
        try:
            r = c.execute(
                "SELECT MAX(data) FROM jogos "
                "WHERE fase='grupos' AND gols_casa IS NOT NULL").fetchone()
        except Exception:
            return None
    return r[0] if r and r[0] else None


def classificacao_grupos():
    """Calcula a tabela de cada grupo a partir dos placares gravados no bolao.db.

    Critérios de desempate (FIFA): pontos → saldo de gols → gols pró → ordem alfab.
    Retorna { 'A': [ {time, J, V, E, D, GP, GC, SG, Pts}, ... ordenado ], ... }.
    Times sem jogo entram com tudo zero (vão pro fim).
    """
    if not os.path.exists(_BOLAO_DB):
        return {}
    gs = grupos()
    # tabela inicial: todos os times do grupo zerados
    tab = {g: {t: dict(time=t, J=0, V=0, E=0, D=0, GP=0, GC=0)
               for t in times} for g, times in gs.items()}
    with sqlite3.connect(_BOLAO_DB) as c:
        rows = c.execute(
            "SELECT grupo, time_casa, time_fora, gols_casa, gols_fora "
            "FROM jogos WHERE fase='grupos' AND gols_casa IS NOT NULL").fetchall()
    for g, casa, fora, gc, gf in rows:
        if g not in tab or casa not in tab[g] or fora not in tab[g]:
            continue
        tc, tf = tab[g][casa], tab[g][fora]
        tc["J"] += 1; tf["J"] += 1
        tc["GP"] += gc; tc["GC"] += gf
        tf["GP"] += gf; tf["GC"] += gc
        if gc > gf:
            tc["V"] += 1; tf["D"] += 1
        elif gc < gf:
            tf["V"] += 1; tc["D"] += 1
        else:
            tc["E"] += 1; tf["E"] += 1

    out = {}
    for g, times in tab.items():
        linhas = []
        for d in times.values():
            d["SG"] = d["GP"] - d["GC"]
            d["Pts"] = d["V"] * 3 + d["E"]
            linhas.append(d)
        linhas.sort(key=lambda d: (-d["Pts"], -d["SG"], -d["GP"], d["time"]))
        out[g] = linhas
    return out


# Round of 32 — chaveamento oficial FIFA 2026 (16 jogos M73–M88), exatamente
# como no bracket oficial (imagem). Cada jogo: (codigo, slot_casa, slot_fora).
# Slots '1X'/'2X' = 1º/2º do grupo X. Slots '3XXXX' = melhor terceiro de um dos
# grupos listados (o usuário escolhe qual seleção ocupa a vaga).
# Ordem aqui = ordem visual de cima p/ baixo no bracket (esquerda e direita).
R32 = [
    # --- chave de cima, lado esquerdo ---
    ("M74", "1E", "3ABCDF"),
    ("M77", "1I", "3CDFGH"),
    ("M73", "2A", "2B"),
    ("M75", "1F", "2C"),
    # --- chave de baixo, lado esquerdo ---
    ("M83", "2K", "2L"),
    ("M84", "1H", "2J"),
    ("M81", "1D", "3BEFIJ"),
    ("M82", "1G", "3AEHIJ"),
    # --- chave de cima, lado direito ---
    ("M76", "1C", "2F"),
    ("M78", "2E", "2I"),
    ("M79", "1A", "3CEFHI"),
    ("M80", "1L", "3EHIJK"),
    # --- chave de baixo, lado direito ---
    ("M86", "1J", "2H"),
    ("M88", "2D", "2G"),
    ("M85", "1B", "3EFGIJ"),
    ("M87", "1K", "3DEIJL"),
]

# Round of 16 (M89–M96): cada jogo recebe os vencedores de dois jogos do R32.
R16 = [
    ("M89", "W74", "W77"),
    ("M90", "W73", "W75"),
    ("M93", "W83", "W84"),
    ("M94", "W81", "W82"),
    ("M91", "W76", "W78"),
    ("M92", "W79", "W80"),
    ("M95", "W86", "W88"),
    ("M96", "W85", "W87"),
]

# Quartas (M97–M100)
QUARTAS = [
    ("M97", "W89", "W90"),
    ("M98", "W93", "W94"),
    ("M99", "W91", "W92"),
    ("M100", "W95", "W96"),
]

# Semis (M101–M102)
SEMIS = [
    ("M101", "W97", "W98"),
    ("M102", "W99", "W100"),
]

# Final (M104) e disputa de 3º (M103)
FINAL = ("M104", "W101", "W102")
TERCEIRO = ("M103", "L101", "L102")   # perdedores das semis

# ordem das rodadas para iterar
RODADAS = [
    ("Round of 32", R32),
    ("Round of 16", R16),
    ("Quartas de final", QUARTAS),
    ("Semifinais", SEMIS),
]

# ---- layout em ÁRVORE (bracket): metade esquerda e metade direita ----
# Para cada lado, as rodadas vão da PONTA (R32) para o CENTRO (Semi). A ordem
# de cima p/ baixo dos códigos espelha o bracket oficial (imagem do usuário).
# A coluna do centro é a Final.
BRACKET_ESQUERDA = [
    ("Round of 32", ["M74", "M77", "M73", "M75", "M83", "M84", "M81", "M82"]),
    ("Round of 16", ["M89", "M90", "M93", "M94"]),
    ("Quartas",     ["M97", "M98"]),
    ("Semifinal",   ["M101"]),
]
BRACKET_DIREITA = [
    ("Round of 32", ["M76", "M78", "M79", "M80", "M86", "M88", "M85", "M87"]),
    ("Round of 16", ["M91", "M92", "M95", "M96"]),
    ("Quartas",     ["M99", "M100"]),
    ("Semifinal",   ["M102"]),
]

# mapa código -> (slot_casa, slot_fora) para lookup rápido no layout em árvore
JOGOS = {}
for _rod, _lista in RODADAS:
    for _cod, _ca, _fo in _lista:
        JOGOS[_cod] = (_ca, _fo)
JOGOS[FINAL[0]] = (FINAL[1], FINAL[2])
JOGOS[TERCEIRO[0]] = (TERCEIRO[1], TERCEIRO[2])
