# 商品替代组恢复文档审计（2026-10-07）

结论：国家级 `global_<good>_pop_demand` 的接口方向成立，符合本次接受市场精度下降的要求；原实施文档仍有会改变需求数值或破坏 SOL 账实一致性的错误，不能照原稿直接实现。本次修订文档并固定审计证据，不代表功能已经恢复或引擎组合语义已经通过测试。

- 历史基线：`origin/v1.1`，`9670e1414d8e2ce5c692672adc588f485baf167c`。
- 当前基线：`substitution`，`ab095a0f`（与本次开始时的 beta 相同）。
- 主审文档：[Global Modifier 实施规格](SOL_Substitute_Groups_Global_Modifier_Implementation.md)，初始为未跟踪文件。[原稿备份](../../tmp/sol_substitution_audit_20261007/original_implementation.md)保留了修订前内容；下表“原稿行号”均指该备份。
- 交叉参考：历史实际需求脚本、`CHANGELOG.md`、历史 v1.1 wiki、早期 `SOL_Per_Group_Demand_Design_Prompt.md`、当前生成源及原版/兼容模组接口声明。

## 1. 按影响排序的问题

| 级别 | 原稿位置 | 发现与影响 | 修订 |
| --- | --- | --- | --- |
| P1 | 90、119、183–188 | 声称跨组商品直接相加；历史 11 个最终聚合块实际都 `divide = 2`。按原文恢复会把这些商品的历史倍率翻倍。 | 记录跨组平均，区分倍率与实际需求。 |
| P1 | 147–199 | 基线份额 A 与独立权重份额 R 不一致。即使 W=1，90/10 的组也会变成 50/50，产生 M=5/9、5，违反中性不变量。 | 撤换原公式；分别定义旧式价格响应候选 A、预算守恒候选 B。 |
| P1 | 170–186 | 重叠商品的完整 B 在每个组重复使用；所谓 A 实际是组内份额，不是“该商品向各组拆分”的份额。跨组 Q 因此不是原来的实际基线。 | A 在倍率层按历史平均；B 显式要求每商品拆分权重之和为 1。 |
| P1 | 194–203、216–219 | 直接 `size=M-1`，内部也乘 M，但未证明同类来源或商品/global/local 需求修正之间的组合方式。仅让 UI 标注“SOL 替代”不能解决内部与实际倍率不同。 | 把组合实测列为接 solver 的前置条件；补充外部 offset 的数值反例。 |
| P1 | 257–263 | victuals 没有接口时仍在内部用非中性倍率，实际人口需求却没变化；改变其他商品的份额也无法补偿这一账面差异。 | 缺接口商品冻结、不参加转移，原需求照常计入账本；补接口后须验证实际需求。 |
| P2 | 147–157、190–201 | 数量/支出混称为同一 Q。一个商品跨市场价格不同时，两种聚合会得到不同国家倍率；没有唯一可实现的规范。 | 替代聚合改用默认价换算的中性参考金额 `B=q×default_price`；同一商品等价于数量加权。当前 SOL 的 `min(市场价,默认价)` 只留在后续 raw spending 层，同时公开地点系数重算后的误差。 |
| P2 | 158–164、194–199 | 对所有正分母用 `max(Q,0.001)`。例如 Q=Q'=0.0005，中性 M 变成 0.5；“无基线写 0”也混淆 M=0 和 size=0。 | 小额用分支中性回退，M=1、size=0；不抬高正分母。 |
| P2 | 135–139 | 将旧 POP 需求链描述为月度地点 modifier 更新，并暗示全刷新覆盖同样缓存。旧全刷新只调用价格列表刷新，没有调用 hub 评分刷新。 | 区分旧脚本值、显示刷新和新 local_pop_demand 链；新完整初始化属于恢复要求。 |
| P2 | 228–255、282 | 国家 static_modifiers 被放在 in_game；若干已删除的旧指示器被称为“现有”。缺少当前生成源和兼容 REPLACE 的修改责任。 | 路径改为 main_menu；标记待恢复项，列出生成源与所有基础/兼容目标。 |
| P2 | 266–278 | 一月更新全部 M，却允许低频 AI 的地点系数沿用旧快照；“默认 AI 月求解”也与当前默认开启年度低频不符。 | 市场缓存一月更新；国家 M 与地点/国家 solver 成套刷新，月度持续应用同一缓存。 |
| P2 | 31、292–295 | “56/57”没有定义集合；忽略 JTG 自己声明的 modifier types，并把缺原版类型近似当成缺全部接口。 | 固定各商品集合，检查最终加载定义，区分类型声明与引擎实际关联。 |

P1 表示会改变主要需求行为或使账本与引擎不一致；P2 表示实现前必须消除的范围、边界或接入问题。

## 2. v1.1 实际机制

### 2.1 数据流与归一化含义

历史调用链为：市场价格相对默认价 → 六个非中性档位的全局市场列表 → POP scope 的商品权重（价格、宗教、文化、地点偏好）→ 组内权重归一化 × N × 阶层组缩放 → 多组平均 → `REPLACE:pop_demand` 商品入口。最后还要由引擎结合该商品的基础人口需求；归一化的对象是倍率权重，不是实际商品数量或金币预算。

历史单组代码含 `10 / max(location.development,1)`，这是旧版抵消逻辑。当前基线已经通过 `DEVELOPMENT_SCALE_ON_DEMAND=0` 及商品阈值修正处理开发度，迁移时不能再叠加旧抵消项。

历史组缩放包含 `(1+savings_pressure) × demand_base × era_coeff × scarcity_adj`。非部落民的 demand_base 为 `GDP_per_capita × budget_share / P + offset`，预算阈值 3、8、25 对应四个区间；部落民 demand_base=1。时代补偿是 1.5 起、逐时代 ×0.95。市场稀缺补偿以每商品唯一主组的四区间平均预算份额加权 `1/P_tier-1`，加 1 后缓存于市场中心。它不是组内替代本身，直接接入当前收入闭合 solver 会重复调整总量。

六档权重及严格比较边界与原稿一致：`>2.30 → 0.25`、`>1.70 → 0.50`、`>1.30 → 0.75`、`<0.40 → 2`、`<0.65 → 1.5`、`<0.85 → 1.25`，其余为 1。当前遗留生成器的 absent 档不属于这个历史提交。

### 2.2 商品集合与重叠

| 集合 | 独立商品 | 说明 |
| --- | ---: | --- |
| v1.1 历史表 | 56 | 55 核心 + victuals；20 组、67 条成员关系，11 商品各属两组 |
| 当前核心表 | 56 | 移除核心里的 PP victuals，新增 camels 到 mounts |
| 当前核心 + PP | 57 | victuals 由 PP 兼容目标提供；需求接口需补充验证 |
| 当前核心 + JTG | 82 | 另加 26 种直接需求商品；其类型均有声明，替代组归属尚未定义 |

v1.1 的跨组商品为 cloth、fine_cloth、lumber、pottery、beeswax、paper、glass、wine、fish、wild_game、mercury。它们都使用两个组倍率的平均值。一个最小例子是 cloth 两组倍率分别 0.6 和 1.4，最终为 1.0，不是 2.0。若之后比较同一商品“当期平均/中性平均”，共同的除数可代数消去，但这不使历史“直接相加”的描述正确，也不能消除基线被重复计数的问题。

victuals 历史权重由 `sol_pp_victuals_compat_is_on` 开关控制，关闭时为 0；luxury_food 仍固定 N=4。当前核心只含三个该组商品，这属于恢复时必须明确的目录适配。

### 2.3 可复核源码证据

以下历史路径都应通过 `git show 9670e141:<path>` 读取，不能在当前 src 中寻找同名文件。行号来自该提交。

| 历史文件（相对仓库根） | 行号 / 事实 |
| --- | --- |
| `src/stable/in_game/common/goods_demand/z_SOL_pop_demand.txt` | 10：`REPLACE:pop_demand`；文件头明确继续与商品中的 pop_type 需求组合 |
| `src/stable/in_game/common/script_values/SOL_goods_demand_values.txt` | 33：单组公式；348：luxury_food 的 N=4；679–742：11 个最终聚合全部 `divide = 2` |
| `src/stable/in_game/common/script_values/SOL_goods_weight_values.txt` | 15：cloth 价格与气候偏好；92：分母下限；1052：wine 的 POP 偏好；1507：victuals 兼容开关；1605：luxury_food 四成员 |
| `src/stable/in_game/common/script_values/z_SOL_group_demand_scales_location.txt` | 28 起：组缩放的实际乘法链；顶部“时代从 2.0 起”的注释已经过时 |
| `src/stable/in_game/common/script_values/z_SOL_group_budget_shares.txt` | 8–10：三个阈值 3、8、25，因此是四个区间 |
| `src/stable/in_game/common/scripted_effects/z_SOL_scarcity_score.txt` | 6：评分公式；1616：每市场中心缓存一次 |
| `src/stable/in_game/common/script_values/SOL_pop_values.txt` | 312：hub 评分缺失时回退 1 |
| `src/stable/in_game/common/situations/SOL_economy_situation.txt` | 27–29：一月依次调用列表刷新和 hub 评分刷新 |
| `src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt` | 1295：全刷新仅显式刷新列表；1316 起：时代系数 1.5、1.425 等 |

## 3. 新接口和求解器的边界

原版 `main_menu/common/modifier_type_definitions/00_modifier_types.txt:12773` 起声明通用 global/local 与逐商品国家需求修正；官方 `docs/modifiers.log:1735` 也列出商品需求类型的 Country 分类。`main_menu/common/static_modifiers/institutions.txt:57` 的 `printing_press_books` 使用 `global_books_pop_demand=0.2`。这些证据支持国家级修正的对象类型和目录，尚不能证明不同需求层次之间的运算顺序。

当前 `src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt:212` 起构建市场共享的七种人口单位支出，逐商品项是校准数量乘 `min(市场价,默认价)`，以 `goods_supply_in_market>0` 过滤。3214 起才在地点读取这些总额并乘对应人口数。现有缓存没有保留完整的每商品金额项；国家商品倍率不同后不能继续直接共用最终阶层总额。必须保留原始市场明细，在国家/地点层应用已验证的实际商品倍率，再进行 raw spending 和国家四类 solver。

两个关键反例：

- **金额与数量口径**：同一商品两市场数量 1/1、有效价格 1/2、当地目标倍率 0.5/1.5。数量加权为 1；金额加权为 `(1×0.5+2×1.5)/3 = 7/6`。
- **同类百分比若相加**：外部 e=-0.75、目标 M=0.5，原稿写 size=-0.5 得到总因子 -0.25（还可能被引擎截断），不是原外部因子 0.25 的一半。正确增量在这个假设下是 -0.125。必须通过游戏观测确认实际规则，并检查商品修正与 local_pop_demand 的组合；内部直接乘 M 不能先行当作事实。

国家倍率还会统一影响各阶层及可能未纳入七类账本的 slaves。市场精度损失虽已接受，仍需记录这种附带影响。旧宗教/文化权重运行在 POP scope，不能不经聚合就用于国家 scope，也不能把旧偏好重复乘进基线。

## 4. 对其他文档的判断

- 早期 `SOL_Per_Group_Demand_Design_Prompt.md` 只有十组，是曲线设计任务草案；已补历史标记，不能用来覆盖二十组实际实现。
- `CHANGELOG.md` 描述二十组和六档价格响应有参考价值，但权重公式略去最终跨组平均，恩格尔段落“三段”未覆盖实际第四区间。应以固定提交的代码为准。
- 历史 wiki 和 `_data.py` 将次级成员表称为显示用途，不代表最终需求脚本没有跨组逻辑；文档和脚本属于不同层次。
- 当前 `PROJECT_OVERVIEW.md` 正确说明替代组运行时已退役。本次只审计文档，无新运行时功能，不应更新成“已恢复”。

## 5. 验证与下一阶段

本次用 eu5 Python 环境读取固定历史提交，程序化核对 20 组、56 商品、67 成员关系、11 个平均聚合块；核对当前 56 种核心商品及 JTG 26 种需求商品的类型声明覆盖。离线复算档位边界、中性反例、跨组平均、两市场聚合、低基线 epsilon 反例及外部 offset 推导，[检查结果](../../tmp/sol_substitution_audit_20261007/results.json)全部通过。知识摘要已重新生成；`validate.py --changed` 返回无修改的 mod 文件，`git diff --check` 通过。以上属于源码和数学审计，不是游戏运行验收。

建议第一阶段只恢复六档价格响应，采用修订规格的方案 A、显式 V=1，以当前金额口径聚合；保留现有收入求解器目标。方案 B 的预算转移是另一个数值设计。正式接入前需固定此选择，并实测商品/通用 global/local 修正的组合、兼容自定义商品关联、供给与需求更新周期；之后再同步基础和兼容生成器、生命周期与 UI。国家级实现方向无需重新确认。
