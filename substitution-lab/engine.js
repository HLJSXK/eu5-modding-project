// Pure math for the substitution explainer. Works in the browser (window.Sub)
// and in Node (require) so the numbers on the page are unit-tested.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.Sub = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // Current core catalogue (data/goods_weights.csv). v1.1 differed only in
  // luxury_food (+victuals) and mounts (no camels).
  const GROUPS = [
    ['basic_clothing', '基本衣物', ['cloth', 'leather']],
    ['crude_goods', '粗制品', ['lumber', 'masonry', 'tools', 'pottery']],
    ['staple', '主食', ['wheat', 'rice', 'millet', 'maize', 'potato', 'legumes']],
    ['condiments', '调味品', ['sugar', 'salt', 'olives']],
    ['heating', '取暖燃料', ['lumber', 'coal', 'beeswax']],
    ['household', '家居用品', ['furniture', 'pottery', 'glass', 'paper', 'beeswax']],
    ['standard_clothing', '标准衣物', ['cloth', 'fine_cloth']],
    ['intoxicants', '嗜好饮料', ['wine', 'beer', 'liquor', 'tobacco']],
    ['luxury_drinks', '奢侈饮品', ['tea', 'coffee', 'wine', 'cocoa']],
    ['luxury_food', '奢侈食物', ['wild_game', 'fruit', 'fish']],
    ['luxury_goods', '奢侈商品', ['fine_cloth', 'fur', 'porcelain', 'lacquerware', 'marble', 'glass']],
    ['protein', '蛋白食物', ['fish', 'wild_game', 'livestock']],
    ['spices', '香料', ['saffron', 'pepper', 'cloves', 'chili']],
    ['precious', '贵重品', ['goods_gold', 'silver', 'jewelry']],
    ['treasures', '珍宝', ['amber', 'gems', 'ivory', 'pearls']],
    ['medicine', '药品', ['medicaments', 'mercury']],
    ['ritual', '祭祀物品', ['incense', 'mercury']],
    ['weapons', '武器', ['weaponry', 'firearms']],
    ['mounts', '坐骑', ['horses', 'camels', 'elephants']],
    ['knowledge', '知识用品', ['paper', 'books']],
  ].map(([id, name, members]) => ({ id, name, members, n: members.length }));

  const GOOD_NAMES = {
    cloth: '布料', leather: '皮革', lumber: '木材', masonry: '石材', tools: '工具', pottery: '陶器',
    wheat: '小麦', rice: '稻米', millet: '小米', maize: '玉米', potato: '马铃薯', legumes: '豆类',
    sugar: '糖', salt: '盐', olives: '橄榄', coal: '煤炭', beeswax: '蜂蜡', furniture: '家具',
    glass: '玻璃', paper: '纸张', fine_cloth: '精细布料', wine: '葡萄酒', beer: '啤酒', liquor: '烈酒',
    tobacco: '烟草', tea: '茶叶', coffee: '咖啡', cocoa: '可可', wild_game: '野味', victuals: '加工食品',
    fruit: '水果', fish: '鱼类', fur: '毛皮', porcelain: '瓷器', lacquerware: '漆器', marble: '大理石',
    livestock: '牲畜', saffron: '藏红花', pepper: '胡椒', cloves: '丁香', chili: '辣椒',
    goods_gold: '黄金', silver: '白银', jewelry: '珠宝', amber: '琥珀', gems: '宝石', ivory: '象牙',
    pearls: '珍珠', medicaments: '药材', mercury: '水银', incense: '熏香', weaponry: '兵器',
    firearms: '火器', horses: '马匹', camels: '骆驼', elephants: '大象', books: '书籍',
  };

  // Strict comparisons, checked in this order (v1.1 SOL_substitute_effects).
  const TIERS = [
    { test: r => r > 2.30, weight: 0.25, label: '严重昂贵', range: '> 2.30' },
    { test: r => r > 1.70, weight: 0.50, label: '明显昂贵', range: '1.70 – 2.30' },
    { test: r => r > 1.30, weight: 0.75, label: '轻度昂贵', range: '1.30 – 1.70' },
    { test: r => r < 0.40, weight: 2.00, label: '非常便宜', range: '< 0.40' },
    { test: r => r < 0.65, weight: 1.50, label: '明显便宜', range: '0.40 – 0.65' },
    { test: r => r < 0.85, weight: 1.25, label: '较便宜', range: '0.65 – 0.85' },
  ];
  const NEUTRAL = { weight: 1, label: '正常', range: '0.85 – 1.30' };
  function tier(ratio) { return TIERS.find(t => t.test(ratio)) || NEUTRAL; }

  const sum = a => a.reduce((s, x) => s + x, 0);

  function memberships(groups) {
    const m = {};
    for (const g of groups) for (const i of g.members) (m[i] ||= []).push(g.id);
    return m;
  }

  // goods[i] = { ratio, active }. active=false means no supply / no modifier
  // interface: frozen at 1 and not counted when the group shares out demand.
  // Returns D(i) = H_T / H_1 with per-group detail.
  function planA(groups, goods) {
    const member = memberships(groups);
    const isActive = i => goods[i]?.active !== false;
    const w = i => tier(goods[i]?.ratio ?? 1).weight;
    const acc = {};
    for (const i of Object.keys(member)) acc[i] = { ht: 0, h1: 0, groups: [] };
    for (const g of groups) {
      const active = g.members.filter(isActive);
      const totalW = sum(active.map(w));
      const substitutes = active.length >= 2;
      for (const i of g.members) {
        if (!isActive(i)) { acc[i].groups.push({ group: g.id, d: 1, skipped: true }); continue; }
        const f1 = g.n / active.length;
        const ft = substitutes ? g.n * w(i) / totalW : f1;
        acc[i].ht += ft / member[i].length;
        acc[i].h1 += f1 / member[i].length;
        acc[i].groups.push({ group: g.id, d: ft / f1, share1: 1 / active.length, shareT: ft / g.n, skipped: !substitutes });
      }
    }
    const out = {};
    for (const [i, a] of Object.entries(acc)) out[i] = { d: a.h1 > 0 ? a.ht / a.h1 : 1, groups: a.groups };
    return out;
  }

  // goods[i] = { ratio, b, active }. Split each good's baseline evenly over its
  // groups, then reshare every group's budget by b × weight. Budget-conserving.
  function planB(groups, goods) {
    const member = memberships(groups);
    const isActive = i => goods[i]?.active !== false && (goods[i]?.b || 0) > 0;
    const w = i => tier(goods[i]?.ratio ?? 1).weight;
    const out = {};
    for (const i of Object.keys(member)) out[i] = { base: goods[i]?.b || 0, target: 0 };
    for (const g of groups) {
      const part = i => (goods[i]?.b || 0) / member[i].length;
      const active = g.members.filter(isActive);
      const budget = sum(active.map(part));
      const weighted = sum(active.map(i => part(i) * w(i)));
      for (const i of g.members) {
        const ok = isActive(i) && active.length >= 2 && weighted > 0;
        out[i].target += ok ? budget * part(i) * w(i) / weighted : part(i);
      }
    }
    for (const o of Object.values(out)) o.d = o.base > 0 ? o.target / o.base : 1;
    return out;
  }

  // rows = [{ q, d }]. q is a neutral-priced reference quantity, so weighting
  // by q equals weighting by q × default_price for one good.
  function aggregate(rows, epsilon = 0.001) {
    const base = sum(rows.map(r => r.q));
    const target = sum(rows.map(r => r.q * r.d));
    return base > epsilon ? target / base : 1;
  }

  // Measured in-game (1.4): sources of the same per-good modifier add inside
  // one factor (1 + sum), different modifier types multiply, and a factor
  // below 0 clamps demand to 0. Size that makes the good end up at M relative
  // to "without SOL", given the existing same-good offset e:
  function modifierSize(m, e) { return (1 + e) * (m - 1); }
  // Resulting multiplier relative to "without SOL" for a given size.
  function realised(size, e) { return 1 + e > 0 ? Math.max(0, 1 + e + size) / (1 + e) : 1; }

  // ---- Whole SOL demand pipeline on a toy country --------------------------
  // Mirrors A_SOL_economy_effects.txt: yearly market unit spending, location
  // raw closure (result alpha), country class solver (result beta), plus the
  // planned country substitution factor M. Four strata as in the solver:
  // nobles, clergy, burghers, lower (= commoners + tribesmen).
  const STRATA = ['nobles', 'clergy', 'burghers', 'lower'];
  const DEMO = {
    goods: { wheat: { price: 1 }, rice: { price: 1 }, cloth: { price: 2 } },
    groups: [{ id: 'staple', n: 2, members: ['wheat', 'rice'] }, { id: 'cloth', n: 1, members: ['cloth'] }],
    // Per-capita quantity: a constant table computed outside the game.
    unit: {
      nobles: { wheat: 4, rice: 2, cloth: 3 },
      clergy: { wheat: 3, rice: 2, cloth: 2 },
      burghers: { wheat: 3, rice: 3, cloth: 2 },
      lower: { wheat: 1, rice: 1, cloth: 0.3 },
    },
    markets: { A: { wheat: 2.0, rice: 1, cloth: 1 }, B: { wheat: 0.6, rice: 1, cloth: 1 } },
    locations: [
      { id: 'L1', market: 'A', pop: { nobles: 0.2, clergy: 0.1, burghers: 4, lower: 10 }, income: { nobles: 5, clergy: 2, burghers: 45, lower: 24 } },
      { id: 'L2', market: 'A', pop: { nobles: 0.2, clergy: 0.1, burghers: 0.3, lower: 30 }, income: { nobles: 5, clergy: 1, burghers: 4, lower: 72 } },
      { id: 'L3', market: 'B', pop: { nobles: 0.1, clergy: 2, burghers: 0.3, lower: 6 }, income: { nobles: 3, clergy: 22, burghers: 3, lower: 10 } },
      { id: 'L4', market: 'B', pop: { nobles: 2, clergy: 0.1, burghers: 0.3, lower: 6 }, income: { nobles: 45, clergy: 2, burghers: 3, lower: 10 } },
    ],
  };

  function solve4(A, b) {
    const n = b.length, M = A.map((r, i) => [...r, b[i]]);
    for (let c = 0; c < n; c++) {
      let p = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
      if (Math.abs(M[p][c]) < 1e-12) return null;
      [M[c], M[p]] = [M[p], M[c]];
      for (let r = 0; r < n; r++) if (r !== c) {
        const f = M[r][c] / M[c][c];
        for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
      }
    }
    return M.map((r, i) => r[n] / r[i]);
  }

  // opts: { substitution, weight: 'quantity'|'money', solver, savings }
  function pipeline(cfg, opts = {}) {
    const goods = Object.keys(cfg.goods);
    const sub = !!opts.substitution, weight = opts.weight || 'quantity';
    // 1. Yearly market refresh: effective price min(market, default) and D.
    const market = {};
    for (const [id, ratios] of Object.entries(cfg.markets)) {
      const D = planA(cfg.groups, Object.fromEntries(goods.map(g => [g, { ratio: ratios[g] }])));
      market[id] = {
        pEff: Object.fromEntries(goods.map(g => [g, Math.min(ratios[g], 1) * cfg.goods[g].price])),
        d: Object.fromEntries(goods.map(g => [g, D[g].d])),
      };
    }
    // 2. Quantities before any scaling: pop x constant unit table.
    const loc = cfg.locations.map(l => ({
      ...l,
      q: Object.fromEntries(STRATA.map(s => [s, Object.fromEntries(goods.map(g => [g, l.pop[s] * cfg.unit[s][g]]))])),
    }));
    const qOf = (l, g) => sum(STRATA.map(s => l.q[s][g]));
    // 3. Country substitution factor M(g), one per good.
    const M = {}, check = {};
    for (const g of goods) {
      let base = 0, target = 0;
      for (const l of loc) {
        const mk = market[l.market], w = weight === 'money' ? mk.pEff[g] : 1;
        base += qOf(l, g) * w; target += qOf(l, g) * mk.d[g] * w;
      }
      M[g] = sub && base > 1e-9 ? target / base : 1;
      const dd = l => (sub ? market[l.market].d[g] : 1);
      check[g] = {
        qTarget: sum(loc.map(l => qOf(l, g) * dd(l))),
        qActual: sum(loc.map(l => qOf(l, g) * M[g])),
        mTarget: sum(loc.map(l => qOf(l, g) * dd(l) * market[l.market].pEff[g])),
        mActual: sum(loc.map(l => qOf(l, g) * M[g] * market[l.market].pEff[g])),
        perMarket: Object.keys(market).map(m => {
          const ls = loc.filter(l => l.market === m);
          return { market: m, target: sum(ls.map(l => qOf(l, g) * dd(l))), actual: sum(ls.map(l => qOf(l, g) * M[g])) };
        }),
      };
    }
    // 4. Location closure (result alpha): k = liquid funds / base spending.
    const fundsMul = Math.max(0, 1 + (opts.savings || 0));
    for (const l of loc) {
      const mk = market[l.market];
      l.base = Object.fromEntries(STRATA.map(s => [s, sum(goods.map(g => l.q[s][g] * M[g] * mk.pEff[g]))]));
      l.funds = Object.fromEntries(STRATA.map(s => [s, l.income[s] * fundsMul]));
      const B = sum(STRATA.map(s => l.base[s])), F = sum(STRATA.map(s => l.funds[s]));
      l.k = B > 0 ? F / B : 1;
    }
    // 5. Country class solver (result beta). Class = most over-represented
    // stratum by base-spending share; the real code adds confidence ordering
    // and capacity penalties, and a vertex sweep when the exact solve fails.
    const country = Object.fromEntries(STRATA.map(s => [s, sum(loc.map(l => l.base[s]))]));
    const cTotal = sum(Object.values(country));
    for (const l of loc) {
      const B = sum(STRATA.map(s => l.base[s]));
      let best = -Infinity;
      STRATA.forEach((s, i) => {
        const score = (l.base[s] / B - country[s] / cTotal) / Math.max(country[s] / cTotal, 0.02);
        if (score > best) { best = score; l.cls = i; }
      });
    }
    const A = STRATA.map(s => STRATA.map((_, c) => sum(loc.filter(l => l.cls === c).map(l => l.base[s] * l.k))));
    const target = STRATA.map(s => sum(loc.map(l => l.funds[s])));
    let coef = [1, 1, 1, 1], solverStatus = 'off';
    if (opts.solver) {
      const x = solve4(A, target);
      if (x && x.every(v => v > 0)) { coef = x; solverStatus = 'exact'; }
      else solverStatus = 'fallback';
    }
    for (const l of loc) {
      l.c = coef[l.cls];
      l.scale = l.k * l.c;
      l.spend = Object.fromEntries(STRATA.map(s => [s, l.base[s] * l.scale]));
    }
    const strata = Object.fromEntries(STRATA.map((s, i) => [s, { funds: target[i], spend: sum(loc.map(l => l.spend[s])) }]));
    return { goods, market, loc, M, check, coef, solverStatus, strata };
  }

  return { STRATA, DEMO, pipeline, solve4, GROUPS, GOOD_NAMES, TIERS, NEUTRAL, tier, sum, memberships, planA, planB, aggregate, modifierSize, realised };
});
