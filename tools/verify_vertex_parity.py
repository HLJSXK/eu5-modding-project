"""Replay the generated vertex selector in Python and check parity.

Mirrors the emitted Jomini logic exactly: same 209 (row-order, free-column)
cases, same fixed-order elimination with the 0.00001 pivot floor, same
strict no-worsen constraint and 1% tie band. Compares the result against the
partial-pivoting reference to confirm the runtime form loses nothing.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from sol_vertex_selector_source import _vertex_cases  # noqa: E402
from tools.eu5_save_parser.demand_analysis import (  # noqa: E402
    DEFAULT_EPSILON,
    _read_inputs,
    build_class_matrix,
    saved_assignments,
)
from tools.eu5_save_parser.lexicographic_bench import (  # noqa: E402
    adopted_factors,
    metrics,
)

PIVOT_FLOOR = 0.00001
TIE = 0.01
CASES = _vertex_cases()


def runtime_solve(matrix, target, rows, free):
    """Fixed-order elimination exactly as the emitted primitives do it."""

    size = len(rows)
    if size == 0:
        return [0.0, 0.0, 0.0, 0.0]
    work = [
        [matrix[r][c] for c in free] + [target[r]]
        for r in rows
    ]
    for pivot in range(size):
        if abs(work[pivot][pivot]) <= PIVOT_FLOOR:
            return None
        for row in range(pivot + 1, size):
            factor = work[row][pivot] / work[pivot][pivot]
            if factor:
                for k in range(pivot, size + 1):
                    work[row][k] -= factor * work[pivot][k]
    delta = [0.0] * size
    for row in range(size - 1, -1, -1):
        if abs(work[row][row]) <= PIVOT_FLOOR:
            return None
        acc = work[row][-1] - sum(
            work[row][k] * delta[k] for k in range(row + 1, size)
        )
        delta[row] = acc / work[row][row]
    if any(v < 0 for v in delta):
        return None
    factors = [0.0] * 4
    for local, column in enumerate(free):
        factors[column] = delta[local]
    return factors


def runtime_selector(matrix, target):
    """Full replay of sol_country_demand_run_vertex_selector."""

    raw = metrics(matrix, target, [1.0] * 4)
    raw_l1, raw_linf = raw[0], raw[1]
    best_f = [1.0] * 4
    best_l1, best_linf = raw_l1, raw_linf
    found = False
    for rows, free in CASES:
        factors = runtime_solve(matrix, target, rows, free)
        if factors is None:
            continue
        current = metrics(matrix, target, factors)
        l1, linf = current[0], current[1]
        if l1 > raw_l1 or linf > raw_linf:
            continue
        tie = best_l1 * TIE
        take = False
        if l1 < best_l1 - tie:
            take = True
        elif l1 < best_l1 + tie and linf < best_linf:
            take = True
        if take:
            best_f, best_l1, best_linf = factors, l1, linf
            found = True
    if not found:
        best_f = [1.0] * 4
    return best_f, metrics(matrix, target, best_f)


def reference_selector(matrix, target):
    """Partial-pivoting reference over the same vertex set."""

    def solve(rows, free):
        size = len(rows)
        if size == 0:
            return [0.0] * 4
        work = [[matrix[r][c] for c in free] + [target[r]] for r in rows]
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
        delta = [0.0] * size
        for row in range(size - 1, -1, -1):
            acc = work[row][-1] - sum(
                work[row][k] * delta[k] for k in range(row + 1, size)
            )
            delta[row] = acc / work[row][row]
        if any(v < -1e-9 for v in delta):
            return None
        out = [0.0] * 4
        for local, column in enumerate(free):
            out[column] = max(0.0, delta[local])
        return out

    raw = metrics(matrix, target, [1.0] * 4)
    raw_l1, raw_linf = raw[0], raw[1]
    best_f = [1.0] * 4
    best_l1, best_linf = raw_l1, raw_linf
    for zero_count in range(5):
        exact = 4 - zero_count
        for zeros in itertools.combinations(range(4), zero_count):
            free = tuple(c for c in range(4) if c not in zeros)
            if len(free) != exact:
                continue
            for rows in itertools.combinations(range(4), exact):
                factors = solve(rows, free)
                if factors is None:
                    continue
                current = metrics(matrix, target, factors)
                l1, linf = current[0], current[1]
                if l1 > raw_l1 + 1e-9 or linf > raw_linf + 1e-9:
                    continue
                tie = best_l1 * TIE
                if l1 < best_l1 - tie or (
                    l1 < best_l1 + tie and linf < best_linf
                ):
                    best_f, best_l1, best_linf = factors, l1, linf
    return best_f, metrics(matrix, target, best_f)


def main() -> None:
    print(f"vertex cases in emitter: {len(CASES)}\n")
    rows = []
    for directory in sorted((ROOT / "data/save_analysis").glob("_all_*")):
        if not (directory / "countries.csv").is_file():
            continue
        recorded = adopted_factors(directory)
        countries, by_owner = _read_inputs(directory)
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
            status = entry.get("exact_status", "")
            if any(v is None for v in factors) or status == "":
                continue
            try:
                if float(status) == 1.0:
                    continue
            except ValueError:
                continue
            if any(v < 0 for v in factors):
                continue
            target = list(country.target)
            _, runtime_m = runtime_selector(matrix, target)
            _, reference_m = reference_selector(matrix, target)
            rows.append((runtime_m, reference_m, metrics(matrix, target, factors)))

    print(f"sample: {len(rows)}")
    for index, label in ((0, "scaled L1"), (1, "scaled Linf")):
        diffs = [r[0][index] - r[1][index] for r in rows]
        worse = sum(1 for v in diffs if v > 1e-6)
        gains = [r[2][index] - r[0][index] for r in rows]
        gains.sort()
        print(f"\n{label}:")
        print(
            f"  runtime vs pivoting reference: worse in {worse} case(s), "
            f"max delta {max(diffs):+.8f}"
        )
        print(
            f"  runtime vs shipped implementation: median gain "
            f"{gains[len(gains) // 2]:+.5f}"
        )


if __name__ == "__main__":
    main()
