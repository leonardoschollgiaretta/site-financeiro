"""
acoes.py — consultas (só leitura) ao banco financeiro (fundamentos das ações).

Respeita a prioridade de fontes do ranker.py (manual > investsite > yfinance):
para cada ticker/ano, usa a melhor fonte disponível.
"""
import pandas as pd

from lib.db import conn_financeiro

FONTE_PRIO = ["manual", "investsite", "statusinvest", "yfinance"]
ANOS = [2021, 2022, 2023, 2024, 2025]


def empresas(considerar=True):
    """Lista de empresas (ticker, nome, setor). considerar=True exclui as marcadas DESCONSIDERAR."""
    where = ""
    if considerar:
        where = "WHERE considerar IS NULL OR considerar <> 'DESCONSIDERAR'"
    with conn_financeiro() as c:
        return pd.read_sql_query(
            f"SELECT ticker, nome, setor FROM empresas {where} ORDER BY ticker", c)


def tickers():
    return empresas()["ticker"].tolist()


def _melhor_fonte_sql():
    """Expressão CASE pra priorizar fonte (menor número = melhor)."""
    casos = " ".join(
        f"WHEN fonte='{f}' THEN {i}" for i, f in enumerate(FONTE_PRIO))
    return f"CASE {casos} ELSE 99 END"


def financeiros(ticker):
    """Série anual de um ticker, escolhendo a melhor fonte por ano. DataFrame indexado por ano."""
    prio = _melhor_fonte_sql()
    sql = f"""
        SELECT f.*
        FROM financeiros_anuais f
        JOIN (
            SELECT ano, MIN({prio}) AS melhor
            FROM financeiros_anuais WHERE ticker = ?
            GROUP BY ano
        ) b ON f.ano = b.ano AND {prio} = b.melhor
        WHERE f.ticker = ?
        ORDER BY f.ano
    """
    with conn_financeiro() as c:
        df = pd.read_sql_query(sql, c, params=[ticker, ticker])
    return df


def preco_atual(ticker):
    with conn_financeiro() as c:
        r = c.execute(
            "SELECT preco, data_fechamento, variacao_pct FROM preco_atual WHERE ticker=?",
            [ticker]).fetchone()
    return r  # (preco, data, var%) ou None


def info_empresa(ticker):
    with conn_financeiro() as c:
        r = c.execute(
            "SELECT nome, setor, acoes_free, acoes_total FROM empresas WHERE ticker=?",
            [ticker]).fetchone()
    return r


def indicadores_ano(ticker, ano=2025):
    """Calcula indicadores-chave de um ticker num ano. Retorna dict (None se faltar)."""
    df = financeiros(ticker)
    if df.empty or ano not in df["ano"].values:
        return {}
    linha = df[df["ano"] == ano].iloc[0]

    def v(campo):
        x = linha.get(campo)
        return float(x) if x is not None and not pd.isna(x) else None

    def safe(a, b):
        return a / b if (a is not None and b not in (None, 0)) else None

    rec = v("receita_liquida")
    ll = v("lucro_liquido")
    lb = v("lucro_bruto")
    pl = v("patrimonio_liquido")
    ebitda = v("ebitda")
    dl = v("divida_liquida")

    info = info_empresa(ticker)
    acoes = float(info[3]) if info and info[3] else None  # acoes_total
    pa = preco_atual(ticker)
    preco = float(pa[0]) if pa and pa[0] else None
    mkt = preco * acoes if (preco and acoes) else None

    return {
        "Preço": preco,
        "Market Cap": mkt,
        "Receita líquida": rec,
        "Lucro líquido": ll,
        "EBITDA": ebitda,
        "Patrimônio líquido": pl,
        "Margem bruta": safe(lb, rec),
        "Margem líquida": safe(ll, rec),
        "ROE": safe(ll, pl),
        "P/L": safe(mkt, ll),
        "P/VP": safe(mkt, pl),
        "Dív. líq. / EBITDA": safe(dl, ebitda),
    }


def serie_historica(ticker, campos=("receita_liquida", "lucro_liquido", "ebitda")):
    """Série anual de campos escolhidos. DataFrame: ano nas linhas, campos nas colunas."""
    df = financeiros(ticker)
    if df.empty:
        return df
    cols = ["ano"] + [c for c in campos if c in df.columns]
    return df[cols].set_index("ano")


def dividendos_anuais(ticker):
    with conn_financeiro() as c:
        return pd.read_sql_query(
            "SELECT ano, dividendo_por_acao FROM dividendos_anuais "
            "WHERE ticker=? ORDER BY ano", c, params=[ticker])


def tabela_indicadores(ano=2025):
    """Indicadores de TODAS as ações num ano, em um único DataFrame (para triagem).

    Uma linha por ticker; colunas = indicadores. Valores None quando faltam.
    """
    linhas = []
    for tk in tickers():
        ind = indicadores_ano(tk, ano)
        if not ind:
            continue
        linha = {"Ticker": tk}
        linha.update(ind)
        linhas.append(linha)
    if not linhas:
        return pd.DataFrame()
    return pd.DataFrame(linhas)
