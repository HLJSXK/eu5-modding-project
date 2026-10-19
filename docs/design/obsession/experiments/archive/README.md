# 已过期的实验（归档）

更新：2026-10-19。这里的脚本都能照常运行复现，但它们验证的架构或参数已经不是现行方案，**不能用来验收现行设计**。现行基准见上级 [README](../README.md) 与共享模拟核心 `tools/obsession_sim/`。

| 文件 | 当初验证什么 | 为什么过期 |
|---|---|---|
| `location_diffusion_budget.py` 及 `_results.json`、`_14_goods_results.json`、`_17_goods_results.json` | 旧推送模型：逐边 sent 缓存、累计压力、量化 signal，以及 128U/32U 固定配额下的积压 | 一变量约束删除了 sent/pressure/signal；成本口径与容量结论随之作废 |
| `window_capacity_study.py` 及 `_results.json` | 旧 E/I/D 多状态的总变差、QSS 精度/期限压缩、时间轮维护税 | 多状态与 QSS 已撤下；依赖 `location_diffusion_budget.py`，两者一起归档 |
| `single_state_diffusion.py` 及 `_results.json` | 单变量 + 原生 current/next 集合调度的模型断言 | 2026-10-19 采纳方案A（侵入式队列），由 `queue_pointer_scheduler.py` 和 `tools/obsession_sim` 取代；集合版与方案A的逐值等价已在 `relaxed_state_study.py` 中留档 |
| `computation_flow_scenarios.py` 及 `_results.json` | 集合版、δ=0 下的增长与全局退潮情景（精确浮点、定点、容差、ε、年度步长） | δ=0.1 已采纳、退潮改为国家级时钟；13 页面图表改用 `tools/obsession_sim` 生成的数据。其中“退潮尾巴占 71%”的结论仍可引用，但数值按集合版计价 |

运行方式不变，例如：

```powershell
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON docs/design/obsession/experiments/archive/single_state_diffusion.py
```
