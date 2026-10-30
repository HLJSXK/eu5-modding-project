"""Relaxed-state options for the obsession core: what one or two extra
per-location fields buy when native container complexity is not trusted.

A  transient queue pointer (exists only while a location is queued):
   intrusive FIFO + round count replaces current/next sets, dedupe and
   cursor; a still-pending target is not re-queued.
B  saturation timestamp: after x first reaches 100 the location holds for T2
   and then decays by a closed-form time formula; it is never served again
   and readers evaluate x_eff(now). Linear and exponential decay variants.
C  incoming neighbour sum S (push deltas, read O(1) at service).

Synthetic ~13.6k-node hex grid, abstract U, no EU5 timing claim.
Only --output writes a file.
"""

import argparse
import json
import math
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from immunity_lock_study import NBRS, N, CENTER  # noqa: E402

RHO, P, EPS, SEED = 0.99, 0.02, 0.00001, 25.0


def baseline(rounds=1500):
    """Current design: frozen current list, deduplicated next set."""
    x = [0.0] * N
    x[CENTER] = SEED
    cur = list(dict.fromkeys([CENTER, *NBRS[CENTER]]))
    U = served = set_ops = peak = r = 0
    while cur and r < rounds:
        peak = max(peak, len(cur))
        nxt = {}
        for v in cur:
            d = len(NBRS[v]); old = x[v]
            s = 0.0
            for u in NBRS[v]:
                s += P * x[u]
            y = min(100.0, RHO * old + s)
            if y < EPS:
                y = 0.0
            U += 8 + 4 * d
            if y != old:
                x[v] = y; U += 1 + 2 * d
                nxt[v] = None; set_ops += 1
                for u in NBRS[v]:
                    nxt[u] = None; set_ops += 1
        served += len(cur); cur = list(nxt); r += 1
    return {"rounds": r, "U": U, "served": served, "peak": peak,
            "native_set_insert_attempts": set_ops, "x": x}


def option_a(rounds=1500):
    """Intrusive FIFO: nxt_ptr[v] set <=> v queued. Only variable read/write."""
    x = [0.0] * N
    ptr = [None] * N          # the relaxed field; None = absent variable
    head = tail = None
    length = 0
    U = served = peak = 0
    max_live_ptr = 0

    def push(v):
        nonlocal head, tail, length
        if ptr[v] is not None:
            return 1                       # already pending: read only
        ptr[v] = v                         # tail points to itself
        if tail is None:
            head = v
        else:
            ptr[tail] = v
        tail = v; length += 1
        return 4

    def pop():
        nonlocal head, tail, length
        v = head
        nxt = ptr[v]
        head = None if nxt == v else nxt
        if head is None:
            tail = None
        ptr[v] = None; length -= 1
        return v

    x[CENTER] = SEED
    for v in (CENTER, *NBRS[CENTER]):
        push(v)
    r = 0
    while length and r < rounds:
        n0 = length                        # one logical round = n0 pops
        peak = max(peak, n0)
        max_live_ptr = max(max_live_ptr, length)
        for _ in range(n0):
            v = pop(); U += 3
            d = len(NBRS[v]); old = x[v]
            s = 0.0
            for u in NBRS[v]:
                s += P * x[u]
            y = min(100.0, RHO * old + s)
            if y < EPS:
                y = 0.0
            U += 8 + 4 * d
            if y != old:
                x[v] = y; U += 1 + d
                U += push(v)
                for u in NBRS[v]:
                    U += push(u)
        served += n0; r += 1
    return {"rounds": r, "U": U, "served": served, "peak": peak,
            "native_set_insert_attempts": 0, "max_live_pointer_fields": max_live_ptr, "x": x}


def option_c(rounds=1500):
    """Pushed unweighted neighbour sum S[v]; p is target-side so S stays exact."""
    x = [0.0] * N
    S = [0.0] * N
    x[CENTER] = SEED
    for u in NBRS[CENTER]:
        S[u] += SEED
    cur = list(dict.fromkeys([CENTER, *NBRS[CENTER]]))
    U = served = peak = r = 0
    while cur and r < rounds:
        peak = max(peak, len(cur))
        nxt = {}
        for v in cur:
            d = len(NBRS[v]); old = x[v]
            y = min(100.0, RHO * old + P * S[v])
            if y < EPS:
                y = 0.0
            U += 10
            if y != old:
                x[v] = y; delta = y - old
                U += 1 + 2 * d + 3 * d
                nxt[v] = None
                for u in NBRS[v]:
                    S[u] += delta
                    nxt[u] = None
        served += len(cur); cur = list(nxt); r += 1
    return {"rounds": r, "U": U, "served": served, "peak": peak, "x": x}


def option_b(t2=240, decay="exp", rounds=2000, slope=0.5):
    """T2 hold then closed-form decay from a saturation timestamp; no service."""
    x = [0.0] * N
    tsat = [None] * N                    # the relaxed field
    pow_cache_mults = math.ceil(math.log2(rounds)) * 2

    def x_eff(v, r):
        t = tsat[v]
        if t is None:
            return x[v], 0
        k = r - (t + t2)
        if k <= 0:
            return 100.0, 2
        if decay == "exp":
            val = 100.0 * RHO ** k; cost = 2 + pow_cache_mults
        else:
            val = 100.0 - slope * k; cost = 4
        return (val if val >= EPS else 0.0), cost

    x[CENTER] = SEED
    cur = list(dict.fromkeys([CENTER, *NBRS[CENTER]]))
    U = served = peak = r = 0
    trace = []
    while cur and r < rounds:
        peak = max(peak, len(cur))
        nxt = {}
        for v in cur:
            d = len(NBRS[v])
            if tsat[v] is not None:      # held or decaying: read field, skip
                U += 2
                continue
            old = x[v]
            s = 0.0
            for u in NBRS[v]:
                val, c = x_eff(u, r)
                s += P * val; U += c
            y = min(100.0, RHO * old + s)
            if y < EPS:
                y = 0.0
            U += 8 + 4 * d
            if y != old:
                x[v] = y; U += 1 + 2 * d
                nxt[v] = None
                for u in NBRS[v]:
                    if tsat[u] is None:
                        nxt[u] = None
                    else:
                        U += 1
            if y >= 100.0:
                tsat[v] = r; U += 2
        served += len(cur); cur = list(nxt); r += 1
        if r % 120 == 0:
            vals = [x_eff(v, r)[0] for v in range(N)]
            trace.append([r, len(cur), sum(a >= 1 for a in vals), sum(a >= 100 for a in vals)])
    # After the queue drains nothing is served; x_eff keeps evolving by time.
    end = max(r, rounds)
    vals = [x_eff(v, end)[0] for v in range(N)]
    return {"rounds_with_service": r, "U": U, "served": served, "peak": peak,
            "members_at_round_%d" % end: sum(a >= 1 for a in vals),
            "timestamp_fields": sum(t is not None for t in tsat),
            "trace_every_120_[round,active,members,held]": trace}


def study():
    out = {}
    b = baseline()
    a = option_a()
    c = option_c()
    maxdiff_a = max(abs(p - q) for p, q in zip(b.pop("x"), a.pop("x")))
    bx = baseline()["x"]
    maxdiff_c = max(abs(p - q) for p, q in zip(bx, c.pop("x")))
    a["max_abs_x_diff_vs_baseline"] = maxdiff_a
    c["max_abs_x_diff_vs_baseline"] = maxdiff_c
    out["baseline"] = b
    out["A_transient_queue_pointer"] = a
    out["C_incoming_sum"] = c
    out["B_T2_240_exp_decay"] = option_b(decay="exp")
    out["B_T2_240_linear_decay_0.5_per_month"] = option_b(decay="linear")
    out["reference_T2_240_timer_served_decay_from_immunity_lock_study_U"] = 463_159_888
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
            print(k, {kk: vv for kk, vv in v.items() if not kk.startswith("trace")})
        else:
            print(k, v)
    print("Synthetic abstract counts only; no EU5 timing claim.")


if __name__ == "__main__":
    main()
