# obsession_sim：痴迷扩散离线模拟核心

更新：2026-10-22。这是「痴迷」系统的 Python 离线参考实现。现行三层实验以设计 26 为准，未覆盖项沿用 23，读取 24 的世界状态格式；旧静态情景与城市代理实验保留以复现既有研究。离线验收不代表玩法代码或实机性能已通过。

## 当前流程：26 第三轮交接规格

只拟合六个共同参数：`p、rho、lambda_contact、lambda_ownership、preemption、internal_rate`。领地回流按首都市场之外的流行人口占比计算；商人常驻排除该市场的有领土国家，保留实际份额而不重新归一化。道路与海峡均为单位权重，亲和表全开，酒仅在意大利/法国/伊比利亚的当月基督教地点提供30背景（无酒模拟器）；δ、来源门槛、入口剂量与退潮值按固定设计执行。

两局观察者档案在 `tmp/obsession_worlds_round2/`，各有 52 档，覆盖 1338.4.1–1840.4.1。SOL 局提供 R 的近开局市场边界和 31 档商人先验；原版局作为独立非史实世界，不参与这两项估计。世界事实、73 项修订与地图映射限制见 `world_facts.json`、`world_facts_amendments.json` 及 [第三轮计划](../../docs/design/obsession/26_Round3_Handoff.md)；新增48条审计方事实逐字保留。R常驻共同份额改取冻结样本0.9分位0.01605427509424987。

```powershell
$env:PYTHONUTF8='1'
$env:EU5_PYTHON='C:/Users/Hades/anaconda3/envs/eu5/python.exe'
& $env:EU5_PYTHON -m tools.obsession_sim.experiment freeze-check
& $env:EU5_PYTHON docs/design/obsession/experiments/run_structural_validation.py quick
& $env:EU5_PYTHON -m tools.obsession_sim.round3_workflow fit
& $env:EU5_PYTHON -m tools.obsession_sim.round3_workflow select
# 先提交 selected_params.json 与 selection_log.json，再通知审计方。
& $env:EU5_PYTHON -m tools.obsession_sim.round3_workflow diagnostics
& $env:EU5_PYTHON docs/design/obsession/experiments/build_round3_report.py
& $env:EU5_PYTHON -m tools.obsession_sim serve --graph tmp/obsession_real/eu5_1337.json --port 8767
```

习俗区按静态地图一次构造并定格，拒收全部输入，不向区外邻接输出；同市场输入使用排除习俗区的开放聚合。商人/领地来源与先占继续读取全量值。国家时钟存截止月D：首次非习俗接触后1440月封顶，开放全国流行后缩到240月；未退潮国家开新波不重置D。`tea_1`保留为不计分输入。

`round3_workflow mechanics`完全不载入目标表、不构造判分器，只用第二轮参数体检；`protocol`在体检后生成64候选Latin协议（种子2026102201），前6名补五种子后选一。协议发布前必须完成30种子世界输入审计。不要重跑`round2 world/config/prior`覆盖冻结输入。

`fit` 要求新排序协议已提交；`diagnostics` 要求选参文件与日志已提交，且运行时和冻结哈希匹配。选参只读拟合集，正式诊断包含 S/H×R 各30种子、双局 S/G×O 各10种子、五通道消融、四项单因素回退与双倍预算（均10种子）。超过三分之一拟合 A/B 里程碑在双倍预算下移动超过容差，将阻止 L2 宣称。

年度入口量按用户确认解释为年风险率，可大于 1，每月用 `1-exp(-r/12)` 抽样；退潮期间拒收。报告构建器校验R30种子/O10种子及当前冻结身份，输出 `docs/design/obsession/27_Round3_Results.md`，并为 JSON/离线 HTML 报告补充已知拟合集必要条件差项。正式闸门仍交审计方。离线 HTML 无损压缩内嵌完整报告，原始 JSON 另行保留；载入后移除一次性 DOM 数据块，支持两局与全部种子查看。

工作台位于 `/docs/design/obsession/experiments/structural_workbench.html`：只显示六个可调参数，固定值另列，支持两局结果切换、习俗区拒收与恒定性、国家截止时钟及全国流行/退潮日志、p_order可达上限、K2对手从未出现，以及队列延迟、放弃事件与逐商品 E_gap。R 地图回放在导出前屏蔽留出地点及其到达列，相关统计也去掉留出地点。实现者接口不运行或加载留出结果；正式全集矩阵留给审计方用显式 `--auditor-holdout` 运行。

观察者汇总选择器可切换 SOL/原版局的矩阵指标，运行详情另可逐种子检查 K 案例。通道消融和双倍预算在独立对照表中显示；阶段性报告标明实际完成次数。O 世界仅作条件规律检查，不展示历史年份对比。

`round2 {config,world,prior,audit,audit-batch,observers}` 是输入准备与一致性检查工具；输入准备只在选参前进行。`config` 不覆盖已经选出的六参数文件。世界输入修订后需重新检查、冻结并发布协议。

旧轮次的接口和验收汇总已从本页移除，避免实现者误读全集结果。当前操作以本页顶部和设计 26 为准。

## 1. 它模拟什么

每个商品独立运行一份。每月按以下顺序执行：

1. **外部播种**：事件、行动、风尚把某些地点的 x 提高到指定值，并把该地点和邻居入队（第 0 月的种子视为初始状态，不计费）。
2. **国家级时钟**（退潮模式 `country_clock`）：每个时钟组（通常是国家）在第一个地点 x ≥ 1 的那个月记下加入月份；保持 `hold_T` 个月后整组开始衰退：每月 `S_c ← decay_factor × S_c`，读取时用 `x × S_c`；S_c 低于 0.1 时遍历本组地点重标定一次；全部归零后该组结束。衰退中的地点不再接收输入，也不入队。设习俗保留率 `habit_floor = κ > 0` 时有效值为 `x × (κ + (1−κ)·S_c)`，S_c 低于 `habit_finish_S`（默认 0.01）时整组定格为 `κ × x`，作为习俗长期保留、不再计算（设计文档里写作 κ，避免与 03 的需求强度 h 混淆）。
3. **节点服务**：方案A侵入式队列，每月最多一个逻辑轮（轮长 = 轮开始时的队列长度）。服务地点 v：
   `y = ρ_v·x_v + Σ_u p_v·w_uv·x_eff(u)`，夹到 [0, 100]，小于 ε 归零；只有 `|y − x_v| > δ` 或归零时才写回，并把自己和出边邻居入队，已在排队的不重复入队。
4. **预算**（可选 `budget`）：预扣下一次节点服务会超出当月额度时停止出队，本轮留到下月继续，传播按日历变慢。国家时钟、整组重标定、外部播种先执行，可能已超过额度；它不是全部工作的硬上限。

下述 core 参考模式仍用原加入月语义；新截止月语义只在 structural 层生效。

游戏里允许持久化的只有：地点×商品的 x、排队期间的指针 q、时钟组×商品的加入月份/衰退标志/结束标志/S_c、商品级队列计数。工具里另外记录的到达月份、峰值、帧和时间序列都是**校准用诊断数据，不是游戏状态**。

## 2. 快速使用

```powershell
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON -m tools.obsession_sim presets
& $env:EU5_PYTHON -m tools.obsession_sim graph-info --graph hex
& $env:EU5_PYTHON -m tools.obsession_sim run --graph hex --groups 1600 --preset baseline `
    --out tmp/obs_baseline.json --playback tmp/obs_baseline_playback.json --frames-every 12
& $env:EU5_PYTHON -m tools.obsession_sim.test_core          # 快速测试（约 15 秒）
& $env:EU5_PYTHON -m tools.obsession_sim.test_core --full   # 加上慢速回归
```

`--set key=value` 可覆盖任意 `Params` 字段，例如 `--set hold_T=180 --set p=0.015`。`--budget 40000` 模拟单层每月 4 万 U 的额度。回放文件可以在 `docs/design/obsession/experiments/immunity_lock_viz.html` 的“载入模拟结果”里播放。

Python 内调用：

```python
from tools.obsession_sim import load_json, Params, simulate, milestones, front_profile, front_speed
g = load_json("data/obsession/map_graph.json")
sim = simulate(g, Params(seeds=[(g.names.index("aden"), 0, 25.0)], hold_T=240, series_every=12))
print(sim.summary())
print(milestones(sim, specs, start_year=1450))
```

## 3. 预设

| 名称 | 用途 |
|---|---|
| `baseline` | 现行基准：δ = 0.1，国家时钟 T = 240 月，衰退因子 0.98/月，ρ = 0.99，p = 0.02（测试系数） |
| `baseline_T120` | 对比保持期长短 |
| `baseline_habit30` | 基准加习俗保留率 κ = 0.3，习惯型商品的建议形态（待校准） |
| `growth_only` | 只看增长与前沿速度，校准 p 时最常用 |
| `growth_delta0` | 对比 δ 的作用 |
| `global_node_800` | 对比：全图同时逐节点退潮，δ = 0.1 下冻结在成员档（为什么不用） |
| `global_lazy_800` | 对比：全图同时共享 S 懒衰退，全球均匀（为什么不用） |

ρ、p 的数值都是合成网格上的测试值，没有历史校准。

## 4. 图数据接口（接入真实地图）

`MapGraph` 只装静态拓扑和静态属性：

| 字段 | 含义 |
|---|---|
| `incoming[v]` | 影响 v 的来源地点（u → v） |
| `outgoing[u]` | u 变化时要通知的目标；无向图与 `incoming` 是同一组元组、同一顺序 |
| `in_weight[v]` | 与 `incoming[v]` 一一对应的边系数，乘在 p 上（陆路 1、海路/海峡另定、屏障 0）；`None` 表示全为 1 |
| `owner[v]` | 时钟组下标（通常是国家）；−1 表示不属于任何组，见第 6 节 |
| `group_names`、`names`、`coords` | 组名、地点名（建议用游戏内地点键）、可视化坐标 |
| `attrs` | 任意静态列（市场、人口、文化、宗教……），供生成 `rho_by_node` / `p_by_node` 用 |

文件格式（`graph.load_json` / `save_json`）：

```json
{
  "format": "obsession_sim.graph/1",
  "directed": false,
  "groups": ["YEM", "MAM", "TUR"],
  "meta": {"source": "EU5 1.x map + 1450 save", "center": 0},
  "nodes": [
    {"id": "aden", "name": "aden", "group": "YEM", "xy": [5123.0, 2210.5],
     "nbrs": ["mocha", "lahij"], "nbr_weights": [1.0, 1.0],
     "market": "aden", "population": 18.2, "culture": "yemeni", "religion": "sunni"}
  ]
}
```

邻接可以写在每个节点的 `nbrs`（推荐，保留顺序）或顶层 `edges: [[a, b, weight], ...]`。`directed: true` 时 `nbrs` 表示“谁影响我”。也可以用 `graph.load_csv(nodes.csv, edges.csv)`：`nodes.csv` 至少有 `id`，可选 `name, group, x, y` 和其他列；`edges.csv` 为 `a,b[,weight]`。

加载后先跑 `graph-info`：它报告度数分布并检查索引越界、自环、`incoming/outgoing` 不一致、列长度。最大入度直接决定单个节点任务的预扣上限（`Simulation.reservation`），真实地图的高扇出节点要在这里先看清。

## 5. 校准流程（真实地图）

1. **建图**：用下文 `import-eu5` 从本地游戏资产提取真实地点邻接和可选海峡；海路必须另有明确依据，不能从海洋接壤自动生成。所有者默认来自1337；可使用 `tools/eu5_save_parser` 导出的 `locations.csv` 覆盖。09 建议按 1337/1450/1550/1650/1750 分段使用快照。
2. **定里程碑**：把 `09_Historical_Calibration.md` 的地区里程碑写成 JSON 列表，每项是 `{"name", "names"|"group"|"nodes", "target_year", "fraction", "tolerance_months"}`，含义是“该组地点中 `fraction` 比例在目标年份前后达到 x ≥ 1”。
3. **先校准增长**：用 `growth_only` 调 p、`in_weight` 和 `p_by_node`（亲和、走廊、政策），看 `milestones` 的误差和 `front_profile` / `front_speed`（每年推进多少跳）。
4. **再校准退潮**：切回 `baseline`，调 `hold_T` 和 `decay_factor`，看各组的加入月份、开始衰退月份、结束月份是否落在 11/12 的波次窗口内。
5. **在预算下复核**：加 `--budget`（按同时活跃层数分配的份额），确认减速后的里程碑误差仍可接受。只用不限额结果校准、事后再加上限是不对的。
6. **回放检查**：导出回放文件，在可视化页面里看前沿形状、屏障和飞地是否合理。

## 6. 已知限制与待定项

- **计价**：U 按实验脚本的抽象原语计数，`PRICE_QUEUE`（无时钟）与 `PRICE_CLOCK`（含所有者/S 查询）两套，便于和既有结果逐值对照。真实脚本展开后要替换，不能当 EU5 指令数。
- **p 的即时求值没有计费**：亲和、政策、供货在真实实现里每次服务都要查，估算器里约 +10 + d U/次。
- **时钟组粒度**：模拟用的 1,600 个合成国家平均 8.5 个地点。真实大国一旦首个地点成为成员，T 个月后全国一起退潮，前沿未到达的部分会永远不被点燃。真实地图上要检查 `ever_member` 与覆盖率；需要时改按省/区域分组（游戏内对应作用域能否挂变量是 P0）。
- **无主地点**：`owner = −1` 的地点不参加时钟，因此不会退潮。真实地图里无主但有人口的地点应按市场或区域分到某个组。
- **所有权不随时间变化**：每次运行使用一个静态快照；征服时 x 按旧组 S 换算的逻辑尚未模拟。
- **多商品**：`batch.run_batch` 已实现同日历、同一额度的多商品模拟：先入账全部维护，再轮转分配节点服务。旧单商品 `budget` 仍只限制服务，不能当总工作的硬封顶；共享模式也明确报告维护本身已超额的月份。

## 7. 回归锚点

`test_core.py` 用 `docs/design/obsession/experiments/` 下已提交的结果做逐值回归：`delta_adoption_study_results.json`（增长 δ=0.1、δ=0、强控制半区、全境疲劳退潮）与 `ripple_country_clock_study_results.json`（T=240、T=120）。核心改动后两者必须仍然一致；如果是有意改变计价或规则，要同时更新实验结果和设计文档。

## 8. 从本地 EU5 真实地图运行

依赖 `numpy`、`Pillow`（项目 eu5 Python 环境已具备）。地图提取只读游戏安装目录；输出到工作区 `tmp/`，不把游戏色图或生成地图提交到仓库。

```powershell
$env:EU5_PYTHON = 'C:\Users\Hades\anaconda3\envs\eu5\python.exe'
$env:PYTHONUTF8 = '1'
& $env:EU5_PYTHON -m tools.obsession_sim import-eu5 `
  --game 'C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V' `
  --out tmp/obsession_real/eu5_1337.json
& $env:EU5_PYTHON -m tools.obsession_sim graph-info --graph tmp/obsession_real/eu5_1337.json
& $env:EU5_PYTHON -m tools.obsession_sim run --graph tmp/obsession_real/eu5_1337.json `
  --preset growth_only --scenario tools/obsession_sim/examples/map_demo.json `
  --set max_months=3000 --out tmp/obsession_real/map_demo_result.json `
  --playback tmp/obsession_real/map_demo_playback.json --html tmp/obsession_real/map_demo.html
& $env:EU5_PYTHON -m tools.obsession_sim run --graph tmp/obsession_real/eu5_1337.json `
  --preset baseline --scenario tools/obsession_sim/examples/coffee_probe.json `
  --out tmp/obsession_real/coffee_probe_result.json --html tmp/obsession_real/coffee_probe.html
```

`map_demo.html` 是双击即可打开的自含报告，有真实地点轮廓、国家边界、时间回放、缩放/平移、地点查找、悬浮详情和可点击里程碑。JSON回放仍可在实验页面载入，旧点图格式继续兼容。显示轮廓默认2048像素宽（`--raster-width`可调，0禁用）；拓扑始终从完整16384×8192色图计算，缩小显示不会改变邻接。

来源与边界：

- `default.map` 指定地点PNG、排除集合和横向环绕；`named_locations/*.txt` 的十六进制RGB把像素对应到地点键。只计算上下左右共享边界，不把对角接触视为陆路。
- 排除 `sea_zones`、`lakes`、`impassable_mountains`、`non_ownable`。默认加入 `adjacencies.csv` 中明确的陆地端点 `sea` 海峡（`--no-straits`可关），不把 `canal` 海区连接变成陆路。不生成推测港口贸易、跨洋路线或自动近邻边。
- 区域层级来自 `definitions.txt`；文化、宗教、原料、地形等来自 `location_templates.txt`；1337所有权来自 `main_menu/setup/1337/10_countries.txt` 的 `own_*` 列表。市场/人口不凭空推测。
- 本机当前资产提取为20,893个陆地节点，其中13,588个有1337所有者，7,305个无主。旧合成实验的13,572不是全世界地图节点总数。四个已命名却没有像素的地点列入 `meta.absent_named_locations` 后排除，避免幽灵节点。
- `--locations-csv <path>` 按地点键覆盖存档属性。默认要求覆盖全部图节点；仅研究局部时加 `--allow-partial-csv`，报告明确标记其余节点沿用1337。存档日期应同时保存在相邻 `metadata.json`；不能将模拟起年1450误认为所有权也来自1450。
- 无主地点保持 `owner=-1`，不会凭空获得国家时钟。要比较更小的时钟组，可显式 `--clock-group area` 或 `province`；这是离线敏感性实验，尚非已核实的游戏内实现。

## 9. 可审阅的校准情景

`--scenario file.json` 支持 `start_year`、具名 `seeds`、地区 `coefficients`、显式 `routes` 和 `milestones`。它们及图的来源信息随结果保存，便于复跑。所有权在一次运行中保持静态；静态路线也不会自动按年代解锁。

```json
{
  "start_year": 1450,
  "seeds": [{"name": "sana_yemen", "year": 1450, "value": 0.5}],
  "coefficients": [{"where": {"region": ["arabia_region", "egypt_region"]}, "p_scale": 2}],
  "routes": [{"from": "venice", "to": "london", "weight": 0.5, "directed": true,
              "note": "人为敏感性实验，必须另补实际贸易证据"}],
  "milestones": [{"name": "开罗风尚", "names": ["cairo"], "threshold": 20,
                  "target_year": 1520, "tolerance_months": 180}]
}
```

选择器支持 `names`、`nodes`、`group` 或 `where`（多个属性AND，单属性列表OR）；空选择器报错。`p_scale`重叠时相乘，显式`rho`按后行覆盖；路线指定已有边时覆盖该边权重，0阻断，单向仅通知指定方向。节点服务顺序和相同输入的结果可复现。

里程碑默认统计`x≥1`，风尚必须写`threshold:20`；也可选45、70、100或`"positive"`（首次非零）。按满足比例向上取整，未到达地点留在分母中；未到达返回null并判定失败。该口径是**等权地点比例**，不冒充09中的人口加权区域指标。首次非零/采纳/阶段到达只作为离线诊断，不新增游戏状态或抽象U费用。回放保留最终帧，不因帧间隔遗漏结束状态。

`coffee_probe.json` 故意保留设计要求的0.5弱入口：基准p=.02、δ=.1使邻居输入小于变化容差，因而可完全无法启动。失败会明确出现在里程碑表，不能通过直接赋予城市风尚来掩盖。`map_demo.json` 用25强种子展示地图传播，明确标记为工程演示。历史年份沿用09草案，逐行史料来源尚未补齐，**两者都不是已经完成的史实校准**。

验证：

```powershell
& $env:EU5_PYTHON -m pytest tools/obsession_sim -q
```

除合成网格逐值回归外，小地图测试覆盖完整像素邻接、横向环绕、海峡/海洋隔离、颜色映射、区域/所有权、CSV覆盖、显示几何及历史阈值；真实地图结果需再次用实际存档、贸易通道和史料校准。

## 10. 页面直接调参、重算

真实地图来自游戏资产；HTML回放中的结果是导出时预计算的。要在页面上改参数并重算，启动本地服务：

```powershell
$env:PYTHONUTF8 = '1'
& C:\Users\Hades\anaconda3\envs\eu5\python.exe -m tools.obsession_sim serve `
  --graph tmp/obsession_real/eu5_1337.json `
  --scenario tools/obsession_sim/examples/map_demo.json --preset baseline --port 8765
```

打开终端显示的本地网址。页面是一个“扩散模拟工作台”：左侧地图，右侧分三页（参数 / 情景与里程碑 / 参数扫描），下方是统计图、里程碑表、运行记录与扫描结果。真实地图与合成六角网格（117×116，1,600 个合成时钟组）在顶部切换，共用参数、播放与统计，两者都调用同一 Python 核心；切换时保留公共系数与日历设置，各自记住种子、情景和回放，运行期间禁止切换。

**地图操作。** 悬浮看详情，点击选中（再点取消；查找框回车也会选中）。选中后可以：设为首个种子；在当前回放月份追加种子；选观察范围（国家、省、Area、Region、次大陆、文化、宗教，取决于图里有哪些属性）；存为地点里程碑或范围里程碑（半数地点 x≥1，目标年先取当前回放年份，要改成史料年份）。观察范围会在地图上描边、淡化范围外地点，并画出范围内接触 / 成员 / 风尚比例曲线；首个接触、10% 成员、半数成员、半数风尚按到达月份精确统计，不受帧间隔影响。

**参数页。** 表单与当前回放不同时，改过的字段标红，并列出差异（种子、情景也比较），提示重算。“启动检查”实时判断每个种子：邻居首次输入 p·x₀ 不大于 δ 时变化不写回，种子无法向外启动（陆路边权按 1，未计地区系数与海峡权重），并给出单点增益 ρ + d̄·p。勾选“计算时实时显示地图”后，重算期间地图每 `frames_every` 个月刷新一次实时画面；取消勾选则继续看旧回放。

**情景与里程碑页。** 种子表和里程碑卡片与高级情景 JSON 双向同步；JSON 无法解析时表格暂停同步，不会覆盖手写内容。地区系数与显式路线目前仍在 JSON 里编辑。

**运行记录与对比。** 每次重算和载入的回放进入运行记录（本页内存，最多 8 次），自动列出相对上一次的参数差异、曾为成员、平静年份、总 U、里程碑通过数。可以查看、恢复参数、删除，或“设为基准”。设了基准且当前回放是同一张图的另一次运行时：节点数图和范围曲线叠加基准虚线；着色选“与基准比较到达”按首次 x≥1 的月份差上色（蓝＝更早、红＝更晚，±20 年饱和；绿＝仅本次到达，紫＝仅基准到达）；里程碑表增列基准模拟时间和“本次 − 基准”；地点详情显示基准到达时间。

**参数扫描。** 以参数页当前设置为基础，只改一个参数（p、ρ、δ、T、退潮因子、κ、预算、首个种子强度），依次跑 1–24 个值（可按起止与个数生成等差 / 等比序列）。扫描只记录统计与年度成员数，不保存逐帧地图；已完成的组边算边显示。结果有每组成员曲线、“里程碑误差 ÷ 容差”图（阴影 ±1 为容差内，空心点为未到达）和结果表；表中 ★ 是 Σ|误差|/容差 最小的一组（未到达按大罚分）。“采用并重算”把该值写回参数页并完整重算。真实地图单次 3000 个月约 5–7 秒。

**时间轴与键盘。** 节点数图与范围图画全程曲线，竖线标当前月，▲ 标里程碑目标（绿＝符合、红＝超出、灰＝未到达）；点击或拖动图表跳转。焦点不在输入框时：空格播放 / 暂停，← → 逐帧（Shift 十帧），Ctrl+Enter 在任何地方都会重算。

服务只监听本机，启动时读取指定图；每次计算使用独立状态，运行时不重读整幅游戏PNG；重算与扫描共用一个作业槽。直接双击HTML且未启动服务时，地图、选中、观察范围、运行记录对比仍可用，重算和扫描面板会说明启动方式。

接口（只接受本机同源请求）：`GET /api/config`、`GET /api/preview?map=real|hex`、`POST /api/run`、`POST /api/sweep`（`{"run": <同 /api/run>, "param": 名称, "values": [...]}`）、`GET /api/jobs/<id>[?live=1]`（`live=1` 时运行中返回最新帧）、`POST /api/jobs/<id>/cancel`。

## 11. 稀疏贸易、走廊与首批三商品

现已实现按年代开闭的有向贸易边、沿真实邻接最短路加权的陆路走廊、海峡折扣、有限发源输入、有条件的弱接触、百年传播窗口与原 x 的跨波复用。关闭路线不在运行图中；路线开放只唤醒目标，不要求来源先变化。国内海运可连接两个真实商港（如博多—大阪），而不是要求中途每个陆上村落都先采纳。所有通道仍使用同一个 x 更新式、δ 与队列；没有另存压力或逐边旧贡献。

真实存档可用 `transport.markets` 建每市场最多 `max_hubs` 个高人口枢纽的环（各枢纽最多两个市场内贸易邻居），边权按市场人口份额归一化；`flows` 以实际市场键和贸易量连接两个市场的最大人口枢纽。缺市场/人口时明确报错，不用像素面积假冒人口，也不创建市场全连接图。没有存档时使用经用户许可、标明 C 级假设的有限历史港口/商队网络。

```json
{
  "start_year": 1450,
  "seeds": [{"name": "al_mukha", "value": 0.5}],
  "waves": [{"start_year": 1450, "end_year": 1530}],
  "sources": [{"name": "al_mukha", "start_year": 1450, "end_year": 1470,
    "amount": 0.5, "requires": {"raw_material": "coffee"}, "evidence": "finite origin input"}],
  "transport": {"strait_weight": 0.5, "routes": [
    {"from": "jeddah", "to": "suez", "start_year": 1490, "end_year": 1530,
     "weight": 3, "directed": true, "evidence": "explicit historical-network assumption"}]},
  "land_corridors": [{"from": "bordeaux", "to": "paris", "weight": 7,
                      "evidence": "static domestic road approximation"}]
}
```

`sources.amount` 是有限窗口内每次服务的入口项，限于小于 1 的输入，非把目标直接设为风尚；入口原料/宗教等资格在当前快照上验证。`initial` 是开局已有习俗，不入增长队列；`contacts` 要求上游当前 x 达到门槛，才把指定入口提高到小于 1 的弱接触。`coefficient_events` 和 `wake` 显式唤醒旧前沿，`renew_clock` 在续波前先物化旧有效值，再重开国家时钟，不会因为清 S 而跳涨。窗口外只走时钟尾巴，清队列也收费。

`parameters` 保存情景的共享参数默认值，CLI 的 `--set` 或网页表单显式覆盖它。`seeds: []` 被保留：茶与烟草不会在网页重算时被悄悄加上默认强种子。`constraints` 记录提前接触和阶段上限违反，`milestones[].aggregation="population"` 使用实际人口加权，缺数据时失败而不降级。

```powershell
& $env:EU5_PYTHON -m tools.obsession_sim.historical `
  --graph tmp/obsession_real/eu5_1337.json --budget 50000 --out tmp/obsession_real/first_batch.json
& $env:EU5_PYTHON -m tools.obsession_sim.study `
  --graph tmp/obsession_real/eu5_1337.json `
  --out docs/design/obsession/experiments/first_batch_transport_results.json `
  --html-dir tmp/obsession_real/first_batch --mc 30
```

冻结目标在 `history_targets.json`，共享参数、商品地理/通道与证据在 `historical.py`。`study` 比较预算前沿及移除组件的结果，再做 30 组启动±10年、初始强度±20%的输入敏感性；保存全部失败、维护超额和原目标哈希，不通过时拒绝发布成功。首批结果及证据边界见 [16 验证报告](../../docs/design/obsession/16_First_Batch_Transport_Results.md)。

输出中的 `商品.playback.json` 才是「载入回放文件」所需的结果；该入口也能提取 `商品.html` 内嵌的回放。`商品.scenario.json` 是「导入配置」使用的输入，导入时会一并恢复其参数和起年，然后重算。旧的 `商品.json` 保留为情景配置兼容路径。总研究结果 JSON 是统计报告，不含逐帧地图，不能当回放载入。

首批咖啡情景导入后应显示 `p=.004`、`T=600`、`κ=.75`。启动提示会识别也门的有限源输入（1450–1470，每次服务+0.5）；`p×x₀≤δ` 只说明弱种子单独不足，不能据此断定含源输入的整个情景无法启动。服务首页在刷新时读取当前前端模板；改动 Python 后端后仍需重新启动服务，以免继续使用旧模块。

这是城市代理的静态网络验收；区域人口、真实跨洋占有/出口、酒与咖啡联合约束、烟草禁令失败率、独立快照和引擎耗时仍未验收。`coefficient_cost=10` 的首批研究每次服务另计 `10+d`，不把原先遗漏的系数求值算作免费；旧预设默认 0，以保留既有逐值回归。
