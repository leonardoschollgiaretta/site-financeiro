"""
main.py — Coleta de dados financeiros

Como usar:
  1. Abra o arquivo tickers.xlsx
  2. Digite os tickers que quer buscar/atualizar (BR ou US)
  3. Salve e rode: python main.py
  - O banco acumula tudo; cada execução atualiza só os tickers listados
"""
import sys
import os
import sqlite3
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import banco
from br import coletor_dre, coletor_balanco, coletor_fluxo, coletor_dividendo, coletor_preco, coletor_acoes
from us import (
    coletor_dre        as us_dre,
    coletor_balanco    as us_balanco,
    coletor_fluxo      as us_fluxo,
    coletor_dividendo  as us_dividendo,
    coletor_preco      as us_preco,
    coletor_acoes      as us_acoes,
    coletor_fechamento as us_fechamento,
)

DIR      = os.path.dirname(os.path.abspath(__file__))
TICKERS_FILE = os.path.join(DIR, "tickers.xlsx")
DB       = os.path.join(DIR, "financeiro.db")


def ler_tickers():
    """Lê tickers.xlsx e retorna listas de tickers BR e US (não-vazios)."""
    if not os.path.exists(TICKERS_FILE):
        print(f"❌ Arquivo não encontrado: {TICKERS_FILE}")
        return [], []

    df = pd.read_excel(TICKERS_FILE, sheet_name="Tickers", header=2)  # linha 3 = cabeçalho
    df.columns = [c.strip() for c in df.columns]

    br = [str(t).strip().upper() for t in df.get("TICKER_BR", []) if pd.notna(t) and str(t).strip()]
    us = [str(t).strip().upper() for t in df.get("TICKER_US", []) if pd.notna(t) and str(t).strip()]
    return br, us


def registrar_empresa(ticker, moeda="BRL"):
    """Registra empresa no banco se ainda não existir."""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO empresas (ticker, nome, setor, moeda)
        VALUES (?, ?, ?, ?)
    """, (ticker, ticker, "N/A", moeda))
    conn.commit()
    conn.close()


def coletar_br(ticker):
    print(f"\n{'─'*45}")
    print(f"  📋 {ticker}  [BR]")
    print(f"{'─'*45}")
    registrar_empresa(ticker, moeda="BRL")
    coletor_dre.coletar(ticker)
    coletor_balanco.coletar(ticker)
    coletor_fluxo.coletar(ticker)
    coletor_dividendo.coletar(ticker)
    coletor_preco.coletar(ticker)
    coletor_acoes.coletar(ticker)


def coletar_us(ticker):
    print(f"\n{'─'*45}")
    print(f"  📋 {ticker}  [US]")
    print(f"{'─'*45}")
    registrar_empresa(ticker, moeda="USD")
    us_dre.coletar(ticker)
    us_balanco.coletar(ticker)
    us_fluxo.coletar(ticker)
    us_dividendo.coletar(ticker)
    us_preco.coletar(ticker)
    us_acoes.coletar(ticker)

    # Fechamento atual (alimenta preco_atual para o TTM do relatorio)
    resultado = us_fechamento.coletar_fechamento(ticker)
    if resultado:
        preco, data_fech, variacao = resultado
        us_fechamento.salvar(ticker, preco, data_fech, variacao)
        var_txt = f"  {variacao:+.2f}%" if variacao is not None else ""
        print(f"  📈 Fechamento: $ {preco:.2f}{var_txt}  [{data_fech}]")


if __name__ == "__main__":
    print("=" * 45)
    print("  COLETA DE DADOS FINANCEIROS")
    print("=" * 45)

    banco.criar_banco()

    tickers_br, tickers_us = ler_tickers()

    if not tickers_br and not tickers_us:
        print("\n⚠️  Nenhum ticker encontrado em tickers.xlsx")
        sys.exit()

    print(f"\n  BR: {tickers_br}")
    print(f"  US: {tickers_us if tickers_us else '(nenhum)'}\n")

    for ticker in tickers_br:
        try:
            coletar_br(ticker)
        except Exception as e:
            print(f"  ❌ {ticker} — erro inesperado, pulando: {e}")

    for ticker in tickers_us:
        try:
            coletar_us(ticker)
        except Exception as e:
            print(f"  ❌ {ticker} — erro inesperado, pulando: {e}")

    print("\n" + "=" * 45)
    print(f"  ✅ {len(tickers_br)} BR + {len(tickers_us)} US processados")
    print("=" * 45)
