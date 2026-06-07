# EU5 Mod - Project Overview

> This document is maintained by AI. Update it whenever mod features or directory structure change.
> Last updated: 2026-06-08 (estate building maintenance integrated into SOL income)

## Project Identity

- Mod name: **Standard of Living (SOL)**
- Mod ID: `hades.sol` | Version: `1.1.0` | Target: EU5 `1.*.*`
- Requires Community Mod Framework v2.*
- Single active mod; branches: `stable` (release) and `beta` (active development)

## Core Features

1. **War & Combat (Harsher Wars)** - War exhaustion has 3x greater impact on morale, levy size, stability, and legitimacy. Capital occupation yields +300% exhaustion, total occupation +400%. Increased sea-landing penalties and combat losses.

2. **Anti-Snowballing** - Building costs scale with age (+200% by Age 6). RGO expansion costs rise similarly. Base RGO size halved (1 vs. vanilla 2). Road construction costs: gravel x2, paved x3, modern x4, railroad x10.

3. **Tax Efficiency** - Base -5% tax efficiency applied to all countries. Bonuses remain meaningful but reduced, preventing tax-stacking dominance.

4. **Prosperity & Economic Decay** - Monthly prosperity decay decreases per age, modelling the world gradually becoming more prosperous. Ice Age event food penalties softened.

5. **Colonial Restrictions** - AI requires a tax base of 1000 (vs. vanilla 100) to colonize. Colonial nations restricted to capital-region colonization. Historical colonizers (Portugal, Spain, England, etc.) are exempt.

6. **Standard of Living (SOL) System** *(primary feature)* - Keeps the calibrated `demand_add` baseline in `z_SOL_pop_goods.txt`, then applies a monthly location-level `local_pop_demand` modifier from `monthly_country_pulse`. Per-pop, per-good unit spending constants are generated from `data/demand_price_table.csv`; yearly market scans cache which pop-consumed goods are active and the unit-pop base spending for each market. Yearly country pulses also cache five-estate building counts on each owned land location and subtract 1 gold of maintenance per estate building from that stratum's local income. Each monthly location coefficient is income-closed: local stratum income, unified country savings pressure, local pop counts, market-keyed base spending, and the engine's automatic development demand divisor `(1 + development / 20)` are combined so liquid funds divided by development-adjusted base spending becomes the final demand multiplier. The former substitute-goods, scarcity-tier, per-stratum Engel, and per-good redistribution chain is no longer active in EU5 1.3. Feeds back into streamlined location and country SOL GUI panels.

## Directory Structure

```text
eu5-modding-project/
|-- src/
|   `-- stable/                         active mod source
|       |-- .metadata/                  mod metadata
|       |-- in_game/
|       |   |-- common/
|       |   |   |-- age/                age-scaling building/prosperity modifiers
|       |   |   |-- auto_modifiers/     war exhaustion, tax efficiency penalties
|       |   |   |-- cabinet_actions/    war exhaustion reduction, institution spread
|       |   |   |-- diplomatic_costs/   rebalanced diplomatic action costs
|       |   |   |-- generic_actions/    colonial charter restrictions
|       |   |   |-- goods/              good definitions and SOL calibrated demand_add baseline
|       |   |   |-- on_action/          trigger hooks, including monthly local_pop_demand and yearly estate-building maintenance refresh
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
|       |       |-- panels/             situation panels
|       |       `-- scripted_widgets/
|       `-- main_menu/
|           |-- common/
|           |   |-- script_values/      tax efficiency bonus values
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
| `gen_brief.py` | After editing `*.yaml` or `PROJECT_OVERVIEW.md` | `docs/knowledge/BRIEF.md` (also calls `gen_index.py` automatically) |
| `gen_index.py` | Called by `gen_brief.py`; or run manually after structural changes | `data/index/` symbol indexes (icons, triggers, effects, modifiers, loc keys) |
| `gen_scaffold.py` | When creating a new EU5 file (event, effect, trigger, modifier, etc.) | Syntactically valid skeleton file with TODO markers |
| `sync_reference.py` | After EU5 game updates to a new version | Mirrors reference game files with whitelist and size caps |
| `validate.py` | Before launching game (`--changed` flag); `--ai-report` for JSON output | Console validation report for anti-patterns, enums, modifiers, SOL baseline, and global_variable_map remove/add writes; exit code indicates pass/fail |

The 1.3 SOL demand runtime no longer uses `gen_scarcity.py`, `gen_sol_ui.py`, `engel_export.py`, or `gen_goods_demand_overrides.py`; those tools are retained only as legacy/reference helpers unless explicitly revived.

## Data Files

| File | Purpose |
|---|---|
| `data/target_demand.csv` | Source of truth for calibrated baseline demand_add per pop type per good |
| `data/demand_price_table.csv` | Computed demand matrix used to hardcode SOL unit-pop spending constants |
| `data/goods_weights.csv` | Legacy substitute-group data; not active in EU5 1.3 SOL demand |
| `data/alpha_bracket_table.csv` | Legacy Engel curve data; not active in EU5 1.3 SOL demand |
| `data/alpha_generator_settings.json` | Legacy Engel generator settings |

## SOL System Architecture

- **Calibrated demand baseline** - `data/target_demand.csv` drives `src/stable/in_game/common/goods/z_SOL_pop_goods.txt`. These `demand_add` values remain the baseline that the SOL multiplier scales.
- **Hardcoded unit spending constants** - `data/demand_price_table.csv` is converted into `src/stable/in_game/common/script_values/SOL_market_unit_spending_values.txt`, storing price times net demand for each pop type and good. Duplicate goods that appear in multiple old demand groups are counted once.
- **Yearly market spending maps** - `sol_refresh_market_pop_demand_maps` scans `every_market_in_world`, checks `demands_goods_by_pops`, writes one `global_variable_map` per pop type keyed by market scope, and writes consumed-goods `global_variable_map` flags keyed by the same market scope for GUI display.
- **Yearly estate building maintenance** - `yearly_country_pulse` calls `sol_update_estate_building_maintenance` to scan every owned land location, cache the five SOL estate building counts, and subtract 1 gold per cached estate building from the matching stratum income.
- **Monthly local demand modifier** - `monthly_country_pulse` calls `sol_update_local_pop_demand_modifiers`, which computes each owned land location's income-closed coefficient and applies `sol_local_pop_demand_modifier` for one month with `size = var:sol_location_pop_demand_modifier_size`.
- **Income-closed location scale** - Each location sums five displayed stratum incomes net of cached estate building maintenance, applies the country's unified savings adjustment `(total savings / total savings target - 1) * 0.1`, divides liquid funds by market-keyed base spending multiplied by `(1 + development / 20)`, and exposes the corrected result as `local_pop_demand`. Commoner base spending remains exact by internally using laborer, peasant, and soldier unit-spending maps.
- **Country-level aggregation** - Location income, savings, base spending, development-adjusted base spending, liquid funds, final coefficient, and consumed market goods feed the situation panel and map overlay.
- **Retired 1.2 chain** - Substitute groups, scarcity tiers, per-good redistribution weights, per-stratum Engel curves, market-hub scarcity corrections, and `sol_era_coeff` are no longer part of the active EU5 1.3 demand calculation.
