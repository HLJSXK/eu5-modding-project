# EU5 Mod - Project Overview

> This document is maintained by AI. Update it whenever mod features or directory structure change.
> Last updated: 2026-08-08 (separate country demand solver output)

## Project Identity

- Mod name: **Standard of Living (SOL)**
- Mod ID: `hades.sol` | Version: `260726` | Target: EU5 `1.3.11`
- Release versions use `YYMMDD`; `build.bat` stamps the selected target from the local date while `supported_game_version` remains independent
- Requires Community Mod Framework v2.*; the Glorp UI location window is copied into SOL rather than declared as a runtime dependency
- Active deploy targets: `src/stable/`, `src/sol_standalone/`, `src/sol_pp_compatibility_submod/`, `src/sol_mnt_compatibility_submod/`, and `src/sol_jtg_compatibility_submod/`

## Core Features

1. **Standard of Living (SOL) System** *(primary feature)* - Recalibrates baseline `demand_add` for 55 goods in `z_SOL_pop_goods.txt`, disables the engine-wide development demand multiplier, fully negates all nine vanilla per-good development thresholds, and sets `NPop.POP_NEEDS_INCOME_SCALE = 1` so strata pay the nominal cost of purchased goods instead of vanilla's 33% surcharge. It then applies a monthly location-level `local_pop_demand` modifier from `monthly_country_pulse`. The monthly coefficient is closed at country scope: local stratum income, estate-building maintenance, capped unified country savings pressure, local pop counts, and market-keyed base spending feed a four-class country solve. Locations are classified by nobles, clergy, burghers, or lower-strata relative over-representation against their own country's structure, with lower = commoners + tribesmen. High-confidence locations are assigned first; every class receives a deliberately tiny 1% raw-spending anchor, while the remaining 96% is directed toward strata whose raw spending exceeds their national target, proportional to that downward-compensation pressure. The class matrix is weighted by each location's raw coefficient and solved for nonnegative factors that multiply rather than replace location raw, preserving within-class local variation; positive factors have no gameplay cap, and raw is retained only when no hard-total candidate passes the strict four-stratum improvement gate. Detailed CMF logs expose structural preferences, negative pressures, dynamic capacity targets, relative profiles, exemplars, raw-weighted and normalized matrices, exact diagnostics, selected strategies, candidate counts, factors, final errors, and total residuals. Successful final coefficients are written back into each location cache for both display and the applied modifier. EU5 1.3.4 poverty-consumption reduction is left to the engine, so no country-level compensation factor is applied; the demand UI keeps showing the raw SOL target and the map keeps showing actual per-capita liquid funds. Yearly market scans cache one-unit pop spending per market using `min(market_price, default_price)`. The old substitute-goods, scarcity-tier, per-stratum Engel, and per-good redistribution chain is retired in EU5 1.3. The system feeds the Living Standard situation panel, its Black Death-style situation data map, the separate economy-category Living Standard mapmode with panel-scoped auto-selection and reset, and location GUI.

**Country-level nonnegative demand approximation** - Stable and standalone retain the exact 4x4 solve only as a diagnostic. Runtime performs constant-cost raw-error and matrix-rank prefilters; AI countries use the `improvement_l2` fast path over actual non-empty active sets (singleton sets are skipped when all four classes exist), while player countries retain all four L2 strategies plus finite-vertex `minimax_ratio`. L2 candidates eliminate the hard-total equation and solve at most 3x3 systems; minimax vertices use the same total elimination, solve at most 4x4 systems for free factors plus the worst-error variable, and reconstruct the anchor factor from unnormalized column totals. A strict four-stratum improvement gate selects the best available candidate; otherwise factors remain 1 and locations use `raw_fallback`. Runtime caches expose the exact status, selected strategy, gate, candidate counts, objective, average improvements, factors, final errors, and hard-total residual. Compatibility submods inherit this base effect and keep their local `REPLACE` overrides.

2. **Economic Balance & Anti-Snowballing** - Base tax efficiency defaults to -15% and is CMF-adjustable. Age escalation raises construction, RGO expansion, city/town upgrade, and food-consumption pressure across ages; by Age 6 it reaches -100% global building efficiency, +100% RGO expansion cost, +50% city/town upgrade cost, and +50% pop food consumption. Base RGO size is halved to 1, total-population RGO scaling is reduced, low-control locations receive a construction-efficiency penalty, and road prices are increased to gravel x2, paved x2, modern x3, railroad x5.

3. **Tax, Prices & Development** - Difficulty tax bonuses are halved for AI Hard/Very Hard and Player Easy/Very Easy. Diplomatic spending changes with used diplomatic capacity, cultural tradition reduces stability investment cost, and gold-transfer/action prices are rebalanced. GDP-to-development applies a yearly local development modifier scaled by local GDP, and AI countries can receive a small configurable devastation-recovery bonus.

4. **War & Combat (Harsher Wars)** - War exhaustion further reduces levy size, control, stability, legitimacy, and defensive capability. Total occupation adds +1.6 monthly war exhaustion on top of vanilla, and capital occupation adds +0.2 monthly war exhaustion on top of vanilla. The reduce-war-exhaustion cabinet action can be restricted to peacetime. Blockade, siege, occupation, hostile troops, looting, raiding, and razing modifiers are harsher for prosperity, control, construction, migration attraction, development, raw materials, and food.

5. **Food, Climate & Prosperity** - Normal winters and raised levies create harsher local food pressure, while Little Ice Age event penalties are softened to avoid runaway food-crisis spirals. Age escalation starts with mild prosperity scarcity and later returns prosperity in the late game.

6. **Colonial & Diplomatic Restrictions** - AI generally requires more than 500 tax base to create colonial charters; historical colonizers are exempt, and colonial nations can colonize only in their capital region. The player is not restricted by this rule. Asking another country to join a war costs 30 favors.

7. **CMF Settings & Migration Support** - Registers CMF settings for SOL pop demand, map coloring, economic balance, base tax efficiency, age escalation, stability discount, diplomatic spending, difficulty tax nerf, GDP-to-development, AI prosperity recovery, and war acceleration sub-features. Built-in after-lobby migration logic notifies human players when loading older saves and triggers full Living Standard cache refreshes on game start/load.

8. **Prosper or Perish Compact Compatibility Submod** - A separate final-loading target keeps full PP while narrowing full SOL to its income-based demand/UI, compact age construction and city/town costs, low-control construction penalty, base tax/diplomatic/stability rules, difficulty tax adjustments, configurable AI devastation recovery, non-conflicting prices, and selected war/expansion rules. It removes SOL residuals from PP-owned weather, Little Ice Age, base location, blockade, siege, occupation, and looting values; lets PP's later same-operation price file naturally replace SOL's repeated road-price fields; keeps SOL GDP-to-development disabled by default but exposes a compatibility-specific CMF opt-in; excludes non-compact age fields; preserves PP's zero lumber demand; and adds PP `victuals` to SOL calculations and both goods panels. Compatibility `demand_add` sets rounded Compact `victuals` net-demand targets of 0.05/0.015/0.035/0.0004/0.0002/0.0004 for nobles/clergy/burghers/laborers/peasants/soldiers, chosen from the PP-only spending-ratio comparison. Stable and standalone contain no PP-load detection or PP-only UI/value data.

9. **Just Trade Goods Compact Compatibility Submod** - A separate final-loading target applies SOL-style per-stratum scaling to the 22 direct-demand goods from Just Brass, Just Meat, Just Soap, Just Spices, and Just Cheese. The fixed multipliers are 1.05/0.45/1.75/0.02/0.10/0.025/0 for nobles/clergy/burghers/laborers/peasants/soldiers/tribesmen; scaled targets use clean 0.01/0.001/0.0001/0.00001 steps by magnitude, all 13 source wealth gates are fully negated, and slave demand remains unchanged. The current JTG sources have no development gates, and the Workshop audit enforces that invariant. It adds final JTG quantities to SOL market and country accounting and rebuilds both goods panels with all 77 demand goods using the JTG DDS icons. All five JTG mods are required, and this target is mutually exclusive with the SOL-PP compatibility target because both replace the same two SOL effects.

10. **MEIOU and Taxes Compatibility Submod** - A separate final-loading target makes M&T authoritative for economic balance by default while retaining SOL demand, Living Standard UI/map, migration, and non-conflicting war/colonial rules. It rebuilds all 55 SOL goods from complete M&T objects, inversely scales the seven SOL pop quantities against M&T prices, equalizes maize/millet/rice, keeps tools laborer demand at 0.0005, preserves M&T slave demand, and removes wealth/development gates. Its marked EPBM replacement leaves M&T country charges unchanged while caching attributable domestic maintenance on SOL's five location variables; foreign, crown, dhimmi, and Gaelic-tribes attribution is excluded by policy. A compatibility-specific CMF economic master defaults off and can explicitly re-enable SOL's trigger-gated base-tax, age-escalation, stability, diplomatic-spending, difficulty, GDP-to-development, and AI-recovery settings; dynamic values and callbacks remain available for that opt-in, while M&T continues to own goods, prices, and economic static modifiers.

11. **Built-in Glorp UI Location Window** - Full SOL's `location_window.gui` is copied from Glorp UI without behavioral edits and receives exactly one additional Living Standard tooltip button. The generator also copies Glorp's separately extracted vanilla location types, while the required `zoom_to_button` keeps Glorp's original name and behavior. SOL Standalone remains vanilla-based, while the M&T target still uses its own final window.

## Directory Structure

```text
eu5-modding-project/
|-- src/
|   |-- stable/                         full stable balance mod source
|       |-- .metadata/                  mod metadata with CMF dependency
|       |-- loading_screen/
|       |   `-- common/defines/       development-independent demand, nominal pop-needs expenditure, and refresh cap
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
|       |       |-- location_window.gui  exact Glorp UI window plus one SOL Living Standard tooltip button
|       |       |-- SOL_glorp_location_support.gui copied Glorp zoom-button type required by the window
|       |       |-- vanilla/             generated self-contained vanilla type support extracted by Glorp UI
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
|       `-- main_menu/                   Little Ice Age cleanup and CMF opt-in localization
|   `-- sol_mnt_compatibility_submod/    late-loading SOL / MEIOU and Taxes compatibility target
|       |-- .metadata/                   formal M&T and SOL dependencies
|       |-- in_game/common/              generated goods, EPBM, cleanup, CMM, war, and colonial overrides
|       |-- in_game/gui/                 M&T location window plus SOL income and Living Standard entry
|       `-- main_menu/                   M&T/vanilla static authority and CMF opt-in localization
|   `-- sol_jtg_compatibility_submod/    late-loading SOL / five-mod JTG compatibility target
|       |-- .metadata/                   SOL plus four formal JTG dependencies; Just Spices is manual
|       `-- in_game/                     generated demand, constants, effects, and 77-good GUI overrides
|-- docs/                              project knowledge, guides, technical notes
|-- scripts/                           Python codegen + validation
|-- tools/                             support tooling
|   |-- eu5_save_parser/               debug-save CSV exporter plus per-country/per-stratum demand-solution analyzer
|   `-- sol_demand_simulator/          legacy interactive demand simulator
|-- data/                              calibration CSVs, generated indexes, and legacy simulator data
|-- assets/                            images and media
|-- reference_game_files/              vanilla EU5 references
|-- reference_mods/                    community mod examples
`-- reference_official_defines/        official EU5 syntax/type definitions
```

## Script Reference

| Script | When to run | Output |
|---|---|---|
| `update_mod_version.py` | Automatically before every `build.bat` deployment; may also be run manually with `--target` and `--date` | Selected target metadata `version` fields in `YYMMDD` form |
| `gen_sol_chain.py` | Preferred one-shot SOL generation entry; `build.bat` runs it automatically for the selected target | Active SOL generated files for all five deploy targets |
| `gen_sol_pp_compat.py` | After changing SOL balance/demand/effects/UI or updating the PP reference; called by `gen_sol_chain.py` | Generated compact feature cleanup plus lumber correction, fixed rounded victuals demand/accounting, effect/GUI overrides, and the default-off PP GDP-to-development CMF opt-in with localization; also verifies that PP's road-price file still wins by same-operation filename order |
| `gen_sol_mnt_compat.py` | After changing SOL demand/effects/UI or updating the M&T reference; called by `gen_sol_chain.py` | Generated M&T-based goods, unit-consumption values, economic authority, EPBM location caches, CMF/action overrides, merged location window, and the default-off SOL economic opt-in settings/value callbacks with localization in `src/sol_mnt_compatibility_submod/` |
| `gen_sol_jtg_compat.py` | After changing `jtg_pop_demand.csv`, SOL demand/effects/UI, or updating the five JTG Workshop mods; called by `gen_sol_chain.py` | Generated JTG demand corrections, unit-consumption values, two effect replacements, and both 77-good GUI overrides in `src/sol_jtg_compatibility_submod/` |
| `sync_location_window.py` | After updating the Glorp UI reference; called by `gen_sol_chain.py` for `stable`/`all` | Exact Glorp stable location window plus one SOL tooltip button, together with unchanged extracted vanilla type support |
| `gen_sol_economy_effects.py` | After changing SOL economy emitters, the country solver, or demand data; called by `gen_sol_chain.py` for `stable`/`sol_standalone`/`all` | Emits the location aggregation/runtime `A_SOL_economy_effects.txt` and the separate fixed-dimensional `B_SOL_country_demand_solver.txt` for stable and standalone |
| `gen_pop_goods.py` | After editing `target_demand.csv` | `src/<target>/in_game/common/goods/z_SOL_pop_goods.txt` (calibrated demand_add baseline plus complete vanilla development-threshold negations; supports `--target stable\|sol_standalone\|all`) |
| `gen_demand_csv.py` | After demand calibration | `data/demand_price_table.csv` |
| `gen_market_unit_consumption.py` | After `gen_demand_csv.py`, or after changing SOL market base-spending logic | `src/<target>/in_game/common/script_values/SOL_market_unit_consumption_values.txt` (supports `--target stable\|sol_standalone\|all`); `gen_sol_economy_effects.py` embeds the matching `sol_refresh_market_pop_demand_maps` block |
| `generate_sol_location_window.py` | After vanilla `location_window.gui` changes; called by `gen_sol_chain.py` for `sol_standalone`/`all` | `src/sol_standalone/in_game/gui/location_window.gui` |
| `gen_brief.py` | After editing `*.yaml` or `PROJECT_OVERVIEW.md` | `docs/knowledge/BRIEF.md` (also calls `gen_index.py` automatically) |
| `gen_index.py` | Called by `gen_brief.py`; or run manually after structural changes | `data/index/` symbol indexes (icons, triggers, effects, modifiers, loc keys) |
| `gen_scaffold.py` | When creating a new EU5 file (event, effect, trigger, modifier, etc.) | Syntactically valid skeleton file with TODO markers; location static-modifier scaffolds emit delta-only `TRY_INJECT` blocks |
| `sync_reference.py` | After EU5 game updates to a new version | Mirrors reference game files with whitelist and size caps |
| `validate.py` | Before launching game (`--changed` checks only changed files under `src/`); `--ai-report` for JSON output | Console validation report for anti-patterns, enums, modifiers, SOL baseline, and global_variable_map remove/add writes; exit code indicates pass/fail |
| `generate_sol_icon.py` | After setting an Images API relay key, or with `--convert-existing-png` for a local source image; add `--overwrite` to refresh existing DDS outputs | Shared SOL icon DDS outputs for `icons/sol/sol_living_standard.dds`, `icons/map_modes/sol_living_standard.dds`, `icons/situations/global_living_standard.dds`, and `icons/modifier_types/sol_living_standard.dds`, plus PNG/metadata under `data/generated_icons/`; uses `dds_image_lib.py` for dependency-free, Clausewitz-compatible PNG/DDS conversion with full mip chains |

The 1.3 SOL demand runtime no longer uses `gen_scarcity.py`, `gen_sol_ui.py`, `engel_export.py`, or `gen_goods_demand_overrides.py`; those tools are retained only as legacy/reference helpers unless explicitly revived.

## Tool Reference

| Tool | When to run | Output |
|---|---|---|
| `python -m tools.eu5_save_parser` | On an uncompressed text save produced with EU5 debug mode when calibrating or auditing the location-class compensation model | Memory-maps the save and extracts only metadata, country tags and solver caches, population records, location/population links, and decoded `sol_location_*` caches; writes analysis-ready location and country CSVs, a diagnostic manifest, and an optional population-group CSV under `data/save_analysis/` by default |
| `python -m tools.eu5_save_parser.demand_analysis` | After exporting a debug save and when comparing the active location classifier with exact and gated approximate solves | Replays the current classifier or uses saved class ids, tries five total-constrained nonnegative approximation objectives, enforces the four-stratum gate by default (with explicit diagnostic bypasses for worsening and total-drift candidates), and writes country diagnostics including maximum worsening and total drift, one raw/approximate/exact error row per country and stratum, four-row stratum summaries, a strategy comparison, and metadata without collapsing nobles, clergy, burghers, and lower into one headline score |
| `docs/knowledge/SOL_Save_Analysis_20260808.md` | Session handoff and reproducibility reference for the save-demand analyzer | Records the three-save 1337/1386/1743 benchmark, definitions of valid locations and solver failure statuses, size-binned gate rates, and the measured cost/benefit of relaxed total preservation |

## Data Files

| File | Purpose |
|---|---|
| `data/target_demand.csv` | Source of truth for calibrated baseline demand_add and complete vanilla development-threshold negations |
| `data/demand_price_table.csv` | Computed demand matrix used to hardcode SOL unit-pop consumption quantities |
| `data/jtg_pop_demand.csv` | Reproducible Workshop IDs, prices, native pop demand, wealth gates, and development gates for the 22 JTG goods scaled by the SOL-JTG generator |
| `data/goods_weights.csv` | Legacy substitute-group data; not active in EU5 1.3 SOL demand |
| `data/alpha_bracket_table.csv` | Legacy Engel curve data; not active in EU5 1.3 SOL demand |
| `data/alpha_generator_settings.json` | Legacy Engel generator settings |
| `scripts/sol_economy_effects_source.py` | Python emitters for location raw demand, classification, country matrix aggregation, diagnostics, panels, and monthly application; target selection controls stable-only gold transfer and the standalone panel-stat variant |
| `scripts/sol_country_demand_solver_source.py` | Renderer for the separate country-level exact diagnostic and five-strategy nonnegative hard-total solver output; it keeps the fixed-dimensional KKT and reduced minimax blocks out of the location aggregation file |

## SOL System Architecture

- **Calibrated demand baseline** - `data/target_demand.csv` drives `src/stable/in_game/common/goods/z_SOL_pop_goods.txt` and `src/sol_standalone/in_game/common/goods/z_SOL_pop_goods.txt`. These `demand_add` values remain the baseline that the SOL multiplier scales. The generator requires exact negation of every vanilla `development_threshold`, while both targets set `NPop.DEVELOPMENT_SCALE_ON_DEMAND = 0` and `NPop.POP_NEEDS_INCOME_SCALE = 1`; the latter removes vanilla's 33% purchase-side surcharge so nominal goods cost matches SOL's strata-income accounting.
- **Hardcoded unit consumption constants** - `data/demand_price_table.csv` is converted into each target's `in_game/common/script_values/SOL_market_unit_consumption_values.txt`, storing net demand quantity for each pop type and good. Duplicate goods that appear in multiple old demand groups are counted once.
- **PP compatibility calculation** - The compatibility target uses fixed rounded `victuals` net-demand targets of 0.05/0.015/0.035/0.0004/0.0002/0.0004 for nobles/clergy/burghers/laborers/peasants/soldiers, selected after comparing each stratum's PP-only default-price spending ratio against six staple goods. It injects the positive or negative `demand_add` delta needed to reach those targets, and the same final quantities feed SOL accounting. It negates PP's `victuals` development threshold, forces all lumber quantities to zero, and explicitly `REPLACE`s the two SOL effects that need PP-aware market refresh and country goods aggregation. Existing SOL values/effects remain owned by the full SOL mod instead of being duplicated under later filenames. The compatibility-specific `sol__pp_gdp_dev` CMF setting defaults off, has no no-CMF fallback, and can explicitly restore SOL's yearly GDP-to-development pulse.
- **M&T compatibility calculation** - The M&T target uses complete M&T goods bodies and replaces only population-demand fields. Seven SOL quantities are inversely scaled by the vanilla/SOL to M&T default-price ratio and rounded to five decimals; maize, millet, and rice are equalized from combined SOL spending, tools laborer demand resolves to 0.0005, M&T slave quantities remain intact, and all wealth/development gates are removed. Matching generated constants and market refresh logic keep SOL accounting aligned with the final goods database. The compatibility-specific `sol__mnt_as_on` CMF master defaults off and gates the restored SOL economic subsettings; without CMF the trigger stays false, while an explicit opt-in reactivates only trigger-controlled SOL systems and leaves M&T's unconditional goods, price, and static-modifier authority intact.
- **JTG compatibility calculation** - `data/jtg_pop_demand.csv` records the 22 direct-demand JTG goods plus their source wealth/development gates. The compatibility generator applies fixed per-stratum SOL multipliers, rounds targets to clean 0.01/0.001/0.0001/0.00001 steps according to magnitude, injects the exact five-decimal demand deltas, fully negates every recorded threshold, and emits matching unit-consumption constants. It replaces only `sol_refresh_market_pop_demand_maps` and `gls_accumulate_panel_stats`, expands both goods grids from 55 to 77 entries, leaves five demand-free JTG goods and all slave demand untouched, and audits the CSV against an installed Workshop content root so new gates cannot be omitted silently.
- **Built-in Glorp UI merge** - `sync_location_window.py` validates Workshop `3601047146` as the expected source snapshot, copies its location window without modifying any existing line or behavior, and inserts one SOL Living Standard tooltip button before the migration spacer. It also copies Glorp's extracted vanilla location types unchanged; the local support file provides the original `zoom_to_button` name and behavior used by the copied window.
- **Generated economy effects** - `gen_sol_economy_effects.py` makes both base-target `A_SOL_economy_effects.txt` files and matching `B_SOL_country_demand_solver.txt` files. A owns location raw demand, classification, matrix aggregation, diagnostics, and modifier application; B owns the exact 4x4 diagnostic, Gaussian/KKT primitives, active-set candidates, minimax vertices, gate, and strategy selection. The split changes file ownership and loading size only; effect names and cross-file calls remain global and compatible submods continue to inherit the base effect.
- **Country solver runtime cost** - For `n` owned locations, classification still contributes one confidence sort `O(n log n)` plus linear scans and matrix aggregation `O(n)`. The solver now prefilters raw-gate-impossible and rank-1 countries in constant time; an AI country runs at most `2^k - 1` `improvement_l2` candidates for `k` non-empty class columns (11 when `k=4`), while a player retains the full strategy/minimax path with the same active-set filtering. L2 uses at most 3x3 elimination and minimax at most 4x4 elimination per vertex; the vertex count is unchanged. The total remains `O(n log n) + O(n) + O(1)` in location count. On the three save exports with SOL runtime caches, this fast path retained about 92% of baseline gated acceptances; `world_current` replay measured 9.26% of the former L2 scalar-operation core (about a 10.8x reduction).
- **Yearly market spending maps** - `sol_refresh_market_pop_demand_maps` scans `every_market_in_world`, writes consumed-good counters keyed by market scope, and caches one unit-spending `global_variable_map` per pop type. For each consumed good, spending is computed as hardcoded consumption quantity times `min(market_price(goods), default_price(goods))`, so cheaper goods lower base spending while expensive goods do not inflate it above vanilla base price.
- **Yearly SOL maintenance caches** - Normal SOL targets call `sol_update_estate_building_maintenance` to scan every owned land location, cache the five SOL estate building counts, and subtract 1 gold per cached estate building from matching stratum income. In the M&T target that scanner is disabled: M&T's own player-monthly/AI-yearly EPBM calculation writes charge-factor- and estate-power-adjusted domestic location costs into the same five variables without changing M&T country deductions.
- **Monthly local demand modifier** - `monthly_country_pulse` calls `sol_update_local_pop_demand_modifiers`, which computes each owned land location's income-closed raw coefficient, scores its four-stratum shares relative to nationwide shares, and classifies it with a confidence-ordered greedy pass. Classification capacity is measured as `raw * base`: every class receives 1% of nationwide raw spending as a deliberately tiny anchor, and the remaining 96% is divided among strata with `raw baseline - target > 0` in proportion to that downward pressure. Candidate affinity is reduced by only `0.05 * current_class_raw_capacity / dynamic_class_target`, preserving structurally pure positive-side anchors while most capacity flows to classes that need bounded reduction and can use factors near zero. The resulting matrix sums each class's raw-weighted stratum spending and feeds five hard-total nonnegative strategies over all nonempty active class sets. A successful gated factor multiplies every member location's raw coefficient before `sol_local_pop_demand_modifier` is applied for one month with `size = var:sol_location_pop_demand_modifier_size`; factor 1 preserves raw, 0 to 1 reduces it without crossing zero, and factors above 1 are uncapped. Missing classes leave empty matrix columns but no longer block approximation; singular, negative, numerical-residual, or gate failures are discarded, and raw remains only when no candidate improves all four strata. The first post-lobby refresh primes the estate-building cache once; yearly pulse keeps it current afterward.
- **Income-closed location scale** - Each location sums five gross stratum incomes, subtracts cached estate building maintenance to derive total net stratum income, applies the country's unified savings adjustment `(total savings / total savings target - 1) * 0.25` capped at `0.5` (+50%), and divides liquid funds directly by market-keyed base spending. Commoner base spending remains exact by internally using laborer, peasant, and soldier unit-spending maps. Development does not scale or gate demand. The raw result remains cached for diagnostics and fallback; successful class coefficients use dedicated caches and become final for classified locations, while negligible-base class-0 locations and failed country solves retain raw. No country-level poverty compensation factor is applied.
- **Country-level aggregation** - Location income, savings, base spending, liquid funds, solved final coefficient, and consumed market goods feed the situation panel and map overlay.
- **Map display** - The automatic situation map uses vanilla's `situation_data` path via `is_data_map = yes` plus the situation's own `tooltip`, `map_color`, and `legend_key` blocks. The `sol_living_standard` economy mapmode is a separate selectable mapmode using actual per-capita liquid funds (`sol_location_liquid_funds / local_sol_total_population`) for both coloring and tooltip bands: colors are linear from 0 to 0.5, with tooltip thresholds at 0.01, 0.1, and 0.5. The SOL situation panel creates a zero-size child whose `trigger_on_create` state calls `PdxGuiWidget.PushMapModeOverride('sol_living_standard')`; the widget-scoped override is removed when the situation-specific panel is destroyed, restoring the prior mapmode. EU5 reference syntax still does not expose a verified situation script field that points to a custom mapmode tag.
- **Retired 1.2 chain** - Substitute groups, scarcity tiers, per-good redistribution weights, per-stratum Engel curves, market-hub scarcity corrections, and `sol_era_coeff` are no longer part of the active EU5 1.3 demand calculation.
