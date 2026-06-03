"""
Coletor Balanço Patrimonial — Ações Brasileiras
Fonte: Investsite.com.br (dados CVM oficiais)
Ativo:  ativo_total, ativo_circulante, caixa (1.01.01+1.01.02), contas_receber,
        estoques, ativo_nao_circulante, investimentos, imobilizado, intangivel,
        outros_ativos_nc
Passivo: passivo_circulante, fornecedores, emprestimos_cp,
         passivo_nao_circulante, emprestimos_lp, debentures,
         capital_social, reservas_lucro, lucros_acumulados, patrimonio_liquido,
         divida_bruta, divida_liquida
"""
import requests
import sqlite3
import os
import re
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bs4 import BeautifulSoup
from db_utils import upsert_financeiro
from db_validacao import is_validado

DB     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")
BASE   = "https://www.investsite.com.br"
FONTE  = "investsite"

ANOS_REF = [2022, 2025]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": BASE,
}

# ── Ativo ────────────────────────────────────────────────────────────────────
MAPA_ATIVO = {
    "1":       "ativo_total",
    "1.01":    "ativo_circulante",
    "1.01.01": "caixa",           # + 1.01.02 somado em salvar_ativo()
    "1.01.03": "contas_receber",
    "1.01.04": "estoques",
    "1.02":    "ativo_nao_circulante",
    "1.02.01": "outros_ativos_nc",   # realizável LP / outros
    "1.02.02": "investimentos",       # participações / equivalência patrimonial
    "1.02.03": "imobilizado",
    "1.02.04": "intangivel",
}

# ── Passivo ──────────────────────────────────────────────────────────────────
MAPA_PASSIVO = {
    "2.01":    "passivo_circulante",
    "2.01.02": "fornecedores",
    "2.01.04": "emprestimos_cp",
    "2.02":    "passivo_nao_circulante",
    "2.02.01": "emprestimos_lp",
    "2.02.02": "debentures",
    "2.03":    "patrimonio_liquido",
    "2.03.01": "capital_social",
    "2.03.04": "reservas_lucro",
    "2.03.05": "lucros_acumulados",
}


def parse_valor(texto):
    if not texto or texto.strip() in ["-", "", "0"]:
        return None
    try:
        return float(texto.replace(".", "").replace(",", ".").strip()) * 1000
    except:
        return None


def extrair_tabela(ticker, pagina, ano_ref):
    url = f"{BASE}/{pagina}?cod_negociacao={ticker}&ano_dem={ano_ref}&mes_dia_dem=1231&consolid=2&tipocontabil=2"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}
    except Exception as e:
        print(f"    ❌ Erro de conexão: {e}")
        return {}

    soup   = BeautifulSoup(resp.text, "html.parser")
    tab    = soup.find("table")
    if not tab:
        return {}

    linhas = tab.find_all("tr")
    if not linhas:
        return {}

    cabecalho = [td.get_text(strip=True) for td in linhas[0].find_all(["th", "td"])]
    anos_cols = []
    for i, txt in enumerate(cabecalho):
        match = re.findall(r'\d{4}', txt)
        if match:
            anos_cols.append((i, int(match[-1])))

    resultado = {}
    for linha in linhas[1:]:
        cols = [td.get_text(strip=True) for td in linha.find_all(["td", "th"])]
        if len(cols) < 3:
            continue
        codigo = cols[0].strip()
        for idx_col, ano in anos_cols:
            if idx_col < len(cols):
                val = parse_valor(cols[idx_col])
                resultado.setdefault(ano, {})[codigo] = val

    return resultado


def upsert(conn, ticker, ano, campos):
    upsert_financeiro(conn, ticker, ano, FONTE, campos)


def salvar_ativo(conn, ticker, dados):
    for ano, codigos in dados.items():
        mapa = {}
        for cod, col in MAPA_ATIVO.items():
            if cod in codigos and codigos[cod] is not None:
                mapa[col] = codigos[cod]

        # Caixa = 1.01.01 (Caixa e Equivalentes) + 1.01.02 (Aplicações Financeiras CP)
        aplic = codigos.get("1.01.02")
        if aplic is not None:
            mapa["caixa"] = (mapa.get("caixa") or 0) + aplic

        if mapa:
            upsert(conn, ticker, ano, mapa)


def salvar_passivo(conn, ticker, dados):
    for ano, codigos in dados.items():
        mapa = {MAPA_PASSIVO[cod]: val
                for cod, val in codigos.items()
                if cod in MAPA_PASSIVO and val is not None}

        if mapa:
            # Calcula dívida bruta = empréstimos CP + LP + debêntures
            emp_cp = mapa.get("emprestimos_cp") or 0
            emp_lp = mapa.get("emprestimos_lp") or 0
            deb    = mapa.get("debentures")     or 0
            if emp_cp or emp_lp or deb:
                mapa["divida_bruta"] = emp_cp + emp_lp + deb

            upsert(conn, ticker, ano, mapa)


def salvar_divida_liquida(conn, ticker):
    """Após salvar ativo e passivo, calcula dívida líquida = dívida bruta − caixa."""
    rows = conn.execute(
        """SELECT ano, fonte, caixa, divida_bruta FROM financeiros_anuais
           WHERE ticker=? AND fonte=? AND divida_bruta IS NOT NULL AND caixa IS NOT NULL""",
        (ticker, FONTE)
    ).fetchall()
    for ano, fonte, caixa, div_bruta in rows:
        div_liq = div_bruta - caixa
        conn.execute(
            "UPDATE financeiros_anuais SET divida_liquida=? WHERE ticker=? AND ano=? AND fonte=?",
            (div_liq, ticker, ano, fonte)
        )


def coletar(ticker):
    print(f"  🏦 Balanço {ticker}...")
    conn = sqlite3.connect(DB)

    for ano_ref in ANOS_REF:
        # Ativo
        ativo = extrair_tabela(ticker, "balanco_patrimonial_ativo.php", ano_ref)
        if ativo:
            anos_val = {ano: d for ano, d in ativo.items() if not is_validado(conn, ticker, "balanco", ano)}
            anos_pulados = [ano for ano in ativo if is_validado(conn, ticker, "balanco", ano)]
            if anos_pulados:
                print(f"     Ativo validado, pulando anos: {sorted(anos_pulados)}")
            if anos_val:
                salvar_ativo(conn, ticker, anos_val)
                print(f"     Ativo ({ano_ref}): {sorted(anos_val.keys())}")
                for ano, d in anos_val.items():
                    ac = d.get("1.01")
                    cx = (d.get("1.01.01") or 0) + (d.get("1.01.02") or 0)
                    imob = d.get("1.02.03")
                    if ac:
                        imob_txt = f" | Imob: R$ {imob:,.0f}" if imob else ""
                        print(f"     {ano} → Ativo Circ: R$ {ac:,.0f} | Caixa+Aplic: R$ {cx:,.0f}{imob_txt}")

        # Passivo
        passivo = extrair_tabela(ticker, "balanco_patrimonial_passivo.php", ano_ref)
        if passivo:
            anos_val = {ano: d for ano, d in passivo.items() if not is_validado(conn, ticker, "balanco", ano)}
            anos_pulados = [ano for ano in passivo if is_validado(conn, ticker, "balanco", ano)]
            if anos_pulados:
                print(f"     Passivo validado, pulando anos: {sorted(anos_pulados)}")
            if anos_val:
                salvar_passivo(conn, ticker, anos_val)
                print(f"     Passivo ({ano_ref}): {sorted(anos_val.keys())}")
                for ano, d in anos_val.items():
                    pl = d.get("2.03")
                    pc = d.get("2.01")
                    if pl:
                        pc_txt = f" | Passivo Circ: R$ {pc:,.0f}" if pc else ""
                        print(f"     {ano} → PL: R$ {pl:,.0f}{pc_txt}")

    # Calcula dívida líquida depois de ter ativo + passivo salvos
    salvar_divida_liquida(conn, ticker)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import banco
    banco.criar_banco()

    import pandas as pd
    TICKERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tickers.xlsx")
    df = pd.read_excel(TICKERS_FILE, sheet_name="Tickers", header=2)
    df.columns = [c.strip() for c in df.columns]
    tickers = [str(t).strip().upper() for t in df.get("TICKER_BR", []) if pd.notna(t) and str(t).strip()]

    print(f"  {len(tickers)} ticker(s) encontrados em tickers.xlsx\n")
    for t in tickers:
        try:
            coletar(t)
        except Exception as e:
            print(f"  ❌ {t} — erro: {e}")
    print("\n✅ Balanço BR finalizado!")
