"""
1_Fundos_CVM.py — página de consulta dos fundos (CVM CDA).

3 abas:
  1. Por ação    — fundos que detêm um ticker (ordenado por valor)
  2. Ranking     — top ações por nº de fundos ou por valor agregado
  3. Evolução    — matriz ticker × mês (valor de mercado agregado)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from lib import fundos

st.set_page_config(page_title="Fundos CVM", page_icon="🏦", layout="wide")
st.title("🏦 Fundos CVM")

# --- período disponível ---
periodos = fundos.periodos_disponiveis()
if not periodos:
    st.error("Sem dados. Rode `python site/atualizar_dados.py` (e antes, a carga da CVM).")
    st.stop()

labels = {p: fundos.periodo_humano(p) for p in periodos}


def fmt_valor(v):
    """Formata R$ em mi/bi para exibição."""
    if v is None or pd.isna(v):
        return "-"
    if abs(v) >= 1e9:
        return f"R$ {v/1e9:,.2f} bi"
    if abs(v) >= 1e6:
        return f"R$ {v/1e6:,.2f} mi"
    return f"R$ {v:,.0f}"


tab1, tab2, tab3 = st.tabs(["🔎 Por ação", "🏆 Ranking", "📈 Evolução mês a mês"])

# ===================== ABA 1: POR AÇÃO =====================
with tab1:
    st.subheader("Fundos que detêm uma ação")
    c1, c2 = st.columns([2, 1])
    with c1:
        tickers = fundos.tickers_disponiveis()
        ticker = st.selectbox("Ticker", tickers,
                              index=tickers.index("PETR4") if "PETR4" in tickers else 0)
    with c2:
        periodo = st.selectbox("Período", periodos, index=len(periodos) - 1,
                               format_func=lambda p: labels[p], key="per_acao")

    df = fundos.fundos_com_ticker(ticker, periodo)
    if df.empty:
        st.warning(f"Nenhum fundo com {ticker} em {labels[periodo]}.")
    else:
        total = df["Valor mercado (R$)"].sum()
        qtd = df["Quantidade"].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Fundos detentores", f"{len(df)}")
        m2.metric("Valor agregado", fmt_valor(total))
        m3.metric("Quantidade total", f"{qtd:,.0f} ações")

        mostrar = df.copy()
        mostrar["% do PL"] = (mostrar["% do PL"] * 100).round(2)
        st.dataframe(
            mostrar, use_container_width=True, hide_index=True,
            column_config={
                "Valor mercado (R$)": st.column_config.NumberColumn(format="R$ %,.0f"),
                "PL do fundo (R$)": st.column_config.NumberColumn(format="R$ %,.0f"),
                "Quantidade": st.column_config.NumberColumn(format="%,.0f"),
                "% do PL": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )
        st.download_button("⬇️ Baixar CSV", mostrar.to_csv(index=False).encode("utf-8"),
                           f"fundos_{ticker}_{periodo}.csv", "text/csv")

# ===================== ABA 2: RANKING =====================
with tab2:
    st.subheader("Ações mais detidas por fundos")
    c1, c2, c3 = st.columns(3)
    with c1:
        periodo_r = st.selectbox("Período", periodos, index=len(periodos) - 1,
                                 format_func=lambda p: labels[p], key="per_rank")
    with c2:
        por = st.radio("Ordenar por", ["fundos", "valor"],
                       format_func=lambda x: "Nº de fundos" if x == "fundos" else "Valor agregado")
    with c3:
        limite = st.slider("Quantas ações", 5, 100, 30, step=5)

    rk = fundos.ranking_acoes(periodo_r, por=por, limite=limite)
    rk_show = rk.copy()
    # coluna-resumo legível (R$ 20,61 bi) ao lado do número completo
    rk_show.insert(rk_show.columns.get_loc("Valor agregado (R$)") + 1,
                   "Valor (resumo)", rk_show["Valor agregado (R$)"].map(fmt_valor))
    st.dataframe(
        rk_show, use_container_width=True, hide_index=True,
        column_config={
            "Valor agregado (R$)": st.column_config.NumberColumn(format="R$ %,.0f"),
            "Nº fundos": st.column_config.NumberColumn(format="%,.0f"),
        },
    )
    st.bar_chart(rk.set_index("Ticker")[
        "Nº fundos" if por == "fundos" else "Valor agregado (R$)"])

# ===================== ABA 3: EVOLUÇÃO =====================
with tab3:
    st.subheader("Evolução do valor de mercado por ação (mês a mês)")
    st.caption("Cada célula = soma do valor de mercado dos fundos selecionados "
               "naquele ticker, naquele mês. **Valores em R$ milhões.**")

    modo = st.radio("Quais fundos somar?",
                    ["Todos os fundos", "Escolher fundos"],
                    horizontal=True)

    if modo == "Todos os fundos":
        top = st.slider("Mostrar quantas ações (maiores no último mês)",
                        10, 200, 50, step=10)
        m = fundos.matriz_ticker_mes(top=top)
        legenda_fundos = "todos os fundos"
    else:
        # busca por nome -> seleção múltipla
        termo = st.text_input("Buscar fundo por nome (ex.: REAL INVESTOR, GERAÇÃO...)",
                              placeholder="digite parte do nome do fundo")
        cat = fundos.buscar_fundos(termo)
        if cat.empty:
            st.info("Digite um nome para listar os fundos. Nenhum encontrado ainda."
                    if termo else "Digite parte do nome de um fundo acima.")
            m = None
            legenda_fundos = ""
        else:
            opcoes = cat["rotulo"].tolist()
            mapa = dict(zip(cat["rotulo"], cat["cnpj"]))
            escolhidos = st.multiselect(
                f"Selecione um ou mais fundos ({len(opcoes)} encontrados)",
                opcoes)
            if not escolhidos:
                st.info("Selecione pelo menos um fundo na lista acima.")
                m = None
            else:
                cnpjs = [mapa[r] for r in escolhidos]
                m = fundos.matriz_ticker_mes_por_fundos(cnpjs)
            legenda_fundos = f"{len(escolhidos)} fundo(s) selecionado(s)" if escolhidos else ""

    if m is None:
        pass  # nada selecionado ainda
    elif m.empty:
        st.warning("Sem posições em ações para os fundos selecionados.")
    else:
        st.caption(f"Somando: **{legenda_fundos}** · {len(m)} ações")
        m_mi = m / 1e6  # exibe em milhões para legibilidade
        st.dataframe(
            m_mi.style.format("{:,.0f}").background_gradient(cmap="YlOrRd", axis=None),
            use_container_width=True,
        )
        st.download_button("⬇️ Baixar matriz (CSV)",
                           m.to_csv().encode("utf-8"),
                           "matriz_ticker_mes.csv", "text/csv")

        st.markdown("**Evolução das maiores posições** (top 8)")
        st.line_chart(m.head(8).T)
