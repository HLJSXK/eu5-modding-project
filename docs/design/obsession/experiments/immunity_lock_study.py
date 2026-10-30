"""Independent check of the proposed saturation-lock / threshold / timed-immunity
simplifications against the one-float obsession core.

Synthetic ~13.6k-node hexagonal grid (d<=6), one good, asynchronous in-place
updates and reference-only candidate sets as in single_state_diffusion.py.
Timed scenarios (T1/T2) need a per-location clock; this script keeps one in a
side array ONLY to model the cost and dynamics of that idea. It also counts
how many shared cohort lists would be needed to replace the clock. Abstract U
only; no EU5 timing claim. Only --output writes a file.
"""

import argparse
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


EPS_ZERO = 0.00001
W, H = 117, 116


def hex_grid(width, height):
    nbrs = [[] for _ in range(width * height)]
    for r in range(height):
        for c in range(width):
            v = r * width + c
            ds = (((0, -1), (0, 1), (-1, -1), (-1, 0), (1, -1), (1, 0)) if r % 2 == 0
                  else ((0, -1), (0, 1), (-1, 0), (-1, 1), (1, 0), (1, 1)))
            for dr, dc in ds:
                rr, cc = r + dr, c + dc
                if 0 <= rr < height and 0 <= cc < width:
                    nbrs[v].append(rr * width + cc)
    return nbrs


NBRS = hex_grid(W, H)
N = len(NBRS)
CENTER = (H // 2) * W + W // 2
COL = [v % W for v in range(N)]


def run(rho, p, *, rounds=1500, delta=0.0, eps_in=0.0, sat_skip=False,
        region=None, t1=None, t2=None, contact_level=1.0, seed=CENTER):
    """region(v) -> (rho_v, p_v) overrides; t1/t2 in rounds (months)."""
    x = [0.0] * N
    params = [region(v) if region else (rho, p) for v in range(N)]
    contact = [None] * N   # side clock: modelling only, forbidden in design
    satur = [None] * N
    immune = [False] * N
    x[seed] = 25.0
    current = list(dict.fromkeys([seed, *NBRS[seed]]))
    cohorts_opened = set()
    stats = {"U": 0, "served": 0, "peak_active": 0, "rounds_run": 0,
             "membership_queries": 0, "skipped_saturated": 0}
    trace = []
    for r in range(rounds):
        if not current:
            break
        nxt = {}
        stats["peak_active"] = max(stats["peak_active"], len(current))
        for v in current:
            d = len(NBRS[v])
            rv, pv = params[v]
            old = x[v]
            if sat_skip and old >= 100.0 and not immune[v]:
                # hold at max: read + compare only; no neighbour reads
                stats["U"] += 3
                stats["skipped_saturated"] += 1
                continue
            if t1 is not None or t2 is not None:
                stats["membership_queries"] += 1
            if immune[v]:
                y = rv * old           # no incoming spread
                stats["U"] += 9
            else:
                s = 0.0
                for u in NBRS[v]:
                    s += pv * x[u]
                if s < eps_in:
                    s = 0.0
                y = rv * old + s
                stats["U"] += 8 + 4 * d
            y = 100.0 if y > 100 else y
            if y < EPS_ZERO:
                y = 0.0
            changed = abs(y - old) > delta or (y == 0.0 and old != 0.0)
            if changed:
                x[v] = y
                stats["U"] += 1 + 2 * d
                nxt[v] = None
                for u in NBRS[v]:
                    if sat_skip and x[u] >= 100.0:
                        stats["U"] += 1        # read-and-reject saturated target
                        continue
                    nxt[u] = None
            # timers (modelled clocks; cohort granularity = 12 rounds)
            if contact[v] is None and x[v] >= contact_level:
                contact[v] = r
                cohorts_opened.add(("contact", r // 12))
            if satur[v] is None and x[v] >= 100.0:
                satur[v] = r
                cohorts_opened.add(("sat", r // 12))
        stats["served"] += len(current)
        # timer expiry: cohort lists flip to immune decay and re-enter service
        if t1 is not None or t2 is not None:
            for v in range(N):   # cohort enumeration modelled; cost added below
                if immune[v]:
                    continue
                hit = ((t1 is not None and contact[v] is not None and r - contact[v] >= t1) or
                       (t2 is not None and satur[v] is not None and r - satur[v] >= t2))
                if hit:
                    immune[v] = True
                    nxt[v] = None
                    stats["U"] += 2
        current = list(nxt)
        stats["rounds_run"] = r + 1
        if r % 12 == 0:
            trace.append([r, len(current), sum(1 for val in x if val >= 1),
                          sum(1 for val in x if val >= 100), sum(1 for i in immune if i)])
    members = sum(1 for val in x if val >= 1)
    stats.update({"final_active": len(current), "final_members_x_ge_1": members,
                  "final_saturated": sum(1 for val in x if val >= 100),
                  "final_immune": sum(immune), "ever_contacted": sum(c is not None for c in contact),
                  "yearly_cohort_lists_opened": len(cohorts_opened),
                  "trace_every_12_rounds_[round,active,members,saturated,immune]": trace})
    return stats


def study():
    out = {"nodes": N, "rho": 0.99, "p": 0.02, "gain": 0.99 + 6 * 0.02,
           "note": "per-round test parameters; one round = one month; abstract U"}
    base = dict(rho=0.99, p=0.02)
    out["baseline"] = run(**base)
    out["sat_skip"] = run(**base, sat_skip=True)
    for dlt in (0.01, 0.1, 1.0, 10.0):
        out[f"delta_{dlt}"] = run(**base, delta=dlt)
    for e in (0.1, 1.0, 10.0):
        out[f"eps_in_{e}"] = run(**base, eps_in=e)
    out["sat_skip_delta_0.1"] = run(**base, sat_skip=True, delta=0.1)

    # Controlled east half. P3-like: rho 0.985, p*0.2 (gain 1.009, still >1).
    # Strong: rho 0.95, p*0.2 (gain 0.974 < 1).
    def p3(v):
        return (0.985, 0.004) if COL[v] > W // 2 + 5 else (0.99, 0.02)

    def strong(v):
        return (0.95, 0.004) if COL[v] > W // 2 + 5 else (0.99, 0.02)

    out["controlled_P3_like"] = run(**base, region=p3, rounds=2500)
    out["controlled_strong"] = run(**base, region=strong, rounds=2500)
    out["controlled_strong_delta_0.1"] = run(**base, region=strong, rounds=2500, delta=0.1)

    # Timed immunity: T2 hold after saturation then rho decay; T1 after contact.
    out["T2_240_after_saturation"] = run(**base, sat_skip=True, t2=240, rounds=2000)
    out["T1_480_after_contact_x_ge_1"] = run(**base, t1=480, rounds=2000)
    out["T1_120_after_contact_x_gt_0"] = run(**base, t1=120, contact_level=EPS_ZERO, rounds=2000)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    res = study()
    if args.output:
        args.output.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in res.items():
        if isinstance(v, dict):
            print(f"{k:32s} rounds={v['rounds_run']:5d} U={v['U']:>11,} peak={v['peak_active']:5d} "
                  f"members={v['final_members_x_ge_1']:5d} sat={v['final_saturated']:5d} "
                  f"immune={v['final_immune']:5d} contacted={v['ever_contacted']:5d} "
                  f"active_end={v['final_active']:5d} cohorts={v['yearly_cohort_lists_opened']}")
    print("Synthetic abstract counts only; timer scenarios use a modelling-only clock.")


if __name__ == "__main__":
    main()
