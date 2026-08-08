# SOL Save-Demand Analysis Handoff

Date: 2026-08-08

This document records the save-converter experiments and conclusions from the
2026-08-08 session. It is an empirical supplement to the implementation notes
in `tools/eu5_save_parser/README.md` and `docs/knowledge/PROJECT_OVERVIEW.md`.

## Reproduction

Use the project's `eu5` environment, not the base Anaconda interpreter:

```powershell
$env:PYTHONUTF8='1'
& C:\Users\Hades\anaconda3\envs\eu5\python.exe -m tools.eu5_save_parser <save.eu5>
& C:\Users\Hades\anaconda3\envs\eu5\python.exe -m tools.eu5_save_parser.demand_analysis <save-analysis-directory>
& C:\Users\Hades\anaconda3\envs\eu5\python.exe -m tools.eu5_save_parser.demand_analysis <save-analysis-directory> --relax-total-constraint
& C:\Users\Hades\anaconda3\envs\eu5\python.exe -m tools.eu5_save_parser.demand_analysis <save-analysis-directory> --disable-four-stratum-gate --output <save-analysis-directory>\demand_strategy_analysis_no_gate
```

The current classifier parameters are:

```text
capacity_floor = 0.01
negative_pool = 0.96
balance_weight = 0.05
```

Default analysis replays the current classifier, enforces the strict
four-stratum gate, and uses five hard-total nonnegative candidates:
`balanced_l2`, `improvement_l2`, `target_l2`, `absolute_l2`, and
`minimax_ratio`. `--relax-total-constraint` adds
`improvement_free_total` and soft-total penalties `0.01`, `0.1`, and `1`.
It is diagnostic only; the default five strategies and gate are unchanged
without the flag.

The complete output for the new save is under:

```text
data/save_analysis/SP_*_1386_03_07_1f28d785-cf65-4299-a25e-c135576a50f9/
```

The two comparison exports are `data/save_analysis/world_current/` (the full
1337 save; `hungary_current` is only its HUN-filtered export) and
`data/save_analysis/SP_*_1743_04_01_88fc7852-139e-4d28-930f-561566e0605e/`.

The four actual save files under `data/saves/` are:

```text
SP_HUN_1337_06_02_b2142032-299d-480c-8f30-0b7d5f61a94c.eu5
SP_观察者_1386_03_07_1f28d785-cf65-4299-a25e-c135576a50f9.eu5
SP_观察者_1536_09_21_636b7b0a-0c01-4efe-9354-76a0d4bbae9b.eu5
SP_观察者_1743_04_01_88fc7852-139e-4d28-930f-561566e0605e.eu5
```

The 1536 export contains 623 countries and 28,573 location records but zero
`sol_location_*` runtime caches (`countries_with_sol_variables = 0`). It is
therefore usable for population/location-size composition only, not for an
honest active-set or gate replay. The other three exports contain valid SOL
runtime data.

## Definitions That Matter

- `valid_location_count` is the number of exported locations for which both
  `sol_location_baseline_total_spending` and
  `sol_location_base_total_spending` exceed `epsilon` (`1e-5`). It is not the
  country's raw location count.
- `missing_class` means the rebuilt four-class matrix has a class with zero
  locations. The exact solver rejects this before attempting Gaussian
  elimination.
- `negative_factor` means the exact linear solution contains a factor below
  `-epsilon`; the game cannot use negative compensation, so it is infeasible.
- `singular` means the exact four-class system cannot be inverted. A country
  can have all four classes and still be singular or nearly indistinguishable.
- The strict approximation gate requires all four strata to reduce absolute
  target error by more than the comparison tolerance. It does not require the
  signed four-stratum errors to sum to zero.
- Candidate selection is separate from the gate: passing candidates are
  ranked by mean improvement ratio, then mean absolute improvement, then the
  solver objective and strategy order. If none passes, the applied result is
  `raw_fallback`.

## Three-Save Benchmark

All figures below use simulated current classes and only countries with valid
locations. The location map has 28,573 locations in all three saves.

| Save | Date | Population records | Countries exported / analyzed | Exact feasible | Hard-total gate | Relaxed-total gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1337 HUN | 1337.6.2.16 | 127,008 | 1,564 / 1,504 | 19 (1.3%) | 451 (30.0%) | 469 (31.2%, +18) |
| 1386 new | 1386.3.7 | 155,367 | 1,070 / 1,059 | 37 (3.5%) | 462 (43.6%) | 479 (45.2%, +17) |
| 1743 late | 1743.4.1 | 195,205 | 595 / 589 | 10 (1.7%) | 349 (59.3%) | 356 (60.4%, +7) |

Exact status breakdown among analyzed countries:

| Save | `missing_class` | `negative_factor` | `singular` | `feasible` |
| --- | ---: | ---: | ---: | ---: |
| 1337 | 1,134 | 278 | 73 | 19 |
| 1386 | 677 | 296 | 49 | 37 |
| 1743 | 310 | 265 | 4 | 10 |

The 1386 save has the best exact count because its missing-class share is much
lower than 1337 while its negative-factor share has not yet reached the late
save level. The late save has fewer missing classes but many more nonnegative-
infeasible exact systems.

## Country-Size Effect

The solver-relevant non-empty class-column distribution in the three valid
exports is:

| Save | `k=1` | `k=2` | `k=3` | `k=4` |
| --- | ---: | ---: | ---: | ---: |
| 1337 HUN | 572 | 284 | 278 | 370 |
| 1386 | 324 | 169 | 184 | 382 |
| 1743 | 119 | 80 | 111 | 279 |

There were no gated acceptances among 1,015 `k=1` countries. `k=2` is not a
safe hard-fallback class: 57 countries still passed the four-stratum gate.
This is why the runtime skips only `k <= 1`, not every country with fewer than
four locations.

Across the same three exports, the current four-L2 replay selected every one
of the 15 masks at least once. The most frequent masks were `3/4` (205),
`2/3/4` (170), `2/3` (100), `1/3/4` (96), full `1/2/3/4` (66), `2/4` (56),
`1/2/3` (53), and `1/2/4` (26). Singleton masks together accounted for only
24 of 846 accepted results; removing them only when `k=4` preserved the
high-value pair/triple structure while removing a disproportionate amount of
fixed candidate work. A static whitelist of only the common 8 masks retained
about 92.6% of acceptances but was less accurate than the rank-aware rule.

Hard-total, four-stratum gate pass rate by `valid_location_count`:

| Valid locations | 1337 | 1386 | 1743 |
| ---: | ---: | ---: | ---: |
| 1 | 0.0% | 0.0% | 0.0% |
| 2 | 10.3% | 16.3% | 4.7% |
| 3-4 | 38.2% | 50.8% | 56.8% |
| 5-9 | 61.7% | 73.3% | 79.6% |
| 10-19 | 82.2% | 87.6% | 95.4% |
| 20-49 | 88.3% | 95.1% | 98.7% |
| 50+ | 92.3% | 100.0% | 100.0% |

This confirms that location count and feature diversity are the dominant
practical bottleneck. The increasing overall pass rate over time is partly a
composition effect: later saves have fewer one-location countries and more
large countries. The within-bin trend is also generally upward, so the effect
is not only composition.

## Optimized Runtime Accuracy

The optimized runtime path was replayed on the same three exports with valid
SOL runtime data (3,152 analyzed countries). The full five-strategy path means
all four hard-total L2 strategies plus `minimax_ratio`; the full-L2 path means
the four L2 strategies without minimax. The optimized AI path uses only
`improvement_l2`, skips `k <= 1`, and removes singleton active sets only when
`k = 4`.

| Path | Gate accepts | Mean final absolute error | Mean normalized absolute error | Mean improvement ratio |
| --- | ---: | ---: | ---: | ---: |
| Full five strategies | 1,262 | 11.154344 | 0.306309 | 0.152543 |
| Full four L2 strategies | 846 | 11.446637 | 0.309147 | 0.143097 |
| Optimized AI path | 778 | 11.743938 | 0.311253 | 0.137007 |

The all-country means include raw-fallback countries, so they combine coverage
and fit quality. Among the 778 countries accepted by both the optimized path
and a full path, the result is nearly unchanged:

- versus full five strategies, mean four-stratum absolute error rises from
  `5.785510` to `5.792492` (`+0.12%`), while mean improvement ratio changes
  from `0.559222` to `0.555071`;
- versus full four L2 strategies, mean absolute error rises from `5.786058` to
  `5.792492` (`+0.11%`), and mean improvement ratio changes from `0.559112` to
  `0.555071`.

The active-set reduction itself is effectively lossless. Running
`improvement_l2` over all active sets accepted 780 countries; applying the
`k = 4` singleton filter accepted 778. The two rejected cases fall back to raw,
and the mean normalized error changes only from `0.311126` to `0.311253`.
The larger coverage difference from the full five-strategy path is therefore
mostly intentional minimax removal for AI: 416 of its 484 additional accepts
are countries accepted only by minimax, while 68 are accepts from the other
three L2 strategies.

## Total-Constraint Experiment

The hard solver enforces `sum(M @ factors) = sum(target)` through a KKT
equality. The relaxed solver instead minimizes:

```text
sum_i (((M @ factors)[i] - target[i]) / stratum_scale[i])^2
  + lambda * ((sum(M @ factors) - sum(target)) / total_scale)^2
```

`lambda = 0` is free total; `0.01`, `0.1`, and `1` are soft penalties. The
implementation adds the equivalent fifth pseudo-row to the normal equations,
still enumerates non-empty active class sets, and rejects negative factors.
The four-stratum gate runs after this solve.

For accepted relaxed candidates, total-drift percentage (absolute) was:

| Save | Median | P90 | P99 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| 1337 | 0.161% | 7.944% | 15.601% | 22.484% |
| 1386 | 0.167% | 7.385% | 13.575% | 22.350% |
| 1743 | 0.000% | 12.230% | 17.431% | 23.857% |

The relaxed-total gain is therefore small (18, 17, and 7 additional
countries) and can cost a large total drift. The selected relaxed strategies
are mostly `improvement_free_total` or `improvement_soft_total_1`; penalties
`0.01` and `0.1` were almost never selected. Keep hard total preservation as
the default and treat relaxed total as a diagnostic unless a later gate is
explicitly redesigned.

## Gate-Removal Diagnostic

Disabling the four-stratum gate does not merely make the optimizer more
permissive; it permits visible regressions in individual strata. The maximum
selected worsening percentage by strategy was:

| Save | `balanced_l2` | `improvement_l2` | `target_l2` | `absolute_l2` | `minimax_ratio` |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1337 | 111.0% | 43.9% | 110.8% | 185.5% | 0.004% |
| 1386 | 105.5% | 34.8% | 197.9% | 89.6% | 0.029% |
| 1743 | 49.1% | 37.6% | 140.9% | 138.5% | 0.035% |

The normal gate therefore corresponds to the set with zero worsening. The
minimax candidate is unusually safe on this diagnostic, but it is also the
most expensive candidate and is selected less often once higher mean-gain
strategies are available. Do not remove the gate for gameplay.

## Solver and Runtime Findings

- Classification is based on a location's stratum profile relative to its own
  country's national profile, with high-confidence locations assigned first.
  Each class gets a 1% raw-spending anchor; the 96% negative pool is directed
  toward strata whose raw spending exceeds target. The current balance penalty
  is `0.05 * current_class_capacity / target_class_capacity`.
- The class matrix is raw-weighted: a class column sums each member location's
  raw stratum spending. The solved factor multiplies each location's raw
  coefficient, preserving local variation. Positive factors are uncapped;
  negative, missing, singular, and residual-failure cases keep raw.
- Hungary's rounded inverse was approximately `(200, 133, -85, -144)`, while
  the game reported a class-1 factor near `200.734`. Gaussian elimination is
  therefore working; the negative factors are the feasibility problem. A
  target nobles-to-burghers ratio near `11.4` also exceeded the matrix's
  maximum column ratio near `10.85`, proving that removing a factor cap alone
  cannot create a nonnegative exact solution.
- All approximate hard-total solves preserve total spending to floating-point
  residue. The raw total error is usually tiny, so relaxing total spending
  addresses class-structure mismatch rather than lost national expenditure.
- Classification sorts locations by confidence and is `O(n log n)` because of
  that ordering, followed by an `O(n)` assignment/matrix pass. The weighted
  solver has four variables and enumerates a constant number of active class
  sets. The offline analyzer still evaluates all five strategies for every
  country so cross-country coverage remains comparable. Runtime first rejects
  raw-gate-impossible and rank-1 matrices; AI then uses only `improvement_l2`
  over actual non-empty subsets, skipping singleton subsets at `k=4`. Players
  retain all four L2 strategies and the finite minimax vertices. On the three
  valid exports, this fast path retained 778 of 846 baseline four-L2 gated
  acceptances (92.0%); the `world_current` replay used 5,092 L2 candidate
  calls and about 1.26 million scalar operations, versus 90,240 calls and
  13.59 million operations on the former AI path (9.26%, about 1/10.8).
- Runtime classification must give `ordered_owned_location` an explicit
  `max = 100000`; an omitted max silently leaves most locations unassigned.
  CMF logs should contain one concept and at most four dynamic values per row.
  For `add_to_global_variable_map`, calculate into a temporary variable first,
  write the scalar map value, then remove the temporary variable; inline math
  blocks are invalid there.
- The previous exact scalar-operation accounting for `world_current` was
  14,977,545 (1,504 valid countries, 90,240 L2 candidates, and 1,461 HUN
  minimax vertices). The new replay isolates the L2 core because the
  classification sort, exact diagnostic, and player-only minimax remain
  separate costs. It measures 5,092 L2 calls and approximately 1,258,748
  scalar operations after the rank/raw-gate/AI-strategy/active-set filters.

## Practical Next Steps

1. Preserve raw coefficients on `missing_class`, singular, negative-factor, or
   residual failure.
2. Keep the four-stratum gate as the gameplay acceptance rule; a global scalar
   score can hide a worsened stratum.
3. Investigate class assignment and matrix distinction for small countries
   before further weakening total preservation. A country with one location
   cannot supply four independent class columns, so no optimizer can recover
   that information.
4. When comparing new saves, report both analyzed-country composition and
   size-binned pass rates; raw overall percentages alone are confounded by the
   changing number of small countries.
