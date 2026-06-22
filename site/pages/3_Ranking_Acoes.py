"""
3_Ranking_Acoes.py — ranking de ações da B3 (dados Investidor10) + montador de
carteira de dividendos. Reproduz as abas do Excel, mas interativo:

  • Ranking      — tabela completa (307 ações) com filtros por setor/indicador.
  • Carteira     — escolhe ações, define o % de cada uma e calcula na hora o
                   valor alocado e os dividendos estimados (como no Excel).
  • Por setor    — concentração da carteira por setor.

Dados: tabela ranking_acoes no financeiro.db (cópia em site/data/), gravada por
financeiro/ranking_investidor10.py. Para atualizar:
    python financeiro/ranking_investidor10.py --banco --sem-excel
    python site/atualizar_dados.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from lib import acoes, ui

st.set_page_config(page_title="Ranking de Ações", page_icon="🏆", layout="wide")
ESCURO = False
ui.aplicar_tema(ESCURO)

ui.cabecalho("Ranking de Ações",
             "Indicadores de toda a B3 e montador de carteira de dividendos · "
             "fonte: Investidor10")

if not acoes.tem_ranking():
    st.error("Sem dados de ranking. Rode:\n\n"
             "`python financeiro/ranking_investidor10.py --banco --sem-excel`\n\n"
             "e depois `python site/atualizar_dados.py`.")
    st.stop()


@st.cache_data(show_spinner="Carregando ranking...")
def carregar():
    return acoes.ranking_acoes(renomear=True)


base = carregar()
ui.selo_atualizacao(acoes.ranking_atualizado_em(), extra=f"{len(base)} ações")


# ----------------- formatadores -----------------
def fmt_dinheiro(v):
    if v is None or pd.isna(v):
        return "–"
    def _br(x, suf):
        return f"R$ {x:,.2f} {suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(v) >= 1e12:
        return _br(v / 1e12, "tri")
    if abs(v) >= 1e9:
        return _br(v / 1e9, "bi")
    if abs(v) >= 1e6:
        return _br(v / 1e6, "mi")
    return f"R$ {ui.fmt_ptbr(v, 2)}"


COLS_MOEDA = ["Valor de Mercado (R$)", "Patrimônio Líquido (R$)", "Receita Líquida (R$)",
              "Lucro Líquido (R$)", "Caixa (R$)"]
COLS_PCT = ["DY 12m (%)", "DY médio 5a (%)", "ROE (%)", "Margem Líquida (%)",
            "Cresc. Receita 5a (%)", "Cresc. Lucro 5a (%)", "Upside Graham (%)",
            "Upside Bazin (%)", "Variação 30d (%)", "Variação 12m (%)", "Variação 5a (%)"]
COLS_MULT = ["P/L", "P/VP", "Dív. Bruta / PL"]
COLS_PRECO = ["Preço Atual (R$)", "Preço Justo Graham (R$)", "Preço-teto Bazin (R$)"]


def column_config(df):
    """Configura colunas do st.dataframe (formatos numéricos pt-BR-ish)."""
    cfg = {}
    for c in df.columns:
        if c in COLS_MOEDA:
            cfg[c] = st.column_config.NumberColumn(format="R$ %.0f")
        elif c in COLS_PCT:
            cfg[c] = st.column_config.NumberColumn(format="%.2f%%")
        elif c in COLS_MULT:
            cfg[c] = st.column_config.NumberColumn(format="%.2f")
        elif c in COLS_PRECO:
            cfg[c] = st.column_config.NumberColumn(format="R$ %.2f")
        elif c == "Nota Buy&Hold":
            cfg[c] = st.column_config.NumberColumn(format="%d")
    return cfg


tab_rank, tab_sim, tab_sub, tab_cart, tab_setor = st.tabs(
    ["🏆 Ranking de ações", "🎯 Simulador de ranking", "🏭 Médias por subsetor",
     "🧺 Carteira de dividendos", "🥧 Por setor"])

# ===================== ABA RANKING =====================
with tab_rank:
    st.markdown("Tabela completa da B3. Filtre por setor e por indicadores; "
                "clique no cabeçalho de qualquer coluna para ordenar.")

    setores = sorted(base["Setor"].dropna().unique())
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        sel_setores = st.multiselect("Setores", setores, default=[])
    with f2:
        pl_max = st.number_input("P/L máx (0 = ignora)", value=0.0, step=1.0)
    with f3:
        dy_min = st.number_input("DY 12m mín % (0 = ignora)", value=0.0, step=1.0)
    f4, f5 = st.columns(2)
    with f4:
        roe_min = st.number_input("ROE mín % (0 = ignora)", value=0.0, step=1.0)
    with f5:
        busca = st.text_input("Buscar ticker ou empresa", "")

    df = base.copy()
    if sel_setores:
        df = df[df["Setor"].isin(sel_setores)]
    if pl_max > 0:
        df = df[(df["P/L"] > 0) & (df["P/L"] <= pl_max)]
    if dy_min > 0:
        df = df[df["DY 12m (%)"] >= dy_min]
    if roe_min > 0:
        df = df[df["ROE (%)"] >= roe_min]
    if busca.strip():
        q = busca.strip().upper()
        df = df[df["Ticker"].str.upper().str.contains(q)
                | df["Empresa"].str.upper().str.contains(q, na=False)]

    st.caption(f"**{len(df)}** ações.")
    # esconde a coluna técnica de data
    mostra = df.drop(columns=[c for c in ["atualizado_em"] if c in df.columns])
    # valores em R$ ficam legíveis (R$ x,xx bi/tri) via Styler — o st.dataframe
    # ainda ordena pelos valores numéricos por trás.
    cols_moeda = [c for c in COLS_MOEDA if c in mostra.columns]
    sty_rk = mostra.style.format({c: fmt_dinheiro for c in cols_moeda}, na_rep="–")
    cfg_rk = {k: v for k, v in column_config(mostra).items() if k not in cols_moeda}
    st.dataframe(sty_rk, use_container_width=True, hide_index=True,
                 height=560, column_config=cfg_rk)
    st.download_button("⬇️ Baixar (CSV)",
                       mostra.to_csv(index=False).encode("utf-8-sig"),
                       "ranking_acoes.csv", "text/csv")

# ===================== ABA SIMULADOR DE RANKING =====================
with tab_sim:
    st.markdown("Defina **direção, limites e peso** de cada indicador. A nota de "
                "cada ação é normalizada **0–100** entre os limites e multiplicada "
                "pelo peso — depois somada na **Nota Final**. Igual à planilha.")

    cfg = acoes.RANKING_CONFIG_PADRAO

    # botão para restaurar os limites/pesos padrão (a direção é sempre fixa)
    topo = st.columns([3, 1])
    topo[0].markdown("##### Configuração dos indicadores")
    if topo[1].button("↺ Restaurar padrão", key="reset_cfg",
                      help="Volta limites e pesos aos valores padrão."):
        for rotulo, _, inf, sup, peso, _ in cfg:
            st.session_state[f"inf_{rotulo}"] = float(inf)
            st.session_state[f"sup_{rotulo}"] = float(sup)
            st.session_state[f"peso_{rotulo}"] = int(peso)
        st.rerun()

    hdr = st.columns([2.2, 1.6, 1.1, 1.1, 1.1])
    for col, txt in zip(hdr, ["Indicador", "Direção (fixa)", "Lim. inferior",
                              "Lim. superior", "Peso %"]):
        col.markdown(f"**{txt}**")

    nova_cfg = []
    for rotulo, maior, inf, sup, peso, zera in cfg:
        c = st.columns([2.2, 1.6, 1.1, 1.1, 1.1])
        c[0].markdown(f"<div style='padding-top:8px'>{rotulo}</div>",
                      unsafe_allow_html=True)
        # direção FIXA (só exibida, não editável)
        seta = "▲ maior" if maior else "▼ menor"
        c[1].markdown(f"<div style='padding-top:8px;color:#5b6677'>{seta} é melhor"
                      "</div>", unsafe_allow_html=True)
        inf_v = c[2].number_input("inf", value=float(inf), step=0.5,
                                  key=f"inf_{rotulo}", label_visibility="collapsed")
        sup_v = c[3].number_input("sup", value=float(sup), step=0.5,
                                  key=f"sup_{rotulo}", label_visibility="collapsed")
        peso_v = c[4].number_input("peso", value=int(peso), step=1, min_value=0,
                                   key=f"peso_{rotulo}", label_visibility="collapsed")
        nova_cfg.append((rotulo, maior, inf_v, sup_v, peso_v, zera))

    soma_peso = sum(c[4] for c in nova_cfg)
    if soma_peso == 0:
        st.error("Defina ao menos um peso > 0 para calcular o ranking.")
    else:
        if soma_peso != 100:
            st.info(f"Soma dos pesos = **{soma_peso}** (não 100). Tudo bem — os "
                    "pesos são normalizados pela soma automaticamente.")
        else:
            st.success("Pesos somam 100. ✓")

        rk = acoes.ranking_ponderado(config=nova_cfg, base=base)

        n_top = st.slider("Quantas mostrar", 10, len(rk), 30, step=10)
        st.markdown("##### 🏆 Ranking final das empresas")
        st.caption("Cada coluna **n.** mostra os **pontos que o indicador soma** na "
                   "nota (já ponderado pelo peso). As colunas **somam a Nota Final**. "
                   "O máximo de cada coluna é o próprio peso do indicador. "
                   "🟩 verde = perto do máximo · 🟥 vermelho = perto de zero.")

        notas_cols = [c for c in rk.columns if c.startswith("nota ")]
        mostrar = rk.head(n_top).rename(
            columns={c: c.replace("nota ", "n. ") for c in notas_cols})

        # teto de cada coluna = peso normalizado (nota 100 × peso/total). A cor é
        # relativa a esse teto (verde = perto do máximo possível da coluna).
        peso_total = sum(c[4] for c in nova_cfg if c[4] > 0) or 1
        teto_col = {f"n. {rot}": (peso / peso_total) * 100
                    for rot, _, _, _, peso, _ in nova_cfg if peso > 0}
        teto_col["Nota Final"] = 100.0
        # ordem preservada e sem duplicatas; só colunas que existem na tabela
        cols_cor = [c for c in (["Nota Final"] + [f"n. {r}" for r, *_ in nova_cfg])
                    if c in mostrar.columns and c in teto_col]

        def cor_celula(v, teto):
            if pd.isna(v):
                return ""
            r = max(0.0, min(1.0, float(v) / (teto or 1.0)))
            rr = int(0xF8 + (0xD4 - 0xF8) * r)
            gg = int(0xD7 + (0xED - 0xD7) * r)
            bb = int(0xDA + (0xDA - 0xDA) * r)
            return f"background-color:#{rr:02X}{gg:02X}{bb:02X};color:#333"

        def grad_coluna(col):
            """Recebe UMA coluna (Series) e devolve a lista de estilos."""
            teto = teto_col.get(col.name, 100.0)
            return [cor_celula(v, teto) for v in col]

        fmt = {c: "{:.1f}" for c in cols_cor}
        sty = (mostrar.style
               .format(fmt, na_rep="–")
               .apply(grad_coluna, axis=0, subset=cols_cor))
        st.dataframe(sty, use_container_width=True, hide_index=True, height=560)
        st.download_button("⬇️ Baixar ranking (CSV)",
                           rk.to_csv(index=False).encode("utf-8-sig"),
                           "ranking_ponderado.csv", "text/csv", key="dl_rk_pond")

# ===================== ABA MÉDIAS POR SUBSETOR =====================
with tab_sub:
    st.markdown("Médias de cada indicador **por subsetor**, ponderadas pelo "
                "**valor de mercado** (empresas maiores pesam mais). Ajuda a ver "
                "qual subsetor está caro/barato e a comparar uma ação com seus pares.")
    ms = acoes.medias_por_subsetor(base=base)
    minimo = st.number_input("Mostrar só subsetores com ao menos N empresas",
                             value=1, min_value=1, step=1)
    ms_f = ms[ms["Nº Empresas"] >= minimo].copy()
    # Market Cap como texto legível (R$ x,xx bi/tri) — número cru fica ilegível
    ms_f["Market Cap (R$)"] = ms_f["Market Cap (R$)"].map(fmt_dinheiro)
    st.caption(f"{len(ms_f)} subsetores. **Clique numa linha** para ver as ações "
               "daquele subsetor, com cor por indicador.")
    sel_sub = st.dataframe(
        ms_f, use_container_width=True, hide_index=True, height=560,
        on_select="rerun", selection_mode="single-row", key="tbl_subsetor",
        column_config={
            "Nº Empresas": st.column_config.NumberColumn(format="%d"),
            **{c: st.column_config.NumberColumn(format="%.2f")
               for c in ["P/L", "P/VP", "Dív. Bruta / PL"]},
            **{c: st.column_config.NumberColumn(format="%.2f%%")
               for c in ["DY 12m (%)", "DY médio 5a (%)", "ROE (%)",
                         "Margem Líquida (%)", "Cresc. Receita 5a (%)",
                         "Cresc. Lucro 5a (%)"]},
        })
    st.download_button("⬇️ Baixar médias (CSV)",
                       ms.to_csv(index=False).encode("utf-8-sig"),
                       "medias_subsetor.csv", "text/csv", key="dl_ms")

    # ---- detalhe: ações do subsetor clicado, com cor por indicador ----
    linhas_sel = sel_sub.selection.rows if sel_sub and sel_sub.selection else []
    if linhas_sel:
        sub_nome = ms_f.iloc[linhas_sel[0]]["Subsetor"]
        st.divider()
        st.markdown(f"#### 🏭 Ações de **{sub_nome}**")

        det = base[base["Subsetor"] == sub_nome].copy()
        cols_det = ["Ticker", "Empresa", "Valor de Mercado (R$)", "P/L", "P/VP",
                    "DY 12m (%)", "DY médio 5a (%)", "ROE (%)", "Margem Líquida (%)",
                    "Dív. Bruta / PL", "Cresc. Receita 5a (%)", "Cresc. Lucro 5a (%)"]
        cols_det = [c for c in cols_det if c in det.columns]
        det = det[cols_det].sort_values("Valor de Mercado (R$)", ascending=False)

        # direção por indicador: True = maior é melhor (verde no topo)
        MAIOR_MELHOR = {
            "DY 12m (%)": True, "DY médio 5a (%)": True, "ROE (%)": True,
            "Margem Líquida (%)": True, "Cresc. Receita 5a (%)": True,
            "Cresc. Lucro 5a (%)": True, "P/L": False, "P/VP": False,
            "Dív. Bruta / PL": False,
        }

        def grad_indicador(col):
            """Verde = melhor da coluna, vermelho = pior (respeita a direção)."""
            vals = pd.to_numeric(col, errors="coerce")
            vmin, vmax = vals.min(), vals.max()
            estilos = []
            for v in vals:
                if pd.isna(v) or vmax == vmin:
                    estilos.append("")
                    continue
                r = (v - vmin) / (vmax - vmin)          # 0..1
                if not MAIOR_MELHOR.get(col.name, True):
                    r = 1 - r                            # menor é melhor: inverte
                rr = int(0xF8 + (0xD4 - 0xF8) * r)
                gg = int(0xD7 + (0xED - 0xD7) * r)
                bb = int(0xDA + (0xDA - 0xDA) * r)
                estilos.append(f"background-color:#{rr:02X}{gg:02X}{bb:02X};color:#333")
            return estilos

        cols_color = [c for c in MAIOR_MELHOR if c in det.columns]
        sty_det = (det.style
                   .format({"Valor de Mercado (R$)": fmt_dinheiro}, na_rep="–")
                   .format({c: "{:.2f}" for c in ["P/L", "P/VP", "Dív. Bruta / PL"]
                            if c in det.columns}, na_rep="–")
                   .format({c: "{:.2f}%" for c in
                            ["DY 12m (%)", "DY médio 5a (%)", "ROE (%)",
                             "Margem Líquida (%)", "Cresc. Receita 5a (%)",
                             "Cresc. Lucro 5a (%)"] if c in det.columns}, na_rep="–")
                   .apply(grad_indicador, axis=0, subset=cols_color))
        st.dataframe(sty_det, use_container_width=True, hide_index=True,
                     height=min(46 + 35 * len(det), 600))
        st.caption("🟩 verde = melhor do subsetor nesse indicador · 🟥 vermelho = "
                   "pior. P/L, P/VP e Dív/PL: **menor** é melhor (cor já invertida).")

# ===================== ABA CARTEIRA =====================
with tab_cart:
    st.markdown("Monte a carteira: escolha as ações, defina o **% de cada uma** e "
                "veja na hora o valor alocado e os **dividendos estimados**. "
                "Igual ao Excel — mas o cálculo é instantâneo.")

    tickers = base["Ticker"].tolist()
    DEFAULT = [t for t in ["ITSA4", "BBSE3", "BBAS3", "CMIG4", "ISAE4", "SAPR4",
                           "PETR4", "GRND3", "CXSE3", "VULC3", "BBDC3", "GMAT3",
                           "JHSF3", "ABCB4", "RECV3", "CGRA4", "MELK3", "BRAP4",
                           "ALLD3"] if t in tickers]

    c0, c1, c2 = st.columns([2.6, 1, 1.4])
    with c0:
        sel = st.multiselect("Ações da carteira", tickers, default=DEFAULT, key="cart_rk")
    with c1:
        patrimonio = st.number_input("Patrimônio (R$)", value=10_000_000,
                                     step=100_000, min_value=0)
    with c2:
        base_dy = st.radio(
            "Estimar dividendos pelo:",
            ["DY últimos 12 meses", "DY médio 5 anos"],
            key="cart_base_dy",
            help="12 meses = mais recente (pode ter proventos extraordinários). "
                 "Médio 5 anos = mais estável/conservador.")
    col_dy = "DY 12m (%)" if base_dy.startswith("DY últimos") else "DY médio 5a (%)"

    if not sel:
        st.info("Selecione ao menos uma ação.")
        st.session_state.pop("_cart_df", None)
        st.stop()  # nada mais a montar nesta página sem ações selecionadas

    sub = base[base["Ticker"].isin(sel)].set_index("Ticker")

    st.markdown("**Pesos (%)** — ajuste cada um:")
    cols = st.columns(min(len(sel), 6))
    peso_default = round(100.0 / len(sel), 1)
    pesos = {}
    for i, tk in enumerate(sel):
        with cols[i % len(cols)]:
            pesos[tk] = st.number_input(tk, min_value=0.0, max_value=100.0,
                                        value=st.session_state.get(f"pk_{tk}", peso_default),
                                        step=0.5, key=f"pk_{tk}")
    soma = sum(pesos.values())
    if abs(soma - 100.0) > 0.05:
        st.warning(f"⚠️ Os pesos somam **{soma:.1f}%** (não 100%). "
                   "Os valores são calculados com os pesos como estão.")
    else:
        st.success(f"Pesos somam {soma:.1f}%. ✓")

    # rótulo curto da coluna de DY usada (aparece na tabela)
    rotulo_dy = "DY 12m (%)" if col_dy == "DY 12m (%)" else "DY 5a (%)"

    # monta a tabela da carteira
    linhas = []
    for tk in sel:
        r = sub.loc[tk]
        peso = pesos[tk]
        valor = patrimonio * peso / 100
        dy = r[col_dy]                       # DY escolhido (12m ou médio 5a)
        div_ano = valor * (dy / 100) if pd.notna(dy) else None
        linhas.append({
            "Ticker": tk, "Empresa": r.get("Empresa"), "Setor": r.get("Setor"),
            "Peso %": peso, "Valor alocado (R$)": valor,
            rotulo_dy: dy, "Dividendos ano 1 (R$)": div_ano,
            "P/L": r.get("P/L"), "P/VP": r.get("P/VP"), "ROE (%)": r.get("ROE (%)"),
            "Nota Buy&Hold": r.get("Nota Buy&Hold"),
        })
    cart = pd.DataFrame(linhas)

    # ponderações da carteira
    w = cart["Peso %"] / 100
    dy_pond = (cart[rotulo_dy].fillna(0) * w).sum()
    div_total = cart["Dividendos ano 1 (R$)"].sum(skipna=True)
    valor_total = cart["Valor alocado (R$)"].sum()
    pvp_pond = (cart["P/VP"].fillna(0) * w).sum()
    roe_pond = (cart["ROE (%)"].fillna(0) * w).sum()

    m = st.columns(4)
    m[0].metric("Total alocado", fmt_dinheiro(valor_total))
    m[1].metric(f"DY ponderado ({'12m' if col_dy=='DY 12m (%)' else '5a'})",
                f"{dy_pond:.2f}%")
    m[2].metric("Dividendos ano 1 (est.)", fmt_dinheiro(div_total))
    m[3].metric("Renda mensal média", fmt_dinheiro(div_total / 12) if div_total else "–")
    m2 = st.columns(4)
    m2[0].metric("P/VP ponderado", f"{pvp_pond:.2f}")
    m2[1].metric("ROE ponderado", f"{roe_pond:.1f}%")
    m2[2].metric("Nº de ações", f"{len(sel)}")
    m2[3].metric("Setores", f"{cart['Setor'].nunique()}")

    st.markdown("#### Composição")
    st.dataframe(
        cart.sort_values("Peso %", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={
            "Peso %": st.column_config.NumberColumn(format="%.1f%%"),
            "Valor alocado (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
            rotulo_dy: st.column_config.NumberColumn(format="%.2f%%"),
            "Dividendos ano 1 (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
            "P/L": st.column_config.NumberColumn(format="%.2f"),
            "P/VP": st.column_config.NumberColumn(format="%.2f"),
            "ROE (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Nota Buy&Hold": st.column_config.NumberColumn(format="%d"),
        })
    st.download_button("⬇️ Baixar carteira (CSV)",
                       cart.to_csv(index=False).encode("utf-8-sig"),
                       "carteira_dividendos.csv", "text/csv")

    if col_dy == "DY 12m (%)":
        st.caption("ℹ️ Dividendos ano 1 = valor alocado × **DY dos últimos 12 meses**. "
                   "Atenção: o DY de 12m pode incluir proventos extraordinários "
                   "(ex.: GRND3) — pode superestimar a renda recorrente.")
    else:
        st.caption("ℹ️ Dividendos ano 1 = valor alocado × **DY médio dos últimos 5 "
                   "anos**. Base mais estável; suaviza anos atípicos, mas pode não "
                   "refletir mudanças recentes na política de dividendos.")

    # guarda pra aba Por setor
    st.session_state["_cart_df"] = cart

# ===================== ABA POR SETOR =====================
with tab_setor:
    cart = st.session_state.get("_cart_df")
    if cart is None or cart.empty:
        st.info("Monte a carteira na aba anterior para ver a concentração por setor.")
    else:
        setor = (cart.groupby("Setor")
                 .agg(**{"Peso %": ("Peso %", "sum"),
                         "Valor (R$)": ("Valor alocado (R$)", "sum"),
                         "Dividendos ano 1 (R$)": ("Dividendos ano 1 (R$)", "sum"),
                         "Nº ações": ("Ticker", "count")})
                 .sort_values("Peso %", ascending=False).reset_index())

        cg1, cg2 = st.columns([1, 1])
        with cg1:
            st.markdown("#### Peso por setor")
            import plotly.express as px
            fig = px.pie(setor, names="Setor", values="Peso %", hole=0.45,
                         color_discrete_sequence=ui.PALETA_GRAFICO)
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0),
                              legend=dict(font=dict(size=11)))
            st.plotly_chart(fig, use_container_width=True)
        with cg2:
            st.markdown("#### Dividendos por setor")
            fig2 = px.bar(setor, x="Setor", y="Dividendos ano 1 (R$)",
                          color="Setor", color_discrete_sequence=ui.PALETA_GRAFICO)
            fig2.update_layout(height=340, showlegend=False,
                               margin=dict(l=0, r=0, t=10, b=0), xaxis_title="")
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(setor, use_container_width=True, hide_index=True,
                     column_config={
                         "Peso %": st.column_config.NumberColumn(format="%.1f%%"),
                         "Valor (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
                         "Dividendos ano 1 (R$)":
                             st.column_config.NumberColumn(format="R$ %.0f"),
                     })
