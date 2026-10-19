# 痴迷离线实验索引

更新：2026-10-19。现行方案：每地点×商品一个持久浮点 x，外加方案A的暂存队列指针 q（只在排队期间存在）；共享变化容差 δ = 0.1；退潮由国家级时钟承担（首个地点成为成员后保持 T = 240 月，再整国懒衰退）。不允许用按地点键的全局表恢复额外状态。

**现行参考实现已收拢到共享模拟包 [`tools/obsession_sim`](../../../../tools/obsession_sim/README.md)**：图数据接口（合成网格 / 真实地图 JSON 与 CSV）、预设、月度预算、到达月份与历史里程碑、回放导出。下面的实验脚本保留为它的回归锚点和对比项。

## 现行基准

| 文件 | 内容 | 被谁引用 |
|---|---|---|
| `ripple_country_clock_study.py` / `_results.json` | 国家级时钟涟漪（T = 240 与 T = 120），1,600 个图 Voronoi 国家。x ≥ 45 的环带由内向外推进，第 1,760 月全图归零；单商品平均 2.75 万 U/月、峰值 12.2 万 | 02 第 8 节、10 第 9 节；`test_core.py` 回归；可视化默认情景 |
| `delta_adoption_study.py` / `_results.json` | δ = 0.1 在方案A下的效果（增长、强控制半区、全境疲劳退潮）与各商品冻结下限 | 02 第 2.1 节；`test_core.py` 回归 |
| `queue_pointer_scheduler.py` / `_results.json` | 方案A的小图规格：15 项断言（q 只在排队期间存在、待处理目标不重复入队、δ 内不写回、预算暂停等） | 02 第 4 节、10 第 3 节 |
| `immunity_lock_viz.html` | 浏览器可视化：现行基准、对比项与早期实验的逐行 JS 移植，13 个情景自动与 Python 核对；可载入 `tools/obsession_sim` 导出的回放文件（任意坐标的真实地图） | 本目录 |
| `first_batch_transport_results.json` | `python -m tools.obsession_sim.study` 生成：冻结咖啡/茶/烟草城市目标，静态稀疏贸易/走廊、共享预算前沿、组件对照与30组输入敏感性；明确不是完整L2或引擎耗时验收 | 16 首批贸易验证 |
| `observer_archive_survey/` | `survey.py extract` 把观察者十年存档压成摘要 JSON（`tmp/`，不提交），`survey.py report` 生成 `survey_results.json`：所有权/市场/贸易网/道路逐档变化、三商品游戏内流向、制度扩散、所有权历史 | 18 观察者存档用途 |

## 仍有价值的对比项（说明为什么没选）

| 文件 | 对比的问题 | 结论 |
|---|---|---|
| `ripple_source_study.py` / `_results.json` | “水滴入湖”：只把发源地脚本化，亚临界介质能否传远并自然平息 | 单变量一阶介质只做衰减扩散，G = 0.999 时成员半径也只有约 9 跳；中继链只亮各自周围；“衰减停滞即归零”会闪烁 |
| `immunity_lock_study.py` / `_results.json` | x = 100 锁定跳过、变化容差、入流阈值、受控半区、T1/T2 地点计时免疫 | 饱和内部本来就休眠（锁定只省 6.5%）；δ ≥ 1 或 ε_in = 10 冻结全部传播；受控区须增益 ρ+Σp < 1；地点计时需要地点时钟且活跃集变大约 5 倍 |
| `relaxed_state_study.py` / `_results.json` | 放宽一变量约束的三种字段：A 暂存队列指针、B 饱和时间戳、C 入流累计和 | A 采纳（与集合调度逐值相同、服务少 6.4%）；B、C 未采纳 |

全局退潮（全图同时逐节点退潮、全图共享一个 S）的对比不再单独成脚本，用 `tools/obsession_sim` 的预设 `global_node_800`、`global_lazy_800` 复现。

## 仍有效的时间窗口审计

- `historical_wave_schedule.py`：逐年核算商品层、同商品波次不重叠及可选百年包络约束。
- `historical_wave_schedule.json` / `_results.json`：16 波长窗口基线。
- `historical_wave_schedule_short.json` / `_short_results.json`：26 短波百年候选。
- 排期只统计潜在工作窗口，和具体传播方程无关。商品层年下降比例不等于实际运算下降比例。国家时钟的退潮尾巴在窗口之后继续，按活跃国家数单独计成本（12 第 3.1 节）。

## 归档

已撤下架构（多状态、QSS、推送式 sent/pressure）与集合版调度的实验在 [`archive/`](archive/README.md)，可以复现，但不能用于验收现行方案。

## 运行

```powershell
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON docs/design/obsession/experiments/ripple_country_clock_study.py --output docs/design/obsession/experiments/ripple_country_clock_study_results.json
& $env:EU5_PYTHON -m tools.obsession_sim.test_core --full
```

所有 U 都是离线抽象计数，系数是合成网格上的测试值，不是 EU5 测量，也不构成 50 万已达标的结论。
