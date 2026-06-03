"""
Carga do Excel '2025 2026 database.xlsx' para SQLite (vessels.db).

Lê as abas 'data25' e 'data26' (formato com 2 linhas por embarque):
  - linha principal: Commodity, Load=Country, Origin, Discharge, Vessel, ETA, BL, Quantity, Status
  - linha auxiliar: (None, Port, None, None, IMO, None, None, None, None)

Refaz a tabela do zero a cada execução.

Uso:
    python carga_db.py
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime

import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
EXCEL = os.path.join(BASE, 'database', '2025 2026 database.xlsx')
DB = os.path.join(BASE, 'vessels.db')

ABAS = ['data25', 'data26']

SCHEMA = """
DROP TABLE IF EXISTS embarques;
CREATE TABLE embarques (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    commodity   TEXT,
    country     TEXT,        -- país de carga (= coluna 'Load')
    port        TEXT,        -- porto de carga (linha auxiliar)
    origin      TEXT,
    discharge   TEXT,        -- país destino
    vessel      TEXT,
    imo         INTEGER,
    eta         TEXT,        -- ISO YYYY-MM-DD ou NULL
    bl_date     TEXT,        -- ISO YYYY-MM-DD ou NULL
    quantity_mt INTEGER,
    quantity_raw TEXT,
    status      TEXT,
    fonte_aba   TEXT         -- 'data25' ou 'data26'
);
CREATE INDEX idx_bl ON embarques(bl_date);
CREATE INDEX idx_status ON embarques(status);
CREATE INDEX idx_commodity ON embarques(commodity);
CREATE INDEX idx_country ON embarques(country);
CREATE INDEX idx_port ON embarques(port);
CREATE INDEX idx_discharge ON embarques(discharge);
"""


def _parse_qty(v) -> tuple[int | None, str | None]:
    if v is None:
        return None, None
    s = str(v).strip()
    if not s or s == '-':
        return None, s
    limpo = re.sub(r'\s+', '', s.replace('\xa0', ''))
    limpo = re.sub(r'(?i)(mt|kg|t)$', '', limpo)
    limpo = limpo.replace(',', '').replace('.', '')
    try:
        return int(limpo), s
    except ValueError:
        return None, s


def _parse_data(v) -> str | None:
    if v is None or v == '-':
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    s = str(v).strip()
    return s if s and s != '-' else None


def _parse_imo(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def carregar():
    if not os.path.exists(EXCEL):
        raise FileNotFoundError(f'Excel não encontrado: {EXCEL}')

    print(f'Lendo: {EXCEL}')
    wb = openpyxl.load_workbook(EXCEL, read_only=True, data_only=True)
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)

    total_ins = 0
    total_pul = 0
    for aba in ABAS:
        ws = wb[aba]
        # transformar gerador em lista pra poder iterar de 2 em 2
        rows = list(ws.iter_rows(values_only=True))
        ins = pul = 0

        # encontrar primeira linha de dados (após cabeçalho 'Commodity, Load, ...')
        i = 0
        while i < len(rows) and (rows[i][0] != 'Commodity'):
            i += 1
        i += 1  # pula o próprio header

        while i < len(rows):
            principal = rows[i]
            auxiliar = rows[i + 1] if i + 1 < len(rows) else None

            commodity = principal[0]
            if not commodity:
                # linha vazia ou auxiliar órfã — pula 1
                pul += 1
                i += 1
                continue

            load_country = principal[1]
            origin       = principal[2]
            discharge    = principal[3]
            vessel       = principal[4]
            eta          = principal[5]
            bl           = principal[6]
            quantity     = principal[7]
            status       = principal[8]

            port = imo = None
            advance = 1
            if auxiliar is not None and auxiliar[0] is None and (auxiliar[1] or auxiliar[4]):
                port = auxiliar[1]
                imo = _parse_imo(auxiliar[4])
                advance = 2

            qty_mt, qty_raw = _parse_qty(quantity)

            conn.execute("""
                INSERT INTO embarques
                    (commodity, country, port, origin, discharge, vessel, imo,
                     eta, bl_date, quantity_mt, quantity_raw, status, fonte_aba)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                commodity, load_country, port, origin, discharge, vessel, imo,
                _parse_data(eta), _parse_data(bl),
                qty_mt, qty_raw,
                status,
                aba,
            ))
            ins += 1
            i += advance

        total_ins += ins
        total_pul += pul
        print(f'  {aba}: {ins:,} inseridos | {pul} pulados')

    conn.commit()
    conn.close()
    wb.close()
    print(f'TOTAL: {total_ins:,} embarques.')


def resumo():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    print()
    print('--- RESUMO ---')
    print(f'Total embarques: {c.execute("SELECT COUNT(*) FROM embarques").fetchone()[0]:,}')
    print(f'Total mt       : {c.execute("SELECT SUM(quantity_mt) FROM embarques").fetchone()[0]:,}')
    print()
    print('Brazil export — por ano:')
    for r in c.execute("""
        SELECT substr(bl_date,1,4), COUNT(*), SUM(quantity_mt)
        FROM embarques WHERE country='Brazil'
        GROUP BY substr(bl_date,1,4)
        ORDER BY 1
    """):
        print(f'  {r[0]}: {r[1]:>5} shipments | {r[2]:>15,} mt')
    print()
    print('Brazil 2025 — top 5 portos:')
    for r in c.execute("""
        SELECT port, SUM(quantity_mt) FROM embarques
        WHERE country='Brazil' AND substr(bl_date,1,4)='2025' AND port IS NOT NULL
        GROUP BY port ORDER BY 2 DESC LIMIT 5
    """):
        print(f'  {r[0]:<25} {r[1]:>15,} mt')
    print()
    print('Brazil 2025 — top 5 destinos:')
    for r in c.execute("""
        SELECT discharge, SUM(quantity_mt) FROM embarques
        WHERE country='Brazil' AND substr(bl_date,1,4)='2025'
        GROUP BY discharge ORDER BY 2 DESC LIMIT 5
    """):
        print(f'  {r[0]:<20} {r[1]:>15,} mt')
    conn.close()


if __name__ == '__main__':
    carregar()
    resumo()
