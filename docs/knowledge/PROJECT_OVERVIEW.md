# EU5 Mod - Project Overview

> This document is maintained by AI. Update it whenever mod features or directory structure change.
> Last updated: 2026-06-24 (SOL icon UI references)

## Project Identity

- Mod name: **Standard of Living (SOL)**
- Mod ID: `hades.sol` | Version: `1.1.0` | Target: EU5 `1.*.*`
- Requires Community Mod Framework v2.*
- Single active mod source: `src/stable/`

## Core Features

1. **Standard of Living (SOL) System** *(primary feature)* - Recalibrates baseline `demand_add` for 55 goods in `z_SOL_pop_goods.txt`, then applies a monthly location-level `local_pop_demand` modifier from `monthly_country_pulse`. The monthly coefficient is income-closed: local stratum income, estate-building maintenance, unified country savings pressure, local pop counts, market-keyed base spending, and the engine's automatic development demand divisor `(1 + development / 20)` combine into the displayed demand multiplier. EU5 1.3.4 poverty-consumption reduction is countered by one country-level compensation factor computed from national stratum income/expense ratios on full refresh and yearly country pulse, while demand UI displays keep showing the uncompensated SOL target and map displays show actual per-capita liquid funds. Yearly market scans cache one-unit pop spending per market using `min(market_price, default_price)`. The old substitute-goods, scarcity-tier, per-stratum Engel, and per-good redistribution chain is retired in EU5 1.3. The system feeds the Living Standard situation panel, its Black Death-style situation data map, the separate economy-category Living Standard mapmode with panel auto-selection, and location GUI.

2. **Economic Balance & Anti-Snowballing** - Base tax efficiency defaults to -15% and is CMF-adjustable. Age escalation raises construction, RGO expansion, city/town upgrade, and food-consumption pressure across ages; by Age 6 it reaches -100% global building efficiency, +100% RGO expansion cost, +50% city/town upgrade cost, and +50% pop food consumption. Base RGO size is halved to 1, total-population RGO scaling is reduced, low-control locations receive a construction-efficiency penalty, and road prices are increased to gravel x2, paved x2, modern x3, railroad x5.

3. **Tax, Prices & Development** - Difficulty tax bonuses are halved for AI Hard/Very Hard and Player Easy/Very Easy. Diplomatic spending changes with used diplomatic capacity, cultural tradition reduces stability investment cost, and gold-transfer/action prices are rebalanced. GDP-to-development applies a yearly local development modifier scaled by local GDP, and AI countries can receive a small configurable devastation-recovery bonus.

4. **War & Combat (Harsher Wars)** - War exhaustion further reduces levy size, control, stability, legitimacy, and defensive capability. Total occupation adds +1.6 monthly war exhaustion on top of vanilla, and capital occupation adds +0.2 monthly war exhaustion on top of vanilla. The reduce-war-exhaustion cabinet action can be restricted to peacetime. Blockade, siege, occupation, hostile troops, looting, raiding, and razing modifiers are harsher for prosperity, control, construction, migration attraction, development, raw materials, and food.

5. **Food, Climate & Prosperity** - Normal winters and raised levies create harsher local food pressure, while Little Ice Age event penalties are softened to avoid runaway food-crisis spirals. Age escalation starts with mild prosperity scarcity and later returns prosperity in the late game.

6. **Colonial & Diplomatic Restrictions** - AI generally requires more than 500 tax base to create colonial charters; historical colonizers are exempt, and colonial nations can colonize only in their capital region. The player is not restricted by this rule. Asking another country to join a war costs 30 favors.

7. **CMF Settings & Migration Support** - Registers CMF settings for SOL pop demand, map coloring, economic balance, base tax efficiency, age escalation, stability discount, diplomatic spending, difficulty tax nerf, GDP-to-development, AI prosperity recovery, and war acceleration sub-features. Built-in after-lobby migration logic notifies human players when loading older saves and triggers full Living Standard cache refreshes on game start/load.

## Directory Structure

```text
eu5-modding-project/
|-- src/
|   `-- stable/                         active mod source
|       |-- .metadata/                  mod metadata
|       |-- loading_screen/
|       |   `-- common/defines/       pop demand performance refresh cap
|       |-- in_game/
|       |   |-- gfx/
|       |   |   `-- map/map_modes/    custom SOL map modes
|       |   |-- common/
|       |   |   |-- auto_modifiers/     war exhaustion, tax efficiency penalties
|       |   |   |-- cabinet_actions/    war exhaustion reduction restriction
|       |   |   |-- diplomatic_costs/   rebalanced diplomatic action costs
|       |   |   |-- generic_actions/    colonial charter restrictions
|       |   |   |-- goods/              good definitions and SOL calibrated demand_add baseline
|       |   |   |-- on_action/          trigger hooks, including monthly local_pop_demand and yearly SOL maintenance/cache refresh
|       |   |   |-- prices/             price adjustments
|       |   |   |-- resolutions/        resolution definitions
|       |   |   |-- scripted_effects/   SOL computation and country gold effects
|       |   |   |-- scripted_guis/      custom GUI logic
|       |   |   |-- scripted_triggers/  custom trigger definitions
|       |   |   |-- script_values/      SOL computation values
|       |   |   |-- situations/         Standard of Living situation definition
|       |   |   `-- trigger_localization/
|       |   |-- events/
|       |   `-- gui/
|       |       |-- location_window.gui  location window integration
|       |       |-- SOL_economy_local.gui location SOL tooltip/panel content
|       |       |-- SOL_migration_caller.gui after-lobby migration/cache callers
|       |       |-- panels/             situation panels
|       |       `-- scripted_widgets/
|       `-- main_menu/
|           |-- gfx/interface/icons/    generated SOL icon targets for shared UI, map modes, and situations
|           |-- gui/                   message category definitions
|           |-- common/
|           |   `-- static_modifiers/   country, location, province modifiers
|           `-- localization/
|-- docs/                              project knowledge, guides, technical notes
|-- scripts/                           Python codegen + validation
|-- tools/                             support tooling
|-- data/                              calibration CSVs and legacy simulator data
|-- assets/                            images and media
|-- reference_game_files/              vanilla EU5 references
|-- reference_mods/                    community mod examples
`-- reference_official_defines/        official EU5 syntax/type definitions
```

## Script Reference

| Script | When to run | Output |
|---|---|---|
| `gen_pop_goods.py` | After editing `target_demand.csv` | `z_SOL_pop_goods.txt` (calibrated demand_add baseline) |
| `gen_demand_csv.py` | After demand calibration | `data/demand_price_table.csv` |
| `gen_market_unit_consumption.py` | After `gen_demand_csv.py`, or after changing SOL market base-spending logic | `SOL_market_unit_consumption_values.txt`; `sol_refresh_market_pop_demand_maps` block |
| `gen_brief.py` | After editing `*.yaml` or `PROJECT_OVERVIEW.md` | `docs/knowledge/BRIEF.md` (also calls `gen_index.py` automatically) |
| `gen_index.py` | Called by `gen_brief.py`; or run manually after structural changes | `data/index/` symbol indexes (icons, triggers, effects, modifiers, loc keys) |
| `gen_scaffold.py` | When creating a new EU5 file (event, effect, trigger, modifier, etc.) | Syntactically valid skeleton file with TODO markers |
| `sync_reference.py` | After EU5 game updates to a new version | Mirrors reference game files with whitelist and size caps |
| `validate.py` | Before launching game (`--changed` flag); `--ai-report` for JSON output | Console validation report for anti-patterns, enums, modifiers, SOL baseline, and global_variable_map remove/add writes; exit code indicates pass/fail |
| `generate_sol_icon.py` | After setting an Images API relay key, or with `--convert-existing-png` for a local source image | Shared SOL icon DDS outputs for `icons/sol/sol_living_standard.dds`, `icons/map_modes/sol_living_standard.dds`, and `icons/situations/global_living_standard.dds`, plus PNG/metadata under `data/generated_icons/`; uses `dds_image_lib.py` for dependency-free PNG/DDS conversion |

The 1.3 SOL demand runtime no longer uses `gen_scarcity.py`, `gen_sol_ui.py`, `engel_export.py`, or `gen_goods_demand_overrides.py`; those tools are retained only as legacy/reference helpers unless explicitly revived.

## Data Files

| File | Purpose |
|---|---|
| `data/target_demand.csv` | Source of truth for calibrated baseline demand_add per pop type per good |
| `data/demand_price_table.csv` | Computed demand matrix used to hardcode SOL unit-pop consumption quantities |
| `data/goods_weights.csv` | Legacy substitute-group data; not active in EU5 1.3 SOL demand |
| `data/alpha_bracket_table.csv` | Legacy Engel curve data; not active in EU5 1.3 SOL demand |
| `data/alpha_generator_settings.json` | Legacy Engel generator settings |

## SOL System Architecture

- **Calibrated demand baseline** - `data/target_demand.csv` drives `src/stable/in_game/common/goods/z_SOL_pop_goods.txt`. These `demand_add` values remain the baseline that the SOL multiplier scales.
- **Hardcoded unit consumption constants** - `data/demand_price_table.csv` is converted into `src/stable/in_game/common/script_values/SOL_market_unit_consumption_values.txt`, storing net demand quantity for each pop type and good. Duplicate goods that appear in multiple old demand groups are counted once.
- **Yearly market spending maps** - `sol_refresh_market_pop_demand_maps` scans `every_market_in_world`, writes consumed-good counters keyed by market scope, and caches one unit-spending `global_variable_map` per pop type. For each consumed good, spending is computed as hardcoded consumption quantity times `min(market_price(goods), default_price(goods))`, so cheaper goods lower base spending while expensive goods do not inflate it above vanilla base price.
- **Yearly SOL maintenance caches** - `yearly_country_pulse` calls `sol_update_estate_building_maintenance` to scan every owned land location, cache the five SOL estate building counts, and subtract 1 gold per cached estate building from the matching stratum income. It then refreshes the country-level 1.3.4 poverty-consumption compensation factor; the same cache refresh runs during full GLS initialization after game start/load.
- **Monthly local demand modifier** - `monthly_country_pulse` calls `sol_update_local_pop_demand_modifiers`, which computes each owned land location's income-closed raw coefficient, multiplies the applied modifier by the cached country poverty-compensation factor, and applies `sol_local_pop_demand_modifier` for one month with `size = var:sol_location_pop_demand_modifier_size`.
- **Income-closed location scale** - Each location sums five gross stratum incomes, subtracts cached estate building maintenance to derive total net stratum income, applies the country's unified savings adjustment `(total savings / total savings target - 1) * 0.25`, and divides liquid funds by market-keyed base spending multiplied by `(1 + development / 20)`. Commoner base spending remains exact by internally using laborer, peasant, and soldier unit-spending maps. The raw result is used for demand UI display, while the applied `local_pop_demand` value is multiplied by the cached country-level 1.3.4 poverty-consumption compensation factor capped at 2x.
- **Country-level aggregation** - Location income, savings, base spending, development-adjusted base spending, liquid funds, final coefficient, and consumed market goods feed the situation panel and map overlay.
- **Map display** - The automatic situation map uses vanilla's `situation_data` path via `is_data_map = yes` plus the situation's own `tooltip`, `map_color`, and `legend_key` blocks. The `sol_living_standard` economy mapmode is a separate selectable mapmode using actual per-capita liquid funds (`sol_location_liquid_funds / local_sol_total_population`) for both coloring and tooltip bands: colors are linear from 0 to 0.5, with tooltip thresholds at 0.01, 0.1, and 0.5. The SOL situation panel auto-selects the mapmode with a zero-size GUI widget whose `_show` state calls `GetMapMode('sol_living_standard').SetMapMode` when `LateralView.IsShown` flips on each reopen; EU5 reference syntax still does not expose a verified situation script field that points to a custom mapmode tag.
- **Retired 1.2 chain** - Substitute groups, scarcity tiers, per-good redistribution weights, per-stratum Engel curves, market-hub scarcity corrections, and `sol_era_coeff` are no longer part of the active EU5 1.3 demand calculation.
