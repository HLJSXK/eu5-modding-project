# Tribesmen Handling in SOL

**Date**: 2026-08-13  
**Question**: How are tribesmen (tribes estate pop type) currently handled throughout the mod?

---

## Summary

Tribesmen are treated as a **fully independent stratum** in all economic calculations up to the classification stage, then **merged with commoners into the "lower" aggregate** for the 4-class country-level solver. This design preserves tribal economic identity in per-location raw demand while simplifying the national matrix to four equations.

---

## 1. Goods Demand (demand_add)

**Status**: Full parity with other pop types.

All 55 SOL goods define `tribesmen` demand_add values in `z_SOL_pop_goods.txt`. Example (clothes):

```
demand_add = {
    nobles = -0.0005
    clergy = -0.001
    burghers = -0.002
    laborers = -0.00185
    peasants = -0.00085
    soldiers = -0.00185
    tribesmen = -0.001     # ← present
}
```

Tribesmen are **excluded from the "upper" group** (which is nobles + clergy + burghers + laborers + soldiers in 1.3.11). This is correct: peasants and tribesmen remain the two lower-income groups that fall outside upper-class demand patterns.

**Source**: `data/target_demand.csv` contains a `tribesmen` column for all goods.

---

## 2. Market Unit Spending

**Status**: Independent per-market map.

Tribesmen have their own `sol_market_unit_spending_tribesmen` global map, calculated separately from commoners/peasants. At runtime:

```
set_variable = { name = sol_unit_spending_tribesmen value = "global_variable_map(sol_market_unit_spending_tribesmen|scope:sol_location_market)" }
```

This means tribal pop in different markets can have different consumption baskets (e.g., maize-heavy in Americas, millet-heavy in Africa), independent of peasant/laborer patterns in the same markets.

**Refresh frequency**: Yearly, on the first day of the year (`gls_update_market_unit_spending`).

---

## 3. Location-Level Raw Demand

**Status**: Independent income, spending, and liquid funds.

Tribesmen are tracked separately through the entire location calculation pipeline:

### Income and Maintenance
```
sol_location_tribesmen_income      = local_sol_tribesmen_income_display
sol_location_tribesmen_net_income  = income - local_sol_tribesmen_building_maintenance, min=0
```

### Base Spending
```
sol_location_tribesmen_base_spending = sol_unit_spending_tribesmen × num_pop_type:tribesmen
```

### Liquid Funds (Savings Pressure)
```
sol_location_tribesmen_liquid_funds = tribesmen_net_income × sol_location_liquid_funds_multiplier
```

The multiplier is **country-wide unified** (same value for all five strata in a given country), but tribesmen's liquid funds are computed independently before aggregation.

### Total Spending Aggregation
```
sol_location_base_total_spending += nobles + clergy + burghers + laborers + peasants + soldiers + tribesmen
```

All seven pop types contribute to the location's total.

### Raw Scale (Pre-Solver Baseline)
```
sol_location_raw_demand_scale = sol_location_liquid_funds / sol_location_base_total_spending
```

This single scalar per location is applied uniformly to all seven pop types in that location's raw baseline. Tribesmen and nobles in the same location get the same raw coefficient.

---

## 4. Classification (Location → Class Mapping)

**Status**: Merged into "lower" aggregate.

Locations are classified by which stratum dominates their spending share. The four classification targets are:

1. Nobles
2. Clergy
3. Burghers
4. **Lower** = commoners + tribesmen

```
sol_location_lower_base_spending = sol_location_commoners_base_spending 
                                  + sol_location_tribesmen_base_spending

sol_location_share_lower = sol_location_lower_base_spending / sol_location_base_total_spending
```

A location with high tribal population is classified as Class 4 (lower) alongside peasant-dominated locations. The classifier **does not distinguish** tribal from peasant dominance—both are "lower strata."

---

## 5. Country-Level Solver (Matrix Construction)

**Status**: Merged into row 4.

The 4×4 matrix `M` and target vector `t` aggregate tribesmen with commoners:

### Target Vector (Liquid Funds)
```
t[0] = Σ nobles_liquid_funds       (over all owned locations)
t[1] = Σ clergy_liquid_funds
t[2] = Σ burghers_liquid_funds
t[3] = Σ (commoners_liquid_funds + tribesmen_liquid_funds)   ← row 4
```

### Matrix Rows (Raw-Weighted Base Spending)
```
M[0, class_j] = Σ (raw_scale × nobles_base_spending)     for locations in class j
M[1, class_j] = Σ (raw_scale × clergy_base_spending)
M[2, class_j] = Σ (raw_scale × burghers_base_spending)
M[3, class_j] = Σ (raw_scale × (commoners + tribesmen)_base_spending)
```

The solver finds four class coefficients `x₁…x₄` such that:

```
M x ≈ t    (with x ≥ 0)
```

Row 4's constraint is: "The total lower-strata (commoners + tribesmen) spending across all classes, scaled by class coefficients, should match the total lower-strata liquid funds."

Tribesmen and commoners are treated as a **unified economic bloc** at this stage.

---

## 6. Savings Pressure (Estate Gold / Target)

**Status**: Independent calculation, unified adjustment.

Tribesmen have their own estate gold and target in `gls_compute_savings_pressure`:

```
gls_tribesmen_gold   = estate(estate_type:tribes_estate).estate_gold
gls_tribesmen_target = 0 + (country_wealth_anchor × 1), min=35
```

Target multiplier is **1.0× the anchor** (vs nobles 8×, clergy/burghers 3×, commoners 2×), reflecting lower expected tribal estate wealth.

These five per-stratum ratios are then **aggregated**:

```
gls_savings_pressure_adjustment = (Σ gold / Σ target - 1) × 0.25, capped at +0.5
```

The unified adjustment applies to all strata, including tribesmen. The per-stratum structure is computed but not preserved in the output—see `docs/analysis/stratified_multiplier_final_report.md` for why this is correct.

---

## 7. JTG Compatibility (Just Trade Goods)

**Status**: Explicit zero demand.

The JTG compact submod applies fixed multipliers to 22 JTG goods:

```
1.05 / 0.45 / 1.75 / 0.02 / 0.10 / 0.025 / 0
nobles clergy burghers laborers peasants soldiers tribesmen
                                                    ↑
```

Tribesmen get **multiplier = 0** for all JTG goods (brass, meat, soap, spices, cheese). This zeroing is deliberate: tribal economies in EU5 are modeled as subsistence-oriented with minimal demand for artisan/luxury processed goods.

---

## 8. MnT Compatibility (MEIOU and Taxes)

**Status**: Full integration.

The M&T submod rebuilds all 55 SOL goods from M&T objects and inversely scales the seven pop quantities (including tribesmen) against M&T prices. Tribesmen receive the same treatment as other pop types:

- M&T's own `tribesmen` demand structure is preserved
- Unit spending maps are built from M&T price/basket data
- Estate building maintenance caches tribal buildings
- The "Gaelic-tribes" attribution is **excluded** (M&T policy: Gaelic clans are a special mechanic outside standard estate accounting)

---

## Design Rationale

### Why Seven Strata → Four Solver Rows?

1. **Engine constraint**: `local_pop_demand` is a location-level scalar. The solver can assign one coefficient per location, not per pop type.

2. **Classification freedom**: Four classes × N locations gives ~4N degrees of freedom. Seven would require partitioning locations into seven classes, but most locations have only 2–4 significant pop types, making a 7-way split sparse and unstable.

3. **Economic coherence**: Commoners and tribesmen share similar consumption baskets (grains, basic clothes, low-value tools) and income ranges. Lumping them as "lower" preserves the economic signal while keeping the matrix well-conditioned.

### Why Independent Tribesmen Before Aggregation?

1. **Geographic variation**: Tribal markets (e.g., Mesoamerica, Sub-Saharan Africa, Siberia) have distinct consumption patterns. A unified "lower" basket at the data layer would force tribal regions to use European peasant prices.

2. **Estate mechanics**: The tribes estate has its own gold, loyalty, and influence. Independent tracking lets savings pressure and estate building maintenance operate on tribal economics separately.

3. **Modding compatibility**: M&T and JTG both define tribal demand. If SOL merged tribesmen into commoners at the data layer, these mods would have no hook to inject tribal-specific values.

---

## Known Limitations

### 1. Classification Cannot Distinguish Tribal from Peasant Dominance

A location that is 80% tribesmen and 5% peasants is classified identically to one that is 80% peasants and 5% tribesmen—both are Class 4 (lower). The class coefficient applies uniformly to both.

**Impact**: Minimal. Both groups have similar economic needs, and the raw baseline already captures per-location variation (a tribal-heavy location's raw scale reflects tribal income, not peasant income). The class coefficient is a national correction on top of that baseline.

### 2. Solver Row 4 Aggregates All Lower-Strata Error

When the solver finds that row 4 (lower) is infeasible, you cannot tell whether the mismatch is in commoner regions, tribal regions, or both. The residual is reported as one combined "lower" error.

**Workaround**: The per-location raw errors (pre-solver) are stratum-specific. If you need to diagnose "tribal demand is too high but peasant demand is correct," check the raw residuals before aggregation.

### 3. Tribal Zero in JTG Is Hard-Coded

If a future version of JTG adds tribal-specific goods (e.g., "furs" or "bison"), the current zero multiplier would suppress that demand. The generator would need to be updated to read tribal demand from JTG source mods.

---

## Recommendation

**No changes needed.** The current seven-stratum input → four-row solver design is well-calibrated:

- Tribesmen retain economic independence where it matters (baskets, income, estate gold)
- The lower-strata merge happens at the right layer (classification, not raw data)
- The 4×4 matrix is stable across 9788 countries tested

If tribal-peasant distinction becomes a gameplay priority (e.g., "tribal regions should grow slower in early game"), the lever is **target formula** (adjust tribal liquid-funds multiplier), not solver structure.

---

## References

- `src/stable/in_game/common/goods/z_SOL_pop_goods.txt` (line 714–725 comments, tribesmen demand_add)
- `scripts/sol_economy_effects_source.py` (lines 938–1127, tribesmen in generator)
- `src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt`:
  - Lines 2732–2739: tribesmen base spending aggregation
  - Lines 2761: tribesmen liquid funds
  - Lines 3040–3044: lower = commoners + tribesmen in solver
- `docs/knowledge/BRIEF.md` (line 32: lower definition)
- `docs/knowledge/anti_patterns.yaml` (line 433: upper group exclusion)
- `docs/analysis/stratified_multiplier_final_report.md` (unified vs per-stratum savings pressure)
