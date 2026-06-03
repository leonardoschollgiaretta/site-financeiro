"""
Coletor Dividendos — Ações Brasileiras
Fonte: Status Invest

Armazena cada pagamento individualmente em dividendos_pagamentos.
O agrupamento por ano e o filtro de Data Com são feitos pelo relatorio.py,
não aqui — assim o banco sempre tem o histórico completo e nada se perde.

Campos por pagamento:
  - data_com  : Data Com em YYYY-MM-DD (critério de direito ao dividendo)
  - data_pgto : Data de Pagamento em YYYY-MM-DD
  - tipo      : 'Dividendo', 'JCP', 'Amortização', etc.
  - valor     : R$ por ação
"""
import requests
import sqlite3
import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_utils import agora
from db_validacao import is_validado

DB    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "financeiro.db")
BASE  = "https://statusinvest.com.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": BASE,
}


def parse_data(texto):
    """Converte 'DD/MM/AAAA' → 'AAAA-MM-DD'. Retorna None se inválido."""
    if not texto or str(texto).strip() in ["", "null", "None"]:
        return None
    try:
        return datetime.strptime(str(texto).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def coletar(ticker):
    print(f"  💰 Dividendos {ticker}...")
    url = f"{BASE}/acao/companytickerprovents?ticker={ticker}&chartProventsType=2"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"     ❌ Status {resp.status_code}")
            return
        data = resp.json()
    except Exception as e:
        print(f"     ❌ Erro: {e}")
        return

    if not data or not isinstance(data, dict):
        print(f"     ⚠️  Sem dados (ticker nao encontrado no StatusInvest)")
        return

    pagamentos = data.get("assetEarningsModels", [])
    if not pagamentos:
        print(f"     ⚠️  Sem dados de dividendos")
        return

    conn = sqlite3.connect(DB)

    # Se o tipo inteiro está validado, pula tudo
    if is_validado(conn, ticker, "dividendos", 0):
        print(f"     Dividendos validados, pulando")
        conn.close()
        return

    sem_data  = 0
    pulados   = 0

    # Agrupa pagamentos por ano (apenas anos não validados)
    por_ano = {}
    for item in pagamentos:
        data_com  = parse_data(item.get("ed", ""))
        data_pgto = parse_data(item.get("pd", ""))
        tipo      = item.get("et") or item.get("etd") or "Dividendo"
        valor     = float(item.get("v") or item.get("value") or 0)

        if not data_com:
            sem_data += 1
            continue

        ano_pgto = int(data_com[:4])
        if is_validado(conn, ticker, "dividendos", ano_pgto):
            pulados += 1
            continue

        por_ano.setdefault(ano_pgto, []).append((data_com, data_pgto, tipo, valor))

    # Deleta uma vez por ano e re-insere todos os pagamentos do ano
    inseridos = 0
    for ano_pgto, items in por_ano.items():
        conn.execute(
            "DELETE FROM dividendos_pagamentos WHERE ticker=? AND substr(data_com,1,4)=?",
            (ticker, str(ano_pgto))
        )
        for data_com, data_pgto, tipo, valor in items:
            conn.execute("""
                INSERT INTO dividendos_pagamentos
                    (ticker, data_com, data_pgto, tipo, valor, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticker, data_com, data_pgto, tipo, valor, agora()))
            inseridos += 1

    if pulados:
        print(f"     {pulados} pagamento(s) em anos validados — mantidos no banco")

    conn.commit()
    conn.close()

    if sem_data:
        print(f"     ⚠️  {sem_data} pagamento(s) sem Data Com — ignorados")
    print(f"     ✅ {inseridos} pagamento(s) gravados no banco")

    # Marca que o coletor rodou para este ticker
    conn2 = sqlite3.connect(DB)
    conn2.execute(
        "UPDATE empresas SET dividendos_coletados_em=? WHERE ticker=?",
        (agora(), ticker)
    )
    conn2.commit()
    conn2.close()

    # Mostra resumo por ano para conferência
    _resumo(ticker)


def _resumo(ticker):
    """Exibe no terminal os totais por ano já gravados."""
    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT substr(data_com, 1, 4) as ano,
               tipo,
               SUM(valor)             as total
        FROM dividendos_pagamentos
        WHERE ticker=?
        GROUP BY ano, tipo
        ORDER BY ano, tipo
    """, (ticker,)).fetchall()
    conn.close()
    for ano, tipo, total in rows:
        print(f"     {ano}  {tipo:<15} R$ {total:.4f}/ação")


if __name__ == "__main__":
    import sys
    import pandas as pd
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
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
    print("\n✅ Dividendos BR finalizado!")
