"""
ui.py — design system do site (tokens CSS, tipografia, helpers de estilo).

Centraliza TODO o visual num só lugar. As páginas chamam `ui.aplicar_tema()`
logo após o set_page_config. Cores vivem em variáveis CSS (:root) — nada de
cor solta espalhada pelo código.

Tema claro por padrão; o escuro é ativado pela classe .dark no <body> (o
seletor próprio do app cuida disso) ou pelo tema nativo do Streamlit.
"""
import streamlit as st

# Paleta — fonte única da verdade (espelha as variáveis CSS abaixo)
MARCA = "#0f9d6e"
POSITIVO = "#0f9d6e"
NEGATIVO = "#e23b4e"
ATENCAO = "#f5a623"

# acentos harmônicos p/ gráficos (marca + complementares)
PALETA_GRAFICO = ["#0f9d6e", "#2f6fed", "#f5a623", "#9b5de5",
                  "#e23b4e", "#13b6c4", "#7cb342", "#ec6cb9"]

# Paletas literais por tema (também usadas pelo AgGrid e pelo gráfico)
TEMA_CLARO = {
    "bg": "#f5f7fa", "surface": "#ffffff", "surface_2": "#fafbfc",
    "text": "#1a2233", "text_2": "#5b6677", "border": "#e6eaf0",
    "shadow": "0 1px 3px rgba(16,24,40,.06), 0 1px 2px rgba(16,24,40,.04)",
}
TEMA_ESCURO = {
    "bg": "#0e1420", "surface": "#161d2b", "surface_2": "#1b2433",
    "text": "#e7ecf3", "text_2": "#98a4b6", "border": "#243044",
    "shadow": "0 1px 3px rgba(0,0,0,.35), 0 1px 2px rgba(0,0,0,.25)",
}


def _css(t):
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg: %(bg)s; --surface: %(surface)s; --surface-2: %(surface_2)s;
  --text: %(text)s; --text-2: %(text_2)s; --border: %(border)s;
  --brand: #0f9d6e; --brand-700: #0c8059;
  --positive: #0f9d6e; --negative: #e23b4e; --warning: #f5a623;
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s6:24px; --s8:32px;
  --radius-card:12px; --radius-ctrl:8px;
  --shadow-card: %(shadow)s;
}

/* ---------- base ---------- */
html, body, [class*="css"], .stApp, button, input, select, textarea {
  font-family: 'Inter', -apple-system, system-ui, sans-serif;
}
.stApp { background: var(--bg); color: var(--text); }
/* números sempre tabulares e alinhados */
[data-testid="stMetricValue"], .num, table td, .ag-cell {
  font-variant-numeric: tabular-nums;
}

/* ---------- títulos ---------- */
h1 { font-weight: 700 !important; letter-spacing: -.01em; color: var(--text); }
h2, h3 { font-weight: 600 !important; color: var(--text); }
.app-sub { color: var(--text-2); font-size: .95rem; margin-top: -.4rem; }

/* ---------- abas estilo Status Invest ---------- */
.stTabs [data-baseweb="tab-list"] {
  gap: var(--s6);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 50;
  background: var(--bg);
}
.stTabs [data-baseweb="tab"] {
  padding: var(--s3) 0; font-weight: 500; color: var(--text-2);
  background: transparent; border: none;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text); }
.stTabs [aria-selected="true"] {
  color: var(--brand) !important; font-weight: 600;
  border-bottom: 2px solid var(--brand);
}

/* ---------- cards ---------- */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-card); box-shadow: var(--shadow-card);
  padding: var(--s4); margin-bottom: var(--s4);
}
.card-head {
  display:flex; align-items:center; justify-content:space-between;
  margin-bottom: var(--s3);
}
.card-title { font-weight: 600; color: var(--text); font-size: 1rem; }
.card-sub { color: var(--text-2); font-size: .8rem; font-weight: 500; }

/* ---------- métricas (cabeçalho de cotação) ---------- */
[data-testid="stMetric"] {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-ctrl); padding: var(--s3) var(--s4);
  box-shadow: var(--shadow-card);
}
[data-testid="stMetricLabel"] { color: var(--text-2); }

/* ---------- controles ---------- */
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {
  border-radius: var(--radius-ctrl) !important;
  border-color: var(--border) !important;
}
.stSelectbox div[data-baseweb="select"] > div:focus-within,
.stMultiSelect div[data-baseweb="select"] > div:focus-within {
  border-color: var(--brand) !important;
  box-shadow: 0 0 0 2px rgba(15,157,110,.18) !important;
}
/* tags do multiselect viram pills na cor de marca */
.stMultiSelect [data-baseweb="tag"] {
  background: rgba(15,157,110,.12) !important; color: var(--brand) !important;
  border-radius: 999px !important; font-weight: 500;
}
/* slider / toggle na cor de marca */
.stSlider [data-baseweb="slider"] [role="slider"] { background: var(--brand) !important; }
.stSlider [data-baseweb="slider"] div[style*="background"] { background: var(--brand) !important; }
[data-testid="stWidgetLabel"] p { color: var(--text-2); font-weight: 500; }
div[data-baseweb="checkbox"][aria-checked="true"] > div { background: var(--brand) !important; }

/* botão secundário (download) bem acabado */
.stDownloadButton button, .stButton button {
  border-radius: var(--radius-ctrl); border: 1px solid var(--border);
  color: var(--text); background: var(--surface); font-weight: 500;
  transition: all .16s ease;
}
.stDownloadButton button:hover, .stButton button:hover {
  border-color: var(--brand); color: var(--brand);
}

/* divisores discretos */
hr { border-color: var(--border) !important; }

/* chrome do Streamlit segue o tema escolhido (toggle do app) */
[data-testid="stHeader"] { background: var(--bg); }
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] * { color: var(--text); }
.stApp, .main, .block-container { background: var(--bg); color: var(--text); }
p, span, label, li { color: var(--text); }

/* transições suaves globais em hover/foco */
button, .stTabs [data-baseweb="tab"], [data-testid="stMetric"] {
  transition: all .16s ease;
}
</style>
""" % t


def aplicar_tema(escuro=False):
    """Injeta o design system no tema escolhido. Chamar após set_page_config."""
    st.markdown(_css(TEMA_ESCURO if escuro else TEMA_CLARO), unsafe_allow_html=True)


def cabecalho(titulo, subtitulo=None):
    """H1 sem emoji + subtítulo discreto, na tipografia do design system."""
    st.markdown(f"<h1>{titulo}</h1>", unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f"<div class='app-sub'>{subtitulo}</div>", unsafe_allow_html=True)
    st.write("")


def fmt_ptbr(valor, casas=0):
    """Número no formato pt-BR: milhar com ponto, decimal com vírgula."""
    if valor is None:
        return "–"
    s = f"{valor:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Tabela de demonstração com AgGrid: 1ª coluna fixa, checkbox embutido,
# zebra, pt-BR, cor +/−, subtotais em negrito.
# ---------------------------------------------------------------------------
# contas tratadas como subtotal/resultado (negrito + fundo de destaque)
_SUBTOTAIS = {
    "Lucro Bruto", "EBIT (result. antes do fin.)", "EBT (antes dos tributos)",
    "Lucro Líquido", "TOTAL ATIVO CIRCULANTE", "TOTAL ATIVO NÃO CIRC.",
    "TOTAL DO ATIVO", "TOTAL PASSIVO CIRCULANTE", "TOTAL PASSIVO NÃO CIRC.",
    "TOTAL PATRIMÔNIO LÍQUIDO", "FLUXO CAIXA OPERACIONAL",
    "FLUXO CAIXA INVESTIMENTOS", "FLUXO CAIXA FINANCIAMENTOS",
}


def tabela_demonstracao(df, casas, preselecao, key, escuro=False, altura=None):
    """Renderiza uma demonstração (contas×trimestres) em AgGrid e devolve as
    contas (índice) marcadas pelo checkbox.

    df         : DataFrame contas(linhas) × períodos(colunas), já na escala certa.
    casas      : nº de casas decimais (0/1/2 conforme a escala).
    preselecao : lista de contas que começam marcadas.
    escuro     : True aplica a paleta escura (cores LITERAIS, pois o AgGrid roda
                 num iframe onde as variáveis CSS do app não chegam).
    """
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

    t = TEMA_ESCURO if escuro else TEMA_CLARO
    sub_bg = "rgba(15,157,110,.16)" if escuro else "rgba(15,157,110,.07)"
    neg = "#ff6b7a" if escuro else "#e23b4e"

    dados = df.reset_index()
    dados.columns = ["Conta"] + list(df.columns)

    fmt_js = JsCode(f"""
        function(p) {{
            if (p.value === null || p.value === undefined || isNaN(p.value)) return '–';
            return p.value.toLocaleString('pt-BR', {{
                minimumFractionDigits: {casas}, maximumFractionDigits: {casas} }});
        }}""")
    cor_js = JsCode("""
        function(p) {
            var sub = %s;
            var base = {'text-align':'right','font-variant-numeric':'tabular-nums'};
            if (p.value < 0) base['color'] = '%s';
            if (sub.indexOf(p.data.Conta) >= 0) {
                base['font-weight'] = '700';
                base['background-color'] = '%s';
            }
            return base;
        }""" % (list(_SUBTOTAIS), neg, sub_bg))
    conta_style = JsCode("""
        function(p) {
            var sub = %s;
            var base = {'font-weight':'500'};
            if (sub.indexOf(p.value) >= 0) {
                base['font-weight'] = '700';
                base['background-color'] = '%s';
            }
            return base;
        }""" % (list(_SUBTOTAIS), sub_bg))

    gb = GridOptionsBuilder.from_dataframe(dados)
    gb.configure_default_column(resizable=False, sortable=False, filterable=False,
                                suppressMovable=True, suppressSizeToFit=True,
                                minWidth=92)
    gb.configure_selection("multiple", use_checkbox=True,
                           pre_selected_rows=[i for i, c in enumerate(dados["Conta"])
                                              if c in (preselecao or [])])
    gb.configure_column("Conta", pinned="left", checkboxSelection=True,
                        headerCheckboxSelection=False, width=230, minWidth=200,
                        cellStyle=conta_style)
    for c in df.columns:
        gb.configure_column(c, type=["numericColumn"], width=98, minWidth=92,
                            valueFormatter=fmt_js, cellStyle=cor_js)
    opts = gb.build()
    opts["rowHeight"] = 34
    opts["headerHeight"] = 38
    # NÃO espremer colunas para caber — usar scroll horizontal (preserva legibilidade)
    opts["suppressColumnVirtualisation"] = True
    opts["alwaysShowHorizontalScroll"] = True

    # dark do AgGrid: sobrescreve as variáveis do tema alpine com !important
    # (o tema 'alpine-dark' não existe nesta versão; força-se via CSS).
    css = {
        ".ag-theme-alpine": {
            "--ag-background-color": t["surface"] + " !important",
            "--ag-odd-row-background-color": t["surface_2"] + " !important",
            "--ag-header-background-color": t["surface"] + " !important",
            "--ag-border-color": t["border"] + " !important",
            "--ag-row-border-color": t["border"] + " !important",
            "--ag-foreground-color": t["text"] + " !important",
            "--ag-data-color": t["text"] + " !important",
            "--ag-header-foreground-color": t["text_2"] + " !important",
            "--ag-row-hover-color": "rgba(15,157,110,.12) !important",
            "--ag-selected-row-background-color": "rgba(15,157,110,.16) !important",
            "--ag-font-family": "Inter, sans-serif !important",
            "--ag-checkbox-checked-color": "#0f9d6e !important",
            "--ag-font-size": "13px !important",
            "border-radius": "12px", "overflow": "hidden",
        },
        ".ag-theme-alpine .ag-header": {
            "background-color": t["surface"] + " !important",
            "border-bottom": "1px solid " + t["border"] + " !important"},
        ".ag-theme-alpine .ag-row": {"background-color": t["surface"] + " !important"},
        ".ag-theme-alpine .ag-row-odd": {
            "background-color": t["surface_2"] + " !important"},
        ".ag-theme-alpine .ag-cell": {"color": t["text"] + " !important"},
        ".ag-theme-alpine .ag-header-cell-text": {"color": t["text_2"] + " !important"},
    }
    h = altura or min(46 + 34 * len(dados), 720)
    grid = AgGrid(dados, gridOptions=opts, height=h,
                  update_mode=GridUpdateMode.SELECTION_CHANGED,
                  allow_unsafe_jscode=True, fit_columns_on_grid_load=False,
                  theme="alpine", key=key, custom_css=css)
    sel = grid.get("selected_rows")
    if sel is None or (hasattr(sel, "empty") and sel.empty):
        return list(preselecao or [])
    try:
        return list(sel["Conta"])           # DataFrame (versões novas)
    except (TypeError, KeyError):
        return [r["Conta"] for r in sel]    # list[dict] (versões antigas)
