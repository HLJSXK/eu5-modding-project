"""ARCHIVED multi-state workload; not the current single-float model.

Reproducible old window/quantization capacity arithmetic and synthetic FIFO study.

This is not a diffusion solver, QSS error test, or EU5 engine benchmark.
Total variation and task counts are assumed workloads, not measured bounds.
Run from any directory; only --output writes an artifact.
"""

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.dont_write_bytecode = True
from location_diffusion_budget import COST, QUOTA, FIXED, RESERVE, simulate


VARIATION = {"E": Fraction(100), "I": Fraction(170), "D": Fraction("1.1")}
STANDARD = {"E": Fraction(5), "I": Fraction(5), "D": Fraction("0.05")}
COARSE = {"E": Fraction(5), "I": Fraction(10), "D": Fraction("0.1")}
NEIGHBORS = 6
TARGET = Fraction(7, 10)


def task_counts(quantum, output_changes=None):
    """Illustrative monotone-segment TV/quantum counts; no hidden extra tasks."""
    components = {key: int(VARIATION[key] / quantum[key]) for key in VARIATION}
    assert all(VARIATION[key] / quantum[key] == components[key] for key in VARIATION)
    output_changes = components["I"] if output_changes is None else output_changes
    return {"state": sum(components.values()), "edge": output_changes * NEIGHBORS}, components


def capacity(months, per_pair, long_due_records=0):
    """70% average load capacity, with a distinct set of 63-month rehangs.

    long_due_records are not the same records already billed by per_pair.
    A real implementation needs measured rehang frequency and phase burst tests.
    """
    rehang = Fraction(long_due_records, 63)
    available = {"state": TARGET * QUOTA["state"] - rehang,
                 "edge": TARGET * QUOTA["edge"]}
    limits = {kind: max(Fraction(0), available[kind] * months / per_pair[kind])
              for kind in available}
    binding = min(limits, key=limits.get)
    nonstrict = max(0, math.floor(limits[binding]))
    strict = max(0, math.ceil(limits[binding]) - 1)
    return {"months": months, "target_utilization": float(TARGET),
            "long_due_records_distinct_from_active_pairs": long_due_records,
            "rehang_state_tasks_per_month": float(rehang),
            "available_state_slots_per_month_at_target": float(available["state"]),
            "state_pair_limit_real": float(limits["state"]),
            "edge_pair_limit_real": float(limits["edge"]),
            "binding_queue": binding,
            "max_integer_pairs_not_exceeding_target": nonstrict,
            "max_integer_pairs_strictly_below_target": strict,
            "zero_active_pairs_within_target": available["state"] >= 0,
            "note": "Average arithmetic only; negative spare state budget means even zero active pairs fail."}


def uniform_arrivals(total, active_months):
    """Cumulative floor differences produce exactly total tasks, without RNG."""
    def arrivals(month):
        if month >= active_months:
            return {}
        return {kind: ((month + 1) * count // active_months
                       - month * count // active_months)
                for kind, count in total.items()}
    for kind, count in total.items():
        assert sum(arrivals(month)[kind] for month in range(active_months)) == count
    return arrivals


def run_scenario(name, pairs, years, per_pair, *, calendar_years=None):
    active_months = years * 12
    calendar_months = (calendar_years or years) * 12
    assert calendar_months >= active_months
    total = {kind: pairs * count for kind, count in per_pair.items()}
    arrivals = uniform_arrivals(total, active_months)
    at_active_end = simulate(name, active_months, arrivals)
    at_window_end = (at_active_end if calendar_months == active_months else
                     simulate(name, calendar_months, arrivals))
    tail = max(math.ceil(at_window_end["remaining_microtasks"][kind] / QUOTA[kind])
               for kind in per_pair)
    final = (at_window_end if not tail else
             simulate(name, calendar_months + tail, arrivals))
    assert not any(final["remaining_microtasks"].values())
    assert all(final["completed_microtasks"][kind] == total[kind] for kind in per_pair)
    if tail:
        before_clear = simulate(name, calendar_months + tail - 1, arrivals)
        assert any(before_clear["remaining_microtasks"].values())
    last_backlog = final["last_month_with_end_of_month_backlog"]
    completion_months = max(active_months, 0 if last_backlog is None else last_backlog + 2)
    return {"scenario": name, "contact_pairs": pairs,
            "active_event_window_months": active_months,
            "calendar_window_months": calendar_months,
            "tasks_per_pair": per_pair, "total_arrivals": total,
            "mean_arrivals_per_active_month": {kind: count / active_months
                                                for kind, count in total.items()},
            "mean_quota_utilization": {kind: count / active_months / QUOTA[kind]
                                       for kind, count in total.items()},
            "total_event_task_U": sum(total[kind] * COST[kind] for kind in total),
            "backlog_at_active_event_window_end": at_active_end["remaining_microtasks"],
            "backlog_at_calendar_window_end": at_window_end["remaining_microtasks"],
            "tail_drain_months_after_calendar_window": tail,
            "completion_calendar_months": completion_months,
            "simulated_calendar_months": calendar_months + tail,
            "max_wait_months_including_tail": final["max_completed_wait_months"],
            "peak_assumed_U_including_full_reserve": final["peak_assumed_U_including_full_reserve"],
            "max_backlog_before_service": final["max_backlog_before_service"],
            "final_completed_microtasks": final["completed_microtasks"]}


def study():
    standard, components = task_counts(STANDARD)
    coarse, coarse_components = task_counts(COARSE)
    stage, _ = task_counts(STANDARD, output_changes=8)
    binary, _ = task_counts(STANDARD, output_changes=2)
    assert standard == {"state": 76, "edge": 204}
    assert coarse == {"state": 48, "edge": 102}
    assert stage == {"state": 76, "edge": 48}
    assert binary == {"state": 76, "edge": 12}
    cap_standard = capacity(1200, standard)
    cap_coarse = capacity(1200, coarse)
    cap_stage = capacity(1200, stage)
    assert cap_standard["max_integer_pairs_not_exceeding_target"] == 16_470
    assert cap_coarse["max_integer_pairs_not_exceeding_target"] == 28_000
    assert cap_coarse["max_integer_pairs_strictly_below_target"] == 27_999
    assert cap_stage["binding_queue"] == "state"
    assert int(TARGET * QUOTA["state"] * 63) == 70_560
    assert capacity(1200, standard, 60_000)["max_integer_pairs_not_exceeding_target"] == 2646
    assert not capacity(1200, standard, 342_876)["zero_active_pairs_within_target"]
    scenarios = [
        run_scenario("standard_60000_pairs_300_years", 60_000, 300, standard),
        run_scenario("same_event_work_compressed_to_100_years", 60_000, 100, standard),
        run_scenario("standard_16000_pairs_100_years_sustainable", 16_000, 100, standard),
        run_scenario("coarse_27000_pairs_100_years_sustainable", 27_000, 100, coarse),
        run_scenario("stage_signal_60000_pairs_100_years", 60_000, 100, stage),
        run_scenario("binary_signal_60000_pairs_100_years", 60_000, 100, binary),
        run_scenario("100_years_event_work_then_200_years_idle", 60_000, 100, standard,
                     calendar_years=300),
    ]
    long, short, sustainable, coarse_ok, staged, binary_case, idle = scenarios
    assert long["tail_drain_months_after_calendar_window"] == 0
    assert short["backlog_at_calendar_window_end"]["state"] == 2_640_000
    assert short["backlog_at_calendar_window_end"]["edge"] == 7_440_000
    assert short["tail_drain_months_after_calendar_window"] == 1860
    assert staged["tail_drain_months_after_calendar_window"] == 1650
    assert binary_case["tail_drain_months_after_calendar_window"] == 1650
    assert all(value <= TARGET for item in (sustainable, coarse_ok)
               for value in item["mean_quota_utilization"].values())
    assert long["total_arrivals"] == short["total_arrivals"] == idle["total_arrivals"]
    assert idle["max_wait_months_including_tail"] == short["max_wait_months_including_tail"]
    return {
        "evidence_scope": "Assumed total variation and synthetic FIFO capacity only; "
                          "not actual diffusion, full QSS, engine instruction counts, or EU5 CPU time.",
        "assumptions": {
            "total_variation_per_contact_pair": {key: float(value) for key, value in VARIATION.items()},
            "directed_neighbors_per_output_change": NEIGHBORS,
            "standard_quantum": {key: float(value) for key, value in STANDARD.items()},
            "coarse_quantum": {key: float(value) for key, value in COARSE.items()},
            "standard_state_components": components, "coarse_state_components": coarse_components,
            "counts_exclude": ["initialization", "extra policy/input changes", "topology repair",
                               "threshold enrichment", "hysteresis reversals", "publish work",
                               "hub work", "probe work", "63-month rehangs in the FIFO scenarios"],
            "arrival_rule": "floor((month+1)*total/active_months)-floor(month*total/active_months)",
            "queue_model": "Independent FIFO microtask classes; arrivals before same-month service; "
                           "no causal dependencies, no task merging, no cancellation, no new arrivals in drain tail.",
            "costs_U": COST, "quotas_all_goods_combined": QUOTA,
            "fixed_plus_fully_spent_reserve_U_per_simulated_month": FIXED + RESERVE,
            "unused_quotas_not_borrowed": True,
        },
        "capacity_at_100_years": {"standard": cap_standard, "coarse": cap_coarse,
                                  "stage_signal_eight_changes": cap_stage,
                                  "binary_signal_two_changes": capacity(1200, binary)},
        "long_due_rehang_arithmetic": {
            "assumption": "P distinct remote-due records each rechecked once per 63 months, costing one "
                          "state slot per check; phase-smoothed average only. Do not add P for the same "
                          "active records already billed as state events; avoid double counting.",
            "max_remote_records_alone_not_exceeding_70_percent": int(TARGET * QUOTA["state"] * 63),
            "rows": [capacity(1200, standard, count) for count in (0, 60_000, 342_876)],
        },
        "window_semantics": {
            "compress_same_work": "300 to 100 years triples event arrival rates and preserves total event work; "
                                  "it can worsen backlog despite reducing calendar lifetime.",
            "delete_pure_idle": "Deleting 200 event-free years after an unchanged 100-year wave preserves "
                                "arrival rates, peak and waiting times. This example uses that idle calendar "
                                "time to drain a backlog; deleting it exposes a 1860-month tail, rather "
                                "than making the outstanding work disappear.",
            "sleeping_idle_cost": "Ideal truly sleeping records generate zero state/edge tasks. Any saved "
                                  "per-situation polling or distant-event rehang work needs separate accounting.",
            "discard_at_close": "Dropping pending tasks at close would change results; these scenarios drain all work.",
            "real_shorter_wave": "Savings require fewer contacted pairs, less total variation, fewer output "
                                 "changes, or less actual scheduling overhead; historical reach and accuracy "
                                 "must be calibrated separately.",
        },
        "scenarios": scenarios,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = study()
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in result["scenarios"]:
        print(f"{item['scenario']}: mean state/edge="
              f"{item['mean_arrivals_per_active_month']['state']:.3f}/"
              f"{item['mean_arrivals_per_active_month']['edge']:.3f}; "
              f"tail={item['tail_drain_months_after_calendar_window']} months; "
              f"peak={item['peak_assumed_U_including_full_reserve']} assumed U")
    print("100-year 70% pair capacities: standard=16470, coarse=28000 (strictly below=27999)")


if __name__ == "__main__":
    main()
