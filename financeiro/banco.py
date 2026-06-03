import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

def criar_banco():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ── Empresas ────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            ticker  TEXT PRIMARY KEY,
            nome    TEXT,
            setor   TEXT,
            moeda   TEXT DEFAULT 'BRL'
        )
    """)

    # ── Financeiros Anuais ───────────────────────────────────────────────────
    # fonte: 'investsite' | 'statusinvest' | 'yfinance' | 'manual'
    c.execute("""
        CREATE TABLE IF NOT EXISTS financeiros_anuais (
            ticker              TEXT,
            ano                 INTEGER,
            fonte               TEXT,
            atualizado_em       TEXT,   -- datetime ISO: '2025-04-26 14:32:00'

            -- DRE
            receita_liquida         REAL,
            custo_receita           REAL,
            lucro_bruto             REAL,
            despesas_operacionais   REAL,   -- SG&A (3.04)
            depreciacao_amortizacao REAL,   -- D&A
            ebit                    REAL,
            receitas_financeiras    REAL,
            despesas_financeiras    REAL,
            resultado_financeiro    REAL,
            ebt                     REAL,
            ir_csll                 REAL,
            lucro_liquido           REAL,
            ebitda                  REAL,   -- calculado: ebit + D&A

            -- Balanço Ativo
            ativo_total             REAL,
            ativo_circulante        REAL,
            caixa                   REAL,
            contas_receber          REAL,
            estoques                REAL,
            ativo_nao_circulante    REAL,   -- (1.02)
            investimentos           REAL,   -- (1.02.02)
            imobilizado             REAL,   -- (1.02.03)
            intangivel              REAL,   -- (1.02.04)
            outros_ativos_nc        REAL,   -- (1.02.01)

            -- Balanço Passivo
            passivo_circulante      REAL,
            fornecedores            REAL,   -- (2.01.02)
            emprestimos_cp          REAL,   -- (2.01.04)
            passivo_nao_circulante  REAL,   -- (2.02)
            emprestimos_lp          REAL,   -- (2.02.01)
            debentures              REAL,   -- (2.02.02)
            capital_social          REAL,   -- (2.03.01)
            reservas_lucro          REAL,   -- (2.03.04)
            lucros_acumulados       REAL,   -- (2.03.05)
            patrimonio_liquido      REAL,
            divida_bruta            REAL,   -- calculado: emp_cp + emp_lp + deb
            divida_liquida          REAL,   -- calculado: div_bruta - caixa

            -- Fluxo de Caixa
            fco                     REAL,
            fci                     REAL,
            fcf_financiamento       REAL,
            capex                   REAL,   -- (6.02.01)
            venda_ativos            REAL,   -- (6.02.02)
            aquisicoes              REAL,   -- (6.02.03)
            captacoes               REAL,   -- (6.03.01)
            pagamento_dividas       REAL,   -- (6.03.02)
            recompra_acoes          REAL,   -- (6.03.03)
            dividendos_pagos        REAL,   -- (6.03.04)
            variacao_caixa          REAL,   -- (6.04)
            caixa_inicial           REAL,   -- (6.05)
            caixa_final             REAL,   -- (6.06)
            variacao_capital_giro   REAL,
            fcl                     REAL,   -- calculado: fco + capex

            PRIMARY KEY (ticker, ano, fonte)
        )
    """)

    # ── Preços Anuais ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS precos_anuais (
            ticker        TEXT,
            ano           INTEGER,
            preco_min     REAL,
            preco_max     REAL,
            preco_medio   REAL,
            atualizado_em TEXT,
            PRIMARY KEY (ticker, ano)
        )
    """)

    # ── Dividendos Anuais ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS dividendos_anuais (
            ticker              TEXT,
            ano                 INTEGER,
            dividendo_por_acao  REAL,
            atualizado_em       TEXT,
            PRIMARY KEY (ticker, ano)
        )
    """)

    # ── Validacoes ───────────────────────────────────────────────────────────
    # kind='tipo'  valor='dre'|'balanco'|'fluxo'|'dividendos'|'acoes'|'precos'
    # kind='ano'   valor='2024'|'2023'|...
    # Uma linha = aquele ticker/kind/valor esta VALIDADO (nao recoleta)
    c.execute("""
        CREATE TABLE IF NOT EXISTS validacoes (
            ticker  TEXT,
            kind    TEXT,
            valor   TEXT,
            PRIMARY KEY (ticker, kind, valor)
        )
    """)

    # Migracoes: colunas de acoes na tabela empresas
    acoes_cols = [
        ("empresas", "acoes_on",              "INTEGER"),
        ("empresas", "acoes_pn",              "INTEGER"),
        ("empresas", "acoes_total",           "INTEGER"),
        ("empresas", "acoes_tesouraria",      "INTEGER"),
        ("empresas", "acoes_free",            "INTEGER"),
        ("empresas", "acoes_atualizadas_em",  "TEXT"),
        ("empresas", "ticker_on",                "TEXT"),   # ticker das ON (ex: PETR3)
        ("empresas", "ticker_pn",                "TEXT"),   # ticker das PN (ex: PETR4), NULL se nao houver
        ("empresas", "dividendos_coletados_em",  "TEXT"),   # timestamp da ultima coleta de dividendos
        ("empresas", "considerar",               "TEXT"),   # '100% VALIDADA' | 'VALIDADA PARCIAL' | 'DESCONSIDERAR'
    ]
    for tabela, coluna, tipo in acoes_cols:
        colunas_existentes = [row[1] for row in c.execute(f"PRAGMA table_info({tabela})")]
        if coluna not in colunas_existentes:
            c.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            print(f"  Coluna '{coluna}' adicionada em '{tabela}'")

    # Migracoes: adiciona colunas novas em tabelas existentes (para DBs ja existentes)
    migracoes = [
        # legado
        ("financeiros_anuais",  "atualizado_em",            "TEXT"),
        ("financeiros_anuais",  "receitas_financeiras",     "REAL"),
        ("financeiros_anuais",  "despesas_financeiras",     "REAL"),
        ("financeiros_anuais",  "resultado_financeiro",     "REAL"),
        ("financeiros_anuais",  "ebt",                      "REAL"),
        ("financeiros_anuais",  "ir_csll",                  "REAL"),
        ("precos_anuais",       "atualizado_em",            "TEXT"),
        ("dividendos_anuais",   "atualizado_em",            "TEXT"),
        # DRE novos
        ("financeiros_anuais",  "despesas_operacionais",    "REAL"),
        ("financeiros_anuais",  "depreciacao_amortizacao",  "REAL"),
        # Balanco Ativo novos
        ("financeiros_anuais",  "ativo_nao_circulante",     "REAL"),
        ("financeiros_anuais",  "investimentos",            "REAL"),
        ("financeiros_anuais",  "imobilizado",              "REAL"),
        ("financeiros_anuais",  "intangivel",               "REAL"),
        ("financeiros_anuais",  "outros_ativos_nc",         "REAL"),
        # Balanco Passivo novos
        ("financeiros_anuais",  "fornecedores",             "REAL"),
        ("financeiros_anuais",  "emprestimos_cp",           "REAL"),
        ("financeiros_anuais",  "passivo_nao_circulante",   "REAL"),
        ("financeiros_anuais",  "emprestimos_lp",           "REAL"),
        ("financeiros_anuais",  "debentures",               "REAL"),
        ("financeiros_anuais",  "capital_social",           "REAL"),
        ("financeiros_anuais",  "reservas_lucro",           "REAL"),
        ("financeiros_anuais",  "lucros_acumulados",        "REAL"),
        # FC novos
        ("financeiros_anuais",  "venda_ativos",             "REAL"),
        ("financeiros_anuais",  "aquisicoes",               "REAL"),
        ("financeiros_anuais",  "captacoes",                "REAL"),
        ("financeiros_anuais",  "pagamento_dividas",        "REAL"),
        ("financeiros_anuais",  "recompra_acoes",           "REAL"),
        ("financeiros_anuais",  "dividendos_pagos",         "REAL"),
        ("financeiros_anuais",  "variacao_caixa",           "REAL"),
        ("financeiros_anuais",  "caixa_inicial",            "REAL"),
        ("financeiros_anuais",  "caixa_final",              "REAL"),
        ("financeiros_anuais",  "variacao_capital_giro",    "REAL"),
    ]
    for tabela, coluna, tipo in migracoes:
        colunas_existentes = [row[1] for row in c.execute(f"PRAGMA table_info({tabela})")]
        if coluna not in colunas_existentes:
            c.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            print(f"  Coluna '{coluna}' adicionada em '{tabela}'")

    # ── Acoes Anuais ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS acoes_anuais (
            ticker           TEXT,
            ano              INTEGER,
            acoes_on         INTEGER,
            acoes_pn         INTEGER,
            acoes_total      INTEGER,
            acoes_tesouraria INTEGER,
            acoes_free       INTEGER,
            atualizado_em    TEXT,
            PRIMARY KEY (ticker, ano)
        )
    """)

    # ── Dividendos — pagamentos individuais ─────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS dividendos_pagamentos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker        TEXT,
            data_com      TEXT,
            data_pgto     TEXT,
            tipo          TEXT,
            valor         REAL,
            atualizado_em TEXT
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    criar_banco()
    print("Banco criado/atualizado com sucesso.")
