"""Transport invariants and budget/anti-cheat checks, independent of calibration."""
from copy import deepcopy

import pytest

from .batch import run_batch
from .core import Params, Simulation, simulate
from .graph import from_spec
from .metrics import group_arrival, milestones
from .scenario import apply_scenario
from .transport import market_routes


def tiny():
    return from_spec({"nodes": [{"id": "a", "market": "west", "population": 80, "raw_material": "coffee"},
                                {"id": "b", "market": "west", "population": 20},
                                {"id": "c", "market": "east", "population": 100}], "edges": []})


def test_route_opens_without_seed_and_wakes_stationary_source_target():
    g = tiny()
    sp = {"initial": [{"names": ["a"], "value": 30}], "seeds": [],
          "transport": {"routes": [{"from": "a", "to": "b", "weight": 1, "directed": True,
                                     "start_month": 4, "end_month": 7, "evidence": "test"}]}}
    over = apply_scenario(g, sp, .02, 1)
    sim = Simulation(g, Params(decay="none", p=.02, rho=1, max_months=10, **over))
    for _ in range(4):
        sim.step()
        assert sim.x[1] == 0 and not g.incoming[1]
    sim.step()
    assert sim.x[1] == .6 and sim.first_positive[1] == 4
    assert sim.x[2] == 0 and sim.x[0] == 30
    sim.run()
    assert not g.incoming[1] and not g.outgoing[0]
    assert sim.arrival_parent[1] == 0


def test_finite_origin_input_solves_weak_seed_without_target_assignment():
    g = tiny()
    sp = {"seeds": [{"name": "a", "value": .5}],
          "sources": [{"name": "a", "start_month": 0, "end_month": 10, "amount": .2,
                       "requires": {"raw_material": "coffee"}, "evidence": "origin ritual"}]}
    over = apply_scenario(g, sp, .02, 1)
    sim = simulate(g, Params(decay="none", rho=1, max_months=15, **over))
    assert sim.arrival[0] == 2 and sim.x[0] == pytest.approx(2.5)
    assert sim.first_positive[1:] == [-1, -1] and not sim.sources
    assert sim.U > 0
    sp["sources"][0]["requires"] = {"raw_material": "tea"}
    with pytest.raises(ValueError, match="required graph"):
        apply_scenario(tiny(), sp, .02, 1)


def test_wave_close_stops_growth_but_does_not_discard_custom():
    g = tiny()
    sp = {"seeds": [], "initial": [{"names": ["a"], "value": 30}],
          "waves": [{"start_month": 3, "end_month": 5}],
          "wake": [{"start_month": 3, "names": ["a"]}]}
    sim = simulate(g, Params(decay="none", rho=1, max_months=8, stop_when_calm=False,
                             **apply_scenario(g, sp, .02, 1)))
    assert sim.x[0] == 30 and sim.arrival[0] == 0 and sim.length == 0
    sp["waves"][0]["end_month"] = 1204
    with pytest.raises(ValueError, match="100 years"):
        apply_scenario(tiny(), sp, .02, 1)


def test_market_hubs_are_sparse_and_population_required():
    nodes = [{"id": str(i), "market": "m", "population": 100 - i} for i in range(100)]
    g = from_spec({"nodes": nodes, "edges": []})
    routes = market_routes(g, {"max_hubs": 6})
    assert len(routes) == 6
    assert max(sum(n in (r["from"], r["to"]) for r in routes) for n in g.names) == 2
    del g.attrs["population"]
    with pytest.raises(ValueError, match="save CSV"):
        market_routes(g, {})


def test_shared_budget_is_calendar_sum_and_reports_unavoidable_overrun():
    sims = [Simulation(tiny(), Params(decay="none", seeds=[(0, 0, 25)], rho=.9,
                                      max_months=4, stop_when_calm=False)) for _ in range(3)]
    result = run_batch(sims, 50)
    assert result["monthly_U"] == [sum(s.month_U[t] for s in sims) for t in range(4)]
    assert result["peak_monthly_U"] <= 50 and not result["overruns"]
    g = tiny()
    sp = {"sources": [{"name": "a", "start_month": 0, "end_month": 1,
                       "amount": .2, "evidence": "fixture"}]}
    sim = Simulation(g, Params(decay="none", max_months=2, **apply_scenario(g, sp, .02, 1)))
    assert run_batch([sim], 1)["overruns"]


def test_population_denominator_includes_unreached_majority():
    sim = simulate(tiny(), Params(decay="none", max_months=1))
    sim.arrival[:] = [-1, 1, -1]
    assert group_arrival(sim, [0, 1], .5, weights=[80, 20, 100]) is None
    sim.arrival[0] = 10
    assert group_arrival(sim, [0, 1], .5, weights=[80, 20, 100]) == 10
    sim.g.attrs.pop("population")
    with pytest.raises(ValueError, match="actual population"):
        milestones(sim, [dict(name="missing", nodes=[0], target_month=0, aggregation="population")])


def test_constraints_catch_contact_and_stage_violations():
    g = tiny()
    sp = {"seeds": [{"name": "b", "value": .5}],
          "constraints": [{"name": "no early contact", "names": ["b"], "before_month": 5, "threshold": "positive"}]}
    sim = simulate(g, Params(decay="none", max_months=2, **apply_scenario(g, sp, .02, 1)))
    assert sim.constraint_violations == [{1: 0}]


def test_invalid_or_ambiguous_transport_is_rejected():
    sp = {"transport": {"routes": [{"from": "a", "to": "b", "weight": 1, "start_month": 0}]}}
    with pytest.raises(ValueError, match="evidence"):
        apply_scenario(tiny(), sp, .02, 1)
    sp["transport"]["routes"][0]["evidence"] = "fixture"
    sp["transport"]["routes"] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        apply_scenario(tiny(), sp, .02, 1)


def test_scenario_does_not_modify_another_graph_or_parameter_input():
    original = tiny()
    g = deepcopy(original)
    sp = {"transport": {"routes": [{"from": "a", "to": "b", "weight": 1, "start_month": 0, "evidence": "fixture"}]}}
    sim = simulate(g, Params(decay="none", max_months=2, **apply_scenario(g, sp, .02, 1)))
    assert g.incoming[0] and not original.incoming[0]
    assert sp["transport"]["routes"][0]["from"] == "a"


def test_custom_joins_current_wave_and_clock_renewal_preserves_effective_x():
    g = from_spec({"nodes": [{"id": "a", "group": "country"}], "edges": []})
    sp = {"initial": [{"names": ["a"], "value": 30}], "seeds": [],
          "waves": [{"start_month": 100, "end_month": 200}],
          "wake": [{"start_month": 100, "names": ["a"]},
                   {"start_month": 150, "names": ["a"], "renew_clock": True}]}
    sim = Simulation(g, Params(rho=1, hold_T=10, max_months=151, habit_floor=.5,
                                **apply_scenario(g, sp, .02, 1)))
    for _ in range(101):
        sim.step()
    assert sim.join == [100] and not sim.decaying[0]
    while sim.t < 150:
        sim.step()
    before = sim.eff(0)
    sim.step()
    assert sim.eff(0) == pytest.approx(before)
    assert sim.join[0] == 150 and not sim.decaying[0]


def test_conditioned_contact_cannot_arrive_without_its_source():
    sp = {"contacts": [{"from": "a", "to": "b", "start_month": 3, "value": .5, "evidence": "gift"}]}
    g = tiny()
    sim = simulate(g, Params(decay="none", max_months=5, **apply_scenario(g, sp, .02, 1)))
    assert sim.first_positive == [-1, -1, -1]
    g = tiny()
    sp["initial"] = [{"names": ["a"], "value": 30}]
    sim = simulate(g, Params(decay="none", max_months=5, **apply_scenario(g, sp, .02, 1)))
    assert sim.first_positive[1] == 3 and sim.arrival[1] == -1


def test_trade_on_a_geographic_edge_restores_the_land_link_on_close():
    g = from_spec({"nodes": [{"id": "a"}, {"id": "b"}], "edges": [["a", "b", .5]]})
    sp = {"waves": [{"start_month": 0, "end_month": 3}],
          "transport": {"routes": [{"from": "a", "to": "b", "weight": 2, "start_month": 0,
                                     "end_month": 3, "evidence": "same endpoints, additive transport"}]}}
    sim = Simulation(g, Params(decay="none", max_months=5, **apply_scenario(g, sp, .02, 1)))
    sim.step()
    assert g.in_weight == [(2.5,), (2.5,)]
    sim.run()
    assert g.in_weight == [(.5,), (.5,)] and g.incoming == [(1,), (0,)]


def test_batch_prebooks_all_goods_maintenance_before_admitting_nodes():
    sims = []
    for i in range(2):
        g = tiny()
        sp = {"seeds": [{"name": "a", "value": 25}],
              "sources": [{"name": "b", "start_month": 0, "end_month": 2,
                           "amount": .2, "evidence": "source maintenance reserve"}]}
        sims.append(Simulation(g, Params(decay="none", rho=.9, max_months=3,
                                          **apply_scenario(g, sp, .02, .9))))
    result = run_batch(sims, 35)
    assert not result["overruns"] and result["peak_monthly_U"] <= 35


def test_closing_trade_on_a_strait_preserves_its_discount():
    g = from_spec({"nodes": [{"id": "a"}, {"id": "b"}], "edges": [["a", "b"]],
                   "meta": {"special_edges": [{"a": 0, "b": 1, "type": "strait"}]}})
    sp = {"transport": {"strait_weight": .25, "routes": [
        {"from": "a", "to": "b", "weight": 2, "start_month": 0, "end_month": 3, "evidence": "fixture"}]}}
    sim = Simulation(g, Params(decay="none", max_months=5, **apply_scenario(g, sp, .02, 1)))
    sim.step()
    assert g.in_weight == [(2.25,), (2.25,)]
    sim.run()
    assert g.in_weight == [(.25,), (.25,)]


def test_runtime_clock_does_not_read_offline_arrival_history():
    sp = {"initial": [{"names": ["a"], "value": 30}], "seeds": [],
          "waves": [{"start_month": 100, "end_month": 200}],
          "wake": [{"start_month": 100, "names": ["a"]}]}
    sims = []
    for _ in range(2):
        g = from_spec({"nodes": [{"id": "a", "group": "country"}], "edges": []})
        sims.append(Simulation(g, Params(rho=1, max_months=105, **apply_scenario(g, sp, .02, 1))))
    sims[1].arrival[:] = [190]  # corrupt diagnostics deliberately
    for sim in sims:
        sim.run()
    assert sims[0].join == sims[1].join == [100]
    assert sims[0].x == sims[1].x and sims[0].month_U == sims[1].month_U
