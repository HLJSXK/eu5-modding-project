"""Tiny reproducible, one-float-per-location sparse diffusion illustration.

This is an asynchronous immediate-write model, not E/I/D or a QSS solver.
Counters are declared abstract primitives, not EU5 instructions or timings.
Only --output writes a file. No location history, cached signal, or local clock.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


RHO = 0.9
WEIGHT = 0.15
EPSILON = 0.00001


class Location:
    __slots__ = ("x",)

    def __init__(self, value=0.0):
        self.x = float(value)


def stage(x):
    """Display only: derive from x on demand; never store on the location."""
    return sum(x >= threshold for threshold in (1, 20, 45, 70))


class SparseModel:
    """Two reference-only candidate collections and a shared current cursor.

    current is an ordered unique tuple (a frozen reference set). next is an
    insertion-ordered reference set, represented by dict keys with None values.
    Incoming/outgoing indexes and weights are immutable topology, not state.
    Every completed current set is one logical round. A budgeted call may serve
    a prefix, leaving the shared cursor for a later call. The round freezes only
    membership; x is always read live, so order affects the result.
    """

    def __init__(self, labels, edges, initial=None, wake=(), rho=RHO):
        initial = initial or {}
        self.locations = {label: Location(initial.get(label, 0)) for label in labels}
        self.incoming = {label: tuple((u, float(p)) for u, v, p in edges if v == label)
                         for label in labels}
        self.outgoing = {label: tuple(v for u, v, p in edges if u == label)
                         for label in labels}
        self.current = tuple(dict.fromkeys(wake))
        self.next = {}
        self.cursor = 0
        self.rho = float(rho)
        self.round = 0
        self.counts = Counter()
        self.finished_tasks = 0
        self.total_precharged_U = 0
        self.peak_call_precharged_U = 0
        self.peak_call_actual_task_U = 0

    def assert_storage(self):
        assert Location.__slots__ == ("x",)
        assert all(type(node.x) is float and not hasattr(node, "__dict__")
                   for node in self.locations.values())
        assert len(self.current) == len(set(self.current))
        assert all(value is None for value in self.next.values())
        assert all(label in self.locations for label in self.current)
        assert all(label in self.locations for label in self.next)

    def task_reservation(self, label):
        # Worst case counts every declared primitive once. Changed x requires
        # one self registration and one per outgoing edge. Static degree lookup
        # is assumed available; its engine implementation remains unverified.
        return 8 + 4 * len(self.incoming[label]) + 1 + 2 * len(self.outgoing[label])

    def process(self, budget):
        """Serve at most the rest of one round; precharge each complete task."""
        assert isinstance(budget, int) and budget >= 0
        spent = 0
        actual = 0
        served = 0
        while self.cursor < len(self.current):
            label = self.current[self.cursor]
            reservation = self.task_reservation(label)
            if spent + reservation > budget:
                break
            # No state is read or written until its complete task is reserved.
            spent += reservation
            task = Counter()
            node = self.locations[label]
            old = node.x
            task["own_state_reads"] += 1
            value = self.rho * old
            task["retain_multiplications"] += 1
            for source, weight in self.incoming[label]:
                task["incoming_edge_enumerations"] += 1
                value += weight * self.locations[source].x
                task["neighbor_state_reads"] += 1
                task["weighted_multiplications"] += 1
                task["weighted_additions"] += 1
            value = max(0.0, min(100.0, value))
            task["clamp_comparisons"] += 2
            if value < EPSILON:
                value = 0.0
            task["epsilon_comparisons"] += 1
            node.x = float(value)
            task["state_writes"] += 1
            task["changed_comparisons"] += 1
            task["current_reference_selections"] += 1
            if node.x != old:
                self.next[label] = None
                task["reference_set_insert_attempts"] += 1
                for target in self.outgoing[label]:
                    task["outgoing_edge_enumerations"] += 1
                    self.next[target] = None
                    task["reference_set_insert_attempts"] += 1
            assert sum(task.values()) <= reservation
            actual += sum(task.values())
            self.counts.update(task)
            self.cursor += 1
            served += 1
        self.finished_tasks += served
        self.total_precharged_U += spent
        self.peak_call_precharged_U = max(self.peak_call_precharged_U, spent)
        self.peak_call_actual_task_U = max(self.peak_call_actual_task_U, actual)
        assert spent <= budget and actual <= spent
        return {"served_nodes": served, "precharged_task_U": spent,
                "actual_declared_task_U": actual,
                "round_finished": self.cursor == len(self.current)}

    def advance_round(self):
        assert self.cursor == len(self.current)
        # Count the explicit reference enumeration separately. Python dict/set
        # allocation and hashing are not primitive-cost estimates for EU5.
        self.counts["round_handoff_reference_enumerations"] += len(self.next)
        self.current = tuple(self.next)
        self.next = {}
        self.cursor = 0
        self.round += 1

    def wake_changed_external_source(self, label, value):
        """Explicit exogenous seed/withdrawal, not hidden monthly discovery."""
        assert self.cursor == 0
        self.locations[label].x = float(value)
        refs = dict.fromkeys(self.current)
        refs[label] = None
        for target in self.outgoing[label]:
            refs[target] = None
        self.current = tuple(refs)

    def report(self):
        self.assert_storage()
        return {"rounds_completed": self.round, "completed_node_tasks": self.finished_tasks,
                "final_x": {label: node.x for label, node in self.locations.items()},
                "final_display_stages_derived_on_read": {
                    label: stage(node.x) for label, node in self.locations.items()},
                "current_references": list(self.current), "next_references": list(self.next),
                "shared_current_cursor": self.cursor,
                "declared_primitive_counts": dict(self.counts),
                "total_precharged_task_U": self.total_precharged_U,
                "peak_call_precharged_task_U": self.peak_call_precharged_U,
                "peak_call_actual_declared_task_U": self.peak_call_actual_task_U}


def full_round(model, budget=500_000):
    while model.cursor < len(model.current):
        result = model.process(budget)
        assert result["served_nodes"] > 0, "Budget smaller than one complete node task"
    model.advance_round()


def study():
    checks = []
    # Directed chain plus a disconnected component. Wake the seed and its direct
    # neighbor once; downstream discoveries are queued for subsequent rounds.
    graph = [("a", "b", WEIGHT), ("b", "c", WEIGHT), ("c", "d", WEIGHT),
             ("unrelated_1", "unrelated_2", WEIGHT)]
    chain = SparseModel(("a", "b", "c", "d", "unrelated_1", "unrelated_2"), graph,
                        {"a": 100}, wake=("a", "b"))
    full_round(chain)
    assert chain.locations["b"].x > 0
    assert chain.locations["c"].x == chain.locations["d"].x == 0
    assert "c" in chain.current and "d" not in chain.current
    checks.append("newly_woken_downstream_node_waits_for_next_round")
    for _ in range(19):
        full_round(chain)
        assert not any(label.startswith("unrelated")
                       for label in (*chain.current, *chain.next))
    assert chain.locations["unrelated_1"].x == chain.locations["unrelated_2"].x == 0
    checks.append("unrelated_component_never_registered")
    chain.assert_storage()
    checks.append("one_float_per_location_and_reference_only_candidate_sets")

    # Current membership is identical, but changing its service order changes
    # the live x read by b. There is no x_next snapshot.
    forward = SparseModel(("a", "b"), [("a", "b", WEIGHT)], {"a": 10}, wake=("a", "b"))
    reverse = SparseModel(("a", "b"), [("a", "b", WEIGHT)], {"a": 10}, wake=("b", "a"))
    full_round(forward)
    full_round(reverse)
    assert abs(forward.locations["b"].x - 1.35) < 1e-12
    assert abs(reverse.locations["b"].x - 1.5) < 1e-12
    checks.append("asynchronous_service_order_changes_result")

    stable = SparseModel(("a", "b"), [("a", "b", .1), ("b", "a", .1)],
                         {"a": 10, "b": 10}, wake=("a", "b"))
    full_round(stable)
    assert not stable.current and all(node.x == 10 for node in stable.locations.values())
    stable.wake_changed_external_source("a", 20)
    full_round(stable)
    assert stable.locations["b"].x > 10 and "b" in stable.current
    checks.append("unchanged_interior_sleeps_and_changed_neighbor_wakes_it")

    multi = SparseModel(("s1", "s2", "target"),
                        [("s1", "target", WEIGHT), ("s2", "target", WEIGHT)],
                        {"s1": 10, "s2": 20}, wake=("s1", "s2", "target"))
    full_round(multi)
    multi.wake_changed_external_source("s1", 0)
    full_round(multi)
    assert multi.locations["target"].x > 0 and "target" in multi.current
    assert multi.locations["s2"].x > 0
    checks.append("withdrawing_one_source_preserves_target_with_another_source")

    decay = SparseModel(("isolated",), (), {"isolated": 10}, wake=("isolated",))
    while decay.current and decay.round < 1000:
        full_round(decay)
    assert decay.locations["isolated"].x == 0 and not decay.current
    checks.append("rho_below_one_isolated_decay_eventually_sleeps_at_epsilon")

    zero = SparseModel(("a", "b"), [("a", "b", WEIGHT)])
    assert zero.process(500_000)["served_nodes"] == 0
    zero.wake_changed_external_source("a", 0)
    full_round(zero)
    assert not zero.current and all(node.x == 0 for node in zero.locations.values())
    checks.append("zero_state_and_zero_external_input_never_self_heats")

    assert [stage(x) for x in (0, .99, 1, 19.9, 20, 44.9, 45, 69.9, 70, 100)] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    checks.append("display_stage_is_derived_without_cache")

    budgeted = SparseModel(("source", "target"), [("source", "target", WEIGHT)],
                           {"source": 10}, wake=("target", "source"))
    first_cost = budgeted.task_reservation("target")
    rejected = budgeted.process(first_cost - 1)
    assert rejected["served_nodes"] == 0
    assert budgeted.cursor == 0 and budgeted.locations["target"].x == 0
    assert budgeted.locations["source"].x == 10 and not budgeted.next
    accepted = budgeted.process(first_cost)
    assert accepted["served_nodes"] == 1 and budgeted.cursor == 1
    assert budgeted.locations["target"].x == 1.5
    assert budgeted.locations["source"].x == 10
    checks.append("complete_node_task_precharged_before_any_state_read_or_write")

    suspended = SparseModel(("a", "b"), [("a", "b", WEIGHT)],
                            {"a": 10}, wake=("a", "b"))
    prefix = suspended.process(suspended.task_reservation("a"))
    assert prefix["served_nodes"] == 1 and not prefix["round_finished"]
    full_round(suspended, budget=suspended.task_reservation("b"))
    assert all(suspended.locations[label].x == forward.locations[label].x for label in ("a", "b"))
    checks.append("shared_cursor_budget_suspension_preserves_fixed_order_result")

    return {
        "evidence_scope": "Small synthetic one-state asynchronous sparse model; no EU5 engine performance claim.",
        "formula": "x_v := epsilon_zero(clamp(rho*x_v + sum(p_uv*x_u), 0, 100)); immediate overwrite",
        "parameters": {"rho_per_logical_round": RHO, "example_static_directed_edge_weight": WEIGHT,
                       "epsilon_below_which_x_is_zero": EPSILON, "hub_or_exogenous_term": 0,
                       "display_stage_thresholds": [1, 20, 45, 70],
                       "display_stage_values": [0, 1, 2, 3, 4]},
        "persistent_storage_contract": {
            "per_location_per_good": ["one float x"],
            "shared_dynamic": ["current unique ordered location references", "next unique location references",
                               "one current cursor", "one logical round number", "shared parameters",
                               "aggregate diagnostic counters only"],
            "immutable_topology": ["incoming references and p", "outgoing references"],
            "forbidden_and_absent": ["E", "D", "x_next", "q cache", "pressure cache", "sent cache",
                                     "local queue flag", "local timestamp", "local next/prev", "per-location history"],
        },
        "scheduling": "A changed x enrolls self and outgoing neighbors in next. Unchanged x does not retain "
                      "itself, but another changed neighbor can wake it. New references are served next round. "
                      "current freezes membership only; sequential live reads mean same-current neighbors can "
                      "propagate within a round depending on order. Budget suspension retains one shared cursor.",
        "limitations": [
            "rho=.9 and p=.15 are per-logical-round test parameters, not calibrated game rules or annual rates.",
            "Python binary float with epsilon cutoff; not a replay of EU5 fixed-point rounding at every operation.",
            "Decay is shown for an isolated node. rho<1 alone does not ensure a connected positive-feedback graph decays; incoming gain can sustain or saturate it.",
            "The candidate collections represent touched/dirty neighborhoods, not an exactly classified F/A border; zero neighbors can incur a harmless no-change task.",
            "A logical round can span multiple budgeted calls; its effective calendar rate slows under load.",
            "Primitive counts include explicit edge/reference enumerations and arithmetic, but exclude Python hashing, allocations, native iterator access, and engine-specific lookup costs.",
            "Round handoff reference enumerations are reported separately and are not paid by the per-node reservation; this illustration does not establish a total monthly 500000-U bound.",
            "External source withdrawal is an explicit wake hook; discovering policy/topology/source changes without hooks needs separately budgeted probing.",
            "Fan-in and fan-out bound the complete node reservation; a node exceeding the entire monthly allowance cannot progress without a different primitive or topology restriction.",
        ],
        "assertions_passed": checks,
        "chain_after_20_rounds": chain.report(),
        "order_dependence": {"forward": forward.report(), "reverse": reverse.report()},
        "stable_then_neighbor_wake_with_p_point_one": stable.report(),
        "two_sources_after_one_withdrawn": multi.report(),
        "isolated_decay": decay.report(), "zero_input": zero.report(),
        "complete_task_budget_test": {"first_node_reservation_U": first_cost,
                                      "too_small_call": rejected, "exact_budget_call": accepted,
                                      "model": budgeted.report()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = study()
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    chain = result["chain_after_20_rounds"]
    print(f"{len(result['assertions_passed'])} checks passed; chain: "
          f"{chain['completed_node_tasks']} node tasks, "
          f"{chain['total_precharged_task_U']} precharged abstract task U")
    print("Order example: target x=1.35 vs 1.5; disconnected component stays zero/unregistered.")
    print("No EU5 timing or total monthly 500000-U guarantee is inferred.")


if __name__ == "__main__":
    main()
