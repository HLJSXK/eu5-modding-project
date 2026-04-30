# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Synced vanilla reference files under `reference_game_files/` to EU5 version 1.1.10.
- Updated documentation to reflect the new reference baseline.

## [Mod v1.1.0] - 2026-04-30

### 替代组 (Substitute Groups)

实现了一套完整的替代商品系统。56种商品被分配至以下20个替代组；部分商品同时归属多个组：

| 替代组 | 含义 |
|--------|------|
| Basic Clothing | 基础服饰（布料、皮革） |
| Crude Goods | 粗制品（木材、砖石、工具、陶器） |
| Staple Food | 主食（小麦、稻米、小米、玉米、土豆、豆类、鱼） |
| Condiments | 调味品（蔗糖、盐、橄榄） |
| Heating & Lighting | 取暖与照明 |
| Household Goods | 家居用品（市民专属） |
| Standard Clothing | 标准服饰 |
| Intoxicants | 麻醉品 |
| Luxury Drinks | 奢侈饮品 |
| Luxury Food | 奢侈食品 |
| Luxury Goods | 奢侈品 |
| Protein Food | 蛋白质食品 |
| Spices | 香料 |
| Precious Goods | 贵重商品（金、银、琥珀） |
| Treasures | 珍宝 |
| Medicine | 药品 |
| Ritual Goods | 祭祀用品（教士专属） |
| Weapons | 武器 |
| Mounts | 坐骑 |
| Knowledge Goods | 知识商品（书籍；教士专属） |

#### 价格稀缺分级（6档）

每种商品依据当前市场价格与默认价格的比值被实时分配到以下档位；档位信息缓存至全局变量列表（如 `SOL_cloth_severe_markets`），每年在 `on_monthly` Pass 0 中全局扫描更新：

| 档位 | 触发条件 | 需求权重乘数 |
|------|----------|------------|
| Severe shortage | 价格 > 2.30× | 0.25 |
| Moderate shortage | 价格 > 1.70× | 0.50 |
| Mild shortage | 价格 > 1.30× | 0.75 |
| Affordable | 价格 < 0.85× | 1.25 |
| Cheap | 价格 < 0.65× | 1.50 |
| Very Cheap | 价格 < 0.40× | 2.00 |
| Normal | 其余 | 1.00 |

权重变化后，组内稀缺商品份额被吸收至剩余商品，实现组内替代。

#### 恩格尔曲线（按阶层分段线性）

各阶层（nobles / clergy / burghers / commoners / tribesmen）对每个替代组拥有独立的预算份额脚本值，由 `data/alpha_bracket_table.csv` 经 `tools/sol_demand_simulator/engel_export.py` 生成，再写入 `z_SOL_group_budget_shares.txt`。曲线以人均GDP为横轴，分三段锚定：GDP ≤ 3.0、3.0–8.0、8.0–25.0，体现恩格尔定律下不同收入阶段消费结构的演化。

---

### 新增脚本值文件

| 文件 | 作用 |
|------|------|
| `SOL_goods_demand_values.txt` | 各商品需求基准值 |
| `SOL_goods_weight_values.txt` | 商品需求权重：稀缺档位乘数 × 气候修正（冬季严酷度 0.5–2.0） |
| `SOL_substitute_good_indicators.txt` | 地点作用域：每种商品的稀缺档位、盈余档位、权重指标、组内需求份额（用于GUI显示） |
| `SOL_substitute_group_indicators.txt` | 地点作用域：每个替代组是否处于稀缺状态（布尔值） |
| `z_SOL_group_budget_shares.txt` | 各阶层对各替代组的预算份额（恩格尔曲线分段值） |
| `z_SOL_group_demand_base_location.txt` | 地点作用域的需求基准 |
| `z_SOL_group_demand_offsets.txt` | 需求偏移修正 |
| `z_SOL_group_demand_scales.txt` | Pop作用域需求规模路由器（按pop_type分派到地点值） |
| `z_SOL_group_demand_scales_location.txt` | 地点作用域各阶层的恩格尔曲线需求规模 |
| `z_SOL_group_prices.txt` | 各商品价格参考值（用于预算份额计算） |

### 新增脚本效果文件

- **`SOL_substitute_effects.txt`**（5545行，`scripts/gen_scarcity.py` 自动生成）：`SOL_update_substitute_scarcity` 效果体。遍历所有市场，清除旧档位成员资格，依当前价格重新分配档位，写入全局变量列表。

### 新增GUI文件

- **`SOL_substitute_tooltip.gui`**（2878行）：替代组详情面板，在地点窗口人口Tab中显示。每个组展示：组名图标、各商品行（图标 / 名称 / 状态徽章：SCARCE/OK/AFFORDABLE/CHEAP/VCHEAP，稀缺红色、盈余绿色）、权重指标、需求影响百分比偏移。
- **`z_SOL_goods_tooltip_override.gui`**（3803行）：各商品提示词覆盖，显示该商品所属的替代组及其在组内的权重占比。

### 修改GUI文件

- **`location_window.gui`**：人口面板新增两组替代信息区：① 当前各替代组稀缺状态；② 基于收入的消费调整情况。
- **`panels/situation/global_living_standard.gui`**：局势面板重构，新增全国消费概览，可快速查看各替代组需求估算。
- **`SOL_economy_local.gui`**：整合地点经济信息展示。

### 触发机制变更

- **`on_game_start`**（`SOL_economy_on_actions.txt`）：新增 `gls_init_after_lobby` 钩子，游戏开始时触发完整GLS初始化（含替代稀缺缓存重建）。
- **`SOL_economy_situation.txt` on_monthly Pass 0**：每年第1月全局扫描所有市场，更新稀缺档位缓存。

---

### 开发工具与代码生成基础设施

新增代码生成脚本（均须通过 `conda run -n eu5 python scripts/...` 执行）：

| 脚本 | 生成目标 |
|------|----------|
| `scripts/gen_scarcity.py` | `SOL_substitute_effects.txt`、`SOL_substitute_good_indicators.txt`、`SOL_substitute_group_indicators.txt` |
| `scripts/gen_sol_ui.py` | `SOL_substitute_tooltip.gui`、`z_SOL_goods_tooltip_override.gui` |
| `scripts/gen_pop_goods.py` | `z_SOL_pop_goods.txt` 商品定义 |
| `scripts/gen_demand_csv.py` | `data/demand_price_table.csv` |

`tools/sol_demand_simulator/` 大幅扩展：
- `engel_export.py`：根据 `data/alpha_bracket_table.csv` 导出分段恩格尔曲线脚本值；`EXPORT_ALPHA_MULTIPLIER = 2.0`
- `curve_designer.py`：交互式曲线设计工具
- `export_static.py`：静态JSON导出（`docs/simulator/data/`）
- `docs/simulator/`：新增基于GitHub Pages的Web需求模拟器

### 本地化

- 新增 `SOL_substitute_goods_l_english.yml` / `SOL_substitute_goods_l_simp_chinese.yml`，覆盖全部20个替代组标题、描述、各商品名称及UI文字（SCARCE/DEMAND/STATUS/WEIGHT标签）。
- 更新 `SOL_economy_l_english.yml` / `SOL_economy_l_simp_chinese.yml`：补充局势面板和全局生活水平相关词条。

---

### 旧存档兼容性

本次更新对旧存档**完全兼容**，但由于需求结构发生根本性变化，市场价格将显著波动，需经较长时间方可重新稳定。如偏好旧版，请订阅旧版分支（链接待填）。

## [2.0.0] - 2026-03-24

### Changed
- Repository scope is now mod development only.
- Online multiplayer tooling moved to a separate repository:
  - https://github.com/HLJSXK/eu5-online-tools

### Removed
- Local online deployment and sync code from this repository.
- Go toolchain and online tool build artifacts from this repository.

## [1.1.0] - 2026-01-22

### Added
- **Steam Account Name Configuration**: Users can now set custom account names for LAN multiplayer sessions
  - New `--account-name` flag for eu5-deployer
  - Default account name: "EU5Player"
  - Creates `force_account_name.txt` in steam_settings folder

- **Input Validation**: Added validation function for account names
  - Account name: 1-32 characters

### Changed
- Updated deployment workflow to include Steam settings configuration as Step 0
- Enhanced deployer package with new configuration functions:
  - `ConfigureSteamSettings()` - Main configuration function
  - `ValidateAccountName()` - Validates account name format

### Documentation
- Updated `docs/Goldberg_Emulator_Guide.md` with account name configuration instructions
- Updated `docs/Tools_Guide.md` with new command-line flags and usage examples
- Updated `docs/Quick_Start_Guide.md` with customization instructions and multi-player setup guide

### Technical Details
- Added `strings` package to deployer
- Template files created in `goldberg_emulator/steam_settings/`:
  - `force_account_name.txt` (default: "EU5Player")

## [1.0.0] - 2026-01-21

### Initial Release
- EU5 installation detector
- Goldberg Emulator deployment tool
- Automatic backup and restore functionality
- Cross-platform support (Windows, Linux, macOS)
- DLC configuration support
- Mods folder support

---

**Project Repository:** https://github.com/HLJSXK/eu5-modding-project  
**Goldberg Emulator:** https://gitlab.com/Mr_Goldberg/goldberg_emulator
