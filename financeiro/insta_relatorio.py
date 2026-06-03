"""
insta_relatorio.py -- Gera imagens (1080x1080) para postagem no Instagram
@capitalemjogo

Slides gerados:
  1  - Capa: chamada provocativa + grafico decorativo
  2a - DRE grafico (escala log)
  2b - DRE tabela com variacoes %
  3  - Balanco (grid 2x2): PL, ROE, Divida Bruta, Divida Liquida
  4  - Fluxo de Caixa (3+2): FCO, FCI, FCF, CAPEX, FCL
  5  - Dividendos: barras empilhadas por trimestre + DY%
  6  - Ranking (2 colunas x 4): P/L, P/VP, Margem Bruta, Margem Liquida,
                                ROE, DY 2025, DY medio 5 anos, Divida Bruta/PL

Uso: python financeiro/insta_relatorio.py
"""
import sqlite3
import os
import sys
import math
import random
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")
DIR_OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "Insta")

# ── Identidade visual ───────────────────────────────────────────────────────────
COR_FUNDO     = "#0B1929"   # azul-marinho muito escuro
COR_FUNDO2    = "#0B1929"   # gráficos sem painel separado (mesmo fundo)
COR_TEXTO     = "#FFFFFF"
COR_DESTAQUE  = "#00E5C8"   # ciano/turquesa vibrante
COR_NEGATIVO  = "#FF6B6B"   # vermelho-salmão
COR_GRADE     = "#1E3A4A"   # linha separadora / gridlines
COR_SECUND    = "#A0B4C8"   # cinza-azulado
COR_AMARELO   = "#F4C542"   # amarelo-ouro
COR_AZUL      = "#5B9BD5"
COR_LARANJA   = "#E8925A"   # laranja-salmão
COR_ROXO      = "#BB8FCE"

# Sequência canônica das cores das barras (multi-séries)
CORES_SERIE = [COR_DESTAQUE, COR_AZUL, COR_AMARELO, COR_LARANJA]

# Cores por trimestre (slide 5)
COR_TRIMESTRE = {
    1: COR_DESTAQUE,
    2: COR_AZUL,
    3: COR_AMARELO,
    4: COR_LARANJA,
}

PERFIL = "@capitalemjogo"
MARCA  = "CAPITAL EM JOGO"

# 1080x1080 @ 150 DPI
FIG_SIZE = (7.2, 7.2)
FIG_DPI  = 150

# Padding interno (em fração da figura) — equivalente a ~50px em 1080
PAD_X_LEFT  = 0.046
PAD_X_RIGHT = 0.954
PAD_Y_TOP   = 0.954
PAD_Y_BOT   = 0.046

# Tipografia (geométrica sans-serif, com fallback para DejaVu Bold)
FONT_FAMILY = ["Barlow", "Poppins", "Montserrat", "DejaVu Sans"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = FONT_FAMILY
plt.rcParams["font.weight"] = "bold"
plt.rcParams["axes.unicode_minus"] = False


# ─────────────────────────────────────────────────────────────────────────────
#  Carga de dados
# ─────────────────────────────────────────────────────────────────────────────

PRIORIDADE = {"investsite": 0, "statusinvest": 1, "yfinance": 2, "manual": 3}


def carregar_empresa(ticker):
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT ticker, nome, moeda, acoes_free, acoes_total FROM empresas WHERE ticker=?",
        (ticker,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "ticker": row[0], "nome": row[1] or row[0],
        "moeda": row[2] or "BRL",
        "acoes_free": row[3] or 0,
        "acoes_total": row[4] or 0,
    }


def carregar_preco_atual(ticker):
    """Retorna (preco, data) ou (None, None)."""
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT preco, data_fechamento FROM preco_atual WHERE ticker=?", (ticker,)
    ).fetchone()
    conn.close()
    if not row:
        return None, None
    return (float(row[0]) if row[0] else None,
            row[1] if row[1] else None)


def carregar_fin(ticker, anos):
    conn = sqlite3.connect(DB)
    df = pd.read_sql(f"SELECT * FROM financeiros_anuais WHERE ticker='{ticker}'", conn)
    conn.close()
    if df.empty:
        return {a: {} for a in anos}
    df["_p"] = df["fonte"].map(lambda f: PRIORIDADE.get(f, 99))
    df = df.sort_values(["ano", "_p"])
    df_best = df.groupby("ano").first().reset_index()

    out = {}
    for ano in anos:
        sub = df_best[df_best["ano"] == ano]
        out[ano] = sub.iloc[0].to_dict() if not sub.empty else {}
    return out


def carregar_dividendos_por_trimestre(ticker, anos):
    """Retorna {ano: {trimestre: total_dividendo}} usando data_com."""
    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT data_com, valor
        FROM dividendos_pagamentos
        WHERE ticker=?
    """, (ticker,)).fetchall()
    conn.close()

    out = {a: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0} for a in anos}
    for data_com, valor in rows:
        if not data_com or len(str(data_com)) < 7:
            continue
        try:
            ano = int(str(data_com)[:4])
            mes = int(str(data_com)[5:7])
        except ValueError:
            continue
        if ano not in out:
            continue
        trimestre = (mes - 1) // 3 + 1
        out[ano][trimestre] += float(valor or 0)
    return out


def carregar_financeiros(ticker):
    """Descobre os anos disponiveis no banco e retorna (anos, fin).

    Wrapper sobre carregar_fin para o orquestrador que nao recebe anos.
    """
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT DISTINCT ano FROM financeiros_anuais WHERE ticker=? ORDER BY ano",
        (ticker,)
    ).fetchall()
    conn.close()
    anos = [int(r[0]) for r in rows if r[0] is not None]
    if not anos:
        return [], {}
    return anos, carregar_fin(ticker, anos)


def carregar_dividendos_trimestrais(ticker):
    """Wrapper sem 'anos': descobre os anos e delega."""
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT DISTINCT ano FROM financeiros_anuais WHERE ticker=? ORDER BY ano",
        (ticker,)
    ).fetchall()
    conn.close()
    anos = [int(r[0]) for r in rows if r[0] is not None]
    return carregar_dividendos_por_trimestre(ticker, anos)


def carregar_preco_medio(ticker, anos):
    """Retorna {ano: preco_medio} a partir de precos_anuais."""
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT ano, preco_medio FROM precos_anuais WHERE ticker=? AND ano IN ({})".format(
            ",".join("?" * len(anos))
        ),
        (ticker, *anos)
    ).fetchall()
    conn.close()
    return {int(a): float(p) for a, p in rows if p is not None}


def _val(d, campo):
    v = d.get(campo) if d else None
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return float(v)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers de formatacao
# ─────────────────────────────────────────────────────────────────────────────

def simbolo_moeda(moeda):
    return "R$" if moeda == "BRL" else "$"


def fmt_grande(valor, moeda="BRL"):
    if valor is None:
        return "-"
    s = simbolo_moeda(moeda)
    abs_v = abs(valor)
    sinal = "-" if valor < 0 else ""
    if abs_v >= 1e9:
        return f"{sinal}{s} {abs_v/1e9:.1f} bi".replace(".", ",")
    if abs_v >= 1e6:
        return f"{sinal}{s} {abs_v/1e6:.0f} mi"
    if abs_v >= 1e3:
        return f"{sinal}{s} {abs_v/1e3:.0f} mil"
    return f"{sinal}{s} {abs_v:.0f}"


def fmt_pct(valor, casas=1):
    if valor is None:
        return "-"
    return f"{valor*100:.{casas}f}%".replace(".", ",")


def fmt_pct_var(valor, casas=1):
    """Formata variacao com sinal explicito (+12,3% / -5,4%)."""
    if valor is None:
        return "-"
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{valor*100:.{casas}f}%".replace(".", ",")


def fmt_num(valor, casas=2):
    if valor is None:
        return "-"
    return f"{valor:.{casas}f}".replace(".", ",")


def variacao(novo, antigo):
    if novo is None or antigo is None or antigo == 0:
        return None
    return (novo - antigo) / abs(antigo)


# ─────────────────────────────────────────────────────────────────────────────
#  Setup da figura
# ─────────────────────────────────────────────────────────────────────────────

def _novo_fig():
    return plt.figure(figsize=FIG_SIZE, dpi=FIG_DPI, facecolor=COR_FUNDO)


def _moldura_padrao(fig, ticker, com_linha=True):
    # Cabeçalho
    fig.text(PAD_X_LEFT, 0.962, MARCA,
             fontsize=10, fontweight="bold", color=COR_DESTAQUE,
             va="center")
    fig.text(PAD_X_RIGHT, 0.962, ticker,
             fontsize=20, fontweight="bold", color=COR_TEXTO,
             ha="right", va="center")
    if com_linha:
        fig.add_artist(plt.Line2D([PAD_X_LEFT, PAD_X_RIGHT], [0.935, 0.935],
                                  color=COR_GRADE, linewidth=0.8))
    # Rodapé
    fig.add_artist(plt.Line2D([PAD_X_LEFT, PAD_X_RIGHT], [0.075, 0.075],
                              color=COR_GRADE, linewidth=0.8))
    fig.text(PAD_X_LEFT, 0.045, PERFIL,
             fontsize=9, color=COR_SECUND, va="center", fontweight="normal")
    fig.text(PAD_X_RIGHT, 0.045,
             datetime.now().strftime("%m/%Y"),
             fontsize=9, color=COR_SECUND, ha="right", va="center",
             fontweight="normal")


def _salvar(fig, caminho):
    fig.savefig(caminho, dpi=FIG_DPI, facecolor=COR_FUNDO,
                bbox_inches=None, pad_inches=0)
    plt.close(fig)


def _estilizar_eixos(ax):
    """Remove frame, esconde tick marks, aplica gridlines sutis."""
    ax.set_facecolor(COR_FUNDO)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="x", colors=COR_SECUND, labelsize=9,
                   length=0, pad=4)
    ax.tick_params(axis="y", colors=COR_SECUND, labelsize=8,
                   length=0, pad=4)
    ax.grid(axis="y", color=COR_GRADE, linewidth=0.5, alpha=0.9)
    ax.set_axisbelow(True)


def _grafico_barras(ax, anos, valores, titulo, moeda, cor=None, log=False):
    cor = cor or COR_DESTAQUE
    ax.set_title(titulo, color=COR_TEXTO, fontsize=12, fontweight="bold",
                 pad=10, loc="left")
    _estilizar_eixos(ax)

    valores_plot = [v if v is not None else 0 for v in valores]
    x = np.arange(len(anos))
    bars = ax.bar(x, valores_plot,
                  color=cor, edgecolor="none", width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([str(a) for a in anos])

    if log:
        ax.set_yscale("symlog")

    for bar, val in zip(bars, valores):
        if val is None:
            continue
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2,
                h,
                fmt_grande(val, moeda),
                ha="center",
                va="bottom" if h >= 0 else "top",
                color=COR_TEXTO,
                fontsize=8, fontweight="bold")

    if not log:
        ymax = max(valores_plot + [0])
        ymin = min(valores_plot + [0])
        if ymax > 0:
            ax.set_ylim(top=ymax * 1.22)
        if ymin < 0:
            ax.set_ylim(bottom=ymin * 1.22)


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 1 - Capa provocativa com grafico decorativo
# ─────────────────────────────────────────────────────────────────────────────

def _grafico_decorativo(fig):
    """Linhas decorativas no fundo: ciano subindo + vermelha caindo (sobrepostas)."""
    ax = fig.add_axes([0.0, 0.10, 1.0, 0.35], frameon=False)
    ax.set_facecolor((0, 0, 0, 0))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    random.seed(42)
    n = 80
    x = np.linspace(0, 1, n)

    # Linha ciano subindo (mercado/altas)
    base_up = np.linspace(0.15, 0.85, n)
    ruido_up = np.array([random.uniform(-0.05, 0.05) for _ in range(n)])
    y_up = base_up + ruido_up
    ax.plot(x, y_up, color=COR_DESTAQUE, linewidth=2.0, alpha=0.55)
    ax.fill_between(x, y_up, 0, color=COR_DESTAQUE, alpha=0.08)

    # Linha vermelha caindo até a metade (quedas), sobreposta
    random.seed(7)
    base_dn = np.linspace(0.78, 0.20, n)
    ruido_dn = np.array([random.uniform(-0.05, 0.05) for _ in range(n)])
    y_dn = base_dn + ruido_dn
    ax.plot(x, y_dn, color=COR_NEGATIVO, linewidth=2.0, alpha=0.55)
    ax.fill_between(x, y_dn, 0, color=COR_NEGATIVO, alpha=0.06)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def gerar_capa(ticker, empresa, anos, pasta):
    fig = _novo_fig()
    _moldura_padrao(fig, ticker, com_linha=True)

    _grafico_decorativo(fig)

    nome = empresa["nome"]
    nome_curto = nome if len(nome) <= 28 else nome[:28] + "..."

    # "COMPRA OU VENDE?" — destaque principal
    fig.text(0.5, 0.835, "COMPRA",
             fontsize=38, fontweight="bold", color=COR_DESTAQUE,
             ha="center", va="center")
    fig.text(0.5, 0.775, "OU VENDE?",
             fontsize=38, fontweight="bold", color=COR_AMARELO,
             ha="center", va="center")

    # Linha separadora curta
    fig.add_artist(plt.Line2D([0.30, 0.70], [0.725, 0.725],
                              color=COR_GRADE, linewidth=1.5))

    # Nome da empresa — destaque alto para leitura no preview do feed
    nome_fontsize = 34 if len(nome_curto) <= 14 else (28 if len(nome_curto) <= 22 else 22)
    fig.text(0.5, 0.665, nome_curto.upper(),
             fontsize=nome_fontsize, fontweight="bold", color=COR_TEXTO,
             ha="center", va="center")

    fig.text(0.5, 0.612, f"Comparativo {anos[0]} – {anos[-1]}",
             fontsize=13, color=COR_DESTAQUE, fontweight="bold",
             ha="center", va="center")

    # Sequencia de slides
    fig.add_artist(plt.Line2D([0.30, 0.70], [0.600, 0.600],
                              color=COR_GRADE, linewidth=1.0))
    fig.text(0.5, 0.568,
             "DRE  •  BALANCO  •  FLUXO  •  DIVIDENDOS  •  RANKING  •  INDICADORES",
             fontsize=9, color=COR_SECUND, ha="center", va="center", fontweight="bold")

    fig.text(0.5, 0.18, "arraste para ver os numeros",
             fontsize=11, color=COR_SECUND, ha="center", fontweight="bold")

    _salvar(fig, os.path.join(pasta, "1_capa.png"))


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 2A - DRE: cards com número grande + sparkline (variação A)
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_short_dre(valor):
    """Label compacto para sparkline: '38,4bi' ou '769mi'."""
    if valor is None:
        return "-"
    abs_v = abs(valor)
    sinal = "-" if valor < 0 else ""
    if abs_v >= 1e9:
        return f"{sinal}{abs_v/1e9:.1f}bi".replace(".", ",")
    if abs_v >= 1e6:
        return f"{sinal}{abs_v/1e6:.0f}mi"
    return f"{sinal}{abs_v/1e3:.0f}k"


def gerar_dre_grafico(ticker, empresa, anos, fin, pasta):
    from matplotlib.patches import Rectangle as _Rect

    fig = _novo_fig()
    _moldura_padrao(fig, ticker)

    moeda    = empresa["moeda"]
    COR_CARD = "#122338"

    receita = [_val(fin[a], "receita_liquida") for a in anos]
    lbruto  = [_val(fin[a], "lucro_bruto")     for a in anos]
    llik    = [_val(fin[a], "lucro_liquido")   for a in anos]

    series = [
        ("RECEITA LIQUIDA", receita, COR_DESTAQUE),
        ("LUCRO BRUTO",     lbruto,  COR_AZUL),
        ("LUCRO LIQUIDO",   llik,    COR_AMARELO),
    ]

    # ── Constantes de layout ──────────────────────────────────────────────
    Y_BOT  = 0.092
    Y_TOP  = 0.818
    GAP    = 0.014
    card_h = (Y_TOP - Y_BOT - 2 * GAP) / 3
    card_w = PAD_X_RIGHT - PAD_X_LEFT

    card_bottoms = [
        Y_BOT + 2 * (card_h + GAP),
        Y_BOT +     (card_h + GAP),
        Y_BOT,
    ]

    SP_FRAC = 0.62          # divisor texto/sparkline (0..1)
    SP_X0   = SP_FRAC + 0.04
    SP_X1   = 0.97
    SP_Y0   = 0.16          # baseline da sparkline
    SP_Y1   = 0.80          # topo da sparkline

    # Título do slide
    fig.text(PAD_X_LEFT, 0.880, "DEMONSTRACAO DE RESULTADO",
             fontsize=18, fontweight="bold", color=COR_TEXTO, va="center")
    fig.text(PAD_X_LEFT, 0.845,
             f"Receita Liquida  •  Lucro Bruto  •  Lucro Liquido  |  {anos[0]} - {anos[-1]}",
             fontsize=10, color=COR_SECUND, va="center", fontweight="normal")

    for (nome, dados, cor), bot in zip(series, card_bottoms):

        # ── Métricas do card ──────────────────────────────────────────────
        val_fim = next((v for v in reversed(dados) if v is not None), None)
        val_ini = next((v for v in dados           if v is not None), None)
        val_pen = next((v for v in reversed(dados[:-1]) if v is not None), None)
        var_tot = variacao(val_fim, val_ini)
        var_yoy = variacao(val_fim, val_pen)
        cor_tot = COR_DESTAQUE if (var_tot or 0) >= 0 else COR_NEGATIVO
        cor_yoy = COR_DESTAQUE if (var_yoy or 0) >= 0 else COR_NEGATIVO

        # ── Axes único por card (coords normalizadas 0..1) ────────────────
        ax = fig.add_axes([PAD_X_LEFT, bot, card_w, card_h])
        ax.set_facecolor(COR_CARD)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.autoscale(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])

        # Borda do card
        ax.add_patch(_Rect(
            (0.005, 0.02), 0.990, 0.960,
            facecolor="none", edgecolor=COR_GRADE, linewidth=1.2,
            clip_on=False, zorder=1
        ))

        # ── Texto lado esquerdo ───────────────────────────────────────────
        ax.text(0.04, 0.87, nome,
                color=cor, fontsize=11, fontweight="bold", va="center")
        ax.text(0.04, 0.65, fmt_grande(val_fim, moeda),
                color=COR_TEXTO, fontsize=22, fontweight="bold", va="center")
        ax.plot([0.04, SP_FRAC - 0.03], [0.37, 0.37],
                color=COR_GRADE, linewidth=0.8)
        ax.text(0.05, 0.28, f"{anos[0]}-{anos[-1]}",
                color=COR_SECUND, fontsize=8, va="center", fontweight="normal")
        ax.text(0.05, 0.12, fmt_pct_var(var_tot),
                color=cor_tot, fontsize=14, fontweight="bold", va="center")
        ax.plot([0.31, 0.31], [0.08, 0.37],
                color=COR_GRADE, linewidth=0.8)
        ax.text(0.33, 0.28, f"{anos[-2]}-{anos[-1]}",
                color=COR_SECUND, fontsize=8, va="center", fontweight="normal")
        ax.text(0.33, 0.12, fmt_pct_var(var_yoy),
                color=cor_yoy, fontsize=14, fontweight="bold", va="center")
        ax.plot([SP_FRAC, SP_FRAC], [0.05, 0.95],
                color=COR_GRADE, linewidth=0.8)

        # ── Sparkline lado direito ────────────────────────────────────────
        validos = [d for d in dados if d is not None]
        if not validos:
            ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            continue

        vmin   = min(validos)
        vmax   = max(validos)
        spread = (vmax - vmin) if vmax != vmin else (abs(vmax) * 0.5 or 1.0)

        xs  = np.linspace(SP_X0, SP_X1, len(anos))
        ys  = np.array([
            SP_Y0 + (d - vmin) / spread * (SP_Y1 - SP_Y0) if d is not None else float("nan")
            for d in dados
        ], dtype=float)

        # Linha de separação + anos
        ax.plot([SP_FRAC + 0.01, 0.99], [0.135, 0.135],
                color=COR_GRADE, linewidth=0.5)
        for xp, an in zip(xs, anos):
            ax.text(xp, 0.065, str(an),
                    color=COR_SECUND, fontsize=6.5,
                    ha="center", va="center", fontweight="normal")

        # Fill + linha + pontos
        mask = ~np.isnan(ys)
        if mask.any():
            ax.fill_between(xs, ys, SP_Y0, where=mask, alpha=0.18, color=cor)
        ax.plot(xs, ys, color=cor, linewidth=2.2, zorder=3)
        ax.scatter(xs[:-1], ys[:-1], color=cor, s=18, zorder=4, linewidths=0)
        ax.scatter([xs[-1]], [ys[-1]], color=cor, s=45,
                   zorder=5, edgecolors=COR_TEXTO, linewidths=0.9)

        # Labels de valor (alternando acima/abaixo)
        pad_y = (SP_Y1 - SP_Y0) * 0.12
        lados = []
        for i, v in enumerate(dados):
            if i == 0:
                lados.append("above")
            elif (v is not None and dados[i-1] is not None
                  and abs(v - dados[i-1]) / spread < 0.15):
                lados.append("below" if lados[-1] == "above" else "above")
            else:
                lados.append("above")

        for xp, yp, v, lado in zip(xs, ys, dados, lados):
            if v is None or math.isnan(yp):
                continue
            ly = min(yp + pad_y, 0.95) if lado == "above" else max(yp - pad_y, SP_Y0 + 0.02)
            ax.text(xp, ly, _fmt_short_dre(v),
                    color=COR_TEXTO, fontsize=7, fontweight="bold",
                    ha="center", va=("bottom" if lado == "above" else "top"),
                    zorder=6)

        # Garantir limites ao final
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    _salvar(fig, os.path.join(pasta, "2a_dre_grafico.png"))


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 2B - DRE tabela com variacoes %
# ─────────────────────────────────────────────────────────────────────────────

def _card_arredondado(fig, x, y, largura, altura):
    """Card sutil com canto arredondado, em coords da figura."""
    card = FancyBboxPatch(
        (x, y), largura, altura,
        boxstyle="round,pad=0,rounding_size=0.012",
        facecolor=COR_FUNDO, edgecolor=COR_GRADE, linewidth=0.8,
        transform=fig.transFigure, mutation_aspect=1
    )
    fig.add_artist(card)


def gerar_dre_tabela(ticker, empresa, anos, fin, pasta):
    fig = _novo_fig()
    _moldura_padrao(fig, ticker)

    fig.text(PAD_X_LEFT, 0.88, "CRESCIMENTO DRE",
             fontsize=18, fontweight="bold", color=COR_TEXTO, va="center")
    fig.text(PAD_X_LEFT, 0.845,
             f"Variação {anos[0]} – {anos[-1]}  e  {anos[-2]} – {anos[-1]}",
             fontsize=10, color=COR_SECUND, va="center", fontweight="normal")

    campos = [
        ("RECEITA LÍQUIDA", "receita_liquida"),
        ("LUCRO BRUTO",     "lucro_bruto"),
        ("LUCRO LÍQUIDO",   "lucro_liquido"),
    ]

    y_topo = 0.78
    altura_card = 0.18
    espaco = 0.022
    x_card = PAD_X_LEFT
    largura_card = PAD_X_RIGHT - PAD_X_LEFT

    moeda = empresa["moeda"]

    for i, (label, campo) in enumerate(campos):
        y = y_topo - i * (altura_card + espaco)

        v_ini  = _val(fin[anos[0]],  campo)
        v_fim  = _val(fin[anos[-1]], campo)
        v_pen  = _val(fin[anos[-2]], campo) if len(anos) >= 2 else None

        var_total = variacao(v_fim, v_ini)
        var_yoy   = variacao(v_fim, v_pen)

        _card_arredondado(fig, x_card, y - altura_card, largura_card, altura_card)

        # Nome do campo (topo do card)
        fig.text(x_card + 0.025, y - 0.030, label,
                 fontsize=13, fontweight="bold", color=COR_DESTAQUE, va="center")

        # Valores absolutos
        fig.text(x_card + 0.025, y - 0.062,
                 f"{anos[0]}: {fmt_grande(v_ini, moeda)}   ->   {anos[-1]}: {fmt_grande(v_fim, moeda)}",
                 fontsize=10, color=COR_SECUND, va="center", fontweight="normal")

        # Variação TOTAL
        cor_t = COR_DESTAQUE if (var_total or 0) >= 0 else COR_NEGATIVO
        fig.text(x_card + 0.10, y - altura_card + 0.060,
                 f"{anos[0]} -> {anos[-1]}",
                 fontsize=9, color=COR_SECUND,
                 ha="center", va="center", fontweight="normal")
        fig.text(x_card + 0.10, y - altura_card + 0.030,
                 fmt_pct_var(var_total),
                 fontsize=22, fontweight="bold", color=cor_t,
                 ha="center", va="center")

        # Variação YoY
        cor_y = COR_DESTAQUE if (var_yoy or 0) >= 0 else COR_NEGATIVO
        fig.text(x_card + largura_card - 0.10, y - altura_card + 0.060,
                 f"{anos[-2]} -> {anos[-1]}",
                 fontsize=9, color=COR_SECUND,
                 ha="center", va="center", fontweight="normal")
        fig.text(x_card + largura_card - 0.10, y - altura_card + 0.030,
                 fmt_pct_var(var_yoy),
                 fontsize=22, fontweight="bold", color=cor_y,
                 ha="center", va="center")

        # Separador vertical entre as 2 variações
        fig.add_artist(plt.Line2D(
            [x_card + largura_card/2, x_card + largura_card/2],
            [y - altura_card + 0.020, y - altura_card + 0.085],
            color=COR_GRADE, linewidth=0.8
        ))

    _salvar(fig, os.path.join(pasta, "2b_dre_tabela.png"))


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 3 - Balanco (grid 2x2)
# ─────────────────────────────────────────────────────────────────────────────

def gerar_balanco(ticker, empresa, anos, fin, pasta):
    import math as _math
    COR_CARD = "#122338"
    from matplotlib.patches import Rectangle as _Rect

    fig = _novo_fig()
    _moldura_padrao(fig, ticker)
    moeda = empresa["moeda"]

    # --- Dados ---
    pl       = [_val(fin[a], "patrimonio_liquido") for a in anos]
    # Divida = emprestimos_cp + emprestimos_lp (sem debentures)
    div_brut = [(_val(fin[a], "emprestimos_cp") or 0) + (_val(fin[a], "emprestimos_lp") or 0)
                for a in anos]
    div_liq  = [db - (_val(fin[a], "caixa") or 0) if db else None
                for db, a in zip(div_brut, anos)]
    ll       = [_val(fin[a], "lucro_liquido")      for a in anos]
    roe      = [(ll[i] / pl[i] * 100) if (ll[i] is not None and pl[i] not in (None, 0))
                else None for i in range(len(anos))]

    # --- Titulo ---
    fig.text(PAD_X_LEFT, 0.880, "BALANCO PATRIMONIAL",
             fontsize=18, fontweight="bold", color=COR_TEXTO, va="center")
    fig.text(PAD_X_LEFT, 0.845,
             f"Patrimonio Liquido  •  ROE  •  Divida Bruta / Liquida"
             f"  |  {anos[0]}–{anos[-1]}",
             fontsize=10, color=COR_SECUND, va="center", fontweight="normal")

    # --- Geometria dos cards (identica ao DRE) ---
    Y_BOT = 0.092; Y_TOP = 0.818; GAP = 0.014
    card_h = (Y_TOP - Y_BOT - 2 * GAP) / 3
    card_w = PAD_X_RIGHT - PAD_X_LEFT
    card_bottoms = [Y_BOT + 2*(card_h+GAP), Y_BOT + (card_h+GAP), Y_BOT]

    # Posicoes da sparkline (lado direito do card)
    SP_FRAC = 0.62
    SP_X0   = SP_FRAC + 0.04
    SP_X1   = 0.97
    SP_Y0   = 0.22   # base da sparkline (acima dos anos)
    SP_Y1   = 0.88   # topo da sparkline
    YR_Y    = 0.08   # posicao vertical dos labels de ano
    SEP_Y   = 0.16   # linha separadora anos / sparkline

    def _spark_std(ax, dados, cor, xs, is_pct=False):
        """Sparkline estilo anos_A: valores acima dos pontos."""
        validos = [d for d in dados if d is not None]
        if not validos:
            return
        vmin = min(validos); vmax = max(validos)
        spread = (vmax - vmin) if vmax != vmin else (abs(vmax) * 0.5 or 1.0)
        ys = np.array([
            SP_Y0 + (d - vmin) / spread * (SP_Y1 - SP_Y0)
            if d is not None else float("nan")
            for d in dados], dtype=float)
        mask = ~np.isnan(ys)
        if mask.any():
            ax.fill_between(xs, ys, SP_Y0, where=mask, alpha=0.18, color=cor)
        ax.plot(xs, ys, color=cor, linewidth=2.2, zorder=3)
        ax.scatter(xs[:-1], ys[:-1], color=cor, s=18, zorder=4, linewidths=0)
        ax.scatter([xs[-1]], [ys[-1]], color=cor, s=45, zorder=5,
                   edgecolors=COR_TEXTO, linewidths=0.9)
        pad_y = (SP_Y1 - SP_Y0) * 0.14
        for xp, yp, v in zip(xs, ys, dados):
            if v is None or _math.isnan(yp):
                continue
            ly = min(yp + pad_y, 0.97)
            lbl = (f"{v:.1f}%".replace(".", ",") if is_pct else _fmt_short_dre(v))
            ax.text(xp, ly, lbl, color=COR_TEXTO, fontsize=7, fontweight="bold",
                    ha="center", va="bottom", zorder=6)

    def _draw_card(ax, nome, dados, cor, is_pct=False, inverter_cor=False):
        """Card full-width com sparkline estilo anos_A."""
        ax.set_facecolor(COR_CARD)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.autoscale(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks([]); ax.set_yticks([])
        ax.add_patch(_Rect((0.005, 0.02), 0.990, 0.960,
                     facecolor="none", edgecolor=COR_GRADE, linewidth=1.2,
                     clip_on=False, zorder=1))
        val_fim = next((v for v in reversed(dados) if v is not None), None)
        val_ini = next((v for v in dados if v is not None), None)
        val_pen = next((v for v in reversed(dados[:-1]) if v is not None), None)
        var_tot = variacao(val_fim, val_ini)
        var_yoy = variacao(val_fim, val_pen)
        # inverter_cor=True: aumento é ruim (ex: dívida), redução é bom
        def _cor_var(v):
            positivo = (v or 0) >= 0
            bom = positivo if not inverter_cor else not positivo
            return COR_DESTAQUE if bom else COR_NEGATIVO
        cor_tot = _cor_var(var_tot)
        cor_yoy = _cor_var(var_yoy)
        # Titulo
        ax.text(0.04, 0.87, nome, color=cor, fontsize=11, fontweight="bold", va="center")
        # Valor grande
        if is_pct:
            big = f"{val_fim:.1f}%".replace(".", ",") if val_fim is not None else "—"
        else:
            big = fmt_grande(val_fim, moeda)
        ax.text(0.04, 0.65, big, color=COR_TEXTO, fontsize=22, fontweight="bold", va="center")
        # Linha separadora horizontal
        ax.plot([0.04, SP_FRAC - 0.03], [0.37, 0.37], color=COR_GRADE, linewidth=0.8)
        # Variacoes com seta
        ax.text(0.05, 0.28, f"{anos[0]} -> {anos[-1]}",
                color=COR_SECUND, fontsize=8, va="center")
        ax.text(0.05, 0.12, fmt_pct_var(var_tot),
                color=cor_tot, fontsize=14, fontweight="bold", va="center")
        ax.plot([0.31, 0.31], [0.08, 0.37], color=COR_GRADE, linewidth=0.8)
        ax.text(0.33, 0.28, f"{anos[-2]} -> {anos[-1]}",
                color=COR_SECUND, fontsize=8, va="center")
        ax.text(0.33, 0.12, fmt_pct_var(var_yoy),
                color=cor_yoy, fontsize=14, fontweight="bold", va="center")
        # Divisor vertical texto / sparkline
        ax.plot([SP_FRAC, SP_FRAC], [0.05, 0.95], color=COR_GRADE, linewidth=0.8)
        # Linha separadora anos
        ax.plot([SP_X0 - 0.01, SP_X1 + 0.01], [SEP_Y, SEP_Y],
                color=COR_GRADE, linewidth=0.6)
        # Labels de ano como eixo inferior
        xs = np.linspace(SP_X0, SP_X1, len(anos))
        for xp, an in zip(xs, anos):
            ax.text(xp, YR_Y, str(an), color=COR_SECUND, fontsize=6.5,
                    ha="center", va="center")
        # Sparkline
        _spark_std(ax, dados, cor, xs, is_pct=is_pct)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    def _draw_divida_card(ax):
        """Card 3: Divida Bruta (esq) + Divida Liquida (dir), mini sparklines."""
        ax.set_facecolor(COR_CARD)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.autoscale(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks([]); ax.set_yticks([])
        ax.add_patch(_Rect((0.005, 0.02), 0.990, 0.960,
                     facecolor="none", edgecolor=COR_GRADE, linewidth=1.2,
                     clip_on=False, zorder=1))
        MID = 0.50
        # Divisor vertical central
        ax.plot([MID, MID], [0.05, 0.95], color=COR_GRADE, linewidth=0.8)

        def _half(dados, cor, x0, x1, titulo):
            val_fim = next((v for v in reversed(dados) if v is not None), None)
            val_ini = next((v for v in dados if v is not None), None)
            val_pen = next((v for v in reversed(dados[:-1]) if v is not None), None)
            var_tot = variacao(val_fim, val_ini)
            var_yoy = variacao(val_fim, val_pen)
            c_tot   = COR_DESTAQUE if (var_tot or 0) >= 0 else COR_NEGATIVO
            c_yoy   = COR_DESTAQUE if (var_yoy or 0) >= 0 else COR_NEGATIVO
            # Conteudo de texto (60% da metade)
            tx = x0 + 0.02
            sp0 = x0 + (x1 - x0) * 0.58  # inicio da sparkline mini
            sp1 = x1 - 0.01
            ax.text(tx, 0.88, titulo, color=cor, fontsize=9.5,
                    fontweight="bold", va="center")
            ax.text(tx, 0.68, fmt_grande(val_fim, moeda), color=COR_TEXTO,
                    fontsize=18, fontweight="bold", va="center")
            ax.plot([tx, sp0 - 0.01], [0.40, 0.40], color=COR_GRADE, linewidth=0.8)
            ax.text(tx + 0.01, 0.30,
                    f"{anos[0]} -> {anos[-1]}",
                    color=COR_SECUND, fontsize=7, va="center")
            ax.text(tx + 0.01, 0.13, fmt_pct_var(var_tot),
                    color=c_tot, fontsize=13, fontweight="bold", va="center")
            div_x = x0 + (x1 - x0) * 0.38
            ax.plot([div_x, div_x], [0.08, 0.40], color=COR_GRADE, linewidth=0.8)
            ax.text(div_x + 0.02, 0.30,
                    f"{anos[-2]} -> {anos[-1]}",
                    color=COR_SECUND, fontsize=7, va="center")
            ax.text(div_x + 0.02, 0.13, fmt_pct_var(var_yoy),
                    color=c_yoy, fontsize=13, fontweight="bold", va="center")
            # Mini sparkline (lado direito da metade)
            ax.plot([sp0 - 0.005, sp1 + 0.005], [SEP_Y, SEP_Y],
                    color=COR_GRADE, linewidth=0.5)
            xs2 = np.linspace(sp0, sp1, len(anos))
            for xp, an in zip(xs2, anos):
                ax.text(xp, YR_Y, str(an)[-2:], color=COR_SECUND,
                        fontsize=6, ha="center", va="center")
            validos = [d for d in dados if d is not None]
            if not validos:
                return
            vmin = min(validos); vmax = max(validos)
            spread = (vmax - vmin) if vmax != vmin else (abs(vmax) * 0.5 or 1.0)
            ys2 = np.array([
                SP_Y0 + (d - vmin) / spread * (SP_Y1 - SP_Y0)
                if d is not None else float("nan")
                for d in dados], dtype=float)
            mask = ~np.isnan(ys2)
            if mask.any():
                ax.fill_between(xs2, ys2, SP_Y0, where=mask, alpha=0.18, color=cor)
            ax.plot(xs2, ys2, color=cor, linewidth=1.8, zorder=3)
            ax.scatter(xs2[:-1], ys2[:-1], color=cor, s=12, zorder=4, linewidths=0)
            ax.scatter([xs2[-1]], [ys2[-1]], color=cor, s=32, zorder=5,
                       edgecolors=COR_TEXTO, linewidths=0.7)
            # Valor do ultimo ponto
            if not _math.isnan(ys2[-1]) and dados[-1] is not None:
                ax.text(xs2[-1], min(ys2[-1] + (SP_Y1-SP_Y0)*0.16, 0.97),
                        _fmt_short_dre(dados[-1]), color=COR_TEXTO,
                        fontsize=6.5, fontweight="bold", ha="center", va="bottom", zorder=6)

        _half(div_brut, COR_AMARELO, 0.0, MID,   "DIVIDA BRUTA")
        _half(div_liq,  COR_LARANJA, MID, 1.0,   "DIVIDA LIQUIDA")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # ── Renderiza os 3 cards ──────────────────────────────────────────────────
    ax1 = fig.add_axes([PAD_X_LEFT, card_bottoms[0], card_w, card_h])
    _draw_card(ax1, "PATRIMONIO LIQUIDO", pl, COR_DESTAQUE)

    ax2 = fig.add_axes([PAD_X_LEFT, card_bottoms[1], card_w, card_h])
    _draw_card(ax2, "ROE", roe, COR_AZUL, is_pct=True)

    ax3 = fig.add_axes([PAD_X_LEFT, card_bottoms[2], card_w, card_h])
    _draw_card(ax3, "DIVIDA LIQUIDA", div_liq, COR_LARANJA, inverter_cor=True)

    _salvar(fig, os.path.join(pasta, "3_balanco.png"))


def _grafico_barras_pct(ax, anos, valores, titulo, cor=None):
    """Variante de _grafico_barras para valores em percentual."""
    cor = cor or COR_AMARELO
    ax.set_title(titulo, color=COR_TEXTO, fontsize=12, fontweight="bold",
                 pad=10, loc="left")
    _estilizar_eixos(ax)

    valores_plot = [v if v is not None else 0 for v in valores]
    x = np.arange(len(anos))
    bars = ax.bar(x, valores_plot,
                  color=cor, edgecolor="none", width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([str(a) for a in anos])

    for bar, val in zip(bars, valores):
        if val is None:
            continue
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2,
                h,
                fmt_pct_var(val, 1),
                ha="center",
                va="bottom" if h >= 0 else "top",
                color=COR_TEXTO,
                fontsize=8, fontweight="bold")

    ymax = max(valores_plot + [0])
    ymin = min(valores_plot + [0])
    if ymax > 0:
        ax.set_ylim(top=ymax * 1.25)
    if ymin < 0:
        ax.set_ylim(bottom=ymin * 1.25)


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 4 - Fluxo de Caixa (3 cards empilhados: FCO / CAPEX / FCL)
# ─────────────────────────────────────────────────────────────────────────────

def gerar_fluxo(ticker, empresa, anos, fin, pasta):
    import math as _math
    COR_CARD = "#122338"
    from matplotlib.patches import Rectangle as _Rect

    fig = _novo_fig()
    _moldura_padrao(fig, ticker)
    moeda = empresa["moeda"]

    # --- Dados ---
    fco_l   = [_val(fin[a], "fco")   for a in anos]
    # CAPEX costuma ser negativo no banco; exibimos valor absoluto
    capex_raw = [_val(fin[a], "capex") for a in anos]
    capex_l   = [abs(v) if v is not None else None for v in capex_raw]
    fcl_l   = [_val(fin[a], "fcl")   for a in anos]

    # --- Titulo ---
    fig.text(PAD_X_LEFT, 0.880, "FLUXO DE CAIXA",
             fontsize=18, fontweight="bold", color=COR_TEXTO, va="center")
    fig.text(PAD_X_LEFT, 0.845,
             f"Operacional  •  CAPEX  •  Free Cash Flow  |  {anos[0]}–{anos[-1]}",
             fontsize=10, color=COR_SECUND, va="center", fontweight="normal")

    # --- Geometria dos cards (identica ao DRE / Balanco) ---
    Y_BOT = 0.092; Y_TOP = 0.818; GAP = 0.014
    card_h = (Y_TOP - Y_BOT - 2 * GAP) / 3
    card_w = PAD_X_RIGHT - PAD_X_LEFT
    card_bottoms = [Y_BOT + 2*(card_h+GAP), Y_BOT + (card_h+GAP), Y_BOT]

    SP_FRAC = 0.62
    SP_X0   = SP_FRAC + 0.04
    SP_X1   = 0.97
    SP_Y0   = 0.22
    SP_Y1   = 0.88
    YR_Y    = 0.08
    SEP_Y   = 0.16

    def _spark_std(ax, dados, cor, xs):
        validos = [d for d in dados if d is not None]
        if not validos:
            return
        vmin = min(validos); vmax = max(validos)
        spread = (vmax - vmin) if vmax != vmin else (abs(vmax) * 0.5 or 1.0)
        ys = np.array([
            SP_Y0 + (d - vmin) / spread * (SP_Y1 - SP_Y0)
            if d is not None else float("nan")
            for d in dados], dtype=float)
        mask = ~np.isnan(ys)
        if mask.any():
            ax.fill_between(xs, ys, SP_Y0, where=mask, alpha=0.18, color=cor)
        ax.plot(xs, ys, color=cor, linewidth=2.2, zorder=3)
        ax.scatter(xs[:-1], ys[:-1], color=cor, s=18, zorder=4, linewidths=0)
        ax.scatter([xs[-1]], [ys[-1]], color=cor, s=45, zorder=5,
                   edgecolors=COR_TEXTO, linewidths=0.9)
        pad_y = (SP_Y1 - SP_Y0) * 0.14
        for xp, yp, v in zip(xs, ys, dados):
            if v is None or _math.isnan(yp):
                continue
            ly = min(yp + pad_y, 0.97)
            ax.text(xp, ly, _fmt_short_dre(v), color=COR_TEXTO,
                    fontsize=7, fontweight="bold", ha="center", va="bottom", zorder=6)

    def _draw_card(ax, nome, dados, cor, inverter_cor=False):
        ax.set_facecolor(COR_CARD)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.autoscale(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks([]); ax.set_yticks([])
        ax.add_patch(_Rect((0.005, 0.02), 0.990, 0.960,
                     facecolor="none", edgecolor=COR_GRADE, linewidth=1.2,
                     clip_on=False, zorder=1))
        val_fim = next((v for v in reversed(dados) if v is not None), None)
        val_ini = next((v for v in dados if v is not None), None)
        val_pen = next((v for v in reversed(dados[:-1]) if v is not None), None)
        var_tot = variacao(val_fim, val_ini)
        var_yoy = variacao(val_fim, val_pen)
        def _cor_var(v):
            positivo = (v or 0) >= 0
            bom = positivo if not inverter_cor else not positivo
            return COR_DESTAQUE if bom else COR_NEGATIVO
        cor_tot = _cor_var(var_tot)
        cor_yoy = _cor_var(var_yoy)
        # Titulo
        ax.text(0.04, 0.87, nome, color=cor, fontsize=11, fontweight="bold", va="center")
        # Valor grande
        big = fmt_grande(val_fim, moeda)
        ax.text(0.04, 0.65, big, color=COR_TEXTO, fontsize=22, fontweight="bold", va="center")
        # Linha separadora horizontal
        ax.plot([0.04, SP_FRAC - 0.03], [0.37, 0.37], color=COR_GRADE, linewidth=0.8)
        # Variacoes
        ax.text(0.05, 0.28, f"{anos[0]} -> {anos[-1]}",
                color=COR_SECUND, fontsize=8, va="center")
        ax.text(0.05, 0.12, fmt_pct_var(var_tot),
                color=cor_tot, fontsize=14, fontweight="bold", va="center")
        ax.plot([0.31, 0.31], [0.08, 0.37], color=COR_GRADE, linewidth=0.8)
        ax.text(0.33, 0.28, f"{anos[-2]} -> {anos[-1]}",
                color=COR_SECUND, fontsize=8, va="center")
        ax.text(0.33, 0.12, fmt_pct_var(var_yoy),
                color=cor_yoy, fontsize=14, fontweight="bold", va="center")
        # Divisor vertical texto / sparkline
        ax.plot([SP_FRAC, SP_FRAC], [0.05, 0.95], color=COR_GRADE, linewidth=0.8)
        # Linha separadora anos
        ax.plot([SP_X0 - 0.01, SP_X1 + 0.01], [SEP_Y, SEP_Y],
                color=COR_GRADE, linewidth=0.6)
        # Labels de ano como eixo inferior
        xs = np.linspace(SP_X0, SP_X1, len(anos))
        for xp, an in zip(xs, anos):
            ax.text(xp, YR_Y, str(an), color=COR_SECUND, fontsize=6.5,
                    ha="center", va="center")
        # Sparkline
        _spark_std(ax, dados, cor, xs)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # --- Renderiza os 3 cards ---
    ax1 = fig.add_axes([PAD_X_LEFT, card_bottoms[0], card_w, card_h])
    _draw_card(ax1, "FCO  (OPERACIONAL)", fco_l, COR_DESTAQUE)

    ax2 = fig.add_axes([PAD_X_LEFT, card_bottoms[1], card_w, card_h])
    _draw_card(ax2, "CAPEX", capex_l, COR_AMARELO, inverter_cor=True)

    ax3 = fig.add_axes([PAD_X_LEFT, card_bottoms[2], card_w, card_h])
    _draw_card(ax3, "FREE CASH FLOW (FCL)", fcl_l, COR_AZUL)

    _salvar(fig, os.path.join(pasta, "4_fluxo.png"))


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 5 - Dividendos (linha DPS por ano + totalizador)
# ─────────────────────────────────────────────────────────────────────────────

def gerar_dividendos(ticker, empresa, anos, divs_tri, precos_med, pasta):
    import math as _math
    COR_CARD = "#122338"
    from matplotlib.patches import Rectangle as _Rect

    fig = _novo_fig()
    _moldura_padrao(fig, ticker)
    moeda = empresa["moeda"]
    s = simbolo_moeda(moeda)

    # --- Dados ---
    totais = []
    for a in anos:
        tri   = divs_tri.get(a, {})
        total = sum(tri.values()) if tri else 0.0
        totais.append(total)   # inclui zeros no grafico

    acumulado = sum(t for t in totais if t)

    # --- Titulo ---
    fig.text(PAD_X_LEFT, 0.880, "DIVIDENDOS",
             fontsize=18, fontweight="bold", color=COR_TEXTO, va="center")
    fig.text(PAD_X_LEFT, 0.845,
             f"Dividendo por acao ({s})  |  {anos[0]}–{anos[-1]}",
             fontsize=10, color=COR_SECUND, va="center", fontweight="normal")

    # --- Totalizador (canto superior direito) ---
    fig.text(PAD_X_RIGHT, 0.880,
             "Total acumulado",
             fontsize=9, color=COR_SECUND, va="center", ha="right", fontweight="normal")
    fig.text(PAD_X_RIGHT, 0.851,
             f"{s} {acumulado:.2f}".replace(".", ","),
             fontsize=16, color=COR_DESTAQUE, va="center", ha="right", fontweight="bold")

    # --- Card unico grande (mesmo estilo DRE) ---
    CX = PAD_X_LEFT; CY = 0.092
    CW = PAD_X_RIGHT - PAD_X_LEFT; CH = 0.726

    ax = fig.add_axes([CX, CY, CW, CH])
    ax.set_facecolor(COR_CARD)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.autoscale(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.add_patch(_Rect((0.005, 0.008), 0.990, 0.984,
                 facecolor="none", edgecolor=COR_GRADE, linewidth=1.2,
                 clip_on=False, zorder=1))

    n     = len(anos)
    xs    = np.linspace(0.10, 0.90, n)
    SEP_Y = 0.10   # linha separadora anos / grafico
    YEAR_Y= 0.055  # y dos labels de ano
    SP_Y0 = 0.22   # base da linha
    SP_Y1 = 0.70   # topo da linha — deixa espaco acima pro label

    # Linha separadora
    ax.plot([0.04, 0.96], [SEP_Y, SEP_Y], color=COR_GRADE, linewidth=0.7)

    # Labels de ano
    for xp, an in zip(xs, anos):
        ax.text(xp, YEAR_Y, str(an), color=COR_SECUND, fontsize=10,
                ha="center", va="center", fontweight="bold")

    # Sparkline de linha (full-width) — zeros sao exibidos
    vmin = min(totais); vmax = max(totais)
    spread = (vmax - vmin) if vmax != vmin else (vmax * 0.5 or 1.0)
    ys = np.array([
        SP_Y0 + (t - vmin) / spread * (SP_Y1 - SP_Y0)
        for t in totais], dtype=float)

    if len(ys):
        # Area sob a linha
        ax.fill_between(xs, ys, SP_Y0, alpha=0.20, color=COR_DESTAQUE)

        # Linha
        ax.plot(xs, ys, color=COR_DESTAQUE, linewidth=3.0, zorder=3)

        # Pontos intermediarios
        ax.scatter(xs[:-1], ys[:-1], color=COR_DESTAQUE, s=28, zorder=4, linewidths=0)

        # Ponto final destacado
        ax.scatter([xs[-1]], [ys[-1]], color=COR_DESTAQUE, s=70, zorder=5,
                   edgecolors=COR_TEXTO, linewidths=1.2)

        # Valores sempre acima do ponto — SP_Y1=0.70 garante espaco suficiente
        PAD_LABEL = 0.09

        for xp, yp, v in zip(xs, ys, totais):
            lbl = f"{s} {v:.2f}".replace(".", ",")
            ax.text(xp, yp + PAD_LABEL, lbl,
                    color=COR_TEXTO, fontsize=11, fontweight="bold",
                    ha="center", va="bottom", zorder=6)

    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    _salvar(fig, os.path.join(pasta, "5_dividendos.png"))


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 6 - Ranking (2 colunas x 4)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_indicadores_ticker(conn, ticker, ano_ref):
    """Retorna dict com os 8 indicadores calculados pra um ticker."""
    # Financeiros do ano_ref (melhor fonte)
    row = None
    for fonte in ["investsite", "statusinvest", "yfinance", "manual"]:
        r = conn.execute("""
            SELECT receita_liquida, lucro_bruto, lucro_liquido,
                   patrimonio_liquido, divida_bruta
            FROM financeiros_anuais
            WHERE ticker=? AND ano=? AND fonte=?
        """, (ticker, ano_ref, fonte)).fetchone()
        if r:
            row = r
            break
    if not row:
        return None
    rec, lb, ll, pl, divb = [float(v) if v is not None else None for v in row]

    # Mkt cap
    emp = conn.execute(
        "SELECT acoes_free FROM empresas WHERE ticker=?", (ticker,)
    ).fetchone()
    pa = conn.execute(
        "SELECT preco FROM preco_atual WHERE ticker=?", (ticker,)
    ).fetchone()
    acoes = float(emp[0]) if emp and emp[0] else None
    preco = float(pa[0])  if pa  and pa[0]  else None
    mkt = (preco * acoes) if (preco and acoes) else None

    # Dividendos do ano_ref
    div_ref = conn.execute("""
        SELECT SUM(valor) FROM dividendos_pagamentos
        WHERE ticker=? AND substr(data_com,1,4)=?
    """, (ticker, str(ano_ref))).fetchone()
    div_ref = float(div_ref[0]) if div_ref and div_ref[0] else 0.0

    # Preco medio do ano_ref (para DY do ano)
    pmref_row = conn.execute(
        "SELECT preco_medio FROM precos_anuais WHERE ticker=? AND ano=?",
        (ticker, ano_ref)
    ).fetchone()
    pmref = float(pmref_row[0]) if pmref_row and pmref_row[0] else None

    # Dividendos medios 5 anos (ano_ref-4 ate ano_ref)
    anos_5 = list(range(ano_ref - 4, ano_ref + 1))
    div_5 = conn.execute("""
        SELECT CAST(substr(data_com,1,4) AS INTEGER) AS ano, SUM(valor)
        FROM dividendos_pagamentos
        WHERE ticker=? AND ano IN ({})
        GROUP BY ano
    """.format(",".join("?" * len(anos_5))),
        (ticker, *anos_5)
    ).fetchall()
    div_5_dict = {int(row[0]): float(row[1]) for row in div_5 if row[1] is not None}

    # Preco medio 5 anos
    pmedio_5_rows = conn.execute("""
        SELECT ano, preco_medio FROM precos_anuais
        WHERE ticker=? AND ano IN ({})
    """.format(",".join("?" * len(anos_5))),
        (ticker, *anos_5)
    ).fetchall()
    pmedio_5_dict = {int(r[0]): float(r[1]) for r in pmedio_5_rows if r[1] is not None}

    def safe(a, b):
        return a / b if (a is not None and b) else None

    dy_ano   = safe(div_ref, pmref) if pmref else None

    # DY medio 5 anos: (soma dos dividendos dos 5 anos / 5) / preco atual.
    # Anos sem dividendo entram como 0; divisor sempre 5; usa preco atual (nao
    # preco medio do ano), respondendo "qual o yield esperado se eu comprar hoje".
    div_total_5 = sum(div_5_dict.get(a, 0.0) for a in anos_5)
    div_medio_anual = div_total_5 / 5
    dy_med5 = (div_medio_anual / preco) if preco else None

    return {
        "P/L":             safe(mkt, ll),
        "P/VP":            safe(mkt, pl),
        "Margem Bruta":    safe(lb, rec),
        "Margem Liquida":  safe(ll, rec),
        "ROE":             safe(ll, pl),
        f"DY {ano_ref}":   dy_ano,
        "DY medio 5 anos": dy_med5,
        "Divida Bruta/PL": safe(divb, pl),
    }


def _direcoes(ano_ref):
    return {
        "P/L":             False,
        "P/VP":            False,
        "Margem Bruta":    True,
        "Margem Liquida":  True,
        "ROE":             True,
        f"DY {ano_ref}":   True,
        "DY medio 5 anos": True,
        "Divida Bruta/PL": False,
    }


def calcular_ranking_v2(ticker_alvo, ano_ref):
    conn = sqlite3.connect(DB)
    moeda_alvo = conn.execute(
        "SELECT moeda FROM empresas WHERE ticker=?", (ticker_alvo,)
    ).fetchone()
    moeda_alvo = moeda_alvo[0] if moeda_alvo else "BRL"
    filtro_moeda = "moeda='BRL'" if moeda_alvo == "BRL" else "moeda!='BRL'"

    tickers = [r[0] for r in conn.execute(
        "SELECT ticker FROM empresas WHERE "
        + filtro_moeda
        + " AND (considerar IS NULL OR considerar != 'DESCONSIDERAR') ORDER BY ticker"
    ).fetchall()]

    todos = {}
    for t in tickers:
        ind = calcular_indicadores_ticker(conn, t, ano_ref)
        if ind:
            todos[t] = ind
    conn.close()

    direcoes = _direcoes(ano_ref)
    resultado = {}
    for ind, maior_melhor in direcoes.items():
        validos = [(t, v) for t, d in todos.items()
                   if (v := d.get(ind)) is not None and v == v]
        if ind in ("P/L", "P/VP"):
            positivos = [(t, v) for t, v in validos if v > 0]
            negativos = [(t, v) for t, v in validos if v <= 0]
            ordenado  = sorted(positivos, key=lambda x: x[1]) + negativos
        else:
            ordenado = sorted(validos, key=lambda x: x[1], reverse=maior_melhor)
        total      = len(ordenado)
        valor_alvo = todos.get(ticker_alvo, {}).get(ind)
        posicao    = next((i + 1 for i, (t, _) in enumerate(ordenado) if t == ticker_alvo), None)
        resultado[ind] = {"posicao": posicao, "total": total, "valor": valor_alvo}
    return resultado


def _formatar_valor_indicador_v2(ind, valor):
    if valor is None:
        return "-"
    if ind in ("P/L", "P/VP", "Divida Bruta/PL"):
        return fmt_num(valor, 2)
    return fmt_pct(valor, 1)


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 6 - Ranking (lista vertical)
# ─────────────────────────────────────────────────────────────────────────────

def _cor_gradiente_ranking(frac):
    """frac=0 (1° lugar) -> verde, frac=0.5 -> amarelo, frac=1 (ultimo) -> vermelho."""
    def hex2rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    def rgb2hex(r, g, b):
        return '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))
    g = hex2rgb(COR_DESTAQUE); y = hex2rgb(COR_AMARELO); r = hex2rgb(COR_NEGATIVO)
    if frac <= 0.5:
        t = frac / 0.5
        c = tuple(g[i]*(1-t) + y[i]*t for i in range(3))
    else:
        t = (frac - 0.5) / 0.5
        c = tuple(y[i]*(1-t) + r[i]*t for i in range(3))
    return rgb2hex(*c)


def gerar_ranking(ticker, empresa, ano_ref, pasta):
    from matplotlib.patches import Rectangle as _Rect

    fig = _novo_fig()
    _moldura_padrao(fig, ticker)

    rk             = calcular_ranking_v2(ticker, ano_ref)
    moeda          = empresa.get("moeda", "BRL")
    preco, data_fech = carregar_preco_atual(ticker)
    s              = simbolo_moeda(moeda)
    universo       = list(rk.values())[0].get("total", "?") if rk else "?"
    preco_str      = f"Preco: {s} {preco:.2f}".replace(".", ",") if preco else ""
    data_str       = data_fech.replace("-", "/") if data_fech else ""

    # --- Titulo centralizado ---
    fig.text(0.50, 0.930, "RANKING NA B3",
             fontsize=22, fontweight="bold", color=COR_TEXTO, va="center", ha="center")
    fig.text(0.50, 0.893,
             preco_str
             + (f"  •  Fechamento: {data_str}" if data_str else "")
             + f"  •  Ano-base: {ano_ref}  •  vs {universo} empresas",
             fontsize=11, color=COR_SECUND, va="center", ha="center", fontweight="normal")

    # --- Mapeamento indicador -> nome longo + sigla ---
    meta = {
        "P/L":             ("PREÇO / LUCRO",          "P/L"),
        "P/VP":            ("PREÇO / VALOR PATRIM.",   "P/VP"),
        "Margem Bruta":    ("MARGEM BRUTA",            "MB"),
        "Margem Liquida":  ("MARGEM LÍQUIDA",          "ML"),
        "ROE":             ("RETORNO S/ PATRIMÔNIO",   "ROE"),
        f"DY {ano_ref}":   (f"DIVIDENDO {ano_ref}",   f"DY {ano_ref}"),
        "DY medio 5 anos": ("DIVIDENDO MÉDIO 5 ANOS",  "DY MED 5A"),
        "Divida Bruta/PL": ("DÍVIDA BRUTA / PL",       "DB/PL"),
    }
    indicadores = list(meta.keys())

    COR_CARD = "#122338"

    # --- Card de fundo unico ---
    ax_bg = fig.add_axes([0.06, 0.090, 0.880, 0.786])
    ax_bg.set_facecolor(COR_CARD)
    ax_bg.set_xlim(0, 1); ax_bg.set_ylim(0, 1); ax_bg.autoscale(False)
    for sp in ax_bg.spines.values():
        sp.set_visible(False)
    ax_bg.set_xticks([]); ax_bg.set_yticks([])
    ax_bg.add_patch(_Rect((0.005, 0.005), 0.990, 0.990,
                    facecolor="none", edgecolor=COR_GRADE, linewidth=1.2, clip_on=False))

    # Cabecalho
    ax_bg.text(0.06,  0.958, "INDICADOR", color=COR_SECUND, fontsize=10,
               fontweight="bold", va="center")
    ax_bg.text(0.63,  0.958, "VALOR",     color=COR_SECUND, fontsize=10,
               fontweight="bold", va="center", ha="center")
    ax_bg.text(0.920, 0.958, "POSIÇÃO",   color=COR_SECUND, fontsize=10,
               fontweight="bold", va="center", ha="right")
    ax_bg.plot([0.03, 0.97], [0.928, 0.928], color=COR_GRADE, linewidth=0.9)

    n     = len(indicadores)
    row_h = 0.895 / n

    for i, ind in enumerate(indicadores):
        nome_longo, sigla = meta[ind]
        dados   = rk.get(ind, {})
        posicao = dados.get("posicao")
        total   = dados.get("total")
        valor   = dados.get("valor")

        frac    = (posicao / total) if (posicao and total) else 0.5
        cor     = _cor_gradiente_ranking(frac) if (posicao and total) else COR_SECUND

        y_center = 0.900 - i * row_h - row_h * 0.45

        # Linha separadora
        if i < n - 1:
            sep_y = 0.900 - (i+1) * row_h
            ax_bg.plot([0.03, 0.97], [sep_y, sep_y],
                       color=COR_GRADE, linewidth=0.5, alpha=0.55)

        # Bolinha colorida
        ax_bg.scatter([0.042], [y_center], color=cor, s=90, zorder=3)

        # Nome longo + sigla
        ax_bg.text(0.075, y_center + 0.020, nome_longo,
                   color=COR_TEXTO, fontsize=13, fontweight="bold", va="center")
        ax_bg.text(0.075, y_center - 0.030, sigla,
                   color=COR_SECUND, fontsize=10, va="center")

        # Valor do indicador
        val_str = _formatar_valor_indicador_v2(ind, valor)
        ax_bg.text(0.63, y_center, val_str,
                   color=COR_DESTAQUE, fontsize=20, fontweight="bold",
                   va="center", ha="center")

        # Posicao grande
        pos_txt   = f"{posicao}°" if posicao else "—"
        total_txt = f"de {total}" if total else ""
        ax_bg.text(0.875, y_center + 0.014, pos_txt,
                   color=cor, fontsize=30, fontweight="bold",
                   va="center", ha="center")
        ax_bg.text(0.875, y_center - 0.036, total_txt,
                   color=COR_SECUND, fontsize=9, va="center", ha="center")

    ax_bg.set_xlim(0, 1); ax_bg.set_ylim(0, 1)

    fig.text(0.50, 0.058,
             "1° = verde  •  meio do ranking = amarelo  •  último = vermelho",
             fontsize=9, color=COR_SECUND, ha="center", fontweight="normal")
    _salvar(fig, os.path.join(pasta, "6_ranking.png"))


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 7 - Indicadores (valuation + rentabilidade + saude financeira)
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
#  Slide 7 - Indicadores (valuation + rentabilidade + saude financeira)
# ─────────────────────────────────────────────────────────────────────────────

def gerar_indicadores(ticker, empresa, ano_ref, pasta):
    from matplotlib.patches import FancyBboxPatch as _FBP

    fig = _novo_fig()
    _moldura_padrao(fig, ticker)

    moeda  = empresa.get("moeda", "BRL")
    s      = simbolo_moeda(moeda)
    preco, data_fech = carregar_preco_atual(ticker)
    preco_str = f"{s} {preco:.2f}".replace(".", ",") if preco else "—"
    data_str  = data_fech.replace("-", "/") if data_fech else ""

    fig.text(0.50, 0.930, "RANKING INDICADORES",
             fontsize=22, fontweight="bold", color=COR_TEXTO, va="center", ha="center")
    sub = f"Preco: {preco_str}"
    if data_str:
        sub += f"  •  {data_str}"
    sub += f"  •  Ano-base: {ano_ref}"
    fig.text(0.50, 0.893, sub, fontsize=10, color=COR_SECUND, va="center", ha="center")

    conn = sqlite3.connect(DB)
    ind  = calcular_indicadores_ticker(conn, ticker, ano_ref)
    conn.close()

    # Ranking de cada indicador
    ranking = calcular_ranking_v2(ticker, ano_ref)

    direcoes = _direcoes(ano_ref)

    # grupos ordenados
    grupos = [
        ("VALUATION",          ["P/L", "P/VP"]),
        ("RENTABILIDADE",      ["Margem Bruta", "Margem Liquida", "ROE"]),
        ("DIVIDENDOS",         [f"DY {ano_ref}", "DY medio 5 anos"]),
        ("SAUDE FINANCEIRA",   ["Divida Bruta/PL"]),
    ]

    def _fmt_ind(nome, v):
        if v is None:
            return "—"
        # multiplicadores / formatters
        pct_nomes = {"Margem Bruta","Margem Liquida","ROE",f"DY {ano_ref}","DY medio 5 anos"}
        if nome in pct_nomes:
            return f"{v*100:.1f}%".replace(".", ",")
        return f"{v:.2f}x".replace(".", ",")

    def _cor_ind(nome, v):
        if v is None:
            return COR_SECUND
        bom_alto = direcoes.get(nome, True)
        # thresholds razoaveis para colorir
        limites = {
            "P/L":             (8, 20),
            "P/VP":            (0.8, 3),
            "Margem Bruta":    (0.20, 0.40),
            "Margem Liquida":  (0.10, 0.20),
            "ROE":             (0.10, 0.20),
            f"DY {ano_ref}":   (0.04, 0.08),
            "DY medio 5 anos": (0.04, 0.08),
            "Divida Bruta/PL": (0.5, 2.0),
        }
        lo, hi = limites.get(nome, (0, 1))
        if bom_alto:
            if v >= hi:   return COR_DESTAQUE
            if v >= lo:   return COR_AMARELO
            return COR_NEGATIVO
        else:
            if v <= lo:   return COR_DESTAQUE
            if v <= hi:   return COR_AMARELO
            return COR_NEGATIVO

    COR_CARD_BG = "#0f1e2e"
    # card background
    ax_bg = fig.add_axes([0.06, 0.07, 0.88, 0.80])
    ax_bg.set_xlim(0, 1); ax_bg.set_ylim(0, 1)
    ax_bg.axis("off")
    ax_bg.add_patch(_FBP((0, 0), 1, 1,
                         boxstyle="round,pad=0.02",
                         facecolor=COR_CARD_BG, edgecolor="#1e3a5f", linewidth=1.5))

    # monta lista de linhas
    all_items = []
    for grupo, nomes in grupos:
        all_items.append(("grupo", grupo, None, None))
        for nm in nomes:
            v   = ind.get(nm) if ind else None
            rk  = ranking.get(nm, {})
            all_items.append(("item", nm, v, rk))

    # total rows to fit
    n_total = len(all_items)
    row_h = 1.0 / (n_total + 1)

    for idx, (tipo, nome, v, rk) in enumerate(all_items):
        y_center = 1.0 - (idx + 0.8) * row_h

        if tipo == "grupo":
            ax_bg.text(0.04, y_center, nome,
                       fontsize=9, fontweight="bold", color=COR_DESTAQUE,
                       va="center", ha="left", transform=ax_bg.transAxes)
            ax_bg.axhline(y=y_center - row_h*0.35, xmin=0.03, xmax=0.97,
                          color="#1e3a5f", linewidth=0.8)
        else:
            cor_v   = _cor_ind(nome, v)
            val_str = _fmt_ind(nome, v)

            posicao = rk.get("posicao")
            total   = rk.get("total")
            frac    = ((posicao - 1) / (total - 1)) if (posicao and total and total > 1) else None
            cor_rk  = _cor_gradiente_ranking(frac) if frac is not None else COR_SECUND

            # dot
            ax_bg.plot(0.04, y_center, "o", color=cor_v, markersize=7,
                       transform=ax_bg.transAxes, clip_on=False)
            # name
            ax_bg.text(0.09, y_center, nome,
                       fontsize=13, color=COR_TEXTO, va="center", ha="left",
                       transform=ax_bg.transAxes, fontweight="bold")
            # valor (centro-direita)
            ax_bg.text(0.58, y_center, val_str,
                       fontsize=16, color=cor_v, va="center", ha="right",
                       transform=ax_bg.transAxes, fontweight="bold")
            # posicao grande (direita) com cor gradiente
            pos_str = f"{posicao}°" if posicao else "—"
            de_str  = f"de {total}" if total else ""
            ax_bg.text(0.78, y_center + row_h * 0.08, pos_str,
                       fontsize=22, color=cor_rk, va="center", ha="center",
                       transform=ax_bg.transAxes, fontweight="bold")
            ax_bg.text(0.78, y_center - row_h * 0.30, de_str,
                       fontsize=8, color=COR_SECUND, va="center", ha="center",
                       transform=ax_bg.transAxes)

    fig.text(0.50, 0.045,
             "1° = verde  •  meio do ranking = amarelo  •  último = vermelho",
             fontsize=8, color=COR_SECUND, ha="center", fontweight="normal")
    _salvar(fig, os.path.join(pasta, "7_indicadores.png"))


# ─────────────────────────────────────────────────────────────────────────────
#  Gerar todos os slides
# ─────────────────────────────────────────────────────────────────────────────

def gerar_todas(ticker, pasta=None, ano_ini=None, ano_fim=None):
    conn = sqlite3.connect(DB)
    emp  = conn.execute(
        "SELECT nome, moeda FROM empresas WHERE ticker=?", (ticker,)
    ).fetchone()
    conn.close()
    if not emp:
        raise ValueError(f"Ticker {ticker} nao encontrado")
    empresa = {"nome": emp[0], "moeda": emp[1] or "BRL"}

    anos, fin = carregar_financeiros(ticker)
    if not anos:
        raise ValueError(f"Sem dados financeiros para {ticker}")

    if ano_ini is not None or ano_fim is not None:
        lo = ano_ini if ano_ini is not None else min(anos)
        hi = ano_fim if ano_fim is not None else max(anos)
        anos = [a for a in anos if lo <= a <= hi]
        fin  = {a: fin[a] for a in anos if a in fin}

    divs_tri   = carregar_dividendos_trimestrais(ticker)
    precos_med = {}
    for a in anos:
        conn2 = sqlite3.connect(DB)
        r = conn2.execute(
            "SELECT preco_medio FROM precos_anuais WHERE ticker=? AND ano=?",
            (ticker, a)
        ).fetchone()
        conn2.close()
        if r and r[0]:
            precos_med[a] = float(r[0])

    if pasta is None:
        pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slides", ticker)
    os.makedirs(pasta, exist_ok=True)

    print(f"[{ticker}] Gerando capa...")
    gerar_capa(ticker, empresa, anos, pasta)
    print(f"[{ticker}] Gerando DRE...")
    gerar_dre_grafico(ticker, empresa, anos, fin, pasta)
    print(f"[{ticker}] Gerando Balanco...")
    gerar_balanco(ticker, empresa, anos, fin, pasta)
    print(f"[{ticker}] Gerando Fluxo...")
    gerar_fluxo(ticker, empresa, anos, fin, pasta)
    print(f"[{ticker}] Gerando Dividendos...")
    gerar_dividendos(ticker, empresa, anos, divs_tri, precos_med, pasta)
    print(f"[{ticker}] Gerando Ranking...")
    gerar_ranking(ticker, empresa, anos[-1], pasta)
    print(f"[{ticker}] Gerando Indicadores...")
    gerar_indicadores(ticker, empresa, anos[-1], pasta)
    print(f"[{ticker}] Pronto! Slides salvos em: {pasta}")


if __name__ == "__main__":
    print("=" * 50)
    print("  GERADOR DE IMAGENS PARA INSTAGRAM")
    print("  @capitalemjogo")
    print("=" * 50)

    ticker = input("\n  Ticker (ex: PETR4, AAPL): ").strip().upper()
    if not ticker:
        sys.exit()

    try:
        ano_ini = int(input("  Ano inicial (ex: 2021): ").strip())
        ano_fim = int(input("  Ano final   (ex: 2025): ").strip())
    except ValueError:
        print("  Anos invalidos.")
        sys.exit()

    if ano_ini > ano_fim:
        print("  Ano inicial deve ser <= ano final.")
        sys.exit()

    gerar_todas(ticker, ano_ini=ano_ini, ano_fim=ano_fim)
