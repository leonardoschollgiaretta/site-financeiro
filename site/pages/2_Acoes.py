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
import plotly.graph_objects as go
import streamlit as st

from lib import acoes, carteiras, ui

st.set_page_config(page_title="Ações — Fundamentos", page_icon="📈", layout="wide")

# Tema claro (padrão profissional). O dark fica desativado por ora: o
# streamlit-aggrid 1.2.x não permite estilizar a grade no escuro de forma
# confiável, e o downgrade quebra o ambiente (altair). Reativar quando resolvido.
ESCURO = False
ui.aplicar_tema(ESCURO)

ui.cabecalho("Ações — Fundamentos",
             "Indicadores, demonstrações trimestrais e composição de fundos · dados BR")
# robusto: se o módulo em cache não tiver data_precos, não quebra a página
_data_precos = getattr(acoes, "data_precos", lambda: None)
ui.selo_atualizacao(_data_precos(), extra="cotações (fechamento)")

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


tab0, tab_dem, tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🔎 Visão geral", "📑 Demonstrações", "📋 Ficha da ação", "⚖️ Comparar",
     "🔎 Triagem", "💰 Dividendos", "🧺 Simulador de carteira"])

# ===================== ABA 0: VISÃO GERAL (estilo Investidor10) =====================
with tab0:
    from lib import fundos as _fundos

    cabec = st.columns([2, 1, 1])
    with cabec[0]:
        tk0 = st.selectbox("Ação", lista, key="tk_overview",
                           index=lista.index("PETR4") if "PETR4" in lista else 0)

    info0 = acoes.info_empresa(tk0)
    nome0 = (info0[0] if info0 else None) or tk0
    setor0 = info0[1] if info0 else None
    cm = acoes.cotacao_e_marketcap(tk0)
    dy = acoes.dividend_yield(tk0)
    ind0 = acoes.indicadores_ano(tk0, acoes.ANOS[-1])

    # ---- cabeçalho ----
    st.markdown(f"## {nome0}  ·  `{tk0}`")
    if setor0:
        st.caption(f"Setor: {setor0}")

    preco0 = cm["preco"] if cm else None
    var = cm.get("variacao_pct") if cm else None
    pa = acoes.preco_atual(tk0)
    var = pa[2] if pa else None  # variacao_pct
    mkt0 = cm["market_cap"] if cm else (ind0.get("Market Cap") if ind0 else None)

    k = st.columns(4)
    k[0].metric("Cotação", fmt_valor(preco0),
                f"{var:+.2f}%" if var is not None else None)
    k[1].metric("Market Cap", fmt_valor(mkt0))
    k[2].metric("Dividend Yield (12m)", fmt_pct(dy["dy"]) if dy["dy"] else "-")
    k[3].metric("P/L", fmt_mult(ind0.get("P/L")) if ind0 else "-")
    k2 = st.columns(4)
    k2[0].metric("P/VP", fmt_mult(ind0.get("P/VP")) if ind0 else "-")
    k2[1].metric("ROE", fmt_pct(ind0.get("ROE")) if ind0 else "-")
    k2[2].metric("Margem líq.", fmt_pct(ind0.get("Margem líquida")) if ind0 else "-")
    k2[3].metric("Dív.líq./EBITDA", fmt_mult(ind0.get("Dív. líq. / EBITDA")) if ind0 else "-")

    if cm and cm.get("data_preco"):
        st.caption(f"Preço de {cm['data_preco']} · ações totais: "
                   f"{cm['acoes_total']:,.0f}".replace(",", "."))

    st.divider()

    # ---- faixa de preço (52s aprox.) + histórico ----
    colA, colB = st.columns([1, 1])
    with colA:
        st.markdown("#### 📊 Faixa de preço do ano")
        faixa = acoes.posicao_na_faixa(tk0)
        if faixa and faixa["pct"] is not None:
            st.caption(f"Mín R$ {faixa['min']:.2f}  ·  "
                       f"Máx R$ {faixa['max']:.2f}  ({faixa['ano']})")
            st.progress(min(max(faixa["pct"], 0.0), 1.0))
            pos = faixa["pct"] * 100
            onde = ("perto da máxima 🔴" if pos > 70
                    else "perto da mínima 🟢" if pos < 30 else "no meio da faixa")
            st.caption(f"Preço atual a **{pos:.0f}%** da faixa — {onde}.")
        else:
            st.info("Sem faixa de preço para esta ação.")

        hp = acoes.historico_preco(tk0)
        if not hp.empty:
            st.markdown("##### Faixa anual (mín · médio · máx)")
            plot = hp.rename(columns={"preco_min": "Mínimo",
                                      "preco_medio": "Médio", "preco_max": "Máximo"})
            fig = px.line(plot, y=["Mínimo", "Médio", "Máximo"],
                          markers=True, labels={"value": "R$", "ano": "Ano"})
            fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                              legend_title="")
            st.plotly_chart(fig, use_container_width=True)

    with colB:
        st.markdown("#### 💰 Proventos por ano (R$/ação)")
        pano = acoes.proventos_por_ano(tk0)
        if pano.empty:
            st.info("Sem histórico de proventos.")
        else:
            dfp = pano.rename("R$/ação").to_frame()
            fig2 = px.bar(dfp, y="R$/ação", labels={"ano": "Ano"})
            fig2.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                               showlegend=False)
            fig2.update_traces(marker_color="#2E7D32")
            st.plotly_chart(fig2, use_container_width=True)
        if dy["prov_12m"]:
            st.caption(f"Proventos últimos 12m: **R$ {dy['prov_12m']:.4f}/ação**"
                       + (f"  ·  DY {fmt_pct(dy['dy'])}" if dy["dy"] else ""))

    st.divider()

    # ---- histórico TRIMESTRAL (CVM ITR/DFP) ----
    st.markdown("#### 📈 Resultados trimestrais")
    if not acoes.tem_trimestrais(tk0):
        st.info("Sem histórico trimestral para esta ação ainda. "
                "Rode `python financeiro/carga_cvm_trimestral.py` "
                "e depois `python site/atualizar_dados.py`.")
    else:
        modo = st.radio("Visão", ["Trimestre isolado", "Acumulado no ano"],
                        horizontal=True, key="modo_tri")
        tri_rec = acoes.trimestrais_isolados(tk0, "receita_liquida")
        tri_luc = acoes.trimestrais_isolados(tk0, "lucro_liquido")
        if tri_rec.empty:
            st.info("Sem dados trimestrais de receita/lucro.")
        else:
            col_val = "isolado" if modo == "Trimestre isolado" else "receita_liquida"
            col_val_l = "isolado" if modo == "Trimestre isolado" else "lucro_liquido"
            base_r = tri_rec.set_index("periodo")[col_val] / 1e9
            base_l = tri_luc.set_index("periodo")[col_val_l] / 1e9
            cg1, cg2 = st.columns(2)
            with cg1:
                st.markdown("##### Receita líquida (R$ bi)")
                figr = px.bar(base_r, labels={"value": "R$ bi", "periodo": ""})
                figr.update_layout(height=280, showlegend=False,
                                   margin=dict(l=0, r=0, t=10, b=0))
                figr.update_traces(marker_color="#1565C0")
                st.plotly_chart(figr, use_container_width=True)
            with cg2:
                st.markdown("##### Lucro líquido (R$ bi)")
                figl = px.bar(base_l, labels={"value": "R$ bi", "periodo": ""})
                figl.update_layout(height=280, showlegend=False,
                                   margin=dict(l=0, r=0, t=10, b=0))
                figl.update_traces(marker_color="#2E7D32")
                st.plotly_chart(figl, use_container_width=True)
            st.caption("Fonte: ITR/DFP estruturados da CVM. 'Acumulado no ano' é como "
                       "a CVM publica (YTD); 'Trimestre isolado' = YTD do trimestre − "
                       "anterior. T4 vem da DFP (ano fechado).")

    st.divider()

    # ---- próximos/últimos proventos (calendário) ----
    st.markdown("#### 🗓️ Proventos recentes")
    prov = acoes.proventos_pagamentos(tk0, desde_ano=acoes.ANOS[0])
    if prov.empty:
        st.info("Sem proventos registrados.")
    else:
        prov = prov.head(12).rename(columns={
            "data_com": "Data-com", "data_pgto": "Pagamento",
            "tipo": "Tipo", "valor": "Valor (R$/ação)"})
        st.dataframe(prov, use_container_width=True, hide_index=True,
                     column_config={"Valor (R$/ação)":
                                    st.column_config.NumberColumn(format="R$ %.4f")})

    st.divider()

    # ---- quem detém: fundos CVM ----
    st.markdown("#### 🏦 Quem detém esta ação (fundos CVM)")
    st.caption("Cruzamento com as carteiras declaradas dos fundos na CVM. "
               "Diferencial que sites de fundamentos não têm.")
    resumo = _fundos.resumo_acao_por_mes(tk0)
    if resumo.empty:
        st.info("Nenhum fundo declarou posição nesta ação no período coletado.")
    else:
        # usa o último período com cobertura razoável (>= 20 fundos) para "quem detém"
        completos = resumo[resumo["Fundos com posição"] >= 20]
        ref = completos.iloc[-1] if not completos.empty else resumo.iloc[-1]
        periodo_ref = ref["_periodo"]

        m = st.columns(3)
        m[0].metric("Fundos detentores", f"{int(ref['Fundos com posição'])}",
                    help=f"no período {_fundos.periodo_humano(periodo_ref)}")
        m[1].metric("Valor agregado", fmt_valor(ref["Valor aplicado (R$)"]))
        m[2].metric("Período de referência", _fundos.periodo_humano(periodo_ref))

        cev1, cev2 = st.columns([1, 1])
        with cev1:
            st.markdown("##### Evolução — nº de fundos detentores")
            serie_f = resumo["Fundos com posição"]
            st.bar_chart(serie_f)
        with cev2:
            st.markdown("##### Evolução — valor agregado (R$)")
            st.bar_chart(resumo["Valor aplicado (R$)"])

        st.markdown(f"##### Top fundos detentores · {_fundos.periodo_humano(periodo_ref)}")
        top = _fundos.fundos_com_ticker(tk0, periodo_ref)
        if top.empty:
            st.info("Sem detalhamento de fundos neste período.")
        else:
            top = top.head(15).copy()
            if "% do PL" in top.columns:
                top["% do PL"] = top["% do PL"] * 100  # fração -> percentual
            st.dataframe(
                top, use_container_width=True, hide_index=True,
                column_config={
                    "Valor mercado (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
                    "PL do fundo (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
                    "% do PL": st.column_config.NumberColumn(format="%.2f%%"),
                    "Quantidade": st.column_config.NumberColumn(format="%.0f"),
                })

# ===================== ABA DEMONSTRAÇÕES (trimestral, lado a lado) =====================
with tab_dem:
    st.markdown("**DRE, Balanço e DFC trimestrais** lado a lado. Marque contas (📊) em "
                "qualquer demonstração e gere um gráfico comparativo estilo TradingView.")

    # --- mercado: BR (CVM, valores YTD) ou US (SEC, já isolados) ---
    mercado = st.radio("Mercado", ["🇧🇷 Brasil", "🇺🇸 EUA"], horizontal=True,
                       key="dem_mercado")
    eh_us = mercado.endswith("EUA")

    if eh_us:
        DEMS = {"DRE": acoes.DRE_US_LINHAS, "Balanço": acoes.BALANCO_US_LINHAS,
                "DFC": acoes.DFC_US_LINHAS}
        lista_dem = acoes.tickers_us()
        moeda = "US$"
        def_a = "AAPL" if "AAPL" in lista_dem else (lista_dem[0] if lista_dem else "")
        def_b = "MSFT" if "MSFT" in lista_dem else (lista_dem[-1] if lista_dem else "")
    else:
        DEMS = {"DRE": acoes.DRE_TRI_LINHAS, "Balanço": acoes.BALANCO_TRI_LINHAS,
                "DFC": acoes.DFC_TRI_LINHAS}
        lista_dem = lista
        moeda = "R$"
        def_a = "PETR4" if "PETR4" in lista_dem else (lista_dem[0] if lista_dem else "")
        def_b = "GMAT3" if "GMAT3" in lista_dem else (lista_dem[-1] if lista_dem else "")

    if not lista_dem:
        st.info("Sem dados trimestrais para este mercado.")
        st.stop()

    DEM_ICON = {"DRE": "📄", "Balanço": "⚖️", "DFC": "💵"}

    ctrl = st.columns([2.5, 2, 1.6])
    with ctrl[0]:
        dems_sel = st.multiselect("Demonstrações (uma ou mais)", list(DEMS.keys()),
                                  default=["DRE"], key="dem_quais")
        modo_cmp = st.radio("Comparar", ["Duas empresas", "Uma empresa · 2 anos"],
                            key="dem_modo", horizontal=True)
    with ctrl[1]:
        escala_nome = st.selectbox("Escala dos valores",
                                   ["Milhares (mil)", "Milhões (mi)", "Bilhões (bi)"],
                                   index=1, key="dem_escala")
        n_tri = st.slider("Trimestres a mostrar", 4, 24, 8, key="dem_ntri")
    with ctrl[2]:
        if eh_us:
            isolar = False   # dados US já são isolados por trimestre
            st.caption("🇺🇸 valores já isolados por trimestre (fonte: SEC).")
        else:
            isolar = st.toggle("Trimestre isolado", value=True, key="dem_isolar",
                               help="Converte valores acumulados no ano (YTD) em valor "
                                    "de cada trimestre. Não afeta o Balanço (que é saldo).")

    if not dems_sel:
        st.info("Selecione ao menos uma demonstração acima.")
        st.stop()

    _ESCALA = {"Milhares (mil)": (1, "mil", "%.0f"),
               "Milhões (mi)":   (1e3, "mi", "%.1f"),
               "Bilhões (bi)":   (1e6, "bi", "%.2f")}
    esc_div, esc_suf, esc_fmt = _ESCALA[escala_nome]
    num_fmt = "%," + esc_fmt[1:]   # separador de milhar + casas decimais

    # --- define os dois "lados" (empresa/ano) da comparação ---
    if modo_cmp == "Duas empresas":
        ca, cb = st.columns(2)
        with ca:
            tkA = st.selectbox("Empresa A", lista_dem, key="demA",
                               index=lista_dem.index(def_a) if def_a in lista_dem else 0)
        with cb:
            tkB = st.selectbox("Empresa B", lista_dem, key="demB",
                               index=lista_dem.index(def_b) if def_b in lista_dem else 0)
        ladoA, ladoB, rotA, rotB = (tkA, None), (tkB, None), tkA, tkB
    else:
        cc = st.columns([2, 1, 1])
        with cc[0]:
            tkU = st.selectbox("Empresa", lista_dem, key="demU",
                               index=lista_dem.index(def_a) if def_a in lista_dem else 0)
        if eh_us:
            d_full = acoes.demonstracao_trimestral_us(tkU, DEMS[dems_sel[0]])
        else:
            d_full = acoes.demonstracao_trimestral(tkU, DEMS[dems_sel[0]], isolar=False)
        anos_disp = sorted({int(c[:4]) for c in d_full.columns}) if not d_full.empty else []
        with cc[1]:
            anoA = st.selectbox("Ano A", anos_disp,
                                index=len(anos_disp) - 1 if anos_disp else 0, key="demAnoA")
        with cc[2]:
            anoB = st.selectbox("Ano B", anos_disp,
                                index=max(0, len(anos_disp) - 2) if anos_disp else 0,
                                key="demAnoB")
        ladoA, ladoB = (tkU, anoA), (tkU, anoB)
        rotA, rotB = f"{tkU} {anoA}", f"{tkU} {anoB}"

    def montar(ticker, ano, linhas, is_bal):
        if eh_us:
            d = acoes.demonstracao_trimestral_us(ticker, linhas)
        else:
            d = acoes.demonstracao_trimestral(ticker, linhas, isolar=isolar and not is_bal)
        if d.empty:
            return d
        if ano is not None:
            d = d[[c for c in d.columns if c.startswith(str(ano))]]
        else:
            d = d[d.columns[-n_tri:]]
        return d

    # contas marcadas, acumuladas por (demonstração, conta) -> guarda quem está no gráfico
    marcadas = []  # tuplas (dem, conta)
    for dem in dems_sel:
        linhas = DEMS[dem]
        is_bal = dem == "Balanço"
        dA = montar(*ladoA, linhas, is_bal)
        dB = montar(*ladoB, linhas, is_bal)
        if dA.empty and dB.empty:
            continue
        natureza = ("saldo" if is_bal
                    else "trimestre isolado" if (isolar or eh_us)
                    else "acumulado no ano")
        casas = {"mil": 0, "mi": 1, "bi": 2}[esc_suf]
        # default: marca as 2 primeiras contas (robusto p/ rótulos BR e US)
        sk = f"_seldem_{mercado}_{dem}"
        if sk not in st.session_state:
            base = dA if not dA.empty else dB
            st.session_state[sk] = list(base.index[:2]) if not base.empty else []

        c1, c2 = st.columns(2)
        for col, df_lado, rot, suf in [(c1, dA, rotA, "A"), (c2, dB, rotB, "B")]:
            with col:
                st.markdown(
                    f"<div class='card-head'><span class='card-title'>"
                    f"{DEM_ICON[dem]} {rot} · {dem}</span>"
                    f"<span class='card-sub'>{moeda} {esc_suf} · {natureza}</span></div>",
                    unsafe_allow_html=True)
                if df_lado.empty:
                    st.info("Sem dados.")
                    continue
                # key única por mercado+demonstração+empresa+nº trimestres+escala
                # evita o erro #252 do AgGrid (re-render no meio do desenho ao
                # trocar de dados na mesma grid)
                gkey = f"ag_{'us' if eh_us else 'br'}_{dem}_{suf}_{rot}_{n_tri}_{esc_suf}"
                marc = ui.tabela_demonstracao(
                    df_lado / esc_div, casas, st.session_state[sk],
                    key=gkey, escuro=ESCURO)
                st.session_state[sk] = list(dict.fromkeys(marc))
        for conta in st.session_state[sk]:
            marcadas.append((dem, conta, dA, dB))

    # ===== GRÁFICO comparativo =====
    st.divider()
    gctl = st.columns([2, 1.4, 1.4])
    with gctl[0]:
        tipo_g = st.radio("Tipo", ["Linha", "Área", "Barras"], horizontal=True, key="g_tipo")
    with gctl[1]:
        normalizar = st.toggle("Base 100", value=False, key="g_norm",
                               help="Rebaseia cada série a 100 no 1º período — compara "
                                    "tendências independente do tamanho da empresa.")
    with gctl[2]:
        suavizar = st.toggle("Linha suave", value=True, key="g_smooth")

    st.markdown(
        f"<div class='card-head'><span class='card-title'>Evolução comparativa</span>"
        f"<span class='card-sub'>{moeda} {esc_suf}{' · base 100' if normalizar else ''}</span>"
        f"</div>", unsafe_allow_html=True)

    if not marcadas:
        st.caption("Marque ao menos uma conta nas tabelas acima para gerar o gráfico.")
    else:
        series = {}
        for dem, conta, dA, dB in marcadas:
            if not dA.empty and conta in dA.index:
                series[f"{rotA} · {conta}"] = dict(dA.loc[conta].items())
            if not dB.empty and conta in dB.index:
                series[f"{rotB} · {conta}"] = dict(dB.loc[conta].items())
        plot = pd.DataFrame(series) / esc_div
        plot = plot.reindex(sorted(plot.index, key=lambda p: (p[:4], p[-1])))
        if normalizar:
            plot = plot.apply(lambda s: s / s.dropna().iloc[0] * 100
                              if s.dropna().size else s)

        PALETA = ui.PALETA_GRAFICO          # paleta do design system
        escuro = ESCURO                     # gráfico segue o tema do app
        surf = "#161d2b" if escuro else "#ffffff"
        txt = "#e7ecf3" if escuro else "#1a2233"
        grid = "#243044" if escuro else "#e6eaf0"
        shape = "spline" if suavizar else "linear"

        fig = go.Figure()
        for i, col in enumerate(plot.columns):
            cor = PALETA[i % len(PALETA)]
            if tipo_g == "Barras":
                fig.add_bar(x=plot.index, y=plot[col], name=col, marker_color=cor)
            else:
                fig.add_scatter(
                    x=plot.index, y=plot[col], name=col, mode="lines+markers",
                    line=dict(color=cor, width=2.4, shape=shape),
                    fill="tozeroy" if tipo_g == "Área" else None,
                    fillcolor=(cor + "22") if tipo_g == "Área" else None,
                    marker=dict(size=6))

        fig.update_layout(
            height=460, hovermode="x unified", legend_title="",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                        font=dict(family="Inter", color=txt, size=12)),
            margin=dict(l=0, r=10, t=10, b=0),
            paper_bgcolor=surf, plot_bgcolor=surf,
            font=dict(family="Inter", color=txt),
            hoverlabel=dict(bgcolor=surf, font=dict(family="Inter", color=txt),
                            bordercolor=grid),
            yaxis_title=f"{moeda} {esc_suf}" if not normalizar else "Base 100",
            xaxis_title="")
        fig.update_xaxes(showgrid=True, gridcolor=grid, linecolor=grid,
                         tickfont=dict(color=txt))
        fig.update_yaxes(showgrid=True, gridcolor=grid, zeroline=True,
                         zerolinecolor=grid, tickfont=dict(color=txt))
        # card em volta do gráfico
        with st.container(border=True):
            st.plotly_chart(fig, use_container_width=True)
            st.download_button("Baixar dados do gráfico (CSV)",
                               plot.to_csv().encode("utf-8-sig"),
                               "demonstracoes_grafico.csv", "text/csv", key="dl_dem")

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

    st.caption("🟢 verde = melhor · 🔴 vermelho = pior (por indicador).")
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

            FORMATOS = {
                "Preço": fmt_valor, "Market Cap": fmt_valor,
                "Receita líq.": fmt_valor, "Lucro líq.": fmt_valor,
                "Margem líq.": fmt_pct, "ROE": fmt_pct,
                "P/L": fmt_mult, "P/VP": fmt_mult,
            }
            # cor condicional nestas colunas, em tons suaves; (col, maior_é_melhor)
            COLORIR = [("Margem líq.", True), ("ROE", True),
                       ("P/L", False), ("P/VP", False)]

            def escala_suave(serie, maior_melhor):
                """Verde-claro (melhor) -> vermelho-claro (pior), tons pastel."""
                s = pd.to_numeric(serie, errors="coerce")
                vmin, vmax = s.min(), s.max()
                estilos = []
                for v in s:
                    if pd.isna(v) or vmax == vmin:
                        estilos.append("")
                        continue
                    r = (v - vmin) / (vmax - vmin)          # 0..1
                    if not maior_melhor:
                        r = 1 - r                            # inverte (menor é melhor)
                    # interpola entre vermelho-claro (#F8D7DA) e verde-claro (#D4EDDA)
                    r1, g1, b1 = 0xF8, 0xD7, 0xDA            # ruim
                    r2, g2, b2 = 0xD4, 0xED, 0xDA            # bom
                    rr = int(r1 + (r2 - r1) * r)
                    gg = int(g1 + (g2 - g1) * r)
                    bb = int(b1 + (b2 - b1) * r)
                    estilos.append(f"background-color:#{rr:02X}{gg:02X}{bb:02X}; color:#333")
                return estilos

            sty = (df.style
                   .format(FORMATOS)
                   .set_properties(**{"text-align": "center", "font-size": "13px"})
                   .set_table_styles([
                       # cabeçalho das colunas — tema escuro
                       {"selector": "th.col_heading",
                        "props": [("background-color", "#0E2841"),
                                  ("color", "#FFFFFF"), ("font-weight", "bold"),
                                  ("text-align", "center"), ("padding", "8px")]},
                       # canto superior esquerdo (rótulo do índice)
                       {"selector": "th.blank",
                        "props": [("background-color", "#0E2841")]},
                       # coluna dos tickers (lateral) — tema escuro
                       {"selector": "th.row_heading",
                        "props": [("background-color", "#0E2841"),
                                  ("color", "#FFFFFF"), ("font-weight", "bold"),
                                  ("text-align", "center"), ("padding", "8px")]},
                   ]))
            if len(df) >= 2:
                for col, maior in COLORIR:
                    if col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().sum() >= 2:
                        sty = sty.apply(lambda s, m=maior: escala_suave(s, m), subset=[col])
            st.dataframe(sty, use_container_width=True)

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
        out = df.sort_values("ROE", ascending=False)
        # tabela formatada para leitura (valores em bi/mi, % em 30% etc.)
        leitura = pd.DataFrame({
            "Ticker": out["Ticker"],
            "Preço": out["Preço"].map(fmt_valor),
            "Market Cap": out["Market Cap"].map(fmt_valor),
            "Receita líq.": out["Receita líquida"].map(fmt_valor),
            "Lucro líq.": out["Lucro líquido"].map(fmt_valor),
            "Margem líq.": out["Margem líquida"].map(fmt_pct),
            "ROE": out["ROE"].map(fmt_pct),
            "P/L": out["P/L"].map(fmt_mult),
            "P/VP": out["P/VP"].map(fmt_mult),
            "Dív.líq./EBITDA": out["Dív. líq. / EBITDA"].map(fmt_mult),
        })
        st.dataframe(leitura, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Baixar resultado (CSV)",
                           out.to_csv(index=False).encode("utf-8-sig"),
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

# ===================== ABA 5: SIMULADOR DE CARTEIRA =====================
with tab5:
    st.markdown("Monte uma carteira: escolha as ações, defina o **% de cada uma** "
                "e veja os indicadores ponderados. Você pode **salvar** a carteira.")

    # --- carregar carteira salva ---
    salvas = carteiras.listar()
    cc1, cc2 = st.columns([3, 1])
    with cc1:
        escolha = st.selectbox("Carregar carteira salva",
                               ["(nova)"] + salvas, key="cart_load")
    with cc2:
        if escolha != "(nova)" and st.button("🗑️ Excluir", key="cart_del"):
            carteiras.excluir(escolha)
            st.rerun()

    # se escolheu uma salva e ainda não aplicou, popula o estado
    if escolha != "(nova)" and st.session_state.get("_cart_atual") != escolha:
        salva = carteiras.carregar(escolha)
        if salva:
            st.session_state["cart_sel"] = list(salva.keys())
            for tk, p in salva.items():
                st.session_state[f"peso_{tk}"] = float(p)
            st.session_state["_cart_atual"] = escolha
            st.rerun()

    anoc = st.selectbox("Ano de referência", acoes.ANOS,
                        index=len(acoes.ANOS) - 1, key="ano_cart")
    sel = st.multiselect("Ações da carteira", lista,
                         default=[t for t in ["PETR4", "VALE3", "ITUB4"] if t in lista],
                         key="cart_sel")

    if not sel:
        st.info("Selecione ao menos uma ação.")
    else:
        st.markdown("**Pesos (%)**")
        cols = st.columns(min(len(sel), 5))
        pesos = {}
        peso_default = round(100.0 / len(sel), 1)
        for i, tk in enumerate(sel):
            with cols[i % len(cols)]:
                pesos[tk] = st.number_input(tk, min_value=0.0, max_value=100.0,
                                            value=st.session_state.get(f"peso_{tk}", peso_default),
                                            step=1.0, key=f"peso_{tk}")
        soma = sum(pesos.values())
        if abs(soma - 100.0) > 0.05:
            st.warning(f"⚠️ Os pesos somam **{soma:.1f}%** (não 100%). "
                       "As médias usam os pesos como estão — o resultado pode ficar distorcido.")
        else:
            st.success(f"Pesos somam {soma:.1f}%. ✓")

        # --- salvar a carteira atual ---
        sv1, sv2 = st.columns([3, 1])
        with sv1:
            nome_save = st.text_input("Nome para salvar esta carteira",
                                      value=escolha if escolha != "(nova)" else "",
                                      placeholder="ex.: Minha carteira dividendos")
        with sv2:
            st.write("")
            st.write("")
            if st.button("💾 Salvar", key="cart_save"):
                try:
                    carteiras.salvar(nome_save, pesos)
                    st.session_state["_cart_atual"] = nome_save
                    st.success(f"Carteira '{nome_save}' salva!")
                except ValueError as e:
                    st.error(str(e))

        # monta tabela de indicadores por ação
        linhas = []
        for tk in sel:
            ind = acoes.indicadores_ano(tk, anoc)
            if not ind:
                continue
            linhas.append({
                "Ticker": tk, "Peso %": pesos[tk],
                "Receita líq.": ind["Receita líquida"], "Lucro líq.": ind["Lucro líquido"],
                "Margem líq.": ind["Margem líquida"], "ROE": ind["ROE"],
                "P/L": ind["P/L"], "P/VP": ind["P/VP"],
            })
        if not linhas:
            st.warning("Sem indicadores para as ações escolhidas neste ano.")
        else:
            df = pd.DataFrame(linhas).set_index("Ticker")
            w = df["Peso %"] / 100.0  # frações

            def media_simples(col):
                """Média ponderada simples (margem, ROE, receita, lucro)."""
                s = pd.to_numeric(df[col], errors="coerce")
                mask = s.notna()
                if mask.sum() == 0 or w[mask].sum() == 0:
                    return None
                return (s[mask] * w[mask]).sum() / w[mask].sum()

            def media_inverso(col):
                """Para P/L e P/VP: pondera o INVERSO (forma correta de agregar múltiplos)."""
                s = pd.to_numeric(df[col], errors="coerce")
                mask = s.notna() & (s > 0)
                if mask.sum() == 0 or w[mask].sum() == 0:
                    return None
                inv = (w[mask] / w[mask].sum() * (1.0 / s[mask])).sum()
                return 1.0 / inv if inv else None

            carteira = {
                "Receita líq.": media_simples("Receita líq."),
                "Lucro líq.": media_simples("Lucro líq."),
                "Margem líq.": media_simples("Margem líq."),
                "ROE": media_simples("ROE"),
                "P/L": media_inverso("P/L"),
                "P/VP": media_inverso("P/VP"),
            }

            # tabela das ações (com pesos)
            st.markdown("**Composição da carteira**")
            sty = (df.style.format({
                        "Peso %": "{:.1f}%",
                        "Receita líq.": fmt_valor, "Lucro líq.": fmt_valor,
                        "Margem líq.": fmt_pct, "ROE": fmt_pct,
                        "P/L": fmt_mult, "P/VP": fmt_mult})
                   .set_table_styles([
                       {"selector": "th.col_heading",
                        "props": [("background-color", "#0E2841"), ("color", "white"),
                                  ("font-weight", "bold"), ("text-align", "center")]},
                       {"selector": "th.row_heading",
                        "props": [("background-color", "#0E2841"), ("color", "white"),
                                  ("font-weight", "bold")]},
                       {"selector": "th.blank",
                        "props": [("background-color", "#0E2841")]},
                   ])
                   .set_properties(**{"text-align": "center"}))
            st.dataframe(sty, use_container_width=True)

            # cartões com o resultado da carteira
            st.markdown("### 🧺 Indicadores da carteira (ponderados)")
            r1c1, r1c2, r1c3 = st.columns(3)
            r1c1.metric("Receita líq. média", fmt_valor(carteira["Receita líq."]))
            r1c2.metric("Lucro líq. médio", fmt_valor(carteira["Lucro líq."]))
            r1c3.metric("Margem líq. média", fmt_pct(carteira["Margem líq."]))
            r2c1, r2c2, r2c3 = st.columns(3)
            r2c1.metric("ROE médio", fmt_pct(carteira["ROE"]))
            r2c2.metric("P/L da carteira", fmt_mult(carteira["P/L"]))
            r2c3.metric("P/VP da carteira", fmt_mult(carteira["P/VP"]))

            st.caption("ℹ️ Receita, lucro, margem e ROE = média ponderada pelos pesos. "
                       "P/L e P/VP = ponderados pelo inverso (forma correta de "
                       "agregar múltiplos numa carteira).")

# touch p/ forcar reload
