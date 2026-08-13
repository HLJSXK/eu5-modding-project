#!/usr/bin/env python3
"""Estimate monthly solver cost from real save data.

Per-stage costs are counted from the generated scripts, not guessed. The
country size distribution and per-country feasibility come from the cone
survey CSV, so the monthly totals reflect real game states rather than a
synthetic worst case.

Cost unit: one "variable operation" (set_variable / change_variable), which is
the dominant primitive in Jomini script. Trigger evaluations inside `limit`
blocks are counted separately because they are cheaper but far more numerous.

Usage:
    python -m tools.eu5_save_parser.solver_cost_model
    python -m tools.eu5_save_parser.solver_cost_model --csv path/to/cone_survey_all.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_CSV = Path("data/save_analysis/cone_survey_all.csv")

# ---------------------------------------------------------------------------
# Stage costs, counted from the generated scripts on 2026-08-13.
# ---------------------------------------------------------------------------

# A_SOL_economy_effects.txt :: sol_compute_location_pop_demand
# 58 set_variable + 12 change_variable, run once per owned land location.
RAW_PER_LOCATION = 70

# Same effect, classification scoring pass: per-location share scoring and
# clipping, then one confidence-ordered assignment visit.
CLASSIFY_PER_LOCATION = 24

# Matrix aggregation: each location contributes its four stratum rows to one
# class column, plus the country-level accumulators.
AGGREGATE_PER_LOCATION = 13

# B_SOL_country_demand_solver.txt :: sol_country_demand_solve_classes
# 15 direct varops + 23 primitive calls (eliminate_row x6 -> 1 + 4*2 + 2 each,
# check_kkt_pivot x4 -> 2 each, backsolve chain).
EXACT_SOLVE = 15 + 6 * 11 + 4 * 3 + 7 + 6 * 2
# -> 15 + 66 + 12 + 7 + 12 = 112

# One vertex case: 38 direct varops, 6 eliminate_row, 4 check_kkt_pivot,
# 6 backsolve_cell, then sol_vertex_consider.
VERTEX_CONSIDER = 16 + 4 * (12 + 2 + 2) + 10   # metrics + 4 rows + reduce
VERTEX_CASE = 38 + 6 * 11 + 4 * 3 + 6 * 2 + VERTEX_CONSIDER
VERTEX_CASES = 209
VERTEX_SWEEP = VERTEX_CASE * VERTEX_CASES

# Cheap fixed overheads per country that enters the solver body.
SOLVER_SETUP = 120          # variable resets, target/baseline sums, capacity split
RAW_ONLY_SETUP = 25         # status flags and cache clears on the raw-only path

SIZE_GATE = 5               # num_locations < 5 -> raw only


def load_states(path: Path) -> list[tuple[int, bool]]:
    """Return (locations, feasible) per country-save state."""
    out: list[tuple[int, bool]] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                n = int(row["locations"])
            except (KeyError, ValueError):
                continue
            out.append((n, row.get("status", "").strip() == "feasible"))
    return out


def country_cost(n: int, feasible: bool, *,
                 size_gate: bool, approx: bool) -> int:
    """Variable operations for one country in one month."""
    # Raw location pass always runs: every configuration still needs the raw
    # coefficient and the modifier write.
    cost = RAW_PER_LOCATION * n

    if size_gate and n < SIZE_GATE:
        return cost + RAW_ONLY_SETUP

    cost += SOLVER_SETUP
    cost += (CLASSIFY_PER_LOCATION + AGGREGATE_PER_LOCATION) * n
    cost += EXACT_SOLVE
    if not feasible and approx:
        cost += VERTEX_SWEEP
    return cost


def summarise(states: list[tuple[int, bool]], saves: int) -> None:
    per_save = len(states) / saves
    locs = [n for n, _ in states]
    feas = sum(1 for _, f in states if f)

    print("=== sample ===")
    print(f"  country-save states : {len(states):,}  over {saves} saves")
    print(f"  countries per save  : {per_save:,.0f} (average)")
    print(f"  total locations     : {sum(locs):,}")
    print(f"  feasible            : {feas:,} ({100 * feas / len(states):.1f}%)")
    print()

    buckets = [(1, 4), (5, 9), (10, 49), (50, 199), (200, 10**9)]
    print("=== size distribution ===")
    print(f"  {'locations':>12} {'states':>8} {'share':>7} {'locs held':>11} {'loc share':>10}")
    total_loc = sum(locs)
    for lo, hi in buckets:
        sel = [n for n in locs if lo <= n <= hi]
        label = f"{lo}-{hi}" if hi < 10**9 else f"{lo}+"
        print(f"  {label:>12} {len(sel):>8,} {100*len(sel)/len(states):>6.1f}% "
              f"{sum(sel):>11,} {100*sum(sel)/total_loc:>9.1f}%")
    print()

    print("=== per-stage unit cost (variable operations) ===")
    print(f"  raw, per location            : {RAW_PER_LOCATION}")
    print(f"  classify + aggregate, per loc: {CLASSIFY_PER_LOCATION + AGGREGATE_PER_LOCATION}")
    print(f"  solver setup, per country    : {SOLVER_SETUP}")
    print(f"  exact solve (4x4)            : {EXACT_SOLVE}")
    print(f"  one vertex case              : {VERTEX_CASE}")
    print(f"  full sweep ({VERTEX_CASES} cases)      : {VERTEX_SWEEP:,}")
    print()

    configs = [
        ("all on, no size gate", dict(size_gate=False, approx=True), 1.0),
        ("all on, size gate", dict(size_gate=True, approx=True), 1.0),
        ("default (AI yearly)", dict(size_gate=True, approx=True), None),
    ]

    print("=== monthly cost per save ===")
    baseline = None
    for label, kw, _ in configs:
        total = sum(country_cost(n, f, **kw) for n, f in states) / saves
        if label == "default (AI yearly)":
            # Human countries solve monthly; AI countries solve on their own
            # anniversary, i.e. 1/12 of them in any given month. The raw pass
            # and modifier write still happen every month for everyone.
            raw_all = sum(RAW_PER_LOCATION * n for n, _ in states) / saves
            solve_only = total - raw_all
            # One human country per save in single player.
            human_share = 1.0 / per_save
            total = raw_all + solve_only * (human_share + (1 - human_share) / 12)
        if baseline is None:
            baseline = total
        print(f"  {label:<24} {total:>14,.0f}   ({100*total/baseline:>5.1f}% of first row)")
    print()

    print("=== where the cost goes, all on + size gate ===")
    raw = sum(RAW_PER_LOCATION * n for n, _ in states) / saves
    gated_out = [(n, f) for n, f in states if n < SIZE_GATE]
    passed = [(n, f) for n, f in states if n >= SIZE_GATE]
    cls = sum((CLASSIFY_PER_LOCATION + AGGREGATE_PER_LOCATION) * n for n, _ in passed) / saves
    setup = SOLVER_SETUP * len(passed) / saves
    exact = EXACT_SOLVE * len(passed) / saves
    sweep = VERTEX_SWEEP * sum(1 for _, f in passed if not f) / saves
    tot = raw + cls + setup + exact + sweep
    for label, v in (("raw location pass", raw), ("classify + aggregate", cls),
                     ("solver setup", setup), ("exact solves", exact),
                     ("vertex sweeps", sweep)):
        print(f"  {label:<24} {v:>14,.0f}   {100*v/tot:>5.1f}%")
    print(f"  {'total':<24} {tot:>14,.0f}")
    print()
    print(f"  size gate filters out {len(gated_out)/saves:,.0f} of "
          f"{len(states)/saves:,.0f} countries per save "
          f"({100*len(gated_out)/len(states):.0f}%)")
    print(f"  they hold {100*sum(n for n,_ in gated_out)/total_loc:.0f}% of all locations")
    infeasible_gated = sum(1 for _, f in gated_out if not f)
    infeasible_all = sum(1 for _, f in states if not f)
    print(f"  and {100*infeasible_gated/infeasible_all:.0f}% of all infeasible "
          f"(i.e. sweep-triggering) countries")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"missing {args.csv}", file=sys.stderr)
        return 1
    states = load_states(args.csv)
    if not states:
        print("no rows parsed", file=sys.stderr)
        return 1

    saves = len({r for r in _saves(args.csv)})
    summarise(states, saves)
    return 0


def _saves(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as fh:
        return [row["save"] for row in csv.DictReader(fh) if row.get("save")]


if __name__ == "__main__":
    sys.exit(main())
