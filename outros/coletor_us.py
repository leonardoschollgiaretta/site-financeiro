import yfinance as yf
import sqlite3
import os
import pandas as pd
from collections import defaultdict

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

TICKERS_US = ["AAPL", "AMZN", "META", "TSLA", "MSFT"]

def salvar_empresa(ticker, info):
    """Registra a empresa na tabela empresas"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO empresas (ticker, nome, setor, bolsa, moeda)
        VALUES (?, ?, ?, ?, ?)
    """, (
        ticker,
        info.get("longName", ticker),
        info.get("sector", ""),
        info.get("exchange", "NASDAQ"),
        "USD"
    ))
    conn.commit()
    conn.close()

def upsert_financeiro(c, ticker, ano, fonte, campos):
    c.execute("""
        INSERT OR IGNORE INTO financeiros_anuais (ticker, ano, fonte, moeda)
        VALUES (?, ?, ?, 'USD')
    """, (ticker, ano, fonte))
    for coluna, valor in campos.items():
        if valor is not None:
            c.execute(f"""
                UPDATE financeiros_anuais SET {coluna} = ?
                WHERE ticker = ? AND ano = ? AND fonte = ?
            """, (valor, ticker, ano, fonte))

def salvar_financeiros(ticker, dre, balanco, fc):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    anos = set(list(dre.keys()) + list(balanco.keys()) + list(fc.keys()))
    for ano in anos:
        mapa = {}
        mapa.update(dre.get(ano, {}))
        mapa.update(balanco.get(ano, {}))
        mapa.update(fc.get(ano, {}))
        if mapa:
            upsert_financeiro(c, ticker, ano, "yfinance", mapa)

    conn.commit()
    conn.close()

def salvar_dividendos(ticker, por_ano):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for ano, total in por_ano.items():
        c.execute("""
            INSERT OR REPLACE INTO dividendos_anuais
            (ticker, ano, fonte, dividendo_por_acao)
            VALUES (?, ?, ?, ?)
        """, (ticker, ano, "yfinance", total))
    conn.commit()
    conn.close()

def salvar_precos(ticker, por_ano):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for ano, vals in por_ano.items():
        c.execute("""
            INSERT OR REPLACE INTO precos_anuais
            (ticker, ano, fonte, preco_min, preco_max, preco_medio)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker, ano, "yfinance",
              vals["preco_min"], vals["preco_max"], vals["preco_medio"]))
    conn.commit()
    conn.close()

def extrair_valor(df, campo):
    """Extrai valor de um DataFrame do yfinance (income_stmt/balance_sheet/cashflow)"""
    for nome in campo if isinstance(campo, list) else [campo]:
        if nome in df.index:
            return df.loc[nome]
    return pd.Series(dtype=float)

def coletar_empresa(ticker):
    print(f"\n🇺🇸 Coletando {ticker}...")
    acao = yf.Ticker(ticker)

    # Info geral
    try:
        info = acao.info
        salvar_empresa(ticker, info)
        print(f"   ✅ Empresa: {info.get('longName', ticker)}")
    except:
        info = {}

    # ── DRE ──────────────────────────────────────────────────────────────
    dre = {}
    try:
        inc = acao.income_stmt  # colunas = datas, linhas = campos
        if inc is not None and not inc.empty:
            for col in inc.columns:
                ano = col.year
                dre[ano] = {
                    "receita_liquida":  _val(inc, col, ["Total Revenue"]),
                    "lucro_bruto":      _val(inc, col, ["Gross Profit"]),
                    "ebitda":           _val(inc, col, ["EBITDA", "Normalized EBITDA"]),
                    "ebit":             _val(inc, col, ["EBIT", "Operating Income"]),
                    "lucro_liquido":    _val(inc, col, ["Net Income", "Net Income Common Stockholders"]),
                    "desp_financeiras": _val(inc, col, ["Interest Expense"]),
                    "ir_csll":          _val(inc, col, ["Tax Provision"]),
                }
            print(f"   ✅ DRE: {len(dre)} anos ({min(dre)}-{max(dre)})")
    except Exception as e:
        print(f"   ⚠️ DRE: {e}")

    # ── Balanço ───────────────────────────────────────────────────────────
    balanco = {}
    try:
        bal = acao.balance_sheet
        if bal is not None and not bal.empty:
            for col in bal.columns:
                ano = col.year
                balanco[ano] = {
                    "ativo_total":        _val(bal, col, ["Total Assets"]),
                    "ativo_circulante":   _val(bal, col, ["Current Assets"]),
                    "caixa":              _val(bal, col, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
                    "contas_receber":     _val(bal, col, ["Accounts Receivable", "Net Receivables"]),
                    "estoques":           _val(bal, col, ["Inventory"]),
                    "divida_bruta":       _val(bal, col, ["Total Debt"]),
                    "divida_liquida":     _val(bal, col, ["Net Debt"]),
                    "patrimonio_liquido": _val(bal, col, ["Stockholders Equity", "Total Stockholders Equity"]),
                }
            print(f"   ✅ Balanço: {len(balanco)} anos")
    except Exception as e:
        print(f"   ⚠️ Balanço: {e}")

    # ── Fluxo de Caixa ────────────────────────────────────────────────────
    fc = {}
    try:
        cf = acao.cashflow
        if cf is not None and not cf.empty:
            for col in cf.columns:
                ano = col.year
                fc[ano] = {
                    "fco":              _val(cf, col, ["Operating Cash Flow", "Cash From Operations"]),
                    "capex":            _val(cf, col, ["Capital Expenditure"]),
                    "fcf":              _val(cf, col, ["Free Cash Flow"]),
                    "fci":              _val(cf, col, ["Investing Cash Flow"]),
                    "fcf_financiamento":_val(cf, col, ["Financing Cash Flow"]),
                }
            print(f"   ✅ Fluxo de Caixa: {len(fc)} anos")
    except Exception as e:
        print(f"   ⚠️ FC: {e}")

    salvar_financeiros(ticker, dre, balanco, fc)

    # ── Dividendos ────────────────────────────────────────────────────────
    try:
        divs = acao.dividends
        if divs is not None and len(divs) > 0:
            por_ano = defaultdict(float)
            for data, val in divs.items():
                try:    ano = data.year
                except: ano = int(str(data)[:4])
                por_ano[ano] += float(val)
            salvar_dividendos(ticker, dict(por_ano))
            print(f"   ✅ Dividendos: {len(por_ano)} anos")
        else:
            print(f"   ℹ️ Dividendos: sem histórico (ex: TSLA, META)")
    except Exception as e:
        print(f"   ⚠️ Dividendos: {e}")

    # ── Preços ────────────────────────────────────────────────────────────
    try:
        hist = acao.history(period="max")
        if hist is not None and not hist.empty:
            try:    hist.index = hist.index.tz_localize(None)
            except: hist.index = pd.to_datetime(hist.index).tz_localize(None)
            hist["ano"] = hist.index.year
            por_ano = {}
            for ano, grupo in hist.groupby("ano"):
                por_ano[ano] = {
                    "preco_min":   round(grupo["Low"].min(), 4),
                    "preco_max":   round(grupo["High"].max(), 4),
                    "preco_medio": round(grupo["Close"].mean(), 4),
                }
            salvar_precos(ticker, por_ano)
            anos_p = sorted(por_ano.keys())
            print(f"   ✅ Preços: {len(por_ano)} anos ({min(anos_p)}-{max(anos_p)})")
    except Exception as e:
        print(f"   ⚠️ Preços: {e}")

def _val(df, col, nomes):
    """Pega o primeiro campo disponível de uma coluna do DataFrame"""
    for nome in nomes:
        if nome in df.index:
            v = df.loc[nome, col]
            if pd.notna(v):
                return float(v)
    return None

if __name__ == "__main__":
    import banco
    banco.criar_banco()

    for ticker in TICKERS_US:
        coletar_empresa(ticker)

    print("\n✅ Coleta US finalizada!")
