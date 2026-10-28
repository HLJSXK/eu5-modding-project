# SOL 原版人口需求控制审计

审计日期：2026-10-27。对象：当前 `beta` 工作区的 stable / standalone 生成源与本机原版；兼容目标只核查本问题涉及的继承关系。结论：**尚未完整接管原版人口需求。商品偏好应迁入 SOL 权重，原版直接需求通道应在同一次迁移中中和。** 本次工作记录审计与迁移要求，没有修改游戏运行时。

## 1. 结论和证据边界

全树搜索原版脚本中的 `global_*_pop_demand`、`global_pop_demand`、`local_pop_demand`，并扩展检查 `industry_types.pop_demand`、文化/宗教需求块、goods 条件字段、`goods_demand/pop_demands.txt` 与需求相关 defines。21 个主要来源文件及 `pop_demands.txt` 共 22 个文件与本机安装目录逐字节一致。这里的“原版”指该本机安装和共享镜像，不推断其他游戏版本。

发现三种不同问题：

1. **计算输入遗漏。** 文化/宗教、商品的地区/气候/冬季/疾病等字段仍加载；SOL 单位支出没有读取这些因素。`pop_demands.txt` 还留有小麦 0.75、水果 0.5。只验证 `demand_add` 与 CSV 一致，不能证明原生最终需求与 SOL 基础支出一致。
2. **控制权仍在原版，但不等于完全漏算。** 国家逐商品 modifier 被 `sol_substitution.py:218-220` 读取为 external，随后进入 `sol_good_effective_*` 和支出。它们没有转为组内权重，而是保留为最终需求的外部倍率。刷新以后这部分已被记账；刷新以前原生 modifier 变化与缓存之间还存在时间差。
3. **引擎缩放需要单独验证。** 原版仍配置收入赤字缩减、价格弹性、市场自产偏好和缺粮相关需求系数。注释足以确认部分用途，但闭源调用顺序、适用商品及与 SOL modifier 的合成方式不能由这些文本完整证明。

原版脚本中未找到另一处直接赋值的 `local_pop_demand`；本轮找到的通用 `global_pop_demand` 来源是自由民社会价值。类型声明、图标、查询值不算施加来源。事件多通过授予下述 static modifier 生效，不能只扫描事件内的逐商品字段。

## 2. 国家级直接需求来源

路径均相对 `.eu5-base/reference_game_files/game/`；行号为本次镜像。

| 来源 | 商品和原始数值 | 证据 | 权重迁移要求 |
| --- | --- | --- | --- |
| 六个时代的 `goods_demand` | liquor、tobacco、coffee、sugar、tea，共 30 项（含 0 占位） | `in_game/common/age/00_default.txt:15,79,140,205,284,357` | 时代偏好进入对应商品权重，去掉直接需求加成；保留其余时代效果 |
| 印刷术 `printing_press_books` | books +0.2 | `main_menu/common/static_modifiers/institutions.txt:57`；`in_game/common/on_action/_hardcoded.txt:5810` | 保留原授予条件，转成书籍偏好 |
| 圣公会祭服 `anglican_vestments_modifier` | fine_cloth +1 | `main_menu/common/static_modifiers/country.txt:13740`；`in_game/events/religion/anglican_events.txt:465` | 保留事件选择及永久效果生命周期，改为精布偏好 |
| 葡萄牙印刷条例 `por_printing_ordinances_modifier` | paper +1 | `main_menu/common/static_modifiers/country.txt:13745`；`in_game/events/DHE/flavor_por.txt:3566` | 保留事件生命周期，改为纸张偏好 |
| 一条鞭法 `single_whip_law` | silver +1 | `in_game/common/government_reforms/country_specific.txt:2269,2279` | 白银偏好；保留税收效率等其他效果 |
| 清洁派鱼素主义 `pescatarianism` | livestock -1 | `in_game/common/religious_aspects/catharism.txt:14,20` | 畜牧品权重为零；保留进口禁令和鱼类产出加成 |
| 自由民社会价值 | 全商品 `global_pop_demand = 0.2`，位于 `serfdom_vs_free_subjects.right_modifier` | `in_game/common/societal_values/00_default.txt:125,146` | 这是总量效果，无法无损变成相对商品权重，见第 7 节 |

逐商品显式赋值合计 **35 项**，另有 **1 项全商品赋值**。时代原值如下，均为 modifier 的加性数值，不是直接的偏好权重：

| 时代 | liquor | tobacco | coffee | sugar | tea |
| --- | ---: | ---: | ---: | ---: | ---: |
| traditions | -0.75 | -0.75 | -0.5 | -0.25 | -0.25 |
| renaissance | -0.5 | -0.75 | -0.5 | -0.1 | -0.25 |
| discovery | 0 | -0.25 | -0.25 | 0.25 | -0.1 |
| reformation | 0.5 | 0.5 | 0 | 0.75 | 0 |
| absolutism | 1 | 1 | 0.5 | 1.25 | 0.5 |
| revolutions | 1.5 | 1.5 | 1.25 | 1.75 | 1.5 |

### 产业扶持的隐式来源

`in_game/common/industry_types/01_industries.txt:1-16` 明确说明：引擎按照 `goods` 列表，为每个商品生成国家 `global_<good>_pop_demand`。因此扫描显式 modifier 名不能发现全部来源。八类均引用 `industry_promotion_pop_demand`；其值在 `main_menu/common/script_values/default_values.txt:1374` 为 **0.5**。

| 产业 | goods | 赋值行 |
| --- | --- | ---: |
| textiles | cloth, fine_cloth | 26 |
| crafts | tools, steel, leather, masonry | 36 |
| arms | weaponry, firearms, cannons | 46 |
| luxury | glass, jewelry, porcelain, lacquerware | 56 |
| paper_goods | paper, books | 66 |
| furnishings | furniture, pottery | 76 |
| naval | naval_supplies, tar | 86 |
| beverages | wine, liquor, beer | 96 |

共 22 个商品；steel、cannons、naval_supplies、tar 不属于当前 56 商品核心，不能因为改权重而为它们凭空增加人口订阅。迁移需同步中和生成需求的入口，按实际扶持状态赋予偏好，保留产业产出效果。多个地区扶持的叠加语义需验证，不能假定每个国家只有一个布尔状态。

## 3. 文化和宗教需求

共 **25 个对象、27 个需求块、88 个商品条目**：7 个文化组、7 个文化、4 个宗教组、7 个宗教。以下是字段原值；这里 `0` 表示禁用因子、`1.2` 表示倍率，不能当作国家 modifier 的 +120% 再加一。文化组与具体文化、宗教组与具体宗教的实际合成顺序仍需迁移测试覆盖。

### 文化组与具体文化

| 对象 | 商品原值 | 文件与对象起始行 |
| --- | --- | --- |
| andean_group | wine .5; liquor .5; beer 2; medicaments 4; goods_gold 2; tobacco .1; potato 4; maize .25; wild_game 2 | `culture_groups/00_culture_groups.txt:12` |
| baltic_group | wine 1.2; liquor .8; beer .8; millet 2; wheat .8; legumes 1.2; wild_game 1.2; livestock .8 | `culture_groups/00_culture_groups.txt:38` |
| greek_group | olives 1.2 | `culture_groups/00_culture_groups.txt:96` |
| iberian_group | olives 1.2 | `culture_groups/00_culture_groups.txt:111` |
| italian_group | olives 1.2 | `culture_groups/00_culture_groups.txt:129` |
| japanese_group | wine .5; liquor 2; beer 0 | `culture_groups/00_culture_groups.txt:135` |
| maghrebi_group | tea 2; saffron 1.2; millet 1.5; wheat .8; legumes 1.2; livestock 1.2; olives 1.2; fruit 1.1 | `culture_groups/00_culture_groups.txt:152` |
| lower_egyptian_culture | tea 1.5; saffron 1.2; millet .1; wheat 1.5; legumes 2; livestock .5; wild_game .25; fish .5 | `cultures/egypt.txt:1` |
| upper_egyptian_culture | 同上 | `cultures/egypt.txt:31` |
| languedocien | olives 1.2 | `cultures/french.txt:389` |
| provencal | olives 1.2 | `cultures/french.txt:518` |
| albanian | olives 1.2 | `cultures/south_slavic.txt:106` |
| turkish_culture | tea 2; saffron 1.5; legumes 1.2; livestock 1.5; olives 1.2 | `cultures/turkic.txt:3` |
| turkoman_culture | 同上 | `cultures/turkic.txt:31` |

本节文件路径前缀为 `in_game/common/`。

### 宗教组与具体宗教

| 对象 | 普通需求原值 | clergy 专属原值 | 文件与对象起始行 |
| --- | --- | --- | --- |
| christian | — | wine 10 | `religion_groups/00_default.txt:1` |
| muslim | wine 0; beer 0; liquor 0 | — | `religion_groups/00_default.txt:15` |
| israelite_group | — | wine 10 | `religion_groups/00_default.txt:59` |
| folk_peruvian_group | — | medicaments 2; livestock 1.5 | `religion_groups/00_default.txt:189` |
| shinto | — | wine 10 | `religions/buddhist.txt:43` |
| catholic | fish 1.25 | incense 2 | `religions/christian.txt:192` |
| miaphysite | livestock .5 | incense 2 | `religions/christian.txt:369` |
| orthodox | — | incense 2 | `religions/christian.txt:435` |
| hindu | livestock .25 | — | `religions/dharmic.txt:1` |
| jain | wine, liquor, beer, fur, ivory, weaponry, firearms, fish, livestock, potato, wild_game 均为 0 | — | `religions/dharmic.txt:41` |
| sikhism | wine, liquor, beer 均为 0 | — | `religions/dharmic.txt:92` |

不能用国教或主流文化代替每个 POP 的宗教/文化。尤其 clergy 专属规则不能扩散给其他阶层。国家统一商品 multiplier 无法精确表达这些差异；如果继续采用国家级近似，必须明确聚合误差，而不能宣称保留了逐 POP 禁忌。

## 4. goods 内部条件修正

共 **18 个商品、24 个 modifier 字段、58 个数值条目**，当前基础目标的 `gen_pop_goods.py` 只处理基线和财富/发展门槛，没有中和这些字段。

| 商品 | 条件字段和原值 | 文件与对象起始行 |
| --- | --- | --- |
| coal | winter: none 0, mild .5, normal 1, severe 2; topography: mountains 1.2 | `goods/00_raw_materials.txt:28` |
| ivory | sub_continent: south_asia 1.2 | `goods/00_raw_materials.txt:321` |
| lumber | winter: none 0, mild .5, normal 1, severe 2; topography: mountains 1.2 | `goods/00_raw_materials.txt:343` |
| salt | winter: none .75, mild 1, normal 1.2, severe 2 | `goods/00_raw_materials.txt:384` |
| medicaments | disease_demand_modifier 2 | `goods/00_raw_materials.txt:410` |
| pearls | sub_continent: south_asia 2 | `goods/00_raw_materials.txt:458` |
| amber | market_unavailability_demand_modifier .5; region: scandinavian/north_german/baltic 各 1.5 | `goods/00_raw_materials.txt:481` |
| wine | region: iberia/italy/balkan 各 2; sub_continent: south_asia .6 | `goods/00_raw_materials.txt:521` |
| pepper | sub_continent: south_asia 1.5 | `goods/00_raw_materials.txt:699` |
| cloth | winter: none .5, mild 1, normal 1.5, severe 2 | `goods/02_produced_goods.txt:103` |
| liquor | region: iberia/italy/balkan 各 .5; scandinavian/ural/russian 各 2 | `goods/02_produced_goods.txt:151` |
| beer | region: iberia/italy/balkan 各 .5 | `goods/02_produced_goods.txt:183` |
| fur | winter: none 0, mild .5, normal 1, severe 2; topography: mountains 1.1 | `goods/03_food.txt:25` |
| wheat | continent: europe 2; climate: subtropical/tropical 各 .5 | `goods/03_food.txt:78` |
| rice | climate: subtropical/tropical 各 2 | `goods/03_food.txt:174` |
| millet | sub_continent: south_asia 1.2 | `goods/03_food.txt:223` |
| fruit | climate: arctic 0, cold_arid .5, tropical 1.2, mediterranean 1.4 | `goods/03_food.txt:494` |
| beeswax | winter: none .5, mild .5, normal 1.2, severe 2 | `goods/03_food.txt:521` |

表内省略字段尾缀 `_demand_modifier` 和 region 键尾缀 `_region`；路径前缀为 `in_game/common/`。这些是原生条件参数的原值，不代表已验证所有字段都采用同一种乘法公式。

同一市场可包含不同冬季、地形、气候和疾病状态。当前按“国家 × 市场 × pop_type”复用七项单位支出的缓存（`scripts/sol_substitution.py:117-153`），不能直接承载这些地点差异。把所有修正写入一份市场权重会把市场中心条件错误推广到所有成员地点。

另有资格/可用性入口，必须与软偏好分开迁移：

- maize 的 `demand_only_in_continent = america`，`goods/03_food.txt:171`。
- wild_game、rice、millet、legumes、olives、beeswax 的 `no_demand_if_no_market_availability = yes`，同文件第 22、220、269、289、491、556 行。
- 时代 `known_goods_demand_threshold` 为 100/80/60/40/20/10，见 `age/00_default.txt:5,57,118,179,246,326`。文本给出阈值，但不足以确认引擎解锁公式。

SOL 已有市场供应资格筛选，但不等于已证明与上述原生资格完全等价。资格应进入候选商品集合或零权重；不能让不可用商品参与分母，也不能把需求计算用于工业建设的普通 `goods_demand` 一并删除。

## 5. 其他绕过路径

### pop_demand 模板

`in_game/common/goods_demand/pop_demands.txt:2-6` 明确说明此对象由硬编码识别，并按 goods 中各 pop_type 的需求继续缩放。第 83 行 `wheat = 0.75`、第 84 行 `fruit = 0.5`；八个阶层 demand 对象在第 93-132 行 `copy_from = pop_demand`。

当前 src 没有接管该数据库；`gen_pop_goods.py` 和 `gen_market_unit_consumption.py` 也没有把这两个常数读入单位消费。迁移应使这层中性化，把对应相对偏好纳入权重；不要在 CSV、模板和权重里重复折算。需要实际需求对照验证当前引擎仍走这条路径，源码注释不能替代运行时测量。

### defines 与引擎行为

均位于 `loading_screen/common/defines/00_defines.txt`。命名空间必须区分：赤字系数在 **NEstate**，弹性在 **NMarket**。

| 参数 | 原值 | 行号 | 审计判断 |
| --- | ---: | ---: | --- |
| NEstate.POP_DEMAND_DEFICIT_SCALE | .5 | 1896 | 注释明确收入不足会缩减 pop demand；零收入时乘以 `1-scale`。SOL 已按可用资金求需求，存在重复收入反馈入口 |
| NMarket.DEMAND_ELASTICITY_COEFFICIENT | .40 | 1997 | 注释明确价格超过默认价时压低需求；与 SOL 价格偏好和封顶支出可能重复作用，需实测叠加顺序 |
| NMarket.DEMAND_ELASTICITY_FLOOR | .35 | 1998 | 上一弹性路径的最低需求比例；不能独立随意设零 |
| NPop.PRODUCED_IN_MARKET_DEMAND | .1 | 1773 | 未接管；具体是额外需求、倍率还是其他公式项需验证 |
| NPop.STARVING_ON_FOOD_DEMAND | 1.5 | 1774 | 未接管；需区分商品需求与原生 food 子系统 |
| NPop.NEGATIVE_FOOD_ON_FOOD_DEMAND | .5 | 1775 | 同上 |
| NMarket.BURGHER_TRADE_IMPACT_ON_DEMAND_SCALE | .25 | 1991 | 市场需求相关参数，未证明属于 POP 消费；不能按名称直接修改 |
| NMarket.TRADE_IMPACT_ON_DEMAND_SCALE | .75 | 1992 | 同上 |

价格/商品偏好可转入相应权重；重复的收入总量缩放应交由 SOL 收入预算统一处理。饥荒、贸易等参数先确认调用路径，避免误改普通贸易需求或原生粮食消费。

## 6. 当前接管状况

已接管：`demand_add` 基线（原版 demand_multiply 已在生成器中先解析）、商品发展/财富门槛、`NPop.DEVELOPMENT_SCALE_ON_DEMAND = 0`、`NPop.POP_NEEDS_INCOME_SCALE = 1`、奴隶商品需求。依据分别为 `scripts/gen_pop_goods.py`、`src/stable/loading_screen/common/defines/SOL_economy_defines.txt` 和 `scripts/test_sol_slave_demand.py`。这些控制不能覆盖前述其他层。

`scripts/gen_goods_demand_overrides.py` 是旧工具，当前生成链不调用；它只列出文化和宗教文件、只输出 stable，且依赖已经退出运行时的 `SOL_goods_weight_values.txt Part 2`。不能直接重跑它后宣称修复：那会清掉原生差异，却没有新权重承接，也漏掉时代、产业、商品条件和 standalone。

当前国家逐商品合成可从生成源还原为：

```text
E[g] = max(0, 1 + live_global_goods_modifier[g] - own_cached_auto_scale[g])
S[g] = (substitution_response[g] - 1) * E[g]
effective[g] = E[g] + S[g] = E[g] * substitution_response[g]
```

证据：`scripts/sol_substitution.py:218-220,244-249,295-297`。外部倍率仅以正负决定资格，未参与组内价格权重；然后再乘在最终商品结果上。`render_location_spending` 第 133-139 行使用这个 effective。因此“所有国家商品修正都完全漏算”不成立；“它们仍直接改变需求、没有成为组内偏好”成立。

相反，通用 `global_pop_demand` 在当前生成源中没有读取/抵消；地点写出的是 `final_scale - 1`（`scripts/sol_economy_effects_source.py:1079`），再应用原生 `local_pop_demand`。通用国家需求与地点需求的最终引擎合成顺序应实测，不能仅凭 modifier 名称推断。

兼容目标：stable 与 standalone 均存在本问题；PP 继承基础文化/宗教等层，lumber 为零的特殊处理须保留；M&T 生成器只移除 demand_add、demand_multiply、发展/财富门槛，当前生成 goods 中仍有上述环境字段；JTG 额外商品已有洲/次大陆字段抵消，但这不覆盖基础 56 商品及原版文化、宗教、国家来源。本轮没有声称已完成第三方 MOD 全量来源审计。

## 7. 权重迁移的实现约束

1. **偏好与最终应用分离。** 年代、制度、事件、改革、产业状态、文化、宗教和环境只能提供偏好或资格。组内归一化之前合成权重；最终原生需求 modifier 由 SOL 一处写出。不能保留原需求效果再加一层权重，造成双重作用。
2. **保留原条件和其他效果。** 将 country/age 加性需求增量映射成非负偏好需定义统一规则；字段本来就是倍率的文化/宗教不能再次加一。禁止商品用独立资格/硬零表达，避免其他正偏好重新开启禁品。
3. **人口与地点差异需要明确实现。** 采用地点/人口组偏好后，再按同一模型聚合支出和国家求解输入；或者接受并量化国家级近似。不得把国教、主流文化、市场中心的冬季当作所有 POP 的状态。若选择原生 pop-scope `goods_demand` 脚本值路径，需单独验证其加载、缓存和性能。
4. **通用总量不是商品偏好。** 自由民给所有商品同乘 1.2 时，`1.2*w[g] / sum(1.2*w)` 与原占比相同。现有收入预算决定总量的设计下，应中和这条原生总量加成；若保留玩法效果，必须另行明确预算/储蓄行为的映射，不能伪装成权重迁移。收入赤字缩放也属于预算层。
5. **缓存与刷新同步。** 新状态纳入按需缓存的键或聚合输入，原生入口中和与 SOL 权重更新同时落地。保留人类月度/降频 AI 年度节奏，不能以每月全图逐 POP 扫描修复这一问题。季节/事件变化在两次求解间的处理必须明确。
6. **不改变篮子契约。** 仍遵守订阅组、重叠商品和 PP 零 lumber、奴隶零商品需求规则。组内权重归一化本身不证明最终支出守恒；仍须按生成后的商品数量和价格验证预算。

验收应至少覆盖：穆斯林禁酒与同国非穆斯林；神职专属 wine 10/incense 2；同市场寒暖两地；医药疾病状态；时代切换、产业授予/撤销和永久事件；小麦/水果模板系数；外部 modifier 变化前后；全组零权重；收入为零和高价商品。同时比较原生实际消费与 SOL 支出，而不仅是离线脚本的内部缓存。引擎 defines 的调用与原生刷新时序应使用独立对照测试确认。
