# Living Standard vs Purchasing Power (2026-10-23)

## Why

Until this change the mod had one number, purchasing power, and showed it under the name "living standard". The next step will let buildings raise living standard without giving pops any extra money, so the two concepts now have separate variables, separate consumers and a test that keeps them apart. With every local bonus at zero (the shipped state) living standard equals purchasing power exactly, so no gameplay number changes except the HUD tier, the world ranking and the two living-standard maps, which were previously computed from per-capita income and now follow living standard.

## Definitions

Both quantities are ratios in units of the baseline basket: 1 means the baseline basket is exactly reached, 0 means nothing. Displays show ratio − 1 (0% baseline, −100% nothing).

**Purchasing power** = liquid funds / baseline spending. Liquid funds are net estate income after building maintenance, times the country savings-pressure multiplier. This is what pops can buy, so it alone drives demand: `sol_location_raw_demand_scale`, the country solver targets (`sol_country_demand_target_*` are sums of liquid funds), `sol_location_final_demand_scale` and the applied `local_pop_demand` modifier.

**Living standard (SOL)** = purchasing power + local bonus. The bonus is welfare that does not pass through the market, valued in baseline baskets (0.1 = +10 percentage points). It adds no money and is never read by demand.

Aggregation uses an SOL-equivalent value per estate:

```
sol_location_<estate>_sol_equivalent = max(0, liquid_funds_<estate> + bonus_<estate> × base_spending_<estate>)
sol_location_sol_equivalent          = Σ estates
country SOL (sol_ls_sol[_<estate>])  = Σ sol_equivalent / Σ base_spending   (unset when Σ base = 0)
```

So a country's or estate's SOL is weighted by baseline spending exactly like its purchasing power. The world average used for tiers is population-weighted over ranked countries, as the income average was before.

## Data flow

`sol_compute_location_pop_demand` computes purchasing power and all demand inputs, then calls `sol_compute_location_living_standard` as its very last statement. Nothing in the demand pass reads what that effect writes. Inside the existing solver preparation pass, `sol_ls_accumulate_country_living_standard` runs right after `sol_ls_accumulate_country_income`; `sol_solve_country_pop_demand` resets the country accumulators after the income reset and finalizes them before the income finalize. No extra location traversal is added. Humans refresh monthly and AI on its solve cadence (yearly by default), the same as income and purchasing power.

## Consumers

| Surface | Reads | Notes |
|---|---|---|
| Demand: raw/final scale, solver, `local_pop_demand` modifier | purchasing power | must never read SOL |
| Location tooltip and situation panel bars ("购买力" rows) | purchasing power | UI unchanged by user decision; the panel title still says 生活水平 |
| HUD section 2 and its tooltip | purchasing power | |
| `sol_purchasing_power` map mode | purchasing power | |
| HUD tier medallion and "生活水平：高/中/低" title | country SOL vs world SOL | title now also prints the SOL index; the tier is relative to the world and refreshed on 1 January, the printed index is absolute and refreshed with the country's solve, so "Low +40%" is possible in a rich world |
| World ranking (HUD section 4, its tooltip, `sol_ranking` map, country map tooltip) | country and estate SOL | ladder bars = SOL / top SOL; values shown as SOL index; an estate with population but no baseline spending (vanilla tribesmen) has no SOL, shows a dash and is not ranked |
| `sol_living_standard` map mode and the situation data map | location SOL | −100% / 0% / +200% anchors like the purchasing-power map; tooltip bands ≥ +100%, ≥ 0%, ≥ −50%, below; a cached location with no baseline consumption gets a separate line |
| HUD section 1 income and YoY | per-capita net income | unchanged; income is a third, separate figure |

## Names

| Name | Scope | Meaning |
|---|---|---|
| `sol_location_local_sol_bonus_value` | location SV | bonus for every estate (currently `value = 0`) |
| `sol_location_<estate>_local_sol_bonus_value` | location SV | per-estate bonus; defaults to the shared one |
| `sol_location_<estate>_sol_equivalent`, `sol_location_sol_equivalent` | location var | SOL-equivalent value; not spendable money |
| `sol_ls_sol_equivalent_<metric>`, `sol_ls_sol_base_<metric>` | country var | accumulators, `<metric>` = all or estate |
| `sol_ls_sol`, `sol_ls_sol_<estate>` | country var | SOL ratio |
| `sol_ls_sol_index_display` | country SV | national ratio − 1 for the tier title (0 while unset) |
| `sol_ls_world_sol[_<estate>]`, `sol_ls_top_sol[_<estate>]` | global var | population-weighted world SOL and the leader's SOL |
| `sol_map_living_standard_value`, `…_below_factor`, `…_above_factor` | location SV | map value and lerp factors |

The source is `scripts/sol_living_standard_source.py`; `gen_sol_economy_effects.py` appends its effects to `A_SOL_economy_effects.txt` and writes `in_game/common/script_values/SOL_living_standard_values.txt` for stable and standalone. Compatibility submods inherit both through their SOL dependency.

## Removed in the same pass

`gls_country_sol_all` and its two display values (purchasing power under an SOL name, no consumer); `gls_location_actual_per_capita_spending`, `gls_location_actual_per_capita_spending_display` and `gls_location_color_factor` (the per-capita figure the old "living standard" maps used; no consumer remains); the dead `GLS_SCORE_TT_*` localization. The CMF feature and substitution descriptions now say demand follows purchasing power.

## Adding a building bonus (next step)

Edit `LOCAL_BONUS_ALL` or `LOCAL_BONUS_BY_ESTATE` in `scripts/sol_living_standard_source.py` (script-value bodies in location scope, baseline-basket units) and regenerate with `gen_sol_chain.py`. Do not add the bonus to liquid funds, base spending or any `sol_location_*_demand*` variable. Because the bonus is weighted by baseline spending, an estate with no baseline spending gains nothing from it, and a negative bonus can never push SOL below zero. The location tooltip and situation panel still show purchasing power; once bonuses exist, decide whether they should show SOL rows as well.

## Verification

`scripts/test_sol_living_standard.py` executes the generated effects (zero bonus equals purchasing power; a bonus changes SOL but no purchasing-power variable; empty estates have no SOL) and statically checks all five deploy targets: no demand variable reads a SOL-only name, location SOL is the last step of the demand pass, the drivers only call the country hooks, and purchasing-power GUIs, the purchasing-power map and HUD tooltip 2 contain no SOL names. A deliberate mutation (raw demand scale reading `sol_location_sol_equivalent`) fails the test. Ranking and map tests now run on SOL. The renderer-based UI tests (`test_sol_lshud_ui.py`, `test_sol_substitution_ui.py`) need the installed game fonts and must be run on Windows; in-game acceptance of the tier, ranking and both SOL maps is pending.

Known leftover: `scripts/gen_sol_lshud.py` still contains dead pre-four-section HUD builders (`leftrow_source`, `_legacy_tooltip_source`, `ladder_row`) that reference the retired per-capita ranking; they are not shipped and are imported only for their layout constants by `test_sol_lshud_ui.py`.
