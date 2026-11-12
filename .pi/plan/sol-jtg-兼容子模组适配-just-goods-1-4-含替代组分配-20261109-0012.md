# SOL-JTG 兼容子模组适配 Just Goods 1.4

## 0. 现状核实（已实测，非推断）

上游 `3785316314` metadata：`version 1.1`、`supported_game_version 1.4`、依赖 CMF `2.*`。仓库基线对应旧版 32 goods。

### 0.1 已确认的断裂

```
$ python scripts\gen_sol_jtg_compat.py --check
[OK] 5/5 产物 Up to date，退出码 0      ← 陷阱：即使已与上游脱节也通过
$ python scripts\gen_sol_jtg_compat.py --check --audit-workshop-root "<workshop>"
ValueError: Workshop goods file not found: ...\in_game\common\goods\brass_produced_goods.txt
退出码 1
```

即：**裸 `--check` 绿、真审计红**。产物 5 个文件全部已过期，但 `--check` 只比对自身生成结果，不校验上游。

### 0.2 上游文件改名（全部加 `just_` 前缀）

| 基线 `JUST_GOODS_FILES` | 上游 1.4 |
|---|---|
| `brass_produced_goods.txt` | `just_brass_produced_goods.txt` |
| `cheese_produced_goods.txt` | `just_cheese_produced_goods.txt` |
| `clocks_produced_goods.txt` | `just_clocks_produced_goods.txt` |
| `meat_produced_goods.txt` | `just_meat_produced_goods.txt` |
| `soap_goods.txt` | `just_soap_goods.txt` |
| `spices_produced_goods.txt` | `just_spices_produced_goods.txt` |
| —（新增） | `just_gunpowder_goods.txt` |
| —（新增） | `just_stone_goods.txt` |

### 0.3 商品集合变化（实测解析上游 8 个文件）

- 总计 42 个 goods（基线 32）
- **有 pop 需求 30 个**（基线 26）
- 无需求 12 个（基线 6）

**新增 10 个，其中 4 个带需求：**

| good | price | nobles | clergy | burghers | dev_thr | wealth | 建议归类 |
|---|---|---|---|---|---|---|---|
| `obsidian` | 2 | 0.02 | — | 0.001 | — | 1.2 | 需求 / treasures |
| `jade` | 3 | 0.02 | — | 0.001 | — | 1.2 | 需求 / treasures |
| `diamonds` | 8 | 0.01 | — | 0.001 | — | 1.2 | 需求 / precious |
| `plaster` | 1.5 | 0.125 | 0.02 | 0.015 | 20 | 1.25 | 需求 / 无组（见 §2.4） |

**新增无需求 6 个**：`limestone`、`lime`、`flint`、`gunpowder`、`sulfur`、`shot` → 进 `EXPECTED_EXCLUDED_GOODS`。

`development_threshold` 出现 16 次（基线 15），新增者为 `plaster`。

---

## 1. 替代组机制（实测源码，这是本方案的核心约束）

### 1.1 当前 JTG 在求解器中的真实状态

实测：

```
combined rows: 82
jtg goods in CORE? []          ← 26 个 JTG 商品全部不在 CORE
jtg goods in GROUPS? {}        ← 全部不属于任何替代组
render_country_runtime(rows, extra_goods=所有JTG商品)
  → ValueError: runtime nobles basket mismatch: extra=[26 个商品全列]
```

**结论：现有 26 个 JTG 商品在价格替代求解器中完全不参与。** 它们只在 `render_location_spending` 里被 `if good in CORE or good in extra_goods` 认作有效，拿到 `sol_good_effective_<good>`，但倍率恒为中性 1。这与 `substitute_groups.json` 的 `"JTG extras have no groups"` 和文档 "JTG 的 26 个额外商品保持中性、无组且计入消费" 一致——**这是刻意设计，不是缺陷**。

### 1.2 三条硬约束（决定哪些商品能进组）

**(A) 整组订阅约束** —— `gen_whole_group_baskets.validate_baskets`：
某个组被阶层 P 订阅（`pop_group_baskets.csv` 中 P 列为 1），则该组**每个成员**对 P 的量必须 ≥ 0.00001；且该阶层消费的商品集合必须**恰好等于**其订阅组成员的并集。

**(B) 签名包含约束** —— 商品的正需求阶层集合必须是目标组订阅阶层集合的超集。实测的组订阅签名：

| 订阅阶层数 | 组 |
|---|---|
| 6（nobles/clergy/burghers/laborers/peasants/soldiers） | `condiments` `crude_goods` `heating` `household` `intoxicants` `luxury_food` `medicine` `protein` `staple` |
| 4 | `basic_clothing` `weapons`(N,L,P,S) `luxury_drinks`(N,C,B,S) |
| 3 | `knowledge` `luxury_goods` `spices` `standard_clothing`（均 N/C/B） |
| 2 | `precious` `treasures`（N/B） |
| 1 | `mounts`(N) `ritual`(C) |

**(C) 稀释效应** —— `response()` 中 `neutral = N / len(active)`，`current = N·w/Σw`。向组内加成员会改变中性分母，从而**移动组内所有既有商品的倍率**。实测 `luxury_goods`（N=6，fine_cloth 权重 2.0）：

| 新增成员数 | n | fine_cloth 倍率 | 其他成员倍率 |
|---|---|---|---|
| 0 | 6 | 1.71429 | 0.85714 |
| 1 | 7 | 1.75000 | 0.87500 |
| 3 | 9 | 1.80000 | 0.90000 |
| 7 | 13 | 1.85714 | 0.92857 |

加成员会**放大**稀缺成员的信号，同时抬升充裕成员的倍率。这是必须显式接受并记录的平衡后果，不能默认"加了就更真实"。

### 1.3 一个必须先修的实现缺陷

`render_country_runtime(..., group_overrides=, group_sizes=)` 这两个参数**只用于校验，不影响发射的代码**：

- `groups`（含 overrides）只参与 `for pop in POPS` 前的 `expected != actual` 断言
- 真正的按阶层循环用 `groups = groups_for_pop(pop, removed_goods)`，硬读模块级 `GROUPS`
- `size = CONFIG["historical_sizes"][group]`，硬读配置，**不用 `sizes`**

所以**即使传入 overrides 也不会生效**。PP 的 silk 走的是另一条路——`gen_sol_pp_compat.py:341` 的 `_patch_substitution()` 直接改写模块级 `_sol_substitution.GROUPS` / `CORE` / `PRIMARY_GROUP` / `HUD_GOODS`。JTG 必须复用该模式。

---

## 2. 替代组分配方案（逐个商品）

对 30 个商品，先按约束 (B) + (A) 算出**可行组**（实测矩阵），再按语义选定。

### 2.1 `spices`（N/C/B）— 香料商品，语义最明确

| good | 最终量 N/C/B | 归属 |
|---|---|---|
| `cardamom` | 0.05 / 0.004 / 0.0026 | **spices** |
| `cinnamon` | 0.05 / 0.004 / 0.0026 | **spices** |
| `nutmeg` | 0.05 / 0.004 / 0.0026 | **spices** |
| `star_anise` | 0.05 / 0.004 / 0.0026 | **spices** |
| `vanilla` | 0.05 / 0.004 / 0.0026 | **spices** |
| `turmeric` | 0.05 / 0.004 / 0.0026 / peasants 0.00004 | **spices** |
| `ginger` | 0.05 / 0.004 / 0.0026 / peasants 0.00004 | **spices** |

`spices` 由 4 → 11 成员。`turmeric`/`ginger` 含 peasants 微量，但 peasants 不订阅 `spices`，不违反 (A)。

### 2.2 `luxury_goods`（N/C/B）— 奢侈品与贵重器物

| good | 最终量 N/C/B | 归属 |
|---|---|---|
| `brassware` | 0.11 / 0.02 / 0.026 | **luxury_goods** |
| `silverware` | 0.11 / 0.004 / 0.0059 | **luxury_goods** |
| `ornaments` | 0.05 / 0.012 / 0.013 | **luxury_goods** |
| `bells` | 0.03 / 0.006 / 0.0066 | **luxury_goods** |
| `mirrors` | 0.11 / 0.004 / 0.0059 | **luxury_goods** |
| `optics` | 0.11 / 0.004 / 0.0059 | **luxury_goods** |
| `clocks` | 0.11 / 0.004 / 0.0059 | **luxury_goods** |
| `aromatics` | 0.05 / 0.018 / 0.026 | **luxury_goods** |

`luxury_goods` 由 6 → 14 成员。`aromatics` 语义上也可入 `spices`，但它上游带 `sub_continent_demand_modifier middle_east`，属区域化奢侈品，放 `luxury_goods` 更贴合；若希望保留"香料"语义可改入 `spices`，届时 `spices` 为 12、`luxury_goods` 为 13。**这是本方案唯一需要你拍板的语义选择。**

### 2.3 `precious` / `treasures`（N/B）

| good | 最终量 N/B | 归属 | 理由 |
|---|---|---|---|
| `diamonds` | 0.11 / 0.0059 | **precious** | 宝石类，与 `gems`/`jewelry` 同组 |
| `jade` | 0.02×1.05 / 0.001×0.6555 → 小量 | **treasures** | 原料珍宝，与 `amber`/`ivory` 同组 |
| `obsidian` | 小量 | **treasures** | 同上 |
| `cosmetics` | 0.11 / 0.0059 | **treasures** | 无更贴切组；备选 `luxury_goods` 但签名只到 N/B |
| `perfume` | 0.11 / 0.0059 | **treasures** | 同上 |
| `precision_instruments` | 0.11 / 0.0059 | **knowledge** 不可（需 clergy），→ **treasures** | 见下 |

⚠️ `precision_instruments` 的量只有 N/B（clergy 为 0），因此**不能进 `knowledge`/`luxury_goods`/`spices`**（它们订阅 clergy）。语义上它是知识器物，但受 (A) 约束只能落 `precious`/`treasures`/`mounts`。这是一个真实的取舍：**要么接受它进 `treasures`（语义略牵强），要么给它补一条 clergy 需求使其能进 `knowledge`**。后者会改变 SOL 标定，不建议。方案默认：`treasures`。

`precious` 3→4，`treasures` 4→9。

### 2.4 不进组的商品（保持中性）

| good | 最终量特征 | 原因 |
|---|---|---|
| `plaster` | N 0.125 / C 0.02 / B 0.015 | 签名 N/C/B 可行组为 `luxury_goods`/`spices`/`knowledge` 等，但语义上是建材，**不宜进任何奢侈品组**；且入组会稀释该组 |
| `candles` | N/C/B + L 0.00008 + P 0.00024，**soldiers 为 0** | 6 阶层的组（`household`/`heating`）要求 soldiers > 0 → 违反 (A)；3 阶层组语义不合 |
| `cheese` / `meat` / `soap` | N/C/B + L/P/S 全有量 | 可进 `staple`/`protein`/`luxury_food`/`condiments`/`medicine` 等。**`meat`+`cheese` 进 `protein`、`soap` 进 `medicine` 语义合理**，但会显著稀释这些只有 2–3 成员的组。建议：**`meat`/`cheese` → `protein`（3→5），`soap` → `medicine`（2→3）** |
| `palmoil` / `tallow` / `whaleoil` | N/C/B + L/P/S 全有量，带区域修饰符 | 语义为油脂原料。`tallow` → `household`（制烛原料）；`palmoil`/`whaleoil` 建议保留无组（区域化强烈，且 `household` 已 5→6） |
| `pewterware` | N/C/B + L/P/S 全有量 | 可入 `household`（5→7）。语义为锡器，合理 |
| `ginger`/`turmeric` | 见 §2.1 | 已入 `spices` |

**综合建议的最终归属（一表定案）：**

| 组 | 新增成员 | 成员数变化 |
|---|---|---|
| `spices` | cardamom, cinnamon, nutmeg, star_anise, vanilla, turmeric, ginger | 4 → 11 |
| `luxury_goods` | brassware, silverware, ornaments, bells, mirrors, optics, clocks, aromatics | 6 → 14 |
| `precious` | diamonds | 3 → 4 |
| `treasures` | jade, obsidian, cosmetics, perfume, precision_instruments | 4 → 9 |
| `protein` | meat, cheese | 3 → 5 |
| `medicine` | soap | 2 → 3 |
| `household` | tallow, pewterware | 5 → 7 |
| **无组（中性）** | plaster, candles, palmoil, whaleoil | 保持中性 |

合计进组 26 个商品中的 26 个（4 个新增需求商品全部进组），**替代组关系 67 → 92 条**。

> 若你认为 `soap`→`medicine` 或 `tallow`→`household` 语义不妥，可退回无组，不影响其余部分。

---

## 3. 实施步骤

### 步骤 1：修上游文件清单

`scripts/gen_sol_jtg_compat.py:115` `JUST_GOODS_FILES` 改为 8 个 `just_` 前缀路径。

同时处理 `just_soap_goods.txt` 末尾的 `INJECT:cloves = { default_market_price = 6 }`——`_parse_vanilla_goods_file` 会把它解析为一个 goods 键，需在 `_audit_workshop` 中过滤 `INJECT:` 前缀，否则误报 `extra=['cloves']`。

### 步骤 2：更新期望集合

- `EXPECTED_DEMAND_GOODS` += `obsidian, jade, diamonds, plaster` → 30
- `EXPECTED_EXCLUDED_GOODS` += `limestone, lime, flint, gunpowder, sulfur, shot` → 12
- `EXPECTED_DEVELOPMENT_THRESHOLD_GOODS` += `plaster` → 16
- `EXPECTED_WEALTH_THRESHOLD_GOODS` 复核为全部 30 个需求商品
- `EXPECTED_CONTINENT_MODIFIER_GOODS` / `EXPECTED_SUB_CONTINENT_MODIFIER_GOODS` 不变（新商品无区域修饰符）

### 步骤 3：补 CSV 4 行

`data/jtg_pop_demand.csv` 追加 `obsidian` / `jade` / `diamonds` / `plaster`，字段按上游原文；`slaves` 一律 `0`（延续现有"slaves 无收入、完全抵消"策略）。

### 步骤 4：建立 JTG 替代组映射数据

新增 `data/jtg_substitute_groups.csv`（单一来源，避免污染 `goods_weights.csv` 的 56 核心口径）：

```csv
good,group
cardamom,spices
cinnamon,spices
...
plaster,            # 空 group = 无组中性
```

**不得**直接改 `data/goods_weights.csv`：`sol_substitution.py:22` 有 `assert len(CORE) == 56 and len(GROUPS) == 20`，`gen_whole_group_baskets` 的 `CORE` 也由它推导，改了会连带影响 stable/standalone/PP/M&T 四个目标。

### 步骤 5：复用 PP 的 `_patch_substitution()` 模式

在 `gen_sol_jtg_compat.py` 中新增等价上下文管理器，在生成器进程内临时扩展：

- `_sol_substitution.CORE` += 30 个 JTG 需求商品
- `_sol_substitution.GROUPS[group]` += 按 §2 映射的成员
- `sol_goods_order.PRIMARY_GROUP` / `GROUP_MEMBERS` 同步（供 UI 排序与 tooltip 分组）
- `_sol_substitution.HUD_GOODS` 是否需要扩展待定（HUD 上限 6 个槽，见 §5 风险）

然后用扩展后的状态调用 `render_country_runtime(combined_rows)`、`render_location_spending(combined_rows, replace=True)`。

**不要**依赖 `group_overrides=`：§1.3 已实测其对发射代码无效。

### 步骤 6：让 JTG 商品进入校验口径

`render_country_runtime` 的 `validate_baskets` 只校验 `good in CORE` 的量。JTG 商品进 CORE 后，会被纳入整组订阅校验，此时必须确认每个 (group, pop) 组合都满足 §1.2 (A)。**这是最容易失败的一步**，建议先跑一次只读校验再生成。

### 步骤 7：重新生成与验证

```powershell
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_chain.py --target sol_jtg_compatibility_submod
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\gen_sol_jtg_compat.py --check --audit-workshop-root "C:\Program Files (x86)\Steam\steamapps\workshop\content\3450310"
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\test_sol_slave_demand.py
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\test_sol_spending_cache.py
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\test_sol_substitution.py
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\test_sol_substitution_ui.py
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\test_sol_pp_compat.py
$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts\validate.py --changed
```

`test_sol_slave_demand.py` 内部调用 `jtg._audit_workshop`，是步骤 1–3 的回归闸门。
`test_sol_pp_compat.py` 用于确认 `_patch_substitution` 的全局状态隔离没有被破坏（PP 每进程只 patch 一次）。

### 步骤 8：文档与版本

- `docs/knowledge/BRIEF.md`：`:57`（26→30、82→86、67→92 条关系）、`:183`、`:260`、`:275`
- `src/sol_jtg_compatibility_submod/README.md`：`26`、`81`（该处本就与 82 不符，一并修正）、组归属说明
- `scripts/gen_sol_jtg_compat.py:505`、`scripts/sol_goods_ui.py:12,247`、`scripts/gen_brief.py:48` 注释中的 `26`/`82`
- `.metadata/metadata.json`：版本号递增
- `docs/technical/EU5_1.4_Beta_Compatibility_Audit.md`：追加本次审计结论

---

## 4. 验证清单

| 项 | 判定 |
|---|---|
| `--audit-workshop-root` 退出码 0，报 `42 new / 30 demand / 12 excluded` | 必须 |
| `--check` 5 个产物全部 `[OK] Up to date` | 必须 |
| 生成 goods 文件含 30 个 `INJECT:` 块 | 必须 |
| 生成 GUI 覆盖含 86 个商品位 | 必须 |
| `test_sol_slave_demand.py` 通过（含 JTG 审计） | 必须 |
| `test_sol_substitution.py` 通过（含 CORE=56 断言未被污染） | 必须 |
| `test_sol_pp_compat.py` 通过（确认 patch 隔离） | 必须 |
| 稳定/独立/PP/M&T 四目标产物**零差异** | 必须（`git status` 确认） |

---

## 5. 风险与待确认

1. **`gruop_overrides` 无效是既有缺陷**：是否顺手修 `render_country_runtime` 使其真正使用 overrides 与 `sizes`？修则更干净、但触及共享代码影响四个目标；不修则沿用 PP 的全局 patch 模式。**方案默认不修**，仅复用 patch 模式，把修复列为独立后续项。
2. **HUD 槽位**：`HUD_GOODS_LIMIT = 6`，`render_hud_goods_cache` 遍历 `(*HUD_GOODS, *extra_goods)`。若把 30 个 JTG 商品加入 HUD，可能与既有 56 核心商品竞争 6 个显示槽。建议**不扩展 HUD_GOODS**，仅在 tooltip 分组中体现。
3. **稀释改变既有商品倍率**：§1.2(C) 实测 `luxury_goods` 从 6 增至 14 成员后，既有成员倍率整体上移约 8%。这是预期的平衡后果，需在 README 中写明，并建议实机对比存档。
4. **`preservation` 语义取舍**：`precision_instruments` 只能落 `treasures`，`plaster`/`candles`/`palmoil`/`whaleoil` 不进组。若你希望它们进组，需调整 `pop_group_baskets.csv` 订阅或补需求，属扩大范围。
5. **定点精度**：`jade`/`obsidian` 标定后 nobles 约 0.021、burghers 约 0.00066，五位小数可表示；但 `ginger`/`turmeric` 的 peasants 0.00004 已在下限附近，入组后需确认不低于 0.00001 门槛。
6. **实机验收不可替代**：`SOL_Substitution_Implementation_20261013.md:74` 明确要求"在 PP、M&T、JTG 的真实加载顺序下检查最终商品数量、价格和求解器记账"。静态测试只能保证生成一致性。
