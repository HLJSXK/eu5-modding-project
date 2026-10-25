# 替代开关对照后的性能跟进

日期：2026-10-15。本轮依据是用户反馈：替代启用时普通过月仍约为加入前十倍，关闭 CMF 商品替代后明显恢复。此前脚本操作下降不能代表过月性能已经修复。

三档已收到并分析：1337.5.15、6.15、7.15。已确认大范围反复 dirty 的主要根因是 guard 的 local-effect `min=0` 把基准1压成0；本轮已改为 value 算术块。详情与计数见 [三档根因及修复](SOL_Three_Save_Performance_Fix_20261015.md)。下文保留先前的回读修正和采样流程。

## 对照能证明什么

关闭替代仍执行低频 AI 的归属/市场快照检查、逐商品外部修正读取和新的支出缓存路径。它会跳过篮子计算、清除商品修正、改变 raw 支出及国家矩阵输入，并触发全刷新。因此可将瓶颈收窄到替代启用后的链路，不能单凭这项对照认定永久 modifier 是唯一根因。输入变化也可能增加已有近似求解器的采用次数。

最新已检查的 00:32 会话中，部署的 C_SOL、A_SOL、on_action 与工作区一致，未见替代 effect 解析或无效 country modifier 错误。启动期 tooltip 警告不能当成持续过月刷错；旧 2026-10-14 存档没有本轮计数，不能用于推断当前 dirty 频率。

## 本轮代码修正

- 用官方 `country_modifier_strength(<modifier key>)` 扣除实际自身修正，代替从 live 总值中扣缓存的请求 size。接口来源：`.eu5-base/reference_official_defines/docs/triggers.log:3517-3523`。
- `sol_sub_applied_*` 继续记录上次请求值；新增 `sol_sub_live_*` 保存引擎实际强度，二者不再混为一谈。内部支出按 `max(external + live, 0)` 记账。
- 真正的自身强度漂移与外部偏移分开处理：自身漂移触发重算并修复修正，稳定的请求值/实际值差异不反复 replace。
- 原始总值没变的 clean 快路不新增 strength getter。没有改变 AI 年度频率或移除替代功能；快照版本 2 会在旧存档/首轮加载时成套刷新一次，应跳过该月份做性能对照。
- 保存轻量诊断字段，首次 dirty 后清掉旧商品 payload，避免领土 dirty 误带上次 external 数值。

这是对不可靠回读假设的正确性修正，不是已经证明“十倍回归由此导致”。原始 aggregate getter 与强度 getter 若在实际引擎有不同精度/时序，仍须看本轮实机数据。

## 如何得到有意义的下一次结果

重新构建部署并重启，在开启替代、保持 AI 降频的同一存档中，跳过加载首月，记录两个相邻普通月末的未压缩 debug 存档；一月及主动全刷新分开测。无需额外调试开关。

```powershell
$env:EU5_PYTHON='C:/Users/Hades/anaconda3/envs/eu5/python.exe'
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON scripts/report_sol_substitution_perf.py <较早存档.eu5> <较晚存档.eu5> --output tmp/substitution_perf.json
```

脚本只 mmap 扫描国家记录，不解析整份人口/地点树。国家 id 匹配后给出刷新/dirty 增量及前 20 名，并按 AI、人类、未知控制快照分组，把新建、清理、计数重置单独列出。控制者以较晚存档的快照为准。当前 strategy 8 缓存占比不是当月 sweep 次数；人类本来月度重算，低频 AI 的正常年度脉冲也可能贡献增量，不能把所有刷新都叫异常。

| 国家诊断变量 | 含义 |
|---|---|
| `sol_sub_perf_refresh_count` | 本次启用周期内完整替代刷新累计次数，包括首次、主动全刷新及年度刷新 |
| `sol_sub_perf_dirty_count` | 月度快照判定 dirty 的累计次数 |
| `sol_sub_perf_dirty_reason` | 最后一次首次 dirty 原因，未 dirty 的月份保留历史原因 |
| `sol_sub_perf_dirty_good` | 受影响商品的 1 起始索引，按 `sol_substitution.CORE` 排序；结构原因置 0 |
| `sol_sub_perf_old_total/new_total` | 上次与当前原始商品 modifier 总值 |
| `sol_sub_perf_cached_own/actual_own` | 请求缓存与当前实际强度 |
| `sol_sub_perf_external_now` | 本次推导的非负外部基准，仅在成功计算后记录 |

原因：1 初始化/开关/控制，2 领土数/归属，3 市场变化，4 市场缓存缺失，5 自身商品修正缺失，6 外部商品修正变化，7 实际自身修正相对 live 快照漂移。停用/清理会重置计数，所以两份诊断存档之间保持替代开启。

若普通月大量低频 AI 的 `dirty_count` 与 `refresh_count` 一起增加，按原因定位反复重算；若多数不增长而耗时仍很高，应重点隔离引擎商品需求成本及已有求解器输入变化。计数没有诊断覆盖时，报告明确给出“无法判定”，不会把零当成已无重算。

## 离线验证

42 项替代规则、回读边界、缓存和存档报告测试通过，五个目标生成一致性检查通过。特定测试覆盖请求缓存失配、确认的实际值/请求值差异、真实 own 漂移修复、0.00001 外部变化、首次 dirty 及 payload 清理。存档读数测试覆盖 signed/zero fixed point、AI/人类/未知控制者和跨档重置。

`validate.py --changed --ai-report` 返回 pass=true、0 errors；9 条 warnings 是用户已暂存自动生成产物的通用提醒。这些产物通过生成链比对，本轮没有改动暂存区。随后已修复默认文本模式把提醒也计入 FAIL 的问题：两种模式使用同一错误/警告分类，提醒不阻断构建，真实错误仍返回 1。三项校验器回归测试和默认 `--changed` 检查通过。

最新操作计数在 [SOL_Substitution_Readback_Counts_20261015.json](SOL_Substitution_Readback_Counts_20261015.json)，与此前第一轮计数分开保存。clean guard 增加一个临时变量清理操作，没有增加 strength getter；native getter 与 modifier 引擎成本仍不是 CPU 秒数。
