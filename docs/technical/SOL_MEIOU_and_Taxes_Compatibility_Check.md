# SOL 与 MEIOU and Taxes 兼容性检查

> 实施状态：审计发现已由 `src/sol_mnt_compatibility_submod` 和
> `scripts/gen_sol_mnt_compat.py` 落地；本文保留为实施前冲突依据。

日期：2026-07-22

## 检查对象

- SOL：`src/stable`，版本 `1.3.11`，目标游戏版本 `1.3.11`。
- 目标模组：`reference_mods/3735059838`，即 **MEIOU and Taxes**（下称 M&T），版本 `0.1.6`，目标游戏版本 `1.3.*`。
- 本报告基于仓库内文件进行静态检查，没有进行游戏内联合加载，也没有读取联合运行后的 `error.log`。

## 最终结论

**当前状态：不兼容，需要专用兼容补丁。**

两者不一定会在启动时立即崩溃，但不能认为经济机制正确共存。主要原因不是普通的数值叠加，而是 M&T 对所有 55 个 SOL 人口消费商品使用 `REPLACE`，会在数据库操作顺序中抹掉 SOL 的全部商品校准；SOL 的运行时倍率却仍按自己的硬编码消费矩阵计算。最终结果是“实际商品需求”和“SOL 用来计算倍率、UI 与生活水平的基础支出”来自两套不同数据。

仅调整播放列表顺序无法解决商品冲突。`INJECT` 与 `REPLACE` 的处理顺序固定为：

```text
INJECT_OR_CREATE -> REPLACE_OR_CREATE -> TRY_INJECT -> TRY_REPLACE -> INJECT -> REPLACE
```

M&T 的 `REPLACE` 始终晚于 SOL 的 `INJECT`。播放列表顺序只会改变同相对路径整文件覆盖，以及相同数据库操作类型之间的先后。

## 扫描摘要

排除每个模组自身的 `.metadata`、缩略图和 README 后，发现：

| 类型 | 数量 | 判断 |
| --- | ---: | --- |
| 完全相同的活动文件路径 | 1 | `in_game/gui/location_window.gui` 整文件互斥 |
| 同数据库顶层对象 | 68 | 55 goods、3 on_actions、4 prices、5 static modifiers、1 define block |
| 同名本地化 key | 0 | 未发现冲突 |
| 同名事件 namespace / event ID | 0 | 未发现冲突 |
| 同名 scripted effect / trigger / GUI / script value | 0 | 未发现冲突 |

GUI 扫描另发现 13 个同名 `type`，但它们全部位于上述同路径 `location_window.gui` 内，不是额外的独立冲突。

## 1. 核心冲突：55 个 goods 的 SOL 校准全部丢失

SOL 的 `src/stable/in_game/common/goods/z_SOL_pop_goods.txt` 对 55 个商品使用 `INJECT`，用途包括：

- 校准 `demand_add`；
- 完全抵消 9 个 vanilla `development_threshold`；
- 完全抵消 35 个 `wealth_impact_threshold`；
- 为 `SOL_market_unit_consumption_values.txt` 和 `sol_refresh_market_pop_demand_maps` 提供一致的单位人口消费矩阵。

M&T 在以下文件中用 `REPLACE` 重新定义全部 74 个 vanilla goods，其中包括 SOL 修改的全部 55 个商品：

```text
reference_mods/3735059838/in_game/common/goods/MnT_raw_materials.txt
reference_mods/3735059838/in_game/common/goods/MnT_plantation_goods.txt
reference_mods/3735059838/in_game/common/goods/MnT_produced_goods.txt
reference_mods/3735059838/in_game/common/goods/MnT_food.txt
```

因此最终数据库对象采用 M&T 完整定义，SOL 注入的 `demand_add` 和 threshold 抵消项全部消失。静态解析结果为：

- 55/55 个共享人口消费商品的最终消费数量都与 SOL 硬编码矩阵不同；
- 54/55 个共享商品的 M&T 默认价格与 SOL/vanilla 默认价格不同；
- M&T 最终保留 8 个正 `development_threshold`：`ivory`、`pearls`、`marble`、`porcelain`、`fine_cloth`、`paper`、`books`、`lacquerware`；
- M&T 最终保留 35 个正 `wealth_impact_threshold`。

SOL 的 `NPop.DEVELOPMENT_SCALE_ON_DEMAND = 0` 仍会生效，但它只能关闭引擎级开发度乘数，不能关闭 M&T 商品对象中保留的 8 个开发度门槛。因此 SOL 的“完全脱离开发度和财富门槛”设计也被破坏。

### 默认价格下的量化偏差

下表假设所有 55 个商品都在市场中存在，并使用 M&T 默认价格；比较的是 threshold 生效前的 M&T 实际基础支出与 SOL 缓存基础支出：

| Pop 类型 | M&T 实际基础支出 | SOL 缓存基础支出 | 实际 / 缓存 |
| --- | ---: | ---: | ---: |
| nobles | 5.430124 | 5.872889 | 0.925 |
| clergy | 0.716124 | 0.330736 | 2.165 |
| burghers | 0.607574 | 1.097779 | 0.553 |
| laborers | 0.144781 | 0.002851 | 50.778 |
| peasants | 0.020620 | 0.002425 | 8.503 |
| soldiers | 0.165999 | 0.004089 | 40.599 |
| tribesmen | 0.000500 | 0 | 无有效比值 |

这不是轻微平衡偏差。SOL 会用右侧缓存计算 `local_pop_demand` 倍率，再把倍率施加到左侧 M&T 实际需求上。尤其是 laborers、peasants、soldiers 和 tribesmen，闭合收入与消费的核心假设不成立。实际市场价格、商品缺失以及 M&T 的 wealth/development gates 还会让偏差随地点继续变化。

## 2. `location_window.gui` 整文件互斥

双方都提供：

```text
in_game/gui/location_window.gui
```

这属于完全相同相对路径的整文件覆盖，播放列表中位置更低的模组获胜，另一个文件完全不参与加载。

- M&T 靠下：保留 M&T 的建筑化 RGO 显示和 scripted GUI 调用，但丢失 SOL 的地点收入行与 `stat_sol_living_standard` 入口。SOL 的局势面板和独立 mapmode 文件仍可能存在，但地点窗口集成不完整。
- SOL 靠下：保留 SOL 的收入与生活水平入口，但丢失 M&T 的 RGO 建筑可见性、容量显示和交互。由于 M&T 把 vanilla RGO 替换成建筑，这会破坏其核心地点窗口工作流。

所以该冲突不存在一个“正确加载顺序”；兼容补丁必须以 M&T 文件为基底合并 SOL 的两个入口。

## 3. M&T 地产维护与 SOL 净收入算法不一致

SOL 在 `A_SOL_economy_effects.txt` 中按地点扫描 estate buildings，并固定按每个建筑 1 gold 记录维护费；随后从各阶层地点收入中减去该值，再计算生活水平倍率。

M&T 则：

- 在 `MnT_Defines.txt` 中设置 `NEstate.UPKEEP_PER_BUILDING = 0`；
- 由 EPBM 系统按生产方式投入、市场价格、建筑效率、建筑等级、地产权力和通胀计算维护费；
- 通过 `epbm_charge_estates` 每月直接修改地产资金。

SOL 不读取 `epbm_pay_*`、`epbm_pool_*` 或 `epbm_assigned_*`。因此它显示和使用的地产维护费不是 M&T 的真实维护费；同时 M&T 的真实扣款还会通过 estate gold 影响 SOL 的储蓄压力。结果可能同时包含真实的 EPBM 储蓄变化与一套无关的“每建筑 1 gold”净收入扣除。

这不会由数据库加载顺序自动解决，必须替换 SOL 的维护费缓存逻辑，或在 M&T 组合中明确禁用该扣除。

### 能否直接借用 EPBM 的计算结果

**可以借用国家级结果，但不能直接替代 SOL 的地点级变量。**

EPBM 已在 country scope 写入每月维护费：

| M&T 变量 | 含义 | SOL 初步映射 |
| --- | --- | --- |
| `epbm_pay_nobles` | nobles estate 最终应付维护费 | nobles |
| `epbm_pay_clergy` | clergy estate 最终应付维护费 | clergy |
| `epbm_pay_burghers` | burghers estate 最终应付维护费 | burghers |
| `epbm_pay_peasants` | peasants estate 最终应付维护费 | commoners |
| `epbm_pay_tribes` | tribes estate 最终应付维护费 | tribesmen 的近似来源 |
| `epbm_pay_cossacks` | cossacks estate 最终应付维护费 | M&T pop 定义中主要归入 tribesmen |
| `epbm_pay_dhimmi` | dhimmi estate 最终应付维护费 | 无法直接对应单一 SOL 阶层 |

应读取 `epbm_pay_*`，而不是 `epbm_show_*` 或 `epbm_prev_*`：

- `epbm_pay_*` 是 EPBM 实际用于下一次 `add_gold_to_estate` 扣款的值，也是 M&T 自己的维护费总览读取值；玩家每月重算，AI 每年重算并逐月按缓存扣款。
- `epbm_show_*` / `epbm_prev_*` 是玩家 tooltip 的历史快照，AI 月度路径不维护这组快照，因此不能作为所有国家的统一数据源。
- 不应自行使用 `epbm_pool_* + epbm_assigned_*` 重组总额；`epbm_pay_*` 已包含有效的 shared-pool 与 estate-assigned 成本，而且 breakdown 变量在某项本月归零时可能保留旧值。

但是 `epbm_pay_*` 只有国家总额。SOL 当前在每个地点分别扣除 `local_sol_*_building_maintenance`；如果把完整 `epbm_pay_nobles` 等值放进每个地点，会按国家地点数重复扣款。

推荐的兼容实现是：

1. 在 country scope 直接读取 `epbm_pay_*`，不要再次调用 `epbm_calculate_maintenance`。M&T 已经运行该建筑扫描，重复调用只会增加开销并改变刷新时序。
2. 将 nobles、clergy、burghers、peasants 映射到 SOL 的四个对应阶层；将 cossacks 暂并入 tribesmen。
3. 对 `epbm_pay_tribes` 和 `epbm_pay_dhimmi` 做显式策略选择。M&T 的 dhimmi 可来自多种 pop，Gaelic tribes estate 也不一定只代表 tribesmen；较稳妥的近似是按各 SOL 阶层全国毛收入占比分摊这些无法一一映射的费用。
4. 对每个可直接映射的阶层，把国家支出按“地点该阶层毛收入 / 全国该阶层毛收入”分摊到地点。这样全国各地点维护费之和严格等于 `epbm_pay_*`，也比按人口分摊更符合 SOL 的收入闭合模型。
5. 如果需要精确到维护费实际发生的建筑地点，现有 `epbm_pay_*` 不够；需要在 EPBM 已有的 building loop 内新增 location-keyed 缓存。单纯读取现有变量无法恢复地点来源。

这种方案能直接复用 M&T 已经完成的市场价格、生产方式、建筑等级、效率、estate power 和通胀计算，同时避免 SOL 继续运行自己的“每建筑 1 gold”扫描。代价是按毛收入分摊属于兼容层模型，不是 EPBM 原生记录的地点成本。

## 4. 道路价格由 M&T `REPLACE` 覆盖

SOL 使用 `TRY_INJECT` 增加道路 gold cost，M&T 使用 `REPLACE`。最终采用 M&T：

| Price key | SOL 目标 | M&T 最终值 |
| --- | ---: | ---: |
| `build_gravel_road` | 20 | 8 |
| `build_paved_road` | 50 | 25 |
| `build_modern_road` | 150 | 100 |
| `build_railroad` | 500 | 500 |

这里的数值只是 price 对象中的 gold 字段；M&T 还通过道路类型和 goods demand 调整完整成本。兼容补丁应让 M&T 拥有道路体系，而不是把 SOL gold delta 重新叠加回去。

## 5. 五个静态 modifier 由 M&T `REPLACE` 覆盖

| 对象 | 丢失的 SOL 设计 | M&T 最终方向 |
| --- | --- | --- |
| `location_base_values` | +0.0005 control、+0.009 promotion、-1 base RGO | promotion 改为 0.0002，native RGO 基础设为 0 |
| `inverse_control` | -0.5 低控制建筑效率 | M&T 定义不包含该建筑效率惩罚 |
| `total_population` | -0.005 RGO scaling、+0.15 free building levels | native RGO scaling 移除，free building levels 最终同为 0.2 |
| `looted` | 清除 vanilla prosperity decay，增加 -0.025 monthly prosperity | M&T 使用 0.2 prosperity decay，并加入人口、开发度、attrition 效果 |
| `winter_normal` | 更强食物压力并抵消 food decay | M&T 把食物影响交给 climate，保留 0.0025 food decay |

这些覆盖使 SOL 的部分功能失效，但与 goods 冲突相比，它们主要是玩法归属问题。M&T 是完整 overhaul，建议由 M&T 拥有这些基础对象。

## 6. 能正常合并的部分

### On-actions

双方重复定义 `on_game_start`、`monthly_country_pulse`、`yearly_country_pulse`，但都只通过 `on_actions = { ... }` 注册各自带前缀的 dispatcher。按项目已验证规则，这些列表会合并；未发现 dispatcher 同名冲突。

联合启用仍会同时运行两边的周期扫描：SOL 的月度地点需求刷新、年度市场/地产缓存，以及 M&T 的 EPBM、RGO、中心与其他周期逻辑。需要游戏内性能测试，但这不是静态覆盖错误。

### Defines

双方都有 `NPop = { ... }`，但字段不重叠：

- SOL：`DEVELOPMENT_SCALE_ON_DEMAND`、`PERFORMANCE_UPDATE_DEMANDS_MIN/MAX`；
- M&T：`RELIGION_OPINION_SATISFACTION`、`TOLERANCE_ON_SATISFACTION_SCALE`。

未发现 define 字段级冲突。

### 命名空间

未发现 SOL 与 M&T 在 localization、event IDs、scripted effects、scripted triggers、script values、scripted GUIs 或 mapmode IDs 上同名。除地点窗口外，双方自定义命名空间隔离良好。

## 7. 额外玩法叠加风险

即使修复硬冲突，完整 SOL 与 M&T 仍有显著的平衡叠加：

- SOL 年代升级继续增加全局建筑成本、RGO 扩张成本、城市/城镇升级成本和人口食物消耗；M&T 已重做 RGO 建筑、建设成本和食物系统。
- M&T 的 RGO replacement buildings 使用 `expand_rgo_*` prices，因此 SOL 年代 `expand_rgo_*_cost_modifier` 仍可能作用于这些建筑，在 M&T 自身逐级成本缩放上再次加价。
- SOL 的 raised levies、siege、occupation、blockade 等未被 M&T 同 key 替换的 modifier 会继续叠加到 M&T 规则上。
- SOL 的 GDP-to-development、动态外交支出、税收与反滚雪球规则会继续运行在 M&T 的经济体系上；这属于未校准组合，不是单纯的语法兼容。

因此，即使制作 compatch，也不建议原样保留 full SOL 的全部平衡功能。`sol_standalone` 能减少这些额外叠加，但它仍然存在本报告第 1、2、3 节的核心冲突，不能直接与 M&T 共用。

## 建议的兼容补丁方向

推荐以 M&T 为规则主体，制作一个最后加载的 SOL/M&T compact compatch：

1. **商品与消费矩阵统一**
   - 对 55 个 goods 使用完整 `REPLACE`，以 M&T 对象为基底；不能使用更晚文件名的 `INJECT`。
   - 二选一：保留 SOL 校准的最终 `demand_add`；或保留 M&T demand 并重新生成 SOL 单位消费常量。无论选择哪种，实际 goods 与 SOL 缓存必须来自同一矩阵。
   - 明确处理 8 个 `development_threshold`、35 个 `wealth_impact_threshold` 和 M&T 的 tribesmen demand。

2. **合并地点窗口**
   - 以 M&T `location_window.gui` 为基底，保留其 RGO building UI。
   - 注入 SOL 的地点收入显示和 `stat_sol_living_standard` 入口。

3. **适配 EPBM**
   - 直接读取 country-scope `epbm_pay_*`，不要重复调用 `epbm_calculate_maintenance`。
   - 按地点阶层毛收入占比分摊国家维护费，以替换 SOL 的“每建筑 1 gold”估算；若要求精确地点来源，则需扩展 EPBM 的 building loop 写入地点缓存。
   - 显式处理无法一一映射的 `dhimmi` 与 `tribes`，并将 M&T 中来自 tribesmen 的 `cossacks` 费用纳入相应 SOL 支出。

4. **确定玩法归属**
   - M&T 应拥有 location base、native RGO、roads、winter/food、looted 和 building maintenance。
   - 只保留 SOL 的收入驱动需求倍率、生活水平 UI/mapmode，以及明确选中的少量非冲突规则。
   - 不应加载现有 `sol_pp_compatibility_submod`；它只处理 Prosper or Perish，不包含 M&T 数据。

5. **联合运行验证**
   - 建议测试顺序：M&T、SOL 或 SOL standalone、SOL/M&T compatch；full SOL 还需要在 SOL 前加载 Community Mod Framework。
   - 新开局至少检查 `error.log`、地点窗口 RGO 与 SOL 入口、市场 pop demand、tribesmen demand、EPBM 扣款、月度倍率和年度市场缓存。
   - 对 1337 开局与一次年度 pulse 分别做性能采样。

## 验证状态

- 已完成同相对路径文件扫描。
- 已完成 `.txt` 顶层对象与操作类型交叉扫描。
- 已完成 GUI type、本地化 key、事件 namespace/ID 与 SOL/M&T 命名空间扫描。
- 已解析 M&T 74 个 goods，并与 SOL 55 个单位消费常量逐项比较。
- 已检查道路价格、静态 modifiers、defines、on-actions、EPBM 与地点窗口。
- 未修改 `src/`，未生成兼容补丁。
- 未进行游戏内联合加载，启动稳定性与实际性能仍需运行时验证。
