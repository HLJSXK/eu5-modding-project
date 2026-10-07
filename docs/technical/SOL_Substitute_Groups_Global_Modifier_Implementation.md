# SOL 商品替代组：国家级 Global Modifier 实施规格

> 状态：2026-10-07 已完成源码审计并修订；运行时尚未实现。历史事实和接口声明已核对，国家算法仍有明确的设计选择，引擎叠加语义尚待实测。问题、反例与证据见 [审计报告](SOL_Substitute_Groups_Global_Modifier_Audit.md)。

## 1. 目标与范围

恢复《商品替代组》的核心行为：同一消费组内，商品变贵时人口减少对该商品的相对需求，并提高同组其他商品的相对需求。当前参考文件提供国家作用域的 `global_<good>_pop_demand`，未找到对应的市场级商品需求接口；本次确定使用国家级接口。这里的 global 指国家辖下适用，并非全世界共享一个结果。国家内部各市场、阶层及 POP 的不同替代偏好最终压缩为每商品一个修正值；市场差异精度下降已获接受，其他聚合误差也须如实披露。

本规格覆盖：

- v1.1 的替代组、价格档位、权重和需求缩放的可追溯定义；
- 国家级商品乘数的聚合、跨组商品分摊和求解器接入；
- 修正器生命周期、缓存、初始化、关闭清理、兼容商品和性能；
- UI、调试信息、分阶段实施清单以及必须在游戏中验证的引擎行为。

恢复应保留 `data/target_demand.csv` 校准后的商品 `demand_add` 基线和现有国家分层求解器的收入目标。旧版需求曲线、时代补偿与市场稀缺总量补偿须与商品替代分开决策，不能重复叠加到当前收入闭合模型上。

## 2. 已核实的引擎接口

`reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt` 定义了：

```text
global_pop_demand = { percent = yes game_data = { category = country } }
local_pop_demand  = { percent = yes game_data = { category = location } }
global_fine_cloth_pop_demand = {
    percent = yes
    game_data = { category = country }
}
```

同一文件列出了商品级 `global_<good>_pop_demand`。当前参考快照中，核心 `data/goods_weights.csv` 的 56 种商品全部有对应定义（含 `camels`，不含 `victuals`）；原版和当前 PP 参考目录未找到 `global_victuals_pop_demand`。Just Goods 参考目录则自行声明了其 26 种有直接人口需求商品的全部对应类型。因此应审计最终加载的原版和兼容模组定义，不能仅凭原版缺项判定自定义商品永远不可支持；反过来，声明了名字也不等于证明引擎把它接到了商品需求计算，仍需实测。

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

`reference_game_files/game/in_game/common/age/00_default.txt` 的 `goods_demand` 块直接写入 `global_<good>_pop_demand`，例如时代一的 liquor=-0.75、tobacco=-0.75、coffee=-0.5。时代、思潮和其他模组可能写入同类修正。必须分别实测同一商品的多个来源如何叠加，以及商品修正与 `local_pop_demand`、通用 `global_pop_demand` 如何组合；`percent = yes` 只证明接口声明，不足以证明这些层次之间的乘法关系。

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

v1.1 使用 20 个消费组、67 条成员关系、56 种独立商品（55 种核心商品加兼容商品 `victuals`）。下表来自实际需求脚本；同一商品出现在多个组时，各组需求倍率先相加，再取平均。

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

历史 `scripts/scarcity/_data.py` 中的 `INDICATOR_GROUPS` 是每商品唯一的主组，用于价格缓存和稀缺评分；`DEMAND_GROUPS` 是允许重叠的显示表，其成员与历史需求脚本相符，但该表本身不是需求脚本的生成入口。恢复运行时成员关系应以 `SOL_goods_weight_values.txt` 的 total-weight 块与 `SOL_goods_demand_values.txt` 交叉核对，不能把“仅 UI”注释解释成重叠组不影响需求。

重复成员为 `cloth`、`fine_cloth`、`lumber`、`pottery`、`beeswax`、`paper`、`glass`、`wine`、`fish`、`wild_game`、`mercury`。历史 `SOL_goods_demand_values.txt:679` 起的 11 个最终聚合块全部包含 `divide = 2`，不能遗漏。`victuals` 权重在 PP 兼容关闭时为 0，但历史 luxury_food 的常数 N 仍为 4；这是历史实现事实，不应默默改写为按有效成员数动态计算。

### 3.2 价格档位与权重

每商品按市场价格记录六个非中性档位，中性状态不进入列表。价格是 `market_price / default_price`，按以下顺序严格判断：

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

旧接口传入的是商品需求倍率，不是已乘人口和商品基础需求的实际数量。对 POP p 的单组贡献为：

```text
F(p,g,i) = weight(p,i) / max(total_group_weight(p,g), 0.001)
           × N_group × group_scale(p,g) × 10 / max(location.development, 1)
H(p,i)   = sum_g_containing_i F(p,g,i) / membership_count(i)
```

`REPLACE:pop_demand` 把 H 交给引擎，再与商品中按 pop_type 定义的基础需求等因子组合。最后的 `10 / max(development, 1)` 是旧脚本的开发度抵消项；当前分支已经通过 define 和商品阈值修正关闭开发度影响，不得照搬此项。组内权重和为 1 只在分母未被 0.001 下限抬高时成立，而且从来不等于实际数量或支出守恒；不同商品基础需求、价格、重叠平均和 group_scale 都影响最终结果。

非部落阶层的历史 `group_scale` 基础为：

```text
max(0, (1 + savings_pressure) × demand_base × era_coefficient × scarcity_adjustment)
```

`demand_base` 的正常形式为：

```text
GDP_per_capita × budget_share / P_group + continuity_offset
```

其中 `P_group` 是该阶层组消费篮子的基准价格总和，不是商品均价；`z_SOL_group_prices.txt` 保存了这些值，`z_SOL_group_demand_offsets.txt` 保存收入分段连续性偏移。五个阶层为 nobles、clergy、burghers、commoners、tribesmen；commoners 的组缩放由 laborers、peasants、soldiers 共用。预算分段阈值为 3、8、25，对应四个区间。tribesmen 的 group demand base 固定为 1，不使用收入恩格尔项。时代系数依次为 `1.5, 1.425, 1.35375, 1.28606, 1.22176, 1.16067`。

### 3.4 稀缺评分和旧市场边界

旧脚本按每商品唯一主组计算 `delta_i = (1 / P_tier - 1) × alpha_avg(stratum, primary_group) / primary_group_size`，再把 `1 + sum_i delta_i` 写入市场中心的 `sol_market_scarcity_adj_<stratum>`。alpha_avg 是四个收入区间预算份额的平均值，不是该 POP 当期预算份额；P_tier 是价格阈值代表值，不是替代权重 0.25/0.50 等。

v1.1 局势每年一月依次刷新价格列表和市场中心稀缺分数，每月刷新 savings pressure 与地点/国家显示缓存；需求通过 POP 脚本值求值，并非当前分支的月度 `local_pop_demand` 链。历史全刷新效果只显式调用了 `SOL_update_substitute_scarcity`，没有调用市场中心评分刷新；缺评分时读取包装器返回 1。新方案的初始化、读档、时代变化和全刷新必须建立完整一致的缓存，这是恢复时的要求，不能声称旧链已经全部做到。

新方案不再把市场列表直接传递到 pop demand。列表仍可保留为调试和稀缺评分来源，但国家商品乘数的输入应从拥有地点的市场数据聚合得到。

## 4. 国家级替代算法：修订后的候选设计

原稿公式不能直接实施：它把不等量基线 A 与独立归一化权重 R 相除，导致中性时也重分配；同时混用数量和金额，并重复计入跨组基线。以下给出可明确检验的两种设计。建议以方案 A 恢复旧版价格响应，方案 B 是另一个玩法选择，不能同时套用。

### 4.1 固定口径与不变量

以地点 l、七个人口类型 s、商品 i 为索引；commoners 在商品明细计算后才合并 laborers、peasants、soldiers。当前基线为：

```text
q(l,s,i) = population(l,s) × calibrated_unit_quantity(s,i)
           × supply_eligible(market(l),i)
p_ref(i) = default_price(i)                       # 中性参考价，与市场当前价格无关
B(l,s,i) = q(l,s,i) × p_ref(i)                   # 金额，尚未乘地点 SOL 系数
```

v1.1 替代组本身没有 B，也没有 `min(市场价,默认价)`；市场价格只通过六档市场列表进入商品权重。这里的 B 是为了把本地数量响应按国家聚合成一个倍率而新增的中性参照账本。对同一个商品，`p_ref` 在所有地点相同，因此按 B 加权与按 q 加权等价，不会让当前市场价格同时改变 D 和聚合权重。当前 SOL 的市场支出缓存确实使用 `min(市场价,默认价)` 作为高价抑制的 raw spending 代理，但那是地点总量 / 收入闭合层，不能回填成替代基线。

供给资格读取引擎 `goods_supply_in_market > 0` 或其已有缓存，不用存档 `supply` 字段代替。商品修正的外部时代等因素是否已进入实际人口需求，需要按 4.3 单独对齐；当前中性参考金额没有读取这些修正。

必须满足：中性价格响应为 1；一个商品只计一次 B、只输出一个国家修正；无基线或零分母返回 `M = 1` / `size = 0` 并移除旧修正；不允许用 `max(Q, 0.001)` 把小正数的中性结果变成不足 1。epsilon 用作分支判定，其单位、五位小数精度和回退规则需固定，而非悄悄改变分母。

### 4.2 组内响应与重叠商品

**方案 A：旧版形状的价格响应。** 对同一组，分别计算当期价格档位 T 和中性 T=1 时的权重分配。V 是非价格偏好；第一阶段可显式选 V=1，只恢复价格替代。若恢复旧宗教/文化/地点偏好，必须按旧 POP scope 聚合或明确另行近似；不能用国家主流宗教、地点 dominant culture 冒充每个 POP 的偏好，也不能直接在 country/location scope 调用旧 pop-scope 值。

```text
W(l,s,i) = T(market(l),i) × V(l,s,i)
F_T(l,s,g,i) = N_g × W(l,s,i) / sum_j_in_g W(l,s,j)
F_1(l,s,g,i) = N_g × V(l,s,i) / sum_j_in_g V(l,s,j)
H_T(l,s,i) = sum_g_containing_i F_T(l,s,g,i) / membership_count(i)
H_1(l,s,i) = sum_g_containing_i F_1(l,s,g,i) / membership_count(i)
D(l,s,i) = H_T(l,s,i) / H_1(l,s,i)
B_target(l,s,i) = B(l,s,i) × D(l,s,i)
```

这保留 N、权重归一化和跨组平均的结构，但只提取相对中性价格的响应，不重新应用旧 group_scale、开发度抵消和时代补偿。取所有旧 group_scale=1 是当前基线下的简化，不能声称还原旧阶层恩格尔曲线。对中性分母为零的项目返回 D=1，并保留其实际零需求；不得凭空生成无法用乘法实现的需求。

供给/零基线处理建议：仅可供应、有正基线且有可用接口的成员参加本轮转移；不足两个有效成员的组无替代，全组权重为零则回退中性。有效成员集在 T 与中性两次计算中一致。此过滤是新方案为避免向不可消费商品分配份额而加入的规则，v1.1 的六档列表并无当前生成器的 absent 档。N 与历史成员数仍分开记录，不因无供应而重写历史定义。

方案 A 不保证组内数量或金额守恒。例如基线金额 90/10、价格权重 0.5/1，旧式两商品倍率为 2/3、4/3，目标金额为 60、13.33333，总额 73.33333。当前地点 SOL 系数之后会根据新篮子成本重算总需求；不能把这个后续闭合步骤解释成旧替代公式天然守恒。

**方案 B：新增的组预算守恒。** 若选择把被替代商品的基线金额全部转给组内其他商品，必须先拆分重叠商品，且以基线金额参与归一化：

```text
alpha(g,i) >= 0; sum_g_containing_i alpha(g,i) = 1
# 默认候选 alpha = 1 / membership_count(i)，不是重复使用完整 B
b(l,s,g,i) = alpha(g,i) × B(l,s,i)
budget(l,s,g) = sum_i_in_g b(l,s,g,i)
b_target(l,s,g,i) = budget(l,s,g) × b(l,s,g,i) × T(l,i)
                      / sum_j_in_g [b(l,s,g,j) × T(l,j)]
B_target(l,s,i) = sum_g_containing_i b_target(l,s,g,i)
```

零分母保留原 b，不可消费/缺接口项目冻结且不参加转移。中性时各商品 B_target=B，组预算守恒；同一 90/10、权重 0.5/1 的例子变成 81.81818、18.18182，与方案 A 显著不同。非价格偏好若属于既有基线，不再重复乘入。这是新增预算规则，不是历史事实。

### 4.3 国家聚合与修正器换算

本候选明确选择**按中性参考金额聚合**。这保留金额单位，且因为同一商品的默认价在各地点相同，数学上等价于按数量聚合：

```text
E_C(i) = sum_owned_land_l,s B(l,s,i)
E_target_C(i) = sum_owned_land_l,s B_target(l,s,i)
M(C,i) = E_target_C(i) / E_C(i)           # E_C > epsilon；否则 M=1
```

人口已经包含在 B 中，不再乘第二遍。仅聚合该国拥有的地点，不能按市场拥有者划归整市场，也不能只取首都市场。由于 `p_ref` 对同一商品固定，按 B 聚合与按 q 聚合等价；当前市场价格只在 D 中生效。本式在地点 SOL 系数尚未重算前保持商品的目标数量比例；统一 M 无法同时还原各市场、各阶层数量，也不能保证最终地点系数变化后的同一总额。后续 solver 必须使用统一 M 后的实际篮子重新计算，不能使用已被压缩掉的本地理想目标。若未来按当前 SOL raw spending 做金额闭合，应在 M 已生效后单独使用其 `min(市场价,默认价)` 支出代理，不能把它再放回 B。

`size = M - 1` 仅在隔离条件成立时可用。以同类百分比来源相加的模型为例，外部 offset 为 e，SOL 写 x，则实际相对倍率为 `(1+e+x)/(1+e)`；要得到 M，应写 `x=(1+e)×(M-1)`。例如 e=-0.75、M=0.5，x 应为 -0.125，而非 -0.5。此处是待验证模型的推导，不是已证实的引擎结论。

必须先验证：同类来源叠加、商品修正与通用 global/local 需求修正的组合、引擎截断、负 size、零基线，以及人口需求滚动更新后的稳定值。若商品与地点修正相加而非相乘，单个国家商品值加一个地点总量值不能表达 `M(C,i)×L(l)`，不能只调整 size 换算就宣称现有 solver 可直接复用。外部 e 的读取和排除自身旧值也须核实，避免每次刷新自我累积。无法对齐时，应保留该商品中性并报告未覆盖项，不能让内部账本假定 M 已生效。

### 4.4 与现有地点级 solver 的顺序

当前 `A_SOL_economy_effects.txt` 的关键流程是：

1. `sol_refresh_market_pop_demand_maps` 每年按 `min(市场价, 默认价)` 和校准单位消费量构建 market-keyed maps；只有 `goods_supply_in_market > 0` 的商品参与。
2. `sol_compute_location_pop_demand` 读取市场 map，得到七类人口的基础支出，再计算地点收入、流动资金和 raw 系数。
3. 国家 solver 聚合地点 raw 系数，求四类国家 strata factor。
4. `sol_apply_local_pop_demand_modifiers` 每月以 `months = 1, mode = replace` 写地点 `local_pop_demand`。

商品替代恢复后必须改为：

1. 市场刷新生成“不含国家替代”的每市场、每商品、每人口类型单位支出金额（校准数量乘有效价格），供各国按自身地点人口聚合；这张 map 是各国共享的原始输入。
2. 国家刷新先遍历所属地点市场，计算完整 `M(C,i)`，根据实测组合规则生成国家 modifier size 与内部实际生效倍率，再提交同一快照。
3. 只有在商品与地点修正的乘法关系已验证时，`sol_compute_location_pop_demand` 才能在商品基线项乘国家实际生效倍率后合计阶层 base spending。若有外部商品修正，账本必须一致表达基线和增量；不得直接假定显示的 SOL 目标 M 就是引擎最终总倍率。
4. 后续收入、国家 strata solver 和地点 `local_pop_demand` 的顺序保持不变。国家商品替代影响 raw spending；`local_pop_demand` 继续调整地点总量/生活水平，不再重复乘一次商品 multiplier。
5. 不能只给国家添加商品 modifiers 而保留旧的“市场通用 unit spending 总和”作为最终国家支出：不同国家的 `M(C,i)` 不同，该总和已经失去可复用性。要么保留每商品明细 map，要么在国家/地点层重新展开每商品项。

国家刷新和地点求解必须使用同一快照：先计算完整 `M(C,i)`，再写 modifier 和缓存；不要在遍历地点的中途使用半成品乘数。缺缓存时使用 neutral `M = 1` 并设置初始化标志，完成计算后再重跑一次，不读取不存在的 map 项。国家 modifier 可能影响账本外人口（例如保留原版需求的 slaves）；验收必须检查这类附带变化，不能声称可按七类人口选择性应用国家商品修正。

## 5. 脚本对象与文件布局

建议按现有生成链拆分，所有商品列表由同一数据源生成：

- `data/goods_weights.csv`：当前只有 `good,group,k_factor` 三列，含重复成员，没有主组/兼容标记。作为候选单一数据源时必须新增或配套定义这些元数据；当前 56 商品是旧 55 核心商品加 camels。
- `scripts/scarcity/_data.py`：历史生成器残留，当前已无对应运行时输出；恢复时整合双表并审计一致性。当前生成器还多了 absent 档，不能直接运行它并称为 v1.1 六档机制。
- `src/stable/in_game/common/script_values/SOL_goods_weight_values.txt`：市场权重和偏好部分；删除过时“固定 0.5”注释。
- `src/stable/in_game/common/script_values/SOL_substitute_good_indicators.txt`、`SOL_substitute_group_indicators.txt`：组成员和 UI 指示器。
- 新增生成的 `SOL_country_substitute_values.txt`：每商品国家乘数、epsilon、刷新状态、外部 offset 诊断。
- `src/stable/main_menu/common/static_modifiers/SOL_substitute_global_modifiers.txt`：每个可用商品一个静态 modifier，category 为 country，内部字段为该商品的 global modifier，静态值为 1。必须位于 main_menu，而非原稿的 in_game 目录。

上述旧 script_values 和指示器在当前 src 中不存在，均属于待恢复或重写项。当前运行时生成源是 `scripts/gen_market_unit_consumption.py`、`sol_economy_effects_source.py` 和 `sol_country_demand_solver_source.py`，由 `gen_sol_economy_effects.py` 输出 stable/standalone；应修改生成源再生成。PP/M&T/JTG 各自覆盖市场刷新入口，也必须同步生成明细，不能只修改基础模组的生成结果。

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

`global_victuals_pop_demand` 在当前原版/PP 参考快照缺失时：

1. 默认冻结该商品：不分配转入/转出份额，保持原商品基线与内部 M=1；其原有需求仍计入 SOL 总支出。剩余可替代成员重新确定本轮集合。
2. 可参考 JTG 的自定义类型声明，在 PP 兼容包中补充类型，并通过加载及实际人口需求测试确认引擎关联后启用。不能仅凭无报错证明需求生效。

不能直接调用没有定义的类型，也不能只让 SOL 账本使用非中性倍率而不改变实际需求；tooltip 提示不能修复账实不符。

## 6. 生命周期、缓存和性能

### 刷新触发

- 新游戏、读档与全刷新：先建立市场明细，再计算国家替代、重算地点与国家 solver，最后写入并标记同一快照版本。
- 每年一月：更新全球市场价格档位/明细并递增版本，不强制让全部低频 AI 同月求解。旧市场稀缺总量评分不进入本次价格替代链，若保留仅作历史诊断。
- 每月：人类和关闭低频选项的 AI 先更新国家替代与 solver，再写 modifiers；默认开启低频的 AI 月度只重写缓存，自身年度 pulse 才成套重算国家替代与 solver。不得只更新 M 而留旧地点系数。
- 国家成立、玩家/AI 切换、领土/市场归属变化：这些是需要处理的失效场景，不是已验证存在的即时 hook。实施时逐项核对 on_action；无可用 hook 时用月度守卫，明确最长一个月延迟。
- 时代/思潮等外部修正变化：触发成套失效重算；若需要移除自身旧值以读取外部 offset，应在同一次效果内完成读取、计算、重新应用，不留跨月空窗。
- CMF 关闭替代：对所有国家和所有商品显式移除替代 modifier，清除其专用变量和 map，并以中性替代重新求解仍启用的 SOL 需求；共享市场缓存继续供 SOL 使用。关闭整个 SOL 时走完整清理，不能只跳过下一次 trigger。

### 缓存规则

国家不保存市场级 persistent variable。市场明细继续使用现有 global variable map，以市场 scope 为 key；国家级结果使用国家变量或以国家 scope 为 key 的 map。所有读取都先用 `has_variable`/`is_key_in_global_variable_map` 守卫。临时商品变量在效果末尾删除，避免跨商品污染。

国家规模较大时，计算成本主要来自“国家 × 所有地点 × 商品 × 阶层”。应保留每市场每商品明细缓存，只有价格档位或国家商品需求发生变化时重算；modifier 写入可以每月执行但不重复求解。记录国家数、地点数、实际有供应商品数和耗时，用于决定是否增加低频门槛。

## 7. UI、调试与可观测性

商品 tooltip 显示：国家级 SOL 替代倍率、所属需求组（重复组全部列出）、当前查看市场的价格档位。通用商品 tooltip 没有唯一消费国家时，不显示虚构的国家倍率；地点入口使用 owner，国家面板使用面板国家，不能自动以市场拥有者或玩家国家替代。详细聚合金额只在调试模式显示。旧 `SOL_substitute_group_indicators` 已被删除，恢复 UI 时必须核对 1.4 GUI 接口。

国家生活水平面板增加三项只读诊断：替代刷新年份、参与商品数、最大绝对 modifier。不要把国家倍率误标为市场价格，也不要在地图上绘制一个看似市场精确的替代值。

建议的开发日志每次只输出一行国家摘要：国家、刷新原因、商品数、是否使用兼容 fallback、是否清理旧 modifier。商品级完整数组放入 debug 变量或离线导出，避免每月日志爆炸。

## 8. 分阶段实施清单

### 阶段 A：数据和接口审计

- 固化 20 组：历史 55 核心 + victuals = 56；当前 55 核心 + camels = 56；PP 加 victuals 后为 57；JTG 当前额外 26 种需求商品是否加入替代组需另定成员关系，默认维持中性。
- 在启动日志确认每个商品都有 `global_<good>_pop_demand`；缺失项进入兼容表。
- 生成 56 个静态国家 modifier，运行最小国家场景验证 `size = 0.25` 是否产生 +25% 商品需求。
- 测量时代/思潮与 SOL 同类 modifier 的叠加，以及它们与 local/global 通用需求修正的组合；验证失败则调整整个接入模型。

### 阶段 B：国家聚合，不接 solver

- 先选定 4.2 的 A 或 B，并固定偏好、供给过滤、epsilon 单位及兼容范围；建议 A 的第一阶段采用 V=1。
- 当前市场缓存只有阶层总额、供给及高价标记，先扩展商品明细，再计算金额 E、E_target、M。
- 用不等基线、单市场、双市场和重叠组验证中性、平均、边界档位；比较金额加权与数量加权的不同结果。

### 阶段 C：接入 SOL raw spending

- 把 market map 从阶层总和扩展为每商品明细，或提供等价的国家层明细读取。
- 在验证过的引擎组合关系下，于 `sol_compute_location_pop_demand` 中应用一次国家实际生效商品倍率，再进入现有国家 strata solver。
- 对国家商品 multiplier 和地点 `local_pop_demand` 做守恒/回归对比，确保关闭替代时结果与当前分支完全一致。

### 阶段 D：生命周期、UI、兼容

- 接入月度重写、年度求解、初始化、读档和 CMF 关闭清理。
- 完成 `victuals` fallback、M&T/JTG 等兼容目标的 modifier 审计。
- 添加 tooltip、面板诊断、开发日志和性能计数器。

## 9. 验收测试

1. **档位边界**：价格比为 2.30、1.70、1.30、0.85、0.65、0.40 时分别得到规范表中的下一档；相邻浮点值不越档。
2. **中性**：所有市场价格等于默认价，使用不等基线 90/10、重叠商品和低于 epsilon 的小额需求，所有 SOL `size = 0`；国家和地点结果与同等外部修正下关闭替代一致。
3. **算法区别**：基线 90/10、权重 0.5/1 时，A 输出 60/13.33333，B 输出 81.81818/18.18182；仅 B 要求本轮组预算守恒。
4. **重叠组**：历史倍率按组贡献平均；新方案 A 按中性与当期的两个平均值之比计算，B 先拆基线再加目标；都不能把完整 B 重复计两次。
5. **多市场国家**：同商品两市场数量 1/1、有效价格 1/2、当地响应 0.5/1.5 时，金额聚合 M=7/6，数量聚合 M=1；按选定金额口径验收。
6. **国家差异**：两个国家拥有同一市场但人口结构不同，国家 modifier 可不同；地点 modifier 仍按各自 solver 结果不同。
7. **引擎组合**：分别测试同商品外部修正、local_pop_demand、global_pop_demand、高价抑制、零基线和 slaves；等待人口需求滚动更新后记录结果，内部支出与实际有效倍率必须一致。
8. **缺接口/无供应商品**：victuals 缺接口时冻结且不收取组内转移；零供应、全组无供应、单有效成员都不产生幽灵需求，也不除零。
9. **生命周期**：新游戏、读档、失去最后一个地点、玩家转 AI、CMF 开关、年度刷新后均无过期 modifier 或旧国家值残留。
10. **回归与性能**：替代关闭时 raw spending、国家 solver、地点 modifier 与基线一致；在代表性大国存档记录年度求解耗时和月度写入耗时。

## 10. 已知限制与后续选择

- 国家级 modifier 把市场、阶层与 POP 间的响应压缩为一个值；当前候选采用基线金额加权，后续地点总量重算还会改变最终分布。市场精度损失已被接受，但不能将这种近似描述成所有阶层和总量同时精确。
- 同类 modifier 的叠加以及商品/通用 global/local 需求层次的组合都必须实测；在确认前不能承诺 `size=M-1` 和内部支出乘 M 同时成立。
- v1.1 的阶层恩格尔曲线、时代系数和稀缺修正仍可作为历史对照，但本恢复优先复用当前 SOL 基线，避免收入缩放和商品替代重复计算。若未来要恢复完整 v1.1 scale，应先定义预算守恒和与当前 savings pressure 的唯一来源。
- 当前商品清单和 modifier type 需按实际加载组合审计；兼容包可声明类型，但需求关联必须实测。每次升级 EU5 或引入兼容商品都要重跑这项检查。

