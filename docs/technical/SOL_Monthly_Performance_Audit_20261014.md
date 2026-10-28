# SOL 1.4 过月性能追溯

> 2026-10-15 三档实机补充：此审计使用的离线 fixture 曾把 `change_local_variable min=0` 错误解释为下限钳制。其“clean 低频 AI”计数仅代表预期路径，不能证明实际每月保持 clean。新存档确认 1461、1415 次 AI dirty 重算，guard 外部基准被错误压为0；详见 `SOL_Three_Save_Performance_Fix_20261015.md`。本文件历史源码归因保留。

日期：2026-10-14。审计代码：`substitution` 分支 `70561daf`。
用户实机配置：CMF + GlorpUI + 完整 SOL，默认设置（AI 降频开启），每个月均有长时间等待。

## 结论与证据边界

新增脚本成本集中在 `dfd3055f`（2026-10-13，国家商品替代实现）。可以确认替代系统引入了大量重复计算、全球 AI 的月度快照检查以及国家商品需求修正的月度重写。**尚不能确认哪一项占据实机过月时间的大部分，也不能确认它是唯一根因**：现有日志没有 effect 分段耗时或每月 dirty 国家计数。

对默认配置，必须区分两条路径：

- **缓存 clean 的低频 AI**：每月执行快照检查及修正重写；不执行庞大的替代篮子计算，也不执行逐商品的地点支出计算。
- **玩家、正常频率 AI、dirty 的低频 AI、年度求解 AI**：先刷新国家替代篮子，再计算地点支出和原有国家求解器。这里存在已量化的重复计算热点。

因此，“所有 AI 每月计算 20 个替代组”不符合当前代码。对用户报告的持续月度卡顿，应优先测量 **dirty 国家数量**、**国家需求修正重写的引擎成本**和**玩家领土的替代计算成本**。本审计没有改动或部署玩法代码。

## 1. 哪次提交引入了变化

| 基线 | 实际含义 | 用途 |
|---|---|---|
| `v1.3.11` = `64f225d0`，2026-07-23 | 较早的 SOL 代码；不包含后续全部 8 月求解器改动 | 不适合单独用来归因游戏 1.4 升级回归 |
| `cd194e05^` = `1eee7cd2` | `src/` 尚未做游戏 1.4 迁移；reference 已更新 | 游戏升级前的 runtime 对照 |
| `v1.4.0` = `ab095a0f`，2026-10-07 | 已完成初期游戏 1.4 兼容，元数据为 261007 | 标签之后才实现替代系统 |
| `09ab11b1` = `dfd3055f^` | 已有新经济 GUI、尚无国家替代 runtime | 隔离替代系统的最直接基线 |
| `dfd3055f`，2026-10-13 | 新增 `C_SOL_substitution.txt`，接入 solve、monthly check 和 apply | 新增计算热点的来源 |
| `70561daf`，2026-10-14 | 修复面板文字上下文等 GUI 问题 | 本次源码审计 HEAD |

`1eee7cd2..v1.4.0` 的 stable common runtime 仅约 62 行新增、4 行删除，on_action 和 SOL defines 没有变化。国家求解器和 AI 年度求解在升级前已经存在。

`09ab11b1..HEAD` 的 `B_SOL_country_demand_solver.txt` 无差异。庞大的 209-case sweep 是原有成本，不能凭文件体积把它认定为 1.4 新增热点。替代系统可以通过 dirty 分支增加它的调用次数，是否发生必须另测。

复核命令：

```powershell
git diff 1eee7cd2 v1.4.0 -- src/stable/in_game/common/on_action src/stable/loading_screen/common/defines
git diff 09ab11b1 HEAD -- src/stable/in_game/common/scripted_effects/B_SOL_country_demand_solver.txt
git diff 09ab11b1 HEAD -- src/stable/in_game/common/on_action/SOL_economy_on_actions.txt
git diff 09ab11b1 HEAD -- src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt
```

## 2. 默认配置的实际调用链

```text
monthly_country_pulse
└─ sol_local_pop_demand_monthly_pulse
   ├─ 低频 AI：sol_check_substitution_snapshot
   │  └─ dirty = 1：sol_solve_country_pop_demand
   ├─ 玩家/普通 AI：sol_update_local_pop_demand_modifiers
   │  └─ sol_solve_country_pop_demand
   └─ sol_apply_local_pop_demand_modifiers
      ├─ sol_apply_country_substitution
      └─ 每个领土重写既有 local_pop_demand 修正

sol_solve_country_pop_demand
├─ sol_refresh_country_substitution        ← 新增；在所有求解器 gate 前
│  ├─ 国家所有地点：商品权重、各人口类型的替代组响应、国家聚合
│  ├─ sol_apply_country_substitution       ← 本次 solve 第一次 apply
│  └─ 保存每个地点的国家/市场快照
├─ 小国/CMF 求解器 gate
└─ raw-only 或国家 solver
   └─ 每地点 sol_compute_location_pop_demand
      └─ sol_compute_substitute_unit_spending
```

精确入口：

- `src/stable/in_game/common/on_action/SOL_economy_on_actions.txt:32`：低频 AI 月度检查，dirty 调完整 solve。
- `src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt:5039`：solve 首行刷新替代组，之后才检查 `<5` 和 CMF 开关。
- 同文件 `:5438`：月度 apply 首行 apply 国家替代修正。
- `src/stable/in_game/common/scripted_effects/C_SOL_substitution.txt:465`：国家替代刷新；`:6137`：快照检查；`:6660`：地点单位支出。

正常 clean AI 的降频仍有效。旧注释“low-frequency AI only re-applies coefficients”现在省略了新增的 guard 和国家商品修正写入，不能据此认定月度成本与旧版相同。

## 3. 已确认的新增计算热点

### 3.1 地点支出：7 次缓存读取变成 215 次

旧版 `sol_compute_location_pop_demand` 对每个地点读取 7 个市场阶层总支出缓存。当前 `A_SOL_economy_effects.txt:4695` 调 `sol_compute_substitute_unit_spending`，后者逐商品、逐人口类型检查并累加。

stable 的正数量商品分布为 nobles 54、clergy 39、burghers 47、laborers 25、peasants 24、soldiers 26、tribesmen 0，共 **215 个商品×人口类型组合**。

| 每地点支出子步骤 | 替代系统前 | 当前 |
|---|---:|---:|
| 市场 map 值读取 | 7 | 215（30.7 倍） |
| 变量变更语句 | 14 | 335（23.9 倍） |

当前还对每个组合检查 map 存在和市场 key 存在；即使该地点没有对应人口，这部分依旧执行。这里的倍率只指支出子步骤，不是总过月耗时倍率。

同一国家、同一市场的 `sum(quantity × effective_price × country_effective_factor)` 与具体地点无关，可以按国家×市场缓存 7 个总价，在地点只读取 7 次。兼容目标应使用各自最终数量，不能混用不同国家的 factor。

### 3.2 替代篮子按地点重复计算

`C_SOL_substitution.txt:816` 的地点遍历对每地点读取 56 个权重，再对有消费的阶层展开组计算。六类消费人口齐全时，实际展开 **96 个组、271 个成员关系、215 个加权聚合组合**。20 个组不是每阶层都全部有效；67 个重叠成员关系也不是 56 个唯一商品。

离线执行计数复核（中性价格、全部商品供给、一个共享市场、各阶层都有正人口）：

| 地点数 | 国家 refresh 变量操作 | 条件节点执行 | 商品 map 值读取 |
|---:|---:|---:|---:|
| 1 | 3,855 | 1,760 | 112 |
| 2 | 7,025 | 3,063 | 224 |
| 10 | 32,385 | 13,487 | 1,120 |

该 fixture 的完整 refresh 变量操作为 **685 + 3,170 × 地点数**，不包含后续地点 raw 计算、国家矩阵或 vertex sweep。3,170 包括主聚合的 3,168 次变量操作及地点快照的两次写入；另外每地点有 430 次 `save_scope_value_as`。

不是领土数平方复杂度。问题是重复展开了相同市场、相同人口类型的篮子响应：在一个国家内，可先按市场聚合各类型人口，然后按市场×人口类型算响应，等价地从 `O(L × 组成员数)` 降为 `O(L × 人口类型数 + M × 组成员数)`。`M` 是该国涉及的市场数。组响应和国家加权聚合应保留 67 个成员关系及既有供给/外部偏移过滤。

### 3.3 clean AI 月月支付的新 guard

设国家拥有 `n` 个有市场的陆地点，`m` 个非零 SOL 商品修正，`m≤56`。

- 每月读 56 种商品外部需求 modifier，执行 **114 + m** 次变量操作。
- 全部领土扫描一次，切换 `n` 次市场 scope，保存 `n+1` 次 scope；每地点检查市场 cache 和国家/市场快照。
- 既有离线 fixture 的条件节点计数为 **347 + 15n + m**；未展开 CMF scripted trigger 的内部判断。
- 检查发现任何失配就 dirty，随后立即重跑替代刷新、地点计算和国家求解。循环不在首个失配后退出。

dirty 条件：没有初始快照、领土数量变化、AI/玩家身份变化、相同领土数量的归属替换、市场变化/消失、市场缓存缺失、外部商品需求偏移变化。没有找到证据证明 scope 相等比较本身无效，也没有现存日志统计 dirty 的频率。

外部偏移使用精确等式比较，固定点舍入/实际修正读取时序应在实机检查；现有 fixture 使用 Python float，不能用浮点误差造成的 dirty 冒充 EU5 复现。

### 3.4 国家商品需求修正每月重写

`C_SOL_substitution.txt:5966`：每月对所有非零商品执行 `add_country_modifier`、`months=2`、`mode=replace`，即使 factor 没变。

发生 solve 的月份，refresh 末尾 `:5898` 已 apply 一次；后续 `A_SOL:5439` 又 apply 一次。因此最多 **112 次 add 请求/国家/求解月份**，refresh 开头还尝试移除已有修正。普通 clean 月最多 56 次 add 请求/国家。

引擎是否因此失效整个国家的人口需求缓存，是与持续月度卡顿高度匹配的候选。**没有 C++ 调用耗时证据，且本地存档显示修正可能根本未成功入库（见第 4 节），不能把 add 请求次数直接视为成功写入或引擎重算次数。**

### 3.5 世界市场 cache 扩大

`A_SOL_economy_effects.txt:212`：每市场缓存从 119 个扩大到 391 个，remove/add 写语句从 **238 次变成 782 次（3.29 倍）**。新增 56 个价格权重、215 个商品×阶层支出和一个 cache marker。

正常在加载/全局 refresh 或一月运行。`C_SOL:468/471` 的国家刷新发现市场缓存缺失，也会触发 `every_market_in_world`。持续每月全世界刷新尚未得到证明；不能把一月路径当成每月路径。

### 3.6 两个开关不能完全隔离替代成本

关闭 exact/approx 只跳过后续 solver body：替代刷新位于 gate 前，小国 `<5` 也同样支付它。关闭替代开关则跳过篮子聚合主体，但仍刷新外部需求基准和快照，地点支出仍执行 215 个组合。因此“关替代仍慢”不能单独排除整次替代实现的成本。

`SOL_economy_situation.txt:15` 的 `on_monthly` 与替代实现前没有差异；它不会新增全球地点替代计算。面板聚合读已有地点缓存，不是另一个隐藏的 215 次支出刷新入口。

## 4. 实机日志与存档证据

### 4.1 GUI 曾持续刷错

本地 EU5 日志会话于 2026-10-14 22:56:57 启动。`error.log` 和 `.1` 到 `.4` 合计 **3,419 次** `ExtraTooltipInfo.GetTintColor` 缺上下文错误及相同数量的 `FetchData failed`，指向 `global_living_standard.gui:1080`。其中 `.1/.2/.3` 每份约 1 MB，各含 840 组错误，在 23:08:48–23:10:03 之间轮转。

这是已发生的 GUI 运行热点；不能把它当作全世界每月替代组的错误。`70561daf` 已改成普通 `text_multi`，部署文件于 23:30 更新，晚于上述会话启动。该日志不能证明最新 HEAD 修复已经在新会话生效。

### 4.2 56 个替代修正初始化失败

`error.5.log:3444` 附近及 `error.4.log` 开头合计 56 条 `add_country_modifier [Invalid database object '']`，每种商品一条，均发生在 **22:57:44 的 PostValidate 初始化阶段**。没有发现这些错误按每月洪泛。

当前 `C_SOL_substitution.txt:5968` 使用 `name = sol_substitute_amber`；官方 `.eu5-base/reference_official_defines/docs/effects.log:105` 也写 `name`，而当前 1.4 原版 `.eu5-base/reference_game_files/game/in_game/common/scripted_effects/country_effects.txt:846` 使用 `modifier`。文档与当前 source 冲突。字段失效是需要复验的兼容性候选，本次未改字段并重启游戏，故不把它当作已验证修复。

本地最新存档（20:37:44 写入、游戏版本 1.4.1、日期 1337.4.1）的只读扫描同时显示：

- 13,588 个地点国家快照正确序列化为 `type=ctry`，市场快照为 `type=mark`，不支持“scope 根本无法持久化”的猜测。
- 1,566 国家×56 商品共 87,696 个 `sol_sub_size_*` 缓存，其中 34,013 个非零（15,883 正、18,130 负）。一个 amber 样本 size 和 effective 分别为 0.00975、1.00975。
- 全文没有任何一个 `sol_substitute_<商品>` modifier ID；只有初始化、年份、商品计数等通用状态缓存。

这确认该存档中内部系数已算出但对应国家修正未入库，也说明内部 SOL 支出与引擎实际需求可能不一致；尚未通过替换字段并重启游戏确认具体修复。该存档处于初始化日期，且早于日志会话，**不是连续月份 dirty 频率或耗时证据**。

精确证据：存档第 2279904/2279910 行的 amber size/effective；第 12159243/12159249 行的国家/市场快照。日志首条在 `error.5.log:3443`，该轮转文件共 23 条；`error.4.log:3` 起另有 33 条。

### 4.3 缺少可归因的 profiler

> 2026-10-27 更正：EU5 在 `-debug_mode` 下有原生脚本 profiler（`Script.Profiling.*`），首份实测见 `SOL_Profiler_Analysis_20261027.md`；本节“缺少 profiler”的判断已过时，原文保留作历史记录。

`performance_degradation.log` 只有 frame 汇总。24.616 秒尖峰在 lobby/初始 1337.4.1 区间；到 1337.6.2 的窗口 max frame 为 2.787 秒，没有 effect 耗时分解。它不能证明“替代组占 CPU 的某个百分比”。`graphs/` 仅缓存初始化依赖图，`dumps/` 为空。

SOL 的 `PERFORMANCE_UPDATE_DEMANDS_MIN/MAX=100` 在 1.4 迁移前已存在，不能当作新回归来源；当前 1.4 原版 defines 中又没有这些键，其有效性需要单独确认。

## 5. 最短的因果验证顺序

每组使用同一初始存档、同一游戏速度和模组列表，在重新启动的会话中执行，跳过加载后的首月，记录至少三个普通月份；一月单独记录。GUI 初始保持关闭，之后再测打开 SOL 面板。确保测的是 HEAD 新会话，避免热更新只替换文件但已有验证对象仍旧。

| 对照 | 保持不变 | 分离出的成本 |
|---|---|---|
| 当前 HEAD vs `09ab11b1` runtime，保留当前 GUI | GUI、goods 校准、原求解器、AI 降频配置 | 整次替代 runtime 引入的月度增量 |
| 当前 guard vs 仅记录 dirty 原因和国家数量 | 原有求解/修正行为 | 验证年度 AI 是否频繁退回月度 solve |
| 国家商品修正只在真实变化/到期时写入 vs 现有每月 replace | 支出计算和求解结果 | 重复 modifier 写入及可能的引擎失效成本；必须先确认修正实际成功加载 |
| 国家×市场总支出缓存 vs 当前逐地点215读取 | 同一最终需求因子与原 solver | 逐商品支出重复读取成本 |
| 相同配置，SOL 面板关闭/打开 | 游戏和脚本 | GUI 刷错与绘制/绑定开销 |

针对 guard，诊断必须至少分别记录：ownership/market、外部偏移、缺 cache/初始状态，另记录完整 solve 和世界 market refresh 的月度次数。现存 human-only CMF solver log无法告诉我们 AI dirty 次数。不要仅通过关 exact 或关替代来下完整结论，也不要为验证把实际用户安装或工作分支直接回滚。

## 6. 已完成的验证

- 阅读 `CLAUDE.md`、知识 brief 与项目概览；按生成产物和 Git 历史追踪真实执行入口。
- `scripts/test_sol_substitution.py`：14 个既有离线测试通过。它验证脚本逻辑，不验证引擎修正加载、固定点语义或性能。
- 用既有 scope fixture 实际执行并统计操作，确认线性重复展开及 clean AI 不走聚合；未把 Python wall time报告为游戏耗时。
- 计数结果：[SOL_Monthly_Performance_Counts_20261014.json](SOL_Monthly_Performance_Counts_20261014.json)。本地复核脚本在 `tmp/sol_performance_audit_20261014.py`，运行环境为 `C:/Users/Hades/anaconda3/envs/eu5/python.exe`。
- 源码归因与实机日志分开；未修改 `src/`，未运行部署，项目概览无需更新。
