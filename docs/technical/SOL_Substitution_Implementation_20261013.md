# SOL 替代组实现与验收记录

日期：2026-10-13。当前分支：`substitution`。原有工作区改动先提交为 `09ab11b1`（Complete SOL economy dashboard and GUI renderer updates）；替代组改动是此后的独立工作区改动。

实现依据为 [实施规格](SOL_Substitute_Groups_Global_Modifier_Implementation.md) 和 [审计报告](SOL_Substitute_Groups_Global_Modifier_Audit.md)。本次完成生成代码与离线验证，没有部署、启动游戏或测量游戏性能。

## 已实现的口径

- 使用算法 A，偏好 V=1。20 个组、56 种核心商品、67 条成员关系来自 `goods_weights.csv`，全部重叠成员保留。历史 N 单独存储于 `substitute_groups.json`；luxury_food 为 4，mounts 为 2，不用当前有效成员数覆盖。
- 严格价格权重为 >2.30→0.25、>1.70→0.5、>1.30→0.75、<0.40→2、<0.65→1.5、<0.85→1.25，其余 1。当前与中性篮子使用相同的有供应、校准需求量大于零、外部有效需求大于零的成员。
- 对商品 i 汇总各组当前和中性贡献，D=H_current/H_neutral；共同的成员数除法相消。国家 M 按人口×校准单位需求×默认价格加权。默认价格对同一种商品固定，因此等价于数量加权；不使用当前市场价格作聚合权重。
- epsilon=0，仅对正的可表示分母求比值；零基线返回 M=1，不抬高小额正分母。引擎定点舍入仍待实机检查。
- 先移除自身旧修正，读取 `modifier:global_<good>_pop_demand` 的外部 offset e；写入 size=(1+e)(M−1)。求解器的 `sol_good_effective_<good>` 缓存是同一实际非负因子，地点单位消费只乘一次，然后进入原有 raw/国家阶层 solver。校准 demand_add、收入目标和阶层 solver 保持原算法。

## 生成与生命周期

`sol_substitution.py` 是算法及生成源，`gen_sol_substitution.py` 生成基础版和独立版的 C_SOL_substitution、国家显示值、启用 trigger、56 个静态国家修正及中英文本地化。`gen_sol_chain.py` 将其放在市场常量和经济效果之间。市场缓存仍以 market scope 为 global map 的 key，新增每商品/人口类型单位支出和价格权重，不保存市场 persistent variable。

新游戏/读档/全刷新先建立市场明细，再成套计算国家商品倍率、地点原始支出、国家阶层系数和修正。人类和普通频率 AI 每月重算；低频 AI 每年重算，并每月重写缓存商品修正（两个月期限）。月度守卫检查地点数量、相同数量下的所有权交换、市场变化/消失、人类转 AI 和外部商品 offset，失效时重算完整 solver 快照。新市场缺缓存时初始化世界市场明细；市场价格和供应的正常变化沿用年度缓存周期。

CMF 新增默认开启的商品替代开关。关闭替代会移除专用修正和倍率/诊断缓存，然后按 M=1 重算仍启用的 SOL；仅保留外部需求记账和通用需求快照。关闭 SOL 总开关显式清理国家商品和地点修正；总开关关闭时替代开关不重新应用 SOL。空国家、无人口和失去最后地点的国家有月度及全刷新清理。独立版不依赖 CMF，替代始终开启。

## 兼容与界面

PP 以最终零 lumber 需求计算，victuals 因无已验证 global 接口保持中性且计入原有消费。M&T 使用最终校准数量和 M&T 默认价。JTG 的 26 个额外商品保持中性、无组且计入消费。各兼容生成器输出匹配的市场明细和地点支出 helper；PP/M&T 还覆盖国家聚合，以免错误使用基础数量。

通用商品提示列出全部静态组关系。地点商品图标提示显示地点 owner 的国家替代倍率与该地点市场的缓存价格权重；国家面板提示使用其 Player 上下文，没有虚构市场。国家面板增加刷新年份、参与商品数、最大绝对 modifier。无效的 bare-widget `sol_good_tooltip` override 已改为直接 tooltip 属性。UI/hover 目前只有源码与离线证据。

## 离线验证与复现

在 PowerShell 设置 `$env:EU5_PYTHON` 为 eu5 环境 python.exe，设置 `$env:PYTHONUTF8="1"`，然后运行：

```powershell
& $env:EU5_PYTHON scripts/gen_sol_chain.py
& $env:EU5_PYTHON scripts/gen_sol_chain.py --check
& $env:EU5_PYTHON scripts/test_sol_substitution.py
& $env:EU5_PYTHON scripts/validate.py --changed
npm --prefix substitution-lab test
git diff --check
```

本次结果：五目标生成一致性检查通过，Python 13/13、substitution-lab 13/13 测试通过，36 个变更 mod 文件校验无问题，`git diff --check` 通过。

Python 测试解析并执行生成的 EU5 effects，覆盖严格档位、重叠组中性、两市场加权、重复刷新、外部 offset、共享市场下不同国家的支出、倍率只应用一次、缺市场/缺供应、空国家、控制模式切换、相同数量的领地交换、关闭清理和 PP fallback。它使用 Python float，不模拟 EU5 定点、实际 modifier 更新时机或需求刷新。

GUI 预览：`ai_gui_assessment/renderer/run.py situation` 和 `tooltip`；地点提示为 484×1003，两个页面均无未知表达式。预览不证明 hover 行为或游戏数据正确；地点预览保留 vanilla ExtraTooltipInfo.GetUIAction 的模拟上下文提示。

## 实机验收清单

1. 在开启/关闭状态下加载新游戏和旧存档，检查 error.log，无新增未知 modifier、缺变量、GUI FetchData 或 tooltip 错误。
2. 用存在于目标 POP 消费列表中的商品，验证同一 effect 内 remove 后读取外部 modifier 的值；负 offset、零需求与重复刷新不得自我累积。
3. 等待实际人口需求更新，核对 commodity×global×local 因子与内部消费；分别检查保留原版需求的 slaves，不能声称国家修正可选择人口类型。
4. 比较中性价格与关闭替代，在相同外部修正下 raw、solver 和地点修正一致；检查定点舍入、小正基线、同档稳定性及高价抑制。
5. 检查低频 AI 月度修正不失效，并测试所有权/市场切换、市场消失、国家形成、最后地点丢失、总开关与替代开关。
6. 在 PP、M&T、JTG 的真实加载顺序下检查最终商品数量、价格和求解器记账，特别是 victuals 与 JTG 中性额外商品。
7. 用代表性大国存档记录年度完整计算和月度重写耗时，评估新增的地点×商品×人口类型成本。本次未提供实机性能数值，也不把 Python 测试时间当游戏性能。

算法 A 不承诺实际组预算守恒；国家单一商品因子会损失市场与 POP 精度。旧 Engel、宗教/文化偏好、开发度抵消、时代缩放和 scarcity 总量补偿均未恢复。
