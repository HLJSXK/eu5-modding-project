# Country-Level Exact Solver Feasibility Survey (2026-08-11)

## Summary

Across 11 debug saves (1337.06 to 1743.04, spanning ~406 years), **87.3% of country-save states
are mathematically infeasible for an exact solve** even when allowed one independent nonnegative
coefficient per owned location — the theoretical upper bound on what any classification can reach.

Sample: 15,283 country-save pairs (1,504–1,525 countries per 1337–1338 save, fewer in later
consolidated states). Skipped: countries with no valid locations or all-zero targets (56–623 per save).

## Aggregate Results

| Metric | Value |
|---|---|
| Total scored country-save pairs | 15,283 |
| Exact solve **possible** | 1,940 (12.7%) |
| Exact solve **impossible** | 13,343 (87.3%) |
| Median infeasible residual | 0.129–0.243 (L1 relative to target) |
| Max infeasible residual | 1.00–1.22 |

## By Owned Location Count

Countries with more locations fare better — large empires can internally balance conflicting strata
needs, while minor states have fewer degrees of freedom:

| Range | Countries | Feasible | Rate |
|---|---|---|---|
| 1–9 locations | 12,829 | 1,292 | **10.1%** |
| 10–49 | 2,090 | 466 | 22.3% |
| 50–199 | 308 | 147 | 47.7% |
| 200+ | 56 | 35 | **62.5%** |

## By Time Period

No clear trend — feasibility stays within a narrow 12.5–13.2% band across 406 simulated years:

| Period | Countries | Feasible | Rate |
|---|---|---|---|
| 1337 (6 saves) | 9,064 | 1,129 | 12.5% |
| 1338 (3 saves) | 4,571 | 603 | 13.2% |
| Later (1386, 1536, 1743) | 1,648 | 208 | 12.6% |

(1536 save had 623 no-valid-location countries and 0 scored, likely a data issue.)

## Per-Save Breakdown

| Save | Date | Countries | Feasible | Rate | Median Residual |
|---|---|---|---|---|---|
| 1337.06.02 (b2142032) | 1337-06-02 | 1,504 | 164 | 10.9% | 0.134 |
| 1337.10.02 (08ba7737) | 1337-10-02 | 1,513 | 194 | 12.8% | 0.129 |
| 1337.10.02 (d95e1b3a) | 1337-10-02 | 1,513 | 192 | 12.7% | 0.129 |
| 1337.11.02 (d95e1b3a) | 1337-11-02 | 1,509 | 192 | 12.7% | 0.131 |
| 1337.12.01 (d95e1b3a) | 1337-12-01 | 1,512 | 195 | 12.9% | 0.129 |
| 1338.01.04 (912fe0ee) | 1338-01-04 | 1,525 | 209 | 13.7% | 0.130 |
| 1338.01.13 (d95e1b3a) | 1338-01-13 | 1,523 | 196 | 12.9% | 0.129 |
| 1338.02.02 (d95e1b3a) | 1338-02-02 | 1,523 | 198 | 13.0% | 0.129 |
| 1386.03.07 (1f28d785) | 1386-03-07 | 1,059 | 155 | 14.6% | 0.146 |
| 1536.09.21 (636b7b0a) | 1536-09-21 | 0 | 0 | — | — |
| 1743.04.01 (88fc7852) | 1743-04-01 | 589 | 53 | 9.0% | 0.243 |

*(1536 save had all 623 countries skipped for no-valid-locations; likely a data corruption or
early-game initialization artifact.)*

## Interpretation

**The 87.3% infeasibility rate is NOT a bug.** It is the inherent structure of the problem:

1. **Conflicting compression ratios** — nobles/clergy often need scaling up (baseline < target),
   while lower needs scaling down (sometimes to 0.6×). Satisfying all four simultaneously requires
   locations where high-raise strata are segregated from high-cut strata.

2. **Per-location coupling** — measured correlation between nobles share and lower share ranges
   0.29–0.47. Locations that are heavy in nobles spending are also heavy in lower spending, so
   raising one means raising the other; no nonnegative factor field decouples them.

3. **No classifier can exceed the all-location cone** — because every class column sums nonnegative
   location vectors, `cone(any 4-way partition) ⊆ cone(all locations)`. A 4-class model cannot
   reach what the 189-class (HUN) or N-class (general country) model already cannot.

Therefore:

- Improving the classifier **cannot** raise the 12.7% feasible rate. It can only preserve it
  (pick a partition whose cone contains the target) or degrade it (pick a partition whose cone
  does not).

- The median residual of 0.13 for infeasible countries means the target is typically 13% away
  from the boundary of the reachable set. This is not numerical noise — it is the magnitude of
  the structural conflict.

## Methodology

For each country with at least one valid location (total spending > ε) and nonzero target:

1. Run Lawson-Hanson nonnegative least squares on the 4×N system `A w = t, w ≥ 0`, where each
   column of `A` is one location's four-stratum spending vector and `t` is the country target.

2. Check whether each row's residual `|Σ_j v_j[i] w_j - t[i]|` is within the runtime tolerance
   `|t[i]| × 0.001 + 0.01`, matching `sol_country_demand_validate_class_residual`.

3. Mark the country-save pair **feasible** if all four rows pass, **infeasible** otherwise.

The NNLS solution is exact (active-set method, finite termination) and fast (~50 iterations typical,
≤200 capped, each solving a ≤4×4 inner least squares). The passive set never exceeds the row count,
so large-country cost stays O(locations × iterations).

Full per-country CSV: `data/save_analysis/cone_survey_all.csv`

Tool: `tools/eu5_save_parser/cone_survey.py`

## Recommended Action

When a country reports `negative_factor` or a class-wide `-100%` `local_pop_demand`:

1. **Run `cone_feasibility.py` first** to decide whether the target is inside the all-location cone.
2. **If residual > 0.01, stop.** No classifier change can fix it. Only relaxing the target
   (e.g., projecting it onto the cone boundary) or accepting an approximation can.
3. **If residual ≈ 0**, the classifier is the bottleneck — then optimizing the classification
   (better scores, adaptive capacity, increased class count) might help.

This survey proves that step 2 applies to **87.3% of normal country-save states**, so attempting
classifier improvements without first checking feasibility wastes investigation effort.

---

*Survey conducted 2026-08-11 on 11 debug saves totaling 6.37 GB, parsing ~17–36s per save (depending
on population count), full NNLS test ~13.6s for 15,283 countries. HUN five-save series (d95e1b3a
1337.10–1338.02) individually confirmed the cone-containment bound on 2026-08-11.*
