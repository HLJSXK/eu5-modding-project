# Living Standard vs Purchasing Power (2026-10-23)

Formula corrected on 2026-10-23 following the user's explicit definition and
`SOL_Living_Standard_Formula_Correction_Plan_20261023.md`. The recommended defaults
apply: zero floor, script-value modifier hooks, world-relative map colors, and
numeric SOL without a coin icon.

## Definitions

```
Living standard = annual liquid funds per thousand people + SOL modifier
Purchasing power = annual liquid funds per thousand / annual baseline consumption per thousand
```

| Quantity | Unit | Calculation |
|---|---|---|
| Annual liquid funds per thousand | gold / 1,000 people / year | monthly liquid funds × 12 / population (thousands) |
| Annual baseline consumption per thousand | gold / 1,000 people / year | monthly baseline total × 12 / population (thousands) |
| SOL modifier | annual gold-equivalent / 1,000 people | location script-value hook, currently 0 |
| Living standard | annual gold-equivalent / 1,000 people | amount, displayed directly; floored at 0 per estate/location |
| Purchasing power | ratio | monthly liquid funds / monthly baseline total; display ratio − 1 as percent |

Example: 2 thousand commoners with 0.3 monthly funds and 0.2 monthly baseline
have SOL **1.8** and PP **1.5 (+50%)**. 0.05 thousand nobles with 0.4 monthly
funds and 0.2 baseline have SOL **96** and PP **2 (+100%)**. National SOL is
8.4 / 2.05 ≈ **4.10**; national PP is 0.7 / 0.4 = **1.75**. A +3 modifier
raises commoner SOL to **4.8**, with PP unchanged.

With zero modifiers, SOL = PP × annual baseline per thousand. SOL is weighted
by population, never by baseline spending. People without baseline consumption
(including vanilla tribesmen) still have SOL. Only zero-population estates are
unset. Changing baseline baskets changes purchasing power, not SOL.

## Names

| Name | Scope | Meaning |
|---|---|---|
| `sol_location_local_sol_modifier_value` | location SV | shared annual per-thousand modifier, currently 0 |
| `sol_location_<estate>_local_sol_modifier_value` | location SV | estate override, defaults to shared hook |
| `sol_location_<estate>_sol_total`, `sol_location_sol_total` | location var | max(0, funds × annualization + modifier × population), and estate sum |
| `sol_location_sol` | location var | annual total / population, unset at zero population |
| `sol_ls_sol_total_<metric>` | country var | annual totals, metric = all or estate |
| `sol_ls_pop_<metric>` | country var | shared income population accumulator (thousands) |
| `sol_ls_sol`, `sol_ls_sol_<estate>` | country var | annual total / population |
| `sol_ls_sol_display` | country SV | SOL amount, 0 while unset |
| `sol_ls_world_sol[_<estate>]`, `sol_ls_top_sol[_<estate>]` | global var | population-weighted world average and leader's amount |
| `sol_map_living_standard_value` | location SV | SOL amount |
| `sol_map_living_standard_relative_value` | location SV | SOL / world average, for colors and tooltip tiers only |

The source is `scripts/sol_living_standard_source.py`; the economy generator
emits effects and `SOL_living_standard_values.txt` for stable and standalone.
Compatibility submods inherit them through their SOL dependency.

## Data flow

`sol_compute_location_pop_demand` finishes purchasing power and demand inputs,
then calls `sol_compute_location_living_standard` as its last statement. Both
solver preparation paths accumulate SOL immediately after income/population.
The country wrapper resets both before preparation and finalizes SOL after the
population sums are complete, before income finalization. Income finalization
does not reset population. No additional location traversal is added.

Humans refresh monthly; AI follows its solve cadence. World ranking reads country
caches at initialization, manual global refresh and each 1 January. Sorting,
tiers (<75% / >133% of world average), leaders and neighbours retain their
existing algorithms. Tribesmen with population now participate normally.

## Consumers

| Surface | Reads |
|---|---|
| Demand, solver and `local_pop_demand` | purchasing power only |
| Location tooltip, situation panel bars, HUD section 2, purchasing-power map | purchasing power; existing presentation retained |
| HUD tier/title and world/estate ranking, ranking map tooltip | SOL amount; no percent format or subtract-one conversion |
| Living-standard map and situation data map | local SOL; red at 0, yellow at world average, green at 3× world average |
| Local migration attraction and population growth | cached population-weighted local SOL; see gameplay feedback below |
| HUD section 1 income and YoY | per-capita net income, unchanged |

Map tooltip bands are ≥2× world average (high), ≥1× (medium), ≥0.5× (low),
otherwise very low. Until a positive world average exists, the map uses a named
fallback of 6 annual units. Values remain uncapped; colors saturate. The
situation panel retains its existing title and purchasing-power bars.

## Gameplay feedback (2026-10-23)

The user's current specification replaces the unavailable early plan. The source
is `scripts/sol_living_standard_source.py`; `gen_sol_economy_effects.py` also
generates three native location static modifiers and their English/Chinese names.
All five deploy targets receive the feature through stable/standalone or their
SOL dependency, independently of the economic-balance compatibility setting.

| Local SOL | Migration attraction | Population growth change |
|---|---|---|
| 0 | 0 | -0.1 percentage points |
| 0 < SOL < 0.1 | 0.02 × SOL | -0.1 percentage points |
| 0.1 ≤ SOL ≤ 10 | 0.02 × SOL | 0 |
| 10 < SOL < 25 | 0.02 × SOL | +0.1 percentage points |
| SOL ≥ 25 | +0.5 | +0.1 percentage points |
| No cache (including a solved zero-population location) | no modifier | no modifier |

This uses the location's population-weighted SOL amount, not national SOL, a
world-relative ratio, purchasing power, or the solver's demand coefficient.
The growth change is additive `local_population_growth = ±0.001`, not a
multiplier of the existing growth rate, and affects the whole location.

`sol_apply_location_living_standard_modifiers` runs inside the existing monthly
`sol_apply_local_pop_demand_modifiers` traversal. Native modifiers last one month
and use `mode = replace`. Crossing thresholds removes the opposite growth
modifier immediately; the inclusive middle range removes both. Missing SOL
clears all three modifiers. No new traversal or economic cache is introduced:
human SOL refreshes monthly; reduced-frequency AI retains its cached SOL until
its annual solve. Initial/start/load/manual refreshes apply feedback immediately.
An acquired location with no cache stays neutral until its scheduled solve;
existing local SOL follows the same cached-data policy as demand. Empty or
ownerless locations stop receiving renewal and expire within a month.

The SOL master switch clears feedback immediately in base, PP and M&T setting
callbacks, with monthly cleanup as a fallback. Standalone remains always enabled.
Tests execute the generated effects for strict thresholds, caps, repeated writes,
transitions, missing caches, local versus national values, local SOL modifiers,
unchanged demand inputs, AI cadence and disabling. Actual migration flows,
growth settlement and native modifier tooltips still require in-game acceptance.

Initial feature acceptance: all 146 script tests passed, including Windows UI regression
renders; all five targets passed generation consistency checks, and changed mod
files passed static validation. Shared/workspace knowledge, enum, route and
migration-coverage checks passed. No game session was launched for this change.

## Adding a building modifier (next step)

Edit `LOCAL_MODIFIER_ALL` or `LOCAL_MODIFIER_BY_ESTATE` in
`scripts/sol_living_standard_source.py` and regenerate with `gen_sol_chain.py`.
These are location script-value bodies in annual per-thousand units: +3 means
each present estate gains 3 SOL. They add no spendable funds. Never add them to
liquid funds, baseline spending or demand variables. A real engine modifier type
for buildings/events requires separate source verification and implementation.

## Verification

Runtime fixtures execute generated effects and assert annualization, population
weighting, the hand-calculated example, nonzero modifiers without demand changes,
floor behavior, zero-baseline tribesmen and zero population. Basket rescaling must
change PP while leaving SOL unchanged. Static checks cover all five deploy targets
for demand isolation, calculation order and numeric SOL formatting. Ranking/map
tests and Windows UI renders exercise shipped output. Native in-game hover, map
colors and ranking acceptance remain a separate check.

The previously removed dead `gls_country_sol_all`, per-capita map caches and
`GLS_SCORE_TT_*` keys remain retired. Dead pre-four-section builders in
`gen_sol_lshud.py` are unchanged; they do not ship.
