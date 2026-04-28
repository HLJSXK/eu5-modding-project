'use strict';

// ---------------------------------------------------------------------------
// Data store (populated by loadData)
// ---------------------------------------------------------------------------
const D = { meta: null, alphaBracket: null, alphaGenerator: null, engelCurves: null, savingsParams: null, goodsWeights: null };
const BASE = './data/';

async function loadData() {
  const files = ['meta', 'alpha_bracket', 'alpha_generator', 'engel_curves', 'savings_params', 'goods_weights'];
  const keys  = ['meta', 'alphaBracket', 'alphaGenerator', 'engelCurves', 'savingsParams', 'goodsWeights'];
  const results = await Promise.all(files.map(f => fetch(`${BASE}${f}.json`).then(r => r.json())));
  keys.forEach((k, i) => { D[k] = results[i]; });
}

// ---------------------------------------------------------------------------
// Tab routing
// ---------------------------------------------------------------------------
function setupTabs() {
  const btns   = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
      if (btn.dataset.tab === 'tab3') renderSavings();
    });
  });
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------
const PLOTLY_LAYOUT = (xTitle, yTitle) => ({
  paper_bgcolor: '#0e1117',
  plot_bgcolor:  '#131720',
  font: { color: '#ccc', size: 12 },
  xaxis: { title: xTitle, gridcolor: '#2a2d35', zerolinecolor: '#444' },
  yaxis: { title: yTitle, gridcolor: '#2a2d35', zerolinecolor: '#444' },
  margin: { t: 30, b: 50, l: 60, r: 20 },
  legend: { bgcolor: 'rgba(0,0,0,0)', font: { size: 11 } },
  hovermode: 'x unified',
});

function populateSelect(id, options, labelFn) {
  const el = document.getElementById(id);
  el.innerHTML = '';
  options.forEach(opt => {
    const o = document.createElement('option');
    o.value = opt;
    o.textContent = labelFn ? labelFn(opt) : opt;
    el.appendChild(o);
  });
}

// ---------------------------------------------------------------------------
// Tab 0 — Substitute Group Manager (goods weights table)
// ---------------------------------------------------------------------------
function renderTab0() {
  const tbody = document.querySelector('#tab0 tbody');
  if (!tbody) return;
  const rows = [];
  D.meta.groups.forEach(({ name, luxury_rank }) => {
    const goods  = D.meta.group_goods[name] || [];
    const wmap   = D.goodsWeights[name] || {};
    goods.forEach(good => {
      rows.push(`<tr>
        <td>${name}</td>
        <td>${luxury_rank}</td>
        <td>${good}</td>
        <td>${(wmap[good] * 100).toFixed(1)}%</td>
      </tr>`);
    });
  });
  tbody.innerHTML = rows.join('');
}

// ---------------------------------------------------------------------------
// Tab 1 — Alpha Generator (power-law preview per strata)
// ---------------------------------------------------------------------------
function renderTab1() {
  const strata = document.getElementById('ag-strata').value;
  const stData = D.alphaGenerator.preview_curves[strata];
  if (!stData) return;

  const settings = D.alphaGenerator.settings[strata];
  document.getElementById('ag-info').textContent =
    `low_rank_exp = ${settings.low_rank_exp}  |  high_rank_exp = ${settings.high_rank_exp}`;

  const thresholds = stData[D.meta.groups[0].name]?.thresholds || [];
  const nBrackets = thresholds.length;
  const xLabels = thresholds.map((t, i) =>
    i < nBrackets - 1 ? `[${t.toFixed(2)}–${thresholds[i + 1].toFixed(2)})` : `≥${t.toFixed(2)}`
  );

  const traces = D.meta.groups.map(({ name, color }) => {
    const cd = stData[name];
    return {
      name,
      type:  'bar',
      x:     xLabels,
      y:     cd ? cd.brackets : [],
      marker: { color },
    };
  });

  Plotly.react('chart-tab1', traces, {
    ...PLOTLY_LAYOUT('Income bracket', 'Budget share α'),
    barmode: 'stack',
    yaxis: { ...PLOTLY_LAYOUT().yaxis, range: [0, 1] },
    title: { text: `Power-law alpha preview — ${strata}`, font: { color: '#ccc', size: 13 } },
  }, { responsive: true });
}

// ---------------------------------------------------------------------------
// Tab 2 — Alpha Adjustment (piecewise Engel viewer)
// ---------------------------------------------------------------------------
function renderTab2Group() {
  const strata = document.getElementById('ea-strata').value;
  const group  = document.getElementById('ea-group').value;

  const stData = D.alphaBracket;
  const thresholds = stData.thresholds[strata] || [];
  const alphas     = stData.alphas[strata]     || {};
  const offsets    = stData.offsets[strata]    || {};
  const P          = stData.base_prices[strata]?.[group] || 1.0;

  // Build piecewise curve
  const nBrackets = thresholds.length;
  const xMax  = (thresholds[nBrackets - 1] || 1.0) * 2.0;
  const nPts  = 200;
  const xs = [], ys = [];

  for (let i = 0; i <= nPts; i++) {
    const y = (xMax * i) / nPts;
    let k = 0;
    for (let j = 0; j < nBrackets; j++) {
      if (thresholds[j] <= y) k = j;
    }
    const alpha = (alphas[k] || {})[group] || 0.0;
    const c     = (offsets[String(k)] || {})[group] || 0.0;
    xs.push(y);
    ys.push(P > 0 ? (alpha / P) * y + c : 0.0);
  }

  // Threshold markers
  const threshMarks = thresholds.slice(1).map(t => ({
    type: 'line', x0: t, x1: t, y0: 0, y1: 1, yref: 'paper',
    line: { color: '#555', width: 1, dash: 'dot' },
  }));

  Plotly.react('chart-tab2', [
    { x: xs, y: ys, mode: 'lines', name: group, line: { color: '#ff6b6b', width: 2 } },
  ], {
    ...PLOTLY_LAYOUT('Income y', `Demand d(y) — ${group} / ${strata}`),
    shapes: threshMarks,
  }, { responsive: true });

  // Bracket table
  const rows = thresholds.map((t, k) => {
    const alpha = ((alphas[k] || {})[group] || 0.0).toFixed(5);
    const off   = ((offsets[String(k)] || {})[group] || 0.0).toFixed(5);
    return `<tr><td>${k}</td><td>${t.toFixed(4)}</td><td>${alpha}</td><td>${off}</td></tr>`;
  });
  document.getElementById('bracket-table-body').innerHTML = rows.join('');
}

function renderTab2All() {
  const strata = document.getElementById('ea-strata').value;

  const curves = D.engelCurves.per_group[strata];
  if (!curves) return;
  const xs = curves.x;

  const traces = D.meta.groups.map(({ name, color }) => ({
    name,
    mode: 'lines',
    x: xs,
    y: curves.curves[name] || [],
    line: { color, width: 1.5 },
  }));

  Plotly.react('chart-tab2-all', traces, {
    ...PLOTLY_LAYOUT('Income y', 'Group demand d(y)'),
    title: { text: `All groups — ${strata}`, font: { color: '#ccc', size: 13 } },
  }, { responsive: true });
}

// ---------------------------------------------------------------------------
// Tab 3 — Savings Dynamics (JS recomputation)
// ---------------------------------------------------------------------------

function fn3(d, mode, p) {
  // Mirror of simulator.py fn3_savings_pressure / savings_pressure_curve_np
  let raw;
  if (mode === 'tanh') {
    raw = p.pmax * Math.tanh(p.k * d);
  } else if (mode === 'quadratic') {
    raw = Math.sign(d) * p.pmax * (Math.abs(d) / p.norm) ** 2;
  } else if (mode === 'deadband') {
    raw = Math.abs(d) < p.delta ? 0.0 : p.slope * (d - Math.sign(d) * p.delta);
  } else { // linear
    raw = d * p.slope;
  }
  return Math.max(p.pmin, Math.min(p.pmax, raw));
}

function renderSavings() {
  const mode  = document.getElementById('sp-mode').value;
  const slope = parseFloat(document.getElementById('sp-slope').value);
  const k     = parseFloat(document.getElementById('sp-k').value);
  const norm  = parseFloat(document.getElementById('sp-norm').value);
  const delta = parseFloat(document.getElementById('sp-delta').value);
  const dslope = parseFloat(document.getElementById('sp-dslope').value);

  // Update displayed values
  document.getElementById('val-slope').textContent  = slope.toFixed(2);
  document.getElementById('val-k').textContent      = k.toFixed(2);
  document.getElementById('val-norm').textContent   = norm.toFixed(2);
  document.getElementById('val-delta').textContent  = delta.toFixed(2);
  document.getElementById('val-dslope').textContent = dslope.toFixed(2);

  // Show/hide relevant param rows
  document.getElementById('row-slope') .style.display = mode === 'linear'    ? '' : 'none';
  document.getElementById('row-k')     .style.display = mode === 'tanh'       ? '' : 'none';
  document.getElementById('row-norm')  .style.display = mode === 'quadratic'  ? '' : 'none';
  document.getElementById('row-delta') .style.display = mode === 'deadband'   ? '' : 'none';
  document.getElementById('row-dslope').style.display = mode === 'deadband'   ? '' : 'none';

  const xs   = [];
  const nPts = 300;
  const [rMin, rMax] = [-1.0, 3.0];
  for (let i = 0; i <= nPts; i++) xs.push(rMin + (rMax - rMin) * i / nPts);

  const traces = D.meta.strata.map(strata => {
    const sp = D.savingsParams.strata_params[strata] || { pmin: -0.4, pmax: 0.4 };
    const p  = { pmin: sp.pmin, pmax: sp.pmax, slope, k, norm, delta, dslope };
    const ys = xs.map(r => fn3(r - 1.0, mode, p));
    return { name: strata, mode: 'lines', x: xs, y: ys, line: { width: 1.8 } };
  });

  Plotly.react('chart-tab3', traces, {
    ...PLOTLY_LAYOUT('savings / target (ratio)', 'Savings pressure'),
    shapes: [
      { type: 'line', x0: 1, x1: 1, y0: 0, y1: 1, yref: 'paper', line: { color: '#666', dash: 'dot' } },
      { type: 'line', x0: rMin, x1: rMax, y0: 0, y1: 0, line: { color: '#555', width: 1 } },
    ],
    title: { text: `Savings pressure — mode: ${mode}`, font: { color: '#ccc', size: 13 } },
  }, { responsive: true });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
  document.getElementById('status').textContent = 'Loading data…';
  try {
    await loadData();
  } catch (e) {
    document.getElementById('status').textContent = `Failed to load data: ${e.message}`;
    return;
  }
  document.getElementById('status').style.display = 'none';
  document.getElementById('main').style.display   = 'block';

  setupTabs();

  // ----- Tab 0 -----
  renderTab0();

  // ----- Tab 1 -----
  populateSelect('ag-strata', D.meta.strata);
  document.getElementById('ag-strata').addEventListener('change', renderTab1);
  renderTab1();

  // ----- Tab 2 -----
  populateSelect('ea-strata', D.meta.strata);
  populateSelect('ea-group', D.meta.groups.map(g => g.name));
  document.getElementById('ea-strata').addEventListener('change', () => { renderTab2Group(); renderTab2All(); });
  document.getElementById('ea-group') .addEventListener('change', renderTab2Group);
  renderTab2Group();
  renderTab2All();

  // ----- Tab 3 -----
  const sp = D.savingsParams.defaults;
  document.getElementById('sp-slope') .value = sp.pressure_linear_slope;
  document.getElementById('sp-k')     .value = sp.pressure_tanh_k;
  document.getElementById('sp-norm')  .value = sp.pressure_quadratic_norm;
  document.getElementById('sp-delta') .value = sp.pressure_deadband_delta;
  document.getElementById('sp-dslope').value = sp.pressure_deadband_slope;

  ['sp-mode','sp-slope','sp-k','sp-norm','sp-delta','sp-dslope'].forEach(id => {
    document.getElementById(id).addEventListener('input', renderSavings);
    document.getElementById(id).addEventListener('change', renderSavings);
  });
  renderSavings();
}

document.addEventListener('DOMContentLoaded', init);
