"""Country-clock ripple: obsession spreads with the supercritical one-float core
(option A queue, delta 0.1); each country records the month it first gets a
member location (country-level variable), holds for T months, then all its
locations decay together through a per-country lazy factor S_c and stop
receiving input. No per-location field beyond x and the transient queue
pointer. Countries are a graph-Voronoi partition of the hex grid.

Abstract U, test coefficients, no EU5 timing claim. Only --output writes.
"""

import argparse
from collections import deque
import json
from pathlib import Path
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from immunity_lock_study import NBRS, N, CENTER  # noqa: E402

EPS = 1e-5


def partition(n_countries, seed=20261019):
    rng = random.Random(seed)
    seeds = rng.sample(range(N), n_countries)
    owner = [-1] * N
    dq = deque()
    for c, s in enumerate(seeds):
        owner[s] = c
        dq.append(s)
    while dq:
        v = dq.popleft()
        for u in NBRS[v]:
            if owner[u] < 0:
                owner[u] = owner[v]
                dq.append(u)
    return owner


def hops_from(src):
    dist = [-1] * N
    dist[src] = 0
    dq = deque([src])
    while dq:
        v = dq.popleft()
        for u in NBRS[v]:
            if dist[u] < 0:
                dist[u] = dist[v] + 1
                dq.append(u)
    return dist


def run(T=240, g_decay=0.98, rho=0.99, p=0.02, delta=0.1, n_countries=1600, months=2400):
    owner = partition(n_countries)
    members_of = [[] for _ in range(n_countries)]
    for v in range(N):
        members_of[owner[v]].append(v)
    dist = hops_from(CENTER)
    x = [0.0] * N
    q = [-1] * N
    st = {"h": -1, "t": -1, "n": 0}
    join = [-1] * n_countries        # country-level: first month with a member
    S = [1.0] * n_countries          # country-level lazy factor
    decaying = [False] * n_countries
    finished = [False] * n_countries
    U = 0

    def push(v):
        if decaying[owner[v]]:
            return 2                 # owner check rejects: decaying land takes no input
        if q[v] != -1:
            return 3
        q[v] = v
        if st["t"] == -1:
            st["h"] = v
        else:
            q[st["t"]] = v
        st["t"] = v
        st["n"] += 1
        return 6

    def pop():
        v = st["h"]
        nx = q[v]
        if st["n"] == 1:
            st["h"] = st["t"] = -1
        else:
            st["h"] = nx
        q[v] = -1
        st["n"] -= 1
        return v

    def eff(v):
        c = owner[v]
        return x[v] * S[c] if decaying[c] else x[v]

    x[CENTER] = 25.0
    push(CENTER)
    for u in NBRS[CENTER]:
        push(u)
    series, monthly_U = [], []
    calm = None
    for t in range(months):
        U0 = U
        # country clocks: start decay, tick S, renormalise or finish
        for c in range(n_countries):
            if finished[c] or join[c] < 0:
                continue
            U += 2
            if not decaying[c] and t >= join[c] + T:
                decaying[c] = True
                S[c] = 1.0
            if decaying[c]:
                S[c] *= g_decay
                U += 1
                if S[c] < 0.1:
                    alive = False
                    for v in members_of[c]:
                        U += 4
                        y = x[v] * S[c]
                        x[v] = y if y >= EPS else 0.0
                        alive = alive or x[v] > 0
                    S[c] = 1.0
                    if not alive:
                        finished[c] = True
        n0 = st["n"]
        for _ in range(n0):
            v = pop()
            U += 3 + 2
            if decaying[owner[v]]:
                continue
            d = len(NBRS[v])
            old = x[v]
            y = rho * old
            for u in NBRS[v]:
                y += p * eff(u)
            y = min(100.0, y)
            if y < EPS:
                y = 0.0
            U += 8 + 6 * d                         # 4 per edge + owner/S read 2
            if abs(y - old) > delta or (y == 0.0 and old != 0.0):
                x[v] = y
                U += 1 + d + push(v)
                for u in NBRS[v]:
                    U += push(u)
                c = owner[v]
                if join[c] < 0 and y >= 1:
                    join[c] = t                    # country-level write
                    U += 2
        if t % 12 == 0:
            effs = [eff(v) for v in range(N)]
            mem = [v for v in range(N) if effs[v] >= 1]
            hot = [v for v in range(N) if effs[v] >= 45]
            dec = [v for v in range(N) if decaying[owner[v]] and effs[v] > 0]
            ring = sorted(dist[v] for v in hot)
            series.append({"month": t, "members": len(mem), "x_ge_45": len(hot),
                           "decaying_positive": len(dec),
                           "hot_ring_min_max_hops": [ring[0], ring[-1]] if ring else None,
                           "queue": st["n"]})
        monthly_U.append(U - U0)
        if calm is None and t > 0 and st["n"] == 0 and all(finished[c] or join[c] < 0 for c in range(n_countries)):
            calm = t
            break
    effs = [eff(v) for v in range(N)]
    active = [u for u in monthly_U if u > 0]
    return {"T_hold_months": T, "decay_gain_per_month": g_decay, "countries": n_countries,
            "mean_locations_per_country": N / n_countries, "calm_month": calm,
            "ever_joined_countries": sum(j >= 0 for j in join),
            "locations_never_member": sum(1 for v in range(N) if join[owner[v]] < 0),
            "residual_positive": sum(1 for a in effs if a > 0),
            "total_U": U, "peak_monthly_U": max(monthly_U),
            "mean_monthly_U": round(sum(active) / len(active)),
            "series_every_12_months": series}


def study():
    return {"T240": run(T=240), "T120": run(T=120)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    res = study()
    if args.output:
        args.output.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in res.items():
        print(k, {kk: vv for kk, vv in v.items() if kk != "series_every_12_months"})
        for row in v["series_every_12_months"][::10]:
            print("   ", row)
    print("Synthetic abstract counts only; no EU5 timing claim.")


if __name__ == "__main__":
    main()
