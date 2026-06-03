"""
2_Acoes.py — fundamentos das ações (banco financeiro).

PROTÓTIPO para discussão. 4 dashboards de exemplo:
  1. Ficha da ação    — indicadores-chave + evolução de receita/lucro
  2. Comparar ações   — tabela de indicadores lado a lado
  3. Triagem (screen) — filtra ações por faixas de indicadores
  4. Dividendos       — histórico de proventos de uma ação
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import acoes

st.set_page_config(page_title="Ações — Fundamentos", page_icon="📈", layout="wide")
st.title("📈 Ações — Fundamentos")
st.caption("⚠️ Protótipo para discussão — dados do banco financeiro (BR).")

lista = acoes.tickers()
if not lista:
    st.error("Sem dados. Rode `python site/atualizar_dados.py`.")
    st.stop()


def fmt_valor(v):
    if v is None or pd.isna(v):
        return "-"
    if abs(v) >= 1e9:
        return f"R$ {v/1e9:,.2f} bi"
    if abs(v) >= 1e6:
        return f"R$ {v/1e6:,.2f} mi"
    return f"R$ {v:,.2f}"


def fmt_pct(v):
    return "-" if v is None or pd.isna(v) else f"{v*100:.1f}%"


def fmt_mult(v):
    return "-" if v is None or pd.isna(v) else f"{v:.1f}x"


tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 Ficha da ação", "⚖️ Comparar", "🔎 Triagem", "💰 Dividendos"])

# ===================== ABA 1: FICHA =====================
with tab1:
    c1, c2 = st.columns([2, 1])
    with c1:
        tk = st.selectbox("Ação", lista,
                          index=lista.index("PETR4") if "PETR4" in lista else 0)
    with c2:
        ano = st.selectbox("Ano de referência", acoes.ANOS, index=len(acoes.ANOS) - 1)

    info = acoes.info_empresa(tk)
    if info:
        st.markdown(f"**{info[0] or tk}**  ·  setor: {info[1] or 'N/A'}")

    ind = acoes.indicadores_ano(tk, ano)
    if not ind:
        st.warning(f"Sem dados de {tk} em {ano}.")
    else:
        # cartões de indicadores
        linhas = [
            ("Preço", fmt_valor(ind["Preço"])),
            ("Market Cap", fmt_valor(ind["Market Cap"])),
            ("Receita líq.", fmt_valor(ind["Receita líquida"])),
            ("Lucro líq.", fmt_valor(ind["Lucro líquido"])),
            ("Margem líq.", fmt_pct(ind["Margem líquida"])),
            ("ROE", fmt_pct(ind["ROE"])),
            ("P/L", fmt_mult(ind["P/L"])),
            ("P/VP", fmt_mult(ind["P/VP"])),
        ]
        cols = st.columns(4)
        for i, (rotulo, valor) in enumerate(linhas):
            cols[i % 4].metric(rotulo, valor)

        st.divider()
        st.markdown("**Evolução — Receita, Lucro e EBITDA (R$)**")
        serie = acoes.serie_historica(tk)
        if not serie.empty:
            serie = serie.rename(columns={
                "receita_liquida": "Receita líquida",
                "lucro_liquido": "Lucro líquido",
                "ebitda": "EBITDA"})
            st.bar_chart(serie)

# ===================== ABA 2: COMPARAR =====================
with tab2:
    st.markdown("Selecione ações para comparar lado a lado.")
    escolhidas = st.multiselect("Ações", lista,
                                default=[t for t in ["PETR4", "VALE3", "ITUB4"] if t in lista])
    ano2 = st.selectbox("Ano", acoes.ANOS, index=len(acoes.ANOS) - 1, key="ano_comp")

    if escolhidas:
        linhas = []
        for tk in escolhidas:
            ind = acoes.indicadores_ano(tk, ano2)
            if ind:
                linhas.append({
                    "Ticker": tk,
                    "Preço": ind["Preço"],
                    "Market Cap": ind["Market Cap"],
                    "Receita líq.": ind["Receita líquida"],
                    "Lucro líq.": ind["Lucro líquido"],
                    "Margem líq.": ind["Margem líquida"],
                    "ROE": ind["ROE"],
                    "P/L": ind["P/L"],
                    "P/VP": ind["P/VP"],
                })
        if linhas:
            df = pd.DataFrame(linhas).set_index("Ticker")
            st.dataframe(
                df, use_container_width=True,
                column_config={
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Market Cap": st.column_config.NumberColumn(format="R$ %,.0f"),
                    "Receita líq.": st.column_config.NumberColumn(format="R$ %,.0f"),
                    "Lucro líq.": st.column_config.NumberColumn(format="R$ %,.0f"),
                    "Margem líq.": st.column_config.NumberColumn(format="%.1f%%"),
                    "ROE": st.column_config.NumberColumn(format="%.1f%%"),
                    "P/L": st.column_config.NumberColumn(format="%.1fx"),
                    "P/VP": st.column_config.NumberColumn(format="%.1fx"),
                },
            )

# ===================== ABA 3: TRIAGEM =====================
with tab3:
    st.markdown("Filtrar ações por faixas de indicadores (ano de referência: 2025).")
    c1, c2, c3 = st.columns(3)
    with c1:
        pl_max = st.number_input("P/L máximo", value=15.0, step=1.0)
    with c2:
        roe_min = st.number_input("ROE mínimo (%)", value=15.0, step=1.0)
    with c3:
        margem_min = st.number_input("Margem líq. mínima (%)", value=10.0, step=1.0)

    if st.button("Rodar triagem"):
        with st.spinner("Calculando..."):
            res = []
            for tk in lista:
                ind = acoes.indicadores_ano(tk, 2025)
                if not ind:
                    continue
                pl, roe, ml = ind["P/L"], ind["ROE"], ind["Margem líquida"]
                if pl is None or roe is None or ml is None:
                    continue
                if 0 < pl <= pl_max and roe >= roe_min / 100 and ml >= margem_min / 100:
                    res.append({"Ticker": tk, "P/L": pl, "ROE": roe,
                                "Margem líq.": ml, "Lucro líq.": ind["Lucro líquido"]})
            if res:
                df = pd.DataFrame(res).sort_values("ROE", ascending=False)
                st.success(f"{len(df)} ações passaram no filtro.")
                st.dataframe(
                    df, use_container_width=True, hide_index=True,
                    column_config={
                        "P/L": st.column_config.NumberColumn(format="%.1fx"),
                        "ROE": st.column_config.NumberColumn(format="%.1f%%"),
                        "Margem líq.": st.column_config.NumberColumn(format="%.1f%%"),
                        "Lucro líq.": st.column_config.NumberColumn(format="R$ %,.0f"),
                    },
                )
            else:
                st.info("Nenhuma ação passou nos filtros.")

# ===================== ABA 4: DIVIDENDOS =====================
with tab4:
    tk = st.selectbox("Ação", lista, key="tk_div",
                      index=lista.index("ITUB4") if "ITUB4" in lista else 0)
    div = acoes.dividendos_anuais(tk)
    if div.empty:
        st.info(f"Sem histórico de dividendos para {tk}.")
    else:
        div = div.set_index("ano").rename(
            columns={"dividendo_por_acao": "Dividendo por ação (R$)"})
        st.bar_chart(div)
        st.dataframe(div, use_container_width=True,
                     column_config={"Dividendo por ação (R$)":
                                    st.column_config.NumberColumn(format="R$ %.4f")})
