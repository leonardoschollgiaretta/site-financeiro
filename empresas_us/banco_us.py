"""
Cria o schema de empresas_us.db — espelhado do projeto BR (financeiro/banco.py),
mas com granularidade TRIMESTRAL (cik, ano, trimestre) ao invés de anual.

Uso:
    python banco_us.py     # cria/atualiza o schema
"""
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'empresas_us.db')

def criar_banco():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ── Empresas ─────────────────────────────────────────────────────────────
    c.execute('''
    CREATE TABLE IF NOT EXISTS empresas (
        cik              TEXT PRIMARY KEY,        -- ex: '0000320193'
        ticker           TEXT,                    -- ticker principal
        ticker_alt       TEXT,                    -- outros tickers (concatenados | )
        nome             TEXT,
        sic              TEXT,
        sic_descricao    TEXT,
        setor            TEXT,                    -- mapeamento SIC → setor (Tech, Finance, ...)
        exchange         TEXT,
        fiscal_year_end  TEXT,                    -- '0926' = 26/set (Apple)
        category         TEXT,                    -- 'Large accelerated filer' etc.
        moeda            TEXT DEFAULT 'USD',
        considerar       TEXT,                    -- '100% VALIDADA' | 'VALIDADA PARCIAL' | 'DESCONSIDERAR'
        atualizado_em    TEXT
    )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_emp_ticker ON empresas(ticker)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_emp_nome   ON empresas(nome)')

    # ── Financeiros trimestrais ──────────────────────────────────────────────
    # fonte: 'sec-xbrl' | 'manual'
    # tipo_periodo: 'Q' (trimestre isolado) | 'FY' (ano fiscal) | 'YTD3' (6M) | 'YTD9' (9M)
    c.execute('''
    CREATE TABLE IF NOT EXISTS financeiros_trimestrais (
        cik                  TEXT,
        ano                  INTEGER,             -- fiscal year (fy do XBRL)
        trimestre            TEXT,                -- 'Q1'/'Q2'/'Q3'/'Q4'/'FY'
        tipo_periodo         TEXT DEFAULT 'Q',    -- 'Q' (3M), 'FY' (12M), 'YTD' (3/6/9M)
        data_inicio          TEXT,
        data_fim             TEXT,
        form                 TEXT,                -- '10-Q' ou '10-K'
        fonte                TEXT DEFAULT 'sec-xbrl',
        atualizado_em        TEXT,

        -- DRE
        receita_liquida          REAL,
        custo_receita            REAL,
        lucro_bruto              REAL,
        despesas_operacionais    REAL,   -- SG&A + outras
        sg_a                     REAL,
        r_e_d                    REAL,
        depreciacao_amortizacao  REAL,
        ebit                     REAL,   -- OperatingIncomeLoss
        receitas_financeiras     REAL,
        despesas_financeiras     REAL,   -- InterestExpense
        resultado_financeiro     REAL,
        ebt                      REAL,
        ir_csll                  REAL,
        lucro_liquido            REAL,
        ebitda                   REAL,   -- calculado: ebit + D&A

        -- Balanço Ativo (instant)
        ativo_total              REAL,
        ativo_circulante         REAL,
        caixa                    REAL,
        investimentos_cp         REAL,            -- short-term investments
        contas_receber           REAL,
        estoques                 REAL,
        ativo_nao_circulante     REAL,
        investimentos            REAL,
        imobilizado              REAL,
        intangivel               REAL,
        goodwill                 REAL,

        -- Balanço Passivo (instant)
        passivo_total            REAL,
        passivo_circulante       REAL,
        fornecedores             REAL,
        emprestimos_cp           REAL,
        passivo_nao_circulante   REAL,
        emprestimos_lp           REAL,
        capital_social           REAL,
        lucros_acumulados        REAL,
        patrimonio_liquido       REAL,
        divida_bruta             REAL,           -- calculado: cp + lp
        divida_liquida           REAL,           -- calculado: bruta - caixa

        -- Fluxo de Caixa
        fco                      REAL,
        fci                      REAL,
        fcf_financiamento        REAL,
        capex                    REAL,
        aquisicoes               REAL,
        venda_ativos             REAL,
        captacoes                REAL,
        pagamento_dividas        REAL,
        recompra_acoes           REAL,
        dividendos_pagos         REAL,
        variacao_caixa           REAL,
        caixa_final              REAL,
        fcl                      REAL,           -- calculado: fco - capex

        PRIMARY KEY (cik, ano, trimestre, tipo_periodo)
    )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_fin_cik ON financeiros_trimestrais(cik)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_fin_ano ON financeiros_trimestrais(ano, trimestre)')

    # ── Preços trimestrais ───────────────────────────────────────────────────
    c.execute('''
    CREATE TABLE IF NOT EXISTS precos_trimestrais (
        cik           TEXT,
        ano           INTEGER,
        trimestre     TEXT,
        preco_min     REAL,
        preco_max     REAL,
        preco_medio   REAL,
        preco_fim     REAL,
        atualizado_em TEXT,
        PRIMARY KEY (cik, ano, trimestre)
    )
    ''')

    # ── Ações em circulação (shares outstanding) ─────────────────────────────
    c.execute('''
    CREATE TABLE IF NOT EXISTS acoes_trimestrais (
        cik                  TEXT,
        ano                  INTEGER,
        trimestre            TEXT,
        shares_basic         REAL,
        shares_diluted       REAL,
        shares_outstanding   REAL,           -- DEI: EntityCommonStockSharesOutstanding
        atualizado_em        TEXT,
        PRIMARY KEY (cik, ano, trimestre)
    )
    ''')

    # ── Dividendos (pagamentos individuais — vem de outra fonte: yfinance ou SEC) ──
    c.execute('''
    CREATE TABLE IF NOT EXISTS dividendos_pagamentos (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        cik           TEXT,
        ticker        TEXT,
        data_com      TEXT,                 -- ex-dividend date
        data_pgto     TEXT,
        tipo          TEXT,                 -- 'cash' | 'stock'
        valor         REAL,                 -- por ação, em USD
        atualizado_em TEXT
    )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_div_cik ON dividendos_pagamentos(cik)')

    # ── Fatos XBRL crus (auditoria) ──────────────────────────────────────────
    # Guarda TODOS os fatos brutos para auditoria e reprocessamento sem rebaixar.
    c.execute('''
    CREATE TABLE IF NOT EXISTS xbrl_fatos (
        cik           TEXT,
        conceito      TEXT,                 -- ex: 'NetIncomeLoss'
        taxonomia     TEXT,                 -- 'us-gaap' | 'dei' | 'ifrs-full'
        unidade       TEXT,                 -- 'USD' | 'shares' | etc
        fy            INTEGER,
        fp            TEXT,                 -- 'Q1'/'Q2'/'Q3'/'FY'
        data_inicio   TEXT,                 -- NULL se instant
        data_fim      TEXT,
        valor         REAL,
        form          TEXT,
        frame         TEXT,                 -- 'CY2024Q1' (calendar) — quando disponível
        accession     TEXT,
        filed         TEXT,
        PRIMARY KEY (cik, conceito, fy, fp, data_inicio, data_fim, form)
    )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_xbrl_cik ON xbrl_fatos(cik)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_xbrl_conceito ON xbrl_fatos(conceito)')

    # ── Validações (mesmo modelo do BR) ──────────────────────────────────────
    c.execute('''
    CREATE TABLE IF NOT EXISTS validacoes (
        cik     TEXT,
        kind    TEXT,                 -- 'tipo' | 'ano' | 'trimestre'
        valor   TEXT,
        PRIMARY KEY (cik, kind, valor)
    )
    ''')

    conn.commit()
    conn.close()
    print(f'Schema criado/atualizado em: {DB}')

if __name__ == '__main__':
    criar_banco()
