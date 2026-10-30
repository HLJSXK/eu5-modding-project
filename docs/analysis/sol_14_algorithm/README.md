# SOL 1.4 算法与过月成本图解

> **调度已更新（2026-10-15）：** 当前默认是玩家月度、AI年度，AI月度snapshot轮询已删除，只保留首次初始化及地点缺系数的中性兜底。以下六图和计数保留为5bc51c51旧实现快照，不能当作修改后的月度路径；详见[当前调度说明](../../technical/SOL_AI_Annual_Cadence_20261015.md)。

审阅日期：2026-10-15。源码基线：`substitution` 分支 `5bc51c5173134240aab464cf0ebc1c9d27f4049d`。

**从 [交互图册 index.html](index.html) 开始。** 双击即可离线打开；图中的输入只改变复杂度示意，不修改游戏配置。

**存档实数补充：[HUN存档的替代OFF月度增量估算](HUN_save_off_estimate.md)**，使用1337年5/6/7月三档的实际国家、地点和市场数据。

本图册解释当前完整 SOL（`src/stable`）的实际调用链：市场缓存 → 国家商品替代 → 地点 raw 系数 → 四阶层国家求解器 → modifier → UI。这里的 `stable` 是当前分支的目录名，不代表历史 1.3 发布版。

## 阅读顺序

1. 每月究竟运行什么：人类、降频 AI、年度与加载刷新。
2. 商品替代 Algorithm A：价格分段、有效成员、跨组响应、国家聚合。
3. 三层缓存：市场明细、国家倍率、带 owner 的市场总支出。
4. 地点与国家闭合：raw → 分类 → 4×4 精确解 → 209 种顶点候选。
5. 旧故障如何放大成本：false dirty 会连带重跑整条国家求解链。
6. 复杂度与离线计数：区分脚本操作数量、引擎成本和真实秒数。

## 先记住的结论

- 当前替代响应按“国家涉及的市场 × 七类人口”计算，已经不再逐地点展开同一个篮子；20 组、56 核心商品、67 个成员关系是固定规模。
- 降频 AI 仍每月扫描地点快照与商品修正，并重写有效期为一个月的地点 modifier。只有 clean 时才省掉完整求解。
- `num_locations < 5` 的早退位于替代刷新之后，只跳过国家矩阵求解，不跳过替代组。
- 209 是固定四维求解器的候选组合数；相对于地点规模是常数，但在脚本解释器中常数可能很大。
- 已有三份存档证明旧版本 false dirty 导致大量 AI 月度重算。当前源码已修复该 clamp；修复后真实秒数仍需要实机测量。

这次只生成解释性文档与图，不修改游戏算法，不部署模组。

## 六张独立矢量图

| 图 | 内容 |
| --- | --- |
| [01 月度调度](01_monthly_dispatch.svg) | 世界缓存、人类月度、AI 年度/dirty、每月地点写入与 UI |
| [02 替代算法](02_substitution_algorithm.svg) | Algorithm A、价格档位和加权公式 |
| [03 缓存层级](03_cache_hierarchy.svg) | 从 N 份篮子变为 M 份、owner 隔离、空间复杂度 |
| [04 国家求解](04_country_solver.svg) | raw α、分类、精确解、209 候选、回退 |
| [05 失效放大](05_dirty_amplification.svg) | 当前 guard 与已修复的历史错误反馈环 |
| [06 操作计数](06_operation_counts.svg) | 本次复跑的离线操作计数，不是实机耗时 |

SVG 可用浏览器直接打开和缩放；HTML 不依赖 CDN、网络、Mermaid 或本地服务。小屏幕可横向滚动图，或单独打开 SVG。

## 符号与循环单位

| 符号 | 含义 / 当前值 |
| --- | --- |
| N、M | 某国地点数、该国所涉市场数；不是全世界市场数 |
| C、W、L | 世界国家数、市场数、总地点数 |
| P | 7 种人口：nobles/clergy/burghers/laborers/peasants/soldiers/tribesmen |
| G、H | 56 核心商品；67 商品–组成员关系，分布在 20 组 |
| Q、R | 215 正消费商品×人口条目；271 有消费的组成员×人口条目 |
| K、V | 4 个求解阶层/地点类别；209 种候选组合 |
| S(N) | 引擎原生 ordered_owned_location 的排序成本 |

代码使用 num_pop_type 聚合 getter，没有显式逐人口实体枚举。人口总量增长不直接增加这些循环次数；原生 getter 内部成本未测。P=7 的消费篮子先合并为五个财务阶层（平民合并 laborers/peasants/soldiers），求解器再把平民与 tribesmen 合并成 lower，得到 K=4。

## 公式细节

### 商品替代

外部基准 E[c,g] = max(1 + aggregate[c,g] − actual_own[c,g], 0)。actual_own 来自实际 modifier 强度，不是请求 size 缓存。有效成员满足：有供给、该人口消费常量 q>0、E>0。

对市场 m、人口 p、组 s，有效集合 A、历史组规模 h：

~~~text
C[g] += h[s] × w[m,g] / Σ(j∈A) w[m,j]
Z[g] += h[s] / |A|
D[m,p,g] = C[g] / Z[g]          （Z=0 时默认为 1）
b[c,m,p,g] = n[c,m,p] × q[p,g] × default_price[g]
M[c,g] = Σ(m,p) b×D / Σ(m,p) b  （无基准时为 1）
requested_size[c,g] = E[c,g] × (M[c,g] − 1)
effective[c,g] = max(E[c,g] + 写入后实际 own[c,g], 0)
~~~

只有有效、存在中性贡献的条目进入实际聚合；无贡献条目不凭空增加分母。重叠商品先汇总各组贡献再取比；历史组规模不等于当前有效个数。M 按默认价加权（同商品默认价可约掉），不使用当前市价，也不乘 α。Algorithm A 不保证数量或预算守恒。

价格档位：r<.40→2；[.40,.65)→1.5；[.65,.85)→1.25；[.85,1.30]→1；(1.30,1.70]→.75；(1.70,2.30]→.5；r>2.30→.25。支出有效价 min(市场价,默认价) 与价格档位是不同计算。

### 地点与国家闭合

~~~text
a = min(0.25 × (全国五阶层财富 / 目标财富 − 1), 0.5)
    目标财富 ≤ 0 时 a=0
I[l] = Σ(e=五阶层) max(收入[l,e] − 缓存建筑维护[l,e], 0)
F[l] = I[l] × max(1+a, 0)
B[l] = Σ(p=7种人口) 人口[l,p] × u[c,m,p]
α[l] = max(F[l]/B[l], 0)       （B=0 时 α=1；α 无上限）
A[s,k] = Σ(l∈第k类) α[l] × B[l,s]
t[s] = Σ(l) F[l,s]
A f = t
β[l] = α[l] × f[class(l)]
local_modifier_size[l] = β[l] − 1
~~~

用 A 表示国家矩阵，避免与商品倍率 M 混淆。精确路径当前也解绝对目标 Af=t；部分历史注释中的 delta 形式不适用于当前执行代码。国家闭合调整后不再保证每个地点自身 F=B×β；它尝试四阶层全国收支闭合。

分类分数为 clip((地点阶层份额−国家份额)/max(国家份额,0.02),−3,3)；confidence=最高分−次高分。排序后以 score−0.05×该类已分配raw支出/目标容量 选类；平手按贵族、教士、市民、下层顺序。每类容量先给总 raw 支出1%，余96%按 raw 超支压力分配。

精确解要求行归一化后 pivot>0.0001、所有 f≥0、逐行残差 |Af−t|≤0.001t+0.01。精确失败/关闭、近似开启、非空类别存在、至少一个 raw 行残差>0.00001 时才执行 sweep。候选消元 pivot 阈值为0.00001。

209=Σ(k=0..4) C(4,k)²k!=1+16+72+96+24，包含行排列的重复尝试，不是209个必定有效的不同最优点。每候选至多四维消元，计算四行相对残差；目标绝对值≤0.00001的行对相对误差贡献记0。候选 L1均值和 L∞最大值均不得超过 raw。主比较为L1，1% tie带内比较L∞。这描述有限候选搜索，不声称附加 no-worsen 约束下已证明全局最优。

## 时间、空间与触发频率

以脚本操作为单位，暂将 getter/map 单次访问计常量；原生实现不公开，不能据此推秒数。

| 环节 | 一次调用复杂度 |
| --- | --- |
| 世界价格/供给/支出缓存 | O(W·(G+Q)) |
| 降频 AI 月度 guard | O(N+G)，clean 也扫描 |
| 替代刷新 | O(G+N·P+M·(G+Q+R)) |
| 国家市场支出与地点 raw | O(M·Q+N·P)，正常按国家连续访问 |
| 分类/矩阵/排序 | 保守上界 O(N·K²)+S(N)，固定 K 后 O(N)+S(N) |
| 精确解 / sweep | O(K³) / O(V·K³)；K=4、V=209固定 |
| 地点 modifier 应用 | O(N) 写入，每月都做 |
| 年度建筑维护缓存 | O(N+B_buildings)，按建筑实体枚举 |

旧替代约 O(N·P·(G+H))，现在昂贵篮子从 N 份变 M 份。固定 G/P/H/K 时均可称近线性，但脚本常数、读写数量不同。常规比较排序可估 S(N)=O(N log N)，不是引擎算法或计时证明。

世界缓存空间 O(W·(G+Q+P))、国家商品变量 O(C·G)、地点缓存 O(L)、临时人口 O(M·P)、求解工作区 O(K²)。市场总支出是 market key + owner，并非永久二维缓存；A→B→A 访问共享市场会重建，但不误用别国结果。

~~~text
T_month ≈ 世界刷新（若触发）
        + Σ降频AI guard
        + Σ活跃国家月度地点modifier应用
        + Σ本月每次完整solve [替代 + raw + 分类/求解分支]
        + 年度/全刷新附加工作 + UI绘制 + 引擎需求内部成本
~~~

没有原生 profiler 时，末几项不能假定为0。完整 solve 与 apply 在图里作为整条调用链一起画，公式中分开计费以免重复。

HTML 模型假设 C 个同规模 AI、周年均匀、每国每月最多一次刷新，非周年国家 dirty 比例 d。平均完整刷新数=C/12+d×11C/12，相对全clean倍数=1+11d。实际周年和dirty可能同月多次刷新；旧存档所有可比国家的dirty占比不能直接代入这个条件概率。滑块90%仅为示例。

## dirty 与历史证据

当前七类原因：初始化/开关/控制改变；地点数/归属；市场变化；市场缓存缺失；自身modifier缺失；真实外部基准变化；实际自身强度漂移。人口/收入/价格正常变化本身不直接dirty，经济响应仍遵循月/年/full cadence。

先比同来源原始total；未变不读strength。total变化才扣actual own。若只是自身修改延迟回读且E/live未变，只更新observed并保持clean。首次dirty后跳过后续有效检查，不能假设引擎枚举即时停止。

旧两个区间有1461/1570（93.1%）、1415/1577（89.7%）可比AI dirty。**包含市场/领土等真实变化，不能把全部dirty都称为误报。** 末次原因是外部变化的分别1335和1278；三档共4311个reason6样本均total=own，却记录external_now=0，正确值为1。当前已将旧local-effect min=0替换为value算术块下限。

第二区间刷新1494比dirty1415多79，含年度/其他刷新；不能全算异常。末档strategy8比例不等于当月sweep次数。修复后耗时待实机；aggregate延迟带来的少量外部缓存偏差仍是原报告记录的独立边界。

## 版本与复现

- f9bee41d：metadata支持游戏1.3.11，已有小国门槛、AI年度和209候选。
- 09ab11b1：替代引入前；其B_SOL solver文件与当前无差异。
- dfd3055f：引入替代runtime。
- 70561daf：计数旧基线，也是早期1.4，不能标作1.3。
- 5bc51c51：图册当前审阅版本，已含clamp修复。

本次 [operation_counts.json](operation_counts.json) 于2026-10-15用现有脚本重跑。180地点/3市场/非中性：变量操作571300→12194；商品条目38700→645，另有1260总数和177owner读取；clean条件3067→3684。1地点/1市场中性场景变量3855→4163。当前unchanged refresh商品add/remove均0；isolated unchanged_apply不属于clean月实际调用链。

~~~powershell
$env:EU5_PYTHON='C:/Users/Hades/anaconda3/envs/eu5/python.exe'
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON scripts/measure_sol_substitution_performance.py --output docs/analysis/sol_14_algorithm/operation_counts.json
& $env:EU5_PYTHON docs/analysis/sol_14_algorithm/render_atlas.py
~~~

旧name=字段仅在fixture中规范化以计旧设计请求，不证明引擎曾成功执行。Python float不模拟完整引擎定点过程。数据排除世界缓存、国家矩阵/sweep、地点modifier与C++需求刷新，不能用操作下降比例宣称过月加速。

实机排查顺序：同档同配置重启，跳过加载首月，普通月、一月和主动全刷分开；对相邻未压缩存档运行现有 scripts/report_sol_substitution_perf.py，先查dirty/refresh增量。若clean但仍慢，再隔离近似开关、UI开闭与引擎需求成本。替代OFF仍保留通用guard和支出cache，并非完全恢复1.3。

## 源码索引（5bc51c51）

| 内容 | 文件与行号 |
| --- | --- |
| 月度/年度/加载 | [SOL_economy_on_actions.txt](../../../src/stable/in_game/common/on_action/SOL_economy_on_actions.txt) :8–99、160–167 |
| 一月缓存/人类面板 | [SOL_economy_situation.txt](../../../src/stable/in_game/common/situations/SOL_economy_situation.txt) :15–36 |
| 常量、档位、Algorithm A | [sol_substitution.py](../../../scripts/sol_substitution.py) :18–67、200–303 |
| 人口聚合与组计算 | 同上 :209–275 |
| owner支出cache | 同上 :90–125、313–314 |
| modifier生命周期与guard | 同上 :316–381 |
| 世界市场缓存 | [gen_market_unit_consumption.py](../../../scripts/gen_market_unit_consumption.py) :145–215 |
| 储蓄压力/raw | [sol_economy_effects_source.py](../../../scripts/sol_economy_effects_source.py) :949–955、1010–1077 |
| 替代先于小国门槛 | 同上 :1564–1605 |
| 分类、排序、求解调用 | 同上 :1845–1958 |
| 地点应用/面板/全刷新 | 同上 :1966–2002、3522–3534 |
| exact目标与验证 | [B_SOL_country_demand_solver.txt](../../../src/stable/in_game/common/scripted_effects/B_SOL_country_demand_solver.txt) :116–194 |
| 近似门槛 | 同上 :282–343、528–575 |
| 209枚举与接受 | [sol_vertex_selector_source.py](../../../scripts/sol_vertex_selector_source.py) :51–185 |
| 计数器与排除范围 | [measure_sol_substitution_performance.py](../../../scripts/measure_sol_substitution_performance.py) :1–116 |
| 旧三档根因 | [SOL_Three_Save_Performance_Fix_20261015.md](../../technical/SOL_Three_Save_Performance_Fix_20261015.md) :7–101 |

UI说明限于调用/缓存边界，未推断GUI秒数。以当前src/stable为主：standalone沿用核心；PP/M&T有数量/覆盖差异，JTG额外商品保持中性并增加Q。

已按CLAUDE要求读PROJECT_OVERVIEW；仅新增docs文档和图，不触发overview/BRIEF更新。

## 本次验证

### 补充：替代 OFF 相对游戏 1.3 仍多出的工作

对照 f9bee41d（游戏支持版本1.3.11）与当前5bc51c51，假设SOL主开关开启、AI降频开启、替代关闭且已完成切换同步。

| 频率 | 1.3 | 当前替代OFF |
| --- | --- | --- |
| 普通月、clean降频AI | 续写地点modifier | 先扫描地点归属/市场和56商品修正，再续写 |
| 普通月、AI发生dirty | 没有这条snapshot即时失效入口 | 仍可触发完整raw/分类/国家求解，哪怕替代关闭 |
| 每次完整solve（人类每月、AI年度/dirty） | 直接原SOL计算 | 先走替代框架：市场检查、56商品变量初始化、计算中性输出、apply的OFF分支、清理、重建外部因子与快照 |
| 每次solve的单位支出 | 每地点读7个世界市场总数 | 每国家市场先读215明细并乘外部因子，后续地点读7个总数，另做owner校验 |
| 一月/加载/缺失世界缓存 | 原价格/供给/总价 | 仍额外算价格档位、保存逐商品人口支出明细，无替代开关门控 |

**OFF清理不是只在切换开关时发生一次。** sol_refresh_country_substitution 每次先设 initialized=1，再进入OFF的 sol_clear_country_substitution，随后又重建通用快照。该路径每次完整求解都会执行；仍clean的降频AI普通月不进入这里。每次包含两次地点遍历（清快照、再保存），以及三次所涉市场遍历（检查、清总价、失效owner）。

本次新增 [OFF路径离线计数](off_path_counts.json)，180地点/3市场/七种人口/全部供给/无外部修正，世界缓存已备好：

- OFF且clean的guard：3644条件节点、56总修正读取、3变量操作；1.3无这段guard。
- 每次OFF刷新框架：2461变量操作、724条件节点、168总修正读取、27 map操作；未加/删实际商品modifier，篮子核心没有执行。第一次OFF和后续OFF刷新相同。
- 地点支出当前3546变量操作，旧路径2520；当前读645商品明细+1260总数+177owner，旧路径只读1260市场总数。当前条件2882，旧3780，说明不能将所有原语都当同价，也不能仅凭某一种计数换算耗时。

旧支出块从f9bee41d的实际sol_compute_location_pop_demand中截到收入计算之前，只比较原单位支出读取部分；使用相同预置地图/人口，旧记录中的other即7类市场总价。不是完整1.3引擎回放。

没有新增：4×4/209候选算法本体、地点一个月modifier续写、situation月度/一月调度。上述on_action及situation的git对照已确认；solver文件相对基线无差异。UI新增五阶层×资金/基准10个聚合项和camels字段，随面板聚合发生（人类一月/缺缓存/全刷新），不能算全球每国每月新增求解。GUI绘制及游戏1.4引擎自身开销未计时。

- Chrome 本地 file 模式加载六张 SVG 全部成功；桌面1440px、手机390px页面无整体横向溢出，窄屏图与导航有各自滚动容器。
- 六张图共278个文字节点的浏览器边界检查未发现出框，已查看实际渲染图。
- 默认示例：篮子1260→21，平均刷新130国；90%示例1417国；N=1时市场限制为1，国家sweep候选为0。
- SVG XML解析与HTML/README本地链接检查通过；当前替代性能回归16项通过（离线正确性测试，不是EU5计时）。
- 既有游戏脚本未改动，本次无需重新生成或部署模组。
