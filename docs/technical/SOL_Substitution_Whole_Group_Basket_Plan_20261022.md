# SOL 替代组：整组消费修改计划

日期：2026-10-22。状态：已按建议实施，实机验收待完成。下文估算与附录保留为迁移前计划，最终实现及验证见 `SOL_Substitution_Implementation_20261013.md`。数据口径：迁移前的 `data/demand_price_table.csv`、`data/goods_weights.csv`、`data/substitute_groups.json`。
复算脚本：`docs/analysis/substitution_whole_group_20261022/estimate.py`（只读，不写文件）。

实施采用第 6 节全部建议：平民订阅基本衣物、保留士兵奢侈饮品、补市民土豆和教士奢侈品，以平均金额补齐后缩回旧预算。最终数量见 `data/target_demand.csv`，实际支出审计见 `docs/analysis/substitution_whole_group_20261022/implementation_results.json`。共享商品连接的组在分配金额累加后一起取整；石材保留原版乘算后可由五位小数差量生成的净值格点，因此不承诺附录中每组最终独立预算严格不变。原估算脚本依赖当前数据，迁移后不再复现历史旧值。

## 1. 问题

运行时把“某阶层消费哪些组”隐式地从校准数量推出来：`sol_substitution.py` 的 `render_country_runtime()` 里
`used = [good for good in CORE if round(quantities[good][pop], 5) > 0]`，然后每组只取 `used` 里的成员。于是一个组里只要有一种商品
数量为 0，这个组对该阶层就缩成了残缺的小组。

调味品（糖、盐、橄榄）就是这样：劳工、农民、士兵只消费橄榄，组对他们只剩一个成员，倍率恒为 1。他们占 CAS 橄榄基线约 78%，
贵族/教士/市民的正常反应被稀释掉（存档核查：CAS 橄榄国家倍率只有 1.086）。用估算脚本的示例（糖无供应、橄榄便宜权重 2、盐权重 1）：
现在橄榄国家倍率 1.055，改为整组后所有阶层都是 1.333；盐 0.667 不变。

这不是个别数据错误。按当前表逐格扫描，六个阶层共有 **35 个“只消费一部分”的格子**（tribesmen 没有任何组需求）：

| 组 | nobles | clergy | burghers | laborers | peasants | soldiers |
| --- | --- | --- | --- | --- | --- | --- |
| 基本衣物 `basic_clothing` | ✓ | 退订 | 退订 | 补齐 | 补齐 | 补齐 |
| 粗制品 `crude_goods` | 补齐 | 补齐 | 补齐 | ✓ | 补齐 | 补齐 |
| 主食 `staple` | ✓ | ✓ | 补齐 | ✓ | ✓ | ✓ |
| 奢侈食物 `luxury_food` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 调味品 `condiments` | ✓ | ✓ | ✓ | 补齐 | 补齐 | 补齐 |
| 取暖燃料 `heating` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 家居用品 `household` | ✓ | 补齐 | ✓ | 补齐 | 补齐 | 补齐 |
| 标准衣物 `standard_clothing` | ✓ | ✓ | ✓ | 退订 | 退订 | 退订 |
| 嗜好饮料 `intoxicants` | ✓ | ✓ | ✓ | 补齐 | 补齐 | 补齐 |
| 奢侈饮品 `luxury_drinks` | ✓ | ✓ | ✓ | 退订 | 退订 | 补齐 |
| 奢侈商品 `luxury_goods` | ✓ | 补齐 | ✓ | — | — | — |
| 蛋白食物 `protein` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 香料 `spices` | ✓ | ✓ | ✓ | — | — | — |
| 贵重品 `precious` | ✓ | — | ✓ | — | — | — |
| 珍宝 `treasures` | ✓ | — | ✓ | — | — | — |
| 药品 `medicine` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 祭祀物品 `ritual` | 退订 | ✓ | 退订 | 退订 | 退订 | 退订 |
| 武器 `weapons` | ✓ | — | — | 补齐 | 补齐 | ✓ |
| 坐骑 `mounts` | ✓ | — | — | — | — | — |
| 知识用品 `knowledge` | ✓ | ✓ | ✓ | — | — | — |

✓ 已是整组；— 整组不消费；“补齐”“退订”是本计划对 35 个残缺格的建议（23 补齐、12 退订，见第 3 节）。

## 2. 新规则（不变量）

1. 阶层消费的单位是组。每个（阶层，组）只有“订阅”或“不订阅”两种状态，由一张显式表决定，不再从数量反推。
2. 订阅的组，**每个成员**的校准数量都大于 0（五位小数取整后至少 0.00001）。
3. 阶层消费的商品集合 **恰好等于** 其订阅组成员的并集：不允许有不属于任何订阅组的商品，也不允许订阅组里有 0。
4. 不属于任何组的商品（JTG 的 26 种额外商品、PP 的 victuals 兼容处理）不受此约束，仍按现状中性处理。
5. 市场层面的“无供应”“外部需求为 0”仍在运行时把成员排除；这对同一市场、同一国家的所有阶层一致，不属于“部分阶层残缺”。

生成器和测试都要硬性检查第 2、3 条，违反即失败。

## 3. 每个残缺格怎么处理

### 3.1 判定规则（建议）

- **退订**：该格已消费的成员全都能由此阶层另一个订阅组覆盖，那么这个组本来就是“借道”，直接退订，数量一个都不用改。
  例：劳工/农民的奢侈饮品只有葡萄酒，而葡萄酒已在嗜好饮料里；各阶层祭祀物品里的水银已在药品里。
- **补齐**：该格有“只属于这个组”的已消费商品（例：调味品里的橄榄、粗制品里的石材、奢侈商品里的皮草/瓷器），组必须保留，缺的成员补上数量。

按此规则得出的 23 补齐 / 12 退订见上表。剩下三处需要人工拍板（第 6 节）：平民的衣物走哪个组、士兵的奢侈饮品、市民的土豆。

### 3.2 补多少：守住每组预算（建议）

对每个（阶层，订阅组）：

1. 现有组预算 = 组内已消费成员的“数量 × 默认价”之和；跨组商品按其订阅组个数平分（与运行时的跨组平均口径一致）。
2. 缺的成员先给“组内已有成员的平均份额”，然后整组按比例缩回原预算。也就是组的总花费不变，原有成员的相对比例不变，新成员拿到平均一份。
3. 数量 = 金额 / 默认价，五位小数取整；订阅组成员最低 0.00001。取整用“最大余数”分配，让每组预算误差不超过一个最小单位。

效果（默认价下阶层总花费）：贵族/教士/市民 ±0.0%，劳工 +0.4%、农民 +0.7%、士兵 +0.5%（来自最低 0.00001 的抬高）。

调味品的例子，劳工/农民/士兵：糖 0 → 0.00003，盐 0 → 0.00002，橄榄 0.00025 → 0.00008。完整新旧数量表见附录。

**不建议“只加不减”**（原有数量不动，缺的按平均份额加上去）：平民总花费会 +23%～+27%，求解器把总额压回收入后，所有已有商品被等比例摊薄，
主食玉米约 −18%、鱼约 −15%，等于把替代组的修正外溢到了与之无关的组。守预算方案把变化限制在组内。

### 3.3 对世界商品量的影响（HUN 1337 人口结构估算，平民占约 98%）

变化大的：工具 +101%、玻璃 +74%、土豆 +20%、皮革 +19%、烟草 +10%、糖 +9%、盐 +4%；橄榄 −57%、陶器 −29%、木材 −14%、蜂蜡 −13%、家具 −10%、啤酒 −9%。
其余在 ±6% 以内。这些是基线需求（替代前）的移动，会改变各地生产和价格，需要观察局确认没有某个商品被推到长期短缺。
橄榄 −57% 是因为平民原来把整组调味品预算都花在橄榄上，现在三样平分；如果认为平民的调味品主要就是橄榄，可以在第 6 节改用“按价格反比”或保留比例分配。

## 4. 代码改动

按执行顺序：

1. **新数据表** `data/pop_group_baskets.csv`：行 = 20 个组，列 = 7 个阶层，值 0/1。这是订阅关系的唯一来源。
   `substitute_groups.json` 的 notes 增一条说明；`goods_weights.csv` 的成员关系不动。
2. **一次性迁移 + 常驻检查** 新脚本 `scripts/gen_whole_group_baskets.py`（带 stdout UTF-8 块）：
   - `--fill`：按 3.2 规则改写 `data/target_demand.csv` 中受影响的格，打印每格新旧值和组预算误差；
   - `--check`：只校验第 2 节不变量，失败返回非零。接入 `gen_sol_chain.py`，放在 `gen_pop_goods.py` 之前。
   - 注意 `target_demand.csv` 与 `demand_price_table.csv` 现有 5 处石材数值不一致（原版 demand_add 叠加后的净值），迁移以净值表为准反算 `target_demand`，并在脚本里断言迁移后两表一致。
3. **`gen_pop_goods.py`**：加载时调用同一检查。新增需求的商品（盐、工具、玻璃、纸、烟草、火器、茶、可可、漆器、大理石等）的原版财富门槛和发展度门槛已在 `target_demand.csv` 中全部抵消，生成器已有强制检查，不需改动规则。
4. **`sol_substitution.py`**：
   - 读入订阅表，暴露 `SUBSCRIBED[pop] -> [group]`；模块加载时断言订阅组成员与数量 > 0 的商品集合完全一致。
   - `render_country_runtime()` 的阶层循环改为遍历订阅组，删除 `used` 推断；跨组平均只计订阅组。
   - `response()` 加一个 `groups` 按阶层传入的调用路径，测试用。
   - `render_location_spending()`、`market_details()` 仍按数量 > 0 生成，迁移后自然与订阅一致，不必改。
5. **兼容生成器**：
   - PP：木材全阶层强制为 0，粗制品和取暖燃料在 PP 下对所有阶层都少木材。这是目标级的成员删除，对所有阶层一致，不算残缺；PP 的订阅检查和 PP 版运行时都要把 lumber 从这两组成员中去掉（`render_country_runtime()` 接收“目标级移除成员”参数），不能因此报错，也不能让 lumber 以 0 数量留在组里参与分母。
   - M&T：`_compat_quantities()` 按价格换算并重新取整，0.00001 级的平民数量可能被舍成 0。对 M&T 结果跑同一检查，舍成 0 的成员抬到 0.00001。
   - JTG：额外商品无组，不受影响；只需重新生成。
6. **测试** `scripts/test_sol_substitution.py`：
   - 新增：各目标（stable、standalone、PP、M&T）都满足不变量；
   - 新增：只有平民的市场里，调味品在糖无供应、橄榄便宜时，橄榄倍率等于单阶层 D（不再是 1）；
   - 新增：退订组不出现在该阶层的运行时块中（例如劳工块里没有 `sol_sub_neutral_tea`）；
   - 现有 `test_generated_overlap_matches_independent_response` 改用订阅组计算期望值。
7. **重新生成与校验**：`gen_sol_chain.py`、`gen_sol_chain.py --check`、两个替代测试、`validate.py --changed`。
8. **文档**：更新 `SOL_Substitution_Implementation_20261013.md` 的口径段、`PROJECT_OVERVIEW.md` 第 13 项，
   在 `anti_patterns.yaml` 记一条“从数量推断组成员导致残缺组”，然后 `gen_brief.py`。

运行时成本：（阶层，组，商品）三元组从 271 增到 291，约 +7%，在既有年度/月度节奏下可忽略。

## 5. 实机验收

1. CAS 1368 存档：同一状态下比较改前改后橄榄、盐、糖的国家倍率；预期橄榄倍率明显高于 1.086，且与仅按贵族/教士/市民计算的值接近。
2. error.log 无新增错误；商品悬停的组成员显示不变。
3. 观察局 50 年：检查第 3.3 节变化大的商品（工具、玻璃、橄榄、陶器）价格是否长期卡在最高或最低档。
4. 平民各组的实际人口需求与生成的单位消费常量一致（确认 0.00001 级需求能被引擎读到，不被舍成 0）。

## 6. 待拍板

1. 判定规则：能被别的组覆盖就退订，否则补齐（建议）。
2. 平民（劳工/农民/士兵）的布：放进基本衣物（补皮革，建议）还是标准衣物（补精布）。平民用精布不太合理。
3. 士兵的奢侈饮品：士兵原版就喝咖啡，咖啡只在这个组里。建议保留并补茶、可可；另一个选择是把士兵的咖啡去掉、整组退订。
4. 市民的主食：现在除土豆外都吃，土豆被刻意设成 0。补齐（建议）还是另有原因。
5. 补齐的分配方式：新成员拿“组内平均一份”（建议）；或按价格反比（便宜的多拿）；或只加不减（不建议，见 3.2）。
6. 教士的奢侈商品：皮草和瓷器只在这个组，必须保留，所以要补漆器、大理石、玻璃。也可以改为删掉教士的皮草和瓷器、整组退订。

## 不在本计划范围

- 价格档位上限 2.0 使三成员组最多 ×1.41 的问题。
- 替代修正本地化键缺 `STATIC_MODIFIER_NAME_` 前缀，游戏里显示原始键（另行小修）。

## 附录：补齐后的新数量（守预算方案，五位小数）

只列有变化的（阶层，组）；跨组商品在每个所属组里重复出现，值相同。

| 阶层 | 组 | 成员：现值 → 建议值 |
| --- | --- | --- |
| nobles | `crude_goods` | lumber 0.002→0.00175，masonry 3e-05→2e-05，tools 0→0.00025，pottery 0.003→0.00263 |
| nobles | `heating` | lumber 0.002→0.00175，coal 0.004→0.004，beeswax 0.003→0.003 |
| nobles | `household` | furniture 0.03→0.03，pottery 0.003→0.00263，glass 0.015→0.015，paper 0.015→0.015，beeswax 0.003→0.003 |
| clergy | `crude_goods` | lumber 0.0012→0.00105，masonry 2e-05→1e-05，tools 0→0.00016，pottery 0.002→0.00155 |
| clergy | `heating` | lumber 0.0012→0.00105，coal 0.0025→0.0025，beeswax 0.002→0.0018 |
| clergy | `household` | furniture 0.01→0.008，pottery 0.002→0.00155，glass 0→0.00756，paper 0.04→0.036，beeswax 0.002→0.0018 |
| clergy | `standard_clothing` | cloth 0.02→0.02，fine_cloth 0.008→0.006 |
| clergy | `luxury_goods` | fine_cloth 0.008→0.006，fur 0.01→0.005，porcelain 0.0015→0.00075，lacquerware 0→0.00162，marble 0→0.00162，glass 0→0.00756 |
| clergy | `knowledge` | paper 0.04→0.036，books 0.01→0.01 |
| burghers | `crude_goods` | lumber 0.00375→0.00328，masonry 6e-05→4e-05，tools 0→0.00054，pottery 0.0072→0.0063 |
| burghers | `staple` | wheat 0.0075→0.00625，rice 0.003→0.0025，millet 0.012→0.01，maize 0.024→0.02，potato 0→0.00875，legumes 0.006→0.005 |
| burghers | `heating` | lumber 0.00375→0.00328，coal 0.0075→0.0075，beeswax 0.006→0.006 |
| burghers | `household` | furniture 0.03→0.03，pottery 0.0072→0.0063，glass 0.015→0.015，paper 0.06→0.06，beeswax 0.006→0.006 |
| laborers | `basic_clothing` | cloth 4e-05→2e-05，leather 0→2e-05 |
| laborers | `crude_goods` | lumber 6e-05→6e-05，masonry 1e-05→1e-05，tools 0.00025→0.00025，pottery 0.00035→0.00028 |
| laborers | `condiments` | sugar 0→3e-05，salt 0→2e-05，olives 0.00025→8e-05 |
| laborers | `heating` | lumber 6e-05→6e-05，coal 2e-05→2e-05，beeswax 0.00012→0.0001 |
| laborers | `household` | furniture 5e-05→3e-05，pottery 0.00035→0.00028，glass 0→3e-05，paper 0→4e-05，beeswax 0.00012→0.0001 |
| laborers | `intoxicants` | wine 5e-05→4e-05，beer 0.0001→7e-05，liquor 5e-05→4e-05，tobacco 0→4e-05 |
| laborers | `weapons` | weaponry 6e-05→3e-05，firearms 0→3e-05 |
| peasants | `basic_clothing` | cloth 2e-05→1e-05，leather 0→1e-05 |
| peasants | `crude_goods` | lumber 6e-05→5e-05，masonry 1e-05→1e-05，tools 0→2e-05，pottery 0.0003→0.0002 |
| peasants | `condiments` | sugar 0→3e-05，salt 0→2e-05，olives 0.00025→8e-05 |
| peasants | `heating` | lumber 6e-05→5e-05，coal 2e-05→2e-05，beeswax 0.00012→0.0001 |
| peasants | `household` | furniture 5e-05→3e-05，pottery 0.0003→0.0002，glass 0→3e-05，paper 0→4e-05，beeswax 0.00012→0.0001 |
| peasants | `intoxicants` | wine 5e-05→4e-05，beer 0.0001→7e-05，liquor 5e-05→4e-05，tobacco 0→4e-05 |
| peasants | `weapons` | weaponry 6e-05→3e-05，firearms 0→3e-05 |
| soldiers | `basic_clothing` | cloth 5e-05→2e-05，leather 0→2e-05 |
| soldiers | `crude_goods` | lumber 6e-05→5e-05，masonry 1e-05→1e-05，tools 0→2e-05，pottery 0.0003→0.0002 |
| soldiers | `condiments` | sugar 0→3e-05，salt 0→2e-05，olives 0.00025→8e-05 |
| soldiers | `heating` | lumber 6e-05→5e-05，coal 2e-05→2e-05，beeswax 0.00012→0.0001 |
| soldiers | `household` | furniture 5e-05→3e-05，pottery 0.0003→0.0002，glass 0→3e-05，paper 0→4e-05，beeswax 0.00012→0.0001 |
| soldiers | `intoxicants` | wine 5e-05→3e-05，beer 0.00025→0.00019，liquor 0.0001→8e-05，tobacco 0→7e-05 |
| soldiers | `luxury_drinks` | tea 0→7e-05，coffee 0.00025→0.00013，wine 5e-05→3e-05，cocoa 0→5e-05 |

附录用简单四舍五入；实施时改为最大余数取整。平民数量在 0.00001 量级，单项取整误差可达 ±20%（如士兵布 0.000025 → 0.00002），
这是五位小数精度的限制，最大余数法只能保证组预算误差在一个最小单位内。
