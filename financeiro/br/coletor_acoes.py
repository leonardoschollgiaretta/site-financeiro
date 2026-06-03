"""
Coletor Quantidade de Acoes -- Acoes Brasileiras
Fonte: Investsite.com.br

Coleta acoes_anuais (historico por ano) e atualiza empresas (snapshot + par ON/PN).

Campos coletados por ano:
  - acoes_on, acoes_pn, acoes_total, acoes_tesouraria, acoes_free

Logica de deteccao do par (baseada no snapshot do ano mais recente):
  - termina em 3  -> ON  -> ticker_pn = base + "4" (se acoes_pn > 0)
  - termina em 4  -> PN  -> ticker_on = base + "3" (se acoes_on > 0)
  - termina em 11 -> unit, sem par
  - outros        -> ON sem par
"""
import requests
import sqlite3
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bs4 import BeautifulSoup
from db_utils import agora
from db_validacao import is_validado

DB   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")
BASE = "https://www.investsite.com.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": BASE,
}

ANOS = [2025, 2024, 2023, 2022, 2021, 2020]


def parse_numero_raw(texto):
    """Converte numero BR para int sem multiplicar — ex: '504.190.947' -> 504190947."""
    texto = str(texto).strip().replace("\xa0", "").replace(" ", "")
    if not texto or texto in ("-", "", "None"):
        return 0
    try:
        return int(texto.replace(".", ""))
    except ValueError:
        return 0


def _em_milhares(tabela):
    """Retorna True se o cabecalho da tabela indicar '(mil)' — valores em milhares."""
    rows = tabela.find_all("tr")
    if not rows:
        return True   # default historico: assume milhares
    return "(mil)" in rows[0].get_text().lower()


def buscar_ano(ticker, ano):
    """Busca dados de acoes para um ano especifico. Retorna dict ou None."""
    url = (f"{BASE}/quantidade_acoes.php?cod_negociacao={ticker}"
           f"&ano_dem={ano}&mes_dia_dem=1231&consolid=2&tipocontabil=2")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    tabelas = soup.find_all("table")
    if len(tabelas) < 3:
        return None

    def val(tbl_idx, row_pos):
        rows = tabelas[tbl_idx].find_all("tr")
        if row_pos >= len(rows):
            return 0
        cols = rows[row_pos].find_all(["td", "th"])
        if len(cols) < 2:
            return 0
        raw = parse_numero_raw(cols[1].get_text(strip=True))
        # Multiplica por 1000 apenas se o cabecalho indicar "(mil)"
        return raw * 1000 if _em_milhares(tabelas[tbl_idx]) else raw

    # Tabela 0: ON+PN total | Tabela 1: Tesouraria | Tabela 2: Exceto Tesouraria
    # Linhas: 0=header, 1=ON, 2=PN, 3=Total
    return {
        "acoes_on":         val(0, 1),
        "acoes_pn":         val(0, 2),
        "acoes_total":      val(0, 3),
        "acoes_tesouraria": val(1, 3),
        "acoes_free":       val(2, 3),
    }


def detectar_par(ticker, acoes_on, acoes_pn):
    base = ticker[:-1] if not ticker.endswith("11") else ticker
    if ticker.endswith("11"):
        return ticker, None
    elif ticker.endswith("3"):
        return ticker, (base + "4") if acoes_pn > 0 else None
    elif ticker.endswith("4"):
        return (base + "3") if acoes_on > 0 else ticker, ticker
    else:
        return ticker, None


def _registrar_e_coletar_preco(ticker_par, moeda="BRL"):
    from br import coletor_preco, coletor_fechamento
    conn = sqlite3.connect(DB)
    conn.execute("""
        INSERT OR IGNORE INTO empresas (ticker, nome, setor, moeda)
        VALUES (?, ?, ?, ?)
    """, (ticker_par, ticker_par, "N/A", moeda))
    conn.commit()
    conn.close()
    print(f"     Par detectado: coletando preco historico de {ticker_par}...")
    coletor_preco.coletar(ticker_par)
    print(f"     Par detectado: coletando fechamento atual de {ticker_par}...")
    resultado = coletor_fechamento.coletar_fechamento(ticker_par)
    if resultado:
        preco, data_fech, variacao = resultado
        coletor_fechamento.salvar(ticker_par, preco, data_fech, variacao)
        print(f"     Fechamento {ticker_par}: R$ {preco:.2f}  [{data_fech}]")


def coletar(ticker):
    print(f"  Acoes {ticker}...")

    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT moeda FROM empresas WHERE ticker=?", (ticker,)).fetchone()
    moeda = row[0] if row else "BRL"
    conn.close()

    conn_val = sqlite3.connect(DB)
    dados_anos = {}
    for ano in ANOS:
        if is_validado(conn_val, ticker, "acoes", ano):
            print(f"     {ano}: validado, pulando")
            continue
        d = buscar_ano(ticker, ano)
        if d:
            dados_anos[ano] = d
            print(f"     {ano}: ON={d['acoes_on']:,}  PN={d['acoes_pn']:,}  Free={d['acoes_free']:,}")
        else:
            print(f"     {ano}: sem dados")
    conn_val.close()

    if not dados_anos:
        print(f"     Nenhum dado encontrado")
        return

    # Salva historico anual
    conn = sqlite3.connect(DB)
    for ano, d in dados_anos.items():
        conn.execute("""
            INSERT OR REPLACE INTO acoes_anuais
                (ticker, ano, acoes_on, acoes_pn, acoes_total, acoes_tesouraria, acoes_free, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, ano, d["acoes_on"], d["acoes_pn"], d["acoes_total"],
              d["acoes_tesouraria"], d["acoes_free"], agora()))

    # Snapshot atual (ano mais recente) para a tabela empresas
    snap = dados_anos.get(max(dados_anos.keys()))
    ticker_on, ticker_pn = detectar_par(ticker, snap["acoes_on"], snap["acoes_pn"])

    conn.execute("""
        UPDATE empresas SET
            acoes_on             = ?,
            acoes_pn             = ?,
            acoes_total          = ?,
            acoes_tesouraria     = ?,
            acoes_free           = ?,
            ticker_on            = ?,
            ticker_pn            = ?,
            acoes_atualizadas_em = ?
        WHERE ticker = ?
    """, (snap["acoes_on"], snap["acoes_pn"], snap["acoes_total"],
          snap["acoes_tesouraria"], snap["acoes_free"],
          ticker_on, ticker_pn, agora(), ticker))
    conn.commit()
    conn.close()

    par_str = f"{ticker_on} (ON) + {ticker_pn} (PN)" if ticker_pn else f"{ticker_on} (somente ON)"
    print(f"     Par: {par_str}")

    # Registra parceiro e coleta preco + fechamento
    ticker_par = ticker_pn if ticker == ticker_on else ticker_on
    if ticker_par and ticker_par != ticker:
        _registrar_e_coletar_preco(ticker_par, moeda)

        # Tambem popula acoes_anuais do parceiro com os mesmos dados
        # (a pagina do Investsite mostra ON e PN juntos — os valores ja estao em dados_anos)
        conn = sqlite3.connect(DB)
        for ano, d in dados_anos.items():
            conn.execute("""
                INSERT OR REPLACE INTO acoes_anuais
                    (ticker, ano, acoes_on, acoes_pn, acoes_total, acoes_tesouraria, acoes_free, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticker_par, ano, d["acoes_on"], d["acoes_pn"], d["acoes_total"],
                  d["acoes_tesouraria"], d["acoes_free"], agora()))
        conn.commit()
        conn.close()
        print(f"     acoes_anuais de {ticker_par} populado com {len(dados_anos)} anos.")


if __name__ == "__main__":
    import pandas as pd
    import banco
    banco.criar_banco()

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
    print("\nDone.")
