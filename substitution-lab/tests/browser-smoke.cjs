// Optional real-browser smoke test. Node >=22, existing Chromium CDP endpoint.
// Example: $env:CDP_URL='http://127.0.0.1:9227'; node tests/browser-smoke.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const cdp = process.env.CDP_URL || 'http://127.0.0.1:9227';
const site = process.env.SOL_TEST_URL || 'http://127.0.0.1:4173';
const shots = process.env.SOL_SCREENSHOTS;
const pause = ms => new Promise(r=>setTimeout(r,ms));
async function main(){
  const target=await fetch(cdp+'/json/new?'+encodeURIComponent('about:blank'),{method:'PUT'}).then(r=>r.json());
  const ws=new WebSocket(target.webSocketDebuggerUrl),pending=new Map(),errors=[];let id=0;
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(m.error.message)):p.resolve(m.result);}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text+' '+JSON.stringify(m.params.exceptionDetails.exception));});
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});ws.send(JSON.stringify({id:key,method,params}));});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  async function screenshot(name){if(!shots)return;fs.mkdirSync(shots,{recursive:true});const result=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(shots,name+'.png'),Buffer.from(result.data,'base64'));}
  try{
    await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await send('Page.navigate',{url:site});
    for(let n=0;n<50;n++){await pause(100);if(await evaluate("Boolean(window.SOL_CHECK_RESULTS)"))break;}
    assert.equal(await evaluate('document.querySelectorAll(".group-card").length'),20);
    assert.equal(await evaluate('window.SOL_CHECK_RESULTS.every(r=>r.passed)'),true);
    assert.equal(await evaluate('window.SOL_BASKET_SNAPSHOT.goods.every(g=>Math.abs(g.m-1)<1e-8)'),true);
    await evaluate("document.documentElement.style.scrollBehavior='auto'");
    await screenshot('desktop-overview');
    await evaluate(`document.querySelector('[data-boundary="2.3"]').click()`);
    assert.match(await evaluate('document.getElementById("price-result").textContent'),/0\.5/);
    await evaluate(`document.querySelector('[data-preset="unequal"]').click()`);
    assert.match(await evaluate('document.getElementById("lab-title").textContent'),/武器/);
    assert.match(await evaluate('document.querySelector("[data-good=weaponry] [data-output=target]").textContent'),/60/);
    await evaluate(`document.querySelector('[data-mode="B"]').click()`);
    assert.match(await evaluate('document.querySelector("[data-good=weaponry] [data-output=target]").textContent'),/81\.81818/);
    await evaluate(`document.getElementById('groups').scrollIntoView({behavior:'instant'})`);await pause(100);await screenshot('desktop-groups');
    await evaluate(`document.querySelector('.lab-panel').scrollIntoView({block:'start',behavior:'instant'})`);await pause(100);await screenshot('desktop-lab');
    await evaluate(`document.getElementById('catalog').value='pp';document.getElementById('catalog').dispatchEvent(new Event('change'));document.querySelector('[data-group=luxury_food]').click()`);
    assert.equal(await evaluate('document.querySelector("[data-good=victuals] [data-field=supported]").checked'),false);
    await evaluate(`document.querySelector('[data-preset=overlap]').click();document.getElementById('overlap-good').value='wine';document.getElementById('overlap-good').dispatchEvent(new Event('change'))`);
    assert.match(await evaluate('document.getElementById("overlap-breakdown").textContent'),/嗜好饮料/);
    assert.match(await evaluate('document.getElementById("overlap-breakdown").textContent'),/奢侈饮品/);
    await evaluate(`document.getElementById('group-search').value='水银';document.getElementById('group-search').dispatchEvent(new Event('input'))`);
    assert.equal(await evaluate('document.querySelectorAll(".group-card").length'),2);
    await evaluate(`document.getElementById('group-search').value='';document.getElementById('group-search').dispatchEvent(new Event('input'))`);
    assert.match(await evaluate('document.getElementById("country-summary").textContent'),/1\.16667/);
    assert.match(await evaluate('document.getElementById("modifier-results").textContent'),/-0\.125/);
    await evaluate(`document.getElementById('basket-shock').click();document.getElementById('basket-show-all').click()`);
    assert.equal(await evaluate('document.querySelectorAll("#basket-results tr").length'),56);
    assert.equal(await evaluate('window.SOL_BASKET_SNAPSHOT.goods.some(g=>Math.abs(g.m-1)>1e-8)'),true);
    await evaluate(`document.querySelector('#basket-populations input').value=18;document.querySelector('#basket-populations input').dispatchEvent(new Event('input',{bubbles:true}))`);
    assert.equal(await evaluate('window.SOL_BASKET_SNAPSHOT.records[0].population'),18);
    await evaluate(`window.originalObjectURL=URL.createObjectURL;URL.createObjectURL=blob=>{window.exportBlob=blob;return window.originalObjectURL(blob)};HTMLAnchorElement.prototype.click=function(){};document.getElementById('basket-export').click()`);
    assert.equal(await evaluate('(async()=>JSON.parse(await window.exportBlob.text()).records.length)()'),784);
    await evaluate(`document.getElementById('lab-export').click()`);
    assert.equal(await evaluate('(async()=>(await window.exportBlob.text()).trim().split(/\\r?\\n/).length)()'),57);
    await evaluate(`document.getElementById('basket-populations').closest('.lab-panel').scrollIntoView({behavior:'instant'})`);await pause(100);await screenshot('desktop-country-basket');
    await evaluate(`document.getElementById('engel-stratum').value='clergy';document.getElementById('engel-group').value='weapons';document.getElementById('engel-stratum').dispatchEvent(new Event('input'))`);
    assert.match(await evaluate('document.getElementById("engel-results").textContent'),/固定 base=1/);
    await evaluate(`document.querySelector('[data-source="history-overlap"]').click()`);
    assert.equal(await evaluate('document.getElementById("source-dialog").open'),true);
    assert.match(await evaluate('document.getElementById("source-content").textContent'),/divide = 2/);
    assert.equal(await evaluate('document.getElementById("source-content").querySelectorAll(".line-no").length>60'),true);
    await screenshot('desktop-source');await evaluate('document.getElementById("source-dialog").close()');
    await evaluate(`document.querySelector('[data-pipeline="2"]').click();document.querySelector('[data-lifecycle="6"]').click()`);
    assert.match(await evaluate('document.getElementById("pipeline-detail").textContent'),/raw spending/);
    assert.match(await evaluate('document.getElementById("lifecycle-detail").textContent'),/remove/);
    await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
    await evaluate('window.scrollTo(0,0)');await pause(200);
    assert.equal(await evaluate('document.documentElement.scrollWidth<=window.innerWidth'),true);
    await screenshot('mobile-overview');
    await evaluate(`document.getElementById('groups').scrollIntoView()`);await pause(100);await screenshot('mobile-groups');
    assert.equal(await evaluate('document.documentElement.scrollWidth<=window.innerWidth'),true);
    assert.deepEqual(errors,[]);
    console.log('Browser smoke passed: 20 groups, all offline checks, prices, A/B, PP, overlaps, search, aggregation, calibrated basket, population inputs, CSV/JSON exports, offsets, Engel fallback, source dialog, lifecycle, 390px mobile.');
  }finally{
    await fetch(cdp+'/json/close/'+target.id).catch(()=>{});ws.close();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
