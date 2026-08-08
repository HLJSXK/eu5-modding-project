# SOL 国家级阶层需求闭合模型（实现说明与原始设计 memo）

> Created: 2026-08-05
> Updated: 2026-08-08
> Status: implemented in `stable` and `sol_standalone` as a four-stratum, hard-total, nonnegative approximation. The old exact 4x4 result is retained only as diagnostic status; raw fallback is used when the four-stratum gate rejects every candidate.

## 0. 当前实现

当前运行时不再从少量锚点地点硬解修正量，而是在贵族、教士、市民、下层四个类别组成的类空间中求解。类系数是直接应用的最终系数，和遗留锚点路径的 `raw + delta` 语义完全分开。

### 0.1 改动范围

- 地点级聚合源: `scripts/sol_economy_effects_source.py`; 生成目标为 `src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt` 和 `src/sol_standalone/in_game/common/scripted_effects/A_SOL_economy_effects.txt`
- 国家级线性空间源: `scripts/sol_country_demand_solver_source.py`; 生成目标为对应目录的 `B_SOL_country_demand_solver.txt`。A 文件只保留 raw 计算、地点分类、国家矩阵聚合、诊断和 modifier 应用，B 文件独占精确诊断、KKT/高斯消元、五种候选、gate 和策略选择。Jomini effect 是全局命名空间，因此跨文件调用契约不变。
- 显示值: `src/stable/in_game/common/script_values/SOL_economy_values.txt`
- 面板: `src/stable/in_game/gui/panels/situation/global_living_standard.gui`
- 触发: `src/stable/in_game/common/on_action/SOL_economy_on_actions.txt` 和 `src/stable/in_game/common/situations/SOL_economy_situation.txt`
- 生成目标: `src/sol_standalone/...` 的对应文件
- 兼容层复查: `scripts/gen_sol_pp_compat.py`, `scripts/gen_sol_jtg_compat.py`, `scripts/gen_sol_mnt_compat.py`

### 0.2 平衡分类

`sol_compute_location_pop_demand` 先计算并缓存地点原始系数 `raw = liquid_funds / base_spending`，同时令 `final = raw`。基础支出不超过 `0.00001` 的地点使用类 0，不参与分类和矩阵，任何失败也都天然保留 raw。

对有效地点 `i` 和阶层 `e`，先计算地点份额 `p[i,e]` 与全国份额 `mu[e]`：

```text
p[i,e] = location_base[i,e] / location_base_total[i]
mu[e]  = country_base[e] / country_base_total
```

分类亲和分数使用相对全国结构，而不是比较四阶层的绝对权力：

```text
normalizer[e] = max(mu[e], 0.02)
affinity[i,e] = clamp((p[i,e] - mu[e]) / normalizer[e], -3, 3)
```

因此一个下层绝对占比很低、但明显高于本国平均值的地点，仍可成为下层类候选；贵族在全国普遍占优本身不再把全国地点都压入贵族类。

第一遍地点扫描记录最高亲和项作为 `structural class`，并把最高分与第二高分之差记为 `confidence`。第二遍通过 `ordered_owned_location` 按 confidence 从高到低处理地点，先固定结构最鲜明的地点；该全量循环必须显式设置 `max = 100000`，因为 `ordered_*` 省略 `max` 时只返回默认的单个结果，并不表示无限遍历。四类的目标基础支出均为：

```text
target_class_base = country_base_total / 4
```

地点进入候选类 `c` 时使用动态分数：

```text
balanced_score[i,c] = affinity[i,c]
                      - 1.5 * current_class_base[c] / target_class_base
```

选中类后立即累计该地点的全部基础支出，后续地点便会倾向欠载类。精确平局仍固定为贵族、教士、市民、下层。该方法只增加一次地点扫描，目标是让四类基础支出接近各 25%，同时保留足够大的相对结构差异；它不再追求不符合游戏实际的对角矩阵。

### 0.3 当前近似求解器

运行时把 `commoners + tribesmen` 聚合为 lower，保留原始 raw 系数、国家矩阵和地点 modifier 语义。`sol_country_demand_solve_mode = 3`、`sol_country_demand_solver_size = 5` 表示固定 5x5 KKT 求解；`sol_country_demand_exact_status` 只保存旧精确 4x4 诊断。

四个硬总额 L2 候选按 `balanced_l2`、`improvement_l2`、`target_l2`、`absolute_l2` 仍保留给玩家国家作完整比较；AI 运行时采用 `improvement_l2` 快路径。候选调用只对实际存在的矩阵列展开：`k` 个非空阶层列最多遍历 `2^k - 1` 个 active class 集合；当 `k = 4` 时跳过四个 singleton 集合。`minimax_ratio` 只对 `is_human = yes` 的玩家国家运行，并使用同一 active-set 预筛。非 active 因素用单位行固定为 0。KKT 总额行满足 `sum(M * factor) = sum(target)`，行尺度分别为：

```text
balanced_l2    max(abs(raw), abs(target), epsilon)
improvement_l2 max(abs(raw-target), epsilon)
minimax_ratio  max(abs(raw-target), epsilon)
target_l2      max(abs(target), epsilon)
absolute_l2    1
```

负因素、奇异主元、硬总额残差和数值残差不合格的候选丢弃；`[-epsilon, 0)` 只钳制到 0。玩家国家的 `minimax_ratio` 运行时入口使用固定有限顶点展开，顶点边界来自总额等式、四行正负残差边界和 active 因素边界。AI 的策略 5 gate 缓存保持初始化值 0，不参与最终选择。

候选必须通过四阶层 gate：四个 raw 绝对误差都大于 `0.00001`，且每层改善量都大于 `max(0.00001, raw_abs_error * 1e-9)`。通过 gate 的候选按平均改善比、平均绝对改善、目标函数和固定策略顺序决胜；没有候选通过时 `sol_country_demand_selected_strategy = 0`，因素为 1，最终保持 `raw_fallback`。缺失类别只让对应矩阵列为空，不再直接阻断尝试。

成功选择的因素继续写入 `sol_country_class_coefficient_1..4`，地点最终系数仍为 `raw * class_factor`，不增加上限。CMF 日志同时记录策略、gate、精确诊断状态、候选统计、因素、四阶层最终误差和硬总额残差。

### 0.4 聚合与求解（历史精确路径）

1. 对最终四类聚合基础支出，构造 `M[e,c] = sum base_spending[e] in class c`，求解 `M * class_coefficient = target`。
2. 求解只要求四类存在且各自具有足够基础支出，不再要求某类的目标阶层绝对支出高于该类所有交叉阶层。
3. 高斯消元前按全国对应阶层基础支出逐行预处理：`A[e,c] = M[e,c] / country_base[e]`，`b[e] = target[e] / country_base[e]`。这是等价行变换，不改变系数解；归一化主元阈值为 `0.0001`，避免贵族与小体量阶层的量级差掩盖病态矩阵。
4. 求解后要求四个类系数均在 `[0, 20]`，并仍按原始未归一化矩阵验证每行残差不超过 `0.01 + RHS * 0.001`。
5. 成功时，同类地点使用对应的 `sol_country_class_coefficient_1..4`；失败时不调用类应用效果，所有地点保留 raw。country driver 不自动回退到遗留锚点法。
6. `raw`、类系数和 `final` 保持独立语义；类路径不复用 `sol_delta_1..4`，也不要求四个系数同号变化或总和为 0。

### 0.4 CMF Action Log

人类国家的 CMF 调试日志会同时记录分类质量、负载均衡和求解质量。每条日志只表达一个概念并最多显示四个动态值；必要的宽向量拆成短行，次要字段不挤入同一行：

- 全国结构；每类地点数/base/系数；四类共同的 25% base 目标、平衡权重、最大单地点 base 及其相对目标倍数。
- 未平衡的 structural class 数量；四维亲和分数范围拆成贵/教与市/下两行；全国 confidence 数量/均值/最小/最大。
- 每类 base share、相对 25% 偏差、signature margin 和原 structural preference 保留率。
- 每类一个最高亲和代表地点，只显示地点名及 base/亲和/confidence。
- 原始和按行归一化 4×4 矩阵各按四值行输出；方程行只显示 lhs/rhs/residual，另记 RHS、主元、类系数和最终误差。
- 失败时明确记录缺类、奇异主元、负系数、系数超过 20 或残差/容差，并说明 final 保留 raw。遗留锚点日志仍分别显示 raw、delta、candidate，避免和类系数混用。

### 0.5 运行时 gate 与失败状态

- 四类 base share 应尽可能接近 `0.25`；超大单地点可能造成不可消除的离散偏差，必须由最大地点/类目标倍数解释。
- 四类的目标 signature margin 是诊断值，可以为负；分类区分度不足应通过实测 Log 调整权重，而不是恢复绝对对角硬门槛。
- 旧 4x4 路径的缺类、奇异主元、负系数和行残差状态只写入 `sol_country_demand_exact_status`。近似候选不设系数上限；其 pivot、非负性、KKT 数值残差、硬总额残差和 minimax 可行性检查失败即丢弃。
- gate 只有在四个 raw 绝对误差都大于 `0.00001` 且四个改善量都超过 `max(0.00001, raw_abs_error * 1e-9)` 时才通过。选中策略编号为 `1..5`；所有候选 gate 失败时编号为 `0`，四个类系数写回 `1`，最终地点系数保持 `raw_fallback`。
- 缺失类别只产生空矩阵列，仍允许其它可用列参与近似；最终是否应用完全由四阶层 gate 决定。月度 modifier、面板和日志必须区分 raw 与 final，并读取同一套 final coefficient cache。
- 生成后检查 stable、standalone 和三个兼容目标；后者只覆盖各自需要改写的效果，完整分类 helper 继续由其 SOL 依赖提供。

### 0.6 2026-08-07 实测经验与下一步判据

匈牙利实测中，189 个有效地点全部完成分类，最终地点数为 `49/55/9/76`；四类 base 为 `19.0/16.7/18.6/19.3`，相对共同目标 `18.4` 已经足够均衡。因此必须把“分类覆盖与负载均衡成功”和“类系数求解可用”视为两个独立阶段，不能再用求解失败反推分类没有运行。

该轮归一化矩阵为：

```text
        C1       C2       C3       C4
贵   0.27465  0.23506  0.20065  0.28962
教   0.23850  0.26099  0.20551  0.29498
市   0.19951  0.14792  0.62584  0.02670
下   0.24850  0.26610  0.05854  0.42684
```

主元 `0.27465/0.05688/0.49263/0.07254` 和原方程残差都表明消元与回代正常；失败来自目标不在当前矩阵的有界非负可行域内。按截图舍入值反算，全国阶层所需平均倍率约为 `27.4/22.5/2.4/18.7`，而当前上限为 20。由于归一化矩阵每行之和约为 1，只要所有 `k[c] in [0, K]`，每个归一化 RHS 必须也在 `[0, K]`；因此贵族和教士目标在任何分类下都不可能通过 `K = 20`。

非负可行性还可用阶层比值快速判断。若 `k[c] >= 0`，对任意两行 `e/f`，最终 `b[e]/b[f]` 必须落在各列比值 `A[e,c]/A[f,c]` 的范围内。该实测要求的贵族/市民比约为 `11.4`，而矩阵能提供的最大列比为 C4 的 `0.28962 / 0.02670 = 10.85`，所以即使取消 20 上限也仍需要负系数。舍入矩阵的精确解约为 `200/133/-85/-144`，与游戏报告的类1系数 `200.734` 一致。

分类结构方面，C3 已形成强市民轴，C4 有下层特征；但 C1/C2 的贵族与教士分布非常接近。原始结构偏好 `14/2/14/159` 被 base 均衡改写为 `49/55/9/76`，说明高平衡权重会把大量低置信度下层地点填入贵族/教士类，改善 base 的同时削弱矩阵区分度。后续不能只调分类数量或只追求 25% base，应同时观察 base 偏差、signature margin、结构保留率、矩阵正锥可行性和系数范围。

下一轮设计应先明确选择：继续追求精确闭合时，需要放宽系数尺度并让分类目标显式奖励矩阵区分度；若优先保证游戏稳定，应考虑有界非负近似求解，以残差最小而非严格等式为目标；另一条路线是以 raw 为基线求独立的类 delta，保留地点 raw 差异并只补偿国家级阶层错配。当前失败时保留 raw 的 fallback 是正确的，匈牙利最终误差约为 `-139/+18/+18/+103`，合计接近 0，表示全国总支出守恒但阶层间发生错配。

下文第 1-10 节保留原数学 memo，作为锚点法和约束求解的理论依据。

## 1. 目标

当前 SOL 的需求闭合是“地点级单标量”：

```text
location coefficient -> all strata in that location
```

这在各地点阶层结构相近时工作良好，但在“乡村型地点 A”和“首都型地点 B”并存时，会把阶层需求的误差分散到不同地点上，最终导致某些阶层长期偏富、另一些阶层长期偏穷。

本方案的目标，是把闭合对象从“地点级收入 = 地点级支出”提升为“国家级阶层收入 = 国家级阶层支出”，同时仍然只使用地点级系数作为运行时控制轴。

---

## 2. 记号

设国家内有：

- `m` 个阶层，`e in {1, ..., m}`，当前通常是 `m = 4` 或 `5`
- `n` 个地点，`l in {1, ..., n}`

对每个 `e, l` 定义：

- `I_{e,l}`: 地点 `l` 上阶层 `e` 的净收入
- `C_{e,l}`: 地点 `l` 上阶层 `e` 的基础支出
- `k_l`: 地点 `l` 的需求修正系数

其中 `I_{e,l}` 和 `C_{e,l}` 都已经是“乘过当地阶层人数之后”的总量。

当前脚本里的对应缓存可粗略映射为：

- `I_{e,l}` <-> `local_sol_*_income_display - local_sol_*_building_maintenance`
- `C_{e,l}` <-> `sol_location_*_base_spending`

---

## 3. 当前基线

现在每个地点先形成一个单一标量：

```text
k_l^(0) = F_l / B_l
```

其中：

```text
F_l = sum_e I_{e,l}
B_l = sum_e C_{e,l}
```

也就是把该地点所有阶层的净收入合并后，再除以该地点所有阶层的基础支出合并值。

这个做法的缺点是：

- 不区分该地点内部的阶层结构
- 不区分国家层面各阶层的总收入目标
- 会把“地点构成差异”误当成“阶层需求差异”

---

## 4. 提议模型

先做国家级聚合：

```text
Y_e = sum_l I_{e,l}
```

然后求一组地点系数 `k_l`，使得对每个阶层 `e` 都满足：

```text
sum_l k_l * C_{e,l} = Y_e
```

写成矩阵形式就是：

```text
C k = Y
```

其中：

- `C in R^{m x n}`
- `C_{e,l}` is the `(e,l)` entry of `C`.
- `k in R^n`
- `Y in R^m`

这一步就是你想要的“国家级闭合”：只有地点系数是变量，但约束是按阶层写的。

---

## 5. 与原设想的关系

你的直觉可以写成一个“基线 + 修正”的形式：

```text
k = k^(0) + delta
C delta = Y - C k^(0)
```

这表示：

- 先保留当前地点级模型作为初始值
- 再用一组国家级修正量 `delta` 去消掉阶层总量偏差

如果不加额外约束，且 `rank(C) = m`，则最小改动解可写成：

```text
k = k^(0) + C^T (C C^T)^(-1) (Y - C k^(0))
```

若使用权重矩阵 `W` 来惩罚某些地点的波动，则：

```text
k = k^(0) + W^(-1) C^T (C W^(-1) C^T)^(-1) (Y - C k^(0))
```

这两种写法都只是理论目标；工程实现时不要把它展开成 `n` 维运行时反演，而是把修正限制在一小组锚点地点上。

---

## 6. 可解条件

### 6.1 方程数等于未知数

如果 `n = m`，则精确解存在的条件是：

```text
det(C) != 0
```

### 6.2 方程数多于未知数

如果 `n > m`，则应检查：

```text
rank(C) = m
```

此时一般会有无穷多组解，真正需要补的是“选哪组解”。
如果要沿用“抽取 4/5 个线性无关地点”的做法，就先选一个 `m` 列基底子矩阵 `C_J`，再检查：

```text
det(C_J) != 0
```

这时 `det` 才是对这个方阵子问题成立的条件。

### 6.3 非负约束

如果还要求：

```text
k_l >= 0
```

那么问题变成带约束的可行性/优化问题，而不只是线性方程求解。

换句话说：

- `rank(C) = m` 只保证“有机会解”
- `k_l >= 0` 决定“这组解能不能真正落地”

---

## 7. 关于你提出的归一化矩阵

你写的

```text
R_{e,l} = C_{e,l} / Y_e
```

可以保留为一个诊断矩阵，但更适合用于“条件数/敏感性分析”，不适合直接作为主求解对象。

原因是：

- 它把目标值 `Y_e` 混进了系数矩阵
- 单位会被改写
- 数值条件可能变得更差

更稳妥的做法仍然是直接解：

```text
C k = Y
```

`R` 可以用来观察哪几个阶层的基底结构最接近线性无关，但不要拿它替代主系统。

---

## 8. 与“地点结构差异”的关系

如果进一步把地点支出写成近似可分离形式：

```text
C_{e,l} ~= beta_e * p_{e,l} / sigma_{e,l} * 1 / omega_l
```

其中：

- `beta_e` 是阶层 `e` 的市场级基础支出常数
- `p_{e,l}` 是地点 `l` 上阶层 `e` 的人口量
- `sigma_{e,l}` 是该阶层在该地的有效权重/势力
- `omega_l` 是地点级权重

那么你原来想说的“用慢变量做判别”是成立的。

但要注意：

- 这种分解只适合做近似分析
- `det` 的因子分解只在方阵、且确实存在严格可分离结构时才是严格成立的

因此，`pop / strength / wealth` 更适合做“构造好基底地点”的依据，而不是直接取代方程系统本身。

---

## 9. 运行时复杂度与文件边界

当前运行时已经不是锚点地点法。地点级逻辑在 A 文件中完成：对 `n` 个地点进行 raw 计算、结构评分、按 confidence 排序和一次或数次线性扫描；随后把四阶层支出聚合成固定的 4×4 国家矩阵。国家级线性空间求解在 B 文件中完成，A 通过全局 effect 调用它。

### 9.1 渐进复杂度

- confidence 排序为 `O(n log n)`。
- raw、分类、矩阵聚合和最终地点 modifier 应用为 `O(n)`；常数阶层维度不随地点数增长。
- 四种 L2 候选以及玩家专用的 minimax 顶点求解只涉及 4 个因子加 1 个总额乘子，因此相对 `n` 是 `O(1)`。
- 总体按地点数记为 `O(n log n) + O(n) + O(1)`，所以渐进上仍由排序项决定。

### 9.2 游戏内实际成本

“仍是 `O(n log n)`”不能直接理解为“只多了一次轻量排序”。每次月度刷新执行的固定候选工作为：

- 旧路径每个有效 AI 国家：4 个 L2 策略 × 15 个 active class 集合 = 60 次 5×5 KKT 求解；
- 新路径先做 raw gate 与 `k <= 1` 预筛；AI 只跑 `improvement_l2`，最多 `2^k - 1` 次，`k = 4` 时为 11 次；
- 新路径每个有效玩家国家仍运行四种 L2，并加 `minimax_ratio` 的有限顶点，但同样按实际非空列和 singleton 规则过滤；

普通单人世界刷新因此不再为 AI 展开三种低收益 L2 策略，也不为小矩阵展开空列集合。玩家国家仍保留最稳健的 minimax 诊断和选择能力；A/B 拆分只负责组织边界，不改变单个候选的运行成本。

### 9.3 `world_current` 标量操作核算

按一次加、减、乘、除或绝对值为一次标量操作，赋值、比较、effect 分发和 scope 查找不计入。旧路径在 `world_current` 的 1,504 个有效国家上展开 90,240 个 L2 候选；新路径按 raw gate、`k` 和 AI 快路径筛选后，AI 只保留 `improvement_l2`，`k = 4` 时跳过 singleton。离线回放得到 5,092 个 L2 候选调用，L2 KKT/残差/评估约 1,258,748 次标量操作；按表中同一计数模型计算，这是旧 L2 核心的 9.26%，即约降为原来的 1/10.8。玩家 HUN 的完整策略和 minimax 只增加固定小项。

| 项目 | 旧路径操作数 | 新路径/说明 |
| --- | ---: | --- |
| 国家/策略预处理（含缓存） | 1,126,680 | raw gate 仍为每国常数预处理；AI 仅准备 `improvement_l2` |
| L2 KKT、残差与候选评估 | 13,589,448 | **约 1,258,748**（5,092 候选调用） |
| HUN minimax 顶点 | 134,674 | 玩家专用；同样跳过四个 singleton active set |
| 旧 4×4 精确诊断（仅诊断） | 126,743 | 不变，仍只记录到 `exact_status` |
| **旧路径合计** | **14,977,545** | 新总量还包括分类排序与上述固定诊断项 |

交接时的 21,505,653 是上一版全策略路径的整体基线；本轮新数字只把 L2 候选核心单独列出，便于和预筛/策略快路径对照，不能把新列误读为完整月度刷新总量。

### 9.4 近似准确度对照

在三个拥有有效 SOL runtime cache 的真实存档上重放，共 3,152 个国家。
完整五策略包含四种硬总额 L2 和 `minimax_ratio`；完整四 L2 不包含
minimax；优化 AI 路径只运行 `improvement_l2`，并应用 `k <= 1` 预筛以及
`k = 4` singleton 过滤。

| 路径 | gate 接受 | 四阶层平均最终绝对误差 | 归一化绝对误差 | 平均改善比 |
| --- | ---: | ---: | ---: | ---: |
| 完整五策略 | 1,262 | 11.154344 | 0.306309 | 0.152543 |
| 完整四种 L2 | 846 | 11.446637 | 0.309147 | 0.143097 |
| 优化 AI 路径 | 778 | 11.743938 | 0.311253 | 0.137007 |

上述全体国家均值包含 `raw_fallback`，因此同时反映了覆盖率和拟合质量。
在优化路径与完整路径都接受的 778 个国家中，完整五策略的平均绝对误差
为 `5.785510`，优化路径为 `5.792492`，仅增加 `0.12%`；相对完整四种
L2 的增加为 `0.11%`。对应平均改善比从 `0.559222`/`0.559112` 降至
`0.555071`，下降不到 `0.8%`。

active-set 过滤本身几乎没有精度代价：`improvement_l2` 保留全部集合时
接受 780 个国家，过滤 singleton 后接受 778 个；归一化误差只从
`0.311126` 变为 `0.311253`。完整五策略比优化路径多出的 484 个接受中，
416 个只依赖 minimax，68 个依赖另外三种 L2；这是 AI 端有意放弃的覆盖，
不是已接受国家的拟合误差大幅恶化。

---

## 10. 一句话版本

把每个地点的一个标量需求系数，改成由国家级阶层收入目标反推出来的地点系数向量；地点仍然是执行单位，但运行时只在少数差异足够大的锚点地点上求解，闭合条件改为阶层维度上的国家平衡。
