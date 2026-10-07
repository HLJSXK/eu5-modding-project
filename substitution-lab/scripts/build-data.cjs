// Static snapshots allow the entire site to work from file://, without a backend.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const revision = '9670e1414d8e2ce5c692672adc588f485baf167c';
const historical = file => execFileSync('git', ['show', `${revision}:${file}`], { cwd: root, encoding: 'utf8', maxBuffer: 8e6 }).replace(/\r/g, '');
const read = file => fs.readFileSync(path.join(root, file), 'utf8').replace(/^\uFEFF/, '').replace(/\r/g, '');
const sv = 'src/stable/in_game/common/script_values/';
function block(text, name) {
  const start = text.indexOf(name + ' = {');
  if (start < 0) throw new Error(`Missing block ${name}`);
  let depth = 0;
  for (let i = text.indexOf('{', start); i < text.length; i++) {
    if (text[i] === '{') depth++;
    if (text[i] === '}' && --depth === 0) return { text: text.slice(start, i + 1), line: text.slice(0, start).split('\n').length };
  }
  throw new Error(`Unclosed block ${name}`);
}
function csv(file) {
  const rows = read(file).trim().split('\n').map(line => line.split(','));
  const header = rows.shift();
  return rows.map(row => Object.fromEntries(header.map((h, i) => [h, row[i]])));
}
const names = {
  basic_clothing:'基本衣物', crude_goods:'粗制品', staple:'主食', condiments:'调味品', heating:'取暖燃料', household:'家居用品', standard_clothing:'标准衣物', intoxicants:'嗜好饮料', luxury_drinks:'奢侈饮品', luxury_food:'奢侈食物', luxury_goods:'奢侈商品', protein:'蛋白食物', spices:'香料', precious:'贵重品', treasures:'珍宝', medicine:'药品', ritual:'祭祀物品', weapons:'武器', mounts:'坐骑', knowledge:'知识用品'
};
const goodNames = {
  cloth:'布料', leather:'皮革', lumber:'木材', masonry:'石材', tools:'工具', pottery:'陶器', wheat:'小麦', rice:'稻米', millet:'小米', maize:'玉米', potato:'马铃薯', legumes:'豆类', sugar:'糖', salt:'盐', olives:'橄榄', coal:'煤炭', beeswax:'蜂蜡', furniture:'家具', glass:'玻璃', paper:'纸张', fine_cloth:'精细布料', wine:'葡萄酒', beer:'啤酒', liquor:'烈酒', tobacco:'烟草', tea:'茶叶', coffee:'咖啡', cocoa:'可可', wild_game:'野味', victuals:'加工食品', fruit:'水果', fish:'鱼类', fur:'毛皮', porcelain:'瓷器', lacquerware:'漆器', marble:'大理石', livestock:'牲畜', saffron:'藏红花', pepper:'胡椒', cloves:'丁香', chili:'辣椒', goods_gold:'黄金', silver:'白银', jewelry:'珠宝首饰', amber:'琥珀', gems:'宝石', ivory:'象牙', pearls:'珍珠', medicaments:'药材', mercury:'水银', incense:'熏香', weaponry:'兵器', firearms:'火器', horses:'马匹', elephants:'大象', camels:'骆驼', books:'书籍'
};
const weightFile = sv + 'SOL_goods_weight_values.txt';
const demandFile = sv + 'SOL_goods_demand_values.txt';
const weights = historical(weightFile), demands = historical(demandFile);
const groups = Object.entries(names).map(([id, name], index) => {
  const b = block(weights, `SOL_${id}_total_weight`);
  const members = [...b.text.matchAll(/add = SOL_(\w+)_weight/g)].map(m => m[1]);
  const n = Number(demands.match(new RegExp(`GROUP \\d+: ${id.toUpperCase()} \\(N=(\\d+)\\)`))?.[1]);
  if (!n || !members.length) throw new Error(`Invalid group ${id}`);
  return { id, name, index: index + 1, n, members, line: b.line };
});
const sources = {};
function source(id, title, file, rev, content, first = 1, last = Infinity) {
  const lines = content.split('\n');
  sources[id] = { title, path: file, revision: rev, line: first, text: lines.slice(first - 1, last).join('\n') };
}
source('history-demand', 'v1.1 · 单组需求公式', demandFile, revision, demands, 1, 50);
source('history-overlap', 'v1.1 · 11 种跨组商品取平均', demandFile, revision, demands, 678, 745);
for (const good of new Set(groups.flatMap(g => g.members))) {
  const b = block(weights, `SOL_${good}_weight`);
  sources[`weight-${good}`] = { title: `v1.1 · ${goodNames[good]}的完整权重与偏好`, path: weightFile, revision, ...b };
}
for (const g of groups) {
  const b = block(weights, `SOL_${g.id}_total_weight`);
  sources[`group-${g.id}`] = { title: `v1.1 · ${g.name}成员`, path: weightFile, revision, ...b };
}
const historicalFiles = [
  ['history-entry','v1.1 · POP 需求入口','src/stable/in_game/common/goods_demand/z_SOL_pop_demand.txt',1,110],
  ['history-tiers','v1.1 · 市场价格列表','src/stable/in_game/common/scripted_effects/SOL_substitute_effects.txt',1,152],
  ['history-scale','v1.1 · 阶层组缩放',sv+'z_SOL_group_demand_scales_location.txt',1,70],
  ['history-pulse','v1.1 · 年度与月度刷新','src/stable/in_game/common/situations/SOL_economy_situation.txt',1,80],
  ['history-scarcity','v1.1 · 稀缺总量补偿','src/stable/in_game/common/scripted_effects/z_SOL_scarcity_score.txt',1,65],
  ['history-full-refresh','v1.1 · 全刷新与时代系数','src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt',1280,1360]
];
historicalFiles.forEach(([id,title,file,a,b])=>source(id,title,file,revision,historical(file),a,b));
const currentRevision = execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
const currentFiles = [
  ['implementation','修订后的国家级实施规格','docs/technical/SOL_Substitute_Groups_Global_Modifier_Implementation.md',1,Infinity],
  ['audit','恢复文档审计与数值反例','docs/technical/SOL_Substitute_Groups_Global_Modifier_Audit.md',1,Infinity],
  ['early-design','早期十组设计草案（非 v1.1 事实）','docs/technical/SOL_Per_Group_Demand_Design_Prompt.md',1,65],
  ['modifier-types','global / local / 商品接口定义','reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt',12773,12815],
  ['static-example','原版国家静态修正范例','reference_game_files/game/main_menu/common/static_modifiers/institutions.txt',57,63],
  ['modifier-add','官方 add_country_modifier 效果','reference_official_defines/docs/effects.log',103,112],
  ['modifier-remove','官方 remove_country_modifier 效果','reference_official_defines/docs/effects.log',10361,10366],
  ['current-market','当前市场支出缓存入口','src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt',212,290],
  ['current-location','当前地点支出与 raw 系数','src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt',3214,3290],
  ['current-apply','当前月度地点修正写入','src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt',4029,4063],
  ['current-groups','当前商品组 CSV','data/goods_weights.csv',1,Infinity],
  ['current-units','当前净单位消费量（非 demand_add）','data/demand_price_table.csv',1,Infinity],
  ['age-modifiers','原版时代商品需求修正','reference_game_files/game/in_game/common/age/00_default.txt',1,120]
];
currentFiles.forEach(([id,title,file,a,b])=>source(id,title,file,`工作树 @ ${currentRevision.slice(0,8)}`,read(file),a,b));
const budgetText = historical(sv+'z_SOL_group_budget_shares.txt');
const offsetText = historical(sv+'z_SOL_group_demand_offsets.txt');
const priceText = historical(sv+'z_SOL_group_prices.txt');
function piecewise(text, name) {
  const b = block(text, name);
  const base = Number(b.text.match(/value = (-?[\d.]+)/)[1]);
  const changes = [...b.text.matchAll(/>= ([\d.]+) } add = (-?[\d.]+)/g)].map(m=>[Number(m[1]),Number(m[2])]);
  return { base, changes };
}
const curves = {};
for (const s of ['nobles','clergy','burghers','commoners']) {
  curves[s] = {};
  for (const g of groups) {
    const p = block(priceText, `local_${s}_${g.id}_P`);
    const base = block(historical(sv+'z_SOL_group_demand_base_location.txt'),`local_${s}_${g.id}_demand_base`);
    curves[s][g.id] = { price:Number(p.text.match(/value = ([\d.]+)/)[1]), share:piecewise(budgetText,`local_${s}_${g.id}_budget_share`), offset:piecewise(offsetText,`local_${s}_${g.id}_demand_offset`), constantBase:base.text.includes('divide =')?null:Number(base.text.match(/value = ([\d.]+)/)[1]) };
  }
}
source('history-budgets','v1.1 · 全部阶层预算分段',sv+'z_SOL_group_budget_shares.txt',revision,budgetText);
source('history-prices','v1.1 · 组篮子基准总价',sv+'z_SOL_group_prices.txt',revision,priceText);
source('history-offsets','v1.1 · 连续性偏移',sv+'z_SOL_group_demand_offsets.txt',revision,offsetText);
source('history-bases','v1.1 · 全部需求基线与固定中性值',sv+'z_SOL_group_demand_base_location.txt',revision,historical(sv+'z_SOL_group_demand_base_location.txt'));
const units = {};
for (const row of csv('data/demand_price_table.csv')) if (!units[row.good]) units[row.good] = { price:Number(row.price), ...Object.fromEntries(['nobles','clergy','burghers','laborers','peasants','soldiers','tribesmen'].map(s=>[s,Number(row[s])])) };
const currentGroups = Object.keys(names).map(id=>({ ...groups.find(g=>g.id===id), members:csv('data/goods_weights.csv').filter(row=>row.group===id).map(row=>row.good) }));
const typeText = read('reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt');
const interfaces = Object.fromEntries(Object.keys(goodNames).map(g=>[g,typeText.includes(`global_${g}_pop_demand`)]));
const data = { revision, currentRevision, snapshotDate:'2026-10-07', groups, currentGroups, goodNames, curves, sources, units, interfaces };
fs.writeFileSync(path.join(__dirname,'../data.js'),`/* Generated by npm run snapshot. Historical commit is pinned. */\nwindow.SOL_DATA = ${JSON.stringify(data)};\n`);
console.log(`Snapshot: ${groups.length} groups, ${new Set(groups.flatMap(g=>g.members)).size} historical goods, ${Object.keys(sources).length} source records.`);
