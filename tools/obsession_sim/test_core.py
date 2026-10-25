"""Tests for tools.obsession_sim.

Run:  python -m pytest tools/obsession_sim/test_core.py        (fast set)
      python -m tools.obsession_sim.test_core --full            (adds slow regressions)

Regression anchors are the committed experiment results under
docs/design/obsession/experiments/, so the shared core is proven to equal the
scripts that the design documents cite.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.obsession_sim import (Params, Simulation, simulate, hex_grid, voronoi_groups, save_json, load_json,
                                 load_csv, from_adjacency, milestones, front_profile, front_speed, playback_payload)

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "docs" / "design" / "obsession" / "experiments"


def _hex_with_groups(w=117, h=116, groups=1600):
    g = hex_grid(w, h)
    g.owner = voronoi_groups(g, groups)
    return g


# ------------------------------------------------------------- regressions

def test_regression_growth_delta_and_control():
    ref = json.loads((EXP / "delta_adoption_study_results.json").read_text(encoding="utf-8"))
    g = hex_grid()
    c, w = g.meta["center"], g.meta["width"]
    east = [v % w > w // 2 + 5 for v in range(g.n)]
    cases = {
        "growth_delta_0.1": dict(decay="none", delta=0.1),
        "controlled_strong_delta_0.1": dict(decay="none", delta=0.1,
                                            rho_by_node=[0.95 if e else 0.99 for e in east],
                                            p_by_node=[0.004 if e else 0.02 for e in east]),
    }
    for name, kw in cases.items():
        s = simulate(g, Params(seeds=[(c, 0, 25.0)], series_every=0, **kw)).summary()
        r = ref[name]
        assert [s["rounds"], s["total_U"], s["peak_queue"], s["final_members"], s["final_saturated"]] == \
               [r["rounds"], r["U"], r["peak"], r["members"], r["sat"]], name


def test_regression_country_clock_T240():
    ref = json.loads((EXP / "ripple_country_clock_study_results.json").read_text(encoding="utf-8"))["T240"]
    g = _hex_with_groups()
    s = simulate(g, Params(seeds=[(g.meta["center"], 0, 25.0)], hold_T=240, max_months=2400,
                           series_every=0)).summary()
    assert [s["total_U"], s["peak_monthly_U"], s["calm_month"]] == \
           [ref["total_U"], ref["peak_monthly_U"], ref["calm_month"]]
    assert s["final_positive"] == 0 and s["final_members"] == 0


def slow_regressions():
    ref = json.loads((EXP / "delta_adoption_study_results.json").read_text(encoding="utf-8"))
    g = hex_grid()
    c = g.meta["center"]
    s = simulate(g, Params(decay="none", delta=0.0, seeds=[(c, 0, 25.0)], series_every=0)).summary()
    r = ref["growth_delta_0"]
    assert [s["rounds"], s["total_U"], s["peak_queue"]] == [r["rounds"], r["U"], r["peak"]]
    s = simulate(g, Params(decay="none", delta=0.1, rho=0.95, p=0.005, init_all=100.0, series_every=0)).summary()
    r = ref["fatigue_decay_delta_0.1"]
    assert [s["rounds"], s["total_U"], s["final_members"]] == [r["rounds"], r["U"], r["members"]]
    cc = json.loads((EXP / "ripple_country_clock_study_results.json").read_text(encoding="utf-8"))["T120"]
    g2 = _hex_with_groups()
    s = simulate(g2, Params(seeds=[(c, 0, 25.0)], hold_T=120, max_months=2400, series_every=0)).summary()
    assert [s["total_U"], s["peak_monthly_U"], s["calm_month"]] == [cc["total_U"], cc["peak_monthly_U"], cc["calm_month"]]


# ------------------------------------------------------------- invariants

def _queue_walk(sim):
    out, cur = [], sim.head
    for _ in range(sim.length):
        out.append(cur)
        cur = sim.q[cur]
    return out


def test_queue_pointer_exists_exactly_while_queued():
    g = _hex_with_groups(30, 30, 20)
    sim = Simulation(g, Params(seeds=[(g.meta["center"], 0, 25.0)], series_every=0, hold_T=60))
    for _ in range(400):
        if not sim.step():
            break
        walk = _queue_walk(sim)
        assert len(walk) == len(set(walk)) == sim.length
        live = {v for v in range(g.n) if sim.q[v] != -1}
        assert live == set(walk)
        if sim.length:
            assert sim.q[sim.tail] == sim.tail
        assert sim.round_remaining <= sim.length


def test_budget_only_stretches_calendar_in_growth_only_runs():
    g = hex_grid(40, 40)
    c = g.meta["center"]
    free = simulate(g, Params(decay="none", seeds=[(c, 0, 25.0)], series_every=0))
    big = simulate(g, Params(decay="none", seeds=[(c, 0, 25.0)], series_every=0, budget=10**9))
    tight = simulate(g, Params(decay="none", seeds=[(c, 0, 25.0)], series_every=0, budget=3000))
    assert free.x == big.x and free.t == big.t
    assert tight.x == free.x and tight.rounds == free.rounds
    assert tight.t > free.t
    assert max(tight.month_U) <= 3000


def test_delta_freezes_small_changes_and_zero_input_stays_zero():
    g = from_adjacency([(1,), (0,)])
    s = simulate(g, Params(decay="none", rho=0.9, p=0.15, seeds=[(0, 0, 0.5)], series_every=0))
    assert s.x[1] == 0.0                       # 0.15 * 0.5 = 0.075 <= delta
    z = simulate(g, Params(decay="none", seeds=[], series_every=0))
    assert z.x == [0.0, 0.0] and z.U == 0


def test_country_clock_decays_to_zero_and_rejects_input():
    g = _hex_with_groups(30, 30, 20)
    sim = simulate(g, Params(seeds=[(g.meta["center"], 0, 25.0)], hold_T=60, series_every=0))
    assert sim.calm_month is not None
    assert all(a == 0 for a in sim.x)
    assert all(sim.finished[c] or sim.join[c] < 0 for c in range(sim.ng))
    assert all(sim.decay_start[c] == sim.join[c] + 60 for c in range(sim.ng) if sim.join[c] >= 0)


def test_habit_floor_keeps_custom_share():
    g = _hex_with_groups(30, 30, 20)
    sim = simulate(g, Params(seeds=[(g.meta["center"], 0, 25.0)], hold_T=60, habit_floor=0.3, series_every=0))
    assert sim.calm_month is not None and all(sim.finished[c] for c in range(sim.ng) if sim.join[c] >= 0)
    kept = [sim.x[v] / sim.peak_x[v] for v in range(g.n) if sim.x[v] > 0]
    assert kept and all(0.3 <= k <= 0.3 + 0.7 * 0.01 + 1e-12 for k in kept)   # custom = h * peak (+ tiny S tail)
    assert sim.summary()["final_members"] > 0


def test_unowned_nodes_do_not_break_clocks():
    g = _hex_with_groups(20, 20, 6)
    g.owner = [o if v % 7 else -1 for v, o in enumerate(g.owner)]
    sim = simulate(g, Params(seeds=[(g.meta["center"], 0, 25.0)], hold_T=60, max_months=900, series_every=0))
    assert sim.t <= 900


def test_directed_edges_and_zero_weights():
    from tools.obsession_sim.graph import from_spec
    one_way = from_spec({"directed": True, "nodes": [{"id": "a"}, {"id": "b"}], "edges": [["a", "b"]]})
    s = simulate(one_way, Params(decay="none", seeds=[(1, 0, 50.0)], series_every=0))
    assert s.x[0] == 0.0                       # b cannot reach a
    s = simulate(one_way, Params(decay="none", seeds=[(0, 0, 50.0)], series_every=0, max_months=24))
    assert s.x[1] > 0
    blocked = from_spec({"nodes": [{"id": 0}, {"id": 1}], "edges": [[0, 1, 0.0]]})
    s = simulate(blocked, Params(decay="none", seeds=[(0, 0, 50.0)], series_every=0, max_months=24))
    assert s.x[1] == 0.0


def test_graph_json_roundtrip_keeps_order_and_results():
    g = _hex_with_groups(25, 25, 12)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "g.json"
        save_json(g, path)
        h = load_json(path)
    assert h.incoming == g.incoming and h.outgoing == g.outgoing and h.owner == g.owner
    p = Params(seeds=[(g.meta["center"], 0, 25.0)], hold_T=60, series_every=0)
    assert simulate(g, p).summary() == simulate(h, p).summary()


def test_csv_loader():
    with tempfile.TemporaryDirectory() as d:
        n = Path(d) / "nodes.csv"
        e = Path(d) / "edges.csv"
        n.write_text("id,name,group,x,y\nA,Aden,YEM,0,0\nB,Mocha,YEM,1,0\nC,Cairo,MAM,2,0\n", encoding="utf-8")
        e.write_text("a,b,weight\nA,B,1\nB,C,0.5\n", encoding="utf-8")
        g = load_csv(n, e)
    assert g.validate() == []
    assert g.names == ["Aden", "Mocha", "Cairo"] and g.group_names == ["MAM", "YEM"]
    assert g.in_weight[2] == (0.5,)


def test_metrics_and_playback():
    g = _hex_with_groups(30, 30, 20)
    c = g.meta["center"]
    sim = simulate(g, Params(seeds=[(c, 0, 25.0)], hold_T=60, frames_every=12, series_every=12))
    ms = milestones(sim, [{"name": "home", "nodes": [c], "target_month": 0, "tolerance_months": 12},
                          {"name": "group0", "group": 0, "target_year": 1400, "fraction": 0.5}], start_year=1337)
    assert ms[0]["simulated_month"] == 0 and ms[0]["within_tolerance"]
    assert ms[1]["target_month"] == 756
    prof = front_profile(sim, c)
    assert front_speed(prof, lo=2) > 0
    pb = playback_payload(sim)
    assert pb["nodes"] == g.n and all(len(f["stages"]) == g.n for f in pb["frames"])


def main(argv):
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    if "--full" in argv:
        tests.append(slow_regressions)
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    main(sys.argv[1:])
