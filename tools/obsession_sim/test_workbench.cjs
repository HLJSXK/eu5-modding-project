/* Exercise the real acceptance UI, including DOM-id and seed selection errors. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../../docs/design/obsession/experiments/structural_workbench.html'),'utf8');
assert.equal((html.match(/<\/body>/g)||[]).length,1,'standalone report injection needs one explicit body end');
function element(tag='div'){
 return {tag,children:[],dataset:{},style:{},value:'',textContent:'',hidden:false,disabled:false,
  append(...xs){this.children.push(...xs);if(this.tag==='select'&&!this.value&&xs[0])this.value=xs[0].value;},
  replaceChildren(...xs){this.children=[];if(this.tag==='select')this.value='';this.append(...xs);},
  querySelectorAll(tag){return this.children.flatMap(c=>typeof c==='object'?[...(c.tag===tag?[c]:[]),...c.querySelectorAll(tag)]:[]);},
  click(){if(this.onclick)this.onclick();}};
}
const elements={};for(const m of html.matchAll(/<(\w+)\b[^>]*\bid="([^"]+)"/g))elements[m[2]]=element(m[1]);
elements.good.value='coffee';
const box={document:{getElementById:id=>elements[id]||null,createElement:element},
 Option:function(text,value){return {...element('option'),textContent:text,value};},
 addEventListener:()=>{},setTimeout:()=>{},URL:{},Blob:class{},console};
vm.createContext(box);
for(const m of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g))vm.runInContext(m[1],box);
assert.equal(elements.cells.children.length,4);
const run=code=>vm.runInContext(code,box);
const sample={mode:'S',world_kind:'R',seed:0,params:{p:.006,lambda_ownership:.1},p_K:.5,peak_U:123,violation_count:0,
 country_labels:['MAM'],K:[{id:'K1',level:'B',status:'fail',cases:[{country:0,t0:1200,t1:1300,status:'fail'}]}],
 milestones:[{good:'coffee',name:'Region',where:{region:'balkan_region'},threshold:20,split:'fit',target_year:1500,simulated_year:1510,error_months:120,
              tolerance_months:180,within_tolerance:true,world_evidence:{counts:{'W-A':1,'W-B':2,'W-C':0}}}],events:[]};
box.data=sample;run('render(data)');
assert.equal(elements.krows.children.length,1);assert.equal(elements.milestones.children.length,1);
box.data={...sample,zone_sizes:{coffee:0,tea:2,tobacco:1},zone_values_constant:{coffee:true,tea:true,tobacco:true},
 zone_rejected_inputs:{coffee:0,tea:5,tobacco:1},zone_adjacency_arrivals:{coffee:0,tea:0,tobacco:0},
 clocks:{coffee:{history:[{country:0,first_touch_month:10,national_month:20,deadline:260}]}},
 waves:{coffee:[{reason:'origin'}]},fit_p_order_upper:.75,triggered_K:3};run('render(data)');
assert.equal(elements.mechanics.children[0].children.length,4);
assert.match(elements.mechanics.children[1].textContent,/75.0%.*3/);
assert.match(elements.mechanics.children[2].children[1].children[1].children[0].textContent,/MAM/);
assert.match(elements.milestones.children[0].children.at(-1).textContent,/1 \/ 2 \/ 0/);
assert.match(elements.milestones.children[0].children[0].children[0].textContent,/balkan_region/);
assert.equal(elements.milestones.children[0].children[2].textContent,'x≥20');
elements.krows.children[0].children[0].children[0].click();
assert.equal(elements['case-details'].hidden,false);
assert.match(elements.cases.children[0].children[1].children[0].textContent,/MAM/);
box.data={cells:{'S×R':{run_count:2,runs:[sample,{...sample,seed:1,p_K:.75}]}},params:sample.params,
 gates:{L1:{status:'未达',failures:['fixture'],missing:[]}}};
run('render(data)');assert.equal(elements['detail-seed'].children.length,2);
elements['detail-seed'].value='1';elements['detail-seed'].onchange();
assert.match(elements.summary.textContent,/seed 1/);assert.match(elements.summary.textContent,/75.0%/);
assert.equal(elements['case-details'].hidden,true);
const previous=run('report');
box.data={format:'obsession.quick-check/1',passed:true,cached:true,elapsed_seconds:.2,rows:[{world:'R',mode:'S',disabled_rules:[]}],transitions:[],limitation:'工程检查，不判定验收'};
run('render(data)');
assert.equal(run('report'),previous,'quick probes must preserve the last acceptance report');
assert.match(elements['check-summary'].textContent,/快速检查通过.*复用缓存/);
assert.match(elements['check-details'].children[0].textContent,/不判定验收/);
box.data={format:'obsession.cache-screen/1',decision:'early_reject',cells:{},coverage:{'S×R':{completed:30,required:30}},elapsed_seconds:1,
 gates:{L1:{status:'未达',failures:['S×R: p_order=.54 < .60'],missing:['H×R']}},limitation:'只读缓存'};
run('render(data)');
assert.match(elements['check-summary'].textContent,/缓存已证实验收差项/);
assert.match(elements.gates.children[0].children[0].textContent,/未达/);
run('busy(true)');for(const id of ['quick','screen','run','matrix'])assert.equal(elements[id].disabled,true);
run('busy(false)');
assert.throws(()=>run('render({unexpected:true})'),/不是痴迷传播验收报告/);
console.log('Acceptance workbench checks passed: actual DOM ids, single/matrix render, K details, W ancestry and seed switching.');

box.data={K:[],milestones:[{split:'holdout'}]};assert.throws(()=>run('render(data)'),/留出/);
run('fillParams({p:.01,rho:.99,hold_T:999,road_scale:3,affinity_strength:0})');assert.equal(elements.params.children.length,2);
run('busy(false)');assert.equal(elements.matrix.disabled,true);

box.data={cells:{'S×O':{runs:[{...sample,world_kind:'O'}],run_count:1}},
 worlds:[{id:'fixture',label:'SOL 观察者',dates:['1338.4.1','1840.4.1']}],frozen_hash:'fixture-hash'};
run('render(data)');
assert.match(elements.milestones.children[0].children[0].textContent,/非史实.*不比较历史年份/);
assert.match(elements.worlds.children[0].textContent,/SOL 观察者/);
assert.match(elements.frozen.textContent,/冻结哈希/);
assert.doesNotMatch(elements.frozen.textContent,/已变化/);

const contrastMetrics={fit_within_2tol:.2,fit_p_order:.6,p_K:.5,violation_count:0,peak_round_delay_months:3,events_abandoned_budget:2};
box.data={...box.data,baseline_10:{metrics:contrastMetrics},ablations:{contact:{metrics:contrastMetrics}},
 budget_sensitivity:{eligible_milestones:25,moved_fraction:.4,blocks_L2:true,double_budget:{metrics:contrastMetrics}}};
run('render(data)');
assert.equal(elements.ablations.children.length,3);
assert.equal(elements.ablations.children[1].children[0].textContent,'关闭商人常驻');
assert.match(elements['budget-summary'].textContent,/40.0%.*阻止 L2 宣称/);
box.data={...box.data,budget_sensitivity:undefined,ablations:undefined,baseline_10:undefined};
run('render(data)');
assert.equal(elements.ablations.children.length,0);
assert.match(elements['budget-summary'].textContent,/尚未完成/);

box.data={...box.data,world_cells:{
 'S×O · SOL 观察者':{run_count:30,runs:[{...sample,world_kind:'O'}],p_K:.6},
 'S×O · 原版观察者':{run_count:30,runs:[{...sample,world_kind:'O'}],p_K:.4}}};
run('render(data)');
assert.equal(elements['observer-cell'].children.length,2);
elements['observer-cell'].value='原版观察者';elements['observer-cell'].onchange();
const observerCell=elements.cells.children[0].children[2];
assert.match(observerCell.children[0].textContent,/原版观察者/);
assert.equal(observerCell.querySelectorAll('b')[0].textContent,'40.0%');

box.atob=atob;box.Blob=Blob;box.Response=Response;box.DecompressionStream=DecompressionStream;
box.packed=require('node:zlib').gzipSync(JSON.stringify({fit_only:true,marker:'离线数据完整'})).toString('base64');
run('unpackReport(packed)').then(data=>{
 assert.equal(data.fit_only,true);assert.equal(data.marker,'离线数据完整');
}).catch(error=>{console.error(error);process.exitCode=1;});
