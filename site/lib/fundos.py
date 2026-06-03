"""
fundos.py — consultas (só leitura) ao banco fundos_cvm.

Reaproveita a lógica dos scripts existentes (consulta_fundos.py,
relatorio_matriz_ticker_mes.py), mas retornando DataFrames do pandas,
que o Streamlit exibe como tabela interativa.
"""
import pandas as pd

from lib.db import conn_fundos

MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
         'jul', 'ago', 'set', 'out', 'nov', 'dez']


def periodo_humano(p):
    """202604 -> 'abr/2026'."""
    if not p or len(str(p)) != 6:
        return p
    p = str(p)
    return f"{MESES[int(p[4:6]) - 1]}/{p[:4]}"


def periodos_disponiveis():
    with conn_fundos() as c:
        df = pd.read_sql_query(
            "SELECT DISTINCT periodo FROM posicoes_acoes ORDER BY periodo", c)
    return df["periodo"].tolist()


def ultimo_periodo():
    ps = periodos_disponiveis()
    return ps[-1] if ps else None


def tickers_disponiveis():
    with conn_fundos() as c:
        df = pd.read_sql_query(
            "SELECT DISTINCT cd_ativo FROM posicoes_acoes "
            "WHERE cd_ativo IS NOT NULL AND cd_ativo <> '' ORDER BY cd_ativo", c)
    return df["cd_ativo"].tolist()


def fundos_com_ticker(ticker, periodo=None):
    """Fundos que detêm um ticker num período, ordenados por valor de mercado."""
    periodo = periodo or ultimo_periodo()
    sql = """
        SELECT p.cnpj_fundo            AS CNPJ,
               f.denominacao           AS Fundo,
               f.tp_fundo_classe       AS Tipo,
               p.qt_pos_final          AS Quantidade,
               p.vl_mercado            AS "Valor mercado (R$)",
               f.patrimonio_liq        AS "PL do fundo (R$)",
               CASE WHEN f.patrimonio_liq > 0
                    THEN p.vl_mercado * 1.0 / f.patrimonio_liq END AS "% do PL"
        FROM posicoes_acoes p
        LEFT JOIN fundos f ON f.cnpj = p.cnpj_fundo AND f.periodo = p.periodo
        WHERE p.cd_ativo = ? AND p.periodo = ?
        ORDER BY p.vl_mercado DESC
    """
    with conn_fundos() as c:
        return pd.read_sql_query(sql, c, params=[ticker.upper(), periodo])


def carteira_do_fundo(termo, periodo=None):
    """Carteira de ações de um fundo (busca por CNPJ parcial ou nome)."""
    periodo = periodo or ultimo_periodo()
    import re
    cnpj_clean = re.sub(r"\D", "", termo)
    with conn_fundos() as c:
        if cnpj_clean and len(cnpj_clean) >= 6:
            fundos = pd.read_sql_query(
                "SELECT cnpj, denominacao, patrimonio_liq FROM fundos "
                "WHERE periodo=? AND REPLACE(REPLACE(REPLACE(cnpj,'.',''),'/',''),'-','') LIKE ?",
                c, params=[periodo, f"%{cnpj_clean}%"])
        else:
            fundos = pd.DataFrame()
        if fundos.empty:
            fundos = pd.read_sql_query(
                "SELECT cnpj, denominacao, patrimonio_liq FROM fundos "
                "WHERE periodo=? AND UPPER(denominacao) LIKE ?",
                c, params=[periodo, f"%{termo.upper()}%"])

        if fundos.empty:
            return None, fundos  # nenhum fundo
        if len(fundos) > 1:
            return "multiplos", fundos  # precisa refinar

        cnpj = fundos.iloc[0]["cnpj"]
        pos = pd.read_sql_query(
            """SELECT cd_ativo AS Ticker, ds_ativo AS Descrição, tp_ativo AS Tipo,
                      qt_pos_final AS Quantidade, vl_mercado AS "Valor (R$)"
               FROM posicoes_acoes WHERE cnpj_fundo=? AND periodo=?
               ORDER BY vl_mercado DESC""",
            c, params=[cnpj, periodo])
    return fundos.iloc[0], pos


def ranking_acoes(periodo=None, por="fundos", limite=30):
    """Top ações por nº de fundos ('fundos') ou por valor agregado ('valor')."""
    periodo = periodo or ultimo_periodo()
    ordem = "n_fundos DESC" if por == "fundos" else "valor_agregado DESC"
    sql = f"""
        SELECT cd_ativo AS Ticker,
               COUNT(DISTINCT cnpj_fundo) AS n_fundos,
               SUM(vl_mercado)            AS valor_agregado
        FROM posicoes_acoes
        WHERE periodo = ? AND cd_ativo IS NOT NULL AND cd_ativo <> ''
        GROUP BY cd_ativo
        ORDER BY {ordem}
        LIMIT ?
    """
    with conn_fundos() as c:
        df = pd.read_sql_query(sql, c, params=[periodo, limite])
    df = df.rename(columns={"n_fundos": "Nº fundos",
                            "valor_agregado": "Valor agregado (R$)"})
    return df


def matriz_ticker_mes(top=None):
    """Matriz ticker (linha) × período (coluna) com valor de mercado agregado.

    top: se informado, limita aos N tickers de maior valor no último período.
    """
    sql = """
        SELECT cd_ativo, periodo, SUM(vl_mercado) AS vl
        FROM posicoes_acoes
        WHERE cd_ativo IS NOT NULL AND cd_ativo <> ''
        GROUP BY cd_ativo, periodo
    """
    with conn_fundos() as c:
        df = pd.read_sql_query(sql, c)
    if df.empty:
        return df

    pivot = df.pivot_table(index="cd_ativo", columns="periodo",
                           values="vl", aggfunc="sum", fill_value=0)
    # remove tickers que nunca tiveram valor
    pivot = pivot[(pivot != 0).any(axis=1)]
    # ordena pelo último período
    ult = pivot.columns[-1]
    pivot = pivot.sort_values(ult, ascending=False)
    if top:
        pivot = pivot.head(top)
    # renomeia colunas para o formato humano (abr/2026)
    pivot.columns = [periodo_humano(p) for p in pivot.columns]
    pivot.index.name = "Ticker"
    return pivot


def buscar_fundos(termo="", limite=300, apenas_com_acoes=False):
    """Lista fundos (cnpj + nome) cujo nome contém o termo. Distintos no banco todo.

    apenas_com_acoes: se True, retorna só fundos que têm ao menos uma posição
    em ações (filtra fora as classes 'em cotas' que não investem em ações).

    Retorna DataFrame com colunas: cnpj, denominacao, rotulo (nome · cnpj).
    """
    termo = (termo or "").strip().upper()
    where = "WHERE f.denominacao IS NOT NULL AND f.denominacao <> ''"
    params = []
    if termo:
        where += " AND UPPER(f.denominacao) LIKE ?"
        params.append(f"%{termo}%")
    if apenas_com_acoes:
        # só fundos com pelo menos 1 posição em ações em algum período
        where += (" AND f.cnpj IN (SELECT DISTINCT cnpj_fundo FROM posicoes_acoes "
                  "WHERE cd_ativo IS NOT NULL AND cd_ativo <> '')")
    sql = f"""
        SELECT f.cnpj AS cnpj, f.denominacao AS denominacao
        FROM fundos f
        {where}
        GROUP BY f.cnpj
        ORDER BY f.denominacao
        LIMIT ?
    """
    params.append(limite)
    with conn_fundos() as c:
        df = pd.read_sql_query(sql, c, params=params)
    if not df.empty:
        # nome primeiro (o que o usuário lê), CNPJ no fim para diferenciar homônimos
        df["rotulo"] = df["denominacao"].str.slice(0, 75) + "  ·  " + df["cnpj"]
    return df


def matriz_ticker_mes_por_fundos(cnpjs):
    """Matriz ticker × mês, mas SOMANDO apenas os fundos (CNPJs) informados.

    Mesma estrutura de matriz_ticker_mes, sem corte de 'top'.
    """
    if not cnpjs:
        return pd.DataFrame()
    placeholders = ",".join("?" * len(cnpjs))
    sql = f"""
        SELECT cd_ativo, periodo, SUM(vl_mercado) AS vl
        FROM posicoes_acoes
        WHERE cnpj_fundo IN ({placeholders})
          AND cd_ativo IS NOT NULL AND cd_ativo <> ''
        GROUP BY cd_ativo, periodo
    """
    with conn_fundos() as c:
        df = pd.read_sql_query(sql, c, params=list(cnpjs))
    if df.empty:
        return df
    pivot = df.pivot_table(index="cd_ativo", columns="periodo",
                           values="vl", aggfunc="sum", fill_value=0)
    pivot = pivot[(pivot != 0).any(axis=1)]
    ult = pivot.columns[-1]
    pivot = pivot.sort_values(ult, ascending=False)
    pivot.columns = [periodo_humano(p) for p in pivot.columns]
    pivot.index.name = "Ticker"
    return pivot
