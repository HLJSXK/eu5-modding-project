// Page interactions. All math lives in engine.js (window.Sub).
// Views are built once; slider moves only patch text and bar widths so a drag
// is never interrupted by a re-render.
(() => {
  'use strict';
  const S = window.Sub;
  const $ = id => document.getElementById(id);
  const all = (sel, root = document) => [...root.querySelectorAll(sel)];
  const name = i => S.GOOD_NAMES[i] || i;
  const group = id => S.GROUPS.find(g => g.id === id);
  const member = S.memberships(S.GROUPS);
  const x = (n, d = 2) => '×' + n.toFixed(d);
  const pct = n => (n >= 0 ? '+' : '') + (n * 100).toFixed(0) + '%';
  const tone = d => d < 0.995 ? 'down' : d > 1.005 ? 'up' : 'flat';
  const setTone = (el, d) => { el.classList.remove('down', 'up', 'flat'); el.classList.add(tone(d)); };
  const AXIS = 3;

  // Shared state: one price ratio and supply flag per good (steps 2, 3, sandbox).
  const price = {}, supply = {};
  const resetPrices = () => { for (const i of Object.keys(member)) { price[i] = 1; supply[i] = true; } };
  const EXAMPLE = { wheat: 2.0, rice: 0.6, cloth: 2.4 };
  resetPrices(); Object.assign(price, EXAMPLE);
  const goodsState = () => Object.fromEntries(Object.keys(member).map(i => [i, { ratio: price[i], active: supply[i] }]));

  const bar = key => `<div class="dbar" data-bar="${key}"><i></i><s style="left:${100 / AXIS}%"></s></div>`;
  const priceCtl = (i, kind = 'range') => kind === 'range'
    ? `<input type="range" min="0.2" max="3" step="0.01" data-price="${i}" aria-label="${name(i)} 价格比"><span class="pr" data-pr="${i}"></span><span class="tier" data-tier="${i}"></span>`
    : `<input type="number" min="0.1" max="5" step="0.1" data-price="${i}" aria-label="${name(i)} 价格比">`;

  // Push shared state + planA result into every bound element on the page.
  function sync(skip) {
    const r = S.planA(S.GROUPS, goodsState());
    const local = {}; // per-view results that are not the full network
    const g2 = group($('g-select').value);
    local.g = S.planA([g2], goodsState());
    for (const el of all('[data-price]')) if (el !== skip) el.value = price[el.dataset.price];
    for (const el of all('[data-supply]')) el.checked = supply[el.dataset.supply];
    for (const el of all('[data-pr]')) el.textContent = price[el.dataset.pr].toFixed(2);
    for (const el of all('[data-tier]')) {
      const t = S.tier(price[el.dataset.tier]);
      el.textContent = `${t.label} · ${t.weight}`;
      setTone(el, t.weight);
    }
    for (const el of all('[data-d]')) {
      const [view, i, gid] = el.dataset.d.split(':');
      const d = view === 'g' ? local.g[i].d : gid ? r[i].groups.find(p => p.group === gid).d : r[i].d;
      el.textContent = x(d);
      setTone(el, d);
    }
    for (const el of all('[data-bar]')) {
      const [, i] = el.dataset.bar.split(':');
      const d = local.g[i].d;
      el.firstElementChild.style.width = Math.min(d, AXIS) / AXIS * 100 + '%';
      setTone(el, d);
    }
    for (const el of all('[data-row]')) el.classList.toggle('off', !supply[el.dataset.row]);
    const o = $('o-select').value, per = member[o].map(gid => r[o].groups.find(p => p.group === gid).d);
    $('o-result').innerHTML = `${name(o)}最终倍率 = (${per.map(d => d.toFixed(2)).join(' + ')}) ÷ 2 = <b class="${tone(r[o].d)}">${x(r[o].d)}</b>`;
  }

  // ---- Step 1 -------------------------------------------------------------
  const ladder = [...S.TIERS.slice(0, 3), S.NEUTRAL, ...S.TIERS.slice(3).reverse()];
  $('t-ladder').innerHTML = ladder.map(row => `
    <div class="rung ${row.weight < 1 ? 'down' : row.weight > 1 ? 'up' : 'flat'}">
      <span>${row.label}</span><span class="range">${row.range}</span><b>权重 ${row.weight}</b>
    </div>`).join('');
  function renderTier() {
    const r = Number($('t-ratio').value), t = S.tier(r);
    $('t-ratio-out').textContent = r.toFixed(2);
    all('.rung').forEach((el, k) => el.classList.toggle('on', ladder[k] === t));
  }
  $('t-ratio').addEventListener('input', renderTier);

  // ---- Step 2 -------------------------------------------------------------
  $('g-select').innerHTML = S.GROUPS.map(g => `<option value="${g.id}">${g.name}（${g.members.map(name).join('、')}）</option>`).join('');
  $('g-select').value = 'staple';
  function buildGroup() {
    const g = group($('g-select').value);
    $('g-rows').innerHTML = g.members.map(i => `<div class="row" data-row="${i}">
        <span class="gname">${name(i)}${member[i].length > 1 ? '<em class="dup">跨组</em>' : ''}</span>
        <span class="ctl">${priceCtl(i)}</span>
        <label class="sup"><input type="checkbox" data-supply="${i}"> 有供给</label>
        ${bar('g:' + i)}<b class="dv" data-d="g:${i}"></b>
      </div>`).join('');
    sync();
  }
  $('g-select').addEventListener('change', buildGroup);
  $('g-reset').addEventListener('click', () => { resetPrices(); sync(); });

  // ---- Step 3 -------------------------------------------------------------
  const overlaps = Object.keys(member).filter(i => member[i].length > 1);
  $('o-select').innerHTML = overlaps.map(i => `<option value="${i}">${name(i)}（${member[i].map(id => group(id).name).join(' + ')}）</option>`).join('');
  $('o-select').value = 'cloth';
  function buildOverlap() {
    const i = $('o-select').value;
    $('o-groups').innerHTML = member[i].map(group).map(g => `
      <div class="mini">
        <h4>${g.name}</h4>
        ${g.members.map(j => `<div class="mrow ${j === i ? 'focus' : ''}"><span class="gname">${name(j)}</span><span class="ctl">${priceCtl(j)}</span></div>`).join('')}
        <p>${name(i)}在本组：<b data-d="o:${i}:${g.id}"></b></p>
      </div>`).join('');
    sync();
  }
  $('o-select').addEventListener('change', buildOverlap);

  // ---- Step 4 -------------------------------------------------------------
  const abIds = ['ab-ba', 'ab-ra', 'ab-bb', 'ab-rb'];
  function renderAB() {
    const [ba, ra, bb, rb] = abIds.map(id => Number($(id).value));
    $('ab-ba-out').textContent = ba; $('ab-bb-out').textContent = bb;
    $('ab-ra-out').textContent = ra.toFixed(2); $('ab-rb-out').textContent = rb.toFixed(2);
    const pair = [{ id: 'pair', n: 2, members: ['a', 'b'] }];
    const goods = { a: { ratio: ra, b: ba }, b: { ratio: rb, b: bb } };
    const A = S.planA(pair, goods), B = S.planB(pair, goods);
    const rows = [
      ['原来', ba, bb, '替代前'],
      ['方案 A', ba * A.a.d, bb * A.b.d, `甲 ${x(A.a.d)}，乙 ${x(A.b.d)}`],
      ['方案 B', B.a.target, B.b.target, `甲 ${x(B.a.d)}，乙 ${x(B.b.d)}`],
    ];
    const scale = Math.max(...rows.map(r => r[1] + r[2]));
    $('ab-bars').innerHTML = rows.map(([label, a, b, note]) => {
      const total = a + b, diff = total - (ba + bb);
      return `<div class="srow">
        <span class="slabel">${label}</span>
        <div class="sbar"><i class="ga" style="width:${a / scale * 100}%">${a / scale >= 0.1 ? a.toFixed(1) : ''}</i><i class="gb" style="width:${b / scale * 100}%">${b / scale >= 0.1 ? b.toFixed(1) : ''}</i></div>
        <span class="stotal">合计 ${total.toFixed(1)}${Math.abs(diff) > 0.05 ? ` <em class="${diff < 0 ? 'down' : 'up'}">(${diff > 0 ? '+' : ''}${diff.toFixed(1)})</em>` : ''}</span>
        <span class="snote">${note}</span>
      </div>`;
    }).join('');
  }
  abIds.forEach(id => $(id).addEventListener('input', renderAB));

  // ---- Step 5 -------------------------------------------------------------
  const markets = [{ label: '市场甲', r: 2.5, q: 30 }, { label: '市场乙', r: 1, q: 50 }, { label: '市场丙', r: 0.5, q: 20 }];
  $('c-markets').innerHTML = markets.map((m, k) => `<div class="market">
      <h4>${m.label}</h4>
      <label class="slider-row"><span>小麦价格比</span><input type="range" min="0.2" max="3" step="0.05" value="${m.r}" data-mr="${k}"><output data-mro="${k}"></output></label>
      <label class="slider-row"><span>原消费量</span><input type="range" min="0" max="100" step="1" value="${m.q}" data-mq="${k}"><output data-mqo="${k}"></output></label>
      <p class="localD">当地 D = <b data-md="${k}"></b></p>
      <div class="vs"><span>想要</span><div class="hbar"><i class="want" data-mw="${k}"></i></div><span data-mwv="${k}"></span></div>
      <div class="vs"><span>实际</span><div class="hbar"><i class="got" data-mg="${k}"></i></div><span data-mgv="${k}"></span></div>
      <p class="err" data-me="${k}"></p>
    </div>`).join('');
  function renderCountry() {
    const staple = group('staple');
    const rows = markets.map(m => ({ q: m.q, d: S.planA([staple], { wheat: { ratio: m.r } }).wheat.d }));
    const M = S.aggregate(rows);
    const scale = Math.max(1, ...markets.map((m, k) => Math.max(m.q * rows[k].d, m.q * M)));
    const q = (attr, k) => document.querySelector(`[data-${attr}="${k}"]`);
    markets.forEach((m, k) => {
      const want = m.q * rows[k].d, got = m.q * M, err = got - want;
      q('mro', k).textContent = m.r.toFixed(2);
      q('mqo', k).textContent = m.q;
      q('md', k).textContent = x(rows[k].d); setTone(q('md', k), rows[k].d);
      q('mw', k).style.width = want / scale * 100 + '%';
      q('mg', k).style.width = got / scale * 100 + '%';
      q('mwv', k).textContent = want.toFixed(1);
      q('mgv', k).textContent = got.toFixed(1);
      q('me', k).textContent = Math.abs(err) < 0.05 ? '无误差' : `误差 ${err > 0 ? '+' : ''}${err.toFixed(1)}`;
      q('me', k).className = 'err ' + (Math.abs(err) < 0.05 ? 'flat' : err > 0 ? 'up' : 'down');
    });
    const tq = S.sum(rows.map(r => r.q));
    $('c-result').innerHTML = tq > 0.001
      ? `国家小麦倍率 M = (${rows.map(r => `${r.q}×${r.d.toFixed(2)}`).join(' + ')}) ÷ ${tq} = <b class="${tone(M)}">${x(M, 3)}</b>`
      : '全国消费量为 0 → M = 1，移除 modifier';
  }
  $('c-markets').addEventListener('input', e => {
    const t = e.target;
    if (t.dataset.mr) markets[t.dataset.mr].r = Number(t.value);
    else if (t.dataset.mq) markets[t.dataset.mq].q = Number(t.value);
    renderCountry();
  });

  // ---- Step 6 -------------------------------------------------------------
  function renderModifier() {
    const M = Number($('m-m').value), e = Number($('m-e').value);
    const stack = document.querySelector('input[name="m-stack"]:checked').value;
    $('m-m-out').textContent = x(M);
    $('m-e-out').textContent = pct(e);
    const fixed = S.modifierSize(M, e, stack);
    const card = (title, size, desc) => {
      const got = S.realised(size, e, stack), ok = Math.abs(got - M) < 1e-6;
      return `<div class="mini ${ok ? 'good' : 'bad'}">
        <h4>${title}</h4>
        <p>写 size = <b>${size.toFixed(3)}</b></p>
        <p>结果：需求是"没有 SOL 时"的 <b>${x(got)}</b></p>
        <p class="verdict">${ok ? '✓ 等于目标 M' : `✗ 目标是 ${x(M)}${got === 0 ? '，需求被压到 0' : ''}`}</p>
        <p class="caption">${desc}</p>
      </div>`;
    };
    $('m-result').innerHTML = card('直接写 M − 1', M - 1, '最直观的写法')
      + (stack === 'additive'
        ? card('按假设换算', fixed, '若相加：size = (1 + 已有修正) × (M − 1)')
        : card('相乘时不用换算', fixed, '若各来源相乘，M − 1 就是对的'));
    $('m-code-size').textContent = fixed.toFixed(3);
  }
  ['m-m', 'm-e'].forEach(id => $(id).addEventListener('input', renderModifier));
  all('input[name="m-stack"]').forEach(el => el.addEventListener('change', renderModifier));

  // ---- Sandbox ------------------------------------------------------------
  $('x-groups').innerHTML = S.GROUPS.map(g => `
    <div class="card">
      <h4>${g.name}</h4>
      ${g.members.map(i => `<div class="xrow ${member[i].length > 1 ? 'dup-row' : ''}">
        <span class="gname">${name(i)}</span>${priceCtl(i, 'number')}<b class="dv" data-d="x:${i}"></b>
      </div>`).join('')}
    </div>`).join('');
  $('x-reset').addEventListener('click', () => { resetPrices(); sync(); });
  $('x-random').addEventListener('click', () => {
    const picks = [0.3, 0.5, 0.75, 1, 1, 1, 1.5, 2, 2.6];
    for (const i of Object.keys(member)) price[i] = picks[Math.floor(Math.random() * picks.length)];
    sync();
  });

  // Any shared price/supply control on the page.
  document.addEventListener('input', e => {
    const t = e.target;
    if (t.dataset.price && t.type === 'range') { price[t.dataset.price] = Number(t.value); sync(t); }
  });
  document.addEventListener('change', e => {
    const t = e.target;
    if (t.dataset.price && t.type === 'number') {
      const v = Number(t.value);
      if (Number.isFinite(v) && v > 0) price[t.dataset.price] = v;
      sync();
    } else if (t.dataset.supply) { supply[t.dataset.supply] = t.checked; sync(); }
  });

  renderTier(); buildGroup(); buildOverlap(); renderAB(); renderCountry(); renderModifier();
})();
