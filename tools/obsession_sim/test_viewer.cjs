/* Node smoke checks for the offline viewer's real-map decoder and compatibility.
 * Run: node tools/obsession_sim/test_viewer.cjs
 * Canvas pixels and layout are additionally checked in a real browser.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../../docs/design/obsession/experiments/immunity_lock_viz.html'), 'utf8');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
scripts.forEach(script=>new vm.Script(script)); // Check the complete live simulator and playback script.
const script = scripts.find(script=>script.includes('let PB = null'));
const colors = script.slice(script.indexOf('const STAGES ='), script.indexOf('function colorOf'));
const playback = script.slice(script.indexOf('let PB = null'), script.indexOf('$("pb-file").addEventListener'));
const ctxBase = {
  createImageData: (w,h) => ({data:new Uint8ClampedArray(w*h*4)}),
  getImageData: (x,y,w,h) => ({data:new Uint8ClampedArray(w*h*4)}),
  measureText: () => ({width:0}),
};
// Any other 2D call (lines, text, dashes) is a harmless no-op in Node.
const ctx2d = new Proxy(ctxBase, {get:(obj,key)=>key in obj?obj[key]:()=>{}, set:()=>true});
function element() {
  const detach=node=>{if(node&&typeof node==='object'&&node.parentElement){const parent=node.parentElement;parent.children=parent.children.filter(child=>child!==node);node.parentElement=null;}};
  return {value:'',checked:false,clientWidth:600,style:{},children:[],parentElement:null,
    getContext:()=>ctx2d,replaceChildren(){this.children=[];},getBoundingClientRect:()=>({left:0,top:0,width:600,height:230}),
    setAttribute(k,v){this[k]=v;},
    append(...children){for(const child of children){detach(child);this.children.push(child);if(child&&typeof child==='object')child.parentElement=this;}},
    prepend(...children){for(const child of [...children].reverse()){detach(child);this.children.unshift(child);if(child&&typeof child==='object')child.parentElement=this;}},
    insertBefore(child,target){if(!this.children.includes(target))throw new Error('NotFoundError: reference is not a direct child');detach(child);this.children.splice(this.children.indexOf(target),0,child);child.parentElement=this;},
    events:{},addEventListener(name,fn){this.events[name]=fn;}};
}
const elements = new Proxy({}, {get:(obj,key)=>obj[key]||(obj[key]=element())});
elements['pb-mode'].value='intensity';elements['pb-borders'].checked=true;
const sandbox = {Uint8ClampedArray,Uint8Array,Int32Array,Set,Map,Math,Number,Array,String,Object,JSON,
  document:{createElement:element,createTextNode:s=>s,querySelector:s=>elements[s],getElementById:id=>elements[id],body:{}},
  getComputedStyle:()=>({fontFamily:'sans-serif'}),addEventListener:()=>{},
  $:id=>elements[id],fmt:n=>String(n),devicePixelRatio:1,
  lineChart:(...args)=>sandbox.lastChart=args,
  setTimeout:()=>1,clearTimeout:()=>{},};
vm.createContext(sandbox);vm.runInContext(colors+playback,sandbox);
const run = code => vm.runInContext(code,sandbox);
const old = {format:'obsession_sim.playback/1',nodes:2,xy:[[25,25],[75,75]],bounds:[0,0,100,100],
  frames:[{month:0,stages:'aa'},{month:12,stages:'ce'}],series:[{month:0,members:0,x_ge_45:0,served:1}],summary:{}};
sandbox.payload=old;run('pbLoad(payload)');
sandbox.playbackText='\uFEFF'+JSON.stringify(old);
assert.equal(run('pbParsePlaybackFile(playbackText).format'),'obsession_sim.playback/1');
sandbox.playbackText='<html><script>throw new Error("must not execute imported HTML")</script><script type="application/json" id="obsession-playback-data">'+JSON.stringify(old)+'</script></html>';
assert.equal(run('pbParsePlaybackFile(playbackText).frames.length'),2);
sandbox.playbackText=JSON.stringify({seeds:[],initial:[],parameters:{p:.004}});
assert.throws(()=>run('pbParsePlaybackFile(playbackText)'),/情景配置.*导入配置/);
sandbox.playbackText=JSON.stringify({selected:{},budget_frontier:[]});
assert.throws(()=>run('pbParsePlaybackFile(playbackText)'),/研究统计报告/);
sandbox.playbackText='<html><h1>No embedded replay</h1></html>';
assert.throws(()=>run('pbParsePlaybackFile(playbackText)'),/没有内嵌回放数据/);
assert.match(elements['pb-clock'].textContent,/第 0 月/);
assert.equal(run('pbRaster'),null);
assert.equal(run('pbMissingNodes.length'),2);
const real = structuredClone(old);
Object.assign(real,{start_year:1600,names:['lisbon','london'],group:[0,1],group_names:['POR','ENG'],
  attrs:{owner_tag:['POR','ENG'],area:['portugal','england'],region:['iberia','britain']},arrival:[0,12],first_positive:[0,3],
  threshold_arrival:{'20':[0,24],'45':[0,36],'70':[0,-1]},
  clock:{join:[0,12],decay_start:[240,252]},
  milestones:[{name:'England',fraction:.5,threshold:1,reached:1,locations:1,target_month:24,simulated_month:12,error_months:-12,tolerance_months:12,within_tolerance:true}],
  graph_meta:{geometry:{type:'index-raster/1',width:2,height:2,bounds:[0,0,100,100],rows:[[[0,1],[-1,1]],[[-1,1],[1,1]]]}}});
sandbox.payload=real;run('pbLoad(payload)');
assert.equal(run('pbRaster.length'),4);
assert.equal(run('pbMissingNodes.length'),0);
assert.equal(run('pbHit({x:153,y:153})'),0);
assert.equal(run('pbHit({x:447,y:447})'),1);
assert.equal(run('pbDate(12)'),'1601 年 1 月');
run('pbHover=1;pbDetails()');
assert.match(elements['pb-detail'].textContent,/ENG/);
assert.match(elements['pb-detail'].textContent,/britain/);
assert.match(elements['pb-detail'].textContent,/1601 年 1 月/);
assert.match(elements['pb-detail'].textContent,/首次非零 x>0：1600 年 4 月/);
assert.match(elements['pb-detail'].textContent,/首次 x≥20：1602 年 1 月/);
assert.match(elements['pb-detail'].textContent,/首次 x≥45：1603 年 1 月/);
assert.match(elements['pb-detail'].textContent,/首次 x≥70：本轮尚未达到/);
assert.equal(elements['pb-milestones'].hidden,false);
assert.equal(elements['pb-milestone-rows'].children.length,1);
run('pbZoom(2);pbZoom(.5)');assert.equal(run('pbView.zoom'),1);
run('pbSeekMonth(11)');assert.equal(run('pbIdx'),1);
const regrouped=structuredClone(real);
Object.assign(regrouped,{group_names:['area_a','area_b'],attrs:{...real.attrs,owner_tag:['POR','POR']}});
Object.assign(regrouped.graph_meta,{kind:'eu5_map',clock_group:'area',source_date:'1337.1.1',owner_source:'1337 setup own_* lists'});
regrouped.milestones[0].threshold='positive';
sandbox.payload=regrouped;run('pbLoad(payload)');
assert.equal(run('pbOwner(0)'),'POR');
assert.equal(run('pbOwnerIds[0] === pbOwnerIds[1]'),true); // Clock partitions do not become country borders.
run('pbHover=1;pbDetails()');
assert.match(elements['pb-detail'].textContent,/时钟组：area_b/);
assert.match(elements['pb-detail'].textContent,/国家：POR/);
assert.match(elements['pb-meta'].textContent,/来源年份：1337/);
assert.match(elements['pb-meta'].textContent,/归属来源：1337 setup/);
assert.match(elements['pb-meta'].textContent,/2 个地点，0 个无主地点/);
assert.match(elements['pb-milestone-rows'].children[0].children[1].textContent,/首次非零 \(x>0\)/);
regrouped.attrs.owner_tag[1]=null;sandbox.payload=regrouped;run('pbLoad(payload)');
assert.equal(run('pbOwner(1)'),'无主');
assert.equal(run('pbOwnerIds[1]'),-1);
assert.match(elements['pb-meta'].textContent,/1 个无主地点/);
const bad=structuredClone(real);bad.graph_meta.geometry.rows[0][0][1]=3;
sandbox.payload=bad;assert.throws(()=>run('pbLoad(payload)'),/地图游程无效/);
assert.equal(run('PB.names[0]'),'lisbon'); // Failed import leaves the current replay intact.
sandbox.payload={...old,frames:[{month:0,stages:'az'}]};assert.throws(()=>run('pbLoad(payload)'),/分档无效/);
assert.match(script,/DOMContentLoaded/);
assert.match(script,/obsession-playback-data/);
async function apiChecks(){
  sandbox.location={protocol:'http:'};
  const apiCode=script.slice(script.indexOf('const PB_RUN_PARAMS='),script.indexOf('/* ---------- local calculation controls ---------- */'));
  vm.runInContext(apiCode,sandbox);
  vm.runInContext(script.slice(script.indexOf('/* ---------- local calculation controls ---------- */'),script.indexOf('addEventListener("DOMContentLoaded"')),sandbox);
  await elements['pb-run-import'].events.change({target:{files:[{text:async()=>JSON.stringify({start_year:1337,seeds:[],initial:[],parameters:{p:.004,hold_T:600}})}],value:'scenario.json'}});
  assert.equal(elements['pb-run-p'].value,.004);assert.equal(elements['pb-run-hold_T'].value,600);
  assert.deepEqual(JSON.parse(elements['pb-run-scenario'].value).seeds,[]);
  const sourceScenario={start_year:1337,parameters:{p:.004,rho:.99,delta:.1,hold_T:600},seeds:[{name:'al_mukha',year:1450,value:.5}],sources:[{name:'al_mukha',start_year:1450,end_year:1470,amount:.5}]};
  await elements['pb-run-import'].events.change({target:{files:[{text:async()=>JSON.stringify(sourceScenario)}],value:'coffee.scenario.json'}});
  assert.equal(elements['pb-run-p'].value,.004);assert.equal(elements['pb-run-start_year'].value,1337);
  run('pbStartupHint()');assert.match(elements['pb-gain'].textContent,/有限源输入 \+0\.5/);assert.match(elements['pb-gain'].textContent,/0\.495 > δ=0\.1/);
  assert.doesNotMatch(elements['pb-gain'].textContent,/该种子无法向外启动/);
  run('pbRunWrite({scenario:{start_year:1400,parameters:{p:.006},seeds:[]}})');
  assert.equal(elements['pb-run-p'].value,.006);assert.equal(elements['pb-run-start_year'].value,1400);
  run('pbRunWrite({scenario:{parameters:{p:.004},seeds:[]},params:{p:.01}})');assert.equal(elements['pb-run-p'].value,.01);
  const config={nodes:2,graph_name:'real test map',presets:['baseline','growth_only'],
    defaults:{preset:'baseline',start_year:1600,seed_name:'lisbon',seed_value:25,
      params:{p:.02,rho:.99,delta:.1,hold_T:240,decay_factor:.98,habit_floor:0,budget:40000,max_months:2400,frames_every:12,series_every:12}},
    preset_defaults:{baseline:{doc:'test baseline',params:{p:.02,budget:null}},growth_only:{doc:'test growth',params:{p:.03,budget:40000}}},
    scenario:{seeds:[{name:'lisbon',month:0,value:25},{name:'london',month:120,value:20}],routes:[{from:'lisbon',to:'london',weight:.1}]}};
  const calls=[],responses=[];
  sandbox.fetch=async(url,opts)=>{
    calls.push({url,opts});const next=responses.shift();
    if(next instanceof Error)throw next;
    assert.ok(next,'Unexpected API request '+url);
    return {ok:next.ok!==false,status:next.status||200,json:async()=>next.body};
  };
  responses.push({body:config});await run('pbApiConnect()');
  assert.equal(run('pbApiConnected'),true);
  assert.equal(elements['pb-run-submit'].disabled,false);
  assert.match(elements['pb-run-status'].textContent,/real test map/);
  let request=run('pbRunRead()');assert.equal(request.params.budget,40000);
  run('pbRunWrite({params:{budget:null}})');assert.equal(elements['pb-run-budget'].value,'');assert.equal(run('pbRunRead().params.budget'),null);
  elements['pb-run-preset'].value='growth_only';elements['pb-run-preset'].events.change();assert.equal(run('pbRunRead().params.budget'),40000);
  elements['pb-run-preset'].value='baseline';elements['pb-run-preset'].events.change();assert.equal(run('pbRunRead().params.budget'),null);
  elements['pb-run-budget'].value='40000';
  assert.equal(request.scenario.seeds.length,2);assert.equal(request.scenario.routes[0].weight,.1);
  elements['pb-run-seed_name'].value='london';elements['pb-run-seed_value'].value='50';
  request=run('pbRunRead()');assert.equal(request.scenario.seeds[0].name,'london');assert.equal(request.scenario.seeds[0].value,50);
  assert.equal(request.scenario.seeds[1].month,120); // A basic seed edit preserves later seeds.
  elements['pb-run-scenario'].value=JSON.stringify({seeds:[{name:'lisbon',month:24,value:44}]});
  run('pbRunSyncSeedFromScenario()');assert.equal(elements['pb-run-seed_name'].value,'lisbon');assert.equal(elements['pb-run-seed_value'].value,44);
  const oldFrame=run('PB.frames[0].stages');
  responses.push({body:{id:'job-1'}},{body:{status:'running',month:120,max_months:2400}});
  await run('pbRunSubmit()');await new Promise(resolve=>setImmediate(resolve));
  assert.equal(run('pbRunJob'),'job-1');assert.equal(elements['pb-run-cancel'].disabled,false);
  assert.equal(elements['pb-run-progress'].value,.05);assert.equal(run('PB.frames[0].stages'),oldFrame);
  const posted=JSON.parse(calls.find(c=>c.url==='/api/run').opts.body);
  assert.equal(posted.seed_name,'lisbon');assert.equal(posted.scenario.seeds[0].month,24);
  responses.push({body:{status:'complete',month:2400,max_months:2400,payload:{...real,title:'fresh Python result',note:'Old scenario x=25',params:{p:0,rho:.99,delta:.1,hold_T:240,decay_factor:.98,habit_floor:0,max_months:120,budget:null,decay:'none'},inputs:{seeds:[[1,0,.5]]}}}});
  await run('pbRunPoll()');assert.equal(run('pbRunJob'),null);assert.equal(run('pbIdx'),0);
  assert.equal(run('PB.title'),'fresh Python result');assert.match(elements['pb-run-status'].textContent,/计算完成/);
  assert.match(elements['.sub'].textContent,/fresh Python result，当前显示本次参数重算结果/);
  assert.doesNotMatch(elements['.sub'].textContent,/预览|尚未完整计算/);
  assert.match(elements['pb-applied'].textContent,/p=0/);
  assert.match(elements['pb-applied'].textContent,/月预算=不限/);
  assert.match(elements['pb-applied'].textContent,/london：x=0.5/);
  assert.doesNotMatch(elements['pb-summary'].textContent,/Old scenario/);
  assert.match(elements['pb-scenario-note'].textContent,/原情景说明.*Old scenario x=25/);
  const hexPayload={...old,title:'hex preview',preview:true,names:['hex_0_0','hex_0_1'],graph_meta:{kind:'hex_grid',simulation_map:'hex',width:2,height:1},inputs:{map:'hex',seeds:[[0,0,25]]}};
  config.maps={real:{label:'真实 EU5',nodes:2,graph_name:'real test map',defaults:config.defaults,scenario:config.scenario},hex:{label:'六角网格',nodes:2,graph_name:'hex test map',defaults:{...config.defaults,seed_name:'hex_0_0',seed_value:25},scenario:{seeds:[{name:'hex_0_0',month:0,value:25}]}}};
  config.current_map='real';responses.push({body:config});await run('pbApiConnect()');
  elements['pb-run-p'].value='.04';elements['pb-run-start_year'].value='1777';elements['pb-run-seed_name'].value='lisbon';elements['pb-run-scenario'].value=JSON.stringify(config.scenario);
  responses.push({body:hexPayload});await run('pbSwitchMap("hex")');
  assert.equal(run('pbMapChoice'),'hex');assert.equal(run('PB.title'),'hex preview');
  assert.equal(elements['pb-run-p'].value,'.04');assert.equal(elements['pb-run-start_year'].value,'1777');
  assert.equal(elements['pb-run-seed_name'].value,'hex_0_0');assert.equal(run('pbRunRead().map'),'hex');
  elements['pb-run-seed_name'].value='hex_0_1';elements['pb-run-scenario'].value=JSON.stringify({seeds:[{name:'hex_0_1',month:7,value:12}],routes:[]});
  await run('pbSwitchMap("real")');assert.equal(run('PB.title'),'fresh Python result');assert.equal(elements['pb-run-seed_name'].value,'lisbon');
  assert.match(elements['.sub'].textContent,/fresh Python result/);
  assert.equal(elements['pb-run-p'].value,'.04');assert.equal(elements['pb-run-start_year'].value,'1777');
  const mapFetchCount=calls.length;await run('pbSwitchMap("hex")');assert.equal(calls.length,mapFetchCount);assert.equal(elements['pb-run-seed_name'].value,'hex_0_1');
  assert.ok(elements['.sub'].textContent.includes(run('PB.title')||'扩散模拟'));
  assert.equal(JSON.parse(elements['pb-run-scenario'].value).seeds[0].month,7);
  run('pbRunSetBusy(true)');await run('pbSwitchMap("real")');assert.equal(run('pbMapChoice'),'hex');assert.equal(elements['pb-run-map'].disabled,true);run('pbRunSetBusy(false)');
  await run('pbSwitchMap("real")');
  run('pbRunJob="job-2";pbRunSetBusy(true)');responses.push({body:{id:'job-2',status:'running'}});await run('pbRunCancel()');
  assert.equal(calls.at(-1).url,'/api/jobs/job-2/cancel');
  responses.push({body:{status:'cancelled'}});await run('pbRunPoll()');assert.equal(run('PB.title'),'fresh Python result');assert.match(elements['pb-run-status'].textContent,/已取消/);
  run('pbRunJob="job-3";pbRunSetBusy(true)');responses.push({body:{status:'failed',error:'bad scenario'}});await run('pbRunPoll()');
  assert.equal(run('PB.title'),'fresh Python result');assert.match(elements['pb-run-status'].textContent,/bad scenario/);
  elements['pb-run-scenario'].value='{';const count=calls.length;await run('pbRunSubmit()');assert.equal(calls.length,count);assert.equal(run('PB.title'),'fresh Python result');
  sandbox.location.protocol='file:';await run('pbApiConnect()');assert.equal(calls.length,count);assert.equal(elements['pb-api-help'].hidden,false);
  assert.equal(elements['pb-run-submit'].disabled,true);
  const main=elements['.wrap'],grid=elements['.grid'],charts=elements['.charts'],section=elements.playback,legacy=elements['legacy-experiments'];
  main.append(grid,charts,section,elements['legacy-reference'],legacy);section.append(elements['pb-controls'],elements['pb-sidebar']);
  elements['obsession-playback-data'].textContent=JSON.stringify({...real,title:'root embedded preview',preview:true});
  const globalEvents={};sandbox.addEventListener=(name,fn)=>globalEvents[name]=fn;sandbox.matchMedia=()=>({matches:false});
  vm.runInContext(script.slice(script.indexOf('addEventListener("DOMContentLoaded"'),script.indexOf('addEventListener("resize"')),sandbox);
  await globalEvents.DOMContentLoaded();
  assert.equal(run('PB.title'),'root embedded preview');
  assert.equal(main.children.indexOf(section)<main.children.indexOf(legacy),true);
  assert.equal(grid.parentElement,legacy);assert.equal(charts.parentElement,legacy);
  assert.doesNotMatch(elements['pb-msg'].textContent||'',/自动载入失败|NotFoundError/);
  run('pbArrangeLayout()'); // Repeated arrangement remains safe after .grid moved into details.
  // ---- workbench: history, comparison, scope, map actions, editors, sweep ----
  run('pbRuns=[];pbRunSeq=0;pbRefId=0;pbScope=null;pbSelected=-1');
  const runA=structuredClone(real);Object.assign(runA,{title:'A',params:{p:.02,rho:.99,delta:.1,hold_T:240,decay_factor:.98,habit_floor:0,budget:null,max_months:24,decay:'country_clock'},inputs:{map:'real',seeds:[[0,0,25]],scenario:{seeds:[{name:'lisbon',month:0,value:25}]}},series:[{month:0,members:1,x_ge_45:0,served:1},{month:12,members:2,x_ge_45:0,served:1}]});
  const runB=structuredClone(runA);Object.assign(runB,{title:'B',arrival:[0,24],params:{...runA.params,p:.03}});
  sandbox.payload=runA;run('pbLoad(payload);pbRunsAdd(PB,"run")');
  sandbox.payload=runB;run('pbLoad(payload);pbRunsAdd(PB,"run")');
  assert.equal(run('pbRuns.length'),2);assert.equal(run('pbRuns[1].diff'),'p 0.02→0.03');assert.equal(run('pbCurrentRun'),2);
  run('pbRunsAdd(PB,"run")');assert.equal(run('pbRuns.length'),2); // Re-adding the same payload does not duplicate.
  assert.equal(run('pbRefPayload()'),null);
  run('pbSetRef(1)');assert.equal(run('pbRefPayload().title'),'A');assert.equal(elements['pb-mode'].value,'compare');
  assert.equal(run('pbCompareColor(0)'),'#f3eedf'); // Same arrival month.
  assert.match(run('pbCompareColor(1)'),/^hsl\(12 /); // Later than the reference.
  assert.match(run('pbRefDetail(1)'),/晚 12 个月/);
  run('pbSetRef(1)');assert.equal(run('pbRefId'),0);assert.equal(elements['pb-mode'].value,'intensity');
  for(let i=0;i<9;i++){sandbox.payload={...structuredClone(runA),title:'R'+i};run('pbLoad(payload);pbRunsAdd(PB,"run")');}
  assert.equal(run('pbRuns.length'),8);
  // Selection and scope survive reloads of the same map and reset on a different geography.
  run('pbSelect(1)');assert.equal(run('pbSelected'),1);
  run('pbScopeSet("region","britain")');assert.equal(run('pbScope.count'),1);assert.equal(run('pbScope.mask[1]'),1);
  assert.equal(run('pbScopeArrival(PB,pbScope.mask,"1",.5)'),12);assert.equal(run('pbScopeArrival(PB,pbScope.mask,"20",.5)'),24);
  assert.deepEqual(Array.from(run('pbScopeCurve(PB,pbScope.mask).mem')),[0,100]);
  assert.deepEqual(JSON.parse(run('JSON.stringify(pbScopeSelector())')),{where:{region:['britain']}});
  sandbox.payload=runB;run('pbLoad(payload)');assert.equal(run('pbSelected'),1);assert.equal(run('pbScope&&pbScope.value'),'britain');
  sandbox.payload=hexPayload;run('pbLoad(payload)');assert.equal(run('pbSelected'),-1);assert.equal(run('pbScope'),null);
  sandbox.payload=runB;run('pbLoad(payload);pbMapChoice="real"');
  elements['pb-run-scenario'].value=JSON.stringify({seeds:[{name:'lisbon',month:0,value:25}],milestones:[]});elements['pb-run-seed_value'].value='30';
  run('pbSelected=1;pbIdx=1;pbSeedFromSelection(true)');
  let sc=JSON.parse(elements['pb-run-scenario'].value);assert.deepEqual(sc.seeds[1],{name:'london',month:12,value:30});
  run('pbSeedFromSelection(false)');sc=JSON.parse(elements['pb-run-scenario'].value);assert.equal(sc.seeds[0].name,'london');assert.equal(elements['pb-run-seed_name'].value,'london');
  run('pbMilestoneFromSelection(false);pbScopeSet("area","england");pbMilestoneFromSelection(true)');
  sc=JSON.parse(elements['pb-run-scenario'].value);
  assert.deepEqual(sc.milestones[0],{name:'london 成员',names:['london'],threshold:1,target_year:1601,tolerance_months:120});
  assert.deepEqual(sc.milestones[1].where,{area:['england']});assert.equal(sc.milestones[1].fraction,.5);
  run('pbScenarioRender()');assert.equal(elements['pb-ms-rows'].children.length,2);assert.equal(elements['pb-seed-rows'].children.length,2);
  elements['pb-run-scenario'].value='{';run('pbScenarioMutate(s=>{s.x=1})');assert.equal(elements['pb-run-scenario'].value,'{'); // Broken JSON is never overwritten.
  // Form-vs-replay marks and the startup check.
  elements['pb-run-scenario'].value=JSON.stringify(runB.inputs.scenario);
  run('pbRunWrite({start_year:1600,seed_name:"lisbon",seed_value:25,params:PB.params})');assert.equal(elements['pb-dirty'].hidden,true);
  elements['pb-run-p'].value='0.05';run('pbDirtyMark()');assert.equal(elements['pb-dirty'].hidden,false);assert.match(elements['pb-dirty'].textContent,/p/);
  elements['pb-run-p'].value='0.02';elements['pb-run-delta'].value='0.1';elements['pb-run-scenario'].value=JSON.stringify({seeds:[{name:'lisbon',month:0,value:.5}]});
  run('pbStartupHint()');assert.match(elements['pb-gain'].textContent,/无法向外启动/);
  elements['pb-run-scenario'].value=JSON.stringify({seeds:[{name:'lisbon',month:0,value:25}]});run('pbStartupHint()');assert.match(elements['pb-gain'].textContent,/可以启动/);
  elements['pb-run-scenario'].value=JSON.stringify({seeds:[],initial:[{names:['lisbon'],value:30}],transport:{routes:[]}});
  assert.equal(run('pbRunRead().scenario.seeds.length'),0);run('pbStartupHint()');assert.match(elements['pb-gain'].textContent,/没有手写种子/);
  // Sweep value handling, scoring and rendering of partial results.
  elements['pb-sweep-param'].value='hold_T';elements['pb-sweep-from'].value='100';elements['pb-sweep-to'].value='300';elements['pb-sweep-n'].value='3';elements['pb-sweep-scale'].value='lin';
  run('pbSweepGenerate()');assert.equal(elements['pb-sweep-values'].value,'100, 200, 300');
  elements['pb-sweep-param'].value='budget';elements['pb-sweep-values'].value='20000, 不限';assert.deepEqual(JSON.parse(run('JSON.stringify(pbSweepParse().values)')),[20000,null]);
  elements['pb-sweep-values'].value='abc';assert.throws(()=>run('pbSweepParse()'),/无法解析/);
  const ms=(err,tol)=>({error_months:err,tolerance_months:tol,within_tolerance:err!=null&&Math.abs(err)<=tol});
  assert.equal(run('pbSweepScore')({milestones:[ms(-60,120)]}),.5);assert.ok(run('pbSweepScore')({milestones:[ms(null,120)]})>=1000);
  sandbox.sweepData={param:'p',values:[.01,.02],results:[{value:.01,summary:{ever_member:3},milestones:[ms(-400,120)],series:[[0,1,0],[12,3,0]]},{value:.02,summary:{ever_member:9},milestones:[ms(30,120)],series:[[0,1,0],[12,9,1]]}],milestones:['m'],start_year:1450,map:'real',status:'complete',base:'x'};
  run('pbSweepData=sweepData;pbSweepRender()');
  assert.equal(elements['pb-sweep-out'].hidden,false);assert.equal(elements['pb-sweep-rows'].children.length,2);
  assert.equal(elements['pb-sweep-rows'].children[1].className,'best');assert.equal(elements['pb-sweep-rows'].children[0].className||'','');
  run('pbTab("sweep")');assert.equal(elements['pb-panel-sweep'].hidden,false);assert.equal(elements['pb-panel-params'].hidden,true);
  console.log('Viewer smoke checks passed: JS syntax, old/real maps, historical thresholds, owner/clock separation, milestones, zoom/seek, config round-trip and seed precedence, Python API run/progress/completion/cancel/failure, offline replay preservation, run history/reference comparison, selection/scope curves, map seed and milestone actions, form-vs-replay marks, startup check, sweep parsing/scoring/rendering.');
}
apiChecks().then(()=>{
  if(!process.argv.includes('--first-batch'))return;
  sandbox.FileReader=class {readAsText(file){this.result=file.textValue;this.onload();}};
  vm.runInContext(script.slice(script.indexOf('$("pb-file").addEventListener'),script.indexOf('$("pb-play").addEventListener')),sandbox);
  for(const good of ['coffee','tea','tobacco']){
    const dir=path.join(__dirname,'../../tmp/obsession_real/first_batch');
    const jsonText=fs.readFileSync(path.join(dir,good+'.playback.json'),'utf8');
    elements['pb-file'].events.change({target:{files:[{textValue:jsonText}]}});
    assert.doesNotMatch(elements['pb-msg'].textContent,/载入失败/);
    assert.equal(run('PB.nodes'),20893);
    assert.equal(run('PB.frames.at(-1).month'),5555);
    const jsonSummary=run('JSON.stringify(PB.summary)');
    elements['pb-file'].events.change({target:{files:[{textValue:fs.readFileSync(path.join(dir,good+'.html'),'utf8')}]}});
    assert.doesNotMatch(elements['pb-msg'].textContent,/载入失败/);
    assert.equal(run('JSON.stringify(PB.summary)'),jsonSummary);
    console.log(good+': actual JSON and HTML imported through the file picker handler.');
  }
}).catch(err=>{console.error(err);process.exitCode=1;});
