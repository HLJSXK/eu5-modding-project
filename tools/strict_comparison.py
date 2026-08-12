"""Compare current implementation vs strict no-worsen vertex selector.

Strict selector:
  - Enumerate all 70 vertex candidates
  - Filter to scaled_L1 <= raw_L1 AND scaled_Linf <= raw_Linf
  - Choose min(scaled_L1), tie-break on scaled_Linf
  - Fallback to raw if no candidate passes
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.eu5_save_parser.demand_analysis import (  # noqa: E402
    DEFAULT_EPSILON,
    _read_inputs,
    build_class_matrix,
    saved_assignments,
)
from tools.eu5_save_parser.lexicographic_bench import (  # noqa: E402
    adopted_factors,
    enumerate_vertices,
    metrics,
)

TIE = 0.01
STRATA = ("nobles", "clergy", "burghers", "lower")


def strict_selector(matrix, target):
    """Strict no-worsen: both scaled L1% and L∞% must not exceed raw."""

    raw = metrics(matrix, target, [1.0] * 4)
    raw_L1, raw_Linf = raw[0], raw[1]
    best = None
    best_L1 = None
    best_Linf = None
    for factors in enumerate_vertices(matrix, target):
        m = metrics(matrix, target, factors)
        L1, Linf = m[0], m[1]
        if L1 > raw_L1 + 1e-9 or Linf > raw_Linf + 1e-9:
            continue
        if best_L1 is None:
            best, best_L1, best_Linf = factors, L1, Linf
            continue
        scale = max(1e-9, best_L1)
        if L1 < best_L1 - TIE * scale:
            best, best_L1, best_Linf = factors, L1, Linf
        elif L1 < best_L1 + TIE * scale and Linf < best_Linf:
            best, best_L1, best_Linf = factors, L1, Linf
    if best is None:
        best = (1.0, 1.0, 1.0, 1.0)
    return best, metrics(matrix, target, best)


def uncapped_selector(matrix, target):
    """Uncapped Pareto: min scaled_L1, tie-break on scaled_Linf."""

    best = None
    best_L1 = None
    best_Linf = None
    for factors in enumerate_vertices(matrix, target):
        m = metrics(matrix, target, factors)
        L1, Linf = m[0], m[1]
        if best_L1 is None:
            best, best_L1, best_Linf = factors, L1, Linf
            continue
        scale = max(1e-9, best_L1)
        if L1 < best_L1 - TIE * scale:
            best, best_L1, best_Linf = factors, L1, Linf
        elif L1 < best_L1 + TIE * scale and Linf < best_Linf:
            best, best_L1, best_Linf = factors, L1, Linf
    return best, metrics(matrix, target, best)


def collect_all():
    """Per-country comparison: current vs strict vs uncapped."""

    rows = []
    for directory in sorted((ROOT / "data/save_analysis").glob("_all_*")):
        if not (directory / "countries.csv").is_file():
            continue
        countries, by_owner = _read_inputs(directory)
        recorded = adopted_factors(directory)
        for country in countries:
            usable = [
                l
                for l in by_owner.get(country.owner_id, [])
                if sum(l.spending) > DEFAULT_EPSILON
            ]
            if not usable or all(
                abs(v) <= DEFAULT_EPSILON for v in country.target
            ):
                continue
            assignments = saved_assignments(usable)
            if not assignments:
                continue
            matrix, counts, _ = build_class_matrix(usable, assignments)
            if any(count <= 0 for count in counts):
                continue
            entry = recorded.get(country.owner_tag, {})
            factors = entry.get("factors") or [None] * 4
            if any(v is None for v in factors):
                continue
            try:
                if float(entry.get("exact_status") or 0) == 1.0:
                    continue
            except ValueError:
                continue
            target = list(country.target)
            raw = metrics(matrix, target, [1.0] * 4)
            current = metrics(matrix, target, factors)
            strict_f, strict_m = strict_selector(matrix, target)
            uncap_f, uncap_m = uncapped_selector(matrix, target)
            rows.append(
                {
                    "tag": country.owner_tag,
                    "locations": len(usable),
                    "target": target,
                    "raw": raw,
                    "current": current,
                    "strict": strict_m,
                    "uncapped": uncap_m,
                    "strict_factors": strict_f,
                    "strict_is_raw": all(
                        abs(v - 1.0) < 1e-9 for v in strict_f
                    ),
                }
            )
    return rows


def percentile(values, q):
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))]


def main() -> None:
    rows = collect_all()
    print(f"Exact-failed countries analysed: {len(rows)}\n")

    print("=" * 78)
    print("SCALED L1% (mean relative deviation — PRIMARY OBJECTIVE)")
    print("=" * 78)
    print(
        f"{'Approach':20} {'median':>10} {'p10':>10} {'p90':>10} "
        f"{'better than current':>20}"
    )
    print("-" * 78)
    for label, key in [
        ("Current (adopted)", "current"),
        ("Strict no-worsen", "strict"),
        ("Uncapped Pareto", "uncapped"),
    ]:
        vals = [r[key][0] for r in rows]
        better = sum(1 for r in rows if r[key][0] < r["current"][0] - 1e-9)
        print(
            f"{label:20} {percentile(vals, 0.5):10.5f} "
            f"{percentile(vals, 0.1):10.5f} {percentile(vals, 0.9):10.5f} "
            f"{better:9} ({better / len(rows) * 100:5.1f}%)"
        )
    gains_strict = [
        r["current"][0] - r["strict"][0] for r in rows
    ]
    gains_uncap = [
        r["current"][0] - r["uncapped"][0] for r in rows
    ]
    print(f"\nImprovement over current (higher = better):")
    print(
        f"  Strict  : median {percentile(gains_strict, 0.5):+.5f}  "
        f"p10 {percentile(gains_strict, 0.1):+.5f}  "
        f"p90 {percentile(gains_strict, 0.9):+.5f}"
    )
    print(
        f"  Uncapped: median {percentile(gains_uncap, 0.5):+.5f}  "
        f"p10 {percentile(gains_uncap, 0.1):+.5f}  "
        f"p90 {percentile(gains_uncap, 0.9):+.5f}"
    )

    print("\n" + "=" * 78)
    print("SCALED L∞% (worst-stratum relative deviation — SECONDARY OBJECTIVE)")
    print("=" * 78)
    print(
        f"{'Approach':20} {'median':>10} {'p10':>10} {'p90':>10} "
        f"{'better than current':>20}"
    )
    print("-" * 78)
    for label, key in [
        ("Current (adopted)", "current"),
        ("Strict no-worsen", "strict"),
        ("Uncapped Pareto", "uncapped"),
    ]:
        vals = [r[key][1] for r in rows]
        better = sum(1 for r in rows if r[key][1] < r["current"][1] - 1e-9)
        print(
            f"{label:20} {percentile(vals, 0.5):10.5f} "
            f"{percentile(vals, 0.1):10.5f} {percentile(vals, 0.9):10.5f} "
            f"{better:9} ({better / len(rows) * 100:5.1f}%)"
        )

    print("\n" + "=" * 78)
    print("CONSTRAINT SATISFACTION & FALLBACK")
    print("=" * 78)
    strict_raw = sum(1 for r in rows if r["strict_is_raw"])
    strict_L1_worse = sum(
        1 for r in rows if r["strict"][0] > r["raw"][0] + 1e-9
    )
    strict_Linf_worse = sum(
        1 for r in rows if r["strict"][1] > r["raw"][1] + 1e-9
    )
    uncap_L1_worse = sum(
        1 for r in rows if r["uncapped"][0] > r["raw"][0] + 1e-9
    )
    uncap_Linf_worse = sum(
        1 for r in rows if r["uncapped"][1] > r["raw"][1] + 1e-9
    )
    print(f"Strict selector:")
    print(
        f"  Fallback to raw         : {strict_raw:5} "
        f"({strict_raw / len(rows) * 100:5.1f}%)"
    )
    print(
        f"  L1% worsens vs raw      : {strict_L1_worse:5} "
        f"({strict_L1_worse / len(rows) * 100:5.1f}%)"
    )
    print(
        f"  L∞% worsens vs raw      : {strict_Linf_worse:5} "
        f"({strict_Linf_worse / len(rows) * 100:5.1f}%)"
    )
    print(f"\nUncapped selector (for reference):")
    print(
        f"  L1% worsens vs raw      : {uncap_L1_worse:5} "
        f"({uncap_L1_worse / len(rows) * 100:5.1f}%)"
    )
    print(
        f"  L∞% worsens vs raw      : {uncap_Linf_worse:5} "
        f"({uncap_Linf_worse / len(rows) * 100:5.1f}%)"
    )

    print("\n" + "=" * 78)
    print("COST OF STRICT CONSTRAINT")
    print("=" * 78)
    l1_lost = [
        r["strict"][0] - r["uncapped"][0]
        for r in rows
        if not r["strict_is_raw"]
    ]
    print(
        f"L1% given up vs uncapped (non-fallback cases, n={len(l1_lost)}):"
    )
    print(
        f"  median {percentile(l1_lost, 0.5):+.5f}  "
        f"p90 {percentile(l1_lost, 0.9):+.5f}  "
        f"max {max(l1_lost) if l1_lost else 0:+.5f}"
    )
    significant = sum(1 for v in l1_lost if v > 0.01)
    print(
        f"  cases giving up >1pp: {significant} "
        f"({significant / len(l1_lost) * 100 if l1_lost else 0:.1f}% of non-fallback)"
    )


if __name__ == "__main__":
    main()
