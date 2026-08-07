# SOL 国家级阶层需求闭合模型 (实施计划)

> Created: 2026-08-05  
> Status: implemented in `stable` and `sol_standalone` as a 4-class aggregate solve using relative stratum-share overrepresentation. Legacy anchor-location notes below are retained as the original design memo.

## 0. 实施计划

这份文档前半段保留原始数学 memo，后半段先落成工程计划。核心原则只有一条: **先把求解拆成可缓存、可回退、可记录的 country-scoped 流程，再去谈精确平衡**。

### 0.1 改动范围

- 主逻辑源: `scripts/sol_economy_effects_source.py`; 生成目标为 `src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt` 和 `src/sol_standalone/in_game/common/scripted_effects/A_SOL_economy_effects.txt`
- 显示值: `src/stable/in_game/common/script_values/SOL_economy_values.txt`
- 面板: `src/stable/in_game/gui/panels/situation/global_living_standard.gui`
- 触发: `src/stable/in_game/common/on_action/SOL_economy_on_actions.txt` 和 `src/stable/in_game/common/situations/SOL_economy_situation.txt`
- 生成目标: `src/sol_standalone/...` 的对应文件
- 兼容层复查: `scripts/gen_sol_pp_compat.py`, `scripts/gen_sol_jtg_compat.py`, `scripts/gen_sol_mnt_compat.py`

### 0.2 执行顺序

1. 保留 `sol_compute_location_pop_demand` 作为地点缓存构建器，不在这里直接做全局求解。
2. 新增一个 country-scoped solve helper，复用 `gls_accumulate_panel_stats` 的扫描，把 `Y_e`、`C_{e,l}`、`k_l^(0)` 一次性收齐。
3. 引入锚点集合 `J`，用“结构差异优先 + 贴近 `k^(0)=1` + 规模软权重”的方式挑选；年度或结构失效时重选，月度只复用既有锚点。
4. 只解锚点子系统，`rank` 不足、条件数过差或非负约束失败时回退到 `k^(0)`。
5. 把最终 `k_l` 写回按 location key 的缓存，再由月度 `add_location_modifier` 读取。
6. `gls_compute_panel_display` 和 `gls_accumulate_panel_stats` 只读取最终缓存，不再重算第二套口径。
7. `gls_country_sol_all`、`gls_country_location_avg_scale` 保留作诊断，不充当新解本身。
8. `SOL_GUI_ROW_FINAL_COEFF` 应该读取新的 solved coefficient；旧的 aggregate ratio 只保留作对照，不要再冒充主结果。

### 0.3 CMF Action Log

CMF 的 action log 只负责阶段标记和分支说明，精确数值继续放在现有 `sol_*` / `gls_*` 缓存里，面板和调试值负责显示数值。

| Planned key | When | Meaning |
| --- | --- | --- |
| `sol_country_demand_refresh` | 求解开始 | 本次刷新原因、国家 scope、是否是月度脉冲 |
| `sol_country_demand_anchor` | 锚点固定后 | 本次使用的锚点策略、候选规模、锚点类别和条件数档位 |
| `sol_country_demand_result` | 成功写回后 | 解已落地，面板与月度路径可以复用 |
| `sol_country_demand_fallback` | 求解失败时 | 回退原因: rank 不足、负值、缺缓存等 |

- 用 `cmf_log` / `cmf_log_with_args` 即可，不必把日志当成第二套数值存储。
- 只在显式 debug reset、加载刷新或受控的人类国家刷新时清空日志，别在每个月度 tick 清空。
- 锚点日志只记摘要，不记整套浮点细节；需要精确值时，仍然读 `gls_*` 调试缓存。
- 所有写回值和调试值都要按 EU5 的 5 dp 精度处理，别让引擎自己截断。

### 0.4 验证门槛

- 每次刷新后，检查 `sum_l k_l * C_{e,l}` 与 `Y_e` 是否在 5 dp 内一致。
- 检查 `k_l >= 0`，若不满足必须记录 fallback。
- 检查 `max |k_l - 1|` 和 `cond(C_J)` 是否落在可接受区间；太偏的锚点集先换，不要强行用。
- 检查月度路径和面板路径是否读到同一套 final coefficient cache。
- 检查 PP / JTG 兼容输出是否还保留新的 helper 调用和新的 cache 名。

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

## 9. 建议的实现路线：锚点地点法

运行时不要直接解 `n` 维系统，而是只在 `m` 个锚点地点上做修正。其余地点保持当前基线 `k^(0)`，这样求解规模固定，随地点数增长的只是一次残差汇总，而不是方程求解本身。

### 9.1 选锚点

- 先过滤候选：只看 `owned land` 地点，且 `B_l > eps`、`F_l > eps`、有效阶层数足够。没有实际支出贡献的点不要拿来当锚点。
- 再做结构归一化：`u_l = C_{:,l} / sum_e C_{e,l}`。锚点比较的是“阶层结构方向”，不是单纯城市大小。
- 再看结构覆盖，再看规模质量。结构覆盖优先于绝对量，但规模权重仍要保留为 soft weight，避免过小地点把 `k` 推得太跳。
- 推荐 greedy 选法：先挑一个 `k_l^(0)` 接近 1 且结构独特的种子，再反复加入与已选集合角距离最大的候选，直到凑满 `m` 个。
- 类别上尽量覆盖不同结构：首都、港口/商贸、工业城、普通农区、边疆混合地带。不要把 `m` 个锚点都选成同一种高人口大城市。
- 如果有多个候选同样接近，优先选 `k_l^(0)` 更接近 1、`B_l` 更稳定、`control` 更高的点。锚点越接近基线，最终解通常越不需要大幅摆动。
- 锚点集可以在年度刷新时重选；月度只复用已经选好的 `J`。如果国家结构变化很大，或者 `cond(C_J)` / `max |k-1|` 变差，再提前重选一次。
- 锚点筛选不要做全量两两比较；候选打分必须是对当前已选集合的增量评估，避免把问题抬成 `O(n^2)`。
- 如果国家很大，先构造固定大小 shortlist（例如 `4m` 或 `8m`），再从 shortlist 里做最终 greedy 选择。这样筛选仍然是线性扫描加小常数修正，而不是全局密集比较。

可执行的打分可以写成：

```text
score(l | J) = diversity(l, J) * quality(l) * weight(l)
```

其中：

- `diversity(l, J)`：与当前锚点集合的最小角距离，越像“另一种结构”越高。
- `quality(l)`：`k_l^(0)` 越接近 1 越高，表示这个点不需要用很激烈的系数纠偏。
- `weight(l)`：`B_l` 的软权重，建议用 `log(1 + B_l)` 一类的平滑形式，避免超大城市把结果完全主导。

### 9.2 只解锚点

把未知量写成：

```text
k = k^(0) + S_J δ_J
```

其中 `S_J` 是只在锚点地点上非零的选择矩阵。于是主系统变成：

```text
C S_J δ_J = Y - C k^(0)
```

实际实现时也可以直接写成：

```text
C_J k_J = Y - sum_{l\notin J} C_{:,l} k_l^(0)
```

然后只求 `k_J`。由于 `|J| = m`，这个子问题是唯一解或小规模带约束解，不再出现 `n` 维运行时求解。

这一步真正关心的不是“是否能解”，而是“解出来的 `k_J` 是否温和”。如果求得的锚点系数明显偏离 1，通常说明锚点集合选得不够像一个好的基底，而不是该直接把系数硬推过去。

### 9.3 约束与回退

- 若 `det(C_J)` 接近 0 或 `cond(C_J)` 太高，就先换一组锚点，而不是强行继续。
- 若 `k_J` 的 spread 太大，或者有明显负值，就把这组锚点标记为“结构不合格”，再尝试下一组。
- 若需要 `k_l >= 0`，就在锚点子系统上做非负投影或小规模约束优化；但这应该是最后一层修正，不是锚点选择的默认依赖。
- 若约束无解，回退到当前基线 `k^(0)`，避免把运行时搞成“硬求解器崩溃”。
- 如果有效阶层数少于 `m`，就按 `rank(C)` 退化成更小的锚点集。

### 9.4 复杂度

- 解算部分固定为 `O(m^3)`，这不是瓶颈。
- 锚点筛选应当是 `O(nm)` 或 `O(nK)` 级别的一次性扫描，其中 `K` 是固定 shortlist 常数；不要写成 `O(n^2)`。
- 由于 `m` 只有 4/5 左右，`O(nm)` 实际上就是线性开销，且可以和现有 `gls_accumulate_panel_stats` / `sol_update_local_pop_demand_modifiers` 的国家-地点遍历合并。
- 年度重选锚点时才承担这笔额外扫描；月度只复用缓存中的 `J`，所以摊到月度后几乎就是常数。
- 如果后续仍然担心大国性能，就把 shortlist 和锚点诊断缓存下来，只在 `cond(C_J)` 或 `max |k-1|` 超阈值时重建。

---

## 10. 一句话版本

把每个地点的一个标量需求系数，改成由国家级阶层收入目标反推出来的地点系数向量；地点仍然是执行单位，但运行时只在少数差异足够大的锚点地点上求解，闭合条件改为阶层维度上的国家平衡。
