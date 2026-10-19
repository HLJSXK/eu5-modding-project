"""'Water drop' study: scripted source curves driving a subcritical medium.

Sources are a bounded shared list whose x follows a scripted curve
(rise, hold, fall). Every other location uses the one-float rule with the
option-A queue and delta, in a medium whose gain G = rho + 6p is below 1, so
nothing self-sustains once sources fall. Measures reach (hop distance whose
peak x reaches 1/20/45), peak timing versus distance, time to calm, frozen
residue under delta, and abstract U. Optional 'decay snap' rule: a decrease
not larger than delta drops x to zero.

Synthetic 13,572-node hex grid, test coefficients, no EU5 timing claim.
Only --output writes a file.
"""

import argparse
from collections import deque
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from immunity_lock_study import NBRS, N, CENTER, W, H  # noqa: E402

EPS = 1e-5


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


def curve(t, start, rise=120, hold=240, fall=240, top=100.0):
    k = t - start
    if k < 0:
        return 0.0
    if k < rise:
        return top * k / rise
    if k < rise + hold:
        return top
    if k < rise + hold + fall:
        return top * (1 - (k - rise - hold) / fall)
    return 0.0


def run(rho, p, sources, delta=0.1, snap=False, months=2400, **cv):
    """sources: list of (location, start_month)."""
    x = [0.0] * N
    q = [-1] * N
    st = {"h": -1, "t": -1, "n": 0}
    is_src = [False] * N
    for s, _ in sources:
        is_src[s] = True
    U = 0
    monthly_U = []

    def push(v):
        if q[v] != -1:
            return 1
        q[v] = v
        if st["t"] == -1:
            st["h"] = v
        else:
            q[st["t"]] = v
        st["t"] = v
        st["n"] += 1
        return 4

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

    peak = [0.0] * N
    peak_t = [-1] * N
    members_series = []
    last_source_end = max(s0 for _, s0 in sources) + cv.get("rise", 120) + cv.get("hold", 240) + cv.get("fall", 240)
    calm_month = None
    snaps = [0, 0]   # total, while any source still scripted
    for t in range(months):
        U0 = U
        # scripted sources: bounded shared list, written each month
        for s, s0 in sources:
            new = curve(t, s0, **cv)
            U += 3                                   # evaluate curve, compare
            if new != x[s]:
                x[s] = new
                U += 1 + len(NBRS[s])
                for u in NBRS[s]:
                    if not is_src[u]:
                        U += push(u)
        n0 = st["n"]
        for _ in range(n0):
            v = pop()
            d = len(NBRS[v])
            old = x[v]
            y = rho * old
            for u in NBRS[v]:
                y += p * x[u]
            y = min(100.0, y)
            if y < EPS:
                y = 0.0
            U += 3 + 8 + 4 * d + 1                   # +1 shared source-list check
            dlt = y - old
            if snap and dlt < 0 and -dlt <= delta and old > 0:
                y = 0.0                              # stalled decline drops to zero
                snaps[0] += 1
                if t < last_source_end:
                    snaps[1] += 1
            if abs(y - old) > delta or (y == 0.0 and old != 0.0):
                x[v] = y
                U += 1 + d + push(v)
                for u in NBRS[v]:
                    if not is_src[u]:
                        U += push(u)
                if y > peak[v]:
                    peak[v] = y
                    peak_t[v] = t
        mem = sum(1 for a in x if a >= 1)
        members_series.append(mem)
        monthly_U.append(U - U0)
        if calm_month is None and t > last_source_end and st["n"] == 0:
            calm_month = t
        if calm_month is not None and t > calm_month + 12:
            break
    return x, peak, peak_t, members_series, monthly_U, U, calm_month, last_source_end, snaps


def summarize(name, res, dist):
    x, peak, peak_t, mem, mU, U, calm, src_end, snaps = res
    def reach(level):
        ds = [dist[v] for v in range(N) if peak[v] >= level and dist[v] >= 0]
        return max(ds) if ds else 0
    by_d = {}
    for dd in (3, 6, 10, 15, 20, 30, 45):
        vs = [v for v in range(N) if dist[v] == dd]
        if vs:
            pk = sorted(peak[v] for v in vs)[len(vs) // 2]
            tt = sorted(peak_t[v] for v in vs)[len(vs) // 2]
            by_d[dd] = {"median_peak_x": round(pk, 2), "median_peak_month": tt}
    resid = [a for a in x if a > 0]
    active = [u for u in mU if u > 0]
    return {"name": name, "reach_hops_peak_ge_1": reach(1), "reach_hops_peak_ge_20": reach(20),
            "reach_hops_peak_ge_45": reach(45), "locations_ever_member": sum(1 for a in peak if a >= 1),
            "max_members_at_once": max(mem), "members_at_end": mem[-1],
            "sources_end_month": src_end, "queue_empty_month": calm,
            "residual_positive_locations": len(resid), "residual_max_x": round(max(resid), 3) if resid else 0,
            "snap_to_zero_total": snaps[0], "snap_to_zero_before_sources_end": snaps[1], "total_U": U, "peak_monthly_U": max(mU), "mean_monthly_U_while_active": round(sum(active) / len(active)) if active else 0,
            "by_distance": by_d}


def study():
    dist_c = hops_from(CENTER)
    out = {}
    single = [(CENTER, 0)]
    cases = [
        ("drop_G0.99_rho0.93_p0.01", dict(rho=0.93, p=0.01)),
        ("drop_G0.995_rho0.8_p0.0325", dict(rho=0.8, p=0.0325)),
        ("drop_G0.999_rho0.4_p0.0998", dict(rho=0.4, p=0.0998)),
        ("drop_G0.9_rho0.78_p0.02", dict(rho=0.78, p=0.02)),
        ("drop_G0.99_snap", dict(rho=0.93, p=0.01, snap=True)),
        ("drop_G0.99_delta0", dict(rho=0.93, p=0.01, delta=0.0)),
    ]
    for name, kw in cases:
        out[name] = summarize(name, run(sources=single, **kw), dist_c)
    # Relay chain along the middle row: scripted milestone sources 15 hops apart.
    row = H // 2
    relays = [(row * W + c, i * 120) for i, c in enumerate((20, 35, 50, 65, 80, 95))]
    dist_r = hops_from(relays[0][0])
    for name, kw in [("relay6_G0.99", dict(rho=0.93, p=0.01)),
                     ("relay6_G0.99_snap", dict(rho=0.93, p=0.01, snap=True))]:
        out[name] = summarize(name, run(sources=relays, months=3000, **kw), dist_r)
    out["relay_sources"] = [{"col": c % W, "start_month": s} for c, s in relays]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    res = study()
    if args.output:
        args.output.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in res.items():
        print(k, v)
    print("Synthetic abstract counts only; no EU5 timing claim.")


if __name__ == "__main__":
    main()
