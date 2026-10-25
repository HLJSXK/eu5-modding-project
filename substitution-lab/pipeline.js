// Interactive walk-through of the whole SOL demand chain. Math in engine.js.
(() => {
  'use strict';
  const S = window.Sub;
  const $ = id => document.getElementById(id);
  const STRATA_CN = { nobles: '贵族', clergy: '教士', burghers: '市民', lower: '平民' };
  const GOOD_CN = { wheat: '小麦', rice: '稻米', cloth: '布料' };
  const f = (n, d = 2) => n.toFixed(d);
  const x = (n, d = 2) => '×' + n.toFixed(d);
  const pct = n => (n * 100).toFixed(0) + '%';
  const tone = r => r > 1.005 ? 'down' : r < 0.995 ? 'up' : 'flat'; // overspending is bad (red)
  const dTone = d => d < 0.995 ? 'down' : d > 1.005 ? 'up' : 'flat';
  const head = cells => `<thead><tr>${cells.map(c => `<th>${c}</th>`).join('')}</tr></thead>`;
  const ratioChip = r => `<span class="chip ${tone(r)}">${pct(r)}</span>`;

  function opts() {
    return {
      substitution: $('c-sub').checked,
      weight: document.querySelector('input[name="c-w"]:checked').value,
      savings: Number($('c-sp').value),
    };
  }
  function config() {
    const cfg = JSON.parse(JSON.stringify(S.DEMO));
    cfg.markets.A.wheat = Number($('c-pa').value);
    cfg.markets.B.wheat = Number($('c-pb').value);
    return cfg;
  }

  function render() {
    const o = opts(), cfg = config();
    $('c-pa-o').textContent = f(cfg.markets.A.wheat);
    $('c-pb-o').textContent = f(cfg.markets.B.wheat);
    $('c-sp-o').textContent = (o.savings >= 0 ? '+' : '') + pct(o.savings);
    document.querySelectorAll('input[name="c-w"]').forEach(el => { el.disabled = !o.substitution; });
    const a = S.pipeline(cfg, { ...o, solver: false });
    const b = S.pipeline(cfg, { ...o, solver: true });
    const goods = a.goods;

    // 1. Country
    $('t-loc').innerHTML = head(['地点', '市场', ...S.STRATA.map(s => STRATA_CN[s] + ' 人口 / 收入')])
      + '<tbody>' + cfg.locations.map(l => `<tr><td>${l.id}</td><td>${l.market}</td>${S.STRATA.map(s => `<td>${l.pop[s]} / ${l.income[s]}</td>`).join('')}</tr>`).join('') + '</tbody>';

    // 2. Unit table
    $('t-unit').innerHTML = head(['每千人消费量', ...goods.map(g => `${GOOD_CN[g]}（默认价 ${cfg.goods[g].price}）`)])
      + '<tbody>' + S.STRATA.map(s => `<tr><td>${STRATA_CN[s]}</td>${goods.map(g => `<td>${cfg.unit[s][g]}</td>`).join('')}</tr>`).join('') + '</tbody>';

    // 3. Markets
    $('t-mkt').innerHTML = head(['市场', '商品', '价格比', '档位权重', '有效价格', 'D'])
      + '<tbody>' + Object.keys(a.market).flatMap(m => goods.map(g => {
        const r = cfg.markets[m][g], t = S.tier(r), d = a.market[m].d[g];
        return `<tr><td>${m}</td><td>${GOOD_CN[g]}</td><td>${f(r)}</td><td>${t.label} · ${t.weight}</td><td>${f(a.market[m].pEff[g])}</td><td class="${dTone(d)}"><b>${x(d)}</b></td></tr>`;
      })).join('') + '</tbody>';

    // 4. Country M
    if (!o.substitution) {
      $('m-out').innerHTML = '<div class="result-line">替代组关闭：所有 M = 1，下面各步就是现在的 SOL。</div>';
    } else {
      const wl = o.weight === 'money' ? '原消费量 × 有效价格' : '原消费量';
      $('m-out').innerHTML = `<div class="result-line">M = Σ(${wl} × D) ÷ Σ(${wl})　→　${goods.map(g => `${GOOD_CN[g]} <b class="${dTone(a.M[g])}">${x(a.M[g], 3)}</b>`).join('　')}</div>`;
    }
    const c = a.check.wheat;
    $('t-mcheck').innerHTML = head(['小麦（k、c 缩放前）', '想要', '统一 M 之后', '差'])
      + '<tbody>'
      + c.perMarket.map(p => `<tr><td>市场 ${p.market} 数量</td><td>${f(p.target, 1)}</td><td>${f(p.actual, 1)}</td><td class="${p.actual - p.target > 0.05 ? 'up' : p.actual - p.target < -0.05 ? 'down' : 'flat'}">${(p.actual - p.target >= 0 ? '+' : '') + f(p.actual - p.target, 1)}</td></tr>`).join('')
      + [['全国数量', c.qTarget, c.qActual], ['全国花费（有效价格）', c.mTarget, c.mActual]].map(([n, t, v]) => `<tr><td><b>${n}</b></td><td>${f(t, 1)}</td><td>${f(v, 1)}</td><td class="${Math.abs(v - t) < 0.05 ? 'flat' : 'down'}">${Math.abs(v - t) < 0.05 ? '✓ 一致' : (v - t >= 0 ? '+' : '') + f(v - t, 1)}</td></tr>`).join('')
      + '</tbody>';
    $('m-note').textContent = !o.substitution ? '' : o.weight === 'money'
      ? '按金额加权：全国花费对上，全国数量偏了。'
      : '按数量加权：全国数量对上，全国花费偏了。两市场价格相同时两者都对。';

    // 5. Alpha
    $('t-alpha').innerHTML = head(['地点', '流动资金', '基础支出', 'k', '地点支出 ÷ 资金', '各阶层支出 ÷ 资金（贵/教/市/平）'])
      + '<tbody>' + a.loc.map(l => {
        const F = S.sum(S.STRATA.map(s => l.funds[s])), B = S.sum(S.STRATA.map(s => l.base[s]));
        return `<tr><td>${l.id}</td><td>${f(F, 1)}</td><td>${f(B, 1)}</td><td><b>${f(l.k, 3)}</b></td><td>${ratioChip(1)}</td><td>${S.STRATA.map(s => ratioChip(l.spend[s] / l.funds[s])).join(' ')}</td></tr>`;
      }).join('') + '</tbody>';

    // 6. Beta
    const status = { exact: '精确解成功', fallback: '精确解失败（真实代码会做顶点搜索，示例直接退回 α）' }[b.solverStatus];
    $('beta-coef').innerHTML = `${status}：` + S.STRATA.map((s, i) => `${STRATA_CN[s]}类 c = <b>${f(b.coef[i], 3)}</b>`).join('　')
      + `<br><span class="caption">分类：${b.loc.map(l => `${l.id} → ${STRATA_CN[S.STRATA[l.cls]]}类`).join('，')}</span>`;
    const row = (label, ra, rb) => `<div class="cmp-row"><span>${label}</span><span>α ${ratioChip(ra)}</span><span>β ${ratioChip(rb)}</span></div>`;
    $('beta-strata').innerHTML = S.STRATA.map(s => row(STRATA_CN[s], a.strata[s].spend / a.strata[s].funds, b.strata[s].spend / b.strata[s].funds)).join('');
    $('beta-loc').innerHTML = b.loc.map((l, i) => {
      const F = S.sum(S.STRATA.map(s => l.funds[s]));
      return row(l.id, S.sum(S.STRATA.map(s => a.loc[i].spend[s])) / F, S.sum(S.STRATA.map(s => l.spend[s])) / F);
    }).join('');

    // 7. Writes
    $('w-loc').innerHTML = b.loc.map(l => `<p>${l.id}：k × c = ${f(l.k, 3)} × ${f(l.c, 3)} → size = <b>${f(l.scale - 1, 3)}</b></p>`).join('');
    $('w-cty').innerHTML = goods.map(g => `<p>sol_substitute_${g}：size = <b>${f(S.modifierSize(b.M[g], 0), 3)}</b></p>`).join('');
    const l1 = b.loc[0];
    $('w-ex').textContent = `${f(b.M.wheat, 3)}（M）× ${f(l1.scale, 3)}（k × c）= ${f(b.M.wheat * l1.scale, 3)}`;
  }

  ['c-pa', 'c-pb', 'c-sp'].forEach(id => $(id).addEventListener('input', render));
  ['c-sub'].forEach(id => $(id).addEventListener('change', render));
  document.querySelectorAll('input[name="c-w"]').forEach(el => el.addEventListener('change', render));
  render();
})();
