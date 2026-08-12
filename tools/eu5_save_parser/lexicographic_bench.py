"""Measure how far the shipped approximation is from the lexicographic optimum.

The declared objective is a four-level lexicographic order over the class
factor vector f >= 0:

  1. minimise mean_s |r_s| / t_s     (scaled L1)
  2. minimise max_s  |r_s| / t_s     (scaled L-infinity)
  3. minimise mean_s |r_s|           (raw L1)
  4. minimise max_s  |r_s|           (raw L-infinity)

where r = M f - t. Both scaled norms are piecewise linear, so the optimum sits
at a vertex where four conditions are active (a residual pinned to zero or a
factor pinned to its bound). Enumerating those vertices gives an exact offline
reference to benchmark the runtime L2/minimax candidate set against.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EPSILON = 1e-9
TIE = 1e-6


def metrics(matrix, target, factors):
    """Return the four declared objectives for one candidate."""

    residual = [
        sum(matrix[r][c] * factors[c] for c in range(4)) - target[r]
        for r in range(4)
    ]
    relative = [
        abs(residual[r]) / abs(target[r]) if abs(target[r]) > EPSILON else 0.0
        for r in range(4)
    ]
    absolute = [abs(v) for v in residual]
    return (
        sum(relative) / 4.0,
        max(relative),
        sum(absolute) / 4.0,
        max(absolute),
    )


def better(left, right) -> bool:
    """Lexicographic comparison with a relative tie band."""

    for a, b in zip(left, right):
        scale = max(1.0, abs(a), abs(b))
        if a < b - TIE * scale:
            return True
        if a > b + TIE * scale:
            return False
    return False


def solve_small(rows, rhs):
    """Gaussian elimination with partial pivoting on a square system."""

    size = len(rhs)
    if size == 0:
        return []
    work = [list(rows[i]) + [rhs[i]] for i in range(size)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(work[r][col]))
        if abs(work[pivot][col]) < 1e-13:
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


def enumerate_vertices(matrix, target):
    """All f >= 0 candidates where 4 conditions are active.

    A condition is either 'residual row r is exactly zero' or 'factor c is
    pinned to 0'. Choosing an exact-row set E and a zero-factor set Z with
    |E| + |Z| = 4 determines a square system in the free factors.
    """

    candidates = []
    for zero_count in range(5):
        exact_count = 4 - zero_count
        for zeros in itertools.combinations(range(4), zero_count):
            free = [c for c in range(4) if c not in zeros]
            if len(free) != exact_count:
                continue
            for rows in itertools.combinations(range(4), exact_count):
                sub = [[matrix[r][c] for c in free] for r in rows]
                rhs = [target[r] for r in rows]
                solved = solve_small(sub, rhs)
                if solved is None:
                    continue
                if any(v < -EPSILON for v in solved):
                    continue
                factors = [0.0] * 4
                for slot, column in enumerate(free):
                    factors[column] = max(0.0, solved[slot])
                candidates.append(tuple(factors))
    candidates.append((0.0, 0.0, 0.0, 0.0))
    candidates.append((1.0, 1.0, 1.0, 1.0))
    return candidates


def lexicographic_optimum(matrix, target):
    """Best vertex under the four-level order, plus its metrics."""

    best = None
    best_metrics = None
    for factors in enumerate_vertices(matrix, target):
        current = metrics(matrix, target, factors)
        if best_metrics is None or better(current, best_metrics):
            best = factors
            best_metrics = current
    return best, best_metrics


def adopted_factors(analysis: Path):
    """Read the class coefficients the game actually applied, per country tag."""

    import csv

    out = {}
    with (analysis / "countries.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            values = []
            for index in range(1, 5):
                raw = row.get(f"sol_country_class_coefficient_{index}", "")
                try:
                    values.append(float(raw) if raw != "" else None)
                except ValueError:
                    values.append(None)
            status = row.get("sol_country_demand_exact_status", "")
            out[row.get("owner_tag", "")] = {
                "factors": values,
                "exact_status": status,
                "strategy": row.get(
                    "sol_country_demand_selected_strategy", ""
                ),
            }
    return out


def benchmark(analysis: Path, *, tags=None):
    """Compare raw, the save's adopted factors, and the lexicographic optimum."""

    from tools.eu5_save_parser.demand_analysis import (
        DEFAULT_EPSILON,
        _read_inputs,
        build_class_matrix,
        saved_assignments,
    )

    countries, by_owner = _read_inputs(analysis, country_tags=tags)
    recorded = adopted_factors(analysis)
    rows = []
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
        target = list(country.target)
        entry = recorded.get(country.owner_tag, {})
        factors = entry.get("factors") or [None] * 4
        if any(v is None for v in factors):
            continue
        _, best_metrics = lexicographic_optimum(matrix, target)
        rows.append(
            {
                "tag": country.owner_tag,
                "locations": len(usable),
                "raw": metrics(matrix, target, [1.0] * 4),
                "adopted": metrics(matrix, target, factors),
                "best": best_metrics,
                "exact": entry.get("exact_status", ""),
            }
        )
    return rows


def pareto_optimal(matrix, target, *, tie_threshold=0.01):
    """Best vertex under scaled L1 primary, scaled L∞ tie-break.

    tie_threshold: if two candidates' scaled L1 differ by less than this
    fraction (relative to the better one), compare their scaled L∞ instead.
    """

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
        if L1 < best_L1 - tie_threshold * scale:
            best, best_L1, best_Linf = factors, L1, Linf
        elif L1 < best_L1 + tie_threshold * scale:
            if Linf < best_Linf:
                best, best_L1, best_Linf = factors, L1, Linf
    return best, metrics(matrix, target, best)


def compare_approaches(analysis: Path, *, tags=None):
    """Compare raw, adopted, lexicographic-best, and Pareto-optimal."""

    from tools.eu5_save_parser.demand_analysis import (
        DEFAULT_EPSILON,
        _read_inputs,
        build_class_matrix,
        saved_assignments,
    )

    countries, by_owner = _read_inputs(analysis, country_tags=tags)
    recorded = adopted_factors(analysis)
    rows = []
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
        target = list(country.target)
        entry = recorded.get(country.owner_tag, {})
        factors = entry.get("factors") or [None] * 4
        if any(v is None for v in factors):
            continue
        _, lex_metrics = lexicographic_optimum(matrix, target)
        _, pareto_metrics = pareto_optimal(matrix, target)
        rows.append(
            {
                "tag": country.owner_tag,
                "raw": metrics(matrix, target, [1.0] * 4),
                "adopted": metrics(matrix, target, factors),
                "lexicographic": lex_metrics,
                "pareto": pareto_metrics,
                "exact": entry.get("exact_status", ""),
            }
        )
    return rows


def constrained_pareto(matrix, target, *, tie_threshold=0.01):
    """Pareto-optimal under the constraint that both L1% and L∞% don't worsen vs raw."""

    raw_metrics = metrics(matrix, target, [1.0] * 4)
    raw_L1, raw_Linf = raw_metrics[0], raw_metrics[1]
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
        if L1 < best_L1 - tie_threshold * scale:
            best, best_L1, best_Linf = factors, L1, Linf
        elif L1 < best_L1 + tie_threshold * scale:
            if Linf < best_Linf:
                best, best_L1, best_Linf = factors, L1, Linf
    if best is None:
        best = (1.0, 1.0, 1.0, 1.0)
    return best, metrics(matrix, target, best)


def detailed_analysis(analysis: Path):
    """Full per-country breakdown with stratum-level residuals."""

    from tools.eu5_save_parser.demand_analysis import (
        DEFAULT_EPSILON,
        _read_inputs,
        build_class_matrix,
        saved_assignments,
    )

    countries, by_owner = _read_inputs(analysis)
    recorded = adopted_factors(analysis)
    rows = []
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
        target = list(country.target)
        entry = recorded.get(country.owner_tag, {})
        factors = entry.get("factors") or [None] * 4
        if any(v is None for v in factors):
            continue
        if entry.get("exact_status") == "1.00000":
            continue
        pareto_f, pareto_m = pareto_optimal(matrix, target)
        raw_f = [1.0] * 4
        raw_res = [
            sum(matrix[r][c] * raw_f[c] for c in range(4)) - target[r]
            for r in range(4)
        ]
        pareto_res = [
            sum(matrix[r][c] * pareto_f[c] for c in range(4)) - target[r]
            for r in range(4)
        ]
        raw_rel = [
            abs(raw_res[r]) / abs(target[r]) if abs(target[r]) > EPSILON else 0
            for r in range(4)
        ]
        pareto_rel = [
            abs(pareto_res[r]) / abs(target[r]) if abs(target[r]) > EPSILON else 0
            for r in range(4)
        ]
        rows.append(
            {
                "tag": country.owner_tag,
                "target": target,
                "raw_L1": sum(raw_rel) / 4,
                "raw_Linf": max(raw_rel),
                "pareto_L1": pareto_m[0],
                "pareto_Linf": pareto_m[1],
                "raw_residual": raw_res,
                "pareto_residual": pareto_res,
                "raw_relative": raw_rel,
                "pareto_relative": pareto_rel,
            }
        )
    return rows
