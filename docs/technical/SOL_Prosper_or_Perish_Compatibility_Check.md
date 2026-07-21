# SOL 与 Prosper or Perish 兼容性检查

> 2026-07-21 实施更新：本报告描述的是**未加载兼容子模时**的冲突状态。仓库现已新增
> `src/sol_pp_compatibility_submod`，负责清理 LIA/天气灾害 modifier 残差、把 lumber
> 最终人口需求归零、把 victuals 纳入 SOL 生活水平计算，并覆盖地点与局势商品面板。
> `stable` 与 `sol_standalone` 本身不再探测 P&P，也不再包含 P&P 专属 UI/数值分支。

日期：2026-07-20

## 检查对象

- 本模组：`src/stable`，Standard of Living，简称 SOL。
- 目标模组：`reference_mods/3613232232`，Prosper or Perish，简称 P&P。
- 本地参考副本信息：P&P 版本 `0.9.0`，标注支持游戏版本 `1.3.10`。
- SOL 本地 metadata：版本 `1.3.11`，标注支持游戏版本 `1.3.11`。

本报告基于仓库内 `reference_mods/3613232232` 的静态文件检查。没有进行游戏内联合加载测试，也没有读取联合运行后的 `error.log`。

## 关键加载规则

本次兼容性判断必须先明确一个已知行为：

**当两个模组对同一个数据库 key 使用 `TRY_REPLACE` 时，最终覆盖关系取决于文件加载顺序；而 common 数据库文件的加载顺序受文件名排序影响。**

SOL 当前许多会覆盖 vanilla 的文件使用了 `A_` 前缀，例如：

```text
src/stable/main_menu/common/static_modifiers/A_SOL_economy_modifiers.txt
src/stable/in_game/common/prices/A_SOL_economy_prices.txt
```

这会让 SOL 的这些文件较早加载。P&P 的相关文件多为 `pp_...`，排序晚于 `A_SOL_...`。因此在双方都 `TRY_REPLACE` 同一个 key 时，实际结果通常不是随机，也不是需要猜“谁后加载”，而是：

**SOL 的 `TRY_REPLACE` 会先应用，随后被 P&P 的后加载 `TRY_REPLACE` 覆盖。**

这点会显著改变兼容性结论：许多冲突项不是“双方互相不确定覆盖”，而是“默认情况下 SOL 的对应改动会丢失”。

## 总结论

**当前不建议声明 SOL 与 P&P 完全兼容。**

两者大概率不是一眼可见的“必然无法加载”关系，因为自定义命名空间大多分开，SOL 主要使用 `SOL_` / `sol_`，P&P 主要使用 `pp_`。双方也没有大量同路径文件覆盖。

但机制上并不兼容。原因有两类：

1. P&P 会在多个同 key `TRY_REPLACE` 上覆盖 SOL 的改动，因为 SOL 的 `A_` 文件先加载。
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

SOL 对 `total_population` 的关键改动包括：

- `local_max_rgo_size = 0.020`
- `free_building_levels = 0.05`
- 后续 `INJECT:total_population` 追加 `free_building_levels = 0.15`

P&P 文件：

```text
reference_mods/3613232232/main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt
```

P&P 对 `total_population` 的关键改动包括：

- `local_max_rgo_size = 0.0020`
- `local_food_capacity = 2.5`

由于 `A_SOL_economy_modifiers.txt` 早于 `pp_location_modifier_adjustments.txt` 加载，最终更可能保留 P&P 的 `TRY_REPLACE:total_population`，而 SOL 的 `total_population` 替换与同文件内后续注入都可能在最终结果中丢失。

影响：

- SOL 的总人口 RGO 缩放设计不会按预期生效。
- SOL 额外提供的 `free_building_levels` 可能丢失。
- P&P 的人口与食物容量设计会成为最终基线。

这必须通过兼容补丁手动合并。

### 2. `raised_levies`：SOL 的食物压力会被 P&P 覆盖

SOL 的 `raised_levies`：

- `local_raw_material_output = -0.3`
- `local_monthly_food_modifier = -0.3`

P&P 的 `raised_levies`：

- `local_production_efficiency = -0.10`
- `local_raw_material_output = -0.30`

因为 SOL 的 `A_SOL_economy_modifiers.txt` 先加载，P&P 的 `pp_location_modifier_adjustments.txt` 后加载，所以最终大概率保留 P&P 版本。也就是说，SOL 给征召状态追加的 `local_monthly_food_modifier = -0.3` 会丢失。

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

由于 SOL 的文件名前缀靠前，涉及同 key `TRY_REPLACE` 的部分默认会先应用，再被 P&P 后续文件覆盖或追加。这意味着 SOL 的 LIA 缓和不应假定仍然完整存在。

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

- SOL：`scaled_gold = 5.0`，并设置 `max_scale = 3000`
- P&P：`scaled_gold = 15.0`，没有 SOL 的封顶逻辑

道路价格：

- SOL：道路价格上调，但仍相对温和，并带有 SOL 自己的反滚雪球节奏。
- P&P：道路和基础设施成本更激进，服务于 P&P 的基础设施稀缺设计。

由于 SOL `A_SOL_economy_prices.txt` 先加载，P&P 的 `pp_...` 价格文件后加载，最终结果会更偏向 P&P，而不是 SOL。

影响：

- SOL 对道路价格的平衡设定大概率不会成为最终结果。
- `embrace_institution` 的 SOL 封顶逻辑可能丢失。
- 兼容补丁需要明确采用 P&P、SOL，还是第三套折中价格。

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

但考虑到 `A_` 加载前缀，SOL 中通过早加载 `TRY_REPLACE` 写入的部分食物压力或缓和逻辑，在与 P&P 同开时不应默认有效。最终更可能呈现 P&P 的食物系统，再叠加 SOL 未被覆盖的其他国家级自动修正和生活水平需求逻辑。

## 软风险

1. **性能风险**

   P&P 有大量 game start 和周期性 location/world 扫描。SOL 也有年度市场缓存、国家缓存和本地生活水平刷新。两者叠加可能提高开局和定期 pulse 的性能压力。

2. **版本风险**

   P&P 本地副本标注游戏版本 `1.3.10`，SOL 当前 metadata 标注 `1.3.6`。如果要发布兼容声明，应先同步双方最新版本并用当前游戏版本重新检查。

3. **已有检测钩子但未完成主链兼容**

   SOL 当前已有：

```text
sol_pp_victuals_compat_is_on
```

   这个 trigger 可以检测 P&P 相关全局变量。但当前 SOL 1.3 主需求链没有使用它把 `victuals` 纳入基础消费计算。因此它只是检测钩子，不等于已经兼容 P&P。

## 建议的兼容补丁方向

### 1. 补上 `victuals` 的 SOL 生活水平计算

兼容补丁至少应处理：

- 为 `victuals` 添加 SOL 单位消费常量。
- 在 `sol_refresh_market_pop_demand_maps` 中添加 `goods:victuals` 的市场价格与消费检测。
- 将 `victuals` 纳入各阶层基础消费支出。
- 如需在生活水平面板展示商品覆盖情况，也应加入国家 consumed-goods 聚合。

### 2. 用后加载文件合并被 P&P 覆盖的 SOL `TRY_REPLACE`

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

道路价格和 `embrace_institution` 必须明确采用哪套设计：

- 如果以 P&P 玩法为核心，应优先保留 P&P 更激进的道路与基础设施成本。
- 如果以 SOL 的反滚雪球但较温和平衡为核心，应保留 SOL 的 capped price 逻辑。
- 如果要两者混合，需要重新写一套兼容价格，而不是任由 P&P 后加载自然覆盖 SOL。

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

兼容补丁必须最后加载，并且文件名应确保晚于双方相关文件，例如使用 `zz_` 或更明确的后加载前缀。

## 最终判断

**当前状态：不兼容 / 需要兼容补丁。**

理由不是“两者一定会立刻崩溃”，而是：

- SOL 的 `A_` 前缀使其 `TRY_REPLACE` 更早加载，冲突处会被 P&P 后加载文件覆盖。
- P&P 新增的 `victuals` 消费没有进入 SOL 的生活水平计算。
- 双方在食物、人口、道路、RGO、价格和商品需求上服务于不同平衡目标。

如果目标只是“能不能进游戏”，需要实际加载测试确认。  
如果目标是“机制是否正确共存”，答案是：**目前不能，需要 compatch。**

## 验证状态

- 已完成静态文件冲突扫描。
- 已检查 goods、prices、static_modifiers、on_action、scripted triggers/effects 等主要交叉区域。
- 已根据已知文件加载规则修正结论：SOL 的 `A_` 前缀会让相关 `TRY_REPLACE` 先加载，并在同 key 冲突中被 P&P 后加载文件覆盖。
- 未完成 `validate.py --changed`，此前两次运行分别在 120 秒和 300 秒超时。
- 未进行游戏内联合加载测试。
