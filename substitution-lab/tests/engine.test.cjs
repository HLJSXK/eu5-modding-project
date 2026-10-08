const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../engine.js');

const close = (a, b, tol = 1e-9) => assert.ok(Math.abs(a - b) < tol, `${a} != ${b}`);
const pair = [{ id: 'g', n: 2, members: ['a', 'b'] }];

test('tier boundaries are strict', () => {
  for (const [r, at, below, above] of [[2.3, .5, .5, .25], [1.7, .75, .75, .5], [1.3, 1, 1, .75], [.85, 1, 1.25, 1], [.65, 1.25, 1.5, 1.25], [.4, 1.5, 2, 1.5]]) {
    assert.equal(S.tier(r).weight, at);
    assert.equal(S.tier(r - 1e-10).weight, below);
    assert.equal(S.tier(r + 1e-10).weight, above);
  }
});

test('catalogue: 20 groups, 56 goods, 67 memberships, 11 overlaps', () => {
  const m = S.memberships(S.GROUPS);
  assert.equal(S.GROUPS.length, 20);
  assert.equal(Object.keys(m).length, 56);
  assert.equal(S.GROUPS.flatMap(g => g.members).length, 67);
  assert.equal(Object.values(m).filter(x => x.length === 2).length, 11);
  for (const i of Object.keys(m)) assert.ok(S.GOOD_NAMES[i], i);
});

test('neutral prices give D = 1 everywhere, both plans', () => {
  const goods = Object.fromEntries(Object.keys(S.memberships(S.GROUPS)).map((i, n) => [i, { ratio: 1, b: n + 1, active: n % 5 !== 0 }]));
  for (const o of Object.values(S.planA(S.GROUPS, goods))) close(o.d, 1);
  for (const o of Object.values(S.planB(S.GROUPS, goods))) close(o.d, 1);
});

test('spec example: 90/10 baseline, weights 0.5/1', () => {
  const goods = { a: { ratio: 2, b: 90 }, b: { ratio: 1, b: 10 } };
  const a = S.planA(pair, goods), b = S.planB(pair, goods);
  close(90 * a.a.d, 60); close(10 * a.b.d, 40 / 3);
  close(b.a.target, 900 / 11); close(b.b.target, 200 / 11);
});

test('plan A: D is weight over the group mean weight', () => {
  const g = S.GROUPS.filter(x => x.id === 'staple');
  const r = S.planA(g, { wheat: { ratio: 2.5 }, rice: { ratio: 0.3 } });
  const mean = (0.25 + 2 + 4) / 6;
  close(r.wheat.d, 0.25 / mean); close(r.rice.d, 2 / mean); close(r.millet.d, 1 / mean);
});

test('plan A averages overlapping goods across both groups', () => {
  const g = [{ id: 'x', n: 2, members: ['a', 'b'] }, { id: 'y', n: 2, members: ['a', 'c'] }];
  const r = S.planA(g, { a: { ratio: 2 }, c: { ratio: 0.3 } });
  close(r.a.d, (2 / 3 + 0.4) / 2);
});

test('inactive goods are frozen and a lone survivor does not substitute', () => {
  const r = S.planA(pair, { a: { ratio: 3, active: false }, b: { ratio: 0.3 } });
  close(r.a.d, 1); close(r.b.d, 1);
});

test('plan B conserves each group budget across the full network', () => {
  const ratios = [.3, .5, .7, 1, 1.5, 2, 2.5];
  const ids = Object.keys(S.memberships(S.GROUPS));
  for (let s = 0; s < 20; s++) {
    const goods = Object.fromEntries(ids.map((i, n) => [i, { ratio: ratios[(n + s) % 7], b: (n * 13 + s * 7) % 41, active: (n + s) % 9 !== 0 }]));
    const r = S.planB(S.GROUPS, goods);
    close(S.sum(Object.values(r).map(o => o.target)), S.sum(ids.map(i => goods[i].b)), 1e-7);
  }
});

test('country aggregation is quantity weighted with a neutral fallback', () => {
  close(S.aggregate([{ q: 1, d: 0.5 }, { q: 1, d: 1.5 }]), 1);
  close(S.aggregate([{ q: 3, d: 0.5 }, { q: 1, d: 1.5 }]), 0.75);
  close(S.aggregate([{ q: 0.0005, d: 0.2 }]), 1);
});

test('modifier size under the additive hypothesis', () => {
  close(S.modifierSize(0.5, -0.75, 'additive'), -0.125);
  close(S.realised(-0.125, -0.75, 'additive'), 0.5);
  close(S.realised(-0.5, -0.75, 'additive'), 0);
  close(S.realised(S.modifierSize(1.3, 0, 'multiplicative'), 0, 'multiplicative'), 1.3);
});
