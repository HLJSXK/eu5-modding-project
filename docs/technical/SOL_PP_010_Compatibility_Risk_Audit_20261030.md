# SOL 与 Prosper or Perish 0.10 兼容风险审计

日期：2026-10-30。结论：**旧兼容补丁不能直接当作 PP 0.10 的兼容层发布；需要重新确认经济、界面和人口反馈的归属。** 已完成文件全量清单、结构化对象交集、旧版差异、需求离线核算及重点调用链检查。本轮只建立讨论依据，没有修改模组、生成器或共享参考库，没有启动游戏、部署或发布。

## 审计基线与覆盖范围

| 标记 | 本轮实际读取的来源 |
| --- | --- |
| S | 当前仓库 `beta`，提交 `efb5a96d`，`src/stable`；这里的目录名 stable 不代表 main 分支的旧算法 |
| C | `src/sol_pp_compatibility_submod`，metadata 版本 261024，依赖完整 SOL |
| O | `.eu5-base/reference_mods/3613232232`，实际 metadata 为 PP 0.9.1、EU5 1.3.11；旧报告所写 0.9.0 不再准确 |
| P | 父目录 `prosper-or-perish-upstream`，提交 `967cadbe`；可部署内容为 `mod/Prosper or Perish (Population Growth & Food Rework)`，PP 0.10.0 |
| 辅助 | SOL standalone；PP 仓库中的独立 Seasonal Harvests；共享参考中的 CMF 2.5.0、Glorp UI、Construction Manager 2.2.11 |

P 包含本地保留的简体中文翻译。本文判断的是上述工作区快照，不把它等同于未来 Workshop 版本。PP 的 0.10 发布文案指定 EU5 **1.4.5**，并明确声明**不兼容旧存档**（`docs/release/0.10/github_release.md:5-7`）。双方 metadata 的 `1.4.*` 不能代替具体游戏构建验证。

扫描先逐文件记录 SHA-256，再对 common、events、GUI 和地图模式文本使用共享结构解析器建立顶层对象表，对本地化读取语言及键；随后对交集、需求来源和生成链作人工检查。所有这些已解析文件均未触发结构解析异常，这不等于游戏语义验证。地图二进制和纹理只做路径及字节清单；setup 与地图结构变化结合构造器配置检查，没有执行地图加载或新开局模拟。

PP 构造器使用的三个 editable 兄弟依赖没有出现在当前父目录，且其 AGENTS 要求 Windows 镜像只用于读取。因此没有运行其 build/sync 工作流；本轮使用本项目已有解析器检查实际交付目录。无需为完成静态审计写入上游。

| 文件清单 | 数量 |
| --- | ---: |
| SOL 完整版 | 115 |
| SOL standalone | 90 |
| 旧 PP 兼容子模 | 18 |
| 旧 PP 快照 | 994 |
| PP 0.10 主模组 | 2,042 |
| 独立 Seasonal Harvests | 42 |
| 旧 PP → 新 PP 新增 / 修改 / 删除 / 逐字节不变 | 1,293 / 638 / 245 / 111 |

这些数字含资源和 metadata，不是脚本改动数。S 与 P 的同名对象候选包括 17 个建筑、55 个商品、13 个 static modifier、5 个价格、3 个 on_action、1 个 define 分组和 98 个 GUI 项。**候选不等于冲突**：`namespace` 声明、不同局势文件中名为 `situation_panel` 的根控件不是全局同 ID 冲突；大量 GUI 项属于同路径整文件覆盖；同名 NPop 分组没有相同的直接 define 键。

## 必须解决的技术项目

### R01 旧生成器与测试没有覆盖新版输入

**确定，高优先级。** `scripts/gen_sol_pp_compat.py:44-48` 仍固定读取 O，只专门读取 victuals、lumber 调整与道路价格文件。它不读新版的 `goods_demand`、新增消费商品、建筑替换和 PP 地点界面。

本轮得到两项可复现结果：

- 现有 `gen_sol_pp_compat.py --check` 的 15 个输出全部通过。
- 仅在内存中把三处 PP 输入路径改为 P，再调用 `_render_outputs()`，**15 个输出仍全部与旧版一致**；没有写回生成文件。

因此“更新路径后生成成功”不足以验收。本轮已有的实际需求差异不会让这项检查失败。后续要固定上游提交与游戏构建，补充全栈解析断言、需求模板和建筑/UI 的测试输入；共享 0.9.1 参考不能被静默覆盖后继续沿用旧结论。

证据：审计附件 `check_demand.py`、`demand_checks.json`；`scripts/test_sol_slave_demand.py:83` 的 PP 测试也只加载旧 victuals 与 goods_adjustments，未加载完整 PP 文件覆盖和需求模板。

### R02 原生需求模板已与 SOL 记账分离

**确定，高优先级。** P 的 `in_game/common/goods_demand/pp_new_goods_demands.txt:7` 改为完整 `REPLACE:pop_demand`。当前 C 没有对应处理，SOL 的单位消费常数和替代篮子仍由自己的 CSV 生成。

| 商品 | 原版模板值 | PP 0.10 模板值 |
| --- | ---: | ---: |
| 盐 | 1 | 0.33 |
| 茶 | 1 | 0.6 |
| 可可 | 1 | 0.7 |
| 马、骆驼 | 1 | 0.7 |
| 马铃薯、玉米、小米、野味、鱼、豆类、橄榄、牲畜、稻米 | 1 | 0.7 |
| 小麦 | 0.75 | 0.53 |
| 水果 | 0.5 | 0.35 |

共 16 种商品的模板系数相对原版改变。小麦和水果在原版已存在记账遗漏，本轮不把全部偏差归因于 PP；PP 又改变了这些系数。最终还会叠加人口、文化、宗教和地区因素，不能将本表直接当作每个 POP 的最终需求。

需要讨论：由 SOL 接管数量并中和 PP 模板，还是保留 PP 倍率并让 SOL 的基准支出、订阅、替代权重和校准同步读取它。不能只改实际需求或只改界面数字，也不能通过注入另一份 `pop_demand` 猜测深层合并。

### R03 丝绸已产生真实人口需求但完全缺席 SOL 篮子

**确定，高优先级。** P 的 `in_game/common/goods/pp_goods_adjustments.txt:257` 为丝绸增加贵族 0.08、教士 0.006、市民 0.004 的基础需求；需求模板把 silk 加入，欧洲还有 1.25 地区因子。

当前 `data/demand_price_table.csv`、`data/goods_weights.csv`、`data/pop_group_baskets.csv` 没有 silk。C 仅补 victuals，未把丝绸加入消费常数、市场遍历、国家求解、商品组、UI 或外部需求读取。离线加载新版商品完整文件后，**基础加法/乘法需求相对旧组合唯一的非零差异就是丝绸**，见 `demand_checks.json`。

不能因为 silk 已是游戏中的商品，就认为 SOL 会自动计入。需决定加入哪个消费组及哪些阶层、作为中性额外消费，或取消 PP 新增的人口需求；这是功能选择，不能在修兼容时偷偷删掉。

### R04 商品条件和国家需求修正需要分层处理

**部分已覆盖，部分明确遗漏。** P 为 fur 改写冬季、气候、市场不可得因子（`pp_goods_adjustments.txt:18-34`），前三时代再增加皮毛需求（`in_game/common/age/pp_age_adjustments.txt`）；`societal_values/pp_societal_value_adjustments.txt:89-134` 为外向/内向社会价值增加多种商品的需求变化，包括丝绸。

当前 `C_SOL_substitution.txt:985,1219` 确实会读取核心商品的 `global_fur_pop_demand`、`global_wine_pop_demand` 等外部国家修正，不能宣称这些全部丢失。但它不能补足未纳入商品表的 silk，也不能把逐 POP 的气候、地区、文化和宗教条件自动变成正确的统一国家篮子。

此项目应与已有 `SOL_Native_Pop_Demand_Audit_20261027.md` 合并确定边界：哪些效果迁移成偏好，哪些仍影响总预算，哪些保留原生并在记账中体现。国家近似不能宣称精确保存逐人口禁忌。

### R05 地点窗口整文件互斥

**确定，高优先级。** S 与 P 同时提供 `in_game/gui/location_window.gui`，内容不同。当前 C 没有第三份合并窗口。

- 按旧约定 PP → 完整 SOL → C，SOL 的 Glorp 基底窗口生效，PP 的储粮状态、土地用量/容量、农场用地、生产及回本信息会失去该窗口入口。
- 交换 PP 与 SOL 顺序，会让 PP 窗口生效，SOL 的地点生活水平按钮和其 Glorp/可选 Construction Manager 集成需要另行接回。

证据：P 窗口中的 `pp_location_status_row`、土地面板与 `pp_location_building_rows`；S 窗口为 `scripts/sync_location_window.py` 生成。**调整加载顺序不能让两个完整窗口自动合并。** 建议讨论以 PP 0.10 窗口为兼容目标的基底，再加入 SOL 入口；是否同时保留完整 Glorp 和 Construction Manager 功能须列入范围。

### R06 市场提示框覆盖会暴露内部商品或丢掉 SOL 提示

**确定，高优先级。** 第二处实际同路径覆盖为 `in_game/gui/shared/market_tooltips.gui`。S 的版本加入 SOL 市场价格与替代组提示；P 的版本配合 `shared/pp_internal_goods.gui` 过滤内部商品，并调整前五项列表的取数与布局。

SOL 后加载会撤掉 PP 在此文件中的隐藏处理；PP 后加载则撤掉 SOL 在此文件中的提示扩展。受影响的是这个提示框文件，不能误报 PP 所有市场列表隐藏均消失。P 仍有其他独立市场、账本和交易界面。

PP 当前隐藏列表是 offset、logistics、local_food、province_food_sales。manual_labor 虽是内部经济商品，但不在这份隐藏列表中；不能擅自把它一并隐藏或加入 POP 消费。

### R07 九项建筑生活水平效果被整体替换抹掉

**按已记录的数据库加载规则确定，高优先级。** S 的 `in_game/common/building_types/SOL_living_standard_buildings.txt` 对 17 个建筑写入 `TRY_INJECT`。P 对以下 9 项使用之后处理的 `REPLACE`，且其定义未包含 SOL 修正：

| 建筑 | 被抹掉的 SOL 效果 |
| --- | --- |
| lazaretto | 固定生活水平 +0.03 |
| library | 生活水平比例 +1% |
| tanning_workshop | 固定生活水平 −0.01 |
| tannery_manufactory | −0.02 |
| tannery_mill | −0.03 |
| putrefaction_works | −0.02 |
| putrefaction_mill | −0.03 |
| iron_mill | −0.02 |
| steel_mill | −0.02 |

证据：P 的 `pp_culture_building_adjustments.txt:3`、`zzzz_pp_water_access_buildings.txt:258` 及相应 `zz_pp_<建筑>.txt:2`。文件名改成更晚的 `zz_` 不能让 `TRY_INJECT` 越过 `REPLACE` 阶段。

其余 8 项没有发现这类整体替换损失，但 aqueduct_system 双方均有 modifier 块，仍应验证最终组合。修复时必须保留 PP 的生产方法、工人、土地、升级与建造条件，不能用原版建筑整块覆盖 PP。还要决定 PP 新增的清洁、医疗、污染建筑是否纳入 SOL，而不是只补回旧的 17 项。

## 需要讨论归属的玩法项目

### R08 储粮和 SOL 同时驱动增长与迁移

**确定会叠加，平衡后果需要实测。** PP 关闭原生储粮/盈余增长 define，用 `pp_food_store_0..24` 的省修正和人口/土地规则接管；SOL 当前额外按本地 SOL 值给迁移吸引力，上限 +0.5；低于 0.1 SOL 时人口增长 −0.001，高于 10 时 +0.001。

这些 SOL 效果由 C 继承，并没有被旧 Compact 清理。富裕但缺粮的地点、贫穷但储粮充足的地点，可能收到不同方向的信号。需决定保留叠加、以储粮/饥荒作门槛、削弱，或交由 PP 独占增长而只保留 SOL 迁移。

证据：S `SOL_living_standard_modifiers.txt:6-15`、`scripts/sol_living_standard_source.py:139`；P `loading_screen/common/defines/pp_defines_adjustments.txt` 的 NPop、`in_game/common/static_modifiers/pp_stored_food.txt`。PP 部分注释仍描述旧的连续 size 实现，实际交付文件已是逐月储粮档位；应以效果代码为准。

### R09 土地容量与 GDP 发展度形成新的反馈链

**功能选择，高优先级。** PP 0.10 的容量已是自然土地、改良、发展度、城镇人口、自给农民占地和农场占地的组合。`total_population` 在 P 中新增 `local_population_capacity = 1`，配合每年更新的 `pp_subsistence_land`；发展度本身参与可耕地及改良上限计算。

旧矩阵写“GDP→发展度硬关闭”，但当前 C 的 `zz_SOL_PP_compact_disabled_triggers.txt:4` 和 CMF 注册保留 `pp_gdp_dev` 默认关闭的主动开启选项。打开后，经济增长可能通过发展度扩大土地/建筑空间，再推动生产和收入。这是明确可达的模式，不应被旧说明遮蔽。

需要决定该开关继续存在、禁用，还是针对 PP 改为有上限/不同来源的增长。默认关闭与开启分别验收；开启测试还必须检查农场上限、在建占地、年度自给土地刷新。

### R10 SOL 收入代理与 PP 新经济模型的适用性

**模型风险，尚不能据此判定数值错误。** SOL 使用地点税基、控制、阶层份额、税率和现金储备近似可消费收入（`SOL_pop_values.txt:246-307`）。PP 重做劳动商品、建筑雇佣、生产方法、劳动力成本、物流、贸易价格与阶层权力，改变这些代理量对应的实际经济活动。

已有的阶层建筑计数使用 `every_buildings_in_location` 和 `estate_type`，不是静态建筑白名单，因此不能笼统认定 PP 新建筑漏算。但 `A_SOL_economy_effects.txt:163-198` 仍假定每个阶层建筑 1 金维护；需要拿 PP 实际维护与收入账本核对。0.10 的生产方法投入不等同于可直接叠加给 POP 的工资，不能把 manual_labor 销售额擅自再算一次。

建议使用新开局农村、粮食省会、工业城市、低控制地区及不同社会价值国家做账本比对，再决定是否重校准七类人口篮子。

### R11 保留的反滚雪球规则会改变 PP 建筑与 AI 节奏

**确定叠加，是否保留待决定。** C 仍保留基础税效率、低控制建筑效率惩罚、时代建筑效率/城镇升级费用、难度、外交/稳定度等。后期时代建筑效率可达 −1，城市/城镇升级费用 +0.5；低控制另有 −0.5 建筑效率来源。

PP 的土地改良、粮食建筑、物流和制造升级依赖自己的费用、利润门槛与 AI 权重。组合后可能显著改变基础建设与饥荒应对速度，但不能仅凭静态系数断言 AI 一定失效。应把这些开关逐项归属，至少区分“SOL 核心需求层”和“额外平衡规则层”。

### R12 战争和灾害清理中既有可复用部分也有剩余叠加

**已核实，不需要全部推倒。** C 对 location_base_values、winter_mild/normal、八项 LIA 修正及四项战争地点修正做反向注入。被双方同时调整的这些对象在 P 中仍为注入路径，SOL 与 C 的相反 delta 可以抵消；PP 的 total_population 与 raised_levies 仍用 `TRY_REPLACE` 接管，旧兼容原则仍成立。

但 C 不会清除 SOL 的 hostile_troops、recently_raided_by_horde、recently_razed，以及战损厌战、首都/全国占领压力和战时内阁限制。PP 自己调整了粮库被占损失、围城产出、AI 战争热情、无堡围城时间等。需逐项决定是否保留 SOL 加重效果，不能把“没有同 key 冲突”解释为战争平衡一致。

另需核对 AI 灾难恢复开关：PP 改变了 devastation 的含义和伴随效果，SOL 的恢复加速虽然能加载，影响已不同于原版。

### R13 价格归属基本可沿用但要更新数值和边界

**未发现需要重新抵消的硬冲突。** 五个价格交集仍是四条道路和 embrace_institution。P 道路 gold 为 45、240、450、1300；它们在同类型注入内晚于 SOL，按已知标量规则覆盖 SOL。机构价格由 P 的 `TRY_REPLACE` 接管。

不应使用负价格注入“抵消”。其他 SOL 价格继续存在，但 P 对探索维护、招募探险家等有独立效率修正，所以“价格 key 无交集”仍可能出现最终费用叠加。需确认道路/机构归 PP、其余价格是否继续保留旧 Compact 约定。

### R14 殖民门槛存在明确的机制方向冲突

**确定存在双重门槛。** PP 将 AI 殖民税基 define 降到 60，探索脚本税基降到 20；其说明指出 PP 经济税基较低，需要避免殖民延迟。SOL 的 `A_SOL_economy_generic_actions.txt:87` 在反滚雪球开启时，仍为非例外国家保留 `country_tax_base > 500` 的行动权重条件，另有历史国家和殖民地例外。

因此即使双方没有同名行动对象交集，SOL 仍可能抵消 PP 降门槛的目的。应讨论保留名单式限制、采用 PP 门槛或单独配置。

`ai_country_should_colonize` 已在官方 `triggers.log:85` 列为原生 trigger；不能因 PP 注释写“移除 scripted trigger”就误报当前调用未定义。

### R15 新地图与旧存档不能靠小补丁迁移

**上游明确不兼容旧档。** PP 0.10 重做地形、气候、土壤/肥力、河流、可航行水道、原料布置、初始建筑和发展度 setup，并删除 farming_village。SOL 没有同路径地图资产冲突，核心遍历主要按地点/国家进行；主要风险是上游世界状态本身变更，以及 SOL 的基于人口、GDP、市场的缓存与新布局失配。

建议把本兼容项目的首个验收目标限定为 PP 0.10 新开局。0.9 存档升级是另一个工程，不能因为旧 C 的开关回调能清变量就宣布地图/建筑/人口已迁移。0.10 同版本存档中启停 SOL 仍需独立检查初始化、月度结果、年度排名及停用清理。

## 依赖 生命周期与验收风险

### R16 CMF 与可选 UI 模组扩大组合范围

C 目前只声明 `hades.sol` 依赖，没有声明 P 新的 `prosperorperish` ID；完整 SOL 依赖 CMF 2.*。这使错误组合和加载顺序难以从 metadata 发现。已有 C 明确面向完整 SOL，不能顺手声称支持 standalone。

CMF、Glorp、Construction Manager 的参考快照与 P 已另做路径/对象交集扫描，完整候选保存在 `dependencies.json.gz`。其中 CMF 有 **9 个内容不同的同名 type/template**，涉及地点卡片、城镇权利、建筑行和省粮食显示，例如 `location_card_core`、`town_rights_type_item`、`food_production_province`。这些定义位于 CMF 的 `gui/vanilla/` 文件中，不能只合并同路径主窗口就视为解决。

Glorp 同样覆盖 location_window；Construction Manager 同时覆盖 location_window 与 **building_view.gui**，还重声明 build_location_entry、粮食生产等组件。它对 rgo_level 的 `INJECT:cm_rgo_level` 则晚于 PP 的 TRY_REPLACE 阶段，不能误判为必然被抹除。候选里的原版 type 重声明不都构成故障，须按最终可见窗口和模板解析确认。建议支持矩阵分为“PP + CMF + 完整 SOL + 新兼容层”核心，以及 Glorp/Construction Manager 可选组合，避免把可选组件日志与本体错误混为一谈。

Construction Manager 还有独立的玩法兼容问题：参考快照的 `in_game/common/scripted_effects/cm_food_auto_build_effects.txt:43,54` 仍评估并建造 `building_type:farming_village`，而 P 的 `constructor.toml:248` 明确从原版建筑文件中删除该对象。自动粮食建设不能只靠合并 UI 就宣称支持；需移植到 PP 农场/粮食建筑模型，或明确限制该功能。是否启用会影响触发路径，实际报错时机需要运行确认。

### R17 月度 年度与开局回调可合并但要验证时序

双方共有 on_game_start、monthly_country_pulse、yearly_country_pulse，均使用 on_actions 分派，没有发现互相整块替换的独立 SOL/PP 脚本效果或触发器。当前 S/P 也没有本地化键交集，SOL/PP 自有变量与对象命名空间基本分离。

这降低了直接覆盖风险，但不保证联合时序正确。PP 月度更新储粮、年度更新自给土地；SOL 人类月度/AI 年度计算及月度应用 modifier，可能观察不同月份的价格、人口和库存。共享回调列表中的随机 delay、开局先后、征服/失去地点、市场变化后的缓存，应在游戏里验证。性能验收需测大国和后期，不能把上游单模组 profiler 的结果直接当作组合结果。

### R18 独立 Seasonal Harvests 不能当作主模组的默认额外依赖

P 已包含收成系统。同仓库的独立版本 README 称可一起加载，本轮确认共同的收成游戏脚本逐字节一致。本地 42 个文件中，26 个与主模组同路径内容一致，其余是 metadata、说明和本地化差异，具体列表见依赖附件。

因此本次默认兼容对象应是 PP 主模组，不需要另加独立 Seasonal Harvests。若用户另有双开需求，应检查同名本地化的最终文本；当前没有证据把它列成收成脚本重复执行故障。

## 已核实可以复用的部分

| 项目 | 本轮结果与边界 |
| --- | --- |
| lumber 人口消费清零 | 完整 PP 新商品文件叠加 S/C 后，八类人口的基础数量均为零 |
| 奴隶商品需求 | 离线基础需求核算没有非零奴隶篮子；不等同于人口原生粮食消费归零 |
| victuals 数量 | 六类非零目标仍为 0.05 / 0.03 / 0.023 / 0.0016 / 0.0008 / 0.0016；tribesmen/slaves 为零 |
| victuals 价格变化 | 旧默认价 2.5，新为 3；当前运行时代码用 `default_price(goods:victuals)`，不能误报仍硬编码 2.5 |
| victuals 与粮食 | P 已将 food 改为 0，省份粮食由 local_food 等转换产生；保留 victuals 消费篮子不等于模拟了整个储粮链 |
| 内部商品 | local_food、offset、logistics、province_food_sales、manual_labor 没有因此自动需要成为 SOL 人口消费品 |
| 原始数量表 | 在仅考虑 goods 的基础 demand_add/multiply 层，新旧差异只有 silk；主要新偏差还在模板和条件层 |
| define | 同有 NPop 分组，但直接字段无重名；增长机制叠加属于另一层问题 |
| 脚本命名空间 | S/P 没有实际 scripted effects、scripted triggers、script values 的同名对象交集 |
| 旧清理策略 | 天气、LIA、地点基础与四种战争状态清理仍可复用，需用最终堆栈逐字段验收 |

## 建议的讨论顺序与项目边界

**第一轮：确定经济控制权。** 优先讨论 R02–R04：SOL 是否统一决定人口消费数量；PP 的需求倍率、丝绸、文化/地区和时代偏好如何保留。这个决定影响生成器、基准支出、求解器、替代组与界面，不宜拆成互不相关的小修补。

**第二轮：确定人口与发展反馈。** 讨论 R08–R10：增长和迁移归属、GDP→发展度、土地容量、收入账本及新篮子校准。先明确设计，再评估必要改码范围。

**第三轮：确定附加平衡规则。** 将 R11–R14 的税收、建筑费用、战争、灾难恢复、价格与殖民逐项标为保留、交给 PP 或独立开关。旧 Compact 不能直接充当新版本的已批准需求。

**第四轮：确定交付和支持矩阵。** 选择窗口基底、建筑效果范围、CMF/Glorp/Construction Manager 组合与新档边界；然后把 R01、R05–R07、R15–R18 拆成实施项目和验收条件。

技术上必需的结果是：引擎实际需求与 SOL 记账使用同一套已决定的语义；两个关键 GUI 文件都保留约定功能；建筑效果能跨 PP 替换存在；上游版本漂移会使检查明确失败。是否保留每项 SOL 平衡规则仍待讨论，本轮没有代替用户作决定。

## 后续验收清单

1. 固定 PP 提交、SOL 提交、EU5 精确构建和 DLC 状态；新开局测试，不混用 0.9 档。
2. 离线解析先处理同路径覆盖，再按数据库操作与字段语义合成；检查商品、需求模板、条件、17 项原建筑与新增建筑、天气/战争净 delta、defines、回调与本地化。
3. 游戏内对照原生 POP 需求 tooltip、市场实际需求与 SOL 支出；覆盖盐、茶、可可、小麦、水果、丝绸、fur、victuals、lumber、奴隶，及不同气候/文化/宗教/时代。
4. 覆盖储粮 0/12/24 月、饥荒、人口上限、SOL 高低边界、GDP 开关、征服、换市场与禁用 SOL；读取最终 modifier 来源与缓存状态。
5. 双语检查地点、土地、储粮、生产列表、市场提示、商品替代、HUD 和地图；按核心/可选 UI 组合分别验证。
6. 开局与后期分别检查 error.log 和 profiler；比较 PP 单开、核心兼容栈及可选 UI 栈，不以静态检查通过替代联合运行。

## 可复现附件

目录：`docs/analysis/pp_010_audit_20261030/`。

- `scan.py`：只读扫描六个来源，输出 SHA-256 文件清单、结构对象及差异。
- `summary.json`：规模、解析异常、同路径覆盖与对象候选数量。
- `file_changes.csv`：全部旧 PP→新 PP 路径变化。
- `symbol_changes.csv`：顶层对象变化候选；移除补丁对象不等于删除原版对象，须检查原版回退。
- `same_paths.csv`：同路径清单，含应排除的 metadata 项。
- `object_collisions.csv`：双方操作、来源路径、行号及直接字段交集；含需要人工排除的根控件/namespace 候选。
- `inventory.json.gz`：完整压缩清单；大块只保留结构哈希和直接子项数。不是可直接部署的合成游戏文件。
- `check_demand.py` / `demand_checks.json`：商品基础数量核算、奴隶/lumber/victuals 检查和生成器新旧输入盲测。
- `check_dependencies.py` / `dependencies.json.gz`：CMF、可选 UI 与 Seasonal Harvests 差异。

运行方式：在仓库根设置 `PYTHONUTF8=1`，依次用 `C:/Users/Hades/anaconda3/envs/eu5/python.exe` 执行上述三个 Python 文件。它们仅写自己的审计附件目录。扫描器不是完整引擎解释器，结构化同名清单需要结合本文的字段与机制判读。

本轮已阅读 PROJECT_OVERVIEW；新增内容仅位于 docs，现有功能未改变，因此无需更新项目功能概览或重新生成 BRIEF。
