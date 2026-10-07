/* No fetch, CDN or module loader: also works by double-clicking index.html. */
(() => {
  'use strict';
  const data = window.SOL_DATA, E = window.SOLEngine;
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const f = (n,d=5) => Number(n).toLocaleString('en-US',{maximumFractionDigits:d});
  const signed = n => `${n>=0?'+':''}${f(n)}`;
  const approx = (a,b) => Math.abs(a-b)<1e-9;
  const goodName = id => data.goodNames[id] || id;
  const state = { catalog:'current', group:'staple', mode:'A', values:{}, result:null, source:null, country:[{q:1,p:1,d:.5},{q:2,p:1,d:1.5}] };
  const strata=['nobles','clergy','burghers','laborers','peasants','soldiers','tribesmen'];
  state.basketPopulation=[Object.fromEntries(strata.map((s,i)=>[s,[8,2,12,25,50,2,1][i]])),Object.fromEntries(strata.map((s,i)=>[s,[2,1,3,30,60,2,2][i]]))];
  state.basketReady=false;state.basketShowAll=false;
  let toastTimer;
  function toast(message) { $('toast').textContent=message; $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').classList.remove('show'),2800); }
  function download(name, content, type='text/plain;charset=utf-8') {
    const url=URL.createObjectURL(new Blob([content],{type})); const a=document.createElement('a'); a.href=url; a.download=name; document.body.append(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000); toast('已导出可复算的实验数据');
  }
  function num(input,min,max) {
    const parsed=Number(input.value); const v=Math.min(max,Math.max(min,Number.isFinite(parsed)?parsed:min));
    return v;
  }
  function groupSet() {
    if(state.catalog==='historical') return data.groups;
    if(state.catalog==='pp') return data.currentGroups.map(g=>g.id==='luxury_food'?{...g,members:[...g.members,'victuals']}:g);
    return data.currentGroups;
  }
  function initValues() {
    state.values=Object.fromEntries(Object.keys(E.memberships(groupSet())).map(i=>[i,{ratio:1,b:50,supply:true,supported:data.interfaces[i]!==false,v:1}]));
  }
  function renderGroupCards() {
    const query=$('group-search').value.trim().toLowerCase(), groups=groupSet();
    const filtered=groups.filter(g=>`${g.id} ${g.name} ${g.members.map(i=>`${i} ${goodName(i)}`).join(' ')}`.toLowerCase().includes(query));
    const member=E.memberships(groups);
    $('group-cards').innerHTML=filtered.map(g=>`<button class="group-card ${g.id===state.group?'active':''}" data-group="${g.id}" aria-pressed="${g.id===state.group}"><span class="group-index">${String(g.index).padStart(2,'0')}</span><strong>${g.name}</strong><span class="group-id">${g.id}</span><small>${g.members.length} 成员 · ${g.members.filter(i=>member[i].length>1).length} 跨组成员</small></button>`).join('') || '<p class="small">没有匹配的组或商品。</p>';
    $('catalog-note').textContent=state.catalog==='historical'?'历史目录含 victuals、不含 camels；此实验对该目录仍使用新版 A/B 规则。要看完整旧倍率，阅读下一章。victuals 默认按当前缺接口策略冻结，勾选接口仅为假设测试。':state.catalog==='pp'?'PP 目录补入 victuals，默认缺接口冻结；勾选接口只是模拟未来已验证补类型的情形。本演示不模拟 PP 的全套 demand_add 或木材零需求。':'当前核心含 camels、不含 victuals。luxury_food 本轮三成员，但历史 N=4；mounts 本轮三成员，历史 N=2。两个 N 都保留，A 的中性对照抵消共同尺度。';
  }
  function renderLabRows() {
    const groups=groupSet(),g=groups.find(g=>g.id===state.group),member=E.memberships(groups);
    $('lab-title').textContent=`${g.name} / ${g.id}`;
    $('lab-rows').innerHTML=g.members.map(i=>{
      const v=state.values[i]; return `<tr data-good="${i}"><td><strong>${goodName(i)}</strong><small>${i}</small><small>${member[i].map(id=>groups.find(x=>x.id===id).name).join(' · ')}</small></td><td><input type="number" data-field="ratio" min="0.01" max="10" step="0.01" value="${v.ratio}" aria-label="${goodName(i)}价格比"><input type="range" data-field="ratio-range" min="0.1" max="3" step="0.01" value="${v.ratio}" aria-label="${goodName(i)}价格比滑块"></td><td><input type="number" data-field="b" min="0" max="1000000" step="0.01" value="${v.b}" aria-label="${goodName(i)}基线金额"></td><td><input type="checkbox" data-field="supply" ${v.supply?'checked':''} aria-label="${goodName(i)}有供应"></td><td><input type="checkbox" data-field="supported" ${v.supported?'checked':''} aria-label="${goodName(i)}有接口"></td><td data-output="weight"></td><td data-output="response"></td><td data-output="target"></td></tr>`;
    }).join('');
    document.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('active',b.dataset.mode===state.mode);b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode));});
    $('mode-description').innerHTML=state.mode==='A'?'<strong>方案 A 是“先问相对偏好，再套回原支出”的方法。</strong> 对同一消费组先做两遍：第一遍使用当前价格档位，第二遍把所有价格暂时当作默认价（这就是“中性对照”）。每一遍都把组内商品的权重换算成份额；如果商品属于两个组，就先得到两个组的结果，再取平均。最后用“当前份额 ÷ 中性份额”得到 D：D=0.8 表示这个商品目标支出是原来的 80%，D=1.2 表示增加到 120%。地点原本的 B 再乘 D 才得到目标金额。这里 V=1 意味着暂时不使用宗教、文化、气候等旧 POP 偏好；group_scale=1 意味着暂时不把收入、储蓄、时代和稀缺总量曲线混进这个价格实验。<br><span class="plain-warning">A 保留 v1.1 的价格响应形状，但它没有承诺每组金额加起来仍等于原金额；金额是否变化交给后续 SOL 收入求解器处理。</span>':'<strong>方案 B 是“把原来的组预算完整搬家”的方法。</strong> 一个跨组商品先按所属组数量拆开：属于两个组就各分一半 B。每个组先算出自己拥有的那份预算，再按“基线金额 × 价格权重”重新分配；各组完成后把同一商品从各组收到的目标金额加起来。这样每个组的目标金额保持不变，但这是一条新设计规则，不是 v1.1 已证实的历史行为。';
    $('lab-formula').innerHTML=state.mode==='A'?'<strong>第一遍（当前价格）</strong>：商品在组里的份额 = 该商品权重 T ÷ 组内所有有效商品权重之和。<br><strong>第二遍（中性价格）</strong>：把每个 T 暂时改成 1，再用同一批商品和同一批基线做一遍。<br><strong>跨组商品</strong>：分别得到每个组的份额后求平均。<br><strong>最后</strong>：D = 当前结果 ÷ 中性结果；目标金额 B′ = 原本金额 B × D。':'<strong>先拆开</strong>：某商品属于几个组，就把它的 B 平分给几个组。<br><strong>每组重分配</strong>：该商品的临时金额 × T，再除以组内所有临时金额的总和，得到新的组内份额。<br><strong>最后合并</strong>：商品从各组收到的目标金额相加，B′ = 各组目标金额之和；D = B′ ÷ B。';
    renderLabResult();
  }
  function summaryItem(label,value,note='') { return `<div class="summary-item"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`; }
  function renderLabResult() {
    const groups=groupSet(),g=groups.find(g=>g.id===state.group);
    const result=E.substitute(groups,state.values,state.mode); state.result=result;
    document.querySelectorAll('#lab-rows tr').forEach(row=>{
      const i=row.dataset.good,v=state.values[i],o=result.goods[i];
      row.querySelector('[data-output=weight]').innerHTML=`<code>${f(E.tier(v.ratio).weight,2)}</code><small>${E.tier(v.ratio).label}</small>`;
      row.querySelector('[data-output=response]').innerHTML=`<strong class="${o.response<1?'negative':o.response>1?'positive':''}">${f(o.response)}×</strong>`;
      row.querySelector('[data-output=target]').innerHTML=`<code>${f(o.target)}</code>${!v.supply?'<small>无供应 · 基线有效额=0</small>':!v.supported?'<small>缺接口 · 冻结原金额</small>':''}`;
    });
    const all=Object.values(result.goods),b=E.sum(all.map(o=>o.baseline)),bt=E.sum(all.map(o=>o.target));
    const active=g.members.filter(i=>state.values[i].supply&&state.values[i].supported&&state.values[i].b>0).length;
    $('lab-summary').innerHTML=summaryItem('全网络基线金额',f(b),'商品仅计一次，供给关闭则为 0')+summaryItem('全网络目标金额',f(bt),state.mode==='B'?'拆分后各组预算守恒':'A 允许金额改变，后续 solver 重算')+summaryItem('全网络金额差',signed(bt-b),`${state.mode==='B'?'舍入误差之外应为 0':'不把归一化误称为预算守恒'}`)+summaryItem('当前组有效成员',`${active} / ${g.members.length}`,`历史 N=${g.n}；V=1；跨组商品影响多组`);
    renderOverlap();
    if(state.basketReady)renderBasket();
  }
  function renderOverlap() {
    const groups=groupSet(),member=E.memberships(groups),i=$('overlap-good').value||'wine',o=state.result.goods[i];
    if(!o) return;
    const rows=member[i].map(id=>{const d=state.result.details[id][i],g=groups.find(x=>x.id===id);return `<div class="breakdown-row"><span>${g.name} <small>N=${g.n}</small></span><code>${state.mode==='A'?`Fᵀ ${f(d.ft)} / F¹ ${f(d.f1)}`:`b ${f(d.b)} → b′ ${f(d.bt)}`}</code></div>`;}).join('');
    $('overlap-breakdown').innerHTML=rows+`<div class="breakdown-total">${state.mode==='A'?`Hᵀ=${f(o.ht)} · H¹=${f(o.h1)}<br>两个组先各自贡献，再取平均。<br>D=${f(o.response)}，B′=${f(o.target)}`:`每个组只使用 B/${member[i].length}<br>目标相加 = ${f(o.target)}；D=${f(o.response)}`}</div>`;
  }
  function preset(name) {
    initValues();
    let g=groupSet().find(g=>g.id===state.group);
    if(name==='overlap'){state.group='intoxicants';g=groupSet().find(g=>g.id===state.group);state.values.wine.ratio=2;state.values.coffee.ratio=.5;}
    else if(name==='shock')state.values[g.members[0]].ratio=2;
    else if(name==='unequal'){
      state.group='weapons';g=groupSet().find(g=>g.id===state.group);
      state.values.weaponry.b=90;state.values.firearms.b=10;state.values.weaponry.ratio=2;
    }else if(name==='missing'){state.values[g.members[0]].supported=false;if(g.members[1])state.values[g.members[1]].supply=false;}
    renderGroupCards();renderLabRows();toast(name==='unequal'?'已切换到无跨组的武器组，精确复现 90/10 对照':'已载入全网络试验');
  }
  function renderPrice(value=1) {
    const t=E.tier(value);$('price-output').textContent=f(value,2)+'×';
    $('price-range').value=value;if(document.activeElement!==$('price-number'))$('price-number').value=value;
    $('price-result').innerHTML=`<span>${t.label} <small>当前价格档</small></span><strong>× ${f(t.weight,2)}</strong>`;
    const segments=[[0,0.4,2],[0.4,.65,1.5],[.65,.85,1.25],[.85,1.3,1],[1.3,1.7,.75],[1.7,2.3,.5],[2.3,3,.25]];
    const x=r=>46+r/3*550,y=w=>210-w/2*165;
    let chart=`<line x1="46" y1="210" x2="596" y2="210" stroke="#cdd6bf"/><text x="10" y="22" fill="#7f8f70" font-size="10">权重 T</text><text x="542" y="241" fill="#7f8f70" font-size="10">价格比 r</text>`;
    [0,.5,1,1.5,2].forEach(w=>chart+=`<line x1="46" y1="${y(w)}" x2="596" y2="${y(w)}" stroke="#e5e9dc"/><text x="13" y="${y(w)+4}" fill="#8b977d" font-size="10">${w.toFixed(2)}</text>`);
    segments.forEach(([a,b,w],i)=>{chart+=`<path d="M ${x(a)} ${y(w)} H ${x(b)}" stroke="#748957" stroke-width="3" fill="none"/>`;if(i>0)chart+=`<line x1="${x(a)}" y1="${y(segments[i-1][2])}" x2="${x(a)}" y2="${y(w)}" stroke="#aabb8e" stroke-dasharray="3 3"/>`;});
    [.4,.65,.85,1.3,1.7,2.3].forEach(r=>chart+=`<text x="${x(r)}" y="227" text-anchor="middle" fill="#8b977d" font-size="10">${r.toFixed(2)}</text>`);
    const px=x(Math.min(3,value));chart+=`<line x1="${px}" y1="30" x2="${px}" y2="210" stroke="#b39458" stroke-dasharray="4 4"/><circle cx="${px}" cy="${y(t.weight)}" r="6" fill="#b39458" stroke="#fff" stroke-width="2"/>`;
    $('tier-chart').innerHTML=chart;
    document.querySelectorAll('#tier-table tr').forEach(row=>row.classList.toggle('highlight',row.dataset.tier===t.key));
  }
  function initPriceTable() {
    const rows=[['1','r > 2.30','.25','severe','严重昂贵','r=2.30 → 0.50'],['2','r > 1.70','.50','moderate','明显昂贵','r=1.70 → 0.75'],['3','r > 1.30','.75','mild','轻度昂贵','r=1.30 → 1.00'],['4','r < 0.40','2.00','vcheap','非常便宜','r=0.40 → 1.50'],['5','r < 0.65','1.50','cheap','明显便宜','r=0.65 → 1.25'],['6','r < 0.85','1.25','affordable','较为便宜','r=0.85 → 1.00'],['其他','0.85 ≤ r ≤ 1.30','1.00','neutral','中性 · 不在列表','两端均中性']];
    $('tier-table').innerHTML=rows.map(([order,condition,weight,key,label,boundary])=>`<tr data-tier="${key}"><td>${order}</td><td><code>${esc(condition)}</code></td><td><strong>${weight}</strong></td><td>${label}<small> / ${key}</small></td><td>${boundary}</td></tr>`).join('');
    $('boundary-buttons').innerHTML=[.4,.65,.85,1.3,1.7,2.3].map(r=>`<button data-boundary="${r}">${r.toFixed(2)}</button>`).join('');
    renderPrice();
  }
  function renderEngel() {
    const s=$('engel-stratum').value,g=$('engel-group').value,curve=data.curves[s]?.[g];
    const yValue=num($('engel-income'),0,60),sp=num($('engel-savings'),-1,.5),scarcity=num($('engel-scarcity'),0,5);
    const era=[1.5,1.425,1.35375,1.28606,1.22176,1.16067][Number($('engel-era').value)];
    const base=y=>s==='tribesmen'?1:E.historicalBase(curve,y);
    const points=Array.from({length:241},(_,i)=>[i/4,base(i/4)]),max=Math.max(...points.map(p=>p[1]),1)*1.1;
    const x=y=>44+y/60*552,z=b=>215-b/max*174;
    let svg='';
    [0,.25,.5,.75,1].forEach(n=>svg+=`<line x1="44" y1="${z(max*n)}" x2="596" y2="${z(max*n)}" stroke="#e1e7d6"/><text x="4" y="${z(max*n)+4}" fill="#8b997c" font-size="9">${f(max*n,1)}</text>`);
    [3,8,25,60].forEach(y=>svg+=`<line x1="${x(y)}" y1="28" x2="${x(y)}" y2="215" stroke="#cdd7bb" stroke-dasharray="4 4"/><text x="${x(y)}" y="234" text-anchor="middle" fill="#889879" font-size="10">${y}</text>`);
    svg+=`<path d="${points.map(([y,b],i)=>`${i?'L':'M'}${x(y)},${z(b)}`).join(' ')}" fill="none" stroke="#647f4b" stroke-width="2.5"/><circle cx="${x(yValue)}" cy="${z(base(yValue))}" r="5" fill="#b69654"/><text x="44" y="17" font-size="10" fill="#7b8d6a">demand_base</text><text x="548" y="252" font-size="10" fill="#7b8d6a">GDP / 人</text>`;
    $('engel-chart').innerHTML=svg;
    const b=base(yValue),scale=Math.max(0,(1+sp)*b*era*scarcity),alpha=s==='tribesmen'?null:E.piecewise(curve.share,yValue),offset=s==='tribesmen'?null:E.piecewise(curve.offset,yValue);
    $('engel-results').className='engel-results';
    $('engel-results').innerHTML=`<span>base <strong>${f(b)}</strong></span><span>group_scale <strong>${f(scale)}</strong></span><span>${s==='tribesmen'?'部落民：固定 base=1，无收入项':`α=${f(alpha)} · P=${f(curve.price)} · offset=${f(offset)}${curve.constantBase!=null?` · 历史 P≈0，固定 base=${curve.constantBase}`:''}`}</span>`;
  }
  function countryResult() { return E.aggregate(state.country.map(r=>({b:r.q*r.p,d:r.d})),num($('country-epsilon'),0,100)); }
  function renderCountryRows() {
    $('country-rows').innerHTML=state.country.map((r,index)=>`<tr data-market="${index}"><td><strong>市场 ${index===0?'A':'B'}</strong><br><small>仅该国所属地点的商品需求</small></td>${['q','p','d'].map(key=>`<td><input type="number" data-country-field="${key}" min="0" max="1000000" step="0.01" value="${r[key]}" aria-label="市场 ${index===0?'A':'B'} ${key}"></td>`).join('')}<td data-country-output="b"></td><td data-country-output="actual"></td><td data-country-output="error"></td></tr>`).join('');renderCountry();
  }
  function renderCountry() {
    const a=countryResult(),q=E.sum(state.country.map(r=>r.q)),qm=q>0?E.sum(state.country.map(r=>r.q*r.d))/q:1;
    document.querySelectorAll('#country-rows tr').forEach(row=>{const r=state.country[Number(row.dataset.market)],b=r.q*r.p,error=b*a.m-b*r.d;row.querySelector('[data-country-output=b]').innerHTML=`<code>${f(b)}</code>`;row.querySelector('[data-country-output=actual]').innerHTML=`<code>${f(b*a.m)}</code><small>M=${f(a.m)}×</small>`;row.querySelector('[data-country-output=error]').innerHTML=`<span class="${error<0?'negative':'positive'}">${signed(error)}</span>`;});
    $('country-summary').innerHTML=summaryItem('国家参考金额加权 M',f(a.m)+'×',a.fallback?'E≤epsilon → 中性回退':'E′ / E')+summaryItem('数量加权对照',f(qm)+'×', '同一商品默认价相同时应与 M 相同')+summaryItem('理想目标金额 E′',f(a.target),`原金额 E=${f(a.baseline)}`)+summaryItem('统一后目标总额',f(a.baseline*a.m),a.fallback?'小额回退保留原额，不采用 E′':'此时尚未重算各地点 SOL 系数');
    const max=Math.max(1,...state.country.flatMap(r=>[r.q*r.p*r.d,r.q*r.p*a.m]));
    $('compression-bars').innerHTML=state.country.map((r,index)=>`<div><h4>市场 ${index===0?'A':'B'} · 该国的本地需求</h4>${[[r.q*r.p*r.d,'本地理想',''],[r.q*r.p*a.m,'国家统一后','actual']].map(([v,label,cls])=>`<div class="bar-row"><span>${label}</span><div class="bar-track"><div class="bar-fill ${cls}" style="width:${v/max*100}%"></div></div><code>${f(v,3)}</code></div>`).join('')}</div>`).join('');
  }
  function renderModifier() {
    const m=num($('modifier-m'),0,10),e=num($('modifier-e'),-.99,5),semantics=$('modifier-semantics').value;
    const naive=m-1,correct=E.modifierSize(m,e,semantics),external=1+e;
    const effective=x=>semantics==='additive'?(external+x)/external:1+x;
    $('modifier-results').innerHTML=summaryItem('外部原因子 1+e',f(external),'外部来源单独生效时')+summaryItem('朴素 size=M−1',signed(naive),`实际相对倍率 ${f(effective(naive))}×`)+summaryItem('此假设下正确 size',signed(correct),`实际相对倍率 ${f(effective(correct))}×`)+summaryItem('最终总因子',f(external*m),'相对于无外部修正的基线');
    $('modifier-explanation').innerHTML=semantics==='additive'?`假设同商品百分比相加：(1+e+x)/(1+e)=M，所以 <strong>x=(1+e)×(M−1)</strong>。当前 e=${f(e)}，M=${f(m)}，x=${f(correct)}。朴素换算${approx(effective(naive),m)?'在此参数下恰好一致':'会让账本与实际响应不一致'}；负总因子可能被引擎截断，本实验不猜测截断规则。`:'假设来源作为独立因子相乘：(1+e)×(1+x)，相对外部原基线的倍率就是 1+x，因此 x=M−1。这个假设不证明商品与 local_pop_demand 也按同样关系组合。';
  }
  function initBasket(){
    $('basket-populations').innerHTML=state.basketPopulation.map((p,market)=>`<tr data-basket-market="${market}"><td>市场 ${market===0?'A':'B'}</td>${strata.map(s=>`<td><input type="number" min="0" max="1000000" step="1" value="${p[s]}" data-stratum="${s}" aria-label="市场 ${market===0?'A':'B'} ${s} 人口"></td>`).join('')}</tr>`).join('');
    state.basketReady=true;renderBasket();
  }
  function renderBasket(){
    const basket=E.nationalBasket(data.currentGroups,data.units,state.basketPopulation,state.values,state.mode,$('basket-price-rule').value);
    state.basket=basket;window.SOL_BASKET_SNAPSHOT=basket;
    const changed=basket.goods.filter(g=>Math.abs(g.m-1)>1e-9).length;
    $('basket-mode').textContent=`沿用方案 ${state.mode} · 当前核心目录 · V=1`;
    $('basket-summary').innerHTML=summaryItem('56 商品基线金额',f(basket.baseline),'来自当前净消费量和教学人口')+summaryItem('本地理想目标金额',f(basket.target),state.mode==='B'?'每人口类型内的组预算守恒':'A 改变篮子成本，未做收入闭合')+summaryItem('压缩后统一倍率金额',f(basket.realized),'尚未乘各地点 SOL 系数')+summaryItem('非中性国家商品数',`${changed} / 56`,'价格、供给、基线与跨组共同决定');
    const sorted=[...basket.goods].sort((a,b)=>Math.abs(b.m-1)-Math.abs(a.m-1));
    const shown=state.basketShowAll?sorted:sorted.slice(0,10);
    $('basket-results').innerHTML=shown.map(g=>`<tr><td><strong>${goodName(g.good)}</strong><small>${g.good}</small></td><td>${f(g.baseline)}</td><td>${f(g.target)}</td><td class="${g.m<1?'negative':g.m>1?'positive':''}">${f(g.m)}×${g.fallback?'<small>小额 / 零基线回退</small>':''}</td><td>${f(g.local[0].d)}×</td><td>${f(g.local[1].d)}×</td><td>A ${signed(g.local[0].error)}<small>B ${signed(g.local[1].error)}</small></td></tr>`).join('');
    $('basket-show-all').textContent=state.basketShowAll?'收起为前 10 商品':'显示全部 56 商品';
  }
  const pipeline=[
    ['保留共享原始商品明细','按市场、商品、七种人口类型生成净单位消费量 q，并用商品默认价建立不受当前市场价格影响的中性参考金额 B。市场价只进入 v1.1 价格档位和 D；当前 SOL 的 min(市场价,默认价) 支出代理留在后续 raw spending 层。此层不写入任何国家 M，其他国家才能安全共享同一原始输入。','current-market'],
    ['计算完整国家快照，再转换接口值','只遍历该国拥有的陆地地点；由 A/B 本地目标聚合 E、E′、M。按实测组合规则计算 size 与内部实际生效倍率；无法覆盖的商品保持中性。商品 M 和地点系数要成套更新。','implementation'],
    ['用实际生效篮子形成 raw spending','验证了商品 / 地点修正关系后，把商品项乘实际生效倍率，再加成各人口类型支出，最后合并平民。地点 raw 从收入、维护支出和储蓄目标闭合得到；不能沿用市场公共总额。','current-location'],
    ['沿用当前国家收入目标与四类求解器','更新后的地点 raw 进入现有分类和国家四类 solver。当前小国 / 设置门槛可能走 raw-only；可行时精确求解，不可行时按现有严格不恶化近似或 raw fallback。替代改变输入篮子，不重新定义收入目标。','implementation'],
    ['提交一致快照，月度持续写入','完整求解后一起提交国家商品缓存、地点最终系数和版本。商品国家 modifiers、地点 local_pop_demand 按月 replace；年度低频 AI 只复用已闭合快照，不能只刷新 M。','current-apply']
  ];
  function renderPipeline(index=0){const [title,description,source]=pipeline[index];$('pipeline-detail').innerHTML=`<span class="tag candidate">恢复接入顺序 · 第 ${index+1} 步</span><h3>${title}</h3><p>${description}</p><button class="source-link" data-source="${source}">查看对应依据 ↗</button>`;document.querySelectorAll('[data-pipeline]').forEach(b=>b.classList.toggle('active',Number(b.dataset.pipeline)===index));}
  const lifecycle=[
    {name:'新游戏 / 读档',tag:'完整初始化',steps:['建立市场原始商品明细，确认商品目录和接口覆盖。','计算国家完整 M 与实际倍率，重算地点 raw 和国家 solver。','提交国家 / 地点同版本缓存并写入修正，初始化成功后再标记版本。'],note:'缺缓存先用中性，并在初始化完成后成套重跑。历史全刷新并未保证建立全部 hub 评分。'},
    {name:'市场年度刷新',tag:'一月更新共享输入',steps:['更新世界市场档位、供给和商品明细，递增市场缓存版本。','人类 / 正常频率国家在相应月度路径成套更新。','低频 AI 保持已有国家 M 和地点系数，等自身年度 pulse 一起重算。'],note:'不要让全部 AI 一月重算，更不要更新商品 M 却保留旧地点系数。'},
    {name:'月度 / 正常 AI',tag:'每月计算与写入',steps:['人类国家及关闭低频选项的 AI 成套更新国家替代、地点 raw、国家 solver。','提交完整快照后按月 replace 国家商品与地点修正。','失去正基线或接口的商品显式 remove，清掉旧商品缓存。'],note:'刷新必须排除自身旧修正后读取外部来源，在同一次效果内重新应用。'},
    {name:'低频 AI',tag:'计算年度 · 写入月度',steps:['每月仅从同一已闭合国家 / 地点快照重写修正。','自身年度 anniversary pulse 成套重算商品 M 与 solver。','读档、失效和启用功能等必需初始化不能被低频设置跳过。'],note:'1～2 个月修正不能因年度求解而中途过期。'},
    {name:'国家 / 市场变化',tag:'失效场景，hook 待核对',steps:['国家成立、领土 / 市场归属变化、玩家 / AI 切换都可能使快照失效。','逐项核对可用 on_action；没有即时 hook 则使用月度守卫。','清理失效商品，成套重算；明确月度守卫最长一个月延迟。'],note:'这些是实现要求，不是已证实存在的引擎 hook。'},
    {name:'时代 / 思潮',tag:'外部来源变化',steps:['将外部商品修正的变化作为国家快照失效原因。','同次效果排除自身旧值，读取外部 offset，按实测模型换算新 size。','同时重算内部实际倍率与地点 / 国家 solver，不留跨月空窗。'],note:'类型声明不能证明实际叠加顺序，需以稳定人口需求实测。'},
    {name:'关闭 / 清理',tag:'显式移除并重算',steps:['对所有国家所有受控商品 remove SOL 替代 modifier。','删除替代专用国家变量和 maps，不删除仍供其他 SOL 功能使用的共享市场缓存。','若只是关闭替代，按 M=1 重算仍启用的 SOL；若关闭整个 SOL 则执行完整清理。'],note:'不能只跳过下一次 trigger，也不能只等待修正过期。'}
  ];
  function renderLifecycle(index=0){const l=lifecycle[index];$('lifecycle-tabs').innerHTML=lifecycle.map((x,i)=>`<button data-lifecycle="${i}" class="${i===index?'active':''}" aria-pressed="${i===index}">${x.name}</button>`).join('');$('lifecycle-detail').innerHTML=`<span class="tag candidate">${l.tag}</span><ol>${l.steps.map(s=>`<li>${s}</li>`).join('')}</ol><p class="small">${l.note}</p>`;}
  function runChecks() {
    const results=[];
    const check=(title,fn,note)=>{let passed=false;try{passed=fn();}catch{}results.push({title,passed,note});};
    check('严格价格边界',()=>[2.3,1.7,1.3,.85,.65,.4].every((r,i)=>E.tier(r).weight===[.5,.75,1,1,1.25,1.5][i]),'2.30 / 1.70 / 1.30 / 0.85 / 0.65 / 0.40 均按严格比较。');
    const groups=[{id:'x',n:2,members:['a','b']}],values={a:{b:90,ratio:2},b:{b:10,ratio:1}};
    check('不等基线中性 A / B',()=>['A','B'].every(mode=>Object.values(E.substitute(groups,{a:{b:90,ratio:1},b:{b:10,ratio:1}},mode).goods).every(o=>approx(o.response,1))),'90/10 在 T=1 时仍是 90/10，不被强制等分。');
    check('A 的价格响应',()=>{const r=E.substitute(groups,values).goods;return approx(r.a.target,60)&&approx(r.b.target,40/3);},'90/10 → 60/13.33333，明确不守恒。');
    check('B 的预算守恒',()=>{const r=E.substitute(groups,values,'B').goods;return approx(r.a.target,900/11)&&approx(r.b.target,200/11);},'90/10 → 81.81818/18.18182，总额 100。');
    check('历史跨组是平均',()=>approx((.6+1.4)/2,1),'源码 divide=2；0.6 与 1.4 最终为 1.0，不是 2.0。');
    check('重叠金额不重复记账',()=>{const g=[{id:'x',n:2,members:['a','b']},{id:'y',n:2,members:['a','c']}],v={a:{b:90,ratio:2},b:{b:10,ratio:.5},c:{b:20,ratio:1}};return approx(E.sum(Object.values(E.substitute(g,v,'B').goods).map(o=>o.target)),120);},'B 先将 a 的基线分到两个组，目标总额仍为 120。');
    check('金额与数量聚合不同',()=>approx(E.aggregate([{b:1,d:.5},{b:2,d:1.5}]).m,7/6),'金额口径 M=7/6；数量 1/1 加权 M=1。');
    check('epsilon 保持中性',()=>E.aggregate([{b:.0005,d:1}]).m===1,'小于阈值分支回退 1，不将正分母抬到 0.001。');
    check('缺接口与无供应',()=>['A','B'].every(mode=>{const r=E.substitute(groups,{a:{b:90,ratio:2,supported:false},b:{b:10,ratio:.3,supply:false}},mode).goods;return r.a.response===1&&r.a.target===90&&r.b.target===0;}),'缺接口冻结原金额，无供应有效金额为零，不制造新需求。');
    check('全组空 / 单有效成员',()=>{const r=E.substitute(groups,{a:{b:10,ratio:3},b:{b:0,ratio:.2}}).goods;return r.a.response===1&&r.b.target===0;},'不足两有效成员无替代；零需求仍为零。');
    check('外部 offset 反例推导',()=>approx(E.modifierSize(.5,-.75,'additive'),-.125),'此处仅验证加法假设的数学推导，不证明引擎采用此模型。');
    check('历史集合完整性',()=>data.groups.length===20&&Object.keys(E.memberships(data.groups)).length===56&&data.groups.flatMap(g=>g.members).length===67&&Object.values(E.memberships(data.groups)).filter(a=>a.length===2).length===11,'固定源码快照：20 组、56 商品、67 成员关系、11 跨组商品。');
    $('checks').innerHTML=results.map(r=>`<div class="check ${r.passed?'':'fail'}"><strong><span class="check-mark">${r.passed?'✓':'×'}</span>${r.title}</strong><p>${r.note}</p></div>`).join('');
    window.SOL_CHECK_RESULTS=results;
  }
  function openSource(id) {
    const s=data.sources[id];if(!s){toast('此商品不在 v1.1 目录中');return;}
    state.source=s;$('source-title').textContent=s.title;
    $('source-meta').textContent=`${s.path}:${s.line}\n版本：${s.revision}`;
    $('source-content').innerHTML=s.text.split('\n').map((line,i)=>`<span class="source-line"><span class="line-no">${s.line+i}</span>${esc(line)||' '}</span>`).join('');
    $('source-dialog').showModal();$('source-content').scrollTop=0;
  }
  function initReferences(){
    const refs=[['implementation','主规格 · 恢复候选算法、接口、生命周期与验收'],['audit','审计报告 · 跨组平均、中性错误、金额口径和接口反例'],['history-entry','实际需求入口 · POP scope 与基础人口需求的组合'],['history-overlap','11 种跨组商品 · 最终聚合的真实 divide=2'],['history-tiers','价格档位 · 336 个市场列表的生命周期'],['current-groups','当前目录映射 · 与历史商品目录的差异'],['current-units','当前净单位消费量 · 可追溯校准后的数量基线'],['early-design','早期十组草案 · 仅作设计背景，不覆盖二十组事实']];
    $('reference-list').innerHTML=refs.map(([id,description])=>`<button class="reference-item" data-source="${id}"><strong>${data.sources[id].title} ↗</strong><small>${description}</small><code>${data.sources[id].path}:${data.sources[id].line}</code></button>`).join('');
    $('weight-source-good').innerHTML=Object.keys(E.memberships(data.groups)).map(i=>`<option value="${i}">${goodName(i)} / ${i}</option>`).join('');
  }
  document.addEventListener('click',event=>{
    const b=event.target.closest('button');if(!b)return;
    if(b.dataset.source)openSource(b.dataset.source);
    if(b.dataset.group){state.group=b.dataset.group;renderGroupCards();renderLabRows();}
    if(b.dataset.mode){state.mode=b.dataset.mode;renderLabRows();}
    if(b.dataset.preset)preset(b.dataset.preset);
    if(b.dataset.boundary)renderPrice(Number(b.dataset.boundary));
    if(b.dataset.pipeline!==undefined)renderPipeline(Number(b.dataset.pipeline));
    if(b.dataset.lifecycle!==undefined)renderLifecycle(Number(b.dataset.lifecycle));
  });
  $('group-search').addEventListener('input',renderGroupCards);
  $('catalog').addEventListener('change',e=>{state.catalog=e.target.value;initValues();renderGroupCards();renderLabRows();});
  $('lab-reset').addEventListener('click',()=>{initValues();renderLabRows();toast('全网络已恢复中性，缺接口项目仍保持冻结');});
  $('lab-rows').addEventListener('input',event=>{
    const input=event.target,field=input.dataset.field;if(!field)return;
    const row=input.closest('tr'),value=state.values[row.dataset.good];
    if(input.type==='checkbox')value[field]=input.checked;
    else if(field==='ratio'||field==='ratio-range'){value.ratio=num(input,.01,10);if(field==='ratio-range')row.querySelector('[data-field=ratio]').value=value.ratio;row.querySelector('[data-field=ratio-range]').value=value.ratio;}
    else value.b=num(input,0,1000000);
    renderLabResult();
  });
  $('overlap-good').addEventListener('change',renderOverlap);
  $('lab-export').addEventListener('click',()=>{
    const rows=['good,name,groups,catalog,mode,ratio,tier_weight,input_B,effective_B,supply,supported,D,target_B'];const member=E.memberships(groupSet());
    for(const [i,o] of Object.entries(state.result.goods)){const v=state.values[i];rows.push([i,goodName(i),member[i].join('|'),state.catalog,state.mode,v.ratio,E.tier(v.ratio).weight,v.b,o.baseline,v.supply,v.supported,o.response,o.target].join(','));}
    download(`sol-substitution-${state.catalog}-${state.mode}.csv`,'\uFEFF'+rows.join('\r\n'),'text/csv;charset=utf-8');
  });
  $('price-range').addEventListener('input',e=>renderPrice(Number(e.target.value)));
  $('price-number').addEventListener('input',e=>renderPrice(num(e.target,.01,10)));
  ['engel-stratum','engel-group','engel-income','engel-savings','engel-era','engel-scarcity'].forEach(id=>$(id).addEventListener('input',renderEngel));
  $('country-rows').addEventListener('input',event=>{const input=event.target,key=input.dataset.countryField;if(!key)return;state.country[Number(input.closest('tr').dataset.market)][key]=num(input,0,1000000);renderCountry();});
  $('country-epsilon').addEventListener('input',renderCountry);
  $('country-example').addEventListener('click',()=>{state.country=[{q:1,p:1,d:.5},{q:2,p:1,d:1.5}];$('country-epsilon').value=.001;renderCountryRows();});
  $('country-export').addEventListener('click',()=>download('sol-national-aggregation.json',JSON.stringify({description:'聚合教学样例，非存档实测；默认价中性参考金额口径，地点 SOL 系数重算前',historicalRevision:data.revision,epsilon:Number($('country-epsilon').value),rows:state.country,result:countryResult()},null,2),'application/json'));
  $('basket-price-rule').addEventListener('input',renderBasket);
  $('basket-populations').addEventListener('input',event=>{const input=event.target,s=input.dataset.stratum;if(!s)return;state.basketPopulation[Number(input.closest('tr').dataset.basketMarket)][s]=num(input,0,1000000);renderBasket();});
  $('basket-show-all').addEventListener('click',()=>{state.basketShowAll=!state.basketShowAll;renderBasket();});
  $('basket-shock').addEventListener('click',()=>{state.catalog='current';$('catalog').value='current';initValues();state.group='staple';state.values.wheat.ratio=2;state.values.rice.ratio=.5;$('basket-price-rule').value='inverse';renderGroupCards();renderLabRows();toast('已将上方主食实验同步为价差场景');});
  $('basket-export').addEventListener('click',()=>download('sol-connected-country-basket.json',JSON.stringify({description:'当前核心真实净单位消费量；教学人口与价格；无收入 solver / 外部 modifier / 实测引擎组合',snapshotRevision:data.currentRevision,population:state.basketPopulation,inputs:state.values,units:data.units,...state.basket},null,2),'application/json'));
  ['modifier-m','modifier-e','modifier-semantics'].forEach(id=>$(id).addEventListener('input',renderModifier));
  $('run-checks').addEventListener('click',()=>{runChecks();toast('已复算全部离线数学检查；游戏语义尚待验证');});
  $('source-close').addEventListener('click',()=>$('source-dialog').close());
  $('source-dialog').addEventListener('click',e=>{if(e.target===$('source-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
  $('source-copy').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(state.source.text);toast('已复制原始源码（无附加行号）');}catch{download('sol-source.txt',state.source.text);toast('浏览器未开放剪贴板，已改为下载源码');}});
  $('source-download').addEventListener('click',()=>download(state.source.path.split('/').pop(),`# ${state.source.path}:${state.source.line}\n# revision: ${state.source.revision}\n${state.source.text}`));
  $('weight-source-open').addEventListener('click',()=>openSource(`weight-${$('weight-source-good').value}`));
  $('print-button').addEventListener('click',()=>window.print());
  initValues();
  $('engel-group').innerHTML=data.groups.map(g=>`<option value="${g.id}">${g.name} / ${g.id}</option>`).join('');$('engel-group').value='staple';
  $('overlap-good').innerHTML=Object.entries(E.memberships(data.groups)).filter(([,groups])=>groups.length>1).map(([i])=>`<option value="${i}" ${i==='wine'?'selected':''}>${goodName(i)} / ${i}</option>`).join('');
  initPriceTable();renderGroupCards();renderLabRows();renderEngel();renderCountryRows();renderModifier();renderPipeline();renderLifecycle();runChecks();initReferences();initBasket();
  const a=E.substitute([{id:'x',n:2,members:['a','b']}],{a:{b:90,ratio:2},b:{b:10,ratio:1}}),b=E.substitute([{id:'x',n:2,members:['a','b']}],{a:{b:90,ratio:2},b:{b:10,ratio:1}},'B');
  $('ab-example').innerHTML=`<div>A · 只恢复价格响应<b>${f(a.goods.a.target)} / ${f(a.goods.b.target)}</b>总额 ${f(a.goods.a.target+a.goods.b.target)}</div><div>B · 预算在组内转移<b>${f(b.goods.a.target)} / ${f(b.goods.b.target)}</b>总额 ${f(b.goods.a.target+b.goods.b.target)}</div>`;
  const sections=[...document.querySelectorAll('main>.section')],links=[...document.querySelectorAll('.sidebar nav a')];
  let scrolling=false;
  window.addEventListener('scroll',()=>{if(scrolling)return;scrolling=true;requestAnimationFrame(()=>{let current=sections[0].id;for(const s of sections)if(s.getBoundingClientRect().top<160)current=s.id;links.forEach(a=>{const active=a.hash===`#${current}`;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});scrolling=false;});},{passive:true});
})();
