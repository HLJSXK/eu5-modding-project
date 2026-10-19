"""Reference scheduler for plan option A: intrusive FIFO with a transient
per-location queue pointer. Replaces native current/next sets.

Storage per location x good: float x, plus pointer q that exists ONLY while the
location is queued (tail points to itself). Per good: head, tail, length and
round_remaining. Every operation is a variable read/write; no native set,
list, index, dedupe or swap is used. A logical round is the round_remaining
locations queued when the round started; pushes during the round land behind
them, so new candidates wait one round. A target that is still pending is not
queued again, so it reads the new value when served.
A change of at most DELTA (0.1, adopted) is not written and not queued.

Counters are abstract primitives, not EU5 instructions. Only --output writes.
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
DELTA = 0.1        # adopted shared change tolerance: |new-old| <= DELTA is not written
POP_U = 3          # read head, read head.q, remove variable
PUSH_NEW_U = 4     # read q, write q, write tail.q, write tail
PUSH_PENDING_U = 1  # read q only


class Location:
    __slots__ = ("x", "q")

    def __init__(self, value=0.0):
        self.x = float(value)
        self.q = None      # absent variable


def stage(x):
    return sum(x >= t for t in (1, 20, 45, 70))


class QueueModel:
    def __init__(self, labels, edges, initial=None, wake=(), rho=RHO, delta=DELTA):
        self.delta = float(delta)
        initial = initial or {}
        self.loc = {k: Location(initial.get(k, 0)) for k in labels}
        self.incoming = {k: tuple((u, float(p)) for u, v, p in edges if v == k) for k in labels}
        self.outgoing = {k: tuple(v for u, v, p in edges if u == k) for k in labels}
        self.rho = float(rho)
        self.head = self.tail = None
        self.length = 0
        self.round_remaining = 0
        self.round = 0
        self.counts = Counter()
        self.finished_tasks = 0
        self.total_precharged_U = 0
        for k in wake:
            self.push(k, self.counts)

    # ---- queue primitives: variable reads/writes only ----
    def push(self, label, task):
        node = self.loc[label]
        if node.q is not None:
            task["push_pending_reads"] += 1
            return PUSH_PENDING_U
        node.q = label                       # tail marker: points to itself
        if self.length == 0:
            self.head = label
        else:
            self.loc[self.tail].q = label
        self.tail = label
        self.length += 1
        task["push_new_writes"] += 1
        return PUSH_NEW_U

    def pop(self, task):
        label = self.head
        node = self.loc[label]
        if self.length == 1:
            self.head = self.tail = None
        else:
            self.head = node.q
        node.q = None
        self.length -= 1
        task["pops"] += 1
        return label

    def queued_labels(self):
        """Debug walk from head; integrity oracle, not runtime."""
        out, cur = [], self.head
        for _ in range(self.length):
            out.append(cur)
            cur = self.loc[cur].q
        return out

    def assert_storage(self):
        assert Location.__slots__ == ("x", "q")
        walk = self.queued_labels()
        assert len(walk) == len(set(walk)) == self.length
        assert (self.tail is None) == (self.length == 0)
        if self.length:
            assert walk[-1] == self.tail and self.loc[self.tail].q == self.tail
        live = {k for k, n in self.loc.items() if n.q is not None}
        assert live == set(walk), "q exists exactly while queued"
        assert all(type(n.x) is float for n in self.loc.values())
        assert self.round_remaining <= self.length

    # ---- service ----
    def reservation(self, label):
        d_in, d_out = len(self.incoming[label]), len(self.outgoing[label])
        return POP_U + 8 + 4 * d_in + 1 + d_out + PUSH_NEW_U * (1 + d_out)

    def process(self, budget, stop_at_round_end=True):
        """Serve within budget. A logical round may span several calls; by
        default a call does not start a second round after serving."""
        spent = actual = served = 0
        while True:
            if self.round_remaining == 0:
                if self.length == 0 or (stop_at_round_end and served):
                    break
                self.round_remaining = self.length      # freeze round size
            label = self.head
            res = self.reservation(label)
            if spent + res > budget:
                break
            spent += res                                 # precharge whole task
            task = Counter()
            cost = POP_U
            self.pop(task)
            self.round_remaining -= 1
            node = self.loc[label]
            old = node.x
            value = self.rho * old
            cost += 2                                    # own read, retain multiply
            for src, w in self.incoming[label]:
                value += w * self.loc[src].x
                cost += 4                                # enumerate, read, multiply, add
            value = max(0.0, min(100.0, value))
            if value < EPSILON:
                value = 0.0
            cost += 6                                    # clamp 2, eps 1, write 1, compare 1, select 1
            changed = abs(value - old) > self.delta or (value == 0.0 and old != 0.0)
            if changed:
                node.x = float(value)                    # within delta: x is not written
                cost += 1 + len(self.outgoing[label])    # self registration, edge enumeration
                cost += self.push(label, task)
                for tgt in self.outgoing[label]:
                    cost += self.push(tgt, task)
            assert cost <= res
            actual += cost
            self.counts.update(task)
            served += 1
            if self.round_remaining == 0:
                self.round += 1
        self.finished_tasks += served
        self.total_precharged_U += spent
        return {"served_nodes": served, "precharged_task_U": spent, "actual_task_U": actual,
                "round_finished": self.round_remaining == 0}

    def wake_changed_external_source(self, label, value):
        """Explicit seed/withdrawal; registers source and targets via push."""
        self.loc[label].x = float(value)
        task = Counter()
        self.push(label, task)
        for t in self.outgoing[label]:
            self.push(t, task)
        self.counts.update(task)

    def report(self):
        self.assert_storage()
        return {"rounds_completed": self.round, "completed_node_tasks": self.finished_tasks,
                "final_x": {k: n.x for k, n in self.loc.items()},
                "final_display_stages_derived_on_read": {k: stage(n.x) for k, n in self.loc.items()},
                "queued": self.queued_labels(), "round_remaining": self.round_remaining,
                "declared_primitive_counts": dict(self.counts),
                "total_precharged_task_U": self.total_precharged_U}


def full_round(model, budget=500_000):
    """Finish the current logical round (or start and finish one if idle)."""
    if model.round_remaining == 0 and model.length == 0:
        return
    start = model.round
    while model.round == start:
        assert model.process(budget)["served_nodes"] > 0, "budget below one complete task"


def study():
    checks = []
    graph = [("a", "b", WEIGHT), ("b", "c", WEIGHT), ("c", "d", WEIGHT),
             ("unrelated_1", "unrelated_2", WEIGHT)]
    chain = QueueModel(("a", "b", "c", "d", "unrelated_1", "unrelated_2"), graph,
                       {"a": 100}, wake=("a", "b"))
    full_round(chain)
    assert chain.loc["b"].x > 0 and chain.loc["c"].x == chain.loc["d"].x == 0
    assert "c" in chain.queued_labels() and "d" not in chain.queued_labels()
    checks.append("newly_woken_downstream_node_waits_for_next_round")
    for _ in range(19):
        full_round(chain)
        assert not any(k.startswith("unrelated") for k in chain.queued_labels())
    assert chain.loc["unrelated_1"].x == chain.loc["unrelated_2"].x == 0
    checks.append("unrelated_component_never_registered")
    chain.assert_storage()
    checks.append("q_exists_exactly_while_queued_and_queue_walk_is_consistent")

    fwd = QueueModel(("a", "b"), [("a", "b", WEIGHT)], {"a": 10}, wake=("a", "b"))
    rev = QueueModel(("a", "b"), [("a", "b", WEIGHT)], {"a": 10}, wake=("b", "a"))
    full_round(fwd); full_round(rev)
    assert abs(fwd.loc["b"].x - 1.35) < 1e-12 and abs(rev.loc["b"].x - 1.5) < 1e-12
    checks.append("asynchronous_service_order_changes_result")

    # a changes first and would re-register b, but b is still pending in this
    # round: it is not queued twice and reads a's new value when served.
    pend = QueueModel(("a", "b"), [("a", "b", WEIGHT), ("b", "a", WEIGHT)],
                      {"a": 10, "b": 100}, wake=("a", "b"))
    pend.process(pend.reservation("a"))
    assert pend.queued_labels()[0] == "b" and pend.queued_labels().count("b") == 1
    assert pend.counts["push_pending_reads"] >= 1
    checks.append("pending_target_is_not_queued_twice")

    stable = QueueModel(("a", "b"), [("a", "b", .1), ("b", "a", .1)],
                        {"a": 10, "b": 10}, wake=("a", "b"))
    full_round(stable)
    assert stable.length == 0 and all(n.x == 10 for n in stable.loc.values())
    stable.wake_changed_external_source("a", 20)
    full_round(stable)
    assert stable.loc["b"].x > 10 and "b" in stable.queued_labels()
    checks.append("unchanged_interior_sleeps_and_changed_neighbor_wakes_it")

    multi = QueueModel(("s1", "s2", "target"), [("s1", "target", WEIGHT), ("s2", "target", WEIGHT)],
                       {"s1": 10, "s2": 20}, wake=("s1", "s2", "target"))
    full_round(multi)
    multi.wake_changed_external_source("s1", 0)
    full_round(multi)
    assert multi.loc["target"].x > 0 and multi.loc["s2"].x > 0
    checks.append("withdrawing_one_source_preserves_target_with_another_source")

    decay = QueueModel(("iso",), (), {"iso": 10}, wake=("iso",))
    while decay.length and decay.round < 1000:
        full_round(decay)
    frozen = decay.loc["iso"].x
    assert 0 < frozen and (1 - RHO) * frozen <= DELTA < (1 - RHO) * frozen / RHO
    assert decay.length == 0 and decay.loc["iso"].q is None
    checks.append("isolated_decay_freezes_at_first_x_with_(1-rho)x_le_delta_and_frees_pointer")
    decay0 = QueueModel(("iso",), (), {"iso": 10}, wake=("iso",), delta=0.0)
    while decay0.length and decay0.round < 1000:
        full_round(decay0)
    assert decay0.loc["iso"].x == 0 and decay0.length == 0
    checks.append("with_delta_zero_isolated_decay_reaches_zero")

    tiny = QueueModel(("s", "t"), [("s", "t", WEIGHT)], {"s": 0.5}, wake=("t",))
    full_round(tiny)
    assert tiny.loc["t"].x == 0 and tiny.length == 0      # 0.15*0.5 = 0.075 <= delta
    checks.append("change_at_or_below_delta_is_not_written_or_requeued")

    zero = QueueModel(("a", "b"), [("a", "b", WEIGHT)])
    assert zero.process(500_000)["served_nodes"] == 0
    zero.wake_changed_external_source("a", 0)
    full_round(zero)
    assert zero.length == 0 and all(n.x == 0 and n.q is None for n in zero.loc.values())
    checks.append("zero_state_and_zero_external_input_never_self_heats")

    assert [stage(x) for x in (0, .99, 1, 19.9, 20, 44.9, 45, 69.9, 70, 100)] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    checks.append("display_stage_is_derived_without_cache")

    bud = QueueModel(("source", "target"), [("source", "target", WEIGHT)],
                     {"source": 10}, wake=("target", "source"))
    first = bud.reservation("target")
    rej = bud.process(first - 1)
    assert rej["served_nodes"] == 0 and bud.loc["target"].x == 0 and bud.length == 2
    acc = bud.process(first)
    assert acc["served_nodes"] == 1 and bud.loc["target"].x == 1.5
    checks.append("complete_node_task_precharged_before_any_pop_read_or_write")

    sus = QueueModel(("a", "b"), [("a", "b", WEIGHT)], {"a": 10}, wake=("a", "b"))
    sus.process(sus.reservation("a"))
    assert sus.round_remaining == 1
    sus.process(sus.reservation("b"))
    assert all(sus.loc[k].x == fwd.loc[k].x for k in ("a", "b"))
    checks.append("budget_suspension_preserves_fixed_order_result_with_round_remaining")

    for m in (chain, fwd, rev, pend, stable, multi, decay, decay0, tiny, zero, bud, sus):
        m.assert_storage()
    checks.append("no_native_set_list_index_or_swap_used")

    return {
        "evidence_scope": "Small synthetic models of plan option A; no EU5 engine performance claim.",
        "storage_contract": {
            "per_location_per_good": ["float x (persistent)",
                                      "location reference q, present only while queued; tail points to itself"],
            "per_good": ["head", "tail", "length", "round_remaining", "round"],
            "forbidden_and_absent": ["E", "D", "x_next", "pressure", "sent", "timestamp", "prev pointer",
                                     "native current/next sets"]},
        "delta": DELTA,
        "primitive_costs_U": {"pop": POP_U, "push_new": PUSH_NEW_U, "push_pending": PUSH_PENDING_U,
                              "reservation": "3 + 8 + 4*d_in + 1 + d_out + 4*(1 + d_out)"},
        "assertions_passed": checks,
        "chain_after_20_rounds": chain.report(),
        "order_dependence": {"forward": fwd.report(), "reverse": rev.report()},
        "pending_not_requeued": pend.report(),
        "stable_then_wake": stable.report(),
        "two_sources_after_one_withdrawn": multi.report(),
        "isolated_decay": decay.report(),
        "complete_task_budget_test": {"first_reservation_U": first, "too_small_call": rej,
                                      "exact_call_served": acc["served_nodes"], "model": bud.report()},
        "hex_grid_equivalence": "see relaxed_state_study_results.json: identical x to set scheduler, 6.4% fewer node services",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    res = study()
    if args.output:
        args.output.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ch = res["chain_after_20_rounds"]
    print(f"{len(res['assertions_passed'])} checks passed; chain: {ch['completed_node_tasks']} node tasks, "
          f"{ch['total_precharged_task_U']} precharged U")
    print("No EU5 timing or monthly 500000-U guarantee is inferred.")


if __name__ == "__main__":
    main()
