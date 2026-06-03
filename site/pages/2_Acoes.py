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


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📋 Ficha da ação", "⚖️ Comparar", "🔎 Triagem", "💰 Dividendos",
     "🧺 Simulador de carteira"])

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
                "e veja os indicadores ponderados da carteira.")
    anoc = st.selectbox("Ano de referência", acoes.ANOS,
                        index=len(acoes.ANOS) - 1, key="ano_cart")
    sel = st.multiselect("Ações da carteira", lista,
                         default=[t for t in ["PETR4", "VALE3", "ITUB4"] if t in lista],
                         key="cart_sel")

    if not sel:
        st.info("Selecione ao menos uma ação.")
    else:
        # campos de % por ação
        st.markdown("**Pesos (%)**")
        cols = st.columns(min(len(sel), 5))
        pesos = {}
        peso_default = round(100.0 / len(sel), 1)
        for i, tk in enumerate(sel):
            with cols[i % len(cols)]:
                pesos[tk] = st.number_input(tk, min_value=0.0, max_value=100.0,
                                            value=peso_default, step=1.0, key=f"peso_{tk}")
        soma = sum(pesos.values())
        if abs(soma - 100.0) > 0.05:
            st.warning(f"⚠️ Os pesos somam **{soma:.1f}%** (não 100%). "
                       "As médias usam os pesos como estão — o resultado pode ficar distorcido.")
        else:
            st.success(f"Pesos somam {soma:.1f}%. ✓")

        # monta tabela de indicadores por ação
        linhas = []
        for tk in sel:
            ind = acoes.indicadores_ano(tk, anoc)
            if not ind:
                continue
            linhas.append({
                "Ticker": tk, "Peso %": pesos[tk],
                "Margem líq.": ind["Margem líquida"], "ROE": ind["ROE"],
                "P/L": ind["P/L"], "P/VP": ind["P/VP"],
            })
        if not linhas:
            st.warning("Sem indicadores para as ações escolhidas neste ano.")
        else:
            df = pd.DataFrame(linhas).set_index("Ticker")
            w = df["Peso %"] / 100.0  # frações

            def media_simples(col):
                """Média ponderada simples (boa p/ margem, ROE)."""
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
                "Margem líq.": media_simples("Margem líq."),
                "ROE": media_simples("ROE"),
                "P/L": media_inverso("P/L"),
                "P/VP": media_inverso("P/VP"),
            }

            # tabela das ações (com pesos)
            st.markdown("**Composição da carteira**")
            sty = (df.style.format({
                        "Peso %": "{:.1f}%", "Margem líq.": fmt_pct,
                        "ROE": fmt_pct, "P/L": fmt_mult, "P/VP": fmt_mult})
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
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Margem líq. média", fmt_pct(carteira["Margem líq."]))
            c2.metric("ROE médio", fmt_pct(carteira["ROE"]))
            c3.metric("P/L da carteira", fmt_mult(carteira["P/L"]))
            c4.metric("P/VP da carteira", fmt_mult(carteira["P/VP"]))

            st.caption("ℹ️ Margem e ROE = média ponderada pelos pesos. "
                       "P/L e P/VP = ponderados pelo inverso (forma correta de "
                       "agregar múltiplos numa carteira).")
