# SOL 替代组实现与验收记录

日期：2026-10-13。当前分支：`substitution`。近期 GUI 大改为 `09ab11b1`（Complete SOL economy dashboard and GUI renderer updates）；本轮先将已有替代组实现与初步界面接入提交为 `dfd3055f`（Implement country goods substitution and initial GUI integration），再完成以下 GUI 衔接。

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

基础版、独立版、PP、JTG 共用 `sol_goods_ui.py` 的完整商品块；M&T 继承基础商品界面。每个标签组按 CSV 完整显示成员，保留全部 67 条关系；跨组重复图标不重复计费。兼容额外商品在尾部无组行显示且倍率保持中性。

有供应与无供应图标的 `visible` 互斥，修复半透明副本叠在不透明图标上无法变暗的问题。核心商品有绿色 + / 红色 - 角标，表示消费国家的替代倍率高于/低于 1；无缓存供应时不显示角标。`sol_market_consumes_*` 实际记录供应，图例不把它写成短缺或需求。

地点图标悬停显示地点 owner 的国家替代倍率、替代状态、全部所属组和当地市场缓存价格权重；权重缺失显示待刷新，不伪造 1.00。国家图标使用 Player 上下文，无市场权重。通用商品提示仍列静态组关系。国家商品区用一行摘要显示刷新年份、参与商品数、最大绝对 modifier，配一行图例；关闭与等待快照时显示对应状态。最大修正计入外部需求 offset，与替代倍率不同；市场权重正常按年或完整重算刷新。状态为 guarded script value，没有新增持久化标志。

无效的 bare-widget `sol_good_tooltip` override 已改为直接 tooltip 属性。UI/hover 目前只有源码与离线证据。

## 离线验证与复现

在 PowerShell 设置 `$env:EU5_PYTHON` 为 eu5 环境 python.exe，设置 `$env:PYTHONUTF8="1"`，然后运行：

```powershell
& $env:EU5_PYTHON scripts/gen_sol_chain.py
& $env:EU5_PYTHON scripts/gen_sol_chain.py --check
& $env:EU5_PYTHON scripts/test_sol_substitution.py
$env:SOL_UI_PREVIEW_OUT='ai_gui_assessment/images/substitution_integration'
& $env:EU5_PYTHON scripts/test_sol_substitution_ui.py
& $env:EU5_PYTHON scripts/validate.py --changed
npm --prefix substitution-lab test
git diff --check
```

初始替代组验收记录：Python 13/13、substitution-lab 13/13 通过，36 个变更 mod 文件校验无问题。本次 GUI 衔接：五目标生成一致性检查通过，Python 核心测试 14/14、GUI 测试 5/5 通过，变更 mod 文件校验与 `git diff --check` 通过。substitution-lab 未修改，本次没有重复运行其历史测试。

Python 核心测试解析并执行生成的 EU5 effects，覆盖严格档位、重叠组中性、两市场加权、重复刷新、外部 offset、共享市场下不同国家的支出、倍率只应用一次、缺市场/缺供应、空国家、控制模式切换、相同数量的领地交换、关闭清理、PP fallback，以及关闭/待刷新/已启用/清理后的显示值。它使用 Python float，不模拟 EU5 定点、实际 modifier 更新时机或需求刷新。

新增 GUI 测试读取实际出货模板及已安装游戏的纹理/字体，在中英文下检查成员关系、悬停内容、缺缓存文案、状态摘要、图标变暗像素和布局边界。完整提示框在 100% 比例下：基础版/独立版 484×1003、PP 484×1028、JTG 484×1078，均无未知表达式或横向溢出。预览位于 `ai_gui_assessment/images/substitution_integration/`；测试保存的双语 PNG 不加外边距，CLI 的 `r3_location_sol_tooltip.png` 带 20px 外边距。

Renderer CLI `situation` 和 `tooltip` 均无未知表达式；`goods_tooltip wine` 的内容框为 442×372，仍有 10 个已知原版 StringPairList/mapmode 等 mock 缺口，没有新增 SOL 表达式问题。地点预览保留 vanilla ExtraTooltipInfo.GetUIAction 的模拟上下文提示。所有数值为 mock；本轮没有启动游戏，预览不证明实机悬停或需求更新。

## 实机验收清单

1. 在开启/关闭状态下加载新游戏和旧存档，检查 error.log，无新增未知 modifier、缺变量、GUI FetchData 或 tooltip 错误。
2. 用存在于目标 POP 消费列表中的商品，验证同一 effect 内 remove 后读取外部 modifier 的值；负 offset、零需求与重复刷新不得自我累积。
3. 等待实际人口需求更新，核对 commodity×global×local 因子与内部消费；分别检查保留原版需求的 slaves，不能声称国家修正可选择人口类型。
4. 比较中性价格与关闭替代，在相同外部修正下 raw、solver 和地点修正一致；检查定点舍入、小正基线、同档稳定性及高价抑制。
5. 检查低频 AI 月度修正不失效，并测试所有权/市场切换、市场消失、国家形成、最后地点丢失、总开关与替代开关。
6. 在 PP、M&T、JTG 的真实加载顺序下检查最终商品数量、价格和求解器记账，特别是 victuals 与 JTG 中性额外商品。
7. 用代表性大国存档记录年度完整计算和月度重写耗时，评估新增的地点×商品×人口类型成本。本次未提供实机性能数值，也不把 Python 测试时间当游戏性能。
8. 实机检查中英文商品悬停、状态切换、跨组重复、供应变暗及 +/- 角标；在 100% 和更大 UI 比例下检查提示框，特别是 JTG 的 1078px 静态预算。

算法 A 不承诺实际组预算守恒；国家单一商品因子会损失市场与 POP 精度。旧 Engel、宗教/文化偏好、开发度抵消、时代缩放和 scarcity 总量补偿均未恢复。
