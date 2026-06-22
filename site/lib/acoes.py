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


# ===================== trimestrais US (SEC EDGAR) =====================
# Diferente do BR: os valores US já vêm ISOLADOS por trimestre (não YTD) e em USD.

def tickers_us():
    """Lista de tickers com trimestrais US no banco."""
    with conn_financeiro() as c:
        try:
            df = pd.read_sql_query(
                "SELECT DISTINCT ticker FROM financeiros_trimestrais_us ORDER BY ticker", c)
        except Exception:
            return []
    return df["ticker"].tolist()


def tem_trimestrais_us(ticker):
    with conn_financeiro() as c:
        try:
            r = c.execute("SELECT 1 FROM financeiros_trimestrais_us WHERE ticker=? LIMIT 1",
                          [ticker.upper()]).fetchone()
        except Exception:
            return False
    return r is not None


def trimestrais_us(ticker, campos):
    """Série trimestral US (já isolada) de um ticker. DataFrame com 'periodo'."""
    cols = ", ".join(["ano", "trimestre"] + list(campos))
    sql = (f"SELECT {cols} FROM financeiros_trimestrais_us "
           "WHERE ticker=? ORDER BY ano, trimestre")
    with conn_financeiro() as c:
        try:
            df = pd.read_sql_query(sql, c, params=[ticker.upper()])
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    df["periodo"] = df["ano"].astype(str) + "T" + df["trimestre"].astype(str)
    return df


# linhas das demonstrações US (campos existentes na tabela financeiros_trimestrais_us)
DRE_US_LINHAS = [
    ("Receita Líquida", "receita_liquida"),
    ("Custo (CPV)", "custo_receita"),
    ("Lucro Bruto", "lucro_bruto"),
    ("Despesas Operacionais", "despesas_operacionais"),
    ("EBIT (oper. income)", "ebit"),
    ("Receitas Financeiras", "receitas_financeiras"),
    ("Despesas Financeiras", "despesas_financeiras"),
    ("EBT (pretax)", "ebt"),
    ("Impostos", "ir_csll"),
    ("Lucro Líquido", "lucro_liquido"),
    ("Depr. & Amort.", "depreciacao_amortizacao"),
]
BALANCO_US_LINHAS = [
    ("Caixa e Equivalentes", "caixa"),
    ("Contas a Receber", "contas_receber"),
    ("Estoques", "estoques"),
    ("TOTAL ATIVO CIRCULANTE", "ativo_circulante"),
    ("Imobilizado", "imobilizado"),
    ("Intangível/Goodwill", "intangivel"),
    ("TOTAL ATIVO NÃO CIRC.", "ativo_nao_circulante"),
    ("TOTAL DO ATIVO", "ativo_total"),
    ("Passivo Circulante", "passivo_circulante"),
    ("Dívida de Longo Prazo", "divida_lp"),
    ("TOTAL DO PASSIVO", "passivo_total"),
    ("TOTAL PATRIMÔNIO LÍQUIDO", "patrimonio_liquido"),
]
DFC_US_LINHAS = [
    ("Fluxo Caixa Operacional", "fco"),
    ("Fluxo Caixa Investimentos", "fci"),
    ("Fluxo Caixa Financiamentos", "fcf_financiamento"),
    ("CAPEX", "capex"),
]


def demonstracao_trimestral_us(ticker, linhas, em_milhares=True):
    """Demonstração trimestral US no formato relatório (contas×períodos).

    Valores já são isolados por trimestre. em_milhares=True divide por 1000
    (mantém consistência com a versão BR, que está em R$ mil).
    """
    campos = [c for _, c in linhas]
    df = trimestrais_us(ticker, campos=tuple(campos))
    if df.empty:
        return pd.DataFrame()
    df = df.sort_values(["ano", "trimestre"]).reset_index(drop=True)
    div = 1000.0 if em_milhares else 1.0
    dados = {}
    for rotulo, campo in linhas:
        serie = []
        for v in df[campo]:
            serie.append(None if (v is None or pd.isna(v)) else float(v) / div)
        dados[rotulo] = serie
    out = pd.DataFrame(dados, index=df["periodo"]).T
    out.index.name = "Conta (US$ mil)" if em_milhares else "Conta (US$)"
    return out


# ===================== histórico trimestral (CVM ITR/DFP) =====================

def tem_trimestrais(ticker):
    """True se há dados trimestrais para o ticker."""
    with conn_financeiro() as c:
        try:
            r = c.execute("SELECT 1 FROM financeiros_trimestrais WHERE ticker=? LIMIT 1",
                          [ticker.upper()]).fetchone()
        except Exception:
            return False
    return r is not None


def trimestrais(ticker, campos=("receita_liquida", "lucro_liquido")):
    """Série trimestral (acumulada no ano) de um ticker.

    Retorna DataFrame com coluna 'periodo' ('2025T3') e os campos pedidos.
    Vazio se não houver tabela/dados.
    """
    cols = ", ".join(["ano", "trimestre"] + list(campos))
    sql = (f"SELECT {cols} FROM financeiros_trimestrais "
           "WHERE ticker=? ORDER BY ano, trimestre")
    with conn_financeiro() as c:
        try:
            df = pd.read_sql_query(sql, c, params=[ticker.upper()])
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    df["periodo"] = df["ano"].astype(str) + "T" + df["trimestre"].astype(str)
    return df


def trimestrais_isolados(ticker, campo):
    """Converte a série ACUMULADA no ano em valor ISOLADO de cada trimestre.

    Ex.: receita do T3 isolado = YTD(T3) − YTD(T2). T1 isolado = YTD(T1).
    Só faz sentido para contas de fluxo (DRE/DFC), não para saldos de balanço.
    """
    df = trimestrais(ticker, campos=(campo,))
    if df.empty:
        return df
    df = df.sort_values(["ano", "trimestre"]).copy()
    df["isolado"] = None
    for ano, g in df.groupby("ano"):
        prev = 0.0
        for idx in g.index:
            ytd = df.at[idx, campo]
            df.at[idx, "isolado"] = (ytd - prev) if ytd is not None else None
            prev = ytd if ytd is not None else prev
    return df[["periodo", "ano", "trimestre", campo, "isolado"]]


# --- estrutura das demonstrações TRIMESTRAIS (só campos que existem na tabela) ---
DRE_TRI_LINHAS = [
    ("Receita Líquida", "receita_liquida"),
    ("CPV / CMV", "custo_receita"),
    ("Lucro Bruto", "lucro_bruto"),
    ("Despesas/Receitas Operacionais", "despesas_operacionais"),
    ("EBIT (result. antes do fin.)", "ebit"),
    ("Receitas Financeiras", "receitas_financeiras"),
    ("Despesas Financeiras", "despesas_financeiras"),
    ("Resultado Financeiro", "resultado_financeiro"),
    ("EBT (antes dos tributos)", "ebt"),
    ("IR e CSLL", "ir_csll"),
    ("Lucro Líquido", "lucro_liquido"),
]
BALANCO_TRI_LINHAS = [
    ("Caixa e Equivalentes", "caixa"),
    ("Contas a Receber", "contas_receber"),
    ("Estoques", "estoques"),
    ("TOTAL ATIVO CIRCULANTE", "ativo_circulante"),
    ("Investimentos", "investimentos"),
    ("Imobilizado", "imobilizado"),
    ("Intangível", "intangivel"),
    ("TOTAL ATIVO NÃO CIRC.", "ativo_nao_circulante"),
    ("TOTAL DO ATIVO", "ativo_total"),
    ("Fornecedores", "fornecedores"),
    ("Empréstimos CP", "emprestimos_cp"),
    ("TOTAL PASSIVO CIRCULANTE", "passivo_circulante"),
    ("Empréstimos LP", "emprestimos_lp"),
    ("TOTAL PASSIVO NÃO CIRC.", "passivo_nao_circulante"),
    ("Capital Social", "capital_social"),
    ("Reservas de Lucro", "reservas_lucro"),
    ("Lucros/Prejuízos Acum.", "lucros_acumulados"),
    ("TOTAL PATRIMÔNIO LÍQUIDO", "patrimonio_liquido"),
]
DFC_TRI_LINHAS = [
    ("FLUXO CAIXA OPERACIONAL", "fco"),
    ("FLUXO CAIXA INVESTIMENTOS", "fci"),
    ("FLUXO CAIXA FINANCIAMENTOS", "fcf_financiamento"),
    ("Caixa Inicial", "caixa_inicial"),
    ("Caixa Final", "caixa_final"),
]

# contas de FLUXO (DRE/DFC) podem ser isoladas por trimestre; balanço é saldo (não)
_CONTAS_FLUXO = {c for _, c in DRE_TRI_LINHAS + DFC_TRI_LINHAS}


def demonstracao_trimestral(ticker, linhas, isolar=False, em_milhares=True):
    """Monta uma demonstração trimestral no formato relatório.

    Linhas = contas (rótulos), colunas = períodos ('2025T3').
    `linhas` é uma das listas *_TRI_LINHAS.
    isolar=True converte contas de FLUXO de YTD->trimestre isolado (não toca balanço).
    """
    campos = [c for _, c in linhas]
    df = trimestrais(ticker, campos=tuple(campos))
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(["ano", "trimestre"]).reset_index(drop=True)
    if isolar:
        for campo in campos:
            if campo not in _CONTAS_FLUXO:
                continue
            for _, g in df.groupby("ano"):
                prev = 0.0
                for idx in g.index:
                    ytd = df.at[idx, campo]
                    df.at[idx, campo] = (ytd - prev) if ytd is not None else None
                    prev = ytd if ytd is not None else prev

    div = 1000.0 if em_milhares else 1.0
    dados = {}
    for rotulo, campo in linhas:
        serie = []
        for v in df[campo]:
            serie.append(None if (v is None or pd.isna(v)) else float(v) / div)
        dados[rotulo] = serie
    out = pd.DataFrame(dados, index=df["periodo"]).T
    out.index.name = "Conta (R$ mil)" if em_milhares else "Conta (R$)"
    return out


# ===================== ficha estilo Investidor10 =====================

def historico_preco(ticker):
    """Faixa de preço anual (mín/máx/médio) 2020-2026. DataFrame indexado por ano."""
    with conn_financeiro() as c:
        df = pd.read_sql_query(
            "SELECT ano, preco_min, preco_max, preco_medio FROM precos_anuais "
            "WHERE ticker=? ORDER BY ano", c, params=[ticker.upper()])
    return df.set_index("ano") if not df.empty else df


def proventos_pagamentos(ticker, desde_ano=None):
    """Pagamentos detalhados de proventos (data-com, data-pgto, tipo, valor)."""
    sql = ("SELECT data_com, data_pgto, tipo, valor FROM dividendos_pagamentos "
           "WHERE ticker=?")
    params = [ticker.upper()]
    if desde_ano:
        sql += " AND data_com >= ?"
        params.append(f"{desde_ano}-01-01")
    sql += " ORDER BY data_com DESC, data_pgto DESC"
    with conn_financeiro() as c:
        return pd.read_sql_query(sql, c, params=params)


def proventos_por_ano(ticker):
    """Soma de proventos por ano (data-com). DataFrame: ano -> total por ação."""
    df = proventos_pagamentos(ticker)
    if df.empty:
        return df
    df = df.copy()
    df["ano"] = pd.to_datetime(df["data_com"], errors="coerce").dt.year
    out = df.dropna(subset=["ano"]).groupby("ano")["valor"].sum()
    out.index = out.index.astype(int)
    return out


def dividend_yield(ticker):
    """DY = proventos por ação dos últimos 12 meses / preço atual. Retorna dict.

    Usa a data-com dos pagamentos para somar os proventos do último ano e o
    preço de preco_atual. None se faltar preço.
    """
    pa = preco_atual(ticker)
    preco = float(pa[0]) if pa and pa[0] else None
    df = proventos_pagamentos(ticker)
    prov_12m = prov_ano = None
    if not df.empty:
        datas = pd.to_datetime(df["data_com"], errors="coerce")
        ref = datas.max()
        if pd.notna(ref):
            corte = ref - pd.Timedelta(days=365)
            prov_12m = float(df.loc[datas >= corte, "valor"].sum())
        # último ano-calendário completo de proventos
        por_ano = proventos_por_ano(ticker)
        if not por_ano.empty:
            prov_ano = float(por_ano.iloc[-1])
    dy = (prov_12m / preco) if (preco and prov_12m) else None
    return {"preco": preco, "prov_12m": prov_12m,
            "prov_ultimo_ano": prov_ano, "dy": dy}


def evolucao_acoes(ticker):
    """Evolução do nº de ações (total/tesouraria/free) por ano — detecta recompra/diluição."""
    with conn_financeiro() as c:
        df = pd.read_sql_query(
            "SELECT ano, acoes_total, acoes_tesouraria, acoes_free FROM acoes_anuais "
            "WHERE ticker=? ORDER BY ano", c, params=[ticker.upper()])
    return df.set_index("ano") if not df.empty else df


def posicao_na_faixa(ticker):
    """Onde o preço atual está na faixa de 52 semanas (aproximada pelo ano corrente).

    Retorna dict {preco, min, max, pct} — pct=0 no fundo, 1 no topo da faixa.
    """
    hp = historico_preco(ticker)
    pa = preco_atual(ticker)
    preco = float(pa[0]) if pa and pa[0] else None
    if hp.empty or preco is None:
        return None
    ano_ref = hp.index.max()
    lo = float(hp.loc[ano_ref, "preco_min"])
    hi = float(hp.loc[ano_ref, "preco_max"])
    pct = (preco - lo) / (hi - lo) if hi > lo else None
    return {"preco": preco, "min": lo, "max": hi, "ano": int(ano_ref), "pct": pct}


# ===================== ranking de ações (Investidor10) =====================
# Tabela ranking_acoes gravada por financeiro/ranking_investidor10.py (scraping
# da página de rankings do Investidor10). 307 ações da B3 com ~26 indicadores.

# nome da coluna no banco -> rótulo amigável para exibir no site
RANKING_ROTULOS = {
    "ticker": "Ticker", "empresa": "Empresa",
    "valor_mercado": "Valor de Mercado (R$)",
    "patrimonio_liquido": "Patrimônio Líquido (R$)",
    "receita_liquida": "Receita Líquida (R$)",
    "lucro_liquido": "Lucro Líquido (R$)",
    "caixa": "Caixa (R$)", "preco": "Preço Atual (R$)",
    "nota_bh": "Nota Buy&Hold", "p_l": "P/L", "p_vp": "P/VP",
    "dy_12m": "DY 12m (%)", "dy_medio_5a": "DY médio 5a (%)",
    "roe": "ROE (%)", "margem_liquida": "Margem Líquida (%)",
    "div_bruta_pl": "Dív. Bruta / PL",
    "cresc_receita_5a": "Cresc. Receita 5a (%)",
    "cresc_lucro_5a": "Cresc. Lucro 5a (%)",
    "graham_preco": "Preço Justo Graham (R$)", "graham_upside": "Upside Graham (%)",
    "bazin_preco": "Preço-teto Bazin (R$)", "bazin_upside": "Upside Bazin (%)",
    "var_30d": "Variação 30d (%)", "var_12m": "Variação 12m (%)",
    "var_5a": "Variação 5a (%)",
    "setor": "Setor", "subsetor": "Subsetor", "segmento": "Segmento",
}


def tem_ranking():
    """True se a tabela ranking_acoes existe e tem dados."""
    with conn_financeiro() as c:
        try:
            r = c.execute("SELECT 1 FROM ranking_acoes LIMIT 1").fetchone()
        except Exception:
            return False
    return r is not None


def ranking_acoes(renomear=True):
    """Ranking completo (Investidor10) como DataFrame, ordenado por valor de mercado.

    renomear=True usa os rótulos amigáveis (RANKING_ROTULOS) nas colunas.
    """
    with conn_financeiro() as c:
        try:
            df = pd.read_sql_query(
                "SELECT * FROM ranking_acoes ORDER BY valor_mercado DESC", c)
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    if renomear:
        df = df.rename(columns=RANKING_ROTULOS)
    return df


def ranking_atualizado_em():
    """Data (str) da última atualização do ranking, ou None."""
    with conn_financeiro() as c:
        try:
            r = c.execute("SELECT MAX(atualizado_em) FROM ranking_acoes").fetchone()
        except Exception:
            return None
    return r[0] if r else None


# ----- simulador de ranking ponderado (espelha a planilha do usuário) -----
# Cada indicador: (rótulo na tabela, maior_é_melhor?, limite_inf, limite_sup,
# peso%, zera_se_negativo?). Defaults idênticos à aba "Config" do Excel.
RANKING_CONFIG_PADRAO = [
    # rótulo,                      maior_melhor, inf,  sup,  peso, zera_neg
    ("P/L",                        False,        3,    15,   12,   True),
    ("P/VP",                       False,        0.5,  4,    12,   True),
    ("DY 12m (%)",                 True,         4,    15,   3,    False),
    ("DY médio 5a (%)",            True,         3,    12,   11,   False),
    ("ROE (%)",                    True,         10,   30,   14,   True),
    ("Margem Líquida (%)",         True,         8,    30,   12,   True),
    ("Dív. Bruta / PL",            False,        0.2,  2,    12,   True),
    ("Cresc. Receita 5a (%)",      True,         20,   100,  12,   False),
    ("Cresc. Lucro 5a (%)",        True,         20,   100,  12,   False),
]


def _nota_indicador(serie, maior_melhor, inf, sup, zera_neg):
    """Normaliza uma série de valores em nota 0–100 entre [inf, sup] (clamp).

    Espelha a fórmula MEDIAN(0; (v-inf)/(sup-inf)*100; 100) do Excel.
    'Menor é melhor' inverte. zera_neg=True força nota 0 quando o valor é < 0
    (ex.: P/L, ROE, margem negativos não pontuam).
    """
    v = pd.to_numeric(serie, errors="coerce")
    if sup == inf:
        base = pd.Series(0.0, index=v.index)
    elif maior_melhor:
        base = (v - inf) / (sup - inf) * 100
    else:
        base = (sup - v) / (sup - inf) * 100
    base = base.clip(lower=0, upper=100)
    if zera_neg:
        base = base.mask(v < 0, 0.0)
    return base


def ranking_ponderado(config=None, base=None, contribuicao=True):
    """Calcula a nota final ponderada de cada ação e ordena (maior=melhor).

    config: lista no formato de RANKING_CONFIG_PADRAO. Pesos são normalizados
            pela soma (não precisa somar exatamente 100). Indicadores com peso 0
            são ignorados.
    contribuicao: se True (padrão), as colunas 'nota <indicador>' trazem a
            CONTRIBUIÇÃO ponderada de cada indicador (nota 0–100 × peso/total),
            de modo que a soma das colunas = Nota Final, e o máximo de cada
            coluna = o próprio peso do indicador. Se False, traz a nota 0–100 crua.
    Retorna DataFrame: Posição, Ticker, Empresa, Setor, Subsetor, Nota Final,
            + uma coluna por indicador.
    """
    if base is None:
        base = ranking_acoes(renomear=True)
    if base.empty:
        return base
    config = config or RANKING_CONFIG_PADRAO
    usados = [c for c in config if c[4] and c[4] > 0]
    peso_total = sum(c[4] for c in usados) or 1

    notas = pd.DataFrame(index=base.index)
    final = pd.Series(0.0, index=base.index)
    for rotulo, maior, inf, sup, peso, zera in usados:
        if rotulo not in base.columns:
            continue
        n = _nota_indicador(base[rotulo], maior, inf, sup, zera)
        contrib = n.fillna(0) * (peso / peso_total)   # pontos que entram na nota
        notas[f"nota {rotulo}"] = contrib if contribuicao else n
        final += contrib

    out = pd.DataFrame({
        "Ticker": base["Ticker"], "Empresa": base.get("Empresa"),
        "Setor": base.get("Setor"), "Subsetor": base.get("Subsetor"),
        "Nota Final": final.round(2),
    })
    out = pd.concat([out, notas.round(2)], axis=1)
    out = out.sort_values("Nota Final", ascending=False).reset_index(drop=True)
    out.insert(0, "Posição", range(1, len(out) + 1))
    return out


def medias_por_subsetor(base=None, indicadores=None):
    """Médias de indicadores por subsetor, PONDERADAS pelo valor de mercado.

    Espelha a aba 'Médias Subsetor' do Excel.
    """
    if base is None:
        base = ranking_acoes(renomear=True)
    if base.empty:
        return base
    if indicadores is None:
        indicadores = ["P/L", "P/VP", "DY 12m (%)", "DY médio 5a (%)", "ROE (%)",
                       "Margem Líquida (%)", "Dív. Bruta / PL",
                       "Cresc. Receita 5a (%)", "Cresc. Lucro 5a (%)"]
    df = base.copy()
    mc = pd.to_numeric(df["Valor de Mercado (R$)"], errors="coerce").fillna(0)
    df["_mc"] = mc

    linhas = []
    for sub, g in df.groupby("Subsetor"):
        if not sub:
            continue
        reg = {"Subsetor": sub, "Nº Empresas": len(g),
               "Market Cap (R$)": g["_mc"].sum()}
        for ind in indicadores:
            vals = pd.to_numeric(g[ind], errors="coerce")
            w = g["_mc"].where(vals.notna(), 0)
            reg[ind] = (vals.fillna(0) * w).sum() / w.sum() if w.sum() else None
        linhas.append(reg)
    out = pd.DataFrame(linhas).sort_values("Market Cap (R$)", ascending=False)
    return out.reset_index(drop=True)


# ===================== ranking de ações US (S&P 500, yfinance) =====================
# Tabela ranking_acoes_us gravada por financeiro/ranking_us.py.

US_ROTULOS = {
    "ticker": "Ticker", "empresa": "Empresa", "setor": "Setor", "industria": "Indústria",
    "preco": "Preço (US$)", "valor_mercado": "Valor de Mercado (US$)",
    "p_l": "P/L", "p_l_fwd": "P/L proj.", "p_vp": "P/VP",
    "dy_12m": "DY 12m (%)", "dy_medio_5a": "DY médio 5a (%)", "roe": "ROE (%)",
    "margem_liquida": "Margem Líquida (%)", "margem_bruta": "Margem Bruta (%)",
    "margem_operacional": "Margem Operacional (%)", "div_pl": "Dívida / PL",
    "cresc_receita": "Cresc. Receita (%)", "cresc_lucro": "Cresc. Lucro (%)",
    "receita": "Receita (US$)", "lucro_liquido": "Lucro Líquido (US$)",
    "ebitda": "EBITDA (US$)", "eps": "LPA (US$)", "beta": "Beta",
    "ev_ebitda": "EV/EBITDA", "ev_receita": "EV/Receita", "p_s": "P/S",
    "peg": "PEG", "payout": "Payout (%)", "roa": "ROA (%)",
    "margem_ebitda": "Margem EBITDA (%)", "liquidez_corrente": "Liquidez Corrente",
    "liquidez_seca": "Liquidez Seca", "caixa_total": "Caixa (US$)",
    "divida_total": "Dívida Total (US$)", "fcl": "Free Cash Flow (US$)",
    "fco": "Fluxo Caixa Oper. (US$)", "vpa": "VPA (US$)",
    "receita_por_acao": "Receita/Ação (US$)", "var_12m": "Variação 12m (%)",
    "preco_alvo": "Preço-alvo (US$)", "upside_alvo": "Upside p/ alvo (%)",
    "n_analistas": "Nº Analistas", "recomendacao": "Recomendação",
    "pct_institucional": "% Institucional",
}

# config padrão do ranking US (limites adaptados ao mercado americano).
# Os indicadores extras entram com PESO 0 (não afetam a nota até você ligar,
# definindo um peso > 0 no simulador). Direção/limites já vêm sugeridos.
RANKING_CONFIG_PADRAO_US = [
    # rótulo,                  maior_melhor, inf,  sup,  peso, zera_neg
    ("P/L",                    False,        8,    35,   14,   True),
    ("P/VP",                   False,        1,    10,   10,   True),
    ("EV/EBITDA",              False,        5,    25,   0,    True),
    ("P/S",                    False,        1,    10,   0,    True),
    ("PEG",                    False,        0.5,  3,    0,    True),
    ("DY 12m (%)",             True,         0.5,  5,    6,    False),
    ("Payout (%)",             True,         20,   70,   0,    False),
    ("ROE (%)",                True,         10,   40,   16,   True),
    ("ROA (%)",                True,         3,    20,   0,    True),
    ("Margem Líquida (%)",     True,         5,    35,   14,   True),
    ("Margem Operacional (%)", True,         5,    35,   10,   True),
    ("Margem EBITDA (%)",      True,         10,   45,   0,    True),
    ("Dívida / PL",            False,        0.1,  2,    10,   True),
    ("Liquidez Corrente",      True,         1,    3,    0,    True),
    ("Cresc. Receita (%)",     True,         0,    30,   10,   False),
    ("Cresc. Lucro (%)",       True,         0,    40,   10,   False),
    ("Upside p/ alvo (%)",     True,         0,    40,   0,    False),
]


def tem_ranking_us():
    with conn_financeiro() as c:
        try:
            r = c.execute("SELECT 1 FROM ranking_acoes_us LIMIT 1").fetchone()
        except Exception:
            return False
    return r is not None


def ranking_acoes_us(renomear=True):
    """Ranking US completo (S&P 500) como DataFrame, ordenado por valor de mercado."""
    with conn_financeiro() as c:
        try:
            df = pd.read_sql_query(
                "SELECT * FROM ranking_acoes_us ORDER BY valor_mercado DESC", c)
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    return df.rename(columns=US_ROTULOS) if renomear else df


def ranking_us_atualizado_em():
    with conn_financeiro() as c:
        try:
            r = c.execute("SELECT MAX(atualizado_em) FROM ranking_acoes_us").fetchone()
        except Exception:
            return None
    return r[0] if r else None


def ranking_ponderado_us(config=None, base=None, contribuicao=True):
    """Igual a ranking_ponderado(), mas para a base US. Usa o mesmo motor de notas."""
    if base is None:
        base = ranking_acoes_us(renomear=True)
    if base.empty:
        return base
    config = config or RANKING_CONFIG_PADRAO_US
    usados = [c for c in config if c[4] and c[4] > 0]
    peso_total = sum(c[4] for c in usados) or 1

    notas = pd.DataFrame(index=base.index)
    final = pd.Series(0.0, index=base.index)
    for rotulo, maior, inf, sup, peso, zera in usados:
        if rotulo not in base.columns:
            continue
        n = _nota_indicador(base[rotulo], maior, inf, sup, zera)
        contrib = n.fillna(0) * (peso / peso_total)
        notas[f"nota {rotulo}"] = contrib if contribuicao else n
        final += contrib

    out = pd.DataFrame({
        "Ticker": base["Ticker"], "Empresa": base.get("Empresa"),
        "Setor": base.get("Setor"), "Indústria": base.get("Indústria"),
        "Nota Final": final.round(2),
    })
    out = pd.concat([out, notas.round(2)], axis=1)
    out = out.sort_values("Nota Final", ascending=False).reset_index(drop=True)
    out.insert(0, "Posição", range(1, len(out) + 1))
    return out


def medias_por_setor_us(base=None, indicadores=None):
    """Médias de indicadores por setor (US), ponderadas pelo valor de mercado."""
    if base is None:
        base = ranking_acoes_us(renomear=True)
    if base.empty:
        return base
    if indicadores is None:
        indicadores = ["P/L", "P/VP", "DY 12m (%)", "ROE (%)", "Margem Líquida (%)",
                       "Margem Operacional (%)", "Dívida / PL",
                       "Cresc. Receita (%)", "Cresc. Lucro (%)"]
    df = base.copy()
    df["_mc"] = pd.to_numeric(df["Valor de Mercado (US$)"], errors="coerce").fillna(0)
    linhas = []
    for setor, g in df.groupby("Setor"):
        if not setor:
            continue
        reg = {"Setor": setor, "Nº Empresas": len(g),
               "Market Cap (US$)": g["_mc"].sum()}
        for ind in indicadores:
            vals = pd.to_numeric(g[ind], errors="coerce")
            w = g["_mc"].where(vals.notna(), 0)
            reg[ind] = (vals.fillna(0) * w).sum() / w.sum() if w.sum() else None
        linhas.append(reg)
    return (pd.DataFrame(linhas).sort_values("Market Cap (US$)", ascending=False)
            .reset_index(drop=True))


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
