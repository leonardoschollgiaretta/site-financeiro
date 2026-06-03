"""
importar_manual.py — Lê todos os .xlsx da pasta 'inputs forcados/' e importa
os dados para o banco com fonte='manual'.

Regras:
  - Só importa valores preenchidos (ignora NaN e zero)
  - Multiplica por 1.000 (arquivos em R$ milhares → banco em R$)
  - Calcula divida_bruta e divida_liquida automaticamente
  - Respeita validacoes: campos validados são pulados
  - fonte='manual' tem prioridade máxima no ranker e infospainel
"""
import os
import sys
import sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import banco
import sync_validador
from db_utils import upsert_financeiro
from db_validacao import is_validado

DIR_INPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs forcados")
DB        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financeiro.db")
ESCALA    = 1_000   # arquivo em R$ milhares -> banco em R$ inteiros

ANOS_VALIDOS = {2020, 2021, 2022, 2023, 2024, 2025, 2026}

# Categoria de cada campo (para checagem de validacao)
CAMPO_CATEGORIA = {
    # DRE
    "receita_liquida": "dre", "custo_receita": "dre", "lucro_bruto": "dre",
    "despesas_operacionais": "dre", "ebitda": "dre", "ebit": "dre",
    "receitas_financeiras": "dre", "despesas_financeiras": "dre",
    "resultado_financeiro": "dre", "ebt": "dre", "ir_csll": "dre",
    "lucro_liquido": "dre",
    # Balanco
    "caixa": "balanco", "contas_receber": "balanco", "estoques": "balanco",
    "ativo_circulante": "balanco", "imobilizado": "balanco", "intangivel": "balanco",
    "investimentos": "balanco", "outros_ativos_nc": "balanco",
    "ativo_nao_circulante": "balanco", "ativo_total": "balanco",
    "emprestimos_cp": "balanco", "fornecedores": "balanco",
    "passivo_circulante": "balanco", "emprestimos_lp": "balanco",
    "debentures": "balanco", "passivo_nao_circulante": "balanco",
    "capital_social": "balanco", "reservas_lucro": "balanco",
    "lucros_acumulados": "balanco", "patrimonio_liquido": "balanco",
    "divida_bruta": "balanco", "divida_liquida": "balanco",
    # Fluxo
    "depreciacao_amortizacao": "fluxo", "variacao_capital_giro": "fluxo",
    "fco": "fluxo", "capex": "fluxo", "venda_ativos": "fluxo",
    "aquisicoes": "fluxo", "fci": "fluxo", "captacoes": "fluxo",
    "pagamento_dividas": "fluxo", "recompra_acoes": "fluxo",
    "dividendos_pagos": "fluxo", "fcf_financiamento": "fluxo",
    "variacao_caixa": "fluxo", "caixa_inicial": "fluxo",
    "caixa_final": "fluxo", "fcl": "fluxo",
}

# Mapeamento: label da planilha -> campo do banco
MAPA = {
    # DRE
    "Receita Liquida":                    "receita_liquida",
    "CPV / CMV":                          "custo_receita",
    "Lucro Bruto":                        "lucro_bruto",
    "Despesas Operacionais (SG&A)":       "despesas_operacionais",
    "EBITDA":                             "ebitda",
    "EBIT (Res. Operacional)":            "ebit",
    "Receitas Financeiras":               "receitas_financeiras",
    "Despesas Financeiras":               "despesas_financeiras",
    "Resultado Financeiro Liquido":       "resultado_financeiro",
    "EBT (Lucro antes do IR)":            "ebt",
    "IR e CSLL":                          "ir_csll",
    "Lucro Liquido":                      "lucro_liquido",
    # Balanco - Ativo
    "Caixa e Equivalentes":               "caixa",
    "Contas a Receber":                   "contas_receber",
    "Estoques":                           "estoques",
    "TOTAL ATIVO CIRCULANTE":             "ativo_circulante",
    "Imobilizado (liquido)":              "imobilizado",
    "Intangiveis":                        "intangivel",
    "Investimentos":                      "investimentos",
    "Outros Ativos Nao Circulantes":      "outros_ativos_nc",
    "TOTAL ATIVO NAO CIRCULANTE":         "ativo_nao_circulante",
    "TOTAL DO ATIVO":                     "ativo_total",
    # Balanco - Passivo
    "Emprestimos CP":                     "emprestimos_cp",
    "Fornecedores":                       "fornecedores",
    "TOTAL PASSIVO CIRCULANTE":           "passivo_circulante",
    "Emprestimos LP":                     "emprestimos_lp",
    "Debentures":                         "debentures",
    "TOTAL PASSIVO NAO CIRCULANTE":       "passivo_nao_circulante",
    "Capital Social":                     "capital_social",
    "Reservas de Lucro":                  "reservas_lucro",
    "Lucros / Prejuizos Acumulados":      "lucros_acumulados",
    "TOTAL PATRIMONIO LIQUIDO":           "patrimonio_liquido",
    # Fluxo de Caixa
    "(+) Depreciacao & Amortizacao":      "depreciacao_amortizacao",
    "(+/-) Variacao Capital de Giro":     "variacao_capital_giro",
    "FLUXO CAIXA OPERACIONAL (FCO)":      "fco",
    "CAPEX - Aquisicao de Imobilizado":   "capex",
    "Recebimentos por Venda de Ativos":   "venda_ativos",
    "Aquisicoes / Participacoes":         "aquisicoes",
    "FLUXO CAIXA INVESTIMENTOS (FCI)":    "fci",
    "Captacoes (Emprestimos/Debentures)": "captacoes",
    "Pagamento de Dividas":               "pagamento_dividas",
    "Recompra de Acoes":                  "recompra_acoes",
    "Dividendos / JCP Pagos":             "dividendos_pagos",
    "FLUXO CAIXA FINANCIAMENTOS (FCF)":   "fcf_financiamento",
    "Variacao Liquida de Caixa":          "variacao_caixa",
    "Caixa Inicial":                      "caixa_inicial",
    "Caixa Final":                        "caixa_final",
    "Free Cash Flow (FCO - CAPEX)":       "fcl",
}

# Versao com acentos (lida diretamente do Excel)
MAPA_ACENTOS = {
    "Receita Líquida":                    "receita_liquida",
    "Lucro Líquido":                      "lucro_liquido",
    "Lucro Bruto":                        "lucro_bruto",
    "Despesas Operacionais (SG&A)":       "despesas_operacionais",
    "Receitas Financeiras":               "receitas_financeiras",
    "Despesas Financeiras":               "despesas_financeiras",
    "Resultado Financeiro Líquido":       "resultado_financeiro",
    "Imobilizado (líquido)":              "imobilizado",
    "Intangíveis":                        "intangivel",
    "Outros Ativos Não Circulantes":      "outros_ativos_nc",
    "TOTAL ATIVO NÃO CIRCULANTE":         "ativo_nao_circulante",
    "Empréstimos CP":                     "emprestimos_cp",
    "Empréstimos LP":                     "emprestimos_lp",
    "Debêntures":                         "debentures",
    "TOTAL PASSIVO NÃO CIRCULANTE":       "passivo_nao_circulante",
    "Reservas de Lucro":                  "reservas_lucro",
    "Lucros / Prejuízos Acumulados":      "lucros_acumulados",
    "TOTAL PATRIMÔNIO LÍQUIDO":      "patrimonio_liquido",
    "(+) Depreciação & Amortização": "depreciacao_amortizacao",
    "(+/−) Variação Capital de Giro": "variacao_capital_giro",
    "CAPEX — Aquisição de Imobilizado": "capex",
    "Aquisições / Participações": "aquisicoes",
    "Captações (Empréstimos/Debêntures)": "captacoes",
    "Recompra de Ações":             "recompra_acoes",
    "Variação Líquida de Caixa": "variacao_caixa",
    "Free Cash Flow (FCO − CAPEX)":       "fcl",
}

# Combina os dois mapas (acentos tem precedencia para nao duplicar)
MAPA_COMPLETO = {**MAPA, **MAPA_ACENTOS}


def _detectar_anos(df):
    """Encontra quais colunas contem anos validos."""
    for _, row in df.iterrows():
        anos_col = {}
        for c in range(1, len(df.columns)):
            val = row.iloc[c]
            if pd.notna(val):
                try:
                    ano = int(float(val))
                    if ano in ANOS_VALIDOS:
                        anos_col[c] = ano
                except (ValueError, TypeError):
                    pass
        if anos_col:
            return anos_col
    return {}


def _detectar_ticker(df, nome_arquivo):
    """Tenta extrair ticker da planilha; fallback = nome do arquivo."""
    for _, row in df.iterrows():
        val = str(row.iloc[0]).strip().upper()
        if val and val != "NAN" and len(val) <= 6 and val.isalnum():
            return val
    return os.path.splitext(nome_arquivo)[0].replace("MANUAL", "").upper()


def importar_arquivo(path):
    df = pd.read_excel(path, sheet_name=0, header=None)

    ticker   = _detectar_ticker(df, os.path.basename(path))
    anos_col = _detectar_anos(df)

    if not anos_col:
        print("  Nao encontrou colunas de ano — verifique o arquivo")
        return

    anos_str = sorted(anos_col.values())
    print(f"  Ticker : {ticker}")
    print(f"  Anos   : {anos_str}")
    print(f"  Escala : x {ESCALA:,} (R$ milhares -> R$)")

    # Coleta dados linha a linha
    dados = {ano: {} for ano in anos_col.values()}

    for _, row in df.iterrows():
        label = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        campo = MAPA_COMPLETO.get(label)
        if campo is None:
            continue
        for c, ano in anos_col.items():
            val = row.iloc[c]
            if pd.notna(val) and val != 0:
                dados[ano][campo] = float(val) * ESCALA

    # Calcula divida_bruta e divida_liquida
    for ano, campos in dados.items():
        emp_cp = campos.get("emprestimos_cp") or 0
        emp_lp = campos.get("emprestimos_lp") or 0
        deb    = campos.get("debentures")     or 0
        caixa  = campos.get("caixa")          or 0
        if emp_cp or emp_lp or deb:
            campos["divida_bruta"]   = emp_cp + emp_lp + deb
            campos["divida_liquida"] = (emp_cp + emp_lp + deb) - caixa

    # Garante que a empresa existe na tabela empresas
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT OR IGNORE INTO empresas (ticker, moeda) VALUES (?, 'BRL')",
        (ticker,)
    )

    total_campos = 0
    for ano in sorted(dados.keys()):
        campos = dados[ano]
        if not campos:
            print(f"  {ano}: nenhum campo mapeado")
            continue

        # Filtra campos cujas categorias estao validadas para este ticker/ano
        campos_filtrados = {}
        pulados = []
        for campo, val in campos.items():
            cat = CAMPO_CATEGORIA.get(campo, "dre")
            if is_validado(conn, ticker, cat, ano):
                pulados.append(campo)
            else:
                campos_filtrados[campo] = val

        if pulados:
            print(f"  {ano}: {len(pulados)} campo(s) pulado(s) por validacao -> {', '.join(sorted(pulados))}")
        if not campos_filtrados:
            print(f"  {ano}: todos os campos validados — pulando ano inteiro")
            continue

        upsert_financeiro(conn, ticker, ano, "manual", campos_filtrados)
        total_campos += len(campos_filtrados)
        print(f"  OK {ano}: {len(campos_filtrados)} campo(s) -> {', '.join(sorted(campos_filtrados.keys()))}")

    conn.commit()
    conn.close()
    print(f"\n  Total: {total_campos} campo(s) importados para {ticker}")


def main():
    banco.criar_banco()
    sync_validador.sincronizar()   # garante que validador.xlsx -> DB antes de checar

    if not os.path.isdir(DIR_INPUT):
        print("Pasta nao encontrada: inputs forcados/")
        return

    arquivos = [f for f in os.listdir(DIR_INPUT) if f.endswith(".xlsx")]
    if not arquivos:
        print("Nenhum .xlsx encontrado em 'inputs forcados/'")
        return

    print(f"\n{'='*50}")
    print(f"  IMPORTACAO MANUAL — {len(arquivos)} arquivo(s)")
    print(f"{'='*50}")

    for nome in sorted(arquivos):
        path = os.path.join(DIR_INPUT, nome)
        print(f"\n  {nome}")
        print(f"  {'─'*45}")
        try:
            importar_arquivo(path)
        except Exception as e:
            print(f"  Erro: {e}")

    print(f"\n{'='*50}")
    print(f"  CONCLUIDO")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
