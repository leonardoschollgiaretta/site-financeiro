"""
main.py — Roda toda a coleta de dados em sequência

Ordem:
1. Cria / atualiza o banco
2. Coleta DRE, Balanço e FC via Status Invest
3. Coleta dividendos via yfinance
4. Coleta preços via yfinance
5. Gera painel de qualidade
"""

import banco
import coletor_statusinvest
import coletor_dividendos
import coletor_precos
import painel

TICKERS = ["GRND3", "ITSA4", "PETR4", "VALE3", "SAPR4"]

if __name__ == "__main__":
    print("=" * 50)
    print("  COLETA COMPLETA — SISTEMA FINANCEIRO B3")
    print("=" * 50)

    # 1. Banco
    banco.criar_banco()

    # 2. Status Invest (DRE + Balanço + FC)
    print("\n📊 STATUS INVEST — DRE / Balanço / Fluxo de Caixa")
    session = coletor_statusinvest.get_session()
    for ticker in TICKERS:
        coletor_statusinvest.coletar_empresa(ticker, session)

    # 3. Dividendos
    print("\n💰 DIVIDENDOS — Yahoo Finance")
    for ticker in TICKERS:
        coletor_dividendos.coletar_empresa(ticker)

    # 4. Preços
    print("\n📈 PREÇOS — Yahoo Finance")
    for ticker in TICKERS:
        coletor_precos.coletar_empresa(ticker)

    # 5. Painel
    print("\n📋 PAINEL DE QUALIDADE")
    painel.gerar_painel()

    print("\n" + "=" * 50)
    print("  ✅ COLETA FINALIZADA!")
    print("=" * 50)
