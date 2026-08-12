"""Sweep the L-infinity worsening cap for the scaled-L1-primary selector.

Selection rule under test:
  feasible  = vertices with scaled_L1 <= raw_L1  AND  scaled_Linf <= raw_Linf + cap
  choose    = min scaled_L1, tie-break (1% band) on scaled_Linf

cap = 0        -> strict "neither metric worsens"
cap = infinity -> unconstrained scaled-L1 primary
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

CAPS = (0.0, 0.02, 0.05, 0.10, 0.15, 0.20, float("inf"))
TIE = 0.01
STRATA = ("nobles", "clergy", "burghers", "lower")


def choose(candidates, raw_L1, raw_Linf, cap):
    """Pick the best candidate under the capped constraint set."""

    best = None
    for factors, (L1, Linf, abs_mean, abs_max) in candidates:
        if L1 > raw_L1 + 1e-9:
            continue
        if Linf > raw_Linf + cap + 1e-9:
            continue
        if best is None:
            best = (factors, L1, Linf, abs_max)
            continue
        scale = max(1e-9, best[1])
        if L1 < best[1] - TIE * scale:
            best = (factors, L1, Linf, abs_max)
        elif L1 < best[1] + TIE * scale and Linf < best[2]:
            best = (factors, L1, Linf, abs_max)
    return best


def collect(analysis: Path):
    """Per-country vertex set plus raw and adopted references."""

    countries, by_owner = _read_inputs(analysis)
    recorded = adopted_factors(analysis)
    out = []
    for country in countries:
        usable = [
            l
            for l in by_owner.get(country.owner_id, [])
            if sum(l.spending) > DEFAULT_EPSILON
        ]
        if not usable or all(abs(v) <= DEFAULT_EPSILON for v in country.target):
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
        candidates = [
            (f, metrics(matrix, target, f))
            for f in enumerate_vertices(matrix, target)
        ]
        out.append(
            {
                "tag": country.owner_tag,
                "target": target,
                "raw": raw,
                "adopted": metrics(matrix, target, factors),
                "candidates": candidates,
            }
        )
    return out


def percentile(values, q):
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))]


def main() -> None:
    rows = []
    for directory in sorted((ROOT / "data/save_analysis").glob("_all_*")):
        if not (directory / "countries.csv").is_file():
            continue
        rows.extend(collect(directory))
    print(f"exact-failed countries analysed: {len(rows)}\n")

    uncapped = {}
    header = (
        f"{'cap':>6} {'L1% vs adopted':>16} {'L1% vs raw':>12} "
        f"{'picks raw':>10} {'Linf worse':>11} {'Linf p50':>9} "
        f"{'Linf p90':>9} {'absx2':>7} {'L1 lost':>9}"
    )
    print(header)
    print("-" * len(header))
    for cap in CAPS:
        gains_adopted = []
        gains_raw = []
        picks_raw = 0
        linf_worse = []
        absx2 = 0
        l1_lost = []
        for row in rows:
            raw_L1, raw_Linf, _, raw_absmax = row["raw"]
            pick = choose(row["candidates"], raw_L1, raw_Linf, cap)
            if pick is None:
                picks_raw += 1
                continue
            factors, L1, Linf, absmax = pick
            if all(abs(v - 1.0) < 1e-9 for v in factors):
                picks_raw += 1
            gains_adopted.append(row["adopted"][0] - L1)
            gains_raw.append(raw_L1 - L1)
            if Linf > raw_Linf + 1e-9:
                linf_worse.append(Linf - raw_Linf)
            if raw_absmax > 1e-6 and absmax > raw_absmax * 2:
                absx2 += 1
            if cap == float("inf"):
                uncapped[row["tag"]] = L1
            else:
                reference = uncapped.get(row["tag"])
                if reference is not None:
                    l1_lost.append(L1 - reference)
        total = len(rows)
        label = "inf" if cap == float("inf") else f"{cap:.2f}"
        print(
            f"{label:>6} {percentile(gains_adopted, 0.5):16.5f} "
            f"{percentile(gains_raw, 0.5):12.5f} "
            f"{picks_raw / total * 100:9.1f}% "
            f"{len(linf_worse) / total * 100:10.1f}% "
            f"{percentile(linf_worse, 0.5):9.5f} "
            f"{percentile(linf_worse, 0.9):9.5f} "
            f"{absx2 / total * 100:6.1f}% "
            f"{percentile(l1_lost, 0.5) if l1_lost else 0.0:9.5f}"
        )
    print(
        "\nL1% columns are medians (higher = better). 'L1 lost' is the median\n"
        "scaled-L1 given up versus the uncapped selector, so 0 means the cap\n"
        "cost nothing at the median."
    )


if __name__ == "__main__":
    main()
