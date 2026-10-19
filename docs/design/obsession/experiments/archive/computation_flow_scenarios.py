"""Synthetic workload scenarios for the one-float obsession core (doc 13).

Same asynchronous in-place rule and per-node reservation as
single_state_diffusion.py, run on a ~13.6k-node hexagonal grid (d=6) to show
how the active candidate set behaves in growth, saturation and decay phases.

Counts are abstract task U from the declared primitive reservation
(8 + 4*d_in + 1 + 2*d_out). They exclude native container, hashing, scope and
iteration costs and are NOT EU5 measurements. Only --output writes a file.
"""

import argparse
import json
import math
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


EPSILON = 0.00001
FIXED_QUANTUM = 0.00001  # assumption: five-decimal fixed point, not verified


def hex_grid(width, height):
    """Offset-row hexagonal grid; interior degree 6, borders fewer."""
    n = width * height
    nbrs = [[] for _ in range(n)]
    for r in range(height):
        for c in range(width):
            v = r * width + c
            if r % 2 == 0:
                deltas = ((0, -1), (0, 1), (-1, -1), (-1, 0), (1, -1), (1, 0))
            else:
                deltas = ((0, -1), (0, 1), (-1, 0), (-1, 1), (1, 0), (1, 1))
            for dr, dc in deltas:
                rr, cc = r + dr, c + dc
                if 0 <= rr < height and 0 <= cc < width:
                    nbrs[v].append(rr * width + cc)
    return nbrs


class Core:
    def __init__(self, nbrs, rho, p, quantize=False, tolerance=0.0, epsilon=EPSILON):
        self.nbrs = nbrs
        self.epsilon = epsilon
        self.x = [0.0] * len(nbrs)
        self.rho = rho
        self.p = p
        self.quantize = quantize
        self.tolerance = tolerance
        self.current = []
        self.next = {}

    def reservation(self, v):
        d = len(self.nbrs[v])
        return 8 + 4 * d + 1 + 2 * d

    def seed(self, v, value):
        self.x[v] = max(self.x[v], value)
        refs = dict.fromkeys(self.current)
        refs[v] = None
        for u in self.nbrs[v]:
            refs[u] = None
        self.current = list(refs)

    def wake_all_positive(self):
        self.current = [v for v, val in enumerate(self.x) if val > 0]

    def round(self):
        """Serve the whole frozen current set once; return (nodes, U, changed)."""
        x, nbrs, rho, p = self.x, self.nbrs, self.rho, self.p
        cost = changed = 0
        for v in self.current:
            cost += self.reservation(v)
            old = x[v]
            y = rho * old
            for u in nbrs[v]:
                y += p * x[u]
            y = 0.0 if y < 0 else (100.0 if y > 100 else y)
            if self.quantize:
                y = round(y / FIXED_QUANTUM) * FIXED_QUANTUM
            if y < self.epsilon:
                y = 0.0
            x[v] = y
            if abs(y - old) > self.tolerance or (y == 0.0 and old != 0.0):
                changed += 1
                self.next[v] = None
                for u in nbrs[v]:
                    self.next[u] = None
        served = len(self.current)
        self.current = list(self.next)
        self.next = {}
        return served, cost, changed

    def members(self):
        return sum(1 for val in self.x if val >= 1)


def run_phase(core, max_rounds, budget_per_month, stop_when_empty=True, months_per_round=1):
    trace, months, total_u, peak_nodes, peak_u = [], 0, 0, 0, 0
    for r in range(max_rounds):
        if stop_when_empty and not core.current:
            break
        served, cost, changed = core.round()
        # A logical round lasts at least its designed step, longer if over budget.
        months += max(months_per_round, math.ceil(cost / budget_per_month))
        total_u += cost
        peak_nodes = max(peak_nodes, served)
        peak_u = max(peak_u, cost)
        if r % 12 == 0 or not core.current:
            trace.append({"round": r, "served": served, "U": cost, "changed": changed,
                          "members_x_ge_1": core.members()})
    return {"rounds": r + 1, "calendar_months_at_budget": months, "total_U": total_u,
            "peak_served_nodes": peak_nodes, "peak_round_U": peak_u,
            "final_active": len(core.current), "trace_every_12_rounds": trace}


def study(width=117, height=116, budget_per_layer=40_000):
    nbrs = hex_grid(width, height)
    n = len(nbrs)
    center = (height // 2) * width + width // 2
    out = {"nodes": n, "mean_degree": sum(map(len, nbrs)) / n,
           "max_degree": max(map(len, nbrs)),
           "budget_per_layer_per_month_U": budget_per_layer,
           "budget_note": "480000 shared U / 12 envelope layers; illustrative split only"}

    # Growth: supercritical gain (rho + 6p = 1.11) from one seed until quiet.
    for label, eps in (("growth_exact_float", EPSILON), ("growth_epsilon_0.1", 0.1)):
        core = Core(nbrs, rho=0.99, p=0.02, epsilon=eps)
        core.seed(center, 25.0)
        res = run_phase(core, 3000, budget_per_layer)
        res["unbudgeted_months_one_round_per_month"] = res["rounds"]
        res["final_members"] = core.members()
        out[label] = res

    # Decay after saturation: fatigue lowers gain to 0.98; every positive node
    # keeps changing until epsilon, quantum or tolerance stops it.
    for label, quant, tol, eps in (
            ("decay_exact_float", False, 0.0, EPSILON),
            ("decay_fixed_point_1e-5", True, 0.0, EPSILON),
            ("decay_shared_tolerance_0.01", False, 0.01, EPSILON),
            ("decay_epsilon_0.1", False, 0.0, 0.1)):
        core = Core(nbrs, rho=0.95, p=0.005, quantize=quant, tolerance=tol, epsilon=eps)
        core.x = [100.0] * n
        core.wake_all_positive()
        res = run_phase(core, 4000, budget_per_layer)
        res["unbudgeted_months_one_round_per_month"] = res["rounds"]
        res["final_members"] = core.members()
        res["final_max_x"] = max(core.x)
        out[label] = res

    # Decay with a deliberate 12-month logical step: per-step gain (0.98)^12,
    # same rho:p ratio. A round lasts >= 12 months, longer if over budget.
    g12 = 0.98 ** 12
    for label, eps in (("decay_annual_step", EPSILON), ("decay_annual_step_epsilon_0.1", 0.1)):
        core = Core(nbrs, rho=g12 * 0.95 / 0.98, p=0.005 * g12 / 0.98, epsilon=eps)
        core.x = [100.0] * n
        core.wake_all_positive()
        res = run_phase(core, 400, budget_per_layer, months_per_round=12)
        res["unbudgeted_months_one_round_per_month"] = res["rounds"] * 12
        res["final_members"] = core.members()
        out[label] = res
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = study()
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    for key, val in result.items():
        if isinstance(val, dict):
            print(f"{key}: rounds={val['rounds']} months={val['calendar_months_at_budget']} "
                  f"total_U={val['total_U']} peak_nodes={val['peak_served_nodes']} "
                  f"peak_U={val['peak_round_U']} members={val.get('final_members')}")
    print("Synthetic abstract counts only; no EU5 timing or 500000 acceptance is implied.")


if __name__ == "__main__":
    main()
