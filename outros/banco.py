import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")

def criar_banco():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS empresas (
        ticker      TEXT PRIMARY KEY,
        nome        TEXT,
        setor       TEXT,
        bolsa       TEXT DEFAULT 'B3',
        moeda       TEXT DEFAULT 'BRL'
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS fontes (
        id          INTEGER PRIMARY KEY,
        nome        TEXT UNIQUE,
        prioridade  INTEGER
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS financeiros_anuais (
        ticker              TEXT,
        ano                 INTEGER,
        fonte               TEXT,
        moeda               TEXT DEFAULT 'BRL',
        receita_liquida     REAL,
        custo_receita       REAL,
        lucro_bruto         REAL,
        ebitda              REAL,
        ebit                REAL,
        lucro_liquido       REAL,
        desp_financeiras    REAL,
        rec_financeiras     REAL,
        ir_csll             REAL,
        eps                 REAL,
        caixa               REAL,
        contas_receber      REAL,
        estoques            REAL,
        ativo_circulante    REAL,
        ativo_total         REAL,
        divida_cp           REAL,
        divida_lp           REAL,
        divida_bruta        REAL,
        divida_liquida      REAL,
        patrimonio_liquido  REAL,
        fco                 REAL,
        capex               REAL,
        fcf                 REAL,
        fci                 REAL,
        fcf_financiamento   REAL,
        dividendos_pagos    REAL,
        PRIMARY KEY (ticker, ano, fonte)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS precos_anuais (
        ticker      TEXT,
        ano         INTEGER,
        fonte       TEXT,
        moeda       TEXT DEFAULT 'BRL',
        preco_min   REAL,
        preco_max   REAL,
        preco_medio REAL,
        PRIMARY KEY (ticker, ano, fonte)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS dividendos_anuais (
        ticker              TEXT,
        ano                 INTEGER,
        fonte               TEXT,
        dividendo_por_acao  REAL,
        total_distribuido   REAL,
        PRIMARY KEY (ticker, ano, fonte)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS qualidade_dados (
        ticker          TEXT,
        ano             INTEGER,
        tem_dre         INTEGER DEFAULT 0,
        tem_balanco     INTEGER DEFAULT 0,
        tem_fc          INTEGER DEFAULT 0,
        tem_dividendos  INTEGER DEFAULT 0,
        tem_precos      INTEGER DEFAULT 0,
        fonte_principal TEXT,
        atualizado_em   TEXT,
        PRIMARY KEY (ticker, ano)
    )""")

    c.executemany("""
    INSERT OR IGNORE INTO fontes (nome, prioridade) VALUES (?, ?)
    """, [
        ("yfinance",    1),
        ("fundamentus", 2),
        ("manual",      3),
    ])

    conn.commit()
    conn.close()
    print("✅ Banco financeiro.db criado com sucesso!")
    print("   Tabelas: empresas | fontes | financeiros_anuais | precos_anuais | dividendos_anuais | qualidade_dados")

criar_banco()