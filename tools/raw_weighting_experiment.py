"""Compare how the raw per-location factor can enter the country matrix.

Three column constructions for class k, over its member locations l:

  A) unweighted   c_k[s] = sum_l base[l,s]
  B) raw-weighted c_k[s] = sum_l base[l,s] * raw[l]        (shipped)
  C) additive     c_k[s] = sum_l base[l,s], solved against
                  t' = t - sum_l base[l,s]*raw[l], factors applied as raw + d_k

A and B differ in the column direction; C differs in where the origin sits.
The combined form gives each class two columns (unweighted and raw-weighted),
so its reachable cone contains both A's and B's by construction.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.eu5_save_parser.demand_analysis import (  # noqa: E402
    DEFAULT_EPSILON,
    _COUNTRY_BASELINE_COLUMNS,
    _COUNTRY_TARGET_COLUMNS,
    _number,
)

BASE_COLUMNS = (
    "sol_location_nobles_base_spending",
    "sol_location_clergy_base_spending",
    "sol_location_burghers_base_spending",
    "sol_location_commoners_base_spending",
    "sol_location_tribesmen_base_spending",
)
STRATA = ("nobles", "clergy", "burghers", "lower")


def load(analysis: Path):
    """Read countries and locations, keeping base spending and raw separate."""

    countries = {}
    with (analysis / "countries.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            owner = row.get("owner_id", "")
            target = [_number(row, k) for k in _COUNTRY_TARGET_COLUMNS]
            baseline = [_number(row, k) for k in _COUNTRY_BASELINE_COLUMNS]
            if all(abs(v) <= DEFAULT_EPSILON for v in target):
                continue
            countries[owner] = {
                "tag": row.get("owner_tag", ""),
                "target": target,
                "baseline": baseline,
                "exact_status": row.get("sol_country_demand_exact_status", ""),
            }

    locations = {}
    with (analysis / "locations.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            owner = row.get("owner_id", "")
            if owner not in countries:
                continue
            base_total = _number(row, "sol_location_base_total_spending")
            if base_total <= DEFAULT_EPSILON:
                continue
            raw = _number(row, "sol_location_raw_demand_scale")
            klass = round(_number(row, "sol_location_demand_class")) - 1
            if not 0 <= klass < 4:
                continue
            five = [_number(row, k) for k in BASE_COLUMNS]
            # Collapse commoners + tribesmen into the lower stratum.
            base = [five[0], five[1], five[2], five[3] + five[4]]
            locations.setdefault(owner, []).append(
                {"class": klass, "base": base, "raw": raw}
            )
    return countries, locations


def build_columns(members, weighted: bool):
    """One 4-vector per class: raw-weighted or plain base spending."""

    matrix = [[0.0] * 4 for _ in range(4)]
    counts = [0] * 4
    for entry in members:
        k = entry["class"]
        scale = entry["raw"] if weighted else 1.0
        counts[k] += 1
        for s in range(4):
            matrix[s][k] += entry["base"][s] * scale
    return matrix, counts


def solve_dense(matrix, rhs):
    size = len(rhs)
    work = [list(matrix[i]) + [rhs[i]] for i in range(size)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(work[r][col]))
        if abs(work[pivot][col]) < 1e-14:
            return None
        work[col], work[pivot] = work[pivot], work[col]
        for row in range(col + 1, size):
            f = work[row][col] / work[col][col]
            if f:
                for k in range(col, size + 1):
                    work[row][k] -= f * work[col][k]
    out = [0.0] * size
    for row in range(size - 1, -1, -1):
        acc = work[row][-1] - sum(
            work[row][k] * out[k] for k in range(row + 1, size)
        )
        out[row] = acc / work[row][row]
    return out


def nnls(columns, target, *, iterations=300):
    """Lawson-Hanson NNLS over a list of column vectors."""

    rows = len(target)
    count = len(columns)
    weights = [0.0] * count
    passive = []

    def residual_of(w):
        return [
            target[i] - sum(columns[j][i] * w[j] for j in range(count))
            for i in range(rows)
        ]

    residual = residual_of(weights)
    for _ in range(iterations):
        grad = [
            sum(columns[j][i] * residual[i] for i in range(rows))
            if j not in passive else float("-inf")
            for j in range(count)
        ]
        best = max(range(count), key=lambda j: grad[j])
        if grad[best] <= 1e-12:
            break
        passive.append(best)
        for _inner in range(60):
            size = len(passive)
            gram = [
                [
                    sum(columns[passive[a]][i] * columns[passive[b]][i]
                        for i in range(rows))
                    for b in range(size)
                ]
                for a in range(size)
            ]
            rhs = [
                sum(columns[passive[a]][i] * target[i] for i in range(rows))
                for a in range(size)
            ]
            trial = solve_dense(gram, rhs)
            if trial is None:
                passive.pop()
                break
            if min(trial) > 0:
                weights = [0.0] * count
                for slot, col in enumerate(passive):
                    weights[col] = trial[slot]
                break
            ratios = [
                weights[passive[a]] / (weights[passive[a]] - trial[a])
                for a in range(size)
                if trial[a] <= 0 and weights[passive[a]] > trial[a]
            ]
            alpha = min(ratios) if ratios else 0.0
            for slot, col in enumerate(passive):
                weights[col] += alpha * (trial[slot] - weights[col])
            passive = [c for c in passive if weights[c] > 1e-14]
            if not passive:
                break
        else:
            break
        residual = residual_of(weights)
    return weights, residual_of(weights)


def feasible(residual, target) -> bool:
    """Runtime per-row tolerance: |t| * 0.001 + 0.01."""

    return all(
        abs(residual[i]) <= abs(target[i]) * 0.001 + 0.01 for i in range(4)
    )


def evaluate(country, members):
    """Feasibility of each construction for one country."""

    weighted, counts = build_columns(members, True)
    plain, _ = build_columns(members, False)
    target = country["target"]
    if any(c <= 0 for c in counts):
        return None

    def cols(matrix):
        return [[matrix[s][k] for s in range(4)] for k in range(4)]

    out = {}
    # A) unweighted columns
    _, res = nnls(cols(plain), target)
    out["unweighted"] = (feasible(res, target), res)
    # B) raw-weighted columns (shipped)
    _, res = nnls(cols(weighted), target)
    out["raw_weighted"] = (feasible(res, target), res)
    # C) additive on top of raw: solve for d >= 0 against the deficit
    current = [sum(weighted[s][k] for k in range(4)) for s in range(4)]
    deficit = [target[s] - current[s] for s in range(4)]
    _, res = nnls(cols(plain), deficit)
    out["additive"] = (feasible(res, deficit), res)
    # D) combined: 8 columns (both constructions available simultaneously)
    _, res = nnls(cols(plain) + cols(weighted), target)
    out["combined"] = (feasible(res, target), res)
    return out


def main() -> None:
    dirs = sorted((ROOT / "data/save_analysis").glob("_all_*"))
    schemes = ("unweighted", "raw_weighted", "additive", "combined")
    totals = {s: 0 for s in schemes}
    scored = 0
    for directory in dirs:
        if not (directory / "countries.csv").is_file():
            continue
        countries, locations = load(directory)
        for owner, country in countries.items():
            members = locations.get(owner, [])
            if not members:
                continue
            result = evaluate(country, members)
            if result is None:
                continue
            scored += 1
            for s in schemes:
                if result[s][0]:
                    totals[s] += 1
    print(f"countries scored: {scored}\n")
    print(f"{'construction':16} {'feasible':>10} {'rate':>8}")
    print("-" * 36)
    for s in schemes:
        print(f"{s:16} {totals[s]:10} {totals[s] / scored * 100:7.2f}%")


if __name__ == "__main__":
    main()


# --------------------------------------------------------------- metrics ---
def metrics_of(columns, weights, target):
    """Scaled L1 and L-infinity of one nonnegative combination."""

    rows = len(target)
    pred = [
        sum(columns[j][i] * weights[j] for j in range(len(columns)))
        for i in range(rows)
    ]
    rel = [
        abs(pred[i] - target[i]) / abs(target[i])
        if abs(target[i]) > DEFAULT_EPSILON else 0.0
        for i in range(rows)
    ]
    return sum(rel) / rows, max(rel)


def best_under_constraint(columns, target, raw_l1, raw_linf, *, tie=0.01):
    """NNLS point, then keep it only if neither scaled metric worsens.

    The vertex sweep used in the runtime is exact for the 4-column case; for
    the 8-column case NNLS gives the least-squares optimum, which is the
    natural reference point for comparing constructions.
    """

    weights, _ = nnls(columns, target)
    l1, linf = metrics_of(columns, weights, target)
    if l1 > raw_l1 + 1e-9 or linf > raw_linf + 1e-9:
        return raw_l1, raw_linf, True   # falls back to raw
    return l1, linf, False


def evaluate_metrics(country, members):
    """Scaled L1/Linf for each construction, plus the raw baseline."""

    weighted, counts = build_columns(members, True)
    plain, _ = build_columns(members, False)
    if any(c <= 0 for c in counts):
        return None
    target = country["target"]

    def cols(matrix):
        return [[matrix[s][k] for s in range(4)] for k in range(4)]

    weighted_cols = cols(weighted)
    plain_cols = cols(plain)
    # Raw baseline: every class factor = 1 on the raw-weighted columns.
    raw_l1, raw_linf = metrics_of(weighted_cols, [1.0] * 4, target)
    if raw_l1 <= DEFAULT_EPSILON:
        return None

    out = {"raw": (raw_l1, raw_linf)}
    for name, columns in (
        ("unweighted", plain_cols),
        ("raw_weighted", weighted_cols),
        ("combined", plain_cols + weighted_cols),
    ):
        l1, linf, fell_back = best_under_constraint(
            columns, target, raw_l1, raw_linf
        )
        out[name] = (l1, linf, fell_back)
    return out


def percentile(values, q):
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))]


def main_metrics() -> None:
    schemes = ("unweighted", "raw_weighted", "combined")
    rows = []
    for directory in sorted((ROOT / "data/save_analysis").glob("_all_*")):
        if not (directory / "countries.csv").is_file():
            continue
        countries, locations = load(directory)
        for owner, country in countries.items():
            members = locations.get(owner, [])
            if not members:
                continue
            result = evaluate_metrics(country, members)
            if result is not None:
                rows.append(result)

    print(f"countries scored: {len(rows)}\n")
    print("SCALED L1 (mean relative deviation, lower is better)")
    print(f"{'construction':16} {'median':>9} {'p90':>9} {'fallback':>9}")
    print("-" * 48)
    raw_l1 = [r["raw"][0] for r in rows]
    print(f"{'raw baseline':16} {percentile(raw_l1, 0.5):9.5f} "
          f"{percentile(raw_l1, 0.9):9.5f} {'-':>9}")
    for s in schemes:
        vals = [r[s][0] for r in rows]
        fb = sum(1 for r in rows if r[s][2])
        print(f"{s:16} {percentile(vals, 0.5):9.5f} "
              f"{percentile(vals, 0.9):9.5f} {fb / len(rows) * 100:8.1f}%")

    print("\nSCALED L-INFINITY (worst stratum, lower is better)")
    print(f"{'construction':16} {'median':>9} {'p90':>9}")
    print("-" * 38)
    raw_linf = [r["raw"][1] for r in rows]
    print(f"{'raw baseline':16} {percentile(raw_linf, 0.5):9.5f} "
          f"{percentile(raw_linf, 0.9):9.5f}")
    for s in schemes:
        vals = [r[s][1] for r in rows]
        print(f"{s:16} {percentile(vals, 0.5):9.5f} {percentile(vals, 0.9):9.5f}")

    print("\nHEAD-TO-HEAD vs raw_weighted (shipped)")
    print(f"{'construction':16} {'L1 better':>11} {'L1 worse':>10} "
          f"{'median L1 gain':>15}")
    print("-" * 56)
    for s in ("unweighted", "combined"):
        gains = [r["raw_weighted"][0] - r[s][0] for r in rows]
        better = sum(1 for g in gains if g > 1e-9)
        worse = sum(1 for g in gains if g < -1e-9)
        print(f"{s:16} {better / len(rows) * 100:10.1f}% "
              f"{worse / len(rows) * 100:9.1f}% "
              f"{percentile(gains, 0.5):+15.5f}")


if __name__ == "__main__":
    main_metrics()
