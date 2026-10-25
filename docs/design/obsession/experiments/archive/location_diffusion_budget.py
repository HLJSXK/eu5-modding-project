"""ARCHIVED architecture: superseded by the single-float model on 2026-10-19.

Check old frontier invariants and abstract service quotas, not EU5 CPU time.

This does not simulate the coupled E/I/D equations or full QSS diffusion.
An isolated monotone exposure ODE illustrates QSS work/error tradeoffs.
Workload arrivals are explicit synthetic assumptions, not measured event rates.
"""

import argparse
from collections import defaultdict, deque
import json
import math
from pathlib import Path
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# Same provisional cost assumptions as section 6 of the design.
COST = {"edge": 32, "state": 128, "probe": 24, "hub": 96, "publish": 64}
QUOTA = {"edge": 4000, "state": 1600, "probe": 2000, "hub": 256, "publish": 512}
FIXED = 10_000
RESERVE = 31_856
CAP = 480_000
KINDS = tuple(COST)


def check_frontier():
    """Incremental edge contributions must equal a fresh dense reference.

    The tiny dense reference here is a correctness oracle, not runtime design.
    Blocked candidate edges remain registered for reopening.
    """
    width, height, goods = 6, 6, 3
    adjacent = {}
    for node in range(width * height):
        x, y = node % width, node // width
        adjacent[node] = tuple(
            ny * width + nx
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if 0 <= nx < width and 0 <= ny < height
        )
    signal = defaultdict(int)
    sent = defaultdict(int)
    pressure = defaultdict(int)
    refs = defaultdict(int)
    blocked = set()
    assertions = 0

    def apply(good, source, target):
        key = good, source, target
        old = sent[key]
        new = 0 if key in blocked else signal[good, source]
        pressure[good, target] += new - old
        refs[good, target] += int(new > 0) - int(old > 0)
        sent[key] = new

    def set_signal(good, source, value):
        signal[good, source] = value
        for target in adjacent[source]:
            apply(good, source, target)

    def verify():
        nonlocal assertions
        for good in range(goods):
            for target in adjacent:
                values = [
                    signal[good, source]
                    for source in adjacent[target]
                    if (good, source, target) not in blocked
                ]
                assert pressure[good, target] == sum(values)
                assert refs[good, target] == sum(value > 0 for value in values)
                assertions += 2

    # Two sources, removal of one, and commodity isolation.
    set_signal(0, 0, 5)
    set_signal(0, 2, 10)
    assert pressure[0, 1] == 15 and refs[0, 1] == 2
    set_signal(0, 0, 0)
    assert pressure[0, 1] == 10 and refs[0, 1] == 1
    assert pressure[1, 1] == 0
    # Repeat delivery is idempotent; blocked edge must survive reopening.
    apply(0, 2, 1)
    assert pressure[0, 1] == 10
    blocked.add((0, 2, 1))
    apply(0, 2, 1)
    assert pressure[0, 1] == 0
    blocked.remove((0, 2, 1))
    apply(0, 2, 1)
    assert pressure[0, 1] == 10
    verify()

    # Pause fanout after one neighbor, change the source again, then resume.
    # Each edge compares the latest signal to its own last committed value.
    source, good = 7, 2
    targets = adjacent[source]
    signal[good, source] = 5
    apply(good, source, targets[0])
    signal[good, source] = 20
    for target in targets[1:]:
        apply(good, source, target)
    apply(good, source, targets[0])  # Required followup for the earlier page.
    for target in targets:
        assert sent[good, source, target] == 20
    verify()

    rng = random.Random(20261018)
    for _ in range(1000):
        good, source = rng.randrange(goods), rng.randrange(width * height)
        if rng.random() < 0.25:
            target = rng.choice(adjacent[source])
            key = good, source, target
            if key in blocked:
                blocked.remove(key)
            else:
                blocked.add(key)
            apply(good, source, target)
        else:
            set_signal(good, source, rng.choice((0, 1, 5, 10, 20)))
        verify()
    return {"seed": 20261018, "random_mutations": 1000,
            "dense_reference_assertions": assertions,
            "explicit_cases": ["multiple_sources", "negative_delta", "idempotence",
                               "barrier_reopening", "goods_isolation",
                               "source_changes_during_partial_fanout"]}


def exposure_example():
    """QSS1 on dE/dt=P-decay*E, with t in years; compare analytic crossing.

    No input changes, monthly rounding, hysteresis, I, D, or queue delays here.
    Full-model accuracy cannot be inferred from this scalar illustration.
    """
    pressure, decay, threshold = 10.0, 0.15, 30.0
    exact_months = -math.log1p(-threshold * decay / pressure) / decay * 12
    results = []
    for step in (1.0, 5.0, 10.0):
        exposure, elapsed, events = 0.0, 0.0, 0
        while exposure < threshold:
            slope = pressure - decay * exposure
            target = min(threshold, exposure + step)
            elapsed += (target - exposure) / slope
            exposure = target
            events += 1
        results.append({"quantum_E": step, "derivative_evaluations": events,
                        "crossing_months_before_month_rounding": elapsed * 12,
                        "error_months": elapsed * 12 - exact_months})
    assert abs(results[0]["error_months"]) < abs(results[1]["error_months"])
    assert abs(results[1]["error_months"]) < abs(results[2]["error_months"])
    assert results[1]["derivative_evaluations"] == 6
    return {"ODE": "dE/dt = 10 - 0.15*E; E(0)=0; adoption at E=30; t in years",
            "analytic_crossing_months": exact_months,
            "monthly_fixed_step_evaluations_to_same_horizon": math.ceil(exact_months),
            "scope": "isolated scalar, constant input, no monthly rounding or queue delay",
            "QSS1": results}


def simulate(name, months, arrivals):
    """Exact FIFO waiting-time simulation using compressed equal-age batches.

    One batch is count copies of a bounded microtask. No simulation work is
    hidden in an assumed whole-market expansion: such work is an edge arrival.
    This is a service-capacity model; it does not generate diffusion arrivals.
    """
    queues = {kind: deque() for kind in KINDS}
    pending = dict.fromkeys(KINDS, 0)
    completed = dict.fromkeys(KINDS, 0)
    max_backlog = dict.fromkeys(KINDS, 0)
    max_wait = dict.fromkeys(KINDS, 0)
    observed_cost = 0
    last_nonempty_month = None
    for month in range(months):
        for kind, count in arrivals(month).items():
            assert kind in KINDS and isinstance(count, int) and count >= 0
            if count:
                queues[kind].append([month, count])
                pending[kind] += count
                max_backlog[kind] = max(max_backlog[kind], pending[kind])
        cost = FIXED + RESERVE  # Reserve fully spent in every stress month.
        for kind in KINDS:
            slots = QUOTA[kind]
            while slots and queues[kind]:
                born, count = queues[kind][0]
                served = min(count, slots)
                queues[kind][0][1] -= served
                slots -= served
                pending[kind] -= served
                completed[kind] += served
                cost += served * COST[kind]
                max_wait[kind] = max(max_wait[kind], month - born)
                if queues[kind][0][1] == 0:
                    queues[kind].popleft()
        assert cost <= CAP < 500_000
        observed_cost = max(observed_cost, cost)
        if any(pending.values()):
            last_nonempty_month = month
    return {
        "scenario": name, "months": months,
        "peak_assumed_U_including_full_reserve": observed_cost,
        "max_backlog_before_service": max_backlog,
        "completed_microtasks": completed,
        "max_completed_wait_months": max_wait,
        "remaining_microtasks": pending,
        "oldest_remaining_age_months": {
            kind: months - 1 - queues[kind][0][0] if queues[kind] else 0
            for kind in KINDS
        },
        "last_month_with_end_of_month_backlog": last_nonempty_month,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--active-goods", type=int, default=12,
                        help="Assumed simultaneous goods (legacy baseline: 12; schedule peak: 14).")
    args = parser.parse_args()
    if args.active_goods < 1:
        parser.error("--active-goods must be positive")
    checks = check_frontier()
    baseline = {"edge": 2000, "state": 800, "probe": 1600,
                "hub": 128, "publish": 256}

    def burst(month):
        result = dict(baseline)
        if month == 12:
            for kind in KINDS:
                result[kind] += QUOTA[kind] * 2
        return result

    goods = args.active_goods
    pairs = 28_573 * goods
    drain_months = max(600, math.ceil(pairs * 6 / QUOTA["edge"]) + 1,
                       math.ceil(pairs / QUOTA["state"]) + 1)
    scenarios = [
        simulate("assumed_normal_half_utilization", 120, lambda month: baseline),
        simulate("two_quota_burst_on_normal_load", 120, burst),
        simulate("all_pairs_six_edges_one_off_no_followup", drain_months,
                 lambda month: {"state": pairs, "edge": pairs * 6}
                 if month == 0 else {}),
        simulate("sustained_twice_capacity", 120,
                 lambda month: {kind: QUOTA[kind] * 2 for kind in KINDS}),
    ]
    assert all(not any(item["remaining_microtasks"].values()) for item in scenarios[:3])
    assert any(scenarios[3]["remaining_microtasks"].values())
    # Allocation arithmetic only; not a simulation of actual per-good FIFOs.
    fairness = {}
    for kind in KINDS:
        base, remainder = divmod(QUOTA[kind], goods)
        assert base > 0
        allocations = [0] * goods
        for month in range(goods):
            current = [base] * goods
            for index in range(remainder):
                current[(month * remainder + index) % goods] += 1
            assert sum(current) == QUOTA[kind]
            allocations = [old + new for old, new in zip(allocations, current)]
        assert max(allocations) == min(allocations)
        fairness[kind] = allocations
    output = {
        "evidence_scope": "synthetic frontier correctness and assumed service costs; "
                          "not QSS accuracy, engine operation counts, or measured EU5 time",
        "workload_scaling_note": "active-goods scales the one-off full-domain shock and "
                                 "allocation arithmetic; normal and burst arrivals remain fixed assumptions",
        "source_scale": {"location_records": 28_573, "active_goods": goods,
                         "pairs": pairs, "save_version": "1.3.11"},
        "assumed_costs_U": COST, "monthly_quotas_all_goods_combined": QUOTA,
        "fixed_U": FIXED, "reserve_U": RESERVE,
        "maximum_assumed_U": FIXED + RESERVE + sum(COST[k] * QUOTA[k] for k in KINDS),
        "frontier_checks": checks, "scalar_QSS_example": exposure_example(),
        "quota_allocation_arithmetic_only": {"goods": goods, "months": goods,
                                              "by_kind": fairness},
        "scenarios": scenarios,
    }
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
