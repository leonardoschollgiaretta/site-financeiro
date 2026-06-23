"""
4_Simular_Copa.py — simulador do mata-mata da Copa do Mundo 2026.

Fluxo:
  1. Você define a ordem de cada grupo (1º–4º) e escolhe os 8 melhores terceiros.
  2. O bracket (Round of 32 → Final) se monta com base nisso.
  3. Você clica para escolher o vencedor de cada confronto; a escolha propaga
     até o campeão.

Dados dos 48 times: bolao_copa/bolao.db (12 grupos A–L). Estrutura do mata-mata:
lib/copa.py (chaveamento oficial FIFA 2026).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from lib import copa, ui

st.set_page_config(page_title="Simular Copa 2026", page_icon="🏆", layout="wide")
ui.aplicar_tema(False)
ui.cabecalho("Simular Copa 2026",
             "Defina a ordem dos grupos e simule o mata-mata até o campeão · "
             "formato 48 seleções")
ui.selo_atualizacao(copa.data_ultimo_resultado(), extra="último resultado de grupo")

GRUPOS = copa.grupos()
if not GRUPOS:
    st.error("Não encontrei os grupos em bolao_copa/bolao.db.")
    st.stop()

POSICOES = ["1", "2", "3", "4"]  # rótulos de colocação


# ---------------- 1) DEFINIR GRUPOS ----------------
st.markdown("### 1️⃣ Classificação dos grupos")
st.caption("A ordem já vem **calculada pelos resultados gravados** (pontos → saldo "
           "→ gols pró). Grupos com jogos faltando podem precisar de ajuste manual. "
           "Os 1º e 2º se classificam; os 3º disputam as vagas de melhores terceiros.")

# classificação calculada dos placares (ordem por critérios FIFA)
CLASSIF = copa.classificacao_grupos()
# ordem default de cada grupo = times na ordem da classificação
ORDEM_DEFAULT = {g: [d["time"] for d in CLASSIF.get(g, [])] or sorted(GRUPOS[g])
                 for g in GRUPOS}

with st.expander("Conferir / ajustar ordem dos 12 grupos", expanded=False):
    cols = st.columns(3)
    coloc = {}   # coloc[(grupo, pos)] = time
    for i, g in enumerate(GRUPOS):
        ordem_g = ORDEM_DEFAULT[g]
        with cols[i % 3]:
            st.markdown(f"**Grupo {g}**")
            for j, pos in enumerate(POSICOES):
                key = f"grp_{g}_{pos}"
                ja = [coloc.get((g, p)) for p in POSICOES if (g, p) in coloc]
                opcoes = [t for t in ordem_g if t not in ja]
                # default: o próximo da classificação ainda não escolhido
                padrao = ordem_g[j] if j < len(ordem_g) else None
                idx = opcoes.index(padrao) if padrao in opcoes else 0
                escolha = st.selectbox(f"{pos}º", opcoes,
                                       index=idx if opcoes else None, key=key)
                coloc[(g, pos)] = escolha
            st.write("")

# tabelas de classificação (visualização)
with st.expander("📊 Tabelas de classificação (pelos resultados gravados)",
                 expanded=True):
    import pandas as pd
    gcols = st.columns(3)
    for i, g in enumerate(GRUPOS):
        linhas = CLASSIF.get(g, [])
        with gcols[i % 3]:
            st.markdown(f"**Grupo {g}**")
            if not linhas:
                st.caption("Sem jogos gravados.")
                continue
            df = pd.DataFrame(linhas)[["time", "J", "V", "E", "D",
                                       "GP", "GC", "SG", "Pts"]]
            df.columns = ["Time", "J", "V", "E", "D", "GP", "GC", "SG", "Pts"]
            df.insert(0, "", range(1, len(df) + 1))   # posição
            st.dataframe(df, use_container_width=True, hide_index=True,
                         height=35 + 35 * len(df))

# primeiros, segundos e terceiros por grupo
primeiro = {g: coloc[(g, "1")] for g in GRUPOS}
segundo = {g: coloc[(g, "2")] for g in GRUPOS}
terceiro = {g: coloc[(g, "3")] for g in GRUPOS}


# ---------------- 2) MELHORES TERCEIROS ----------------
st.markdown("### 2️⃣ Melhores terceiros (8 vagas)")
st.caption("Escolha quais **8 grupos** classificaram o 3º colocado. Depois atribua "
           "cada um a uma vaga do chaveamento (os slots '3XXXX' do bracket).")

# vagas de terceiro no R32 (slot -> grupos elegíveis)
vagas_terceiro = []
for cod, casa, fora in copa.R32:
    for slot in (casa, fora):
        if slot.startswith("3"):
            vagas_terceiro.append((cod, slot))

todos_grupos = list(GRUPOS.keys())
col3a, col3b = st.columns([1, 2])
with col3a:
    grupos_3 = st.multiselect(
        "Grupos que classificaram o 3º colocado (escolha 8)",
        todos_grupos, default=todos_grupos[:8], max_selections=8)

terceiros_disp = {g: terceiro[g] for g in grupos_3}

st.caption(f"Vagas de terceiro no bracket: {len(vagas_terceiro)}. "
           "Atribua um grupo a cada vaga (a vaga só aceita grupos elegíveis).")

atribuicao_3 = {}   # slot -> grupo escolhido
vcols = st.columns(4)
for i, (cod, slot) in enumerate(vagas_terceiro):
    elegiveis = [g for g in grupos_3 if g in slot[1:]]  # ex.: '3ABCDF' -> A,B,C,D,F
    with vcols[i % 4]:
        if not elegiveis:
            st.selectbox(f"{slot} ({cod})", ["—"], key=f"v3_{cod}", disabled=True)
            atribuicao_3[slot] = None
        else:
            g = st.selectbox(f"{slot} ({cod})", elegiveis, key=f"v3_{cod}")
            atribuicao_3[slot] = g


# ---------------- resolver slots -> seleções ----------------
def resolve_slot(slot, vencedores, perdedores):
    """Traduz um slot ('1A', '2B', '3ABCDF', 'W74', 'L101') para a seleção atual."""
    if slot.startswith("W"):           # vencedor de um jogo
        return vencedores.get("M" + slot[1:])
    if slot.startswith("L"):           # perdedor (disputa de 3º)
        return perdedores.get("M" + slot[1:])
    if slot.startswith("1"):
        return primeiro.get(slot[1:])
    if slot.startswith("2"):
        return segundo.get(slot[1:])
    if slot.startswith("3"):
        g = atribuicao_3.get(slot)
        return terceiro.get(g) if g else None
    return None


# ---------------- 3) BRACKET INTERATIVO ----------------
st.divider()
st.markdown("### 3️⃣ Bracket — escolha os vencedores")

# estado: vencedor escolhido por jogo
if "copa_venc" not in st.session_state:
    st.session_state["copa_venc"] = {}
venc = st.session_state["copa_venc"]
perd = {}   # perdedores (para a disputa de 3º)


# --- 1ª passada: resolve TODOS os jogos em ordem lógica (R32→Final), para que
#     venc/perd já estejam corretos quando formos desenhar em qualquer ordem. ---
for nome, jogos in copa.RODADAS:
    for cod, sa, sb in jogos:
        a = resolve_slot(sa, venc, perd)
        b = resolve_slot(sb, venc, perd)
        if a and b and venc.get(cod) in (a, b):
            perd[cod] = b if venc[cod] == a else a
        elif venc.get(cod) not in (a, b):
            venc.pop(cod, None)        # escolha anterior ficou inválida
# final e 3º
for cod, sa, sb in [copa.FINAL, copa.TERCEIRO]:
    a = resolve_slot(sa, venc, perd)
    b = resolve_slot(sb, venc, perd)
    if a and b and venc.get(cod) in (a, b):
        perd[cod] = b if venc[cod] == a else a
    elif venc.get(cod) not in (a, b):
        venc.pop(cod, None)


def jogo_card(cod, compacto=True):
    """Desenha UM confronto (radio p/ escolher vencedor). Lê venc/perd já resolvidos."""
    sa, sb = copa.JOGOS[cod]
    a = resolve_slot(sa, venc, perd)
    b = resolve_slot(sb, venc, perd)
    rot_a = a or f"({sa})"
    rot_b = b or f"({sb})"
    st.markdown(f"<span style='color:#9aa4b2;font-size:.72rem'>{cod}</span>",
                unsafe_allow_html=True)
    opcoes = [x for x in (a, b) if x]
    if not opcoes:
        st.caption(f"{rot_a}\n\n{rot_b}")
        return
    atual = venc.get(cod)
    idx = opcoes.index(atual) if atual in opcoes else None
    escolha = st.radio(cod, opcoes, index=idx, key=f"j_{cod}",
                       label_visibility="collapsed")
    venc[cod] = escolha if escolha else venc.get(cod)
    if a and b and venc.get(cod):
        perd[cod] = b if venc[cod] == a else a


# --- desenho em ÁRVORE: esquerda (4 col) → Final (centro) → direita (4 col) ---
st.markdown("#### 🗺️ Mata-mata (chaveamento)")
st.caption("Round of 32 nas pontas, convergindo para a Final no centro. "
           "Clique no time que vence cada confronto.")

n_esq = len(copa.BRACKET_ESQUERDA)        # 4 rodadas por lado
colunas = st.columns(n_esq + 1 + n_esq)   # 4 + final + 4 = 9 colunas

# lado esquerdo: ponta (R32) -> centro
for ci, (nome_rodada, codigos) in enumerate(copa.BRACKET_ESQUERDA):
    with colunas[ci]:
        st.markdown(f"<div style='font-size:.78rem;color:#5b6677;font-weight:600;"
                    f"text-align:center'>{nome_rodada}</div>", unsafe_allow_html=True)
        for cod in codigos:
            with st.container(border=True):
                jogo_card(cod)

# centro: Final + disputa de 3º + pódio
with colunas[n_esq]:
    st.markdown("<div style='font-size:.85rem;color:#0f9d6e;font-weight:700;"
                "text-align:center'>🏆 FINAL</div>", unsafe_allow_html=True)
    with st.container(border=True):
        jogo_card(copa.FINAL[0])
    campeao = venc.get(copa.FINAL[0])
    if campeao:
        st.success(f"🏆 **{campeao}**")
    st.markdown("<div style='font-size:.78rem;color:#5b6677;text-align:center;"
                "margin-top:8px'>3º lugar</div>", unsafe_allow_html=True)
    with st.container(border=True):
        jogo_card(copa.TERCEIRO[0])

# lado direito: centro -> ponta (R32). Rodadas na ordem inversa das colunas.
for ci, (nome_rodada, codigos) in enumerate(reversed(copa.BRACKET_DIREITA)):
    with colunas[n_esq + 1 + ci]:
        st.markdown(f"<div style='font-size:.78rem;color:#5b6677;font-weight:600;"
                    f"text-align:center'>{nome_rodada}</div>", unsafe_allow_html=True)
        for cod in codigos:
            with st.container(border=True):
                jogo_card(cod)

cb_limpar = st.columns([3, 1])[1]
with cb_limpar:
    if st.button("🔄 Limpar escolhas"):
        st.session_state["copa_venc"] = {}
        st.rerun()

# --- pódio ---
campeao = venc.get(copa.FINAL[0])
if campeao:
    a_final = resolve_slot(copa.FINAL[1], venc, perd)
    b_final = resolve_slot(copa.FINAL[2], venc, perd)
    vice = b_final if campeao == a_final else a_final
    st.divider()
    st.markdown("### 🏅 Pódio")
    p = st.columns(3)
    p[0].metric("🥇 Campeão", campeao)
    p[1].metric("🥈 Vice", vice or "—")
    p[2].metric("🥉 Terceiro", venc.get(copa.TERCEIRO[0]) or "—")
