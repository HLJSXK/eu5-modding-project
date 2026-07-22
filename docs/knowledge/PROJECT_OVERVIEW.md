# EU5 Mod - Project Overview

> This document is maintained by AI. Update it whenever mod features or directory structure change.
> Last updated: 2026-07-22 (SOL-JTG compact compatibility target)

## Project Identity

- Mod name: **Standard of Living (SOL)**
- Mod ID: `hades.sol` | Version: `1.3.11` | Target: EU5 `1.3.11`
- Requires Community Mod Framework v2.*
- Active deploy targets: `src/stable/`, `src/sol_standalone/`, `src/sol_pp_compatibility_submod/`, and `src/sol_jtg_compatibility_submod/`

## Core Features

1. **Standard of Living (SOL) System** *(primary feature)* - Recalibrates baseline `demand_add` for 55 goods in `z_SOL_pop_goods.txt`, disables the engine-wide development demand multiplier, fully negates all nine vanilla per-good development thresholds, then applies a monthly location-level `local_pop_demand` modifier from `monthly_country_pulse`. The monthly coefficient is income-closed: local stratum income, estate-building maintenance, unified country savings pressure, local pop counts, and market-keyed base spending combine into the displayed demand multiplier without development-based scaling or gates. EU5 1.3.4 poverty-consumption reduction is countered by one country-level compensation factor computed from national stratum income/expense ratios on full refresh and yearly country pulse, while demand UI displays keep showing the uncompensated SOL target and map displays show actual per-capita liquid funds. Yearly market scans cache one-unit pop spending per market using `min(market_price, default_price)`. The old substitute-goods, scarcity-tier, per-stratum Engel, and per-good redistribution chain is retired in EU5 1.3. The system feeds the Living Standard situation panel, its Black Death-style situation data map, the separate economy-category Living Standard mapmode with panel auto-selection, and location GUI.

2. **Economic Balance & Anti-Snowballing** - Base tax efficiency defaults to -15% and is CMF-adjustable. Age escalation raises construction, RGO expansion, city/town upgrade, and food-consumption pressure across ages; by Age 6 it reaches -100% global building efficiency, +100% RGO expansion cost, +50% city/town upgrade cost, and +50% pop food consumption. Base RGO size is halved to 1, total-population RGO scaling is reduced, low-control locations receive a construction-efficiency penalty, and road prices are increased to gravel x2, paved x2, modern x3, railroad x5.

3. **Tax, Prices & Development** - Difficulty tax bonuses are halved for AI Hard/Very Hard and Player Easy/Very Easy. Diplomatic spending changes with used diplomatic capacity, cultural tradition reduces stability investment cost, and gold-transfer/action prices are rebalanced. GDP-to-development applies a yearly local development modifier scaled by local GDP, and AI countries can receive a small configurable devastation-recovery bonus.

4. **War & Combat (Harsher Wars)** - War exhaustion further reduces levy size, control, stability, legitimacy, and defensive capability. Total occupation adds +1.6 monthly war exhaustion on top of vanilla, and capital occupation adds +0.2 monthly war exhaustion on top of vanilla. The reduce-war-exhaustion cabinet action can be restricted to peacetime. Blockade, siege, occupation, hostile troops, looting, raiding, and razing modifiers are harsher for prosperity, control, construction, migration attraction, development, raw materials, and food.

5. **Food, Climate & Prosperity** - Normal winters and raised levies create harsher local food pressure, while Little Ice Age event penalties are softened to avoid runaway food-crisis spirals. Age escalation starts with mild prosperity scarcity and later returns prosperity in the late game.

6. **Colonial & Diplomatic Restrictions** - AI generally requires more than 500 tax base to create colonial charters; historical colonizers are exempt, and colonial nations can colonize only in their capital region. The player is not restricted by this rule. Asking another country to join a war costs 30 favors.

7. **CMF Settings & Migration Support** - Registers CMF settings for SOL pop demand, map coloring, economic balance, base tax efficiency, age escalation, stability discount, diplomatic spending, difficulty tax nerf, GDP-to-development, AI prosperity recovery, and war acceleration sub-features. Built-in after-lobby migration logic notifies human players when loading older saves and triggers full Living Standard cache refreshes on game start/load.

8. **Prosper or Perish Compact Compatibility Submod** - A separate final-loading target keeps full PP while narrowing full SOL to its income-based demand/UI, compact age construction and city/town costs, low-control construction penalty, base tax/diplomatic/stability rules, difficulty tax adjustments, configurable AI devastation recovery, non-conflicting prices, and selected war/expansion rules. It removes SOL residuals from PP-owned weather, Little Ice Age, base location, road price, blockade, siege, occupation, and looting values; disables SOL GDP-to-development and excluded age fields; preserves PP's zero lumber demand; and adds PP `victuals` to SOL calculations and both goods panels. Compatibility `demand_add` sets rounded Compact `victuals` net-demand targets of 0.05/0.015/0.035/0.0004/0.0002/0.0004 for nobles/clergy/burghers/laborers/peasants/soldiers, chosen from the PP-only spending-ratio comparison. Stable and standalone contain no PP-load detection or PP-only UI/value data.

9. **Just Trade Goods Compact Compatibility Submod** - A separate final-loading target applies SOL-style per-stratum scaling to the 22 direct-demand goods from Just Brass, Just Meat, Just Soap, Just Spices, and Just Cheese. The fixed multipliers are 1.05/0.45/1.75/0.02/0.10/0.025/0 for nobles/clergy/burghers/laborers/peasants/soldiers/tribesmen; scaled targets use clean 0.01/0.001/0.0001/0.00001 steps by magnitude, and slave demand remains unchanged. It adds final JTG quantities to SOL market and country accounting and rebuilds both goods panels with all 77 demand goods using the JTG DDS icons. All five JTG mods are required, and this target is mutually exclusive with the SOL-PP compatibility target because both replace the same two SOL effects.

## Directory Structure

```text
eu5-modding-project/
|-- src/
|   |-- stable/                         full stable balance mod source
|       |-- .metadata/                  mod metadata
|       |-- loading_screen/
|       |   `-- common/defines/       development-independent demand and refresh cap
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
|           |-- gfx/interface/icons/    generated SOL icon targets for shared UI, map modes, modifier types, and situations
|           |-- gui/                   message category definitions
|           |-- common/
|           |   |-- modifier_icons/      SOL modifier-type icon mappings
|           |   `-- static_modifiers/   country, location, province modifiers
|           `-- localization/
|   `-- sol_standalone/                 SOL-only deploy target generated from the shared SOL chain where possible
|       |-- .metadata/                  standalone mod metadata
|       |-- loading_screen/common/defines/
|       |-- in_game/
|       |   |-- common/                 SOL goods, on_actions, resolutions, script values/effects, situation, map mode
|       |   |-- gfx/map/map_modes/      SOL map mode
|       |   `-- gui/                    generated location window plus shared SOL panels/tooltips
|       `-- main_menu/
|           |-- common/                 SOL modifier icons and static modifiers
|           |-- gfx/interface/icons/    shared generated SOL icon DDS targets
|           |-- gui/                    SOL message category
|           `-- localization/           SOL economy localization
|   `-- sol_pp_compatibility_submod/     late-loading SOL / Prosper or Perish compatibility target
|       |-- .metadata/                   compatibility metadata and SOL dependency
|       |-- in_game/common/              lumber correction and PP-aware SOL calculation overrides
|       |-- in_game/gui/                 victuals-aware location and situation panel overrides
|       `-- main_menu/common/            Little Ice Age residual cleanup
|   `-- sol_jtg_compatibility_submod/    late-loading SOL / five-mod JTG compatibility target
|       |-- .metadata/                   SOL plus four formal JTG dependencies; Just Spices is manual
|       `-- in_game/                     generated demand, constants, effects, and 77-good GUI overrides
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
| `gen_sol_chain.py` | Preferred one-shot SOL generation entry; `build.bat` runs it automatically for the selected target | Active SOL generated files for all four deploy targets |
| `gen_sol_pp_compat.py` | After changing SOL balance/demand/effects/UI or updating the PP reference; called by `gen_sol_chain.py` | Generated compact feature cleanup plus lumber correction, fixed rounded victuals demand/accounting, effect, and GUI overrides in `src/sol_pp_compatibility_submod/` |
| `gen_sol_jtg_compat.py` | After changing `jtg_pop_demand.csv`, SOL demand/effects/UI, or updating the five JTG Workshop mods; called by `gen_sol_chain.py` | Generated JTG demand corrections, unit-consumption values, two effect replacements, and both 77-good GUI overrides in `src/sol_jtg_compatibility_submod/` |
| `gen_pop_goods.py` | After editing `target_demand.csv` | `src/<target>/in_game/common/goods/z_SOL_pop_goods.txt` (calibrated demand_add baseline plus complete vanilla development-threshold negations; supports `--target stable\|sol_standalone\|all`) |
| `gen_demand_csv.py` | After demand calibration | `data/demand_price_table.csv` |
| `gen_market_unit_consumption.py` | After `gen_demand_csv.py`, or after changing SOL market base-spending logic | `src/<target>/in_game/common/script_values/SOL_market_unit_consumption_values.txt`; `sol_refresh_market_pop_demand_maps` block (supports `--target stable\|sol_standalone\|all`) |
| `generate_sol_location_window.py` | After vanilla `location_window.gui` changes; called by `gen_sol_chain.py` for `sol_standalone`/`all` | `src/sol_standalone/in_game/gui/location_window.gui` |
| `gen_brief.py` | After editing `*.yaml` or `PROJECT_OVERVIEW.md` | `docs/knowledge/BRIEF.md` (also calls `gen_index.py` automatically) |
| `gen_index.py` | Called by `gen_brief.py`; or run manually after structural changes | `data/index/` symbol indexes (icons, triggers, effects, modifiers, loc keys) |
| `gen_scaffold.py` | When creating a new EU5 file (event, effect, trigger, modifier, etc.) | Syntactically valid skeleton file with TODO markers; location static-modifier scaffolds emit delta-only `TRY_INJECT` blocks |
| `sync_reference.py` | After EU5 game updates to a new version | Mirrors reference game files with whitelist and size caps |
| `validate.py` | Before launching game (`--changed` checks only changed files under `src/`); `--ai-report` for JSON output | Console validation report for anti-patterns, enums, modifiers, SOL baseline, and global_variable_map remove/add writes; exit code indicates pass/fail |
| `generate_sol_icon.py` | After setting an Images API relay key, or with `--convert-existing-png` for a local source image; add `--overwrite` to refresh existing DDS outputs | Shared SOL icon DDS outputs for `icons/sol/sol_living_standard.dds`, `icons/map_modes/sol_living_standard.dds`, `icons/situations/global_living_standard.dds`, and `icons/modifier_types/sol_living_standard.dds`, plus PNG/metadata under `data/generated_icons/`; uses `dds_image_lib.py` for dependency-free, Clausewitz-compatible PNG/DDS conversion with full mip chains |

The 1.3 SOL demand runtime no longer uses `gen_scarcity.py`, `gen_sol_ui.py`, `engel_export.py`, or `gen_goods_demand_overrides.py`; those tools are retained only as legacy/reference helpers unless explicitly revived.

## Data Files

| File | Purpose |
|---|---|
| `data/target_demand.csv` | Source of truth for calibrated baseline demand_add and complete vanilla development-threshold negations |
| `data/demand_price_table.csv` | Computed demand matrix used to hardcode SOL unit-pop consumption quantities |
| `data/jtg_pop_demand.csv` | Reproducible Workshop IDs, prices, and native pop demand for the 22 JTG goods scaled by the SOL-JTG generator |
| `data/goods_weights.csv` | Legacy substitute-group data; not active in EU5 1.3 SOL demand |
| `data/alpha_bracket_table.csv` | Legacy Engel curve data; not active in EU5 1.3 SOL demand |
| `data/alpha_generator_settings.json` | Legacy Engel generator settings |

## SOL System Architecture

- **Calibrated demand baseline** - `data/target_demand.csv` drives `src/stable/in_game/common/goods/z_SOL_pop_goods.txt` and `src/sol_standalone/in_game/common/goods/z_SOL_pop_goods.txt`. These `demand_add` values remain the baseline that the SOL multiplier scales. The generator requires exact negation of every vanilla `development_threshold`, while both targets set `NPop.DEVELOPMENT_SCALE_ON_DEMAND = 0`.
- **Hardcoded unit consumption constants** - `data/demand_price_table.csv` is converted into each target's `in_game/common/script_values/SOL_market_unit_consumption_values.txt`, storing net demand quantity for each pop type and good. Duplicate goods that appear in multiple old demand groups are counted once.
- **PP compatibility calculation** - The compatibility target uses fixed rounded `victuals` net-demand targets of 0.05/0.015/0.035/0.0004/0.0002/0.0004 for nobles/clergy/burghers/laborers/peasants/soldiers, selected after comparing each stratum's PP-only default-price spending ratio against six staple goods. It injects the positive or negative `demand_add` delta needed to reach those targets, and the same final quantities feed SOL accounting. It negates PP's `victuals` development threshold, forces all lumber quantities to zero, and explicitly `REPLACE`s the two SOL effects that need PP-aware market refresh and country goods aggregation. Existing SOL values/effects remain owned by the full SOL mod instead of being duplicated under later filenames.
- **JTG compatibility calculation** - `data/jtg_pop_demand.csv` records the 22 direct-demand JTG goods. The compatibility generator applies fixed per-stratum SOL multipliers, rounds targets to clean 0.01/0.001/0.0001/0.00001 steps according to magnitude, injects the exact five-decimal deltas, and emits matching unit-consumption constants. It replaces only `sol_refresh_market_pop_demand_maps` and `gls_accumulate_panel_stats`, expands both goods grids from 55 to 77 entries, leaves five demand-free JTG goods and all slave demand untouched, and can audit the CSV against an installed Workshop content root.
- **Yearly market spending maps** - `sol_refresh_market_pop_demand_maps` scans `every_market_in_world`, writes consumed-good counters keyed by market scope, and caches one unit-spending `global_variable_map` per pop type. For each consumed good, spending is computed as hardcoded consumption quantity times `min(market_price(goods), default_price(goods))`, so cheaper goods lower base spending while expensive goods do not inflate it above vanilla base price.
- **Yearly SOL maintenance caches** - `yearly_country_pulse` calls `sol_update_estate_building_maintenance` to scan every owned land location, cache the five SOL estate building counts, and subtract 1 gold per cached estate building from the matching stratum income. It then refreshes the country-level 1.3.4 poverty-consumption compensation factor; the same cache refresh runs during full GLS initialization after game start/load.
- **Monthly local demand modifier** - `monthly_country_pulse` calls `sol_update_local_pop_demand_modifiers`, which computes each owned land location's income-closed raw coefficient, multiplies the applied modifier by the cached country poverty-compensation factor, and applies `sol_local_pop_demand_modifier` for one month with `size = var:sol_location_pop_demand_modifier_size`.
- **Income-closed location scale** - Each location sums five gross stratum incomes, subtracts cached estate building maintenance to derive total net stratum income, applies the country's unified savings adjustment `(total savings / total savings target - 1) * 0.25`, and divides liquid funds directly by market-keyed base spending. Commoner base spending remains exact by internally using laborer, peasant, and soldier unit-spending maps. Development does not scale or gate demand. The raw result is used for demand UI display, while the applied `local_pop_demand` value is multiplied by the cached country-level 1.3.4 poverty-consumption compensation factor capped at 2x.
- **Country-level aggregation** - Location income, savings, base spending, liquid funds, final coefficient, and consumed market goods feed the situation panel and map overlay.
- **Map display** - The automatic situation map uses vanilla's `situation_data` path via `is_data_map = yes` plus the situation's own `tooltip`, `map_color`, and `legend_key` blocks. The `sol_living_standard` economy mapmode is a separate selectable mapmode using actual per-capita liquid funds (`sol_location_liquid_funds / local_sol_total_population`) for both coloring and tooltip bands: colors are linear from 0 to 0.5, with tooltip thresholds at 0.01, 0.1, and 0.5. The SOL situation panel auto-selects the mapmode with a zero-size GUI widget whose `_show` state calls `GetMapMode('sol_living_standard').SetMapMode` when `LateralView.IsShown` flips on each reopen; EU5 reference syntax still does not expose a verified situation script field that points to a custom mapmode tag.
- **Retired 1.2 chain** - Substitute groups, scarcity tiers, per-good redistribution weights, per-stratum Engel curves, market-hub scarcity corrections, and `sol_era_coeff` are no longer part of the active EU5 1.3 demand calculation.
