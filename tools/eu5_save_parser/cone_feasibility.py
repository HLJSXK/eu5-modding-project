"""Decide whether a country's exact demand solve can be feasible at all.

Exact-solve feasibility means the target vector lies in the nonnegative cone
spanned by the four class columns. Because every class column is a sum of
nonnegative location vectors, the cone of any 4-way partition is contained in
the cone of all owned locations. So if the target is outside the all-location
cone, NO classifier can make the exact solve feasible -- changing scores,
class count, capacity allocation, or conditioning cannot help.

Run this before diagnosing negative_factor / -100% demand reports.

Usage:
  python -m tools.eu5_save_parser.cone_feasibility <analysis_dir> [--country TAG]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.eu5_save_parser.demand_analysis import (  # noqa: E402
    DEFAULT_EPSILON,
    _read_inputs,
)

STRATA = ("nobles", "clergy", "burghers", "lower")
FEASIBLE_TOLERANCE = 0.01


def _solve_dense(matrix, rhs):
    """Gaussian elimination with partial pivoting; None when singular."""

    size = len(rhs)
    work = [list(matrix[i]) + [rhs[i]] for i in range(size)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(work[r][col]))
        if abs(work[pivot][col]) < 1e-14:
            return None
        work[col], work[pivot] = work[pivot], work[col]
        for row in range(col + 1, size):
            factor = work[row][col] / work[col][col]
            if factor:
                for k in range(col, size + 1):
                    work[row][k] -= factor * work[col][k]
    out = [0.0] * size
    for row in range(size - 1, -1, -1):
        acc = work[row][-1] - sum(
            work[row][k] * out[k] for k in range(row + 1, size)
        )
        out[row] = acc / work[row][row]
    return out


def cone_residual(vectors, target, *, iterations: int = 4000) -> float:
    """Relative L1 residual of the best nonnegative combination of `vectors`.

    Projected gradient descent on min ||A w - t||^2 subject to w >= 0.
    A residual near zero means `target` lies inside the cone.
    """

    count = len(vectors)
    if not count:
        return float("inf")
    dimension = len(target)
    weights = [1.0] * count
    scale = sum(abs(v) for v in target) or 1.0
    largest = max(
        sum(v[i] * v[i] for i in range(dimension)) for v in vectors
    )
    step = 1.0 / max(1e-9, largest * count)
    for _ in range(iterations):
        residual = [
            sum(vectors[j][i] * weights[j] for j in range(count)) - target[i]
            for i in range(dimension)
        ]
        for j in range(count):
            gradient = sum(
                vectors[j][i] * residual[i] for i in range(dimension)
            )
            updated = weights[j] - step * 2.0 * gradient
            weights[j] = updated if updated > 0.0 else 0.0
    residual = [
        sum(vectors[j][i] * weights[j] for j in range(count)) - target[i]
        for i in range(dimension)
    ]
    return sum(abs(v) for v in residual) / scale


def ideal_factor_field(country, locations):
    """Minimum-norm per-location factors: argmin ||f - 1||^2 s.t. A f = target.

    Negative entries mark locations that would have to carry negative demand
    for the target to be met, which is the concrete reason the nonnegative
    problem is infeasible.
    """

    usable = [l for l in locations if sum(l.spending) > DEFAULT_EPSILON]
    if not usable:
        return None
    baseline = [sum(l.spending[i] for l in usable) for i in range(4)]
    gram = [
        [sum(l.spending[r] * l.spending[c] for l in usable) for c in range(4)]
        for r in range(4)
    ]
    dual = _solve_dense(
        gram, [country.target[i] - baseline[i] for i in range(4)]
    )
    if dual is None:
        return None
    return [
        1.0 + sum(l.spending[i] * dual[i] for i in range(4)) for l in usable
    ]


SUBSETS = (
    (0,), (1,), (2,), (3,),
    (0, 1), (0, 3), (1, 3), (2, 3),
    (0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3),
    (0, 1, 2, 3),
)


def analyse(country, locations) -> dict:
    usable = [l for l in locations if sum(l.spending) > DEFAULT_EPSILON]
    full = cone_residual(
        [list(l.spending) for l in usable], list(country.target)
    )
    subsets = {}
    for subset in SUBSETS:
        subsets[subset] = cone_residual(
            [[l.spending[i] for i in subset] for l in usable],
            [country.target[i] for i in subset],
            iterations=3000,
        )
    field = ideal_factor_field(country, locations)
    return {
        "locations": len(usable),
        "residual": full,
        "subsets": subsets,
        "field_min": min(field) if field else None,
        "field_negative": sum(1 for v in field if v < 0) if field else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Test whether a country's exact demand solve is feasible for ANY "
            "4-way classification (cone-containment bound)."
        )
    )
    parser.add_argument(
        "analysis",
        type=Path,
        help="parser export directory containing countries.csv and locations.csv",
    )
    parser.add_argument(
        "--country", action="append", default=[], metavar="TAG",
        help="restrict to this country tag; may be repeated",
    )
    args = parser.parse_args()

    tags = {tag.upper() for tag in args.country} or None
    countries, by_owner = _read_inputs(args.analysis, country_tags=tags)
    if not countries:
        print("no countries matched")
        return 1

    for country in countries:
        result = analyse(country, by_owner[country.owner_id])
        verdict = (
            "FEASIBLE for some classification"
            if result["residual"] <= FEASIBLE_TOLERANCE
            else "INFEASIBLE for every classification"
        )
        print(f"\n{country.owner_tag}  ({result['locations']} valid locations)")
        print(f"  all-location cone residual : {result['residual']:.6f}")
        print(f"  verdict                    : {verdict}")
        if result["field_min"] is not None:
            print(
                f"  ideal field min factor     : {result['field_min']:.4f}"
                f"   locations needing < 0: {result['field_negative']}"
            )
        print("  reachable strata subsets (residual, 0.000 = reachable):")
        for subset, value in result["subsets"].items():
            label = "+".join(STRATA[i][0].upper() for i in subset)
            flag = "" if value <= FEASIBLE_TOLERANCE else "  <-- conflict"
            print(f"    {label:<8} {value:.4f}{flag}")
        if result["residual"] > FEASIBLE_TOLERANCE:
            print(
                "  NOTE: no classifier change can fix this. Only relaxing the\n"
                "        target definition or accepting an approximation can."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def nnls(vectors, target, *, max_iterations: int = 200):
    """Lawson-Hanson active-set NNLS. Exact and fast for a 4-row system.

    Returns (weights, residual_vector). The passive set never exceeds the row
    count, so each inner solve is at most 4x4 regardless of location count.
    """

    rows = len(target)
    count = len(vectors)
    weights = [0.0] * count
    passive: list[int] = []

    def residual_of(w):
        return [
            target[i] - sum(vectors[j][i] * w[j] for j in range(count))
            for i in range(rows)
        ]

    residual = residual_of(weights)
    for _ in range(max_iterations):
        gradient = [
            sum(vectors[j][i] * residual[i] for i in range(rows))
            if j not in passive
            else float("-inf")
            for j in range(count)
        ]
        best = max(range(count), key=lambda j: gradient[j])
        if gradient[best] <= 1e-12:
            break
        passive.append(best)
        for _inner in range(60):
            size = len(passive)
            gram = [
                [
                    sum(
                        vectors[passive[a]][i] * vectors[passive[b]][i]
                        for i in range(rows)
                    )
                    for b in range(size)
                ]
                for a in range(size)
            ]
            rhs = [
                sum(vectors[passive[a]][i] * target[i] for i in range(rows))
                for a in range(size)
            ]
            trial = _solve_dense(gram, rhs)
            if trial is None:
                passive.pop()
                break
            if min(trial) > 0:
                for index in range(count):
                    weights[index] = 0.0
                for slot, column in enumerate(passive):
                    weights[column] = trial[slot]
                break
            ratios = [
                weights[passive[a]] / (weights[passive[a]] - trial[a])
                for a in range(size)
                if trial[a] <= 0 and weights[passive[a]] > trial[a]
            ]
            alpha = min(ratios) if ratios else 0.0
            for slot, column in enumerate(passive):
                weights[column] += alpha * (trial[slot] - weights[column])
            passive = [c for c in passive if weights[c] > 1e-14]
            if not passive:
                break
        else:
            break
        residual = residual_of(weights)
    return weights, residual_of(weights)
