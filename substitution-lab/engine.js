(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SOLEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function tier(r) {
    if (r > 2.30) return { weight:0.25, label:'严重昂贵', key:'severe' };
    if (r > 1.70) return { weight:0.50, label:'明显昂贵', key:'moderate' };
    if (r > 1.30) return { weight:0.75, label:'轻度昂贵', key:'mild' };
    if (r < 0.40) return { weight:2.00, label:'非常便宜', key:'vcheap' };
    if (r < 0.65) return { weight:1.50, label:'明显便宜', key:'cheap' };
    if (r < 0.85) return { weight:1.25, label:'较为便宜', key:'affordable' };
    return { weight:1, label:'中性', key:'neutral' };
  }
  const sum = a => a.reduce((s,x)=>s+x,0);
  function memberships(groups) {
    const result = {};
    for (const g of groups) for (const i of g.members) (result[i] ||= []).push(g.id);
    return result;
  }
  // Values B are monetary baselines before any location SOL factor.
  function substitute(groups, values, mode = 'A') {
    const member = memberships(groups), output = {}, details = {};
    const baseline = i => values[i]?.supply === false ? 0 : values[i]?.b || 0;
    for (const i of Object.keys(member)) output[i] = { baseline:baseline(i), target:0, response:1, ht:0, h1:0 };
    const eligible = i => values[i] && values[i].b > 0 && values[i].supply !== false && values[i].supported !== false;
    for (const g of groups) {
      const active = g.members.filter(eligible);
      const w = i => tier(values[i].ratio ?? 1).weight * (values[i].v ?? 1);
      const v = i => values[i].v ?? 1;
      const totalW = sum(active.map(w)), totalV = sum(active.map(v));
      const budget = sum(active.map(i=>baseline(i) / member[i].length));
      const weightedBudget = sum(active.map(i=>baseline(i) / member[i].length * tier(values[i].ratio ?? 1).weight));
      details[g.id] = {};
      for (const i of g.members) {
        const valid = active.includes(i) && active.length >= 2 && totalW > 0 && totalV > 0;
        const f1 = eligible(i) && totalV > 0 ? g.n * v(i) / totalV : 0;
        const ft = valid ? g.n * w(i) / totalW : f1;
        output[i].ht += ft / member[i].length;
        output[i].h1 += f1 / member[i].length;
        const b = baseline(i) / member[i].length;
        const bt = eligible(i) && active.length >= 2 && weightedBudget > 0 ? budget * b * tier(values[i].ratio ?? 1).weight / weightedBudget : b;
        if (mode === 'B') output[i].target += bt;
        details[g.id][i] = { ft, f1, b, bt, active:eligible(i), members:active.length };
      }
    }
    for (const [i,o] of Object.entries(output)) {
      if (mode === 'A') { o.response = eligible(i) && o.h1 > 0 ? o.ht / o.h1 : 1; o.target = o.baseline * o.response; }
      else o.response = o.baseline > 0 ? o.target / o.baseline : 1;
    }
    return { goods:output, details };
  }
  function aggregate(rows, epsilon = 0.001) {
    const baseline = sum(rows.map(r=>r.b)), target = sum(rows.map(r=>r.b*r.d));
    const m = baseline > epsilon ? target/baseline : 1;
    return { baseline, target, m, size:m-1, fallback:baseline <= epsilon };
  }
  function piecewise(spec, y) { return spec.base + sum(spec.changes.filter(([threshold])=>y>=threshold).map(([,delta])=>delta)); }
  function historicalBase(curve, y) {
    if (!curve) return 0;
    if (curve.constantBase != null) return curve.constantBase;
    if (curve.price === 0) return 1;
    return y * piecewise(curve.share,y) / curve.price + piecewise(curve.offset,y);
  }
  function modifierSize(m, external, semantics) { return semantics === 'additive' ? (1+external)*(m-1) : m-1; }
  function nationalBasket(groups, units, populations, values, mode = 'A', rule = 'neutral', epsilon = 0.001) {
    const goods=Object.keys(memberships(groups)),records=[];
    populations.forEach((population,market)=>{
      for(const [stratum,people] of Object.entries(population)){
        const local={};
        for(const i of goods){
          const v=values[i] || {},ratioA=v.ratio ?? 1;
          const ratio=market===0 || rule==='same'?ratioA:rule==='inverse'?1/ratioA:1;
          // The substitution baseline is neutral: market price belongs only in the
          // price ratio that produces D. The current SOL spending cache has a
          // separate high-price cap and must not become the baseline weight here.
          const unit=units[i]?.[stratum] || 0,price=units[i]?.price || 0;
          const q=people*unit*(v.supply===false?0:1);
          local[i]={b:q*price,ratio,supply:v.supply!==false,supported:v.supported!==false,v:1};
        }
        const response=substitute(groups,local,mode);
        for(const i of goods){
          const o=response.goods[i],ratio=local[i].ratio;
          records.push({market,stratum,good:i,population:people,unit:units[i]?.[stratum] || 0,ratio,referencePrice:units[i]?.price || 0,baseline:o.baseline,target:o.target,d:o.response});
        }
      }
    });
    const result=goods.map(good=>{
      const rows=records.filter(r=>r.good===good),total=aggregate(rows.map(r=>({b:r.baseline,d:r.d})),epsilon);
      const local=populations.map((_,market)=>{const subset=rows.filter(r=>r.market===market),baseline=sum(subset.map(r=>r.baseline)),target=sum(subset.map(r=>r.target));return {baseline,target,d:baseline>0?target/baseline:1,error:baseline*total.m-target};});
      return {good,...total,local};
    });
    return {goods:result,records,baseline:sum(result.map(g=>g.baseline)),target:sum(result.map(g=>g.target)),realized:sum(result.map(g=>g.baseline*g.m)),mode,rule,epsilon};
  }
  return { tier, memberships, substitute, aggregate, piecewise, historicalBase, modifierSize, nationalBasket, sum };
});
