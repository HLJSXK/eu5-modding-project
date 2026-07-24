# SOL 与 Prosper or Perish 兼容性检查

> 2026-07-21 实施更新：本报告描述的是**未加载兼容子模时**的冲突状态。仓库现已新增
> `src/sol_pp_compatibility_submod`，负责清理 LIA/天气灾害 modifier 残差、把 lumber
> 最终人口需求归零、把 victuals 纳入 SOL 生活水平计算，并覆盖地点与局势商品面板。
> `stable` 与 `sol_standalone` 本身不再探测 P&P，也不再包含 P&P 专属 UI/数值分支。
>
> 2026-07-24 价格注入更正：价格对象中重复的 `gold` 等标量字段并不累加，后加载
> 的字段会替代前值。SOL 的 `A_SOL_economy_prices.txt` 早于 P&P 的
> `pp_road_gold_adjustments.txt`，因此 P&P 自然拥有最终道路价格；兼容子模不得再用
> 负数注入尝试抵消 SOL，否则负值会成为最终价格并在运行时把费用钳制为 0。

日期：2026-07-20

## 检查对象

- 本模组：`src/stable`，Standard of Living，简称 SOL。
- 目标模组：`reference_mods/3613232232`，Prosper or Perish，简称 P&P。
- 本地参考副本信息：P&P 版本 `0.9.0`，标注支持游戏版本 `1.3.10`。
- SOL 本地 metadata：版本 `1.3.11`，标注支持游戏版本 `1.3.11`。

本报告基于仓库内 `reference_mods/3613232232` 的静态文件检查。没有进行游戏内联合加载测试，也没有读取联合运行后的 `error.log`。

## 关键加载规则

本次兼容性判断必须先明确一个已知行为：数据库对象先按操作类型处理，再在相同操作类型内按文件顺序处理。当前顺序为：

```text
INJECT_OR_CREATE -> REPLACE_OR_CREATE -> TRY_INJECT -> TRY_REPLACE -> INJECT -> REPLACE
```

SOL 当前许多会覆盖 vanilla 的文件使用了 `A_` 前缀，例如：

```text
src/stable/main_menu/common/static_modifiers/A_SOL_economy_modifiers.txt
src/stable/in_game/common/prices/A_SOL_economy_prices.txt
```

文件名前缀只在双方操作类型相同时决定顺序。P&P 对 `total_population`、`raised_levies` 和 `embrace_institution` 使用 `TRY_REPLACE`，因此会在 SOL 的 `TRY_INJECT` 之后处理并抹掉对应注入，与 `A_`/`pp_` 文件名无关。双方都使用 `TRY_INJECT` 时仍需按数据类型判断：LIA 静态修正器的数值 delta 会累加；道路价格中重复的 `gold` 标量则由后加载字段替代前值。

## 总结论

**当前不建议声明 SOL 与 P&P 完全兼容。**

两者大概率不是一眼可见的“必然无法加载”关系，因为自定义命名空间大多分开，SOL 主要使用 `SOL_` / `sol_`，P&P 主要使用 `pp_`。双方也没有大量同路径文件覆盖。

但机制上并不兼容。原因有两类：

1. P&P 的后处理 `TRY_REPLACE` 会抹掉 SOL 对部分同 key 对象的 `TRY_INJECT`；双方都是 `TRY_INJECT` 时，静态修正器数值可累加，但价格对象的重复标量字段由后值替代。
2. P&P 新增 `victuals` pop demand，但 SOL 当前的生活水平基础消费计算没有纳入 `victuals`。

因此更准确的结论是：

**两者可能可以一起加载，但不能认为经济机制正确共存；需要单独兼容补丁。**

## 相对安全的部分

1. **文件路径冲突很少**

   除 `.metadata/metadata.json` 和 `.metadata/thumbnail.png` 外，没有发现 SOL active 内容与 P&P active 内容存在相同相对路径文件冲突。

2. **命名空间基本分离**

   没有发现 SOL 与 P&P 在 scripted effects、scripted triggers、scripted GUIs、GUI、map modes、modifier icons 等区域出现明显同名顶层 key 冲突。

3. **on_action 大概率能合并**

   双方都定义了 `on_game_start`、`yearly_country_pulse` 等 on_action 入口。按照项目已知规则，EU5 会合并同名 on_action 的 `on_actions` 列表，因此这类重复定义本身不一定是覆盖冲突。

## 主要硬冲突

### 1. `total_population`：SOL 改动默认会被 P&P 覆盖

SOL 文件：

```text
src/stable/main_menu/common/static_modifiers/A_SOL_economy_modifiers.txt
```

SOL 当前通过 `TRY_INJECT:total_population` 注入相对 vanilla 的 delta：

- `local_max_rgo_size = -0.005`
- `free_building_levels = 0.15`

P&P 文件：

```text
reference_mods/3613232232/main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt
```

P&P 对 `total_population` 的关键改动包括：

- `local_max_rgo_size = 0.0020`
- `local_food_capacity = 2.5`

P&P 的 `TRY_REPLACE:total_population` 在 `TRY_INJECT` 批次之后处理，因此会整体抹掉 SOL delta。最终保留 P&P 版本，不取决于双方文件名前缀。

影响：

- SOL 的总人口 RGO 缩放设计不会按预期生效。
- SOL 额外提供的 `free_building_levels` 可能丢失。
- P&P 的人口与食物容量设计会成为最终基线。

这必须通过兼容补丁手动合并。

### 2. `raised_levies`：SOL 的食物压力会被 P&P 覆盖

SOL 当前对 `raised_levies` 注入相对 vanilla 的 delta：

- `local_raw_material_output = -0.1`
- `local_monthly_food_modifier = -0.1`

P&P 的 `raised_levies`：

- `local_production_efficiency = -0.10`
- `local_raw_material_output = -0.30`

由于 P&P 使用 `TRY_REPLACE:raised_levies`，该替换在 SOL 的 `TRY_INJECT` 之后处理，SOL delta 会丢失，最终保留 P&P 版本。

影响：

- SOL 的“征召加剧食物压力”设计不会按预期生效。
- P&P 的生产效率惩罚会保留。
- 如果想两者共存，兼容补丁应合并为同时包含生产效率、原料、食物压力的版本。

### 3. Little Ice Age 与天气/灾害相关 modifier：SOL 缓和逻辑会被部分覆盖或反向叠加

双方都碰到一些 vanilla 食物和灾害修正，例如：

- `harsh_winters_modifier`
- `fewer_fisheries_modifier`
- `short_harvest_modifier`
- `recent_white_storm_modifier`

SOL 的目标是缓和部分 Little Ice Age 与灾害食物惩罚，避免食物危机失控。P&P 则大幅重做食物系统，并对很多天气、灾害、任务修正追加新的作物产出与食物压力逻辑。

这些 LIA 对象中，SOL 与 P&P 当前主要都使用 `TRY_INJECT`。因此双方 delta 会累加，而不是由后加载文件整体覆盖；这提高了结构兼容性，但未经兼容子模清理时，最终数值仍可能同时包含 SOL 缓和与 P&P 的作物/食物重做，不能直接视为经过平衡的组合。

影响：

- 食物压力强度会更接近 P&P 设计，而不是 SOL 设计。
- SOL 文档中对 LIA 缓和的描述，在与 P&P 同开时不一定成立。
- 兼容补丁需要重新决定这些 modifier 的最终数值。

### 4. 价格定义：道路和机构价格默认更偏向 P&P

SOL 文件：

```text
src/stable/in_game/common/prices/A_SOL_economy_prices.txt
```

P&P 文件示例：

```text
reference_mods/3613232232/in_game/common/prices/pp_institution_price_adjustments.txt
reference_mods/3613232232/in_game/common/prices/pp_road_gold_adjustments.txt
```

冲突项包括：

- `embrace_institution`
- `build_gravel_road`
- `build_paved_road`
- `build_modern_road`
- `build_railroad`

`embrace_institution`：

- SOL：用 `TRY_INJECT` 添加 `max_scale = 3000`
- P&P：用 `TRY_REPLACE` 定义 `scaled_gold = 15.0`、`stability = 50`
- 结果：P&P 替换在 SOL 注入之后处理，SOL 封顶仍会丢失

道路价格双方都使用 `TRY_INJECT`，但价格对象中的重复 `gold` 字段不是加法。由于 `A_SOL_economy_prices.txt` 先加载、`pp_road_gold_adjustments.txt` 后加载，P&P 的字面值成为最终值：碎石路 30、铺装路 160、现代路 380、铁路 1100。

影响：

- 道路价格由 P&P 的后加载字段自然接管，不需要兼容子模再写价格清理文件。
- `embrace_institution` 的 SOL 封顶逻辑可能丢失。
- 如果未来需要第三套折中道路价格，应写经过验证的最终对象；不能用负 `TRY_INJECT` 抵消前值。

### 5. 商品需求与商品属性大范围重叠

SOL 在 `z_SOL_pop_goods.txt` 中对 55 种商品注入校准后的 `demand_add` 和部分 `wealth_impact_threshold`。

P&P 在 `pp_goods_adjustments.txt` 中对其中约 51 种商品也做了注入，常见字段包括：

- `food`
- `transport_cost`
- `default_market_price`
- `block_rgo_upgrade`
- `demand_add`

这里多数是 `INJECT` / `TRY_INJECT`，不是同 key `TRY_REPLACE`，所以并不等同于上面的完整覆盖问题。多数商品字段理论上可以叠加。

但需要注意两个点：

- `salt` 和 `lumber` 双方都涉及 `demand_add`，需要单独检查最终消费篮子。
- P&P 修改 `default_market_price` 与 `transport_cost` 后，会影响 SOL 基础消费支出的市场价格估算。

### 6. P&P 新增 `victuals`，但 SOL 主计算未计入

这是最重要的机制兼容问题。

P&P 新增商品：

```text
reference_mods/3613232232/in_game/common/goods/pp_goods_victuals.txt
```

并通过：

```text
reference_mods/3613232232/in_game/common/goods_demand/pp_new_goods_demands.txt
```

向 `pop_demand` 注入：

```text
INJECT:pop_demand = {
    victuals = 1
}
```

也就是说，P&P 激活后，`victuals` 会成为人口消费篮子的一部分。

但 SOL 的生成文件：

```text
src/stable/in_game/common/script_values/SOL_market_unit_consumption_values.txt
```

当前没有 `victuals` 的单位消费常量。SOL 的：

```text
sol_refresh_market_pop_demand_maps
```

也没有 `goods:victuals` 的价格、市场消费、基础支出计算路径。

结果是：P&P 开启后，人口实际需要消费 `victuals`，但 SOL 的生活水平算法没有把它算进基础消费支出。这样会导致 SOL 低估人口维持生活所需的消费成本，从而高估生活水平，并可能给出过高的 `local_pop_demand` 修正。

这一项不会被 `A_` 文件加载顺序解决，必须修改 SOL 计算链或制作 compatch。

### 7. 食物系统存在概念冲突

P&P 的核心设计是让食物成为人口增长、迁移、储备和地方经济压力的主轴。它大幅改动：

- pop food consumption
- local food capacity
- food price behavior
- starvation
- cheap/expensive food modifiers
- food storage
- victuals / food revenue 商品链
- 农业与食物建筑体系

SOL 也有自己的食物和反滚雪球设计，包括：

- 年代推进增加 `global_pop_food_consumption`
- 冬季和征召带来更强食物压力
- Little Ice Age 惩罚缓和
- RGO 和建设成本调整

由于操作类型不同，SOL 的部分食物 delta 会被 P&P 的 `TRY_REPLACE` 抹掉；双方同为 `TRY_INJECT` 的 LIA/灾害 delta 则会叠加。最终更可能呈现 P&P 的食物系统、双方累加的部分灾害修正，再叠加 SOL 未被覆盖的国家级自动修正和生活水平需求逻辑。

## 软风险

1. **性能风险**

   P&P 有大量 game start 和周期性 location/world 扫描。SOL 也有年度市场缓存、国家缓存和本地生活水平刷新。两者叠加可能提高开局和定期 pulse 的性能压力。

2. **版本风险**

   P&P 本地副本标注游戏版本 `1.3.10`，SOL 当前 metadata 标注 `1.3.11`。如果要发布兼容声明，应先同步双方最新版本并用当前游戏版本重新检查。

3. **基础模组不包含 P&P 检测分支**

   `stable` 和 `sol_standalone` 不探测 P&P，也不在基础计算链中包含 `victuals`。P&P 专属计算和 UI 由独立的 `src/sol_pp_compatibility_submod` 提供；不加载该子模时，本报告中的机制缺口仍然存在。

## 建议的兼容补丁方向

### 1. 补上 `victuals` 的 SOL 生活水平计算

兼容补丁至少应处理：

- 为 `victuals` 添加 SOL 单位消费常量。
- 在 `sol_refresh_market_pop_demand_maps` 中添加 `goods:victuals` 的市场价格与消费检测。
- 将 `victuals` 纳入各阶层基础消费支出。
- 如需在生活水平面板展示商品覆盖情况，也应加入国家 consumed-goods 聚合。

### 2. 用兼容子模合并被 P&P 替换或与 P&P 累加的 SOL delta

兼容补丁应最后加载，并重新定义以下 key 的最终形态：

- `total_population`
- `raised_levies`
- `harsh_winters_modifier`
- `fewer_fisheries_modifier`
- `short_harvest_modifier`
- `recent_white_storm_modifier`
- `embrace_institution`
- `build_gravel_road`
- `build_paved_road`
- `build_modern_road`
- `build_railroad`

重点不是“让 SOL 覆盖回来”，而是把 SOL 与 P&P 的设计有选择地合并成一套最终规则。

### 3. 明确价格设计归属

当前 compact 方案的价格归属如下：

- 道路价格由 P&P 的后加载 `TRY_INJECT` 字段接管，兼容子模不生成道路价格文件。
- `embrace_institution` 仍由 P&P 的 `TRY_REPLACE` 接管。
- 如果以后要混合两套道路价格，应明确写最终值；不能把重复 price 标量当作 additive delta。

### 4. 检查是否需要关闭或缩放 SOL 食物压力

P&P 已经极大强化食物系统。兼容补丁可以考虑在检测到 P&P 时：

- 关闭 SOL 的部分 food pressure；
- 或降低 SOL 的 age escalation food consumption；
- 或只保留 SOL 的生活水平系统，弱化 SOL 的食物惩罚。

### 5. 推荐测试加载顺序

建议初始测试顺序：

```text
1. Community Mod Framework
2. Prosper or Perish
3. Standard of Living
4. SOL / P&P Compatibility Patch
```

兼容补丁应放在双方之后，以确保同路径文件覆盖关系符合预期；对数据库对象还必须选择正确的操作类型。文件名 `zz_` 只在双方使用相同操作类型时决定先后，不能让 `TRY_INJECT` 越过后处理的 `TRY_REPLACE`。

## 最终判断

**当前状态：不兼容 / 需要兼容补丁。**

理由不是“两者一定会立刻崩溃”，而是：

- P&P 的 `TRY_REPLACE` 会在 SOL `TRY_INJECT` 之后处理并抹掉对应 delta；双方同为 `TRY_INJECT` 的对象则会累加。
- P&P 新增的 `victuals` 消费没有进入 SOL 的生活水平计算。
- 双方在食物、人口、道路、RGO、价格和商品需求上服务于不同平衡目标。

如果目标只是“能不能进游戏”，需要实际加载测试确认。  
如果目标是“机制是否正确共存”，答案是：**目前不能，需要 compatch。**

## 验证状态

- 已完成静态文件冲突扫描。
- 已检查 goods、prices、static_modifiers、on_action、scripted triggers/effects 等主要交叉区域。
- 已按数据库操作优先级修正结论：操作类型先于文件名；`TRY_REPLACE` 会晚于 `TRY_INJECT` 处理，相同 `TRY_INJECT` 则按文件顺序全部追加。
- 未完成 `validate.py --changed`，此前两次运行分别在 120 秒和 300 秒超时。
- 未进行游戏内联合加载测试。
