# Stratified Savings Pressure Multiplier Impact Analysis

**Date**: 2026-08-13  
**Scope**: 7 saves (1337–1386), 9788 countries  
**Question**: Should liquid funds use per-stratum savings pressure adjustments instead of a unified multiplier?

---

## Executive Summary

**Recommendation: Keep the unified multiplier.**

Per-stratum adjustments cause:
- **Exact solve success rate to halve**: 1.1% → 0.5% (-0.6% absolute, -56% relative)
- **Total feasibility to drop by 0.7%**: 7.7% → 7.0% (73 countries lose cone containment)
- **Late-game impact to amplify**: 1386 observer save shows -2.9% feasibility, -2.7% exact

Approximation success rises slightly (+0.3%), but this compensation is insufficient and comes with worse per-stratum residuals.

---

## Current Implementation

```
unified_adjustment = (Σ estate_gold / Σ estate_target - 1) × 0.25, capped at +0.5
```

Every stratum's liquid funds multiplier equals `1 + unified_adjustment`:

```
nobles_liquid_funds    = nobles_net_income    × (1 + unified_adjustment)
clergy_liquid_funds    = clergy_net_income    × (1 + unified_adjustment)
burghers_liquid_funds  = burghers_net_income  × (1 + unified_adjustment)
commoners_liquid_funds = commoners_net_income × (1 + unified_adjustment)
tribesmen_liquid_funds = tribesmen_net_income × (1 + unified_adjustment)
```

The five per-stratum `gold/target` ratios are **computed** but then **aggregated** into a single scalar before being applied. This scales all four target-vector rows proportionally, preserving their relative structure.

---

## Alternative: Per-Stratum Adjustments

```
nobles_adjustment    = (nobles_gold / nobles_target - 1) × 0.25, capped at +0.5
clergy_adjustment    = (clergy_gold / clergy_target - 1) × 0.25, capped at +0.5
burghers_adjustment  = (burghers_gold / burghers_target - 1) × 0.25, capped at +0.5
commoners_adjustment = (commoner_gold / commoner_target - 1) × 0.25, capped at +0.5
tribesmen_adjustment = (tribesmen_gold / tribesmen_target - 1) × 0.25, capped at +0.5
```

Each stratum gets its own multiplier:

```
nobles_liquid_funds    = nobles_net_income    × (1 + nobles_adjustment)
clergy_liquid_funds    = clergy_net_income    × (1 + clergy_adjustment)
...
```

This **rotates** the target vector instead of merely scaling it.

---

## Quantitative Results

### Solver Outcome Breakdown

|                       | Unified  | Stratified | Delta        |
|-----------------------|----------|------------|--------------|
| **Exact solve**       | 111 (1.1%) | 49 (0.5%)  | **-62 (-0.6%)** |
| **Approximation**     | 643 (6.6%) | 675 (6.9%) | +32 (+0.3%)  |
| **Total feasible**    | 754 (7.7%) | 681 (7.0%) | **-73 (-0.7%)** |
| **Infeasible**        | 9034 (92.3%) | 9107 (93.0%) | +73 (+0.7%)  |

### Per-Save Breakdown

| Save | Countries | Feasible Δ | Exact Δ | Approx Δ |
|------|-----------|------------|---------|----------|
| HUN 1337.06 | 1504 | -0.2% | -0.1% | +0.3% |
| HUN 1337.10 | 1445 | -0.8% | -0.6% | +0.2% |
| HUN 1337.11 | 1445 | -1.0% | -0.6% | +0.1% |
| HUN 1337.12 | 1445 | -0.8% | -0.6% | +0.4% |
| HUN 1338.01 | 1445 | -0.2% | -0.1% | +0.4% |
| HUN 1338.02 | 1445 |  0.0% | -0.3% | +0.8% |
| Observer 1386 | 1059 | **-2.9%** | **-2.7%** | +0.6% |

Late-game (1386) shows the steepest decline, confirming that per-stratum divergence amplifies over time as estates accumulate wealth at different rates.

### Gate Pass Rate

**99.9% in both variants** (unchanged). The wide gate prefilter checks whether `|raw_pred - target| > 1e-5` for at least one stratum. Since raw baseline is defined identically in both variants (`total_liquid / total_base`), gate pass criteria remain the same.

---

## Mechanism Explanation

### Unified Multiplier (Current)

```
t' = k · t    (target vector scaled by scalar k)
M' = k · M    (matrix scaled by same k)
```

When solving `M' x = t'`, the factor `k` cancels:

```
k·M x = k·t  ⟹  M x = t
```

The solution direction is **invariant** to `k`. Savings pressure scales the magnitude of all class coefficients proportionally, but does not affect feasibility (whether `t ∈ cone(M columns)`).

### Per-Stratum Multiplier (Alternative)

```
t' = K · t    where K = diag(k₁, k₂, k₃, k₄)
M' ≠ K · M    (matrix rows are location-weighted cross-stratum blends)
```

The target vector **rotates**. When `k₁ ≠ k₂ ≠ k₃ ≠ k₄`, the direction of `t'` changes relative to `cone(M')`, often moving outside the feasible region.

#### Why Rotation Causes Infeasibility

The cone `cone(M columns)` is a strict subset of `cone(all owned locations)` because the 4-class partition cannot span all directions the full location set can reach. When the target lies near the cone boundary under unified multiplier, even a small rotation can push it outside.

**Empirical confirmation**:

| Group | N | Spread p50 | Spread p90 | Mean |
|-------|---|------------|------------|------|
| Lost feasibility | 114 | 0.33 | 0.75 | 0.40 |
| Kept feasibility | 640 | 0.25 | 0.25 | 0.23 |

"Spread" = max pairwise difference among the five per-stratum adjustments. Countries that lose feasibility have median spread **0.33** (one stratum at +0.2, another at -0.13), while countries that retain it cluster at **0.25** (all adjustments on the same side, minimal rotation).

### Example Case: JAP (1337.06)

- **Unified**: `-0.23` for all strata → exact solve succeeds
- **Stratified**: nobles `+0.36`, clergy `-0.10`, burghers `-0.20`, commoners `+0.13`, tribesmen `-0.25` → spread = **0.61** → infeasible

The target vector rotates ~34° from the raw baseline equilibrium and exits the cone entirely.

---

## Interpretation

### What the Unified Multiplier Represents

The unified adjustment is a **macroeconomic pressure gauge**: when `Σ gold > Σ target`, the country's estates are over-funded relative to expectations, so all strata have looser spending constraints. When `Σ gold < Σ target`, all tighten together.

This is **total-quantity control**, not **inter-stratum redistribution**. The five per-stratum `gold/target` ratios inform the aggregate but do not independently steer individual strata.

### What Per-Stratum Multipliers Would Represent

A structural shift: "nobles are flush (+0.4) while peasants are broke (-0.2), so nobles should consume more and peasants less." This introduces **distributional feedback** where estate gold imbalances directly reshape demand proportions across strata.

**Problem**: The solver's fundamental constraint is that all strata in a given location share one `local_pop_demand` scalar—the engine has no mechanism for "nobles in this province get ×1.3, peasants get ×0.8." The country-level solve finds class coefficients that weight locations, but the per-location freedom is still one degree per location, not five.

Per-stratum multipliers inject five independent signals into a system with only four class outputs. The mismatch manifests as rotation-induced infeasibility: the target asks for something the class-location structure cannot deliver.

---

## Alternatives Considered

If the design intent is genuinely **"let rich estates consume more, poor estates less"**, three paths exist:

### 1. Retain Unified Multiplier (Recommended)

Accept that savings pressure is a total-quantity lever, not a redistributive one. The five `gold/target` ratios still enter the input (they determine the aggregate), but their variance is filtered out.

**Cost**: None. Delivers current 7.7% feasibility.

### 2. Add a Total-Preservation Constraint

Modify the approximation solver to enforce `Σ(target_i × x_c) = constant` as a hard constraint, reducing the problem from 4 independent equations to 3 + 1 constraint. This keeps stratified targets but prevents the total from drifting away from what the raw baseline naturally achieves.

**Cost**: Solver complexity increases. Approximate candidates now satisfy 3 strata tightly + 1 total, rather than 4 strata loosely. Benefit unclear.

### 3. Adjust `target` Formula Directly

Instead of `target = liquid_funds`, use `target = liquid_funds × estate_influence_weight`, where influence weights are per-stratum modifiers derived from estate privileges, loyalty, or gold ratio. This keeps the target direction aligned with what the economy naturally produces (so cone containment holds) while still encoding estate-power feedback.

**Cost**: Requires new game-mechanical grounding for "influence weight." Risk of circular feedback loops (low gold → low influence → lower target → solver scales down → even lower gold).

---

## Recommendation

**Keep the unified multiplier.**

- Stratified adjustments collapse exact-solve success by 56% and net feasibility by 0.7%.
- The +0.3% approximation gain is insufficient compensation and comes with worse per-stratum residuals (rotation enlarges worst-case error).
- Late-game amplification (-2.9% in 1386) suggests the problem worsens as estates diverge.
- The conceptual mismatch (five distributional signals → four class outputs) is structural, not tunable.

If distributional feedback is a design goal, pursue alternative #3 (adjust target formula) rather than rotating the multiplier. The savings pressure system is correctly scoped as a **macroeconomic stabilizer**, not a **microeconomic redistributor**.

---

## Appendix: Detailed Results

- **Full per-country CSV**: `data/save_analysis/stratified_multiplier_comparison.csv`
- **Analysis script**: `tools/eu5_save_parser/stratified_multiplier_impact.py`
- **Saves analyzed**:
  - `SP_HUN_1337_06_02_b2142032` (1504 countries)
  - `SP_HUN_1337_10_02_d95e1b3a` (1445 countries)
  - `SP_HUN_1337_11_02_d95e1b3a` (1445 countries)
  - `SP_HUN_1337_12_01_d95e1b3a` (1445 countries)
  - `SP_HUN_1338_01_13_d95e1b3a` (1445 countries)
  - `SP_HUN_1338_02_02_d95e1b3a` (1445 countries)
  - `SP_观察者_1386_03_07_1f28d785` (1059 countries)

Saves 1536 and 1743 were excluded due to missing `gls_*` export columns (pre-2026-08 export format).
