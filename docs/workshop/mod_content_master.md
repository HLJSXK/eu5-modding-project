# Standard of Living (SOL) — Mod Content Master Reference

> **用途**：这是一份绝对全面的内容大全，供进一步创建工坊说明文档使用。
> 所有数值均直接来自代码，已标注来源文件。

---

## 一、概述（Overview）

### 模组定位

**Standard of Living（生活水准，缩写 SOL）** 是一个面向多人游戏的 EU5 平衡与经济深化模组，核心目标：

- 修正人口需求的固定性缺陷，引入真实的宏观经济动态
- 抑制强者滚雪球，让精密策略规划持续有价值
- 加重战争代价，避免无止境消耗战
- 保留原版游戏机制框架，不做颠覆性改动

### 继承关系

本模组是以下两个已停止更新的模组的延续开发：

1. **Standard of Living（旧 SOL 模组）** — 原始的生活水准需求系统框架
2. **Antisnowballing（AS 模组）** — 经济平衡与滚雪球抑制系统

本模组在两者基础上进行了整合、修正与大量优化，并持续维护更新。

### 涉及的修改范围

- `common/goods_demand/pop_demands.txt` — 核心：人口需求重写，引入 `gdp_per_capita_scale`
- `common/script_values/pop_wealth.txt` — SOL 全套计算逻辑（约 728 行）
- `common/script_values/standard_of_living.txt` — 情境面板展示变量
- `common/situations/standard_of_living.txt` — 生活水准全局情境（地图着色、面板）
- `common/auto_modifiers/` — 税收效率、外交支出、文化传统稳定、战争惩罚
- `main_menu/common/static_modifiers/` — 地点/省份/国家级修正重写
- `in_game/common/age/SOL_default.txt` — 时代递增建筑/食物消耗
- `in_game/common/prices/SOL_00_hardcoded.txt` — 道路价格、各类行动金币上限
- `in_game/common/cabinet_actions/SOL_reduce_war_exhaustion.txt` — 战时无法降低厌战度
- `in_game/common/generic_actions/SOL_colonial_charters.txt` — AI 殖民限制
- `main_menu/localization/` — 完整中英双语本地化

---

## 二、原版问题（Vanilla Problem）

### 需求固定性问题

EU5 原版中，人口的商品需求（`pop_demand`）完全固定，从 1337 年到 1836 年唯一变化的变量是 `development`（发展度），但发展度增长极为缓慢。这导致：

**问题一：宏观经济无深度**
- 国家经济几乎只有一条路：扩建原产地（RGO），从贸易网络获利
- 没有"藏富于民"的概念——阶层存款无限积累，与现实经济完全脱节
- 贵族/商人阶层可以无限积累存款，永不花出去（例：法兰西贵族存款滚到天文数字）

**问题二：生产过剩**
- EU5 建筑拥有极高的单位劳动力产出加成
- 全球几乎永远处于生产过剩状态，商品价格持续低迷
- 应对方式：大量建造终端消费建筑（政府建筑等）以消耗商品、拉升价格
- 本质上是从"虚空"（火星）凭空制造购买力，而非真实经济循环

**问题三：需求应动态响应收入**
- 14 世纪的农民与 18 世纪的商人，消费能力理应天差地别
- 原版对此无任何体现

---

## 三、核心系统：Standard of Living（Feature 1）

### 3.1 系统总览

SOL 系统通过一个三层叠加公式修正每个人口单位的商品需求乘数 `gdp_per_capita_scale`，该乘数作用于 `pop_demands.txt` 中所有商品的最终 `multiply`。

**公式结构（来源：`pop_wealth.txt`）**

```
gdp_per_capita_scale = 1
  + [层一：收入驱动的非线性需求偏移量]  (local_*_gdp_nonlinear_component)
  + [层二：存款压力修正量]              (local_*_savings_pressure)
  + [层三：制度加成]                    (num_embraced_institutions × 0.05)
```

最终值 ≥ 0（通过 `min` 限制），避免出现负需求。

---

### 3.2 层一：收入驱动的需求（Income-Driven Demand）

**来源文件**：`src/stable/in_game/common/script_values/pop_wealth.txt`

**核心思想**：根据每个地点每个阶层的"人均收入池"（即分配给该阶层的税基份额，经税率和控制力损耗计算），计算出 SOL 压力值，再通过非线性函数压平极端值。

**Step A：计算各阶层收入池**

- `local_*_income_pool = local_control_loss_component + local_*_taxed_component`
  - `local_control_loss_component`：因控制力不足损耗的部分（= tax_base / control - tax_base），代表实际流入民间的财富
  - `local_*_taxed_component`：阶层被征税后剩余的部分（= (1 - tax_rate) × tax_base）
- 各阶层税份额权重（`local_*_tax_share`）：
  - 贵族：每 pop × 150
  - 教士：每 pop × 25
  - 商人：每 pop × 20
  - 平民（劳工+农民+士兵）：每 pop × 1
  - 部落民：每 pop × 0.01

**Step B：计算人均 GDP**

- `local_*_gdp_display = income_pool × class_share / total_share`
- `local_*_gdp_per_capita_display = gdp_display / pop_count`

**Step C：计算 SOL 压力（线性部分）**

各阶层线性系数不同（反映阶层对收入变化的敏感度）：

| 阶层 | 公式 | 含义 |
|------|------|------|
| 贵族 | `gdp_per_capita × 0.05 - 0.3` | 贵族收入弹性低，门槛高 |
| 教士 | `gdp_per_capita × 0.15 - 0.2` | 中等弹性 |
| 商人 | `gdp_per_capita × 0.15 - 0.2` | 中等弹性 |
| 平民 | `gdp_per_capita × 1.5 - 0.1` | 平民收入弹性最高，即使微小收入也有影响 |
| 部落民 | `gdp_per_capita × 1.5 - 0.1` | 同平民 |

**Step D：非线性压缩（防止极端值）**

使用饱和函数，防止富裕地区无限放大需求：

```
nonlinear_component = sol_pressure / (1 + sol_pressure × 0.45)
                      （分母最小值 0.05，防止除零）
```

效果：压力越大，增量越小；负压力时需求适度压缩。

---

### 3.3 层二：存款压力修正（Savings Pressure）

**来源文件**：`pop_wealth.txt`（本地计算）、`standard_of_living_effects.txt`（国家缓存）

**核心思想**：当阶层存款高于"目标存款"时，增加需求；当存款低于目标时，减少需求。目标存款锚定于国家经济规模，随国家增长而增长。

**存款目标公式**（`gls_compute_panel_display` 与 `pop_wealth.txt` 保持一致）：

| 阶层 | 目标公式 | 最低值 |
|------|---------|--------|
| 贵族 | `200 + monthly_income_trade_and_tax × 8` | 80 |
| 教士 | `100 + monthly_income_trade_and_tax × 3` | 60 |
| 商人 | `100 + monthly_income_trade_and_tax × 3` | 60 |
| 平民 | `monthly_income_trade_and_tax × 2` | 45 |
| 部落民 | `monthly_income_trade_and_tax × 1` | 35 |

**存款压力公式**：

```
savings_pressure = (estate_gold / savings_target - 1) × 0.5
                   范围：[-0.5, max]（各阶层 max 不同）
```

| 阶层 | 压力上限 |
|------|---------|
| 贵族 | 3.0 |
| 教士 | 2.0 |
| 商人 | 2.0 |
| 平民 | 1.5 |
| 部落民 | 1.5 |

**效果**：
- 贵族存款 = 目标 → 压力 = 0，需求正常
- 贵族存款 = 2倍目标 → 压力 = 0.5，需求增加
- 贵族存款 = 0 → 压力 = -0.5，需求显著降低
- **根本解决了原版贵族无限存款的问题**，存款越高越花钱，自然趋向目标值

---

### 3.4 层三：思潮制度加成（Institution Bonus）

**来源文件**：`pop_wealth.txt`（`gdp_per_capita_scale`），`standard_of_living_effects.txt`（面板显示）

```
institution_bonus = num_embraced_institutions × 0.05
```

即每接纳一项思潮制度，该国所有人口的商品需求提高 5%。

**逻辑**：制度代表社会文明程度的提升，人口对商品的了解与需求随之增加。这是线性增长，与 SOL 的非线性部分互补。

**效果示例**：
- 接纳 0 个制度：基础需求 ×1.0
- 接纳 4 个制度：基础需求 ×1.20
- 接纳 8 个制度：基础需求 ×1.40

**关键设计原则**：本系统没有"凭空"创造需求。所有需求增加都对应真实的资金流出，迫使阶层花掉手中的资金，而不是从虚空购买。

---

### 3.5 需求总乘数（gdp_per_capita_scale）组合效果

**完整公式**：

```
gdp_per_capita_scale = 1
  + local_*_gdp_nonlinear_component   (层一，约 -1 到 +5+)
  + local_*_savings_pressure          (层二，-0.5 到 3.0)
  + num_institutions × 0.05           (层三，0 到 +0.40)
```

最终这个乘数直接乘在原版 `pop_demands.txt` 中每个商品条目的最终 `multiply` 上，影响所有商品（食物、奢侈品、原材料等）。

---

### 3.6 地点 UI 说明

**入口一：地点界面人口栏**
- 位置：地点界面 → 人口栏 → 阶层满意度右侧
- 功能：显示当地 SOL 综合值及对应的需求情况
- 悬停即显示详细数值（tooltip）

**入口二：SOL 局势面板**
- 触发：游戏开始后第二个月自动弹出 `global_living_standard` 情境
- 条件：`current_date >= 1337.2.1`，永不结束（`can_end = always = no`）
- 内容：显示全国各阶层的生活水准加权平均值，以及存款/目标存款/税率等

**情境面板数据（仅人类玩家，每月更新）**：
- `gls_country_sol_nobles/clergy/burghers/commoners/tribesmen` — 各阶层国家平均 SOL
- `gls_country_sol_all` — 全国人口加权平均 SOL
- `gls_*_savings_pressure` — 各阶层存款压力
- `gls_*_gold` / `gls_*_target` — 各阶层存款现值与目标值
- `gls_*_tax_pct` — 各阶层当前税率
- `gls_institution_bonus` — 制度加成值
- `gls_demand_*` — 各阶层总需求偏差（相对基准的百分比）
- `gls_avg_development` / `gls_avg_control` — 国家平均发展度/控制力

**地图着色（所有国家，每年更新）**：
- 着色因子：`gls_location_color_factor = (gls_location_avg_scale × development) / 50`，范围 [0, 1]
- 高 SOL（≥50 加权值）：绿色（`MAP_COLOR_HIGH`）
- 中 SOL（≥25 加权值）：黄色（通过 lerp 插值）
- 低 SOL：红色（`MAP_COLOR_LOW`）
- 图例：HIGH / MID / LOW 三档

---

## 四、抑制滚雪球系统（Feature 2：Anti-Snowballing）

来源模组：AS（Antisnowballing）整合并优化

### 4.1 基础税收效率 -15%

**来源文件**：`src/stable/in_game/common/auto_modifiers/SOL_tax_efficiency.txt`

```
base_tax_efficiency_602 = {
    potential_trigger = { exists = yes }
    tax_income_efficiency = -0.15
}
```

- 对所有国家生效（`exists = yes` = 所有真实国家）
- 原版 AS 为 -10%，本模组调高至 -15%，因为本模组同时提供了更多获得收入加成的途径
- **设计意图**：原版正税收效率意味着多出来的钱完全来自虚空。-15% 确保税收是真实国家实力的反映，可通过发展经济逐步克服
- AI 困难模式税收效率加成从原版 +5% 调低至 +2.5%；极难从原版 +20% 调低至 +10%（见下方难度部分）

### 4.2 冬季食物产出加重

**来源文件**：`src/stable/main_menu/common/static_modifiers/SOL_location.txt`

| 修正器 | 原版值 | 本模组值 |
|--------|--------|---------|
| `winter_mild` 月食物修正 | -0.25 | **-0.50** |
| `winter_normal` 月食物修正 | -0.50 | **-1.00** |
| `winter_severe` | 与原版相同 | 无修改 |
| 征募兵役 `raised_levies` 月食物修正 | -0.20 | **-0.30** |
| 征募兵役原产地产出修正 | -0.20 | **-0.30** |

**额外说明**：
- 小冰期 `harsh_winters_modifier` 食物容量从 -25% 调至 **-15%**，月食物从 -25% 调至 **-10%**（相对削弱，因为本模组食物压力已经加重，避免叠加过于极端）
- `short_harvest_modifier`（省级）月食物 -0.5 → **-0.25**
- `recent_white_storm_modifier`（省级）月食物 -0.5 → **-0.25**

**游戏玩法提示**：
- AI 和玩家面临相同的食物压力
- 省份严重缺粮时：可临时降低食物购买支出，允许阶层暂时节衣缩食
- 长远策略：优先扩建食物 RGO，必要时建造耕种村落保障人口增长

### 4.3 建筑成本随时代递增

**来源文件**：`src/stable/in_game/common/age/SOL_default.txt`

| 时代 | 建筑费用加成 | 食物消耗加成 | RGO扩建费用加成 | 城镇升级费用加成 |
|------|------------|------------|----------------|----------------|
| 时代1（传统/中世纪） | 无 | 无 | 无 | 无 |
| 时代2（文艺复兴） | +20% | +10% | +20% | +10% |
| 时代3（大发现） | +40% | +20% | +40% | +20% |
| 时代4（宗教改革） | +60% | +30% | +60% | +30% |
| 时代5（绝对主义） | +80% | +40% | +80% | +40% |
| 时代6（革命） | +100% | +50% | +100% | +50% |

**繁荣度自然衰减**（通过时代 `global_monthly_prosperity` 注入）：
- 时代1：-0.0015/月
- 时代2：-0.001/月
- 时代3：-0.0005/月
- 时代4：无衰减
- 时代5：+0.0005/月（轻微正向）
- 时代6：+0.001/月

**效果**：早期布局（时代1）的建设效率远高于后期扩张（时代6），强迫玩家在早期奠定基础，而非靠滚雪球一路堆量。

### 4.4 基础 RGO 规模减半

**来源文件**：`src/stable/main_menu/common/static_modifiers/SOL_location.txt`（`location_base_values`）

```
local_max_rgo_size = 1   # 原版：2
```

同时每单位总人口提供的 RGO 规模加成从 0.025 下调至 **0.020**（来自 `total_population` 修正器）。

**效果**：RGO 产出不再随领土无限线性增长，抑制了单纯靠扩张地块堆产量的策略。

### 4.5 低控制力地区建筑更贵

**来源文件**：`src/stable/main_menu/common/static_modifiers/SOL_location.txt`（`inverse_control`）

```
local_build_buildings_cost = 0.5  # 新增修正
```

`inverse_control` 随控制力降低而增强，意味着在低控制力地区建造建筑有额外费用惩罚，强迫玩家先稳固控制力再扩建。

### 4.6 道路价格大幅提升

**来源文件**：`src/stable/in_game/common/prices/SOL_00_hardcoded.txt`

| 道路类型 | 原版价格 | 本模组价格 | 倍数 |
|---------|---------|----------|------|
| 碎石路 | 10金 | **20金** | 2× |
| 铺装道路 | 25金 | **50金** | 2× |
| 现代道路 | 50金 | **150金** | 3× |
| 铁路 | 100金 | **500金** | 5× |

**历史依据**：道路在前工业化时代造价极高，直到近现代才得以普及。

### 4.7 AI 殖民限制

**来源文件**：`src/stable/in_game/common/generic_actions/SOL_colonial_charters.txt`

- AI 殖民要求税基 ≥ **500**（原版 100，原 AS mod 为 1000）
- 殖民地国家可在本国首都所在地区内殖民（减少边境混乱）
- 历史性殖民者豁免（CAS、POR、SPA、SWE、KUR、ENG、GBR、FRA、NED、RUS、DAN）
- **不影响玩家**

### 4.8 外交支出动态成本

**来源文件**：`src/stable/in_game/common/auto_modifiers/SOL_diplomatic_spending.txt`

```
diplomatic_spending_cost 修正值 = used_diplomatic_capacity × 0.005 - 0.05
```

即外交容量用得越满，每单位外交支出的花费越高（在原版 0.1 基础上叠加）。
- 容量为 0：实际成本 ≈ 0.05（低于原版）
- 容量为 10：实际成本 ≈ 0.1（等于原版）
- 容量为 20：实际成本 ≈ 0.15（高于原版）

### 4.9 文化传统 → 稳定度折扣

**来源文件**：`src/stable/in_game/common/auto_modifiers/SOL_cultural_tradition_stability.txt`

```
折扣公式（script_value）：stability_cost 减少 = 0.05 - 0.05 / (cultural_tradition + 1)
```

文化传统越高，降低稳定度的花费越低，鼓励专注文化建设。

### 4.10 各类行动金币上限与价格调整

**来源文件**：`src/stable/in_game/common/prices/SOL_00_hardcoded.txt`

关键调整（防止大国用无限金币碾压一切）：

| 行动 | 原版上限 | 本模组上限 |
|------|---------|----------|
| 接纳制度 | 无上限 | **3000金** |
| 迁都 | 无上限 | **2500金** |
| 招募探索者 | 1000金 | **250金** |
| 招募将领 | 无金币消耗 | **25金** |
| 招募海军提督 | 无金币消耗 | **25金** |
| 雇佣顾问 | 无金币消耗 | **25金** |
| 雇佣艺术家 | 无金币消耗 | **25金** |

---

## 五、战争代价系统（Feature：Harsher Wars）

来源模组：Harsher Wars，经修改调整

### 5.1 厌战度生成加速

**来源文件**：`src/stable/in_game/common/auto_modifiers/SOL_harsher_wars.txt`

| 触发条件 | 原版月厌战 | 本模组月厌战 |
|---------|-----------|------------|
| 首都被占领 | +0.1 | **+0.3** |
| 全境被占领 | +0.5 | **+2.0** |

### 5.2 厌战度 Debuff 加重

**来源文件**：`src/stable/in_game/common/auto_modifiers/SOL_harsher_wars.txt`（`war_exhaustion_impact`）

新增/加强修正（每级厌战）：

| 效果 | 原版 | 本模组 |
|------|------|--------|
| 陆军士气 | -2% | **-2%**（保持） |
| 海军士气 | -2% | **-2%**（保持） |
| 征召规模 | 无 | **-5%**（新增） |
| 生产效率 | 无（仅通用） | **通过 scaled_production_efficiency_penalty** |
| 贸易效率 | 无 | **通过 scaled_trade_efficiency_penalty** |
| 人口增长 | 无 | **-0.03%/月** |
| 月控制力 | 无 | **-0.01%/月** |
| 稳定度衰减 | 无 | **+0.01%/月** |
| 月合法性 | 无 | **-1%/月** |
| 要塞防御 | 无 | **-5%/级**（`global_defensive`，加速围城） |

### 5.3 战时无法通过内阁降低厌战度

**来源文件**：`src/stable/in_game/common/cabinet_actions/SOL_reduce_war_exhaustion.txt`

```
allow = {
    war_exhaustion > 0
    at_war = no    # 新增：战时不可用
}
```

**效果**：战争期间无法通过内阁行动降低厌战度，只能等战后通过外交解决。

### 5.4 被围攻省份更严苛的惩罚

**来源文件**：`src/stable/main_menu/common/static_modifiers/SOL_location.txt`

| 修正器 | 效果 | 原版 | 本模组 |
|--------|------|------|--------|
| `under_siege` | 食物 hostile 乘数 | 无 | **-100%**（食物被完全封锁） |
| `under_siege` | 月繁荣度 | +0.05衰减 | **-0.05/月** |
| `under_siege` | 月发展度 | 无 | **-0.20/月** |
| `under_siege` | 建设暂停 | 部分 | **完全暂停** |
| `is_occupied` | 月繁荣度 | -0.025 | **-0.05** |
| `is_occupied` | 月控制力 | -0.002 | **-0.005** |
| `is_occupied` | 月发展度 | 无 | **-0.25/月** |
| `is_occupied` | 食物 hostile | 无 | **-50%** |
| `is_occupied` | 建造速度 | -25% | **-75%** |
| `is_blockaded_by_enemies` | 月繁荣度 | -0.025 | **-0.05** |
| `is_blockaded_by_enemies` | 最大控制力 | -0.10 | **-0.30** |
| `is_blockaded_by_enemies` | 月发展度 | 无 | **-0.20/月** |

### 5.5 游牧/劫掠加重

| 修正器 | 原版月繁荣度 | 本模组 |
|--------|------------|--------|
| `recently_raided_by_horde` | -0.02 | **-0.035**，新增原产 -25%、食物 -30% |
| `recently_razed` | -0.02 | **-0.035**，新增原产 -25%、食物 -30% |
| `looted` | -0.1衰减 | **-0.025/月**，新增人口 -0.5%、发展度 -0.25/月 |

---

## 六、难度设置与游戏体验（Difficulty）

### 6.1 难度修正调整

**来源文件**：`src/stable/main_menu/common/static_modifiers/SOL_difficulty.txt`

由于全局 -15% 税收效率，原版难度加成按比例削减，维持合理难度曲线：

| 难度 | 税收效率 原版 | 本模组 |
|------|------------|--------|
| AI 困难 | +5% | **+2.5%** |
| AI 极难 | +20% | **+10%** |
| 玩家极简单 | +25% | **+12.5%** |
| 玩家简单 | +5% | **+2.5%** |

### 6.2 测试结论（作者+朋友多次测试）

- **1337年开局**：欧洲国家经济发展较慢，属正常现象（对应14世纪战乱、饥荒、黑死病、中世纪晚期停滞）
- **约1400年**：大多数国家可以打平原版税基（需精心管理）
- **1400年后**：SOL 带来的需求增益对经济增长的推动作用开始肉眼可见
- **建议首次游玩**：AI 设为普通难度
- **熟悉后**：强烈建议 AI 至少困难难度（AI 完全不如人类玩家擅长经济发展）

---

## 七、其他改动细节

### 7.1 新增鱼类商品

**来源文件**：`src/stable/in_game/common/goods/SOL_fish_food.txt`

（具体内容未读取，但文件存在）

### 7.2 SOL 决议

**来源文件**：`src/stable/in_game/common/resolutions/standard_of_living_resolution.txt`

（具体内容未读取，但文件存在）

### 7.3 小冰期平衡调整

由于本模组已显著加重食物压力，小冰期相关修正适当减弱，避免叠加过于残酷：

- `livestock_suffers_modifier`：全国牲畜产出从 -10% 调至 **-5%**
- `wineries_suffering_modifier`：葡萄酒产出从 -100% 调至 **-5%**（大幅减弱）
- `great_frost_modifier`：月食物从 -1 调至 **-0.5**，小麦/水稻/玉米从 -100% 调至 **-50%**

### 7.4 pop_demands 商品多样性保留

本模组**完整保留**了原版 `pop_demands.txt` 中所有文化/宗教/气候相关的需求差异：

- 伊斯兰/耆那教/锡克教禁酒（需求×0）
- 地中海地区偏好葡萄酒
- 北欧地区偏好烈酒
- 波罗的海文化偏好蜂蜜酒
- 亚洲热带地区偏好大米
- 欧洲偏好小麦
- 印度/安第斯/各地区食物偏好
- 疾病爆发时药材需求翻倍
- 扫盲率影响纸张/书籍需求
- 等等

所有这些差异都被 `gdp_per_capita_scale` 乘数放大——即富裕的地区其文化特色消费也更突出。

---

## 八、兼容性（Compatibility）

### 不兼容

- **其他需求 rework mod**：本模组从根本上修改了 `pop_demands.txt`，不与任何对人口需求进行重写的模组兼容
- **修改地点 UI 的 mod**：本模组修改了地点界面（人口栏 SOL 显示）

### 兼容

- 不修改 `situations`、`auto_modifiers`、`pop_demands` 的大多数模组应可兼容
- 不修改地点 UI 的模组（此类 mod 较少）

### 未测试

欢迎玩家报告兼容问题，作者将尽力修复。

---

## 九、致谢

本模组整合、延续并改进了以下两个已停止更新的优秀模组：

1. **Standard of Living（旧 SOL）** — 链接占位符：`LINK_OLD_SOL` — 生活水准系统的原始框架
2. **Antisnowballing（AS）** — 链接占位符：`LINK_AS` — 经济平衡与反滚雪球系统

感谢两位作者的开创性工作。

---

## 十、外部资源（待填写）

- 工坊英文页：`LINK_EN`
- 工坊中文页：`LINK_ZH`
- Bilibili 讲解视频：`LINK_BILI`
- GitHub 仓库：https://github.com/HLJSXK/eu5-modding-project

---

## 十一、核心文件索引

| 功能 | 文件路径 |
|------|---------|
| 需求主入口（gdp_per_capita_scale） | `in_game/common/goods_demand/pop_demands.txt` |
| SOL 全套计算逻辑 | `in_game/common/script_values/pop_wealth.txt` |
| 情境面板展示变量 | `in_game/common/script_values/standard_of_living.txt` |
| 情境定义（地图着色） | `in_game/common/situations/standard_of_living.txt` |
| 情境更新/计算 effect | `in_game/common/scripted_effects/standard_of_living_effects.txt` |
| 税收效率 -15% | `in_game/common/auto_modifiers/SOL_tax_efficiency.txt` |
| 战争代价 | `in_game/common/auto_modifiers/SOL_harsher_wars.txt` |
| 外交支出动态 | `in_game/common/auto_modifiers/SOL_diplomatic_spending.txt` |
| 文化传统稳定折扣 | `in_game/common/auto_modifiers/SOL_cultural_tradition_stability.txt` |
| 地点级修正重写 | `main_menu/common/static_modifiers/SOL_location.txt` |
| 国家级修正重写 | `main_menu/common/static_modifiers/SOL_country.txt` |
| 时代建筑/食物递增 | `in_game/common/age/SOL_default.txt` |
| 道路/行动价格 | `in_game/common/prices/SOL_00_hardcoded.txt` |
| 难度调整 | `main_menu/common/static_modifiers/SOL_difficulty.txt` |
| 战时无法降厌战 | `in_game/common/cabinet_actions/SOL_reduce_war_exhaustion.txt` |
| AI殖民限制 | `in_game/common/generic_actions/SOL_colonial_charters.txt` |
