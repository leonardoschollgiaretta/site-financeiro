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


# Estrutura das demonstrações (mesmos rótulos/contas do relatorio.py).
# Cada item: (rótulo, campo). Campo None = linha calculada (tratada à parte).
DRE_LINHAS = [
    ("Receita Líquida", "receita_liquida"),
    ("CPV / CMV", "custo_receita"),
    ("Lucro Bruto", "lucro_bruto"),
    ("Despesas Operacionais (SG&A)", "despesas_operacionais"),
    ("Depreciação & Amortização", "depreciacao_amortizacao"),
    ("EBIT", "ebit"),
    ("EBITDA", "ebitda"),
    ("Receitas Financeiras", "receitas_financeiras"),
    ("Despesas Financeiras", "despesas_financeiras"),
    ("Resultado Financeiro Líq.", "resultado_financeiro"),
    ("EBT", "ebt"),
    ("IR e CSLL", "ir_csll"),
    ("Lucro Líquido", "lucro_liquido"),
]

BALANCO_LINHAS = [
    ("Caixa + Aplicações Fin.", "caixa"),
    ("Contas a Receber", "contas_receber"),
    ("Estoques", "estoques"),
    ("TOTAL ATIVO CIRCULANTE", "ativo_circulante"),
    ("Imobilizado (líquido)", "imobilizado"),
    ("Intangíveis", "intangivel"),
    ("Investimentos", "investimentos"),
    ("Outros Ativos NC", "outros_ativos_nc"),
    ("TOTAL ATIVO NÃO CIRC.", "ativo_nao_circulante"),
    ("TOTAL DO ATIVO", "ativo_total"),
    ("Empréstimos CP", "emprestimos_cp"),
    ("Fornecedores", "fornecedores"),
    ("TOTAL PASSIVO CIRCULANTE", "passivo_circulante"),
    ("Empréstimos LP", "emprestimos_lp"),
    ("Debêntures", "debentures"),
    ("TOTAL PASSIVO NÃO CIRC.", "passivo_nao_circulante"),
    ("Capital Social", "capital_social"),
    ("Reservas de Lucro", "reservas_lucro"),
    ("Lucros / Prejuízos Acum.", "lucros_acumulados"),
    ("TOTAL PATRIMÔNIO LÍQUIDO", "patrimonio_liquido"),
    ("Dívida Bruta", "divida_bruta"),
    ("Dívida Líquida", "divida_liquida"),
]

DFC_LINHAS = [
    ("Lucro Líquido do Período", "lucro_liquido"),
    ("(+) D&A", "depreciacao_amortizacao"),
    ("FLUXO CAIXA OPERACIONAL", "fco"),
    ("CAPEX", "capex"),
    ("Venda de Ativos", "venda_ativos"),
    ("Aquisições / Participações", "aquisicoes"),
    ("FLUXO CAIXA INVESTIMENTOS", "fci"),
    ("Captações", "captacoes"),
    ("Pagamento de Dívidas", "pagamento_dividas"),
    ("Recompra de Ações", "recompra_acoes"),
    ("Dividendos / JCP Pagos", "dividendos_pagos"),
    ("FLUXO CAIXA FINANCIAMENTOS", "fcf_financiamento"),
    ("Variação Líquida de Caixa", "variacao_caixa"),
    ("Caixa Inicial", "caixa_inicial"),
    ("Caixa Final", "caixa_final"),
    ("Free Cash Flow (FCO−CAPEX)", "fcl"),
]


def demonstracao(ticker, linhas, em_milhares=True):
    """Monta uma demonstração no formato relatório: contas nas linhas, anos nas colunas.

    `linhas` é uma das listas DRE_LINHAS / BALANCO_LINHAS / DFC_LINHAS.
    Valores em R$ mil (em_milhares=True) como no relatorio.py.
    """
    df = financeiros(ticker)
    if df.empty:
        return pd.DataFrame()
    anos = sorted(df["ano"].unique())
    por_ano = {int(r["ano"]): r for _, r in df.iterrows()}

    dados = {}
    for rotulo, campo in linhas:
        valores = []
        for ano in anos:
            linha = por_ano.get(int(ano))
            v = None
            if linha is not None and campo in linha.index:
                x = linha[campo]
                if x is not None and not pd.isna(x):
                    v = float(x) / 1000 if em_milhares else float(x)
            valores.append(v)
        dados[rotulo] = valores

    out = pd.DataFrame(dados, index=[int(a) for a in anos]).T
    out.index.name = "Conta (R$ mil)" if em_milhares else "Conta (R$)"
    return out


def cotacao_e_marketcap(ticker):
    """Cruza o banco financeiro para um ticker (que pode ser ON ou PN).

    Acha o registro consolidado da empresa (acoes_total já soma ON+PN),
    pega o último preço disponível e calcula market cap = preço × ações totais.

    Retorna dict: {nome, ticker_dados, preco, data_preco, atualizado_em,
                   acoes_total, market_cap, ticker_on, ticker_pn} ou None.
    """
    tk = ticker.upper()
    with conn_financeiro() as c:
        # 1) registro com dados de ações (direto, ou via ticker_on/ticker_pn)
        row = c.execute(
            "SELECT ticker, nome, acoes_total, acoes_atualizadas_em, ticker_on, ticker_pn "
            "FROM empresas WHERE ticker=? AND acoes_total IS NOT NULL", [tk]).fetchone()
        if not row:
            row = c.execute(
                "SELECT ticker, nome, acoes_total, acoes_atualizadas_em, ticker_on, ticker_pn "
                "FROM empresas WHERE (ticker_on=? OR ticker_pn=?) "
                "AND acoes_total IS NOT NULL LIMIT 1", [tk, tk]).fetchone()
        if not row:
            return None
        ticker_dados, nome, acoes_total, acoes_em, t_on, t_pn = row

        # 2) preço: tenta o ticker pedido; senão o ticker_dados; senão ON/PN
        preco = data_preco = atualizado = None
        for cand in [tk, ticker_dados, t_pn, t_on]:
            if not cand:
                continue
            p = c.execute(
                "SELECT preco, data_fechamento, atualizado_em FROM preco_atual WHERE ticker=?",
                [cand]).fetchone()
            if p and p[0]:
                preco, data_preco, atualizado = float(p[0]), p[1], p[2]
                ticker_preco = cand
                break
        else:
            ticker_preco = None

    acoes_total = float(acoes_total) if acoes_total else None
    market_cap = preco * acoes_total if (preco and acoes_total) else None
    return {
        "nome": nome, "ticker_dados": ticker_dados, "ticker_preco": ticker_preco,
        "preco": preco, "data_preco": data_preco, "atualizado_em": atualizado,
        "acoes_total": acoes_total, "market_cap": market_cap,
        "ticker_on": t_on, "ticker_pn": t_pn,
    }


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
