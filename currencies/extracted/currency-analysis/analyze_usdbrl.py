"""
analyze_usdbrl.py -- Fase 1: Coleta + exploracao visual

Baixa 10+ anos de USD/BRL do Yahoo Finance, salva em CSV local,
gera grafico do historico e tabela de estatisticas descritivas.

Uso: python analyze_usdbrl.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.fetchers.yahoo_fetcher import fetch_currency_history
from src.analysis.descriptive import (
    add_returns,
    descriptive_stats,
    annualized_volatility,
    rolling_volatility,
    drawdown,
)

# ── Caminhos ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_RAW = BASE_DIR / "data" / "raw"
OUT_DIR  = BASE_DIR / "outputs"
OUT_DIR.mkdir(exist_ok=True)

TICKER = "USDBRL=X"
PERIOD = "10y"   # 10 anos


# ── Estilo dos graficos ─────────────────────────────────────────────────────────
COR_FUNDO    = "#0B1E2D"
COR_FUNDO2   = "#13283C"
COR_TEXTO    = "#FFFFFF"
COR_DESTAQUE = "#00D4AA"
COR_NEGATIVO = "#FF6B6B"
COR_GRADE    = "#1F3F5C"
COR_SECUND   = "#9BB3C4"


def _aplicar_estilo(ax, titulo=""):
    ax.set_facecolor(COR_FUNDO2)
    if titulo:
        ax.set_title(titulo, color=COR_TEXTO, fontsize=13, fontweight="bold", pad=10)
    ax.tick_params(colors=COR_SECUND, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(COR_GRADE)
    ax.grid(color=COR_GRADE, linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)


# ── Coleta ──────────────────────────────────────────────────────────────────────

def carregar_dados(force_refetch=False):
    """
    Carrega CSV mais recente da pasta data/raw/.
    Se nao houver, ou force_refetch=True, baixa do Yahoo.
    """
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    csvs = sorted(DATA_RAW.glob("USDBRL_*.csv"))

    if csvs and not force_refetch:
        ultimo = csvs[-1]
        print(f"Usando CSV existente: {ultimo.name}")
        df = pd.read_csv(ultimo, index_col=0, parse_dates=True)
        return df

    print(f"Baixando {TICKER} ({PERIOD}) do Yahoo Finance...")
    df = fetch_currency_history(TICKER, period=PERIOD, save=True)
    return df


# ── Exploracao visual ───────────────────────────────────────────────────────────

def grafico_historico(df, fig_path):
    """Grafico 1: serie completa com pico/fundo destacados."""
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=COR_FUNDO)
    _aplicar_estilo(ax, f"USD/BRL  --  Ultimos {PERIOD}")

    ax.plot(df.index, df["Close"], color=COR_DESTAQUE, linewidth=1.2)

    # Marca pico e fundo
    pico_idx = df["Close"].idxmax()
    fundo_idx = df["Close"].idxmin()
    pico_val = df["Close"].loc[pico_idx]
    fundo_val = df["Close"].loc[fundo_idx]

    ax.scatter(pico_idx, pico_val, color=COR_NEGATIVO, s=80, zorder=5,
               label=f"Pico: R$ {pico_val:.2f} ({pico_idx.date()})")
    ax.scatter(fundo_idx, fundo_val, color=COR_DESTAQUE, s=80, zorder=5,
               label=f"Fundo: R$ {fundo_val:.2f} ({fundo_idx.date()})")

    # Marca valor atual
    ult_idx = df.index[-1]
    ult_val = df["Close"].iloc[-1]
    ax.scatter(ult_idx, ult_val, color="#F4D03F", s=80, zorder=5,
               label=f"Atual: R$ {ult_val:.2f} ({ult_idx.date()})")

    ax.set_ylabel("USD/BRL (R$)", color=COR_TEXTO, fontsize=11)
    leg = ax.legend(loc="upper left", facecolor=COR_FUNDO,
                    edgecolor=COR_GRADE, labelcolor=COR_TEXTO, fontsize=10)

    plt.tight_layout()
    fig.savefig(fig_path, dpi=120, facecolor=COR_FUNDO)
    plt.close(fig)
    print(f"  Salvo: {fig_path.name}")


def grafico_volatilidade(df, fig_path):
    """Grafico 2: volatilidade movel anualizada (janela 30 dias)."""
    df = add_returns(df)
    vol = rolling_volatility(df["log_return"], window=30)

    fig, ax = plt.subplots(figsize=(14, 5), facecolor=COR_FUNDO)
    _aplicar_estilo(ax, "Volatilidade movel anualizada (janela 30 dias)")

    ax.plot(vol.index, vol * 100, color="#F4D03F", linewidth=1.0)
    ax.fill_between(vol.index, vol * 100, 0, color="#F4D03F", alpha=0.15)

    ax.set_ylabel("Volatilidade %", color=COR_TEXTO, fontsize=11)

    # Linhas horizontais de referencia
    media = vol.mean() * 100
    ax.axhline(media, color=COR_SECUND, linestyle="--", linewidth=1, alpha=0.7,
               label=f"Media: {media:.1f}%")
    leg = ax.legend(loc="upper left", facecolor=COR_FUNDO,
                    edgecolor=COR_GRADE, labelcolor=COR_TEXTO, fontsize=10)

    plt.tight_layout()
    fig.savefig(fig_path, dpi=120, facecolor=COR_FUNDO)
    plt.close(fig)
    print(f"  Salvo: {fig_path.name}")


def grafico_drawdown(df, fig_path):
    """Grafico 3: drawdown ao longo do tempo (queda desde o pico)."""
    dd = drawdown(df["Close"])

    fig, ax = plt.subplots(figsize=(14, 4), facecolor=COR_FUNDO)
    _aplicar_estilo(ax, "Drawdown da serie  --  queda desde o pico anterior")

    ax.fill_between(dd.index, dd["drawdown"] * 100, 0, color=COR_NEGATIVO, alpha=0.4)
    ax.plot(dd.index, dd["drawdown"] * 100, color=COR_NEGATIVO, linewidth=0.8)

    pior = dd["drawdown"].min() * 100
    ax.axhline(pior, color=COR_NEGATIVO, linestyle="--", linewidth=1, alpha=0.7,
               label=f"Pior drawdown: {pior:.1f}%")

    ax.set_ylabel("Drawdown %", color=COR_TEXTO, fontsize=11)
    leg = ax.legend(loc="lower left", facecolor=COR_FUNDO,
                    edgecolor=COR_GRADE, labelcolor=COR_TEXTO, fontsize=10)

    plt.tight_layout()
    fig.savefig(fig_path, dpi=120, facecolor=COR_FUNDO)
    plt.close(fig)
    print(f"  Salvo: {fig_path.name}")


def grafico_distribuicao_retornos(df, fig_path):
    """Grafico 4: histograma dos retornos diarios (log)."""
    df = add_returns(df)
    log_ret = df["log_return"].dropna() * 100   # em %

    fig, ax = plt.subplots(figsize=(12, 5), facecolor=COR_FUNDO)
    _aplicar_estilo(ax, "Distribuicao dos retornos diarios (log) --  USD/BRL")

    ax.hist(log_ret, bins=80, color=COR_DESTAQUE, edgecolor=COR_FUNDO, alpha=0.85)
    ax.axvline(log_ret.mean(), color="#F4D03F", linestyle="--", linewidth=1.5,
               label=f"Media: {log_ret.mean():.3f}%")
    ax.axvline(log_ret.median(), color=COR_SECUND, linestyle=":", linewidth=1.5,
               label=f"Mediana: {log_ret.median():.3f}%")

    ax.set_xlabel("Retorno log diario (%)", color=COR_TEXTO, fontsize=11)
    ax.set_ylabel("Frequencia", color=COR_TEXTO, fontsize=11)
    leg = ax.legend(loc="upper right", facecolor=COR_FUNDO,
                    edgecolor=COR_GRADE, labelcolor=COR_TEXTO, fontsize=10)

    plt.tight_layout()
    fig.savefig(fig_path, dpi=120, facecolor=COR_FUNDO)
    plt.close(fig)
    print(f"  Salvo: {fig_path.name}")


# ── Estatisticas ────────────────────────────────────────────────────────────────

def imprimir_resumo(df):
    """Imprime tabela de estatisticas no terminal."""
    df_r = add_returns(df)
    log_ret = df_r["log_return"].dropna()

    SEP = "=" * 60
    print(f"\n{SEP}")
    print("  RESUMO USD/BRL")
    print(SEP)
    print(f"  Periodo:        {df.index.min().date()}  ate  {df.index.max().date()}")
    print(f"  Observacoes:    {len(df):,} dias de pregao")
    print(f"  Anos cobertos:  {(df.index.max() - df.index.min()).days / 365.25:.1f}")
    print()

    # ── Estatisticas de preco ──
    print("  PRECO USD/BRL (R$)")
    print("  " + "-" * 56)
    s_preco = descriptive_stats(df["Close"])
    print(f"    Atual          R$ {df['Close'].iloc[-1]:>8.4f}")
    print(f"    Media          R$ {s_preco['mean']:>8.4f}")
    print(f"    Mediana        R$ {s_preco['median']:>8.4f}")
    print(f"    Min            R$ {s_preco['min']:>8.4f}")
    print(f"    Max            R$ {s_preco['max']:>8.4f}")
    print(f"    Desvio padrao  R$ {s_preco['std']:>8.4f}")
    print(f"    Q25            R$ {s_preco['q25']:>8.4f}")
    print(f"    Q75            R$ {s_preco['q75']:>8.4f}")
    print()

    # ── Estatisticas de retornos ──
    print("  RETORNOS DIARIOS (log)")
    print("  " + "-" * 56)
    s_ret = descriptive_stats(log_ret)
    print(f"    Media            {s_ret['mean']*100:>+8.4f} %")
    print(f"    Mediana          {s_ret['median']*100:>+8.4f} %")
    print(f"    Desvio padrao    {s_ret['std']*100:>+8.4f} %")
    print(f"    Min (pior dia)   {s_ret['min']*100:>+8.4f} %")
    print(f"    Max (melhor dia) {s_ret['max']*100:>+8.4f} %")
    print(f"    Skew             {s_ret['skew']:>+8.4f}    (>0 = cauda direita)")
    print(f"    Kurtosis         {s_ret['kurtosis']:>+8.4f}    (>0 = caudas pesadas)")
    print()

    # ── Volatilidade ──
    vol_anu = annualized_volatility(log_ret) * 100
    print("  VOLATILIDADE")
    print("  " + "-" * 56)
    print(f"    Anualizada (12m)         {vol_anu:>6.2f} %")

    # Volatilidade dos ultimos 30, 90, 252 dias
    for window, label in [(30, "30 dias"), (90, "90 dias"), (252, "252 dias")]:
        vol_w = log_ret.tail(window).std() * (252 ** 0.5) * 100
        print(f"    Anualizada (ultimos {label:>10})   {vol_w:>6.2f} %")
    print()

    # ── Drawdown ──
    dd = drawdown(df["Close"])
    pior_dd = dd["drawdown"].min() * 100
    pior_idx = dd["drawdown"].idxmin()
    print("  DRAWDOWN")
    print("  " + "-" * 56)
    print(f"    Pior queda     {pior_dd:>+7.2f} %  em  {pior_idx.date()}")
    dd_atual = dd["drawdown"].iloc[-1] * 100
    print(f"    Atual          {dd_atual:>+7.2f} %")
    print(SEP)


def salvar_resumo_csv(df, csv_path):
    """Salva tabela de stats em CSV."""
    df_r = add_returns(df)
    log_ret = df_r["log_return"].dropna()

    s_preco = descriptive_stats(df["Close"])
    s_ret   = descriptive_stats(log_ret)

    out = pd.DataFrame({
        "preco_BRL":     s_preco,
        "retorno_log_d": s_ret,
    })
    out.to_csv(csv_path, float_format="%.6f")
    print(f"  Salvo: {csv_path.name}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  USD/BRL  --  Fase 1: Coleta + Exploracao visual")
    print("=" * 60)

    df = carregar_dados()

    # Mantem so as colunas relevantes (Close vai ser o foco)
    df = df[["Open", "High", "Low", "Close"]].dropna()

    print(f"\nDados carregados: {len(df)} linhas, periodo "
          f"{df.index.min().date()} a {df.index.max().date()}")

    imprimir_resumo(df)

    # Gera os 4 graficos
    print("\nGerando graficos em outputs/...")
    grafico_historico(df, OUT_DIR / "1_historico.png")
    grafico_volatilidade(df, OUT_DIR / "2_volatilidade.png")
    grafico_drawdown(df, OUT_DIR / "3_drawdown.png")
    grafico_distribuicao_retornos(df, OUT_DIR / "4_distribuicao_retornos.png")

    # Salva tabela
    salvar_resumo_csv(df, OUT_DIR / "stats_resumo.csv")

    print(f"\nConcluido. Saidas em: {OUT_DIR}")


if __name__ == "__main__":
    main()
