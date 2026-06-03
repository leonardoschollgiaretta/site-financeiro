"""
run_all.py — Executa a sequencia completa de coleta e geracao de relatorios.

Sequencia:
  0. sync_validador.py  — sincroniza validador.xlsx → banco de dados
  1. main.py            — coleta DRE, Balanco, Fluxo, Dividendos, Precos historicos, Acoes
  2. infospainel.py     — gera o painel (outputs/infospainel.xlsx)
  3. relatorio.py       — gera relatorios individuais (pede tickers ao final)

Nota: coletor_fechamento.py e ranker.py sao rodados separadamente quando necessario.

Uso: python run_all.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import banco
import main as _main
import infospainel
import sync_validador
import relatorio
import sqlite3

DIR = os.path.dirname(os.path.abspath(__file__))
DB  = os.path.join(DIR, "financeiro.db")

SEP = "=" * 50


def passo(numero, descricao):
    print(f"\n{SEP}")
    print(f"  PASSO {numero}: {descricao}")
    print(SEP)


if __name__ == "__main__":

    banco.criar_banco()

    # ── Sync validador (antes de qualquer coleta) ─────────────────────────────
    passo(0, "SYNC VALIDADOR  (sync_validador.py)")
    sync_validador.sincronizar()

    # ── Passo 1: Coleta completa (main.py) ────────────────────────────────────
    passo(1, "COLETA DE DADOS  (main.py)")
    tickers_br, tickers_us = _main.ler_tickers()

    if not tickers_br and not tickers_us:
        print("Nenhum ticker encontrado em tickers.xlsx — encerrando.")
        sys.exit()

    print(f"  BR: {tickers_br}")
    print(f"  US: {tickers_us if tickers_us else '(nenhum)'}\n")

    erros = []
    for ticker in tickers_br:
        try:
            _main.coletar_br(ticker)
        except Exception as e:
            print(f"  ❌ {ticker} — erro inesperado, pulando: {e}")
            erros.append(ticker)

    for ticker in tickers_us:
        try:
            _main.coletar_us(ticker)
        except Exception as e:
            print(f"  ❌ {ticker} — erro inesperado, pulando: {e}")
            erros.append(ticker)

    if erros:
        print(f"\n  ⚠️  Tickers com erro durante coleta: {erros}")

    # ── Passo 2: Painel ───────────────────────────────────────────────────────
    passo(2, "PAINEL  (infospainel.py)")
    infospainel.main()

    # ── Passo 3: Relatorios individuais ──────────────────────────────────────
    passo(3, "RELATORIOS INDIVIDUAIS  (relatorio.py)")

    conn = sqlite3.connect(DB)
    disponiveis = sorted(
        row[0] for row in conn.execute("SELECT DISTINCT ticker FROM financeiros_anuais")
    )
    conn.close()

    print(f"\n  Tickers com dados no banco: {disponiveis}")
    entrada = input("\n  Digite os tickers para o relatorio (Enter = pular): ").strip()

    if not entrada:
        print("  Relatorio pulado.")
    else:
        tickers_rel = [t.strip().upper() for t in entrada.replace(",", " ").split() if t.strip()]
        com_dados   = [t for t in tickers_rel if t in disponiveis]
        sem_dados   = [t for t in tickers_rel if t not in disponiveis]

        if sem_dados:
            print(f"  Sem dados para: {sem_dados} — ignorados")
        if com_dados:
            relatorio.gerar_relatorio(com_dados)

    print(f"\n{SEP}")
    print("  CONCLUIDO")
    print(SEP)
