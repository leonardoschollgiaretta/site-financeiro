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
import plotly.express as px
import streamlit as st

from lib import acoes, fundos

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

# estilo de cabeçalho escuro reutilizável
ESTILO_HDR = [
    {"selector": "th.col_heading",
     "props": [("background-color", "#0E2841"), ("color", "white"),
               ("font-weight", "bold"), ("text-align", "center")]},
    {"selector": "th.row_heading",
     "props": [("background-color", "#0E2841"), ("color", "white"),
               ("font-weight", "bold")]},
    {"selector": "th.blank", "props": [("background-color", "#0E2841")]},
]


def pontua(v):
    return "-" if pd.isna(v) else f"{v:,.0f}".replace(",", ".")


# ===================== ABA 1: POR AÇÃO =====================
with tab1:
    # --- FILTRO no topo, vale para as duas tabelas ---
    tickers = fundos.tickers_disponiveis()
    ticker = st.selectbox(
        "Filtrar por ação (vazio = todas)", ["(todas)"] + tickers, index=0,
        key="filtro_acao")
    acao_sel = None if ticker == "(todas)" else ticker

    # --- TABELA 1: panorama mensal (geral OU da ação escolhida) ---
    if acao_sel is None:
        st.subheader("Panorama — declarações de carteira por mês (todas as ações)")
        st.caption("Quantos fundos declararam posição em ações a cada mês. "
                   "Meses recentes costumam ter menos declarações (defasagem da CVM). "
                   "Escolha uma ação acima para ver a série dela.")
        cob = fundos.resumo_cobertura_por_mes()
        sty = (cob.style.format({
                    "Total de fundos": pontua, "Com posição em ações": pontua,
                    "Sem posição em ações": pontua, "Valor aplicado (R$)": fmt_valor})
               .set_table_styles(ESTILO_HDR)
               .background_gradient(cmap="Blues", subset=["Com posição em ações"])
               .set_properties(**{"text-align": "center"}))
        st.dataframe(sty, use_container_width=True)
        st.info("💡 Selecione uma ação no filtro acima para destravar a série "
                "mensal dela e poder clicar num mês.")
    else:
        # --- cotação e market cap (banco financeiro) ---
        fin = acoes.cotacao_e_marketcap(acao_sel)
        if fin and fin["preco"]:
            from datetime import datetime
            mc1, mc2, mc3 = st.columns(3)
            preco_fmt = f"R$ {fin['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            mc1.metric(f"Último preço ({fin.get('ticker_preco') or acao_sel})",
                       preco_fmt)
            mc2.metric("Ações totais (ON+PN)",
                       pontua(fin["acoes_total"]) if fin["acoes_total"] else "-")
            mc3.metric("Market cap", fmt_valor(fin["market_cap"]))
            # data do preço + aviso se defasado
            dstr = fin.get("data_preco")
            legenda = f"Preço de fechamento em **{dstr}**" if dstr else "Data do preço indisponível"
            try:
                d = datetime.strptime(str(dstr)[:10], "%Y-%m-%d").date()
                dias = (datetime.now().date() - d).days
                if dias > 7:
                    legenda += f" ⚠️ defasado ({dias} dias atrás)"
            except (ValueError, TypeError):
                pass
            classes = []
            if fin.get("ticker_on"):
                classes.append(f"ON {fin['ticker_on']}")
            if fin.get("ticker_pn"):
                classes.append(f"PN {fin['ticker_pn']}")
            if classes:
                legenda += "  ·  classes: " + " + ".join(classes)
            st.caption(legenda)
        else:
            st.caption("ℹ️ Sem preço no banco financeiro para esta ação "
                       "(market cap indisponível).")
        st.divider()

        st.subheader(f"{acao_sel} — fundos e valor aplicado por mês")
        st.caption("Clique em um mês na tabela para ver os fundos detentores embaixo.")
        serie = fundos.resumo_acao_por_mes(acao_sel)
        if serie.empty:
            st.warning(f"Nenhum fundo com {acao_sel} em nenhum período.")
        else:
            # tudo em R$ milhões (numérico) para ordenar/filtrar corretamente
            visivel = serie.drop(columns=["_periodo"]).copy()
            visivel["Valor aplicado (R$ mi)"] = visivel["Valor aplicado (R$)"] / 1e6
            visivel = visivel.drop(columns=["Valor aplicado (R$)"])
            # tabela clicável (seleção de linha)
            evento = st.dataframe(
                visivel, use_container_width=True,
                on_select="rerun", selection_mode="single-row", key="sel_mes",
                column_config={
                    "Fundos com posição": st.column_config.NumberColumn(format="%d"),
                    "Valor aplicado (R$ mi)": st.column_config.NumberColumn(
                        format="%.0f", help="Valor de mercado total aplicado, em R$ milhões"),
                })

            # descobre qual mês foi clicado (senão, usa o último)
            linhas_sel = evento.selection.rows if evento and evento.selection else []
            if linhas_sel:
                periodo_alvo = serie.iloc[linhas_sel[0]]["_periodo"]
            else:
                periodo_alvo = serie.iloc[-1]["_periodo"]

            # --- TABELA 2: fundos detentores da ação no mês selecionado ---
            st.divider()
            st.subheader(f"Fundos com posição em {acao_sel} — {labels.get(periodo_alvo, periodo_alvo)}")
            if not linhas_sel:
                st.caption("(mostrando o último mês; clique numa linha acima para trocar)")

            df = fundos.fundos_com_ticker(acao_sel, periodo_alvo)
            if df.empty:
                st.warning("Nenhum fundo neste mês.")
            else:
                total = df["Valor mercado (R$)"].sum()
                qtd = df["Quantidade"].sum()
                m1, m2, m3 = st.columns(3)
                m1.metric("Fundos detentores", f"{len(df)}")
                m2.metric("Valor agregado", fmt_valor(total))
                m3.metric("Quantidade total", f"{pontua(qtd)} ações")

                # valores em R$ milhões (numérico) para ordenar pela coluna
                mostrar = pd.DataFrame({
                    "CNPJ": df["CNPJ"], "Fundo": df["Fundo"], "Tipo": df["Tipo"],
                    "Quantidade": df["Quantidade"],
                    "Valor mercado (R$ mi)": df["Valor mercado (R$)"] / 1e6,
                    "PL do fundo (R$ mi)": df["PL do fundo (R$)"] / 1e6,
                    "% do PL": df["% do PL"] * 100,
                })
                st.caption("👇 Clique em um fundo para ver a carteira dele mês a mês.")
                ev_fundo = st.dataframe(
                    mostrar, use_container_width=True, hide_index=True,
                    on_select="rerun", selection_mode="single-row", key="sel_fundo",
                    column_config={
                        "Quantidade": st.column_config.NumberColumn(format="%.0f"),
                        "Valor mercado (R$ mi)": st.column_config.NumberColumn(
                            format="%.1f", help="Valor de mercado, em R$ milhões"),
                        "PL do fundo (R$ mi)": st.column_config.NumberColumn(
                            format="%.1f", help="Patrimônio líquido do fundo, em R$ milhões"),
                        "% do PL": st.column_config.NumberColumn(format="%.2f%%"),
                    })
                st.download_button(
                    "⬇️ Baixar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                    f"fundos_{acao_sel}_{periodo_alvo}.csv", "text/csv")

                # --- ao clicar num fundo: carteira dele mês a mês (matriz) ---
                sel_f = ev_fundo.selection.rows if ev_fundo and ev_fundo.selection else []
                if sel_f:
                    fundo_row = df.iloc[sel_f[0]]
                    cnpj_f = fundo_row["CNPJ"]
                    nome_f = fundo_row["Fundo"]
                    st.divider()
                    st.subheader(f"🧾 Carteira de {nome_f[:60]}")
                    st.caption(f"CNPJ {cnpj_f} · valor de mercado por ação, mês a mês "
                               "(R$ milhões).")
                    mat = fundos.matriz_ticker_mes_por_fundos([cnpj_f])
                    if mat.empty:
                        st.info("Sem carteira de ações para este fundo.")
                    else:
                        # total aplicado pelo fundo em cada mês (valor por extenso)
                        totais_f = mat.sum(axis=0)
                        st.markdown("**Total aplicado em ações por mês**")
                        ct = st.columns(len(totais_f))
                        for i, col in enumerate(ct):
                            col.metric(totais_f.index[i], fmt_valor(totais_f.iloc[i]))

                        mat_mi = mat / 1e6
                        st.dataframe(
                            mat_mi.style.format(lambda v: pontua(v) if v else "-")
                                  .background_gradient(cmap="YlGn", axis=None),
                            use_container_width=True)

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

    # --- treemap: quanto maior a ação, maior o quadrado ---
    st.markdown("**Mapa de proporção** — cada quadrado é uma ação; o tamanho "
                "reflete a métrica escolhida abaixo.")
    metrica = st.radio(
        "Tamanho do quadrado por:",
        ["Valor aplicado", "Nº de fundos"],
        horizontal=True, key="treemap_metrica")
    por_valor = metrica == "Valor aplicado"
    col_val = "Valor agregado (R$)" if por_valor else "Nº fundos"
    # ordena pela própria métrica do treemap (coerência tamanho x posição)
    tm = rk.sort_values(col_val, ascending=False).copy()
    tm["rotulo_val"] = (tm[col_val].map(fmt_valor) if por_valor
                        else tm[col_val].map(lambda v: f"{int(v):,}".replace(",", ".") + " fundos"))
    fig = px.treemap(
        tm,
        path=[px.Constant("Total"), "Ticker"],
        values=col_val,
        color=col_val,
        color_continuous_scale="YlOrRd",
        custom_data=["rotulo_val"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[0]}",
        textposition="middle center",
        hovertemplate="<b>%{label}</b><br>%{customdata[0]}<extra></extra>",
    )
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=450,
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

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
        # caixa única: clique e digite para buscar (só fundos com ações)
        cat = fundos.buscar_fundos(apenas_com_acoes=True, limite=10000)
        opcoes = cat["rotulo"].tolist()
        mapa = dict(zip(cat["rotulo"], cat["cnpj"]))
        escolhidos = st.multiselect(
            f"Fundo(s) — clique e digite para buscar ({len(opcoes)} fundos com ações)",
            opcoes,
            placeholder="ex.: GERAÇÃO, REAL INVESTOR, SPX...")
        if not escolhidos:
            st.info("Selecione um ou mais fundos acima.")
            m = None
            legenda_fundos = ""
        else:
            cnpjs = [mapa[r] for r in escolhidos]
            m = fundos.matriz_ticker_mes_por_fundos(cnpjs)
            legenda_fundos = f"{len(escolhidos)} fundo(s) selecionado(s)"

    if m is None:
        pass  # nada selecionado ainda
    elif m.empty:
        st.warning(
            "Os fundos selecionados não têm posição em **ações** neste banco.\n\n"
            "Dica: alguns fundos (ex.: classes 'FIF em cotas') investem em **cotas "
            "de outros fundos**, não em ações diretas — por isso não aparecem aqui. "
            "Procure a versão do fundo que é 'FUNDO DE INVESTIMENTO ... DE AÇÕES'."
        )
    else:
        st.caption(f"Somando: **{legenda_fundos}** · {len(m)} ações · valores em reais")

        def fmt_celula(v):
            if v is None or pd.isna(v) or v == 0:
                return "-"
            if abs(v) >= 1e9:
                return f"R$ {v/1e9:,.2f} bi"
            if abs(v) >= 1e6:
                return f"R$ {v/1e6:,.2f} mi"
            if abs(v) >= 1e3:
                return f"R$ {v/1e3:,.0f} mil"
            return f"R$ {v:,.0f}"

        # --- linha de TOTAL por mês (valor do fundo em ações), fixa no topo ---
        totais = m.sum(axis=0)  # soma todas as ações, por mês
        st.markdown("**Total em ações por mês** (soma de todas as posições)")
        cols = st.columns(len(totais))
        meses_list = list(totais.index)
        for i, col in enumerate(cols):
            mes = meses_list[i]
            atual = totais.iloc[i]
            # variação vs mês anterior
            delta = None
            if i > 0 and totais.iloc[i - 1]:
                var = (atual - totais.iloc[i - 1]) / totais.iloc[i - 1]
                delta = f"{var*100:+.1f}%"
            col.metric(mes, fmt_celula(atual), delta)

        st.dataframe(
            m.style.format(fmt_celula).background_gradient(cmap="YlGn", axis=None),
            use_container_width=True,
        )
        st.download_button("⬇️ Baixar matriz (CSV)",
                           m.to_csv().encode("utf-8"),
                           "matriz_ticker_mes.csv", "text/csv")

        st.markdown("**Evolução das maiores posições** (top 8)")
        st.line_chart(m.head(8).T)
