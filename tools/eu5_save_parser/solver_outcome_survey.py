#!/usr/bin/env python3
"""Replay the shipped solver offline and report its outcome per save.

Rebuilds each country's 4xK matrix from the exported location caches, then
reproduces the runtime pipeline:

    size prefilter (num_locations < 5)  ->  raw only
    exact 4x4 solve                     ->  adopt if all factors >= 0
    209-vertex sweep, hard no-worsen    ->  adopt best by scaled L1
    otherwise                            ->  raw fallback

Reports the outcome split and, for each path, the error improvement against
raw on both scaled metrics. Feasibility for the "unsolvable" bucket comes from
the all-location cone test, which bounds what any classification can reach.

Usage:
    python tools/eu5_save_parser/solver_outcome_survey.py
    python tools/eu5_save_parser/solver_outcome_survey.py --saves 1337_10_02 1386 1743
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ANALYSIS_DIR = Path("data/save_analysis")
CONE_CSV = ANALYSIS_DIR / "cone_survey_all.csv"
SIZE_GATE = 5
NEGLIGIBLE = 1e-5
TIE_BAND = 0.01

# Three timepoints spanning the campaign. The 1337 cluster holds nine
# near-identical states, so only one is taken -- including more would just
# weight the early game without adding information.
DEFAULT_PICKS = ("1337_10_02_d95e1b3a", "1386_03_07", "1743_04_01")

STRATA = ("nobles", "clergy", "burghers", "lower")


def find_save_dirs(picks: tuple[str, ...]) -> list[tuple[str, Path]]:
    out = []
    for pick in picks:
        hits = [d for d in ANALYSIS_DIR.iterdir()
                if d.is_dir() and d.name.startswith("_all_") and pick in d.name]
        if hits:
            out.append((pick, sorted(hits)[0]))
    return out


def load_countries(save_dir: Path) -> dict[str, dict]:
    """Group locations by owner and build each country's matrix and target."""
    path = save_dir / "locations.csv"
    if not path.exists():
        return {}

    by_owner: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            tag = (row.get("owner_tag") or "").strip()
            if not tag:
                continue
            by_owner.setdefault(tag, []).append(row)

    def num(row: dict, key: str) -> float:
        try:
            return float(row.get(key) or 0.0)
        except ValueError:
            return 0.0

    countries: dict[str, dict] = {}
    for tag, locs in by_owner.items():
        n = len(locs)
        # Target: nationwide liquid funds per stratum (lower = commoners+tribesmen).
        t = np.zeros(4)
        for r in locs:
            t[0] += num(r, "sol_location_nobles_liquid_funds")
            t[1] += num(r, "sol_location_clergy_liquid_funds")
            t[2] += num(r, "sol_location_burghers_liquid_funds")
            t[3] += (num(r, "sol_location_commoners_liquid_funds")
                     + num(r, "sol_location_tribesmen_liquid_funds"))

        # Matrix: raw-weighted base spending, one column per class.
        M = np.zeros((4, 4))
        for r in locs:
            k = int(num(r, "sol_location_demand_class"))
            if not 1 <= k <= 4:
                continue
            raw = num(r, "sol_location_raw_demand_scale")
            col = k - 1
            M[0, col] += raw * num(r, "sol_location_nobles_base_spending")
            M[1, col] += raw * num(r, "sol_location_clergy_base_spending")
            M[2, col] += raw * num(r, "sol_location_burghers_base_spending")
            M[3, col] += raw * (num(r, "sol_location_commoners_base_spending")
                                + num(r, "sol_location_tribesmen_base_spending"))

        # All-location matrix for the cone bound.
        A = np.zeros((4, n))
        for j, r in enumerate(locs):
            raw = num(r, "sol_location_raw_demand_scale")
            A[0, j] = raw * num(r, "sol_location_nobles_base_spending")
            A[1, j] = raw * num(r, "sol_location_clergy_base_spending")
            A[2, j] = raw * num(r, "sol_location_burghers_base_spending")
            A[3, j] = raw * (num(r, "sol_location_commoners_base_spending")
                             + num(r, "sol_location_tribesmen_base_spending"))

        countries[tag] = {"n": n, "M": M, "t": t, "A": A}
    return countries


def metrics(M: np.ndarray, f: np.ndarray, t: np.ndarray) -> tuple[float, float]:
    """Scaled L1 (mean relative row residual) and scaled L-infinity."""
    pred = M @ f
    r = np.zeros(4)
    for s in range(4):
        if abs(t[s]) > NEGLIGIBLE:
            r[s] = abs(pred[s] - t[s]) / abs(t[s])
    return float(r.mean()), float(r.max())


def exact_solve(M: np.ndarray, t: np.ndarray) -> np.ndarray | None:
    if abs(np.linalg.det(M)) < 1e-9:
        return None
    try:
        x = np.linalg.solve(M, t)
    except np.linalg.LinAlgError:
        return None
    if np.all(x >= -1e-9):
        return np.maximum(x, 0.0)
    return None


def vertex_sweep(M: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Hard no-worsen sweep: L1 primary, L-inf as a 1% tie-break.

    Enumerates the same family the runtime does: pick which columns are free
    and solve the corresponding square subsystem, zeroing the rest.
    """
    best_f = np.ones(4)
    raw_l1, raw_linf = metrics(M, best_f, t)
    best_l1, best_linf = raw_l1, raw_linf

    for k in range(1, 5):
        for cols in itertools.combinations(range(4), k):
            for rows in itertools.combinations(range(4), k):
                sub = M[np.ix_(rows, cols)]
                if abs(np.linalg.det(sub)) < 1e-9:
                    continue
                try:
                    xs = np.linalg.solve(sub, t[list(rows)])
                except np.linalg.LinAlgError:
                    continue
                if np.any(xs < 0):
                    continue
                f = np.zeros(4)
                for idx, c in enumerate(cols):
                    f[c] = xs[idx]
                l1, linf = metrics(M, f, t)
                # Hard constraint: neither metric may worsen against raw.
                if l1 > raw_l1 or linf > raw_linf:
                    continue
                tie = TIE_BAND * best_l1
                if l1 < best_l1 - tie or (l1 < best_l1 + tie and linf < best_linf):
                    best_f, best_l1, best_linf = f, l1, linf
    return best_f, best_l1, best_linf


def cone_feasible(A: np.ndarray, t: np.ndarray) -> bool:
    from scipy.optimize import nnls
    try:
        x, _ = nnls(A, t)
    except Exception:
        return False
    denom = np.linalg.norm(t)
    if denom < NEGLIGIBLE:
        return True
    return float(np.linalg.norm(A @ x - t) / denom) < 0.01


def classify(save_dir: Path) -> list[dict]:
    """Return one record per country describing its path and error."""
    out = []
    for tag, c in load_countries(save_dir).items():
        n, M, t = c["n"], c["M"], c["t"]
        if np.linalg.norm(t) < NEGLIGIBLE or M.sum() < NEGLIGIBLE:
            continue

        raw_l1, raw_linf = metrics(M, np.ones(4), t)
        rec = {"tag": tag, "n": n, "raw_l1": raw_l1, "raw_linf": raw_linf}

        if n < SIZE_GATE:
            rec.update(path="gated", l1=raw_l1, linf=raw_linf)
            out.append(rec)
            continue

        x = exact_solve(M, t)
        if x is not None:
            l1, linf = metrics(M, x, t)
            rec.update(path="exact", l1=l1, linf=linf)
            out.append(rec)
            continue

        f, l1, linf = vertex_sweep(M, t)
        improved = l1 < raw_l1 - 1e-12 or linf < raw_linf - 1e-12
        if improved:
            rec.update(path="approx", l1=l1, linf=linf)
        else:
            rec.update(path="unsolvable", l1=raw_l1, linf=raw_linf)
        out.append(rec)
    return out


def fmt(count: int, total: int) -> str:
    return f"{count:,}（{100 * count / total:.1f}%）" if total else "-"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saves", nargs="*", default=list(DEFAULT_PICKS))
    args = ap.parse_args()

    dirs = find_save_dirs(tuple(args.saves))
    if not dirs:
        print("no matching save directories", file=sys.stderr)
        return 1

    results = {}
    for label, d in dirs:
        recs = classify(d)
        if recs:
            results[label] = recs
            print(f"[survey] {label}: {len(recs)} countries", file=sys.stderr)

    print()
    print("=== 4.1 可行率 ===")
    order = ("gated", "unsolvable", "approx", "exact")
    names = {"gated": "预筛未通过 → raw", "unsolvable": "不可解 → raw",
             "approx": "近似解", "exact": "精确解"}
    print(f"  {'类别':<20}", end="")
    for label in results:
        print(f"{label:>22}", end="")
    print()
    for p in order:
        print(f"  {names[p]:<20}", end="")
        for label, recs in results.items():
            print(f"{fmt(sum(1 for r in recs if r['path'] == p), len(recs)):>22}", end="")
        print()
    print(f"  {'合计':<20}", end="")
    for label, recs in results.items():
        print(f"{len(recs):>22,}", end="")
    print()

    print()
    print("=== 4.2 改善率 ===")
    print("  改善率按每个国家单独计算后取中位数，不是拿中位 raw 除中位解后。")
    for metric, rk, ck in (("缩放 L1", "raw_l1", "l1"), ("缩放 Linf", "raw_linf", "linf")):
        print(f"\n  [{metric}]")
        print(f"    {'路径':<10}{'存档':<22}{'国家数':>7}{'raw 中位':>10}"
              f"{'解后中位':>10}{'改善率中位':>12}")
        for p in ("exact", "approx"):
            for label, recs in results.items():
                sel = [r for r in recs if r["path"] == p]
                if not sel:
                    continue
                raw = np.median([r[rk] for r in sel])
                got = np.median([r[ck] for r in sel])
                # Per-country improvement, then take the median of those.
                per = [1 - r[ck] / r[rk] for r in sel if r[rk] > 1e-12]
                imp = np.median(per) * 100 if per else 0.0
                print(f"    {names[p]:<10}{label:<22}{len(sel):>7,}{raw:>10.4f}"
                      f"{got:>10.4f}{imp:>11.1f}%")

    print()
    print("=== 5.2 / 5.3 月度成本（按实测路径分布，非可行性上界）===")
    RAW, CLS, SETUP, EXACT, SWEEP = 70, 37, 120, 112, 45_562
    print(f"  {'存档':<22}{'C':>7}{'L':>8}{'扫掠数':>8}{'全开+预筛':>14}"
          f"{'AI 降频':>14}{'扫掠占比':>10}")
    for label, recs in results.items():
        C = len(recs)
        L = sum(r["n"] for r in recs)
        entered = [r for r in recs if r["path"] != "gated"]
        swept = [r for r in recs if r["path"] in ("approx", "unsolvable")]
        raw_cost = RAW * L
        solve = (CLS * sum(r["n"] for r in entered) + SETUP * len(entered)
                 + EXACT * len(entered) + SWEEP * len(swept))
        full = raw_cost + solve
        human = 1.0 / C
        reduced = raw_cost + solve * (human + (1 - human) / 12)
        share = SWEEP * len(swept) / full * 100
        print(f"  {label:<22}{C:>7,}{L:>8,}{len(swept):>8,}{full:>14,.0f}"
              f"{reduced:>14,.0f}{share:>9.1f}%")
    print(f"\n  一次扫掠 = {SWEEP / (RAW + CLS):.0f} 个地点的逐地点工作量；"
          f"平均国家规模仅 {min(sum(r['n'] for r in v) / len(v) for v in results.values()):.1f}"
          f"-{max(sum(r['n'] for r in v) / len(v) for v in results.values()):.1f} 个地点")

    print()
    print("=== 4.3 预筛效果 ===")
    # For the gated countries, replay what they would have got had they entered.
    stats = {}
    for label, d in dirs:
        if label not in results:
            continue
        recs = {r["tag"]: r for r in results[label]}
        cs = load_countries(d)
        n_gate = n_exact = n_approx = n_none = 0
        loc_gate = loc_all = 0
        for tag, r in recs.items():
            loc_all += r["n"]
            if r["path"] != "gated":
                continue
            n_gate += 1
            loc_gate += r["n"]
            M, t = cs[tag]["M"], cs[tag]["t"]
            if exact_solve(M, t) is not None:
                n_exact += 1
                continue
            f, l1, linf = vertex_sweep(M, t)
            raw_l1, raw_linf = r["raw_l1"], r["raw_linf"]
            if l1 < raw_l1 - 1e-12 or linf < raw_linf - 1e-12:
                n_approx += 1
            else:
                n_none += 1
        stats[label] = dict(total=len(recs), gate=n_gate, loc_gate=loc_gate,
                            loc_all=loc_all, would_exact=n_exact,
                            would_approx=n_approx, would_none=n_none)

    print(f"  {'项目':<28}", end="")
    for label in stats:
        print(f"{label:>22}", end="")
    print()
    lines = [
        ("过滤掉的国家", lambda s: fmt(s["gate"], s["total"])),
        ("放弃的地点遍历量", lambda s: fmt(s["loc_gate"], s["loc_all"])),
        ("其中本可精确求解", lambda s: fmt(s["would_exact"], s["gate"])),
        ("其中本可近似改善", lambda s: fmt(s["would_approx"], s["gate"])),
        ("其中本来也无解", lambda s: fmt(s["would_none"], s["gate"])),
    ]
    for name, fn in lines:
        print(f"  {name:<28}", end="")
        for label in stats:
            print(f"{fn(stats[label]):>22}", end="")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
