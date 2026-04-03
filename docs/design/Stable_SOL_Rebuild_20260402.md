# SOL (Standard of Living) Rebuild (2026-04-02)

## Background

The previous implementation recalculated all countries and ranked them globally every monthly tick. This was expensive and provided limited gameplay value for the EU5 timeline.

The SOL system was previously developed in two separate streams ("Global SOL" for country-level aggregates and a per-province stream), but these are now treated as a single, continuous feature: **Standard of Living (SOL)**. The "Global" prefix has been retired from all file names and user-facing text.

## Rebuild Goals

1. Move repeated country-internal calculations out of per-location script values.
2. Remove cross-country ranking logic and redesign UI for current-country decision support.
3. Let the situation system drive update cadence (monthly/yearly cache), instead of always-on global recomputation.
4. Keep map feedback useful with location-level cached values.

## Naming Convention

- **SOL** = Standard of Living — the unified name for this mod's living standard system.
- Files use `standard_of_living` as the base name (e.g. `standard_of_living.txt`, `standard_of_living_effects.txt`).
- The EU5 situation ID remains `global_living_standard` internally (changing it requires cascading updates; deferred).
- **Engine constraint:** The situation panel GUI file must be named after the situation ID. So `gui/panels/situation/global_living_standard.gui` cannot be renamed until the situation ID is also renamed.
- `gls_` variable prefix = **country-level** cached/aggregate variables — intentionally kept to reflect scope.
- `local_` variable prefix = **per-location** computed variables — intentionally kept to reflect scope.
- No "Global" distinction in user-facing labels or file names.

## New Update Pipeline

### Monthly (country cache)

- Effect: `gls_update_country_monthly_cache`
- Scope: country
- Cached variables:
  - `gls_country_wealth_anchor_cached`
  - `gls_nobles_savings_pressure`
  - `gls_clergy_savings_pressure`
  - `gls_burghers_savings_pressure`
  - `gls_commoner_savings_pressure`
  - `gls_tribesmen_savings_pressure`

`pop_wealth` now reads these country variables first, then falls back to old local formulas if cache is missing.

### Yearly (January, location + national aggregate)

- Effect: `gls_update_country_yearly_cache`
- Scope: country
- Location cache:
  - For each owned location, set `gls_location_avg_scale` from `local_average_gdp_per_capita_scale`.
- National aggregate:
  - Average SOL for all population and five strata.
  - Average location scale and location count.
  - Population-weighted aggregation model.

### Orchestrator

- Situation `on_monthly` executes `gls_update_country_visual_cache` for countries with population.
- `gls_update_country_visual_cache` always runs monthly cache and conditionally runs yearly cache when `current_month = 1`.

## Data Model

### Location-level key/value (requested)

- Key: owned location (scope)
- Value: location variable `gls_location_avg_scale`

This behaves as a location map and is used for map coloring and hover tooltip text.

### Country-level values for panel

- SOL values:
  - `gls_country_sol_all`
  - `gls_country_sol_nobles`
  - `gls_country_sol_clergy`
  - `gls_country_sol_burghers`
  - `gls_country_sol_commoners`
  - `gls_country_sol_tribesmen`
- Intermediate values:
  - `gls_country_location_avg_scale`
  - `gls_location_count`
  - `gls_country_wealth_anchor_cached`
  - five savings pressure variables

## GUI Redesign

File: `src/stable/in_game/gui/panels/situation/global_living_standard.gui` (filename must match situation ID `global_living_standard`)

- Removed global top3 ranking cards.
- Added current-country overview card:
  - all-pop average SOL
  - five strata average SOL
- Added intermediate-variable card:
  - average location scale
  - location count
  - wealth anchor
  - five monthly cached savings pressures

## Situation Map Behavior

File: `src/stable/in_game/common/situations/standard_of_living.txt`

- Tooltip now shows location cached value via localization key.
- Map colors use `gls_location_avg_scale` bands:
  - high: `>= 1.25`
  - medium: `>= 1.05`
  - low: `> 0`
  - else default
- Added legend keys for high/medium/low.

## Files Changed

- `src/stable/in_game/common/script_values/pop_wealth.txt`
- `src/stable/in_game/common/script_values/standard_of_living.txt`
- `src/stable/in_game/common/scripted_effects/standard_of_living_effects.txt`
- `src/stable/in_game/common/situations/standard_of_living.txt`
- `src/stable/in_game/common/resolutions/standard_of_living_resolution.txt`
- `src/stable/in_game/gui/panels/situation/global_living_standard.gui`
- `src/stable/main_menu/localization/simp_chinese/standard_of_living_l_simp_chinese.yml`
- `src/stable/main_menu/localization/english/standard_of_living_l_english.yml`

## Notes

1. This rebuild intentionally deprioritizes global ranking and cross-country comparison.
2. The panel now targets country management and debugging of SOL mechanics.
3. If needed later, global ranking can be reintroduced as an optional manual debug action rather than monthly default behavior.
