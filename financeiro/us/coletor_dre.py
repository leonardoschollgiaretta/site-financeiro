"""
Coletor DRE -- Acoes Americanas
Fonte: yfinance (income_stmt)
Campos: receita_liquida, custo_receita, lucro_bruto, despesas_operacionais,
        ebit, receitas_financeiras, despesas_financeiras, resultado_financeiro,
        ebt, ir_csll, lucro_liquido, ebitda, depreciacao_amortizacao

Diferencas vs BR:
  - Valores em USD, ja em unidade absoluta (NAO multiplicar por 1000).
  - Ano: usado o ano da data de fechamento (col.year), conforme combinado.
    Empresas com fechamento fiscal fora de dezembro (AAPL=set, MSFT=jun) terao
    o ano atribuido pela data de fim do periodo. Normalizacao "mais meses"
    fica para depois.
  - EBITDA ja vem do yfinance, nao precisa calcular.
  - Nomes dos campos no DataFrame yfinance variam — testamos varios apelidos.
"""
import sqlite3
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yfinance as yf
import pandas as pd
from db_utils import upsert_financeiro
from db_validacao import is_validado

DB    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")
FONTE = "yfinance"

# Coluna do banco -> lista de nomes possiveis no DataFrame yfinance
# A primeira que existir e tiver valor nao-nulo vence.
MAPA = {
    "receita_liquida":         ["Total Revenue", "Operating Revenue"],
    "custo_receita":           ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "lucro_bruto":             ["Gross Profit"],
    "despesas_operacionais":   ["Operating Expense", "Operating Expenses",
                                "Selling General And Administration"],
    "depreciacao_amortizacao": ["Reconciled Depreciation",
                                "Depreciation And Amortization",
                                "Depreciation Amortization Depletion"],
    "ebit":                    ["EBIT", "Operating Income"],
    "ebitda":                  ["EBITDA", "Normalized EBITDA"],
    "despesas_financeiras":    ["Interest Expense", "Interest Expense Non Operating"],
    "receitas_financeiras":    ["Interest Income", "Interest Income Non Operating"],
    "ebt":                     ["Pretax Income"],
    "ir_csll":                 ["Tax Provision", "Income Tax Expense"],
    "lucro_liquido":           ["Net Income",
                                "Net Income Common Stockholders",
                                "Net Income From Continuing Operation Net Minority Interest"],
}


def _val(df, col, nomes):
    for nome in nomes:
        if nome in df.index:
            v = df.loc[nome, col]
            if pd.notna(v):
                return float(v)
    return None


def coletar(ticker):
    print(f"  📊 DRE {ticker}...")
    try:
        acao = yf.Ticker(ticker)
        inc = acao.income_stmt
    except Exception as e:
        print(f"     ❌ Erro yfinance: {e}")
        return

    if inc is None or inc.empty:
        print(f"     ⚠️  Sem dados de DRE")
        return

    conn = sqlite3.connect(DB)

    gravados = []
    pulados  = []

    for col in inc.columns:
        ano = int(col.year)
        if is_validado(conn, ticker, "dre", ano):
            pulados.append(ano)
            continue

        mapa = {}
        for coluna_db, nomes in MAPA.items():
            v = _val(inc, col, nomes)
            if v is not None:
                mapa[coluna_db] = v

        # Resultado financeiro = receitas - despesas (despesas vem positiva no yfinance)
        rf = mapa.get("receitas_financeiras")
        df_ = mapa.get("despesas_financeiras")
        if rf is not None or df_ is not None:
            mapa["resultado_financeiro"] = (rf or 0) - (df_ or 0)

        if mapa:
            upsert_financeiro(conn, ticker, ano, FONTE, mapa)
            rec = mapa.get("receita_liquida")
            luc = mapa.get("lucro_liquido")
            luc_txt = f" | Lucro: $ {luc:,.0f}" if luc else ""
            print(f"     {ano} → Receita: $ {rec:,.0f}{luc_txt}" if rec else f"     {ano} → sem receita")
            gravados.append(ano)

    if pulados:
        print(f"     validado, pulando anos: {sorted(pulados)}")
    if gravados:
        print(f"     gravados: {sorted(gravados)}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    import banco
    banco.criar_banco()

    TICKERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tickers.xlsx")
    df = pd.read_excel(TICKERS_FILE, sheet_name="Tickers", header=2)
    df.columns = [c.strip() for c in df.columns]
    tickers = [str(t).strip().upper() for t in df.get("TICKER_US", []) if pd.notna(t) and str(t).strip()]

    print(f"  {len(tickers)} ticker(s) US encontrados em tickers.xlsx\n")
    for t in tickers:
        try:
            coletar(t)
        except Exception as e:
            print(f"  ❌ {t} — erro: {e}")
    print("\n✅ DRE US finalizado!")
