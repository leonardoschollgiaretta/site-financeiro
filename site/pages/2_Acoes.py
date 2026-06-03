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

        # --- Demonstrações financeiras (formato relatório, anos em colunas) ---
        st.divider()
        st.markdown("### 📑 Demonstrações financeiras  ·  valores em **R$ mil**")

        def mostra_demonstracao(titulo, linhas):
            dem = acoes.demonstracao(tk, linhas, em_milhares=True)
            if dem.empty:
                st.info(f"Sem dados para {titulo}.")
                return
            # destaca linhas de totais (TOTAL / EBITDA / Lucro Líquido)
            def realca(s):
                negrito = any(k in s.name for k in
                              ("TOTAL", "EBITDA", "Lucro Líquido", "FLUXO", "Free Cash"))
                return ["font-weight:bold" if negrito else "" for _ in s]
            sty = (dem.style
                   .format(lambda v: "-" if pd.isna(v) else f"{v:,.0f}")
                   .apply(realca, axis=1))
            st.dataframe(sty, use_container_width=True)

        d1, d2, d3 = st.tabs(["DRE — Resultado", "Balanço", "DFC — Fluxo de Caixa"])
        with d1:
            mostra_demonstracao("DRE", acoes.DRE_LINHAS)
        with d2:
            mostra_demonstracao("Balanço", acoes.BALANCO_LINHAS)
        with d3:
            mostra_demonstracao("DFC", acoes.DFC_LINHAS)

        # download das 3 juntas
        partes = []
        for nome, linhas in [("DRE", acoes.DRE_LINHAS),
                             ("BALANCO", acoes.BALANCO_LINHAS),
                             ("DFC", acoes.DFC_LINHAS)]:
            d = acoes.demonstracao(tk, linhas)
            if not d.empty:
                d.insert(0, "Demonstração", nome)
                partes.append(d)
        if partes:
            full = pd.concat(partes)
            st.download_button("⬇️ Baixar demonstrações (CSV)",
                               full.to_csv().encode("utf-8-sig"),
                               f"demonstracoes_{tk}.csv", "text/csv")

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
    st.markdown("Filtre o universo de ações por critérios. **Marque** os filtros "
                "que quer aplicar — os desmarcados são ignorados.")

    @st.cache_data(show_spinner="Calculando indicadores de todas as ações...")
    def carregar_tabela(ano):
        return acoes.tabela_indicadores(ano)

    ano3 = st.selectbox("Ano de referência", acoes.ANOS,
                        index=len(acoes.ANOS) - 1, key="ano_triagem")
    base = carregar_tabela(ano3)
    if base.empty:
        st.warning("Sem dados.")
        st.stop()

    # cada filtro: (rótulo, coluna, operador, valor_default, é_percentual, é_multiplo_de_mi)
    st.markdown("**Critérios**")
    col_a, col_b = st.columns(2)
    filtros = []  # (coluna, operador, valor, label)

    with col_a:
        if st.checkbox("P/L máximo", value=True):
            v = st.number_input("P/L ≤", value=15.0, step=1.0, key="f_pl")
            filtros.append(("P/L", "<=", v, "P/L"))
        if st.checkbox("P/VP máximo"):
            v = st.number_input("P/VP ≤", value=3.0, step=0.5, key="f_pvp")
            filtros.append(("P/VP", "<=", v, "P/VP"))
        if st.checkbox("Dív.líq./EBITDA máximo"):
            v = st.number_input("Dív.líq./EBITDA ≤", value=3.0, step=0.5, key="f_dl")
            filtros.append(("Dív. líq. / EBITDA", "<=", v, "Dív.líq./EBITDA"))
    with col_b:
        if st.checkbox("ROE mínimo (%)", value=True):
            v = st.number_input("ROE ≥ (%)", value=15.0, step=1.0, key="f_roe")
            filtros.append(("ROE", ">=", v / 100, "ROE"))
        if st.checkbox("Margem líq. mínima (%)", value=True):
            v = st.number_input("Margem líq. ≥ (%)", value=10.0, step=1.0, key="f_ml")
            filtros.append(("Margem líquida", ">=", v / 100, "Margem líq."))
        if st.checkbox("Market Cap mínimo (R$ bi)"):
            v = st.number_input("Market Cap ≥ (R$ bi)", value=1.0, step=0.5, key="f_mc")
            filtros.append(("Market Cap", ">=", v * 1e9, "Market Cap mín"))

    # aplica filtros
    df = base.copy()
    for coluna, op, valor, _ in filtros:
        if coluna not in df.columns:
            continue
        serie = pd.to_numeric(df[coluna], errors="coerce")
        if op == "<=":
            # P/L e P/VP: ignora negativos (prejuízo/PL negativo) e nulos
            df = df[(serie.notna()) & (serie > 0) & (serie <= valor)]
        else:
            df = df[(serie.notna()) & (serie >= valor)]

    ativos = ", ".join(l for *_, l in filtros) or "nenhum"
    st.caption(f"Filtros ativos: {ativos}")

    if df.empty:
        st.info("Nenhuma ação passou nos filtros. Tente afrouxar os critérios.")
    else:
        st.success(f"**{len(df)}** ações passaram.")
        cols_show = ["Ticker", "Preço", "Market Cap", "Receita líquida",
                     "Lucro líquido", "Margem líquida", "ROE", "P/L", "P/VP",
                     "Dív. líq. / EBITDA"]
        cols_show = [c for c in cols_show if c in df.columns]
        out = df[cols_show].sort_values("ROE", ascending=False)
        st.dataframe(
            out, use_container_width=True, hide_index=True,
            column_config={
                "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                "Market Cap": st.column_config.NumberColumn(format="R$ %,.0f"),
                "Receita líquida": st.column_config.NumberColumn(format="R$ %,.0f"),
                "Lucro líquido": st.column_config.NumberColumn(format="R$ %,.0f"),
                "Margem líquida": st.column_config.NumberColumn(format="%.1f%%"),
                "ROE": st.column_config.NumberColumn(format="%.1f%%"),
                "P/L": st.column_config.NumberColumn(format="%.1fx"),
                "P/VP": st.column_config.NumberColumn(format="%.1fx"),
                "Dív. líq. / EBITDA": st.column_config.NumberColumn(format="%.1fx"),
            },
        )
        st.download_button("⬇️ Baixar resultado (CSV)",
                           out.to_csv(index=False).encode("utf-8"),
                           f"triagem_acoes_{ano3}.csv", "text/csv")

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
