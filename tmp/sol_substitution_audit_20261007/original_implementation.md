# SOL 商品替代组：国家级 Global Modifier 实施规格

> 状态：待实现的功能规格。本文记录 v1.1 的行为、当前 1.4 beta 接口以及建议的恢复方案；不表示该功能已经在当前分支恢复。

## 1. 目标与范围

恢复《商品替代组》的核心行为：同一消费组内，商品变贵时人口减少对该商品的需求，并把需求转移给同组的其他商品；商品便宜时反向增加需求。新接口不提供可供 SOL 使用的市场级商品人口需求修正，因此本次把最终替代结果写成国家级 `global_<good>_pop_demand` 修正。一个国家的所有地点和市场共享该商品乘数，市场之间的价格差异会被压缩，这是已接受的精度损失。

本规格覆盖：

- v1.1 的替代组、价格档位、权重和需求缩放的可追溯定义；
- 国家级商品乘数的聚合、跨组商品分摊和求解器接入；
- 修正器生命周期、缓存、初始化、关闭清理、兼容商品和性能；
- UI、调试信息、分阶段实施清单以及必须在游戏中验证的引擎行为。

本规格不改变商品基础 `pop_demand` 数值、阶层收入模型、国家地点级 `local_pop_demand` 求解器的目标，也不把国家级替代伪装成市场级精确模拟。

## 2. 已核实的引擎接口

`reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt` 定义了：

```text
global_pop_demand = { percent = yes, game_data = { category = country } }
local_pop_demand  = { percent = yes, game_data = { category = location } }
global_fine_cloth_pop_demand = {
    percent = yes
    game_data = { category = country }
}
```

同一文件列出了商品级 `global_<good>_pop_demand`。当前安装版本存在 `camels`、`fine_cloth`、`paper`、`books` 等定义，但没有 `global_victuals_pop_demand`。因此商品名可以用于生成脚本标识符的前提是引擎先提供对应 modifier type；兼容内容的 `victuals` 不能靠动态命名自动获得接口。

官方 `reference_official_defines/docs/effects.log` 记录的国家修正器调用为：

```text
add_country_modifier = {
    name = name
    days/months/years = x
    mode = add/extend/replace/add_and_extend
    size = x
}
remove_country_modifier = name
```

当前 SOL 的地点修正器使用同样的生命周期模式：`months = 1`、`mode = replace`，每月重写；年度低频计算只延后求解，不能让一个一年期修正器自行维持。国家商品修正器应采用相同原则，每次刷新都显式写入全部商品，关闭功能或商品失去接口时显式移除。

`reference_game_files/game/in_game/common/age/00_default.txt` 的 `goods_demand` 块直接写入 `global_<good>_pop_demand`，例如时代一的 liquor=-0.75、tobacco=-0.75、coffee=-0.5。年龄、机构、其他模组也可能写入相同 modifier；`percent = yes` 的实际叠加顺序必须在验收场景中测量，不能假定 SOL 值会覆盖外部值。

## 3. v1.1 历史机制

本文的历史基线为 `origin/v1.1`（提交 `9670e1414d8e2ce5c692672adc588f485baf167c`）。实现时应优先对照以下文件，而不是对照已经退役的早期十组草案 `docs/technical/SOL_Per_Group_Demand_Design_Prompt.md`：

- `src/stable/in_game/common/scripted_effects/SOL_substitute_effects.txt`：价格档位、市场列表刷新和稀缺更新；
- `src/stable/in_game/common/script_values/SOL_goods_weight_values.txt`：商品权重及组内归一化；
- `src/stable/in_game/common/script_values/SOL_goods_demand_values.txt`：人口需求映射；
- `src/stable/in_game/common/goods_demand/z_SOL_pop_demand.txt`：`REPLACE:pop_demand` 的商品需求入口；
- `z_SOL_group_demand_base_location.txt`、`z_SOL_group_demand_scales*.txt`：阶层基线、预算和时代缩放；
- `SOL_substitute_good_indicators.txt`、`SOL_substitute_group_indicators.txt`：商品/组指示器；
- `src/stable/in_game/common/situations/SOL_economy_situation.txt` 与 `A_SOL_economy_effects.txt`：刷新生命周期。

### 3.1 替代组成员

v1.1 使用 20 个消费组。下表是需求脚本实际使用的完整成员；同一商品出现在多个组时，各组需求贡献会相加。

| 组 | 商品 |
| --- | --- |
| `basic_clothing` 基本衣物 | `cloth`, `leather` |
| `crude_goods` 粗制品 | `lumber`, `masonry`, `tools`, `pottery` |
| `staple` 主食 | `wheat`, `rice`, `millet`, `maize`, `potato`, `legumes` |
| `condiments` 调味品 | `sugar`, `salt`, `olives` |
| `heating` 取暖燃料 | `lumber`, `coal`, `beeswax` |
| `household` 家居用品 | `furniture`, `pottery`, `glass`, `paper`, `beeswax` |
| `standard_clothing` 标准衣物 | `cloth`, `fine_cloth` |
| `intoxicants` 嗜好饮料 | `wine`, `beer`, `liquor`, `tobacco` |
| `luxury_drinks` 奢侈饮品 | `tea`, `coffee`, `wine`, `cocoa` |
| `luxury_food` 奢侈食物 | `wild_game`, `victuals`, `fruit`, `fish` |
| `luxury_goods` 奢侈商品 | `fine_cloth`, `fur`, `porcelain`, `lacquerware`, `marble`, `glass` |
| `protein` 蛋白食物 | `fish`, `livestock`, `wild_game` |
| `spices` 香料 | `saffron`, `pepper`, `cloves`, `chili` |
| `precious` 贵重品 | `goods_gold`, `silver`, `jewelry` |
| `treasures` 珍宝 | `amber`, `gems`, `ivory`, `pearls` |
| `medicine` 药品 | `medicaments`, `mercury` |
| `ritual` 祭祀物品 | `incense`, `mercury` |
| `weapons` 武器 | `weaponry`, `firearms` |
| `mounts` 坐骑 | `horses`, `elephants` |
| `knowledge` 知识用品 | `paper`, `books` |

`scripts/scarcity/_data.py` 中的 `INDICATOR_GROUPS` 是每商品唯一的主组，用于价格缓存和稀缺评分；`DEMAND_GROUPS` 才是需求替代组，允许重叠。生成器中的“仅 UI”注释不能作为运行时需求的依据，需求脚本本身实现了重叠组。

重复成员为 `cloth`、`fine_cloth`、`lumber`、`pottery`、`beeswax`、`paper`、`glass`、`wine`、`fish`、`wild_game`、`mercury`。v1.1 的实际 multiplier 是各组贡献相加，不是选择一个主组；恢复实现必须保留这一行为。

### 3.2 价格档位与权重

每个市场每年被归入商品的六个价格档位之一。价格是 `market_price / default_price`，按以下顺序严格判断：

| 条件 | 权重倍数 |
| --- | ---: |
| `> 2.30` | `0.25` |
| `> 1.70` | `0.50` |
| `> 1.30` | `0.75` |
| `< 0.40` | `2.00` |
| `< 0.65` | `1.50` |
| `< 0.85` | `1.25` |
| 其他 | `1.00` |

边界必须按严格比较实现：2.30 属于 `0.50` 档，1.70 属于 `0.75` 档；0.40 属于 `1.50` 档，0.65 属于 `1.25` 档；0.85 和 1.30 保持 1.00。每商品有六个全球市场列表，旧版 56 商品共 336 个列表；刷新时先移除旧列表，再加入新列表。没有价格滞回，通常年度刷新以降低振荡。

旧权重通常从 1 开始，再乘价格档位以及宗教、文化、地点偏好。每个组的分母至少为 `0.001`，避免空组除零。v1.1 顶部“稀缺乘 0.5”的注释已经过时，实际六档表才是权威。

### 3.3 需求量与重复组

旧单组公式为：

```text
group_good_demand = weight_good / max(total_group_weight, 0.001)
                     × N_group × group_scale
```

多组商品的最终需求为所有所属组的 `group_good_demand` 之和。该归一化只保证一个组内的权重份额相加为一，不保证实际数量、支出金额或跨组总量守恒；`N_group` 和 `group_scale` 仍会改变总量。因此新实现不能把“每组归一化”描述成天然预算守恒。

非部落阶层的历史 `group_scale` 基础为：

```text
max(0, (1 + savings_pressure) × demand_base × era_coefficient × scarcity_adjustment)
```

`demand_base` 的正常形式为：

```text
GDP_per_capita × budget_share / P_group + continuity_offset
```

其中 `P_group` 是该阶层组消费篮子的基准价格总和，不是商品均价；`z_SOL_group_prices.txt` 保存了这些值，`z_SOL_group_demand_offsets.txt` 保存收入分段连续性偏移。五个阶层为 nobles、clergy、burghers、commoners、tribesmen；commoners 在地点求解器中合并 laborers、peasants、soldiers。tribesmen 的 group demand base 固定为 1，不使用收入恩格尔项。时代系数依次为 `1.5, 1.425, 1.35375, 1.28606, 1.22176, 1.16067`。

### 3.4 稀缺评分和旧市场边界

旧脚本把主组价格档位转换为 `1 / P_tier - 1`，按阶层预算加权后写入市场中心的 `sol_market_scarcity_adj_<stratum>`。每年一月先更新替代稀缺列表和市场稀缺分数；每月更新国家 savings pressure 和地点需求修正。初始化、读档、年龄变化、全刷新也必须能建立同样缓存。

新方案不再把市场列表直接传递到 pop demand。列表仍可保留为调试和稀缺评分来源，但国家商品乘数的输入应从拥有地点的市场数据聚合得到。

## 4. 国家级替代算法

### 4.1 数据层和不变量

对每个国家 `C`、阶层 `s`、地点 `l`、组 `g`、商品 `i` 保存或临时计算以下量：

```text
B(C,l,s,i)       当前 SOL 基础支出/数量（不含本轮替代）
W(l,i)           市场价格档位 × 地点/宗教/文化权重
A(g,i)           商品 i 在组 g 的分摊权重
Q(C,s,i)         国家基线商品数量/支出聚合
Q'(C,s,i)        组内替代后的国家目标数量/支出
M(C,i)           最终国家商品乘数 = sum_s Q'(C,s,i) / max(sum_s Q(C,s,i), eps)
```

推荐以当前 SOL 的基线数量（或基线金额）作为 `B`，不要重新复制 v1.1 的收入公式；这样能保留现在的生活水平和国家 solver 校准。每个地点的市场价格只影响其自身 `W`，然后按人口和该商品基线支出聚合到国家。国家聚合权重必须是需求/支出权重，不能按地点数简单平均，也不能只按总人口平均。

必须满足：

1. 中性价格（所有 `W = 1`）时 `M(C,i) = 1`，写入的 modifier size 为 0。
2. 每个商品只有一个最终国家乘数；跨组商品的贡献先相加，再生成一个修正器。
3. 组内每个组的替代后总量保持该组本轮目标总量；跨组总量是否保持由基线 solver 决定，而不是隐式假设守恒。
4. 分母小于 `eps = 0.001` 时不产生异常值：无基线需求的商品写 0，整个国家无该商品基线时不创建或移除 modifier。
5. 输出允许大于 1 或接近 0，但必须在引擎验证后决定是否设置有限上下限；不能用未经验证的硬编码 `[-1, 1]` 截断。

### 4.2 组内计算

对每个地点、阶层和需求组，先取得当前组的基线组量 `N(C,l,s,g)`。它可以由现有 solver 的商品基线反推，或者由生成器输出的单位消费量直接计算；实现时选一种并在单元数据中固定，不能在不同路径混用。

```text
A(g,i,l) = B(C,l,s,i) / sum_j_in_g B(C,l,s,j)
            （分母为零时使用 W(l,i) / sum_j W(l,j)）

W'(g,i,l) = W(l,i) × non_price_preference(l,s,i)
R(g,i,l) = W'(g,i,l) / max(sum_j_in_g W'(g,j,l), 0.001)

Q'_g(C,s,i) = sum_l [ N(C,l,s,g) × R(g,i,l) ]
Q_g(C,s,i)  = sum_l [ N(C,l,s,g) × A(g,i,l) ]
```

若 v1.1 的权重已经包含宗教、文化、地点偏好，则只把价格档位替换为新的国家聚合价格输入，避免重复乘偏好。跨组商品按组独立算出 `Q'_g`，最后：

```text
Q'(C,s,i) = sum_g_containing_i Q'_g(C,s,i)
Q (C,s,i) = sum_g_containing_i Q_g (C,s,i)
```

这一步保留了 v1.1 的“多组实际累加”。如果产品设计选择预算守恒版本，应另行定义每组预算分配并更新验收数字；不能只在文档中把旧公式改称为守恒公式。

### 4.3 国家聚合与修正器数值

跨阶层聚合使用当前基线的数量/支出作为权重：

```text
Q_C(i)  = sum_s Q (C,s,i)
Q'_C(i) = sum_s Q'(C,s,i)
M(C,i)  = Q'_C(i) / max(Q_C(i), 0.001)
size(C,i) = M(C,i) - 1
```

`size` 的正负含义必须通过隔离测试确认。现有 `sol_local_pop_demand_modifier` 的静态值为 1，size=0.25 表示 +25%；商品 modifier 的 `percent=yes` 应先用同样的 `size = M - 1` 假设实现，然后用单商品场景测出引擎实际结果。若引擎把同类来源相乘或按别的基准解释，调整转换函数，不改 `M` 的定义。

国家商品 modifier 与时代、机构、其他模组的同一商品 modifier 可能同时存在。实现必须建立三组验收：只有 SOL、只有外部、SOL+外部；记录最终人口需求和 modifier tooltip，确认是相加、相乘还是覆盖。若无法可靠推导外部 offset，SOL 应把自身目标乘数作为独立来源并在 UI 标明“国家级 SOL 替代”，不得声称它已经抵消全部外部修正。

### 4.4 与现有地点级 solver 的顺序

当前 `A_SOL_economy_effects.txt` 的关键流程是：

1. `sol_refresh_market_pop_demand_maps` 每年按市场价格和硬编码单位消费量构建 market-keyed maps；只有市场中有供应的商品参与。
2. `sol_compute_location_pop_demand` 读取市场 map，得到七类人口的基础支出，再计算地点收入、流动资金和 raw 系数。
3. 国家 solver 聚合地点 raw 系数，求四类国家 strata factor。
4. `sol_apply_local_pop_demand_modifiers` 每月以 `months = 1, mode = replace` 写地点 `local_pop_demand`。

商品替代恢复后必须改为：

1. 市场刷新仍生成“不含国家替代”的每市场、每商品、每阶层基线金额/数量；这张 map 仍是所有国家共享的原始输入。
2. 国家刷新先遍历所属地点市场，计算 `M(C,i)`，写入国家商品 modifiers，同时把相同 `M(C,i)` 放入国家变量/缓存。
3. `sol_compute_location_pop_demand` 在形成各阶层 base spending 时，对每个商品基线项乘该国家缓存的 `M(C,i)`，然后才合计为阶层 raw spending。这样国家商品修正和 SOL 自己的 raw 目标使用同一个数值，不会出现 UI 有替代、solver 仍按旧消费篮子的双轨结果。
4. 后续收入、国家 strata solver 和地点 `local_pop_demand` 的顺序保持不变。国家商品替代影响 raw spending；`local_pop_demand` 继续调整地点总量/生活水平，不再重复乘一次商品 multiplier。
5. 不能只给国家添加商品 modifiers 而保留旧的“市场通用 unit spending 总和”作为最终国家支出：不同国家的 `M(C,i)` 不同，该总和已经失去可复用性。要么保留每商品明细 map，要么在国家/地点层重新展开每商品项。

国家刷新和地点求解必须使用同一快照：先计算完整 `M(C,i)`，再写 modifier 和缓存；不要在遍历地点的中途使用半成品乘数。缺缓存时使用 neutral `M = 1` 并设置初始化标志，完成计算后再重跑一次，不读取不存在的 map 项。

## 5. 脚本对象与文件布局

建议按现有生成链拆分，所有商品列表由同一数据源生成：

- `data/goods_weights.csv`：20 组、成员顺序、商品主组/兼容标记；需求组以重复行表达。
- `scripts/scarcity/_data.py`：保留主组与需求组的双表，增加 modifier 可用性审计，不把 `INDICATOR_GROUPS` 当需求组。
- `src/stable/in_game/common/script_values/SOL_goods_weight_values.txt`：市场权重和偏好部分；删除过时“固定 0.5”注释。
- `src/stable/in_game/common/script_values/SOL_substitute_good_indicators.txt`、`SOL_substitute_group_indicators.txt`：组成员和 UI 指示器。
- 新增生成的 `SOL_country_substitute_values.txt`：每商品国家乘数、epsilon、刷新状态、外部 offset 诊断。
- `src/stable/in_game/common/static_modifiers/SOL_substitute_global_modifiers.txt`：每个可用商品一个静态 modifier，category 为 country，内部字段为该商品的 global modifier，静态值为 1。

静态定义形态应与原版 `printing_press_books` 一致：

```text
sol_substitute_cloth = {
    game_data = { category = country }
    global_cloth_pop_demand = 1
}
```

运行时写入示例（实际名称以最终定义为准）：

```text
add_country_modifier = {
    name = sol_substitute_cloth
    months = 2
    mode = replace
    size = var:sol_substitute_cloth_size
}
```

`months = 2` 只是避免月初调用顺序造成短暂过期；若实现按月重写，也可使用 1。年度低频选项只能减少昂贵的国家求解，不能停止月度重写，原则与现有地点修正器相同。清理效果必须遍历同一商品清单，对已存在 modifier 执行 `remove_country_modifier`，并删除国家缓存。

当前引擎没有 `global_victuals_pop_demand` 时有两种可接受策略：

1. 默认跳过 `victuals` 的 global modifier，但仍把它作为组内计算项；国家 solver 的内部支出使用缓存乘数，UI 明确显示“引擎无国家 modifier，victuals 仅参与 SOL 计算”。
2. 在目标兼容包中先定义该 modifier type（若 1.4 beta 支持扩展 modifier type），通过启动日志和单商品测试确认后才启用。

不能直接生成并调用一个未在 modifier type 定义中存在的名字。

## 6. 生命周期、缓存和性能

### 刷新触发

- 新游戏、读档、玩家/AI 身份切换、成立国家、合并/失去地点：立即执行国家替代初始化。
- 每年一月：更新市场价格档位、市场稀缺评分、国家商品乘数。
- 每月：从国家缓存重写商品 modifiers；人类国家和默认 AI 国家按现有频率求解，低频 AI 仅按自己的年度 pulse 重算国家乘数。
- 年龄、机构、商品供应大变更或全刷新：先清理旧国家商品修正，再计算完整新快照。
- CMF 关闭：对所有国家和所有商品显式移除 SOL modifier，清除变量和全局 map；不能只跳过下一次 trigger。

### 缓存规则

国家不保存市场级 persistent variable。市场明细继续使用现有 global variable map，以市场 scope 为 key；国家级结果使用国家变量或以国家 scope 为 key 的 map。所有读取都先用 `has_variable`/`is_key_in_global_variable_map` 守卫。临时商品变量在效果末尾删除，避免跨商品污染。

国家规模较大时，计算成本主要来自“国家 × 所有地点 × 商品 × 阶层”。应保留每市场每商品明细缓存，只有价格档位或国家商品需求发生变化时重算；modifier 写入可以每月执行但不重复求解。记录国家数、地点数、实际有供应商品数和耗时，用于决定是否增加低频门槛。

## 7. UI、调试与可观测性

商品 tooltip 显示：国家级 SOL 替代倍率、所属需求组（重复组全部列出）、当前价格档位、国家聚合基线与目标（仅在调试/开发者模式显示详细数字）。组图标继续使用现有 `SOL_substitute_group_indicators`。

国家生活水平面板增加三项只读诊断：替代刷新年份、参与商品数、最大绝对 modifier。不要把国家倍率误标为市场价格，也不要在地图上绘制一个看似市场精确的替代值。

建议的开发日志每次只输出一行国家摘要：国家、刷新原因、商品数、是否使用兼容 fallback、是否清理旧 modifier。商品级完整数组放入 debug 变量或离线导出，避免每月日志爆炸。

## 8. 分阶段实施清单

### 阶段 A：数据和接口审计

- 固化 20 组和 56/57 商品清单，明确 `victuals`、`camels` 以及任何 PP 商品。
- 在启动日志确认每个商品都有 `global_<good>_pop_demand`；缺失项进入兼容表。
- 生成 56 个静态国家 modifier，运行最小国家场景验证 `size = 0.25` 是否产生 +25% 商品需求。
- 测量年龄、机构和 SOL 同类 modifier 的叠加顺序。

### 阶段 B：国家聚合，不接 solver

- 从现有市场明细计算 `Q`、`Q'`、`M`，输出离线 CSV 与国家变量。
- 用全为 1 的权重、单市场、双市场和重叠组固定样例验证中性、加和、边界档位。
- 比较“按需求支出加权”和“按地点/人口平均”的差异，锁定前者为规范。

### 阶段 C：接入 SOL raw spending

- 把 market map 从阶层总和扩展为每商品明细，或提供等价的国家层明细读取。
- 在 `sol_compute_location_pop_demand` 中只应用一次国家 `M`，再进入现有国家 strata solver。
- 对国家商品 multiplier 和地点 `local_pop_demand` 做守恒/回归对比，确保关闭替代时结果与当前分支完全一致。

### 阶段 D：生命周期、UI、兼容

- 接入月度重写、年度求解、初始化、读档和 CMF 关闭清理。
- 完成 `victuals` fallback、M&T/JTG 等兼容目标的 modifier 审计。
- 添加 tooltip、面板诊断、开发日志和性能计数器。

## 9. 验收测试

1. **档位边界**：价格比为 2.30、1.70、1.30、0.85、0.65、0.40 时分别得到规范表中的下一档；相邻浮点值不越档。
2. **中性**：所有市场价格等于默认价，所有商品 `size = 0`，国家和地点结果与关闭替代时一致。
3. **单组守恒**：两商品组一贵一便宜时，组内目标份额按权重归一化；组总量保持，国家 modifier 与离线 `M` 一致。
4. **重叠组**：cloth、lumber、wine、mercury 等商品的最终目标等于各组贡献之和，不出现最后一个组覆盖前一个组。
5. **多市场国家**：两个市场同组价格相反时，国家倍率等于基线需求/支出加权结果；不能等于市场数平均或人口简单平均。
6. **国家差异**：两个国家拥有同一市场但人口结构不同，国家 modifier 可不同；地点 modifier 仍按各自 solver 结果不同。
7. **外部修正**：年龄/机构/其他国家修正与 SOL 同时存在时，记录引擎最终值并按实测叠加规则计算预期。
8. **缺接口商品**：`victuals` 没有 global modifier 时不报错、不生成幽灵修正；兼容日志和 UI 标明 fallback。
9. **生命周期**：新游戏、读档、失去最后一个地点、玩家转 AI、CMF 开关、年度刷新后均无过期 modifier 或旧国家值残留。
10. **回归与性能**：替代关闭时 raw spending、国家 solver、地点 modifier 与基线一致；在代表性大国存档记录年度求解耗时和月度写入耗时。

## 10. 已知限制与后续选择

- 国家级 modifier 无法表达同一国家不同市场的价格档位，市场间差异被需求加权平均；这是本任务明确接受的精度损失。
- 引擎是否把多个 `percent=yes` 商品 modifier 按加法、乘法或其他顺序合成，必须通过游戏观测确认；在确认前不要承诺精确抵消时代/机构值。
- v1.1 的阶层恩格尔曲线、时代系数和稀缺修正仍可作为历史对照，但本恢复优先复用当前 SOL 基线，避免收入缩放和商品替代重复计算。若未来要恢复完整 v1.1 scale，应先定义预算守恒和与当前 savings pressure 的唯一来源。
- 当前商品清单和 modifier type 属于游戏接口，不是任意字符串 API；每次升级 EU5 或引入 PP 商品都必须重新运行接口审计。

