"""
Relatório PDF — IMPORTAÇÕES de Indonésia e Filipinas (como destino).
Histórico 2025 (ano completo) e 2026 (parcial, ~até junho).

Reaproveita o visual do weekly_report (reportlab, A4 paisagem,
faixas coloridas, tabela 2025 azul / 2026 laranja).

Fonte: Weekly report/vessels.db  (coluna discharge = país destino).
Data de referência: bl_date; quando ausente, eta.

Uso:
    python relatorio_indo_phil_pdf.py
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle, PageBreak)

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'Weekly report', 'vessels.db')
OUT = os.path.join(BASE, 'Weekly report',
                   f'importacoes_indonesia_filipinas_{datetime.now():%Y%m%d_%H%M%S}.pdf')

CINZA = colors.HexColor('#3a3a3a')
AZUL = colors.HexColor('#1d3557')
LARANJA = colors.HexColor('#d35400')
BG_CLARO = colors.HexColor('#f4ebe0')

COR_PAIS = {
    'Indonesia':  colors.HexColor('#9d2235'),  # vermelho (bandeira)
    'Philippines': colors.HexColor('#0038a8'),  # azul (bandeira)
}

ANO_A = '2025'
ANO_B = '2026'
MESES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# data de referência: bl_date, senão eta
DATA = "COALESCE(NULLIF(bl_date,''), eta)"
ANO_SQL = f"substr({DATA},1,4)"
MES_SQL = f"substr({DATA},6,2)"


# ============================== QUERIES ==============================

def conectar():
    return sqlite3.connect(DB)


def key_metrics(c, pais):
    sql = f"""
        SELECT {ANO_SQL} ano, SUM(quantity_mt), COUNT(*),
               CAST(AVG(quantity_mt) AS INTEGER)
        FROM embarques
        WHERE discharge = ? AND {ANO_SQL} IN ('{ANO_A}','{ANO_B}')
        GROUP BY ano
    """
    rows = {r[0]: r for r in c.execute(sql, [pais]).fetchall()}
    a = rows.get(ANO_A, (ANO_A, 0, 0, 0))
    b = rows.get(ANO_B, (ANO_B, 0, 0, 0))
    return [
        ('Total Volume (mt)', a[1] or 0, b[1] or 0),
        ('Shipments',         a[2] or 0, b[2] or 0),
        ('Avg Shipment (mt)', a[3] or 0, b[3] or 0),
    ]


def monthly_volume(c, pais):
    sql = f"""
        SELECT {ANO_SQL} ano, {MES_SQL} mes, SUM(quantity_mt)
        FROM embarques
        WHERE discharge = ? AND {ANO_SQL} IN ('{ANO_A}','{ANO_B}')
        GROUP BY ano, mes
    """
    d = {(r[0], r[1]): r[2] for r in c.execute(sql, [pais]).fetchall()}
    out = []
    for i, lbl in enumerate(MESES, start=1):
        mes = f'{i:02d}'
        out.append((lbl, d.get((ANO_A, mes), 0) or 0, d.get((ANO_B, mes), 0) or 0))
    return out


def commodity_pivot(c, pais):
    sql = f"""
        SELECT commodity,
               SUM(CASE WHEN {ANO_SQL}='{ANO_A}' THEN quantity_mt ELSE 0 END),
               SUM(CASE WHEN {ANO_SQL}='{ANO_B}' THEN quantity_mt ELSE 0 END)
        FROM embarques
        WHERE discharge = ? AND {ANO_SQL} IN ('{ANO_A}','{ANO_B}')
        GROUP BY commodity
        ORDER BY (SUM(CASE WHEN {ANO_SQL}='{ANO_A}' THEN quantity_mt ELSE 0 END) +
                  SUM(CASE WHEN {ANO_SQL}='{ANO_B}' THEN quantity_mt ELSE 0 END)) DESC
    """
    return c.execute(sql, [pais]).fetchall()


def origin_pivot(c, pais, top_n=12):
    sql = f"""
        SELECT country,
               SUM(CASE WHEN {ANO_SQL}='{ANO_A}' THEN quantity_mt ELSE 0 END),
               SUM(CASE WHEN {ANO_SQL}='{ANO_B}' THEN quantity_mt ELSE 0 END)
        FROM embarques
        WHERE discharge = ? AND {ANO_SQL} IN ('{ANO_A}','{ANO_B}')
        GROUP BY country
        ORDER BY (SUM(CASE WHEN {ANO_SQL}='{ANO_A}' THEN quantity_mt ELSE 0 END) +
                  SUM(CASE WHEN {ANO_SQL}='{ANO_B}' THEN quantity_mt ELSE 0 END)) DESC
    """
    rows = c.execute(sql, [pais]).fetchall()
    rows = [(n or '(sem origem)', a, b) for n, a, b in rows]
    top = rows[:top_n]
    oa = sum(r[1] for r in rows[top_n:]); ob = sum(r[2] for r in rows[top_n:])
    if oa or ob:
        top.append(('Others', oa, ob))
    return top


# ============================== FORMATAÇÃO ==============================

def fmt_int(v):
    if v is None or v == 0:
        return '-'
    return f'{int(v):,}'.replace(',', '.')


def estilo_header_anos():
    return [
        ('BACKGROUND', (0, 0), (0, 0), CINZA),
        ('BACKGROUND', (1, 0), (1, 0), AZUL),
        ('BACKGROUND', (2, 0), (2, 0), LARANJA),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, 0), 'RIGHT'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.3, colors.white),
        ('GRID', (0, 1), (-1, -1), 0.2, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_CLARO]),
    ]


def _cols(largura_cm):
    return [largura_cm * 0.50 * cm, largura_cm * 0.25 * cm, largura_cm * 0.25 * cm]


def _tabela_total(body, largura_cm):
    t = Table(body, colWidths=_cols(largura_cm))
    style = estilo_header_anos()
    style.append(('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'))
    style.append(('BACKGROUND', (0, -1), (-1, -1), CINZA))
    style.append(('TEXTCOLOR', (0, -1), (-1, -1), colors.white))
    for i, row in enumerate(body):
        if row[0] == 'Others':
            style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Oblique'))
    t.setStyle(TableStyle(style))
    return t


def tabela_key_metrics(c, pais, largura_cm):
    body = [['Metric', ANO_A, ANO_B]]
    for nome, va, vb in key_metrics(c, pais):
        body.append([nome, fmt_int(va), fmt_int(vb)])
    t = Table(body, colWidths=_cols(largura_cm))
    style = estilo_header_anos()
    style.append(('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'))
    t.setStyle(TableStyle(style))
    return t


def tabela_monthly(c, pais, largura_cm):
    dados = monthly_volume(c, pais)
    body = [['Month', ANO_A, ANO_B]]
    for mes, va, vb in dados:
        body.append([mes, fmt_int(va), fmt_int(vb)])
    body.append(['TOTAL', fmt_int(sum(d[1] for d in dados)), fmt_int(sum(d[2] for d in dados))])
    return _tabela_total(body, largura_cm)


def tabela_lista(c, pais, titulo_col, fonte_func, largura_cm):
    body = [[titulo_col, ANO_A, ANO_B]]
    ta = tb = 0
    for nome, va, vb in fonte_func(c, pais):
        body.append([str(nome), fmt_int(va), fmt_int(vb)])
        ta += va or 0; tb += vb or 0
    body.append(['TOTAL', fmt_int(ta), fmt_int(tb)])
    return _tabela_total(body, largura_cm)


def faixa_titulo(texto, largura_cm, cor=CINZA, numero=''):
    prefix = f'{numero} &nbsp;&nbsp;' if numero else ''
    t = Table([[Paragraph(f'<font color="white" size="12"><b>{prefix}▶ {texto}</b></font>', PS_FAIXA)]],
              colWidths=[largura_cm * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t


def faixa_resumo(texto, largura_cm):
    t = Table([[Paragraph(f'<font color="#444444" size="8.5"><i>{texto}</i></font>', PS_FAIXA)]],
              colWidths=[largura_cm * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ]))
    return t


def faixa_sub(texto, largura_cm):
    t = Table([[Paragraph(f'<font color="white" size="9"><b>{texto}</b></font>', PS_FAIXA)]],
              colWidths=[largura_cm * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CINZA),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t


def _col_box(linhas, largura_cm):
    t = Table(linhas, colWidths=[largura_cm * cm])
    t.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


# ============================== PÁGINA ==============================

def montar_pagina(c, pais, cor=CINZA, numero='', resumo=''):
    flow = []
    LARG = 9.0
    largura_total = LARG * 3
    flow.append(faixa_titulo(f'{pais.upper()} — IMPORTS', largura_total, cor=cor, numero=numero))
    if resumo:
        flow.append(faixa_resumo(resumo, largura_total))
    flow.append(Spacer(1, 0.15 * cm))

    esq = _col_box([
        [faixa_sub('KEY METRICS', LARG - 0.1)],
        [tabela_key_metrics(c, pais, LARG - 0.1)],
        [Spacer(1, 0.3 * cm)],
        [faixa_sub('MONTHLY VOLUME (mt)', LARG - 0.1)],
        [tabela_monthly(c, pais, LARG - 0.1)],
    ], LARG - 0.1)

    centro = _col_box([
        [faixa_sub('BY COMMODITY', LARG - 0.1)],
        [tabela_lista(c, pais, 'Commodity', commodity_pivot, LARG - 0.1)],
    ], LARG - 0.1)

    dir_ = _col_box([
        [faixa_sub('ORIGIN (LOAD COUNTRY)', LARG - 0.1)],
        [tabela_lista(c, pais, 'Origin', origin_pivot, LARG - 0.1)],
    ], LARG - 0.1)

    grid = Table([[esq, centro, dir_]], colWidths=[LARG * cm] * 3)
    grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    flow.append(grid)
    return flow


def pagina_capa(largura_total):
    flow = []
    flow.append(faixa_titulo('IMPORTAÇÕES — INDONÉSIA & FILIPINAS (2025–2026)', largura_total, cor=CINZA))
    flow.append(Spacer(1, 0.5 * cm))
    txt = [
        ('Fonte', 'Weekly report / vessels.db (base 2025 2026 database.xlsx)'),
        ('Escopo', 'Tudo que tem Indonésia ou Filipinas como DESTINO (discharge), todas as commodities'),
        ('Período', '2025 = ano completo | 2026 = ANO CORRENTE / PARCIAL (vai até ~junho)'),
        ('Data de referência', 'Bill of Lading (bl_date); quando ausente, ETA'),
        ('Unidade', 'toneladas métricas (mt)'),
    ]
    for k, v in txt:
        flow.append(Paragraph(f'<b>{k}:</b> {v}', PS_TXT))
        flow.append(Spacer(1, 0.2 * cm))
    flow.append(Spacer(1, 0.4 * cm))
    avisos = [
        '⚠ 2026 é parcial — NÃO comparar o total de 2026 com o de 2025 como anos fechados.',
        '⚠ Junho/2026 tem poucos embarques (mês ainda em andamento na data da base).',
        '⚠ Páginas seguintes: azul = 2025, laranja = 2026 (mesmo padrão do weekly report).',
    ]
    for a in avisos:
        flow.append(Paragraph(f'<font color="#C00000">{a}</font>', PS_TXT))
        flow.append(Spacer(1, 0.15 * cm))
    return flow


# ============================== MAIN ==============================

styles = getSampleStyleSheet()
PS_FAIXA = ParagraphStyle('f', parent=styles['Normal'], fontSize=10, leading=12,
                          textColor=colors.white)
PS_TXT = ParagraphStyle('t', parent=styles['Normal'], fontSize=11, leading=16)


def gerar():
    print(f'Gerando: {OUT}')
    c = conectar().cursor()
    doc = SimpleDocTemplate(
        OUT, pagesize=landscape(A4),
        leftMargin=1.0 * cm, rightMargin=1.0 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        title='Importações Indonésia & Filipinas 2025-2026',
    )
    story = []
    story.extend(pagina_capa(27.0))
    story.append(PageBreak())

    paises = [
        ('Indonesia', 'Importações da Indonésia por mês, commodity e país de origem. '
                      'Trigo e farelo de soja dominam. Compare 2025 (azul, completo) vs 2026 (laranja, parcial).'),
        ('Philippines', 'Importações das Filipinas por mês, commodity e país de origem. '
                        'Forte concentração em trigo; milho ganha peso em 2026.'),
    ]
    n = len(paises)
    for i, (pais, resumo) in enumerate(paises):
        cor = COR_PAIS.get(pais, CINZA)
        story.extend(montar_pagina(c, pais, cor=cor, numero=f'{i+1}/{n}', resumo=resumo))
        if i < n - 1:
            story.append(PageBreak())

    doc.build(story)
    c.connection.close()
    print(f'OK: {OUT}')


if __name__ == '__main__':
    gerar()
