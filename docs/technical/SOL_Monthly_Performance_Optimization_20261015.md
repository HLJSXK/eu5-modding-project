# SOL 1.4 月度性能优化

日期：2026-10-15。基线：`70561daf`；此前审计保留在 [SOL_Monthly_Performance_Audit_20261014.md](SOL_Monthly_Performance_Audit_20261014.md)。本次修改生成源并更新 stable、standalone、PP、M&T、JTG 的运行脚本，没有部署到游戏安装目录。

后续实机反馈：第一轮优化后仍有约十倍回归，关闭商品替代后明显恢复。本文件的操作表保留为第一轮历史测量，不代表问题已解决；当前实际强度回读修正与诊断流程见 [后续跟进](SOL_Substitution_Performance_Followup_20261015.md)。

## 独立判断

“国家层面替代应当成本较低”在算法上成立，但原实现的实际计算单位是地点：同一国家、同一市场、同一阶层重复计算相同的组响应，随后每地点又读取 215 个商品×阶层支出条目。结果保存在国家上，并不意味着运算只做一次。

默认 clean 低频 AI 没有每月全量展开替代组，因此不能把全球 AI 每月计算所有篮子作为归因。人类每月、正常频率 AI、年度 AI、dirty AI 会进入完整刷新；clean AI 另付月度快照检查和重复商品修正请求。原来的 209-case 国家求解器并非本次新增，本次未修改其算法或频率。

旧审计关于修正字段的结论可以进一步收紧：本机 `error.5.log:2575-2630` 逐项明确报告 `Failed to read 'name' for 'add_country_modifier'`，随后出现空数据库对象和 PostValidate 失败。当前原版 `country_effects.txt:846-850` 使用 `modifier=`、`days=-1`。本次修正该字段；成功加载及实际需求变化仍须新游戏会话确认，不能用离线 fixture 代替。

## 实现

1. 每国按市场汇总七类拥有的人口，再按市场×阶层计算组响应与国家加权。保留全部 20 组、56 商品、67 成员关系、价格分段、供给过滤、正数量/外部需求过滤和历史组规模。
2. 用市场 key 的七个 `global_variable_map` 暂存人口，消费后移除。这避免用 `local_var` 假装每市场独立存储：官方将其列为 Global Link，原版 `transfer_pop` 跨作用域读取同一 local。原离线 fixture 已修正为共享脚本上下文。
3. 每市场计算一次七类最终支出，写入 `sol_country_market_spending_*`；owner map 保存国家 scope，避免共用市场的国家混用系数。地点仅读七个总价。国家替代刷新与世界价格/供给刷新均失效 owner；无市场/无 owner 时地点总价归零。
4. 国家商品修正使用 `modifier=`、永久时长；只在缺失或实际 size 改变时写入。读取外部偏移时扣除当前存在的 SOL 修正的 applied size，不再先删除。保留旧 size 回退以处理迁移。
5. 去掉地点 modifier 应用步骤里的第二次国家 apply。每月的一月期限地点 modifier 仍重写；永久商品修正由国家刷新管理，不靠每月续期。
6. 快照保存实际 getter 的原始商品 modifier 总值。clean 月份直接比较同来源原始值，不反复做逆向减法；变化时按原公式检查外部基准，不使用 epsilon 忽略小变化。首次 dirty 后跳过后续有效检查；缺修正、开关变化、旧快照、等数量领土替换和市场迁移仍触发刷新。
7. 无 SOL 状态的空/停用国家跳过重复清理；首次清理仍移除国家修正、缓存与地点快照。

## 可复现操作计数

执行：

```powershell
$env:EU5_PYTHON='C:/Users/Hades/anaconda3/envs/eu5/python.exe'
$env:PYTHONUTF8='1'
& $env:EU5_PYTHON scripts/measure_sol_substitution_performance.py
```

完整结果：[SOL_Monthly_Performance_Optimization_Counts_20261015.json](SOL_Monthly_Performance_Optimization_Counts_20261015.json)。Fixture：AI、全商品供应、七种人口、默认数量；中性价格的 180 地点 / 3 市场：

| 操作 | 修改前 | 修改后 |
|---|---:|---:|
| 替代 refresh 变量操作 | 571,285 | 12,023 |
| 替代 refresh 条件节点执行 | 234,997 | 5,067 |
| 替代 refresh map 值读取 | 20,160 | 1,617 |
| 全部地点支出变量操作 | 60,300 | 3,546 |
| 全部地点支出商品条目读取 | 38,700 | 645 |
| 全部地点支出总价读取 | 0 | 1,260 |
| 全部地点支出 owner 读取 | 0 | 177 |
| clean 快照变量操作 | 114 | 2 |
| clean 快照条件节点执行 | 3,047 | 3,639 |

refresh 变量操作减少约 97.9%，另增加 2,586 次人口 map remove/add；地点支出总 map 读取为 2,082，减少约 94.6%，包含首次市场计算及 owner 校验。单地点、单市场首次计算没有复用空间，refresh 变量操作由 3,855 增到 4,048，不能声称所有国家所有路径都等比例变快。

clean 快照用更多条件换掉外部反向算术，并未消除领土扫描。低频 AI 既有地点 modifier 月度写入仍存在。计数脚本的独立 apply 项为了比较还会调用当前 helper，但实际月度调用链已不再调用它。

非中性价格案例产生 20 个非零修正。旧 helper 每次 unchanged apply 发起 20 个 add 请求、unchanged refresh 发起 20 remove + 20 add；新 helper 和 unchanged refresh 均为 0 add / 0 remove。旧字段在实际引擎无法解析，计数脚本仅把它规范化为当前字段来测原设计的操作次数，不把这些请求当作实际成功写入。

## 验证与限制

- `test_sol_substitution.py`：14 项，既有替代规则、快照、清理和包装覆盖；fixture 使用共享 local 上下文及当前 modifier schema。
- `test_sol_spending_cache.py`：8 项，180 地点/3 市场、跨国家 A→B→A、国家/世界市场刷新与清理、缺 scope/map/key、PP 零 lumber + 中性 victuals、JTG/M&T 最终数量；世界刷新测试执行真实生成器的缓存失效前缀。
- `test_sol_substitution_performance.py`：6 项，多市场/不同阶层人口与独立 oracle 等价，24 个 clean 月份无修正写入、重复 solve 不重写、0.00001 外部变化、缺修正、开关与旧快照迁移、空国家清理。
- `gen_sol_chain.py --check`：五个目标完整生成链一致性检查通过；`validate.py --changed`：7 个修改的运行脚本通过，`git diff --check` 和 Python 编译检查通过。
- 现有替代 UI 回归另有 8 项通过。完整生成检查还暴露消息数据库生成器遗漏现有 UTF-8 BOM 的误报，本次补上 BOM，并允许 Git 的 CRLF 检出；消息数据库内容没有变化。

这些是实际执行脚本节点的计数，并非 EU5 秒数。未计入原国家矩阵/vertex sweep、引擎需求缓存刷新或每月地点修正写入，不能据此声称总过月时间降低 97.9%。

人口汇总改变乘法与求和顺序；独立 oracle 证明数学规则等价，但离线 fixture 用 Python float，不模拟 EU5 中间固定点舍入。商品修正现在会首次正确进入引擎，还须确认回读时序、需求刷新、奴隶影响和稳定性。

实机验收采用同一存档、速度、模组列表和配置，重新启动游戏并跳过加载首月，记录至少三个普通月，一月单独记录；SOL 面板先关闭再打开。确认 56 项字段错误消失、非零商品修正入库、clean AI 保持年度求解，以及开启/关闭替代后需求响应与清理正常。若仍慢，下一步应获取 dirty 国家数与引擎级耗时，避免仅凭静态脚本大小继续归因。
