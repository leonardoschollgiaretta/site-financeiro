"""
Gera o relatório semanal em PDF — bloco Brazil Export.

Páginas:
  1. ALL COMMODITIES (TOTAL)
  2. SOYBEAN
  3. CORN
  4. SOYBEAN MEAL

Cada página: Key Metrics + Monthly Volume (esquerda) | Origin Ports (centro) | Destinations (direita)

Uso:
    python relatorio_pdf.py
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
DB = os.path.join(BASE, 'vessels.db')
OUT = os.path.join(BASE, f'weekly_report_{datetime.now():%Y%m%d_%H%M%S}.pdf')

# Cores do template
CINZA = colors.HexColor('#3a3a3a')
AZUL = colors.HexColor('#1d3557')
LARANJA = colors.HexColor('#d35400')
BG_CLARO = colors.HexColor('#f4ebe0')

# Paleta por commodity (faixa do título)
COR_PAGINA = {
    'all':          colors.HexColor('#3a3a3a'),  # cinza escuro
    'soybean':      colors.HexColor('#2d6a4f'),  # verde
    'corn':         colors.HexColor('#c9a227'),  # amarelo mostarda
    'soybean_meal': colors.HexColor('#6f4518'),  # marrom
}

ANO_A = '2025'
ANO_B = '2026'

MESES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


# ============================== QUERIES ==============================

def conectar():
    return sqlite3.connect(DB)


def filtro_commodity_sql(commodity: str | None) -> tuple[str, list]:
    """Retorna ('AND commodity = ?', [valor]) ou ('', [])."""
    if commodity is None:
        return '', []
    return ' AND commodity = ?', [commodity]


def key_metrics(c, commodity):
    """Total volume, shipments, avg shipment — por ano."""
    fc, par = filtro_commodity_sql(commodity)
    sql = f"""
        SELECT substr(bl_date,1,4) AS ano,
               SUM(quantity_mt), COUNT(*),
               CAST(AVG(quantity_mt) AS INTEGER)
        FROM embarques
        WHERE country='Brazil' AND bl_date IS NOT NULL {fc}
        GROUP BY ano
    """
    rows = {r[0]: r for r in c.execute(sql, par).fetchall()}
    a = rows.get(ANO_A, (ANO_A, 0, 0, 0))
    b = rows.get(ANO_B, (ANO_B, 0, 0, 0))
    return [
        ('Total Volume (mt)', a[1] or 0, b[1] or 0),
        ('Shipments',         a[2] or 0, b[2] or 0),
        ('Avg Shipment (mt)', a[3] or 0, b[3] or 0),
    ]


def monthly_volume(c, commodity):
    """Volume mensal por ano. Retorna lista de (mes_label, vol_2025, vol_2026)."""
    fc, par = filtro_commodity_sql(commodity)
    sql = f"""
        SELECT substr(bl_date,1,4) AS ano, substr(bl_date,6,2) AS mes,
               SUM(quantity_mt)
        FROM embarques
        WHERE country='Brazil' AND bl_date IS NOT NULL {fc}
        GROUP BY ano, mes
    """
    d = {(r[0], r[1]): r[2] for r in c.execute(sql, par).fetchall()}
    out = []
    for i, lbl in enumerate(MESES, start=1):
        mes = f'{i:02d}'
        out.append((lbl, d.get((ANO_A, mes), 0) or 0, d.get((ANO_B, mes), 0) or 0))
    return out


def ports_pivot(c, commodity):
    """Top portos BR (por SUM 2025+2026). Retorna lista (port, vol_2025, vol_2026)."""
    fc, par = filtro_commodity_sql(commodity)
    sql = f"""
        SELECT port,
               SUM(CASE WHEN substr(bl_date,1,4)='{ANO_A}' THEN quantity_mt ELSE 0 END),
               SUM(CASE WHEN substr(bl_date,1,4)='{ANO_B}' THEN quantity_mt ELSE 0 END)
        FROM embarques
        WHERE country='Brazil' AND port IS NOT NULL {fc}
        GROUP BY port
        ORDER BY (SUM(CASE WHEN substr(bl_date,1,4)='{ANO_A}' THEN quantity_mt ELSE 0 END) +
                  SUM(CASE WHEN substr(bl_date,1,4)='{ANO_B}' THEN quantity_mt ELSE 0 END)) DESC
    """
    return c.execute(sql, par).fetchall()


def destinations_pivot(c, commodity, top_n=15):
    """Top destinos. Lista (destino, vol_2025, vol_2026). Linha 'Others' agrega o resto."""
    fc, par = filtro_commodity_sql(commodity)
    sql = f"""
        SELECT discharge,
               SUM(CASE WHEN substr(bl_date,1,4)='{ANO_A}' THEN quantity_mt ELSE 0 END),
               SUM(CASE WHEN substr(bl_date,1,4)='{ANO_B}' THEN quantity_mt ELSE 0 END)
        FROM embarques
        WHERE country='Brazil' AND discharge IS NOT NULL {fc}
        GROUP BY discharge
        ORDER BY (SUM(CASE WHEN substr(bl_date,1,4)='{ANO_A}' THEN quantity_mt ELSE 0 END) +
                  SUM(CASE WHEN substr(bl_date,1,4)='{ANO_B}' THEN quantity_mt ELSE 0 END)) DESC
    """
    rows = c.execute(sql, par).fetchall()
    top = rows[:top_n]
    outros_a = sum(r[1] for r in rows[top_n:])
    outros_b = sum(r[2] for r in rows[top_n:])
    if outros_a or outros_b:
        top.append(('Others', outros_a, outros_b))
    return top


# ============================== FORMATAÇÃO ==============================

def fmt_int(v):
    if v is None or v == 0:
        return '-'
    return f'{int(v):,}'.replace(',', '.')


# ============================== TABELAS ==============================

def header_grupo(titulo: str, span: int = 3):
    """Faixa cinza-escura com o título do bloco."""
    return Table(
        [[Paragraph(f'<font color="white"><b>▶ {titulo}</b></font>', PS_HEADER)]],
        colWidths=[2.5 * cm * span],
    )


def estilo_header_anos():
    """Estilo da linha 2025 (azul) / 2026 (laranja)."""
    return [
        ('BACKGROUND', (0, 0), (0, 0), CINZA),  # primeira col header em cinza
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


def _calc_cols(largura_cm: float):
    """Divide largura: 50% nome, 25% ano A, 25% ano B."""
    return [largura_cm * 0.50 * cm,
            largura_cm * 0.25 * cm,
            largura_cm * 0.25 * cm]


def tabela_key_metrics(c, commodity, largura_cm: float):
    dados = key_metrics(c, commodity)
    body = [['Metric', ANO_A, ANO_B]]
    for nome, va, vb in dados:
        body.append([nome, fmt_int(va), fmt_int(vb)])
    t = Table(body, colWidths=_calc_cols(largura_cm))
    style = estilo_header_anos()
    style.append(('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'))
    t.setStyle(TableStyle(style))
    return t


def tabela_monthly(c, commodity, largura_cm: float):
    dados = monthly_volume(c, commodity)
    body = [['Month', ANO_A, ANO_B]]
    for mes, va, vb in dados:
        body.append([mes, fmt_int(va), fmt_int(vb)])
    total_a = sum(d[1] for d in dados)
    total_b = sum(d[2] for d in dados)
    body.append(['TOTAL', fmt_int(total_a), fmt_int(total_b)])
    t = Table(body, colWidths=_calc_cols(largura_cm))
    style = estilo_header_anos()
    style.append(('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'))
    style.append(('BACKGROUND', (0, -1), (-1, -1), CINZA))
    style.append(('TEXTCOLOR', (0, -1), (-1, -1), colors.white))
    t.setStyle(TableStyle(style))
    return t


def tabela_lista(c, commodity, titulo_col, fonte_func, largura_cm: float):
    dados = fonte_func(c, commodity)
    body = [[titulo_col, ANO_A, ANO_B]]
    total_a = total_b = 0
    for nome, va, vb in dados:
        body.append([str(nome), fmt_int(va), fmt_int(vb)])
        total_a += va or 0
        total_b += vb or 0
    body.append(['TOTAL', fmt_int(total_a), fmt_int(total_b)])
    t = Table(body, colWidths=_calc_cols(largura_cm))
    style = estilo_header_anos()
    style.append(('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'))
    style.append(('BACKGROUND', (0, -1), (-1, -1), CINZA))
    style.append(('TEXTCOLOR', (0, -1), (-1, -1), colors.white))
    # destacar "Others" em itálico
    for i, row in enumerate(body):
        if row[0] == 'Others':
            style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Oblique'))
    t.setStyle(TableStyle(style))
    return t


def faixa_titulo(texto: str, largura_cm: float, cor=CINZA, numero: str = ''):
    """Faixa colorida com numero da pagina + titulo."""
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


def faixa_resumo(texto: str, largura_cm: float):
    """Caixa clara abaixo do titulo com explicacao da pagina."""
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


def faixa_sub(texto: str, largura_cm: float):
    """Faixa secundária cinza (Key Metrics, Monthly Volume, etc)."""
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


# ============================== PÁGINA ==============================

def montar_pagina(c, titulo_pagina: str, commodity: str | None,
                  cor=CINZA, numero: str = '', resumo: str = ''):
    flow = []
    # A4 paisagem útil ~ 27.7cm. Reservamos: 9.0 + 9.0 + 9.0 = 27.0cm
    LARG_ESQ = 9.0
    LARG_CENTRO = 9.0
    LARG_DIR = 9.0
    largura_total = LARG_ESQ + LARG_CENTRO + LARG_DIR
    flow.append(faixa_titulo(titulo_pagina, largura_total, cor=cor, numero=numero))
    if resumo:
        flow.append(faixa_resumo(resumo, largura_total))
    flow.append(Spacer(1, 0.15 * cm))

    # === COLUNA ESQUERDA (Key Metrics + Monthly) ===
    esq = [
        [faixa_sub('KEY METRICS', LARG_ESQ - 0.1)],
        [tabela_key_metrics(c, commodity, LARG_ESQ - 0.1)],
        [Spacer(1, 0.3 * cm)],
        [faixa_sub('MONTHLY VOLUME', LARG_ESQ - 0.1)],
        [tabela_monthly(c, commodity, LARG_ESQ - 0.1)],
    ]
    tab_esq = Table(esq, colWidths=[(LARG_ESQ - 0.1) * cm])
    tab_esq.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    # === COLUNA CENTRO (Origin Ports) ===
    centro = [
        [faixa_sub('ORIGIN PORTS', LARG_CENTRO - 0.1)],
        [tabela_lista(c, commodity, 'Port', ports_pivot, LARG_CENTRO - 0.1)],
    ]
    tab_centro = Table(centro, colWidths=[(LARG_CENTRO - 0.1) * cm])
    tab_centro.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    # === COLUNA DIREITA (Destinations) ===
    dir_ = [
        [faixa_sub('DESTINATIONS', LARG_DIR - 0.1)],
        [tabela_lista(c, commodity, 'Destination', destinations_pivot, LARG_DIR - 0.1)],
    ]
    tab_dir = Table(dir_, colWidths=[(LARG_DIR - 0.1) * cm])
    tab_dir.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    # Junta as 3 colunas
    grid = Table([[tab_esq, tab_centro, tab_dir]],
                 colWidths=[LARG_ESQ * cm, LARG_CENTRO * cm, LARG_DIR * cm])
    grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    flow.append(grid)
    return flow


# ============================== MAIN ==============================

styles = getSampleStyleSheet()
PS_HEADER = ParagraphStyle('h', parent=styles['Normal'], fontSize=10, leading=12)
PS_FAIXA = ParagraphStyle('f', parent=styles['Normal'], fontSize=10, leading=12,
                          textColor=colors.white)


def gerar():
    print(f'Gerando: {OUT}')
    c = conectar().cursor()

    doc = SimpleDocTemplate(
        OUT, pagesize=landscape(A4),
        leftMargin=1.0 * cm, rightMargin=1.0 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        title='Weekly Vessel Report — Brazil Export',
    )

    story = []

    paginas = [
        {
            'titulo': 'ALL COMMODITIES (TOTAL)',
            'commodity': None,
            'cor_key': 'all',
            'resumo': (
                'Visão consolidada de TODAS as commodities exportadas pelo Brasil. '
                'KEY METRICS (esquerda): volume total, número de embarques e tamanho médio por embarque, comparando 2025 vs 2026. '
                'MONTHLY VOLUME (esquerda-inferior): evolução mensal do volume embarcado nos dois anos. '
                'ORIGIN PORTS (centro): ranking dos portos brasileiros por volume escoado. '
                'DESTINATIONS (direita): top 15 países de destino + linha "Others" agregando os demais.'
            ),
        },
        {
            'titulo': 'SOYBEAN',
            'commodity': 'Soybean',
            'cor_key': 'soybean',
            'resumo': (
                'Foco exclusivo em SOYBEAN (soja em grão). Mesma estrutura da página anterior, mas filtrada apenas para soja. '
                'Útil para acompanhar a safra brasileira, sazonalidade (pico fev-mai) e concentração de demanda na China.'
            ),
        },
        {
            'titulo': 'CORN',
            'commodity': 'Corn',
            'cor_key': 'corn',
            'resumo': (
                'Foco exclusivo em CORN (milho). Mostra a janela típica da safrinha brasileira (jul-out) '
                'e a diversificação maior de destinos comparada à soja.'
            ),
        },
        {
            'titulo': 'SOYBEAN MEAL',
            'commodity': 'Soybean Meal',
            'cor_key': 'soybean_meal',
            'resumo': (
                'Foco exclusivo em SOYBEAN MEAL (farelo de soja). Produto processado que tende a fluir '
                'para destinos diferentes do grão (mais Europa/Ásia para consumo de ração animal).'
            ),
        },
    ]

    n = len(paginas)
    for i, p in enumerate(paginas):
        cor = COR_PAGINA.get(p['cor_key'], CINZA)
        numero = f'{i + 1}/{n}'
        story.extend(montar_pagina(
            c, p['titulo'], p['commodity'],
            cor=cor, numero=numero, resumo=p['resumo'],
        ))
        if i < n - 1:
            story.append(PageBreak())

    doc.build(story)
    c.connection.close()
    print(f'OK: {OUT}')


if __name__ == '__main__':
    gerar()
