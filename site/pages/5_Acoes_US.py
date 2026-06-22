"""
5_Acoes_US.py — ranking de ações dos EUA (S&P 500, fonte yfinance) + simulador
de ranking ponderado, no mesmo estilo da aba de ações BR.

Abas:
  • Ranking US        — tabela completa do S&P 500, filtrável/ordenável.
  • Simulador         — define direção/limites/peso de cada indicador → ranking.
  • Médias por setor  — médias por setor, ponderadas pelo valor de mercado.

Dados: tabela ranking_acoes_us no financeiro.db (cópia em site/data/), gravada por
financeiro/ranking_us.py. Para atualizar:
    python financeiro/ranking_us.py --banco --sem-excel
    python site/atualizar_dados.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from lib import acoes, ui

st.set_page_config(page_title="Ações US — Ranking", page_icon="🇺🇸", layout="wide")
ESCURO = False
ui.aplicar_tema(ESCURO)
ui.cabecalho("Ações US — Ranking",
             "Indicadores do S&P 500 e ranking ponderado · fonte: yfinance")

if not acoes.tem_ranking_us():
    st.error("Sem dados de ranking US. Rode:\n\n"
             "`python financeiro/ranking_us.py --banco --sem-excel`\n\n"
             "e depois `python site/atualizar_dados.py`.")
    st.stop()


@st.cache_data(show_spinner="Carregando ranking US...")
def carregar():
    return acoes.ranking_acoes_us(renomear=True)


base = carregar()
ui.selo_atualizacao(acoes.ranking_us_atualizado_em(),
                    extra=f"{len(base)} ações (S&P 500)")


def fmt_dolar(v):
    if v is None or pd.isna(v):
        return "–"
    def _us(x, suf):
        return f"US$ {x:,.2f} {suf}"
    if abs(v) >= 1e12:
        return _us(v / 1e12, "tri")
    if abs(v) >= 1e9:
        return _us(v / 1e9, "bi")
    if abs(v) >= 1e6:
        return _us(v / 1e6, "mi")
    return f"US$ {v:,.2f}"


COLS_MOEDA = ["Valor de Mercado (US$)", "Receita (US$)", "Lucro Líquido (US$)",
              "EBITDA (US$)", "Caixa (US$)", "Dívida Total (US$)",
              "Free Cash Flow (US$)", "Fluxo Caixa Oper. (US$)"]
COLS_PCT = ["DY 12m (%)", "DY médio 5a (%)", "ROE (%)", "ROA (%)",
            "Margem Líquida (%)", "Margem Bruta (%)", "Margem Operacional (%)",
            "Margem EBITDA (%)", "Cresc. Receita (%)", "Cresc. Lucro (%)",
            "Payout (%)", "Variação 12m (%)", "Upside p/ alvo (%)", "% Institucional"]
COLS_MULT = ["P/L", "P/L proj.", "P/VP", "Dívida / PL", "Beta", "EV/EBITDA",
             "EV/Receita", "P/S", "PEG", "Liquidez Corrente", "Liquidez Seca"]
COLS_PRECO = ["Preço (US$)", "LPA (US$)", "VPA (US$)", "Receita/Ação (US$)",
              "Preço-alvo (US$)"]


def column_config(df):
    cfg = {}
    for c in df.columns:
        if c in COLS_PCT:
            cfg[c] = st.column_config.NumberColumn(format="%.2f%%")
        elif c in COLS_MULT:
            cfg[c] = st.column_config.NumberColumn(format="%.2f")
        elif c in COLS_PRECO:
            cfg[c] = st.column_config.NumberColumn(format="US$ %.2f")
    return cfg


tab_rank, tab_sim, tab_setor = st.tabs(
    ["🏆 Ranking US", "🎯 Simulador de ranking", "🏭 Médias por setor"])

# ===================== ABA RANKING =====================
with tab_rank:
    st.markdown("Tabela completa do S&P 500. Filtre por setor e indicadores; "
                "clique no cabeçalho de qualquer coluna para ordenar.")
    setores = sorted(base["Setor"].dropna().unique())
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        sel_setores = st.multiselect("Setores", setores, default=[])
    with f2:
        pl_max = st.number_input("P/L máx (0 = ignora)", value=0.0, step=1.0)
    with f3:
        roe_min = st.number_input("ROE mín % (0 = ignora)", value=0.0, step=1.0)
    busca = st.text_input("Buscar ticker ou empresa", "")

    df = base.copy()
    if sel_setores:
        df = df[df["Setor"].isin(sel_setores)]
    if pl_max > 0:
        df = df[(df["P/L"] > 0) & (df["P/L"] <= pl_max)]
    if roe_min > 0:
        df = df[df["ROE (%)"] >= roe_min]
    if busca.strip():
        q = busca.strip().upper()
        df = df[df["Ticker"].str.upper().str.contains(q)
                | df["Empresa"].str.upper().str.contains(q, na=False)]

    st.caption(f"**{len(df)}** ações.")
    mostra = df.drop(columns=[c for c in ["atualizado_em"] if c in df.columns])
    cols_moeda = [c for c in COLS_MOEDA if c in mostra.columns]
    sty = mostra.style.format({c: fmt_dolar for c in cols_moeda}, na_rep="–")
    cfg = {k: v for k, v in column_config(mostra).items() if k not in cols_moeda}
    st.dataframe(sty, use_container_width=True, hide_index=True, height=560,
                 column_config=cfg)
    st.download_button("⬇️ Baixar (CSV)",
                       mostra.to_csv(index=False).encode("utf-8-sig"),
                       "ranking_us.csv", "text/csv")

# ===================== ABA SIMULADOR =====================
with tab_sim:
    st.markdown("Defina **direção, limites e peso** de cada indicador. A nota de "
                "cada ação é normalizada **0–100** entre os limites e multiplicada "
                "pelo peso. As colunas **n.** mostram os pontos (já ponderados) que "
                "**somam a Nota Final**.")

    cfg_us = acoes.RANKING_CONFIG_PADRAO_US
    topo = st.columns([3, 1])
    topo[0].markdown("##### Configuração dos indicadores")
    if topo[1].button("↺ Restaurar padrão", key="reset_us"):
        for rotulo, _, inf, sup, peso, _ in cfg_us:
            st.session_state[f"usinf_{rotulo}"] = float(inf)
            st.session_state[f"ussup_{rotulo}"] = float(sup)
            st.session_state[f"uspeso_{rotulo}"] = int(peso)
        st.rerun()

    hdr = st.columns([2.4, 1.5, 1.1, 1.1, 1.1])
    for col, txt in zip(hdr, ["Indicador", "Direção (fixa)", "Lim. inferior",
                              "Lim. superior", "Peso %"]):
        col.markdown(f"**{txt}**")

    nova_cfg = []
    for rotulo, maior, inf, sup, peso, zera in cfg_us:
        c = st.columns([2.4, 1.5, 1.1, 1.1, 1.1])
        c[0].markdown(f"<div style='padding-top:8px'>{rotulo}</div>",
                      unsafe_allow_html=True)
        seta = "▲ maior" if maior else "▼ menor"
        c[1].markdown(f"<div style='padding-top:8px;color:#5b6677'>{seta} é melhor"
                      "</div>", unsafe_allow_html=True)
        inf_v = c[2].number_input("inf", value=float(inf), step=0.5,
                                  key=f"usinf_{rotulo}", label_visibility="collapsed")
        sup_v = c[3].number_input("sup", value=float(sup), step=0.5,
                                  key=f"ussup_{rotulo}", label_visibility="collapsed")
        peso_v = c[4].number_input("peso", value=int(peso), step=1, min_value=0,
                                   key=f"uspeso_{rotulo}", label_visibility="collapsed")
        nova_cfg.append((rotulo, maior, inf_v, sup_v, peso_v, zera))

    soma_peso = sum(c[4] for c in nova_cfg)
    if soma_peso == 0:
        st.error("Defina ao menos um peso > 0.")
    else:
        if soma_peso != 100:
            st.info(f"Soma dos pesos = **{soma_peso}** (não 100). Normalizado "
                    "automaticamente.")
        else:
            st.success("Pesos somam 100. ✓")

        rk = acoes.ranking_ponderado_us(config=nova_cfg, base=base)
        n_top = st.slider("Quantas mostrar", 10, len(rk), 30, step=10, key="us_ntop")
        st.markdown("##### 🏆 Ranking final (S&P 500)")
        st.caption("🟩 verde = perto do máximo da coluna (= peso) · 🟥 vermelho = perto de zero.")

        notas_cols = [c for c in rk.columns if c.startswith("nota ")]
        mostrar = rk.head(n_top).rename(
            columns={c: c.replace("nota ", "n. ") for c in notas_cols})
        peso_total = sum(c[4] for c in nova_cfg if c[4] > 0) or 1
        teto_col = {f"n. {rot}": (peso / peso_total) * 100
                    for rot, _, _, _, peso, _ in nova_cfg if peso > 0}
        teto_col["Nota Final"] = 100.0
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
            teto = teto_col.get(col.name, 100.0)
            return [cor_celula(v, teto) for v in col]

        fmt = {c: "{:.1f}" for c in cols_cor}
        sty = (mostrar.style.format(fmt, na_rep="–")
               .apply(grad_coluna, axis=0, subset=cols_cor))
        st.dataframe(sty, use_container_width=True, hide_index=True, height=560)
        st.download_button("⬇️ Baixar ranking (CSV)",
                           rk.to_csv(index=False).encode("utf-8-sig"),
                           "ranking_us_ponderado.csv", "text/csv", key="dl_us")

# ===================== ABA MÉDIAS POR SETOR =====================
with tab_setor:
    st.markdown("Médias de cada indicador **por setor**, ponderadas pelo **valor de "
                "mercado**. Clique numa linha para ver as ações do setor, com cor por indicador.")
    ms = acoes.medias_por_setor_us(base=base).copy()
    ms["Market Cap (US$)"] = ms["Market Cap (US$)"].map(fmt_dolar)
    sel_setor = st.dataframe(
        ms, use_container_width=True, hide_index=True, height=440,
        on_select="rerun", selection_mode="single-row", key="tbl_setor_us",
        column_config={
            "Nº Empresas": st.column_config.NumberColumn(format="%d"),
            **{c: st.column_config.NumberColumn(format="%.2f")
               for c in ["P/L", "P/VP", "Dívida / PL"]},
            **{c: st.column_config.NumberColumn(format="%.2f%%")
               for c in ["DY 12m (%)", "ROE (%)", "Margem Líquida (%)",
                         "Margem Operacional (%)", "Cresc. Receita (%)",
                         "Cresc. Lucro (%)"]},
        })

    linhas_sel = sel_setor.selection.rows if sel_setor and sel_setor.selection else []
    if linhas_sel:
        setor_nome = ms.iloc[linhas_sel[0]]["Setor"]
        st.divider()
        st.markdown(f"#### 🏭 Ações de **{setor_nome}**")
        det = base[base["Setor"] == setor_nome].copy()
        cols_det = ["Ticker", "Empresa", "Valor de Mercado (US$)", "P/L", "P/VP",
                    "DY 12m (%)", "ROE (%)", "Margem Líquida (%)",
                    "Margem Operacional (%)", "Dívida / PL", "Cresc. Receita (%)",
                    "Cresc. Lucro (%)"]
        cols_det = [c for c in cols_det if c in det.columns]
        det = det[cols_det].sort_values("Valor de Mercado (US$)", ascending=False)

        MAIOR_MELHOR = {
            "DY 12m (%)": True, "ROE (%)": True, "Margem Líquida (%)": True,
            "Margem Operacional (%)": True, "Cresc. Receita (%)": True,
            "Cresc. Lucro (%)": True, "P/L": False, "P/VP": False, "Dívida / PL": False,
        }

        def grad_indicador(col):
            vals = pd.to_numeric(col, errors="coerce")
            vmin, vmax = vals.min(), vals.max()
            out = []
            for v in vals:
                if pd.isna(v) or vmax == vmin:
                    out.append("")
                    continue
                r = (v - vmin) / (vmax - vmin)
                if not MAIOR_MELHOR.get(col.name, True):
                    r = 1 - r
                rr = int(0xF8 + (0xD4 - 0xF8) * r)
                gg = int(0xD7 + (0xED - 0xD7) * r)
                bb = int(0xDA + (0xDA - 0xDA) * r)
                out.append(f"background-color:#{rr:02X}{gg:02X}{bb:02X};color:#333")
            return out

        cols_color = [c for c in MAIOR_MELHOR if c in det.columns]
        sty_det = (det.style
                   .format({"Valor de Mercado (US$)": fmt_dolar}, na_rep="–")
                   .format({c: "{:.2f}" for c in ["P/L", "P/VP", "Dívida / PL"]
                            if c in det.columns}, na_rep="–")
                   .format({c: "{:.2f}%" for c in
                            ["DY 12m (%)", "ROE (%)", "Margem Líquida (%)",
                             "Margem Operacional (%)", "Cresc. Receita (%)",
                             "Cresc. Lucro (%)"] if c in det.columns}, na_rep="–")
                   .apply(grad_indicador, axis=0, subset=cols_color))
        st.dataframe(sty_det, use_container_width=True, hide_index=True,
                     height=min(46 + 35 * len(det), 600))
        st.caption("🟩 verde = melhor do setor · 🟥 pior. P/L, P/VP e Dívida/PL: "
                   "**menor** é melhor (cor invertida).")
