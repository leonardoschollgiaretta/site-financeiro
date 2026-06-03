/**
 * E-mail diário consolidado (TESTE — só para Leonardo)
 *
 * Junta num único e-mail:
 *   1) Fechamento de Ações BR
 *   2) Fechamento de Ações US
 *   3) Fluxo de Investidores B3 (scraping dadosdemercado.com.br)
 *
 * Como usar:
 *  - Cole no editor do Apps Script (substituindo tudo).
 *  - Salve (Ctrl+S).
 *  - Para testar agora: selecione `enviarEmailConsolidado` e clique Executar.
 *  - Para automatizar: selecione `setupTrigger` e clique Executar (uma vez).
 */

// ============================ CONFIG ============================
const PLANILHA_ID = '1V-q3--vBT-yjLQLauWj1-19LgJJOFYv2XY7-ocobUOM';
const DESTINATARIO = 'leonardo@anelempreendimentos.com.br';

// Fluxo B3
const URL_FLUXO = 'https://www.dadosdemercado.com.br/fluxo';
const ABA_BANCO_FLUXO = 'fluxo_diario';

// Gatilho
const HORA_TRIGGER = 19;
// ================================================================


// ============================================================
//                    ENTRY POINT
// ============================================================

/** Função principal — gera um e-mail único com tudo dentro. */
function enviarEmailConsolidado() {
  const fusoBrasil = 'America/Sao_Paulo';
  const planilha = SpreadsheetApp.openById(PLANILHA_ID);
  const ontem = new Date();
  ontem.setDate(ontem.getDate() - 1);
  const dataStr = Utilities.formatDate(ontem, fusoBrasil, 'dd/MM/yyyy');

  let corpo = `<h1>📊 Fechamento Diário - ${dataStr}</h1>`;

  // ---- AÇÕES BR ----
  const abaBR = planilha.getSheetByName('envio diario');
  if (abaBR) {
    corpo += `<h2 style="margin-top:30px">🇧🇷 Mercado Brasileiro</h2>`;
    corpo += `<h3 style="color:#1d3557;margin-bottom:8px">Índice de Referência</h3>`;
    corpo += montarLinhaIndice(abaBR, 3, 3, '#1d3557');
    corpo += `<h3 style="color:#2d6a4f;margin-top:25px;margin-bottom:8px">Ações Acompanhadas</h3>`;
    corpo += montarTabelaAcoes(abaBR, 'C5:S50', '#2d6a4f', 'R$', 'Mkt cap (Bi R$)');
  } else {
    corpo += `<p>⚠️ Aba 'envio diario' não encontrada</p>`;
  }

  // ---- AÇÕES US ----
  const abaUS = planilha.getSheetByName('e diario 2');
  if (abaUS) {
    corpo += `<h2 style="margin-top:40px">🇺🇸 Mercado Americano</h2>`;
    corpo += `<h3 style="color:#1d3557;margin-bottom:8px">Índice de Referência</h3>`;
    corpo += montarLinhaIndice(abaUS, 3, 3, '#1d3557');
    corpo += `<h3 style="color:#1d3557;margin-top:25px;margin-bottom:8px">Ações Acompanhadas</h3>`;
    corpo += montarTabelaAcoes(abaUS, 'C5:S50', '#1d3557', 'US$', 'Mkt cap (Bi US$)');
  } else {
    corpo += `<p>⚠️ Aba 'e diario 2' não encontrada</p>`;
  }

  // ---- FLUXO B3 ----
  try {
    const linhas = baixarFluxos();
    upsertFluxoNaPlanilha(linhas);
    corpo += `<h2 style="margin-top:40px">📈 Fluxo de Investidores B3</h2>`;
    corpo += `<h3 style="color:#1d3557;margin-bottom:8px">Investidores na B3</h3>`;
    corpo += gerarResumoFluxoHtml();
  } catch (e) {
    corpo += `<h2 style="margin-top:40px">📈 Fluxo de Investidores B3</h2>`;
    corpo += `<p style="color:#c00">Erro ao coletar fluxo B3: ${e}</p>`;
  }

  MailApp.sendEmail({
    to: DESTINATARIO,
    subject: `📊 Fechamento + Fluxo B3 - ${dataStr}`,
    htmlBody: corpo,
  });
}


/** Cria/recria o gatilho diário. Rode UMA vez. */
function setupTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'enviarEmailConsolidado')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('enviarEmailConsolidado')
    .timeBased()
    .everyDays(1)
    .atHour(HORA_TRIGGER)
    .create();
  Logger.log(`Trigger diário criado às ${HORA_TRIGGER}h`);
}


// ============================================================
//                  BLOCOS DE AÇÕES (BR + US)
// ============================================================

function montarLinhaIndice(aba, linhaIndice, colInicio, corHeader) {
  const range = aba.getRange(linhaIndice, colInicio, 1, 17).getValues()[0];

  const ticker     = range[0];
  const nome       = range[1];
  const priceToday = range[2];
  const price1mAgo = range[7];
  const priceYTD   = range[8];
  const price12m   = range[9];
  const price24m   = range[10];
  const price60m   = range[11];
  const deltaMes   = range[12];
  const deltaYTD   = range[13];
  const delta12    = range[14];
  const delta24    = range[15];
  const delta60    = range[16];

  const fmt = v => typeof v === 'number' ? v.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : v;
  const pct = v => typeof v === 'number' ? (v * 100).toFixed(1) + '%' : v;
  const cor = v => typeof v === 'number' && v < 0 ? 'color:#c00' : 'color:#080';

  let html = `<table border="1" cellpadding="8" style="border-collapse:collapse;font-family:Arial;font-size:13px;margin-bottom:40px">`;
  html += `<tr style="background:${corHeader};color:white">
              <th>Índice</th><th>Nome</th>
              <th>Pontos Hoje</th>
              <th>1m atrás</th><th>Início Ano</th><th>12m atrás</th><th>24m atrás</th><th>60m atrás</th>
              <th>Δ mês</th><th>Δ YTD</th><th>Δ 12m</th><th>Δ 24m</th><th>Δ 60m</th>
            </tr>`;
  html += `<tr>
    <td><b>${ticker}</b></td>
    <td>${nome}</td>
    <td><b>${fmt(priceToday)}</b></td>
    <td>${fmt(price1mAgo)}</td>
    <td>${fmt(priceYTD)}</td>
    <td>${fmt(price12m)}</td>
    <td>${fmt(price24m)}</td>
    <td>${fmt(price60m)}</td>
    <td style="${cor(deltaMes)}">${pct(deltaMes)}</td>
    <td style="${cor(deltaYTD)}">${pct(deltaYTD)}</td>
    <td style="${cor(delta12)}">${pct(delta12)}</td>
    <td style="${cor(delta24)}">${pct(delta24)}</td>
    <td style="${cor(delta60)}">${pct(delta60)}</td>
  </tr></table>`;
  return html;
}

function montarTabelaAcoes(aba, range, corHeader, moeda, labelMktCap) {
  const dados = aba.getRange(range).getValues();

  let html = `<table border="1" cellpadding="8" style="border-collapse:collapse;font-family:Arial;font-size:13px;margin-bottom:30px">`;
  html += `<tr style="background:${corHeader};color:white">
              <th>Ticker</th><th>Companie</th>
              <th>Price Today</th><th>P/E</th><th>${labelMktCap}</th>
              <th>max 12m</th><th>min 12m</th>
              <th>Price 1m ago</th><th>Início Ano</th><th>12m atrás</th><th>24m atrás</th><th>60m atrás</th>
              <th>Δ mês</th><th>Δ YTD</th><th>Δ 12m</th><th>Δ 24m</th><th>Δ 60m</th>
            </tr>`;

  dados.forEach(linha => {
    const ticker = linha[0];
    if (!ticker) return;

    const empresa    = linha[1];
    const priceToday = linha[2];
    const pl         = linha[3];
    const mktCap     = linha[4];
    const max12      = linha[5];
    const min12      = linha[6];
    const price1mAgo = linha[7];
    const priceYTD   = linha[8];
    const price12m   = linha[9];
    const price24m   = linha[10];
    const price60m   = linha[11];
    const deltaMes   = linha[12];
    const deltaYTD   = linha[13];
    const delta12    = linha[14];
    const delta24    = linha[15];
    const delta60    = linha[16];

    const fmt = v => typeof v === 'number' ? v.toFixed(2) : v;
    const pct = v => typeof v === 'number' ? (v * 100).toFixed(1) + '%' : v;
    const cor = v => typeof v === 'number' && v < 0 ? 'color:#c00' : 'color:#080';

    html += `<tr>
      <td><b>${ticker}</b></td>
      <td>${empresa}</td>
      <td>${moeda} ${fmt(priceToday)}</td>
      <td>${fmt(pl)}</td>
      <td>${moeda} ${fmt(mktCap)}</td>
      <td>${fmt(max12)}</td>
      <td>${fmt(min12)}</td>
      <td>${moeda} ${fmt(price1mAgo)}</td>
      <td>${fmt(priceYTD)}</td>
      <td>${fmt(price12m)}</td>
      <td>${fmt(price24m)}</td>
      <td>${fmt(price60m)}</td>
      <td style="${cor(deltaMes)}">${pct(deltaMes)}</td>
      <td style="${cor(deltaYTD)}">${pct(deltaYTD)}</td>
      <td style="${cor(delta12)}">${pct(delta12)}</td>
      <td style="${cor(delta24)}">${pct(delta24)}</td>
      <td style="${cor(delta60)}">${pct(delta60)}</td>
    </tr>`;
  });
  html += '</table>';
  return html;
}


// ============================================================
//                  BLOCO DO FLUXO B3
// ============================================================

const CATEGORIAS_FLUXO = ['estrangeiro', 'institucional', 'pessoa_fisica', 'inst_financeira', 'outros'];
const ROTULOS_FLUXO = {
  estrangeiro:     'Estrangeiro',
  institucional:   'Institucional',
  pessoa_fisica:   'Pessoa Física',
  inst_financeira: 'Inst. Financeira',
  outros:          'Outros',
};
const CABECALHO_FLUXO = ['data', ...CATEGORIAS_FLUXO, 'atualizado_em'];

// ----- Scraper -----

function baixarFluxos() {
  const html = UrlFetchApp.fetch(URL_FLUXO, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; fluxo-b3-apps-script/1.0)' },
    muteHttpExceptions: false,
  }).getContentText('UTF-8');

  const tbody = html.match(/<tbody[^>]*>([\s\S]*?)<\/tbody>/i);
  if (!tbody) throw new Error('tbody da tabela de fluxos não encontrado');

  const linhas = [];
  const reTr = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  let m;
  while ((m = reTr.exec(tbody[1])) !== null) {
    const celulas = [...m[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)]
      .map(c => stripHtml(c[1]));
    if (celulas.length < 6) continue;
    linhas.push({
      data:            parseDataBr(celulas[0]),
      estrangeiro:     parseValorMi(celulas[1]),
      institucional:   parseValorMi(celulas[2]),
      pessoa_fisica:   parseValorMi(celulas[3]),
      inst_financeira: parseValorMi(celulas[4]),
      outros:          parseValorMi(celulas[5]),
    });
  }
  if (linhas.length === 0) throw new Error('Nenhuma linha de fluxo parseada');
  return linhas;
}

function stripHtml(s) {
  return s.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim();
}

function parseDataBr(s) {
  const [d, m, y] = s.trim().split('/');
  return `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
}

function parseValorMi(s) {
  const t = s.toLowerCase().replace('mi', '').trim();
  if (!t || t === '-' || t === '—') return null;
  const num = parseFloat(t.replace(/\./g, '').replace(',', '.'));
  return isNaN(num) ? null : num;
}

// ----- Banco (aba fluxo_diario) -----

function getAbaFluxo() {
  const ss = SpreadsheetApp.openById(PLANILHA_ID);
  let aba = ss.getSheetByName(ABA_BANCO_FLUXO);
  if (!aba) {
    aba = ss.insertSheet(ABA_BANCO_FLUXO);
    aba.getRange(1, 1, 1, CABECALHO_FLUXO.length).setValues([CABECALHO_FLUXO]).setFontWeight('bold');
    aba.setFrozenRows(1);
  }
  return aba;
}

function dataParaIso(v) {
  if (v instanceof Date) {
    const y = v.getFullYear();
    const m = String(v.getMonth() + 1).padStart(2, '0');
    const d = String(v.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  return String(v);
}

function upsertFluxoNaPlanilha(linhas) {
  const aba = getAbaFluxo();
  aba.getRange('A:A').setNumberFormat('@');

  const dadosExistentes = aba.getLastRow() > 1
    ? aba.getRange(2, 1, aba.getLastRow() - 1, CABECALHO_FLUXO.length).getValues()
    : [];

  const idxPorData = new Map();
  dadosExistentes.forEach((row, i) => idxPorData.set(dataParaIso(row[0]), i + 2));

  const agora = new Date();
  const novas = [];
  let atualizados = 0;

  linhas.forEach(ln => {
    const row = [
      ln.data, ln.estrangeiro, ln.institucional, ln.pessoa_fisica,
      ln.inst_financeira, ln.outros, agora,
    ];
    if (idxPorData.has(ln.data)) {
      aba.getRange(idxPorData.get(ln.data), 1, 1, CABECALHO_FLUXO.length).setValues([row]);
      atualizados++;
    } else {
      novas.push(row);
    }
  });

  if (novas.length > 0) {
    aba.getRange(aba.getLastRow() + 1, 1, novas.length, CABECALHO_FLUXO.length).setValues(novas);
    aba.getRange(2, 1, aba.getLastRow() - 1, CABECALHO_FLUXO.length).sort({ column: 1, ascending: false });
  }
  return { inseridos: novas.length, atualizados };
}

function carregarFluxos() {
  const aba = getAbaFluxo();
  if (aba.getLastRow() < 2) return [];
  const dados = aba.getRange(2, 1, aba.getLastRow() - 1, CABECALHO_FLUXO.length).getValues();
  return dados.map(r => ({
    data: dataParaIso(r[0]),
    estrangeiro:     r[1] === '' ? null : Number(r[1]),
    institucional:   r[2] === '' ? null : Number(r[2]),
    pessoa_fisica:   r[3] === '' ? null : Number(r[3]),
    inst_financeira: r[4] === '' ? null : Number(r[4]),
    outros:          r[5] === '' ? null : Number(r[5]),
  })).sort((a, b) => b.data.localeCompare(a.data));
}

// ----- Resumo HTML do fluxo -----

function fmtFluxo(v) {
  if (v === null || v === undefined) return '—';
  const sinal = v < 0 ? '-' : '';
  const s = Math.abs(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return sinal + s;
}

function somaFluxo(linhas, cat) {
  return linhas.reduce((acc, ln) => acc + (ln[cat] || 0), 0);
}

function gerarResumoFluxoHtml() {
  const linhas = carregarFluxos();
  if (linhas.length === 0) return '<p>Banco vazio.</p>';

  const hoje = linhas[0];
  const [yyyy, mm, dd] = hoje.data.split('-');
  const dataHojeBr = `${dd}/${mm}/${yyyy}`;
  const mesesPt = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  const mesExtenso = `${mesesPt[parseInt(mm, 10) - 1]}/${yyyy}`;

  const ult10 = linhas.slice(0, 10);
  const doMes = linhas.filter(ln => ln.data.startsWith(`${yyyy}-${mm}`));
  const doAno = linhas.filter(ln => ln.data.startsWith(`${yyyy}-`));

  const corHeader = '#1d3557';
  const cor = v => typeof v === 'number' && v < 0 ? 'color:#c00' : 'color:#080';

  const linhaTotais = (vals, primeiraCelula = null) => {
    let h = '<tr>';
    if (primeiraCelula !== null) h += `<td>${primeiraCelula}</td>`;
    CATEGORIAS_FLUXO.forEach(c => {
      const v = vals[c];
      h += `<td style="${cor(v)}">${fmtFluxo(v)}</td>`;
    });
    h += '</tr>';
    return h;
  };

  let out = `<p style="font-family:Arial;font-size:12px;color:#555;margin:0 0 8px 0">`;
  out += `Pregão de <b>${dataHojeBr}</b> · Valores em R$ milhões · Fonte: `;
  out += `<a href="https://www.dadosdemercado.com.br/fluxo" style="color:#1d3557">dadosdemercado.com.br</a></p>`;

  const baseTable = `border="1" cellpadding="8" style="border-collapse:collapse;font-family:Arial;font-size:13px;margin-bottom:25px"`;
  const headRow = (incluirData = false) => {
    let h = `<tr style="background:${corHeader};color:white">`;
    if (incluirData) h += `<th>Data</th>`;
    CATEGORIAS_FLUXO.forEach(c => h += `<th>${ROTULOS_FLUXO[c]}</th>`);
    h += `</tr>`;
    return h;
  };

  // DIA
  out += `<h4 style="color:${corHeader};margin:18px 0 6px 0">Dia</h4>`;
  out += `<table ${baseTable}>${headRow(false)}${linhaTotais(hoje)}</table>`;

  // ÚLTIMOS 10
  out += `<h4 style="color:${corHeader};margin:18px 0 6px 0">Últimos 10 pregões</h4>`;
  out += `<table ${baseTable}>${headRow(true)}`;
  ult10.forEach(ln => {
    const [y, m, d] = ln.data.split('-');
    out += linhaTotais(ln, `${d}/${m}/${y}`);
  });
  out += `</table>`;

  // MÊS
  const totaisMes = {}; CATEGORIAS_FLUXO.forEach(c => totaisMes[c] = somaFluxo(doMes, c));
  out += `<h4 style="color:${corHeader};margin:18px 0 6px 0">Acumulado do mês · ${mesExtenso} · ${doMes.length} pregões</h4>`;
  out += `<table ${baseTable}>${headRow(false)}${linhaTotais(totaisMes)}</table>`;

  // ANO
  const totaisAno = {}; CATEGORIAS_FLUXO.forEach(c => totaisAno[c] = somaFluxo(doAno, c));
  out += `<h4 style="color:${corHeader};margin:18px 0 6px 0">Acumulado do ano · ${yyyy} · ${doAno.length} pregões</h4>`;
  out += `<table ${baseTable}>${headRow(false)}${linhaTotais(totaisAno)}</table>`;

  return out;
}
