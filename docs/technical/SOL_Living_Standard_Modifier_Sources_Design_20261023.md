# 生活水平修正来源设计（2026-10-23）

状态：第 4.5 节第一批已实现（2026-10-23）；公式、来源、图标和中英说明已生成，待实机验收。
第 4.1–4.4 节是后续候选清单，第 6 节中尚未确定的阶层、战乱、疾病和制度项继续暂缓。
前置：`SOL_Living_Standard_Purchasing_Power_Separation_20261023.md`（公式与反馈），
`scripts/sol_living_standard_source.py`（`LOCAL_MODIFIER_ALL` / `LOCAL_MODIFIER_BY_ESTATE` 钩子）。

## 1. 目标与边界

修正只改生活水平，所以只影响三件事：移民吸引力、人口增长、排行（含顶栏分档和生活水平地图）。
它不进入流动资金、基准消费、购买力或需求。这一点由现有契约和 `test_sol_living_standard.py` 保证，本设计不改。

修正表达的是"钱买不到、但确实让日子更好或更差"的东西，主要有四类：
公共服务（医疗、清洁水），环境与安全（臭气、工厂、战乱、无法无天），疾病，以及制度（休息日、人身自由）。
钱已经反映的东西不再计入，例如市场、贸易、生产效率。

## 2. 公式（2026-10-23 用户定义）

设某地点、某阶层只算钱的生活水平为 x，即千人均年流动资金。修正后：

```
生活水平 = 固定值之和 + (1 + 百分比之和) × x        最低为 0
```

算例：x = 1.0，有一个固定 +0.2、一个 +5%，则生活水平 = 0.2 + 1.05 × 1.0 = 1.25。

- 多个百分比相加后再乘，不连乘：+5% 和 +3% 合起来是 1.08 × x。这和原版百分比修正的叠加方式相同。
- 百分比只乘钱的部分，不乘固定值。
- 百分比之和低于 −100% 时，按 −100% 算，即钱的部分最低为 0。
- 公式按阶层算，地点和国家仍按人口加权汇总。如果修正对全体阶层相同，按阶层算再加权，
  结果与直接对地点生活水平套公式完全一样：Σ人口ₑ·(f + (1+p)·xₑ) ÷ 总人口 = f + (1+p)·x。

### 2.1 分工原则（用户确认）

**固定值主要影响低生活水平，百分比主要影响高生活水平。** 每个来源挂哪一种，就看它在现实中主要作用于谁：

- **固定值：生存层面的东西。** 生老病死、安全、住处、基本的人身自由。它们对穷人和富人是同一个绝对量，
  所以对穷人是大事，对富人几乎无感。以 0.1 贫困线为例：x = 0.05 的农村加 +0.05 就能越线，
  而 x = 300 的贵族加同样的数，变化不到万分之二。
- **百分比：品质层面的东西。** 文化、闲暇、高端服务、整体繁荣，以及环境好坏对享受的折损。
  能从中多得的人，本来就是有余力去享用的人。x = 0.05 的农村加 +5% 只多 0.0025，x = 300 的贵族加 +5% 多 15。

判断时可以问一句：**"这件事落在一个一无所有的人身上，影响会不会小？"**
会的，用百分比，例如歌剧院；不会的，用固定值，例如瘟疫、围城、清洁水。

固定值的单位是每千人每年。它不随时代放大，所以后期作用会自然变小，因为那时穷地方也少了。这也符合它"兜底"的定位。

## 3. 机制：新增游戏修正类型

### 3.1 修正类型

每个作用范围定义一对修正类型，一个是固定值，一个是百分比：

```
# main_menu/common/modifier_type_definitions/SOL_living_standard_modifier_types.txt
local_sol_living_standard          = { decimals = 2  game_data = { category = location } }  # 固定值，每千人每年
local_sol_living_standard_modifier = { percent = yes game_data = { category = location } }  # 百分比
global_sol_living_standard         = { decimals = 2  game_data = { category = country } }
global_sol_living_standard_modifier= { percent = yes game_data = { category = country } }
# 按阶层（决策 2）：local_/global_<estate>_sol_living_standard[_modifier]
#   estate = nobles clergy burghers commoners tribesmen
```

命名沿用原版习惯：不带后缀的是数值，带 `_modifier` 的是百分比，例如原版的 `local_population_capacity` 和
`local_population_capacity_modifier`。

只做全体时共 4 个类型，按阶层分时共 24 个。每个类型都要配中英本地化和 `modifier_icons` 条目。

### 3.2 钩子和计算

阶层总量已改为下面的形式，只多一个乘数，不新增除法（第一批仅接入全体本地修正）：

```
sol_location_<e>_sol_total = max(0, 固定值ₑ × 人口ₑ + max(0, 1 + 百分比ₑ) × 资金ₑ × 12)

固定值ₑ = modifier:local_<e>_sol_living_standard + owner.modifier:global_<e>_sol_living_standard
        + modifier:local_sol_living_standard     + owner.modifier:global_sol_living_standard
百分比ₑ = 对应 4 个 _modifier 之和
```

现有钩子 `sol_location_<e>_local_sol_modifier_value` 是固定值钩子，新增 `sol_location_<e>_local_sol_percent_value`。
两者都由 `sol_living_standard_source.py` 生成。

第一批仅定义 `local_sol_living_standard` 和 `local_sol_living_standard_modifier` 两个全体本地类型。
全体钩子分别读取 `modifier:local_sol_living_standard` 和 `modifier:local_sol_living_standard_modifier`，
五个阶层各自的固定值与百分比钩子默认引用全体钩子。上面的 global / 按阶层原生类型是后续设计，尚未注册。

计算量方面，不新增遍历，也不新增缓存。每个地点的每个阶层多读几个修正值，多做一次乘法。
刷新节奏不变：人类玩家每月一次，AI 按求解节奏。新建成的建筑最晚在下一次刷新时生效。

### 3.3 依据（Step 3）

| 环节 | 依据 |
|---|---|
| 自定义地点修正类型 | `reference_mods/3613232232/main_menu/common/modifier_type_definitions/pp_farming_capacity_modifier_types.txt:4` `farm_capacity_from_irrigation_systems = { decimals = 2 game_data = { category = location } }` |
| 建筑挂自定义修正 | `reference_mods/3613232232/in_game/common/building_types/zz_pp_bund.txt:6-7` `raw_modifier = { farm_capacity_from_bund = 0.60 }` |
| 脚本值读自定义修正 | `reference_mods/3613232232/in_game/common/script_values/pp_farming_capacity.txt:70` `value = modifier:farm_capacity_from_bund` |
| 地点作用域读本地与所有者修正 | 原版 `in_game/common/script_values/building_caps.txt:273` `add = owner.modifier:market_building_levels`；`:283` `value = modifier:local_market_upgrade_building_levels` |
| 数值 / 百分比修正类型的写法 | 原版 `main_menu/common/modifier_type_definitions/00_modifier_types.txt:5535` `local_population_growth={ percent=yes ... }` |
| 建筑 `modifier` 随等级叠加，`raw_modifier` 不叠加 | 原版 `building_types/readme.txt:34-35` |
| 向已有建筑追加 `modifier` 块 | `reference_mods/3613232232/in_game/common/building_types/zz_pp_aqueduct_system.txt:2,10` |
| 向引擎按比例缩放的静态修正注入 | `reference_mods/3613232232/in_game/common/static_modifiers/pp_population_growth_and_food_adjustments.txt:5` `TRY_INJECT:prosperity`；缩放说明见原版 `static_modifiers/location.txt:386` "multiplies with devastation in location (0 to -1)"、`:407`、`:518` "multiplied with 1-control" |
| 向疾病地点修正注入 | `reference_mods/3613232232/in_game/common/diseases/pp_disease_migration_adjustments.txt:1-5` |
| 向特权、社会价值注入 | `reference_mods/3613232232/in_game/common/estate_privileges/pp_rgo_building_cost_redirects.txt:6`；`.../societal_values/pp_societal_value_adjustments.txt:2` |
| 新修正类型的配套要求 | 项目 BRIEF：每个新类型需要 `MODIFIER_TYPE_NAME_/DESC_` 中英本地化，以及 `main_menu/common/modifier_icons` 同名条目 |

以下三点需要进游戏确认：

- 读出的自定义修正值是否已含建筑等级。PP 的用法表明是这样。
- 社会价值的 `left_modifier` / `right_modifier` 是否按滑块位置缩放。
- 原版提示里两行的显示措辞。

## 4. 来源清单（初值，按 2.1 节原则分配）

固定值的单位是每千人每年。量级可参考旧观察局 c681faf6 的平民平均：1340 年 0.07，1500 年 0.36，1800 年 1.5。
贫困线是 0.1。负的固定值会把穷地方压到 0（封底），这正是它要表达的效果：瘟疫、战乱首先压垮穷人。

### 4.1 固定值来源（生存层面）

**医疗与清洁水**

| 来源 | 固定值 | 说明 |
|---|---|---|
| hospital 医院 | +0.05 | 1 级，城镇及以上 |
| lazaretto 隔离院 | +0.03 | 1 级 |
| pest_house 疫病收容所 | +0.03 | 农村也能建 |
| aqueduct_system 引水渠 | 每级 +0.02 | |
| darussifa / charite_of_berlin / magistrato_alla_sanita | +0.08 / +0.06 / +0.06 | 慈善医院性质的名胜 |

**污染和恶劣环境**（穷人住在下风口）

| 来源 | 固定值 | 说明 |
|---|---|---|
| 制革 tanning_workshop / tannery_manufactory / tannery_mill | 每级 −0.01 / −0.02 / −0.03 | |
| 硝石腐熟场 putrefaction_works / putrefaction_mill | 每级 −0.02 / −0.03 | |
| 工厂 textile_mill / iron_mill / steel_mill | 每级 −0.02 | |
| slave_market 奴隶市场 | −0.03 | |

**战乱、失序和拥挤**（注入引擎按比例缩放的静态修正）

| 来源 | 固定值 | 引擎缩放方式 |
|---|---|---|
| devastation 荒废 | 满荒废 −0.3 | 乘以荒废度（0 到 −1），所以定义里写 **+0.3** |
| inverse_control 低控制 | 零控制 −0.05 | 乘以（1 − 控制度） |
| overpopulation 人口过剩 | −0.05 | 按超出容量的程度 |
| is_occupied 被占领 | −0.05 | 开关 |
| under_siege 被围城 | −0.1 | 开关 |
| looted 被劫掠 | −0.1 | 开关 |
| recently_raided_by_horde 遭游牧劫掠 | −0.05 | 开关 |

**疾病**（注入疾病的地点修正）

| 疾病 | 固定值 |
|---|---|
| great_pestilence 大瘟疫 | −0.5 |
| bubonic_plague / egyptian_plague 鼠疫 | −0.3 |
| smallpox 天花 | −0.15 |
| typhus 斑疹伤寒 | −0.1 |
| measles 麻疹 | −0.05 |
| influenza / malaria | −0.03 |

**基本自由与生计**（国家修正，走 `global_*`，只给平民，需要按阶层分）

| 来源 | 固定值 | 说明 |
|---|---|---|
| no_labor_sunday 礼拜日休息 | 平民 +0.03 | 原版同时让原产地产出 −5%：钱少了，日子好了 |
| peasants_free_peasantry 自由农民 | 平民 +0.03 | |
| communal_lands 公地 | 平民 +0.02 | 生计兜底 |
| serfdom_vs_free_subjects 农奴制 ↔ 自由臣民 | 平民 −0.04 / +0.04 | 需先确认滑块是否缩放 |
| festival_grounds 节庆场 | 平民 +0.02 | |

### 4.2 百分比来源（品质层面）

| 来源 | 百分比 | 说明 |
|---|---|---|
| prosperity 繁荣 | 满繁荣 +10% | 乘以繁荣度（0–1） |
| medical_school 医学院 | +3% | 受过训练的医生，主要服务有钱人 |
| theater 剧院 / opera_house 歌剧院 / library 图书馆 | +2% / +3% / +1% | |

### 4.3 待补的百分比来源

按原则，百分比来源应该是有余力的人才享用得到的东西。现在这一类偏少，后续可以考虑：

- 贵族、市民专属的享乐建筑，比如 royal_garden，按阶层加百分比；
- 艺术品，原版的 location_art（"multiplied by total share of art"）；
- 品质类事件修正。

### 4.4 暂不做

- 事件修正（rampant_crime、chk_river_water_polluted、almoners_almshouses_modifier 等），框架上线后按同一原则逐个加。
- 首都、市场中心、发展度：它们和钱高度相关，再加修正就是重复计算。

### 4.5 第一批（已实现，只做无争议项）

入选条件有三条：不依赖待定决策（不需要按阶层分，不和原版移民、增长重复）；不依赖未验证的引擎缩放；语义没有疑问。
第一批只是在建筑上挂修正，所以只需要两个全体修正类型：`local_sol_living_standard` 和 `local_sol_living_standard_modifier`。
以下均经最小 `TRY_INJECT:<building> = { modifier = { ... } }` 增量注入，不覆盖建筑原有属性。
按原版 `building_types/readme.txt:34`，所有数值随建筑等级和商品供给缩放；一层建筑表中数值是完整供给时的值。

| 建筑 | 修正 |
|---|---|
| hospital 医院 | +0.05 |
| lazaretto 隔离院 | +0.03 |
| pest_house 疫病收容所 | +0.03 |
| aqueduct_system 引水渠 | 每级 +0.02 |
| darussifa / charite_of_berlin / magistrato_alla_sanita | +0.08 / +0.06 / +0.06 |
| tanning_workshop / tannery_manufactory / tannery_mill 制革 | 每级 −0.01 / −0.02 / −0.03 |
| putrefaction_works / putrefaction_mill 硝石腐熟场 | 每级 −0.02 / −0.03 |
| iron_mill / steel_mill 冶铁、炼钢厂 | 每级 −0.02 |
| theater / opera_house / library 剧院、歌剧院、图书馆 | +2% / +3% / +1% |

暂缓项及原因：

| 暂缓项 | 原因 |
|---|---|
| 繁荣、荒废、占领、围城、劫掠、疾病 | 原版已经影响移民和增长（决策 3） |
| 制度、节庆场 | 只给平民，需要按阶层分（决策 2） |
| 农奴制滑块、低控制、人口过剩 | 引擎缩放方式未确认 |
| 医学院 | 归固定值还是百分比有分歧 |
| textile_mill 纺织厂 | 问题是劳动条件，不是环境污染 |
| slave_market 奴隶市场 | 对当地自由人的生活水平影响存疑 |

## 5. 兼容性与风险

- **与原版重复。** 繁荣、荒废、占领、瘟疫在原版里本来就影响移民和增长。
  固定值只在穷地方明显，百分比只有百分之几到十，经现有反馈换算后，对移民和增长的影响远小于原版本身，主要体现在排行和观感上。
- **PP。** PP 也注入了 prosperity、looted、is_occupied 和疾病，但注入的是不同字段，可以共存。
  静态修正的数值字段在多次注入时相加（BRIEF）。
- **封底。** 钱的部分最低为 0，阶层合计最低为 0（现有规则）。
- **部落民。** 照常享受地点修正。

## 6. 后续批次待定项（不阻塞第一批）

1. **公式**：按第 2 节"固定值 + (1 + 百分比) × x"。已由用户给出。
2. **要不要分阶层**：只做全体时，礼拜日休息、节庆场这类只该给平民的来源做不了。推荐分阶层。
3. **原版已影响移民、增长的来源（繁荣、荒废、占领、瘟疫）要不要加**：推荐加。
4. **范围与数值**：当前按第 4.5 节 17 种建筑及其数值实现；其他来源保留为候选，不能将本节较早的推荐视为已实现范围。

## 7. 实现与验收

已完成第一批：来源表 `BUILDING_SOURCES`、两个修正类型、同名图标映射、中英名称和公式说明，
以及固定值 / 百分比计算钩子，均由 `scripts/sol_living_standard_source.py` 声明。
`scripts/gen_sol_economy_effects.py` 为 stable / sol_standalone 生成以下新增文件，PP / M&T / JTG 通过 SOL 依赖继承：

- `main_menu/common/modifier_type_definitions/SOL_living_standard_modifier_types.txt`
- `main_menu/common/modifier_icons/SOL_living_standard_modifier_icons.txt`
- `in_game/common/building_types/SOL_living_standard_buildings.txt`
- `main_menu/localization/<language>/SOL_living_standard_modifier_types_l_<language>.yml`

顶栏中英公式说明同步更新。没有新增遍历、缓存或刷新入口；购买力和需求路径不读这两个类型。
离线测试覆盖 1.25 算例、多个百分比相加、乘数与结果封底、固定值不被百分比放大、
五阶层钩子、混合建筑来源、人口加权、移民反馈与五个部署目标的需求隔离。
原生建筑来源提示、等级 / 供给缩放和实际移民 / 增长结算仍需进游戏验收。

后续扩展仍按以下步骤，但不得自动启用暂缓来源：

1. 在 `sol_living_standard_source.py` 中声明修正类型表和来源表。生成以下内容：
   - 修正类型定义、图标、中英本地化；
   - 建筑、静态修正、疾病、特权、社会价值的 `TRY_INJECT` 文件；
   - 固定值和百分比两个钩子。
2. 改 `sol_compute_location_living_standard` 的阶层总量公式（第 3.2 节）。
3. 测试：
   - 以 x = 1.0、固定 +0.2、+5% 为例，得到 1.25；
   - 百分比低于 −100% 时，钱的部分按 0 算；
   - 修正不为 0 时购买力和需求输入不变；
   - 荒废的符号正确；
   - 按阶层的修正只作用于目标阶层；
   - 五个部署目标的生成结果一致。
4. 进游戏验收：
   - 提示中能看到来源；
   - 数值按公式变化；
   - 确认第 3.3 节末尾的三点。
5. 补知识记录：自定义修正类型可以经 `modifier:` 在脚本值中读出。

## 8. 本次验证记录（2026-10-23）

- `scripts/test_sol_living_standard.py`：23 项通过，包含五个部署目标的源文件隔离检查。
- `gen_sol_economy_effects.py --target all --check`、`gen_sol_lshud.py --target all --check`、PP / JTG 兼容生成检查通过。
- `validate.py --changed`：20 个改动模组文件通过；`test_validate.py`：4 项通过。
- 共享与本地知识、枚举、路由、迁移覆盖校验通过，BRIEF 和索引已重建。
- `unittest discover -s scripts -p test_sol_*.py` 共运行 138 项；生活水平、排行、地图和顶栏双语渲染通过。
  失败仅为同一市场提示保真测试在 stable / standalone 的两个子项：共享原版镜像已改用
  `Merchant.GetProjectedTradeProfit` 和新的分商品提示，现有产物仍是 `GetTotalTradeProfit`。
  两个产物均与本次修改前的 Git HEAD 一致，属于已有生成差异，本次保留原状。
- 全量 `gen_sol_chain.py --target all --check` 在上述市场提示差异处停止。
  M&T 单独生成检查另有已有的骆驼地区差异（`mongolia_region` / `xinjiang_region`）；
  其余 M&T 产物通过。本次 M&T 商品文件与 HEAD 逐字节一致，未将地区变更混入生活水平功能。
- 未启动游戏；原生建筑提示、等级与供给缩放、移民流动和人口增长实际结算仍待实机验收。
