"""
Gera PDF comparativo das 6 empresas: ISAE4, CMIG4, TAEE4, CPLE3, SAPR4, SBSP3.
Usa o que existe no financeiro.db; marca gaps explicitamente.
"""
import os, json, sqlite3
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                  PageBreak, Image, KeepTogether)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, 'financeiro.db')
OUT_DIR = os.path.join(BASE, 'outputs')
CHART_DIR = os.path.join(OUT_DIR, '_charts_eletricas')
os.makedirs(CHART_DIR, exist_ok=True)
PDF_OUT = os.path.join(OUT_DIR, f'analise_eletricas_saneamento_{datetime.now():%Y%m%d_%H%M}.pdf')

ALVOS = ['ISAE4','CMIG4','TAEE4','CPLE3','SAPR4','SBSP3']
ANOS = [2021, 2022, 2023, 2024, 2025]

CORES = {
    'ISAE4': '#1f4e79', 'CMIG4': '#c00000', 'TAEE4': '#548235',
    'CPLE3': '#bf8f00', 'SAPR4': '#7030a0', 'SBSP3': '#0070c0',
}

NOMES = {
    'ISAE4': 'ISA Energia Brasil',
    'CMIG4': 'Cemig',
    'TAEE4': 'Taesa',
    'CPLE3': 'Copel',
    'SAPR4': 'Sanepar',
    'SBSP3': 'Sabesp',
}

SETORES = {
    'ISAE4': 'Transmissão de Energia',
    'CMIG4': 'Energia Integrada (Ger+Tra+Dist) — MG',
    'TAEE4': 'Transmissão de Energia',
    'CPLE3': 'Energia Integrada (Ger+Dist) — PR',
    'SAPR4': 'Saneamento Básico — PR',
    'SBSP3': 'Saneamento Básico — SP',
}

# ---------- Extração ----------
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def get_dados(tk):
    info = {'ticker': tk, 'nome': NOMES[tk], 'setor': SETORES[tk]}
    variantes = {'SAPR4':['SAPR4','SAPR3','SAPR11'],
                 'SBSP3':['SBSP3','SBSP4'],
                 'CPLE3':['CPLE3','CPLE6','CPLE11']}.get(tk, [tk])
    fin = {}; tfin = None
    for v in variantes:
        cur.execute("SELECT * FROM financeiros_anuais WHERE ticker=? ORDER BY ano", (v,))
        rows = cur.fetchall()
        if rows:
            tfin = v
            for r in rows:
                d = dict(r)
                if d['ano'] in ANOS or d['ano']==2020:
                    fin[d['ano']] = d
            break
    info['ticker_fin'] = tfin; info['fin'] = fin

    # Preços
    precos = {}
    for v in variantes:
        cur.execute("SELECT * FROM precos_anuais WHERE ticker=? ORDER BY ano", (v,))
        rows = cur.fetchall()
        if rows:
            for r in rows:
                d = dict(r)
                if d['ano'] in ANOS: precos[d['ano']] = d
            info['ticker_prc'] = v; break
    info['precos'] = precos

    cur.execute("SELECT preco FROM preco_atual WHERE ticker=?", (tk,))
    r = cur.fetchone()
    info['preco_atual'] = r['preco'] if r else None

    # Dividendos
    divs = defaultdict(float)
    cur.execute("SELECT data_com, valor FROM dividendos_pagamentos WHERE ticker=?", (tk,))
    for r in cur.fetchall():
        try:
            ano = int(str(r['data_com'])[:4])
            if ano in ANOS:
                divs[ano] += float(r['valor'] or 0)
        except: pass
    info['divs'] = dict(divs)

    # Ações
    acoes = {}
    cur.execute("SELECT ano, acoes_total FROM acoes_anuais WHERE ticker=?", (tk,))
    for r in cur.fetchall():
        if r['ano'] in ANOS: acoes[r['ano']] = r['acoes_total']
    info['acoes'] = acoes
    return info

DADOS = {tk: get_dados(tk) for tk in ALVOS}

# ---------- Indicadores derivados ----------
def safe_div(a, b):
    try:
        if a is None or b is None or b == 0: return None
        return a / b
    except: return None

def calc_ind(d):
    """Calcula indicadores derivados ano a ano."""
    out = {}
    for ano, f in d['fin'].items():
        if ano not in ANOS: continue
        r = {}
        r['receita'] = f.get('receita_liquida')
        r['ebitda'] = f.get('ebitda')
        r['ebit'] = f.get('ebit')
        r['lucro_liq'] = f.get('lucro_liquido')
        r['div_liq'] = f.get('divida_liquida')
        r['div_bruta'] = f.get('divida_bruta')
        r['pl'] = f.get('patrimonio_liquido')
        r['ativo'] = f.get('ativo_total')
        r['fco'] = f.get('fco')
        r['capex'] = f.get('capex')
        r['fcl'] = f.get('fcl')

        r['marg_ebitda'] = safe_div(r['ebitda'], r['receita'])
        r['marg_liq'] = safe_div(r['lucro_liq'], r['receita'])
        r['roe'] = safe_div(r['lucro_liq'], r['pl'])
        r['divliq_ebitda'] = safe_div(r['div_liq'], r['ebitda'])
        # ROIC simplificado
        cap_invest = (r['pl'] or 0) + (r['div_liq'] or 0)
        nopat = (r['ebit'] or 0) * 0.66  # 34% efetivo aprox
        r['roic'] = safe_div(nopat, cap_invest) if cap_invest else None

        # DPA e DY
        acs = d['acoes'].get(ano)
        div_total = d['divs'].get(ano)
        r['dpa'] = safe_div(div_total, acs) if acs else None
        preco = d['precos'].get(ano, {}).get('preco_medio')
        r['dy'] = safe_div(r['dpa'], preco) if r['dpa'] and preco else None
        r['payout'] = safe_div(div_total, r['lucro_liq']) if div_total and r['lucro_liq'] else None

        out[ano] = r
    # DY atual
    pa = d['preco_atual']
    div24 = d['divs'].get(2024) or d['divs'].get(2025)
    acs = d['acoes'].get(2024) or d['acoes'].get(2025)
    if pa and acs and div24:
        d['dy_atual'] = (div24/acs)/pa
    else:
        d['dy_atual'] = None
    return out

for tk in ALVOS:
    DADOS[tk]['ind'] = calc_ind(DADOS[tk])

# ---------- Helpers de formatação ----------
def fmt_milhoes(v):
    if v is None: return 'N/D'
    try:
        v = float(v)
        # heurística: assume já em reais
        bi = v / 1e9
        if abs(bi) >= 1: return f'{bi:.2f} bi'
        return f'{v/1e6:.0f} mi'
    except: return 'N/D'

def fmt_pct(v, casas=1):
    if v is None: return 'N/D'
    try: return f'{v*100:.{casas}f}%'
    except: return 'N/D'

def fmt_x(v, casas=2):
    if v is None: return 'N/D'
    try: return f'{v:.{casas}f}x'
    except: return 'N/D'

def fmt_num(v, casas=2):
    if v is None: return 'N/D'
    try: return f'{v:.{casas}f}'
    except: return 'N/D'

# ---------- Charts ----------
plt.rcParams.update({'font.size':9, 'axes.titlesize':10, 'axes.labelsize':9})

def chart_serie(metric_key, titulo, ylabel, fmt='bi', fname=None):
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    for tk in ALVOS:
        ys = []
        xs = []
        for ano in ANOS:
            v = DADOS[tk]['ind'].get(ano, {}).get(metric_key)
            if v is not None:
                if fmt == 'bi': v = v/1e9
                elif fmt == 'pct': v = v*100
                ys.append(v); xs.append(ano)
        if xs:
            ax.plot(xs, ys, marker='o', label=tk, color=CORES[tk], linewidth=2)
    ax.set_title(titulo); ax.set_ylabel(ylabel); ax.set_xticks(ANOS)
    ax.grid(True, alpha=0.3); ax.legend(loc='best', fontsize=8, ncol=3)
    if fmt == 'pct': ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    plt.tight_layout()
    path = os.path.join(CHART_DIR, fname or f'{metric_key}.png')
    plt.savefig(path, dpi=150); plt.close()
    return path

chart_receita = chart_serie('receita', 'Receita Líquida — 2021 a 2025', 'R$ bilhões', 'bi', 'receita.png')
chart_ebitda = chart_serie('ebitda', 'EBITDA — 2021 a 2025', 'R$ bilhões', 'bi', 'ebitda.png')
chart_lucro = chart_serie('lucro_liq', 'Lucro Líquido — 2021 a 2025', 'R$ bilhões', 'bi', 'lucro.png')
chart_margebitda = chart_serie('marg_ebitda', 'Margem EBITDA', '%', 'pct', 'marg_ebitda.png')
chart_marg_liq = chart_serie('marg_liq', 'Margem Líquida', '%', 'pct', 'marg_liq.png')
chart_roe = chart_serie('roe', 'ROE', '%', 'pct', 'roe.png')
chart_alav = chart_serie('divliq_ebitda', 'Alavancagem (Dívida Líquida / EBITDA)', 'x', 'bi', 'alav.png')
# alav: keep raw (não dividir por bi)
def chart_alav_raw():
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    for tk in ALVOS:
        xs, ys = [], []
        for ano in ANOS:
            v = DADOS[tk]['ind'].get(ano, {}).get('divliq_ebitda')
            if v is not None: xs.append(ano); ys.append(v)
        if xs: ax.plot(xs, ys, marker='o', label=tk, color=CORES[tk], linewidth=2)
    ax.set_title('Alavancagem (Dívida Líquida / EBITDA)'); ax.set_ylabel('x')
    ax.set_xticks(ANOS); ax.grid(True, alpha=0.3); ax.legend(fontsize=8, ncol=3)
    ax.axhline(3.0, ls='--', color='red', alpha=0.4, label='_alerta')
    plt.tight_layout(); p = os.path.join(CHART_DIR, 'alav.png')
    plt.savefig(p, dpi=150); plt.close(); return p
chart_alav = chart_alav_raw()

chart_dy = chart_serie('dy', 'Dividend Yield (calc. preço médio anual)', '%', 'pct', 'dy.png')

# ---------- Análise qualitativa ----------
ANALISE = {
    'ISAE4': {
        'modelo': """A ISA Energia Brasil (ex-ISA CTEEP) é uma das maiores transmissoras de energia do país, com mais de 18 mil km de linhas e atuação em 18 estados. Sua receita vem essencialmente da <b>RAP — Receita Anual Permitida</b>, definida pela ANEEL, reajustada anualmente pelo IPCA. Modelo de negócio extremamente previsível: presta o serviço de disponibilizar a linha, recebe a RAP independentemente do volume de energia transmitido.""",
        'pontos_fortes': [
            "Receita previsível e indexada à inflação (RAP corrigida pelo IPCA)",
            "Margens EBITDA estruturalmente altas (geralmente >80% pelo padrão regulatório)",
            "Baixo risco operacional — não depende de despacho, demanda ou hidrologia",
            "Histórico consistente de dividendos; ação típica de renda",
            "Reforços e melhorias geram nova RAP sem grande risco de execução",
        ],
        'pontos_fracos': [
            "Crescimento limitado pelo ritmo de leilões da ANEEL e capacidade de capex",
            "Exposição a revisões tarifárias periódicas (RTP) que podem reduzir RAP de contratos antigos",
            "Receita de contratos antigos (RBSE) sujeita a discussões judiciais/regulatórias",
            "Pouca alavancagem operacional: difícil surpreender positivamente o mercado",
        ],
    },
    'CMIG4': {
        'modelo': """A Cemig é uma utility integrada, controlada pelo governo de Minas Gerais. Atua em <b>geração</b> (hidrelétricas, solar, eólica), <b>transmissão</b> e <b>distribuição</b> (Cemig D atende grande parte de MG). Modelo misto: parte regulada (transmissão e distribuição) e parte exposta ao mercado livre/PLD (geração). Histórico de gestão estatal com episódios de interferência política, mas com plano recente de desinvestimento em ativos não-core e foco em eficiência.""",
        'pontos_fortes': [
            "Diversificação ao longo da cadeia (gera, transmite, distribui) reduz risco isolado",
            "Distribuidora em MG com grande base de clientes — receita estável",
            "Programa de desinvestimentos liberou caixa e reduziu dívida nos últimos anos",
            "Dividendos relevantes e payout elevado nos últimos exercícios",
            "Múltiplos historicamente descontados versus pares privados",
        ],
        'pontos_fracos': [
            "Controle estatal: risco político e de interferência tarifária/governança",
            "Distribuição exposta a inadimplência, perdas técnicas e revisões da ANEEL",
            "Geração hidrelétrica sujeita ao GSF e ao risco hidrológico",
            "Capex elevado e contínuo (rede de distribuição envelhece e exige reforço)",
            "Histórico de discussões trabalhistas e fundo de pensão (Forluz)",
        ],
    },
    'TAEE4': {
        'modelo': """A Taesa é uma transmissora pura, com portfólio amplo de concessões. Modelo idêntico ao da ISA Energia em essência: receita = RAP, corrigida pelo IPCA/IGP-M conforme o contrato. Diferencial vs. ISAE4: portfólio mais antigo, com vários contratos no <b>Lote 1</b> chegando ao fim do ciclo de RAP integral (queda de 50% prevista a partir de meados da década), o que pressiona resultados futuros caso não haja reposição via leilões.""",
        'pontos_fortes': [
            "Operação enxuta, margens EBITDA históricas próximas de 85%",
            "Pagador histórico de dividendos — DY frequentemente entre os mais altos do setor",
            "Receita atrelada a inflação, baixa volatilidade operacional",
            "Boa execução em integrações de novos lotes adquiridos via leilão",
        ],
        'pontos_fracos': [
            "<b>Risco de redução de RAP</b>: contratos do ciclo 1 perdem 50% da receita a partir do 16º ano",
            "Crescimento exige vencer leilões cada vez mais competitivos (TIRs apertadas)",
            "Alavancagem mais alta do que ISAE4 — sensível ao custo da dívida",
            "Dependência de captação para sustentar capex de novos projetos",
        ],
    },
    'CPLE3': {
        'modelo': """A Copel atua em geração, transmissão e distribuição, com forte presença no Paraná. Foi <b>privatizada em 2023</b>, deixando de ser controlada pelo governo do PR — virou corporation, sem controlador definido. Esse marco abriu espaço para reestruturação, corte de custos, plano de desinvestimentos (ex.: venda da UEG Araucária) e mudança de governança. Tese é de re-rating pós-privatização.""",
        'pontos_fortes': [
            "<b>Privatização em 2023</b>: nova governança, foco em eficiência e geração de valor",
            "Geração predominantemente renovável (hidro, eólica) com matriz competitiva",
            "Posição relevante na distribuição do PR — receita regulada estável",
            "Espaço para destravar valor via venda de ativos não-core",
            "Histórico recente de aumento de payout e disciplina de capital",
        ],
        'pontos_fracos': [
            "Tese de re-rating pós-privatização já parcialmente precificada",
            "Geração hidro sujeita a risco hidrológico e GSF",
            "Necessidade contínua de capex em distribuição",
            "Transição cultural pós-estatal: execução do plano ainda em curso",
            "Liquidez se divide entre CPLE3, CPLE6 e CPLE11 (units)",
        ],
    },
    'SAPR4': {
        'modelo': """A Sanepar é a companhia de saneamento básico do Paraná, controlada pelo governo estadual. Modelo regulado: tarifas definidas pela AGEPAR, com revisões periódicas. Setor de saneamento ganhou impulso com o <b>Novo Marco do Saneamento (2020)</b>, que estabelece metas de universalização até 2033 — exige capex pesado mas também abre oportunidade de crescimento.""",
        'pontos_fortes': [
            "Setor com demanda inelástica e essencial — receita estável",
            "Universalização do saneamento (Marco 2020) → oportunidade estrutural de crescimento",
            "Pagadora consistente de dividendos; tradicional ação de renda",
            "Múltiplos historicamente baixos versus pares privados (Sabesp pós-privatização)",
            "Tarifa indexada à inflação garante manutenção de margens",
        ],
        'pontos_fracos': [
            "<b>Controle estatal (PR)</b>: risco político e atritos em revisões tarifárias (já houve reajustes negados/postergados)",
            "Capex elevado e crescente para cumprir metas do Marco do Saneamento",
            "Endividamento tende a aumentar para financiar investimentos",
            "Sem perspectiva clara de privatização no curto prazo",
            "Risco regulatório local (AGEPAR) com histórico volátil",
        ],
    },
    'SBSP3': {
        'modelo': """A Sabesp é a maior empresa de saneamento da América Latina, atendendo São Paulo. Foi <b>privatizada em julho de 2024</b> — Equatorial entrou como acionista de referência. O plano de novo controlador prevê forte aceleração de capex (~R$ 70 bi até 2029) para atingir universalização até 2029 (5 anos antes do Marco), com captura de eficiência e re-rating de múltiplos.""",
        'pontos_fortes': [
            "<b>Privatização em 2024</b>: nova governança (Equatorial) com track record sólido",
            "Maior saneamento da América Latina — escala difícil de replicar",
            "Plano agressivo de universalização (2029) gera narrativa de crescimento + ESG",
            "Margens estruturalmente altas (EBITDA >50%) — setor com altíssima alavancagem operacional",
            "Re-rating de múltiplos já em curso; espaço adicional se eficiências entregarem",
        ],
        'pontos_fracos': [
            "Tese de privatização parcialmente precificada — múltiplos já se aproximaram de pares",
            "<b>Plano de capex agressivo</b> vai elevar dívida e pressionar FCF nos próximos anos",
            "Execução do plano de eficiência ainda em fase inicial — risco de frustração",
            "Histórico curto sob nova gestão; aprendizado regulatório com a Arsesp em andamento",
            "Possíveis ruídos políticos em ano eleitoral (tarifas e contratos)",
        ],
    },
}

CONCLUSAO = """
<b>Síntese balanceada — Renda + Crescimento</b><br/><br/>

<b>Perfil de renda pura (previsibilidade alta, crescimento baixo):</b><br/>
• <b>ISAE4</b> — melhor combinação risco/retorno no segmento transmissão. Portfólio maduro, balanço sólido, RAP indexada à inflação. Para um investidor focado em fluxo recorrente é a posição estrutural natural.<br/>
• <b>TAEE4</b> — DY historicamente alto, mas atenção ao "fiscal cliff" de redução de RAP em contratos do ciclo 1 ao longo desta década. Funciona como complemento, não como núcleo.<br/><br/>

<b>Perfil misto (renda razoável + potencial de re-rating):</b><br/>
• <b>CMIG4</b> — boa pagadora atualmente e múltiplos descontados, mas o desconto existe por motivo real (controle estatal). Adequada para quem aceita esse risco em troca do yield.<br/>
• <b>CPLE3</b> — caso de re-rating pós-privatização (2023), com upside de execução; renda média e crescimento de retorno por captura de eficiência. Hoje é a maneira mais direta de jogar "ex-estatal virando privada".<br/>
• <b>SAPR4</b> — defensiva, paga bem, mas crescimento limitado por capex pesado e risco político local. Boa diversificação dentro do bloco regulado.<br/><br/>

<b>Perfil de crescimento (yield menor, tese de transformação):</b><br/>
• <b>SBSP3</b> — a tese mais "growth" do grupo. Equatorial mostrou em outras concessionárias que entrega; mas o múltiplo já incorpora boa parte do otimismo. Tamanho da posição deve refletir convicção na execução.<br/><br/>

<b>Recomendação balanceada de carteira (ilustrativa):</b> núcleo em ISAE4 + CMIG4 para renda recorrente, satélites em CPLE3 e SBSP3 para crescimento/re-rating, e SAPR4 + TAEE4 como complemento defensivo conforme apetite por dividendos vs. risco regulatório.<br/><br/>

<i>Observação importante: este relatório foi gerado com os dados disponíveis no banco local. Para SAPR4 não havia série financeira no banco; para SBSP3 só há 2024 e 2025 (consistente com a privatização recente); CPLE3 e TAEE4 estão sem 2023. A análise qualitativa não depende desses gaps, mas os comparativos numéricos refletem apenas anos disponíveis. Próximo passo recomendado: buscar série histórica completa via scraping (yfinance/Fundamentus/RI das empresas) para fechar o quadro.</i>
"""

# ---------- PDF ----------
styles = getSampleStyleSheet()
H1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1f4e79'),
                    spaceAfter=12, spaceBefore=6, alignment=TA_LEFT)
H2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#1f4e79'),
                    spaceAfter=8, spaceBefore=14)
H3 = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor('#2e75b6'),
                    spaceAfter=4, spaceBefore=8)
BODY = ParagraphStyle('BODY', parent=styles['BodyText'], fontSize=9.5, leading=13, alignment=TA_JUSTIFY,
                       spaceAfter=6)
BODYC = ParagraphStyle('BODYC', parent=BODY, alignment=TA_CENTER)
SMALL = ParagraphStyle('S', parent=styles['BodyText'], fontSize=8, textColor=colors.grey)
BULLET = ParagraphStyle('B', parent=BODY, leftIndent=14, bulletIndent=2, spaceAfter=2)

doc = SimpleDocTemplate(PDF_OUT, pagesize=A4, leftMargin=1.7*cm, rightMargin=1.7*cm,
                          topMargin=1.7*cm, bottomMargin=1.7*cm,
                          title='Análise Comparativa — Elétricas e Saneamento Brasil')
story = []

# Capa
story.append(Spacer(1, 3*cm))
story.append(Paragraph('Análise Comparativa', H1))
story.append(Paragraph('Elétricas e Saneamento — Brasil', H1))
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph('ISAE4 • CMIG4 • TAEE4 • CPLE3 • SAPR4 • SBSP3', H2))
story.append(Spacer(1, 0.6*cm))
story.append(Paragraph('Comparativo de fundamentos dos últimos 5 anos (2021–2025) e análise '
                       'qualitativa dos modelos de negócio, pontos fortes e pontos fracos.', BODY))
story.append(Spacer(1, 5*cm))
story.append(Paragraph(f'Gerado em {datetime.now():%d/%m/%Y %H:%M}', SMALL))
story.append(Paragraph('Leonardo Giaretta — Análise pessoal', SMALL))
story.append(PageBreak())

# Sumário executivo
story.append(Paragraph('1. Sumário executivo', H1))
story.append(Paragraph(
    "Este relatório compara seis empresas brasileiras dos setores de transmissão de energia "
    "(ISAE4, TAEE4), energia integrada (CMIG4, CPLE3) e saneamento básico (SAPR4, SBSP3). "
    "São empresas predominantemente reguladas, com receitas previsíveis e tradicional foco em dividendos, "
    "mas que apresentam perfis bem distintos em termos de crescimento, risco regulatório e estágio "
    "do ciclo de capital. O objetivo é mapear pontos fortes e fracos de cada modelo de negócio "
    "para apoiar decisão de alocação balanceada entre <b>renda</b> e <b>crescimento</b>.", BODY))
story.append(Paragraph('Visão de uma página', H2))

# Tabela resumo: ticker, setor, preço, DY estimado
tab_data = [['Ticker','Empresa','Setor','Preço atual','DY (últ. 12m)*']]
for tk in ALVOS:
    d = DADOS[tk]
    pa = d['preco_atual']
    dy = d.get('dy_atual')
    tab_data.append([tk, NOMES[tk], SETORES[tk],
                       f'R$ {pa:.2f}' if pa else 'N/D',
                       fmt_pct(dy) if dy else 'N/D'])
t = Table(tab_data, colWidths=[2*cm, 3.5*cm, 6.5*cm, 2.5*cm, 2.7*cm])
t.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#1f4e79')),
    ('TEXTCOLOR',(0,0),(-1,0), colors.white),
    ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
    ('FONTSIZE',(0,0),(-1,-1),9),
    ('ALIGN',(3,1),(-1,-1),'RIGHT'),
    ('ALIGN',(0,0),(-1,0),'CENTER'),
    ('GRID',(0,0),(-1,-1),0.3, colors.grey),
    ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f2f2f2')]),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
]))
story.append(t)
story.append(Paragraph('* DY estimado: dividendos pagos em 2024 ÷ ações ÷ preço atual. Indicativo apenas.', SMALL))
story.append(PageBreak())

# Seção 2: comparativo numérico
story.append(Paragraph('2. Comparativo numérico — 2021 a 2025', H1))
story.append(Paragraph(
    "As tabelas e gráficos abaixo consolidam os principais indicadores extraídos do banco local. "
    "Valores em <b>bi = bilhões de R$</b>, <b>mi = milhões de R$</b>. Onde aparece 'N/D', o dado não "
    "estava disponível no banco no momento da geração.", BODY))

# Tabela receita por ano
def tabela_metrica(metric, titulo, formatter):
    story.append(Paragraph(titulo, H2))
    header = ['Empresa'] + [str(a) for a in ANOS]
    rows = [header]
    for tk in ALVOS:
        row = [tk]
        for ano in ANOS:
            v = DADOS[tk]['ind'].get(ano, {}).get(metric)
            row.append(formatter(v))
        rows.append(row)
    t = Table(rows, colWidths=[2.5*cm] + [2.6*cm]*5)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#1f4e79')),
        ('TEXTCOLOR',(0,0),(-1,0), colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(1,0),(-1,-1),'RIGHT'),
        ('ALIGN',(0,0),(0,-1),'LEFT'),
        ('GRID',(0,0),(-1,-1),0.3, colors.grey),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f2f2f2')]),
    ]))
    story.append(t); story.append(Spacer(1, 0.3*cm))

tabela_metrica('receita', 'Receita Líquida', fmt_milhoes)
story.append(Image(chart_receita, width=16*cm, height=6.5*cm))
story.append(PageBreak())

tabela_metrica('ebitda', 'EBITDA', fmt_milhoes)
story.append(Image(chart_ebitda, width=16*cm, height=6.5*cm))
tabela_metrica('marg_ebitda', 'Margem EBITDA', fmt_pct)
story.append(Image(chart_margebitda, width=16*cm, height=6.5*cm))
story.append(PageBreak())

tabela_metrica('lucro_liq', 'Lucro Líquido', fmt_milhoes)
story.append(Image(chart_lucro, width=16*cm, height=6.5*cm))
tabela_metrica('marg_liq', 'Margem Líquida', fmt_pct)
story.append(Image(chart_marg_liq, width=16*cm, height=6.5*cm))
story.append(PageBreak())

tabela_metrica('roe', 'ROE (Lucro Líquido / Patrimônio Líquido)', fmt_pct)
story.append(Image(chart_roe, width=16*cm, height=6.5*cm))
tabela_metrica('roic', 'ROIC simplificado (NOPAT / Cap. Investido)', fmt_pct)
story.append(PageBreak())

tabela_metrica('div_liq', 'Dívida Líquida', fmt_milhoes)
tabela_metrica('divliq_ebitda', 'Alavancagem (Dív. Líq. / EBITDA) — alerta acima de 3x', fmt_x)
story.append(Image(chart_alav, width=16*cm, height=6.5*cm))
story.append(PageBreak())

tabela_metrica('dpa', 'Dividendos por ação (R$)', lambda v: fmt_num(v,3))
tabela_metrica('dy', 'Dividend Yield (sobre preço médio do ano)', fmt_pct)
story.append(Image(chart_dy, width=16*cm, height=6.5*cm))
tabela_metrica('payout', 'Payout (Dividendos / Lucro Líq.)', fmt_pct)
story.append(PageBreak())

# Seção 3: análise por empresa
story.append(Paragraph('3. Análise por empresa', H1))
for tk in ALVOS:
    d = DADOS[tk]; a = ANALISE[tk]
    story.append(Paragraph(f'{tk} — {NOMES[tk]}', H2))
    story.append(Paragraph(f'<i>Setor:</i> {SETORES[tk]}', BODY))
    story.append(Paragraph('Modelo de negócio', H3))
    story.append(Paragraph(a['modelo'], BODY))
    story.append(Paragraph('Pontos fortes', H3))
    for p in a['pontos_fortes']:
        story.append(Paragraph(f'• {p}', BULLET))
    story.append(Paragraph('Pontos fracos / riscos', H3))
    for p in a['pontos_fracos']:
        story.append(Paragraph(f'• {p}', BULLET))

    # mini-tabela dos últimos dados disponíveis
    story.append(Paragraph('Indicadores recentes', H3))
    anos_disp = sorted([a for a in d['ind'].keys()])
    if anos_disp:
        ult = anos_disp[-1]
        ind = d['ind'][ult]
        mini = [['Métrica', f'{ult}'],
                ['Receita Líq.', fmt_milhoes(ind.get('receita'))],
                ['EBITDA', fmt_milhoes(ind.get('ebitda'))],
                ['Margem EBITDA', fmt_pct(ind.get('marg_ebitda'))],
                ['Lucro Líquido', fmt_milhoes(ind.get('lucro_liq'))],
                ['Margem Líquida', fmt_pct(ind.get('marg_liq'))],
                ['ROE', fmt_pct(ind.get('roe'))],
                ['Dívida Líquida', fmt_milhoes(ind.get('div_liq'))],
                ['Dív.Líq/EBITDA', fmt_x(ind.get('divliq_ebitda'))],
                ['DPA', fmt_num(ind.get('dpa'),3)],
                ['DY (preço médio)', fmt_pct(ind.get('dy'))],
                ['Payout', fmt_pct(ind.get('payout'))],
                ]
        t = Table(mini, colWidths=[5*cm, 4*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#2e75b6')),
            ('TEXTCOLOR',(0,0),(-1,0), colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9),
            ('ALIGN',(1,0),(-1,-1),'RIGHT'),
            ('GRID',(0,0),(-1,-1),0.3, colors.grey),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f7f9fc')]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph('<i>Sem dados financeiros no banco local para este ticker. '
                                'A análise qualitativa acima permanece válida.</i>', BODY))
    story.append(PageBreak())

# Seção 4: ranking e conclusão
story.append(Paragraph('4. Síntese e ranking por perfil', H1))
story.append(Paragraph(CONCLUSAO, BODY))

# Build
doc.build(story)
print(f'\nPDF gerado: {PDF_OUT}')
print(f'Tamanho: {os.path.getsize(PDF_OUT)/1024:.1f} KB')
