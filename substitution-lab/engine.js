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

  // What size to write so the good ends up at M relative to the outside
  // offset e, under two engine hypotheses that still need in-game testing.
  function modifierSize(m, e, stacking) {
    return stacking === 'additive' ? (1 + e) * (m - 1) : m - 1;
  }
  // Resulting multiplier relative to "without SOL" for a given size.
  function realised(size, e, stacking) {
    if (stacking === 'additive') return 1 + e > 0 ? Math.max(0, 1 + e + size) / (1 + e) : 1;
    return Math.max(0, 1 + size);
  }

  return { GROUPS, GOOD_NAMES, TIERS, NEUTRAL, tier, sum, memberships, planA, planB, aggregate, modifierSize, realised };
});
