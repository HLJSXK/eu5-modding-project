# 连续三档确认的月度重算根因与修复

日期：2026-10-15。用户提供同一 HUN 游戏的 `1337.5.15`、`1337.6.15`、`1337.7.15` 三份未压缩存档，位于 `data/saves/`。此前“关闭商品替代后明显恢复”的实机对照与本次存档共同说明：预期的低频 AI clean 路径实际被大范围误判绕过。

## 实测重算次数

| 两档区间 | 可比 AI 国家 | AI 完整替代刷新增量 | AI dirty 增量 | 玩家刷新/dirty |
|---|---:|---:|---:|---:|
| 1337.5.15 → 6.15 | 1,570 | 1,461 | 1,461 | 1 / 0 |
| 1337.6.15 → 7.15 | 1,577 | 1,494 | 1,415 | 1 / 0 |

第一段有 93.1% 的可比 AI 发生 dirty 刷新，第二段有 89.7%。第二段的 79 次额外非 dirty 刷新包含正常年度/其他完整刷新，不能都叫异常。唯一玩家为 HUN#381，其月度刷新符合设计。

原报告器已用独立的原文本逐国读取和 signed 5dp 解码交叉核对：所有国家记录边界与诊断字段零差异，没有把省份/人口数据混入国家记录。

仅统计区间中 `dirty_delta>0` 的 AI，其末次原因分布如下。这是每国最后事件的原因，不是完整事件日志；本次各国 dirty 增量均为 1，因此没有多次事件被末次原因覆盖的问题。

| 原因 | 5→6 月 | 6→7 月 |
|---|---:|---:|
| 外部商品修正变化（reason 6） | 1,335 | 1,278 |
| 市场变化 | 117 | 128 |
| 领土数量/归属 | 9 | 9 |

新刷新 AI 的末档 strategy 8 截面分别为 388/1461、389/1425；它显示许多重算国家采用了昂贵近似解，但不是 sweep 的实际调用总次数，也不能直接换算 CPU 秒数。完整交叉核对共 45,122 项诊断/控制字段，全部零差异。

详细结果：[SOL_Three_Save_Diagnostics_20261015.json](SOL_Three_Save_Diagnostics_20261015.json)。它记录旧版本实测，不能用作修复后的耗时或计数结果。

## 决定性错误：外部基准 1 被错误压为 0

三份存档分别有 1,450、1,433、1,428 个完整 reason 6 样本，共 4,311 个。全部满足：

```text
记录的新 aggregate total == 实际自身 modifier strength
正确外部基准 = max(1 + total - own, 0) = 1
实际记录的 sol_sub_perf_external_now = 0
```

例如 6 月的 DAN#4 amber：

| 保存字段 | 值 |
|---|---:|
| 旧 observed total | -0.13527 |
| guard 当前 total | -0.13511 |
| guard cached own / actual own | -0.13511 / -0.13511 |
| guard external_now | **0** |
| 国家 external 缓存 | **1** |

TUR#41 beeswax 的 total/own 同为 `0.26557`，却也记录 external 为 0。正负值都会触发，与负 modifier 不支持或普遍 size 丢失无关。7 月 34,731 个原生 SOL 商品修正全部与 applied/live 缓存一致，其中负值 18,352 个、正值 16,379 个；市场人口临时 map 也没有残留。

旧 guard 使用：

```text
set_local_variable = { name = sol_sub_check_external value = { value = 1 add = modifier:global_amber_pop_demand } }
change_local_variable = { name = sol_sub_check_external subtract = local_var:sol_sub_check_actual_own }
change_local_variable = { name = sol_sub_check_external min = 0 }
```

这里的 local effect `min=0` 在实机把正基准压成 0；不能套用 value 算术块的“min 是下限”规则。离线 fixture 曾错误地将该 effect 模拟为 `max(value, 0)`，因此之前的 clean AI 检查漏报了这一错误。

另一个真实行为是 aggregate modifier 回读可能晚于自身 modifier 更新：DAN 6 月最后的 native/live/applied 已为 `-0.13541`，observed aggregate 仍为 `-0.13511`。这会让下一月进入回读检查，本来应只更新 observed；错误的 1→0 钳制却把它升级为 external dirty，重新计算替代组、所有地点和原国家求解器，再更新自身修正，从而持续循环。

## 修复

guard 现在用单个已验证的 value 算术块：

```text
set_local_variable = {
    name = sol_sub_check_external
    value = {
        value = 1
        add = modifier:global_amber_pop_demand
        subtract = local_var:sol_sub_check_actual_own
        min = 0
    }
}
```

该下限写法与现有国家刷新路径、原版 `country_effects.txt:1660-1665` 一致；新存档中刷新路径确实得到 external=1。没有改替代组、价格阈值或年度频率，真实外部变化、归属/市场变化与自身修正缺失仍能触发同步。

生成源 `scripts/sol_substitution.py` 已修复，stable、standalone、PP、M&T 运行产物已重新生成；JTG 继承修正后的基础国级效果。离线 fixture 对 local effect 的模型单独纠正，没有猜测性地反转 persistent `change_variable` 的 min/max，也未改变 value 算术块的上下限规则。

## 定点回算与剩余边界

以 5dp 整数重新计算全部 reason 6 样本，旧 `min(E,0)` 与 4,311 个记录全部吻合；修正的下限与 4,308 个最终 external 缓存吻合。7 月 AZF、HBN、NRK 的最后缓存分别偏离 1 至多 `0.00013`，三国均发生当月 dirty+额外完整刷新：第二次刷新读取旧 aggregate 与新 own，造成小额基准污染。

这三个最后缓存不是本轮主要错误的反例：它们的 guard 样本同样错误地把应为 1 的值压为 0。额外刷新后的回读一致性仍是独立边界，可能保留少量纠正性重算；本次没有用 epsilon 掩盖小额外部变化，也没有据此改 AI 年度经济响应规则。

## 验证及性能结论

- 49 项替代、回读、缓存、报告器和校验器测试通过；新增案例用 DAN/TUR/NOR 实际保存小数作 exact decimal guard 回放，并覆盖正/负自身修正、外部正/负/零基准、旧 clamp 故障复现和真实 0.00001 外部变化。
- 五个目标 `gen_sol_chain.py --check` 通过；`validate.py --changed` 返回 0、无错误，保留生成产物暂存提醒；`git diff --check` 通过。
- 对三档的操作次数和变量解码复核都是旧版本实测；Decimal guard 测试不是完整引擎固定点、执行时序或 C++ profiler。

本次修复针对已确认的大规模 false dirty，能够解释为何年度降频事实上退回了全世界月度求解。修复后的真实过月耗时仍需重新构建部署并重启验证；不能把这些旧档的计数当成新版本结果，也不能承诺精确的速度倍数。
