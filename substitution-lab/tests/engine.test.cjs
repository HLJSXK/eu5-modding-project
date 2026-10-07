const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const E = require('../engine.js');
const context = { window:{} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../data.js'),'utf8'),context);
const data = context.window.SOL_DATA;
const close = (a,b,tolerance=1e-8) => assert.ok(Math.abs(a-b)<tolerance,`${a} != ${b}`);
const pair = [{id:'g',n:2,members:['a','b']}];

test('all strict boundaries and their adjacent prices',()=>{
  for(const [r,at,below,above] of [[2.3,.5,.5,.25],[1.7,.75,.75,.5],[1.3,1,1,.75],[.85,1,1.25,1],[.65,1.25,1.5,1.25],[.4,1.5,2,1.5]]){
    assert.equal(E.tier(r).weight,at);assert.equal(E.tier(r-1e-10).weight,below);assert.equal(E.tier(r+1e-10).weight,above);
  }
});
test('pinned historical data agrees with audit counts and overlapping final blocks',()=>{
  assert.equal(data.revision,'9670e1414d8e2ce5c692672adc588f485baf167c');
  assert.equal(data.groups.length,20);const member=E.memberships(data.groups);
  assert.equal(Object.keys(member).length,56);assert.equal(data.groups.flatMap(g=>g.members).length,67);
  assert.equal(Object.values(member).filter(m=>m.length===2).length,11);
  assert.equal((data.sources['history-overlap'].text.match(/divide = 2/g)||[]).length,11);
  for(const g of data.groups)assert.equal(g.n,g.members.length);
});
test('current core changes only victuals/camels, PP missing interface stays explicit',()=>{
  const old=Object.keys(E.memberships(data.groups)),current=Object.keys(E.memberships(data.currentGroups));
  assert.equal(current.length,56);assert.ok(old.includes('victuals'));assert.ok(!old.includes('camels'));
  assert.ok(!current.includes('victuals'));assert.ok(current.includes('camels'));
  assert.equal(data.interfaces.victuals,false);for(const i of current)assert.equal(data.interfaces[i],true);
});
test('neutral prices with unequal baselines do not redistribute, including overlaps',()=>{
  for(const groups of [data.groups,data.currentGroups]){
    const v=Object.fromEntries(Object.keys(E.memberships(groups)).map((i,n)=>[i,{b:(n+1)*7,ratio:1,supported:data.interfaces[i],supply:n%7!==0}]));
    for(const mode of ['A','B'])for(const [i,o] of Object.entries(E.substitute(groups,v,mode).goods)){
      close(o.response,1);close(o.target,v[i].supply?v[i].b:0);
    }
  }
});
test('non-price preferences cancel correctly in A neutral response',()=>{
  const v={a:{b:90,ratio:1,v:.1},b:{b:10,ratio:1,v:2}};
  const r=E.substitute(pair,v);close(r.goods.a.response,1);close(r.goods.b.response,1);
});
test('A restores historical shape while B preserves the group budget',()=>{
  const v={a:{b:90,ratio:2},b:{b:10,ratio:1}};
  const a=E.substitute(pair,v),b=E.substitute(pair,v,'B');
  close(a.goods.a.target,60);close(a.goods.b.target,40/3);close(a.goods.a.response,2/3);
  close(b.goods.a.target,900/11);close(b.goods.b.target,200/11);
  close(E.sum(Object.values(b.goods).map(o=>o.target)),100);
});
test('A averages both overlapping multipliers rather than choosing a main group',()=>{
  const g=[{id:'x',n:2,members:['a','b']},{id:'y',n:2,members:['a','c']}];
  const r=E.substitute(g,{a:{b:90,ratio:2},b:{b:10,ratio:1},c:{b:10,ratio:.3}});
  close(r.goods.a.ht,(2/3+.4)/2);close(r.goods.a.h1,1);close(r.goods.a.target,48);
});
test('B budget conservation across the actual 20-group network for many price/supply combinations',()=>{
  const goods=Object.keys(E.memberships(data.currentGroups));
  for(let scenario=0;scenario<30;scenario++){
    const ratios=[.3,.5,.7,1,1.5,2,2.5];
    const v=Object.fromEntries(goods.map((i,n)=>[i,{b:((n*13+scenario*7)%101)/3,ratio:ratios[(n+scenario)%7],supply:(n+scenario)%9!==0,supported:(n+scenario)%11!==0}]));
    const r=E.substitute(data.currentGroups,v,'B');
    close(E.sum(Object.values(r.goods).map(o=>o.target)),E.sum(Object.values(r.goods).map(o=>o.baseline)));
    for(const [i,o] of Object.entries(r.goods)){
      assert.ok(Number.isFinite(o.target));assert.ok(o.target>=0);
      if(!v[i].supported&&v[i].supply)close(o.target,v[i].b);
      if(!v[i].supply)assert.equal(o.target,0);
    }
  }
});
test('unsupported, no supply, empty and single-active groups cannot acquire phantom demand',()=>{
  for(const mode of ['A','B']){
    for(const v of [
      {a:{b:90,ratio:2,supported:false},b:{b:10,ratio:.3,supply:false}},
      {a:{b:90,ratio:2},b:{b:0,ratio:.3}},
      {a:{b:0,ratio:2},b:{b:0,ratio:.3}}
    ]){
      const r=E.substitute(pair,v,mode);
      for(const [i,o] of Object.entries(r.goods)){close(o.response,1);close(o.target,v[i].supply===false?0:v[i].b);}
    }
  }
});
test('same price tier for every good cancels in both modes',()=>{
  for(const mode of ['A','B'])for(const ratio of [.3,.5,.7,1.5,2,2.5]){
    const v=Object.fromEntries(Object.keys(E.memberships(data.currentGroups)).map((i,n)=>[i,{b:n+1,ratio}]));
    for(const o of Object.values(E.substitute(data.currentGroups,v,mode).goods))close(o.response,1);
  }
});
test('market price ratio changes response but never the neutral reference baseline',()=>{
  const populations=[{nobles:10,clergy:0,burghers:0,laborers:0,peasants:0,soldiers:0,tribesmen:0}];
  const neutral=Object.fromEntries(Object.keys(E.memberships(data.currentGroups)).map(i=>[i,{ratio:1,supply:true,supported:true}]));
  const expensive=Object.fromEntries(Object.keys(neutral).map(i=>[i,{...neutral[i],ratio:i==='wheat'?2:1}]));
  const a=E.nationalBasket(data.currentGroups,data.units,populations,neutral,'A','neutral');
  const b=E.nationalBasket(data.currentGroups,data.units,populations,expensive,'A','neutral');
  const wa=a.goods.find(g=>g.good==='wheat'),wb=b.goods.find(g=>g.good==='wheat');
  close(wa.baseline,wb.baseline);assert.notEqual(wa.m,wb.m);
});
test('reference-price aggregation is quantity-equivalent and loses local ideal response',()=>{
  const r=E.aggregate([{b:1,d:.5},{b:2,d:1.5}]);close(r.m,7/6);close(r.baseline*r.m,r.target);
  close(r.size,1/6);assert.notEqual(r.m,.5);assert.notEqual(r.m,1.5);
});
test('epsilon is a branch, never a clamp on a positive denominator',()=>{
  assert.equal(E.aggregate([{b:.0005,d:1}]).m,1);assert.equal(E.aggregate([{b:0,d:2}]).m,1);
  assert.equal(E.aggregate([{b:.001,d:.5}]).fallback,true);
  close(E.aggregate([{b:.0011,d:.5}]).m,.5);
});
test('external offset size conversion expresses either assumed model',()=>{
  close(E.modifierSize(.5,-.75,'additive'),-.125);
  close(E.modifierSize(.5,-.75,'multiplicative'),-.5);
  for(const e of [-.9,-.75,0,.25,1])for(const m of [0,.5,1,1.5,3]){
    const x=E.modifierSize(m,e,'additive');close((1+e+x)/(1+e),m);
  }
});
test('historical Engel parameters produce finite piecewise curves and expected basic sample',()=>{
  const c=data.curves.nobles.basic_clothing;
  close(E.historicalBase(c,2),2*.03531/.18);
  close(E.piecewise(c.share,3),.03531-.02223);
  assert.equal(E.historicalBase(data.curves.clergy.weapons,10),1);
  for(const s of Object.keys(data.curves))for(const curve of Object.values(data.curves[s]))for(const y of [0,3,8,25,60])assert.ok(Number.isFinite(E.historicalBase(curve,y)));
});
test('end-to-end calibrated basket keeps neutral goods and counts population exactly once',()=>{
  const populations=[{nobles:8,clergy:2,burghers:12,laborers:25,peasants:50,soldiers:2,tribesmen:1},{nobles:2,clergy:1,burghers:3,laborers:30,peasants:60,soldiers:2,tribesmen:2}];
  const values=Object.fromEntries(Object.keys(E.memberships(data.currentGroups)).map(i=>[i,{ratio:1,b:50,supply:true,supported:true}]));
  for(const mode of ['A','B']){
    const basket=E.nationalBasket(data.currentGroups,data.units,populations,values,mode,'inverse');
    assert.equal(basket.goods.length,56);assert.equal(basket.records.length,56*7*2);
    for(const g of basket.goods)close(g.m,1);
    const horses=basket.goods.find(g=>g.good==='horses');
  close(horses.baseline,(8+2)*data.units.horses.nobles*data.units.horses.price);
  }
  values.wheat.ratio=2;values.rice.ratio=.5;
  const a=E.nationalBasket(data.currentGroups,data.units,populations,values,'A','inverse');
  const b=E.nationalBasket(data.currentGroups,data.units,populations,values,'B','inverse');
  close(b.baseline,b.target);
  close(a.realized,a.target);assert.ok(a.goods.some(g=>Math.abs(g.m-1)>1e-8));
  for(const g of a.goods)if(!g.fallback)close(g.local[0].error+g.local[1].error,0);
});
