"""Calibration acceptance tests: wrong thresholds or partial denominators must not pass."""

from pathlib import Path
import json
import tempfile

import pytest

from .core import Params, simulate
from .export import export_html, playback_payload
from .graph import from_adjacency, from_spec, save_json, hops_from
from .metrics import group_arrival, milestones, resolve_nodes
from .scenario import apply_scenario


def test_thresholds_contact_and_unreached_denominator():
    g = from_adjacency([()] * 5, names=list("abcde"))
    sim = simulate(g, Params(decay="none", rho=1, seeds=[(0, 0, .5), (1, 0, 25)], max_months=2))
    assert sim.first_positive == [0, 0, -1, -1, -1]
    assert sim.arrival == [-1, 0, -1, -1, -1]
    assert sim.threshold_arrival[20] == [-1, 0, -1, -1, -1]
    sim.arrival[:] = [0, 1, -1, -1, -1]
    assert group_arrival(sim, list(range(5)), .5) is None
    sim.arrival[2] = 4
    assert group_arrival(sim, list(range(5)), .5) == 4
    row = milestones(sim, [{"name": "unreached", "nodes": [4], "threshold": 20,
                            "target_year": 1500}], 1450)[0]
    assert row["simulated_year"] is None and not row["within_tolerance"]


def test_stationary_seed_starts_country_clock():
    g = from_adjacency([()], owner=[0], group_names=["test"])
    sim = simulate(g, Params(rho=1, p=0, seeds=[(0, 0, 25)], hold_T=1, max_months=5))
    assert sim.join == [0] and sim.decay_start == [1]
    assert sim.eff(0) < 25


def test_weak_seed_freeze_is_reported_not_hidden():
    g = from_adjacency([(1,), (0,)])
    sim = simulate(g, Params(decay="none", seeds=[(0, 0, .5)]))
    assert sim.x == [.5, 0] and sim.arrival == [-1, -1]


def test_attribute_selectors_and_explicit_one_way_route():
    g = from_spec({"nodes": [{"id": "a", "region": "west"}, {"id": "b", "region": "east"}], "edges": []})
    spec = {"seeds": [{"name": "a", "year": 1451, "value": 25}],
            "coefficients": [{"where": {"region": "east"}, "p_scale": 2}],
            "routes": [{"from": "a", "to": "b", "weight": .5, "directed": True}]}
    over = apply_scenario(g, spec, .02, .99, 1450)
    assert over["seeds"] == [(0, 12, 25)] and over["p_by_node"] == [.02, .04]
    assert g.outgoing == [(1,), ()] and g.incoming == [(), (0,)] and not g.validate()
    assert resolve_nodes(g, {"where": {"region": ["east"]}}) == [1]
    assert simulate(g, Params(decay="none", seeds=[(1, 0, 25)], max_months=2)).x[0] == 0
    with pytest.raises(ValueError, match="no locations"):
        group_arrival(simulate(g, Params(decay="none")), [])


def test_embedded_html_is_self_contained_and_safe():
    g = from_adjacency([()], coords=[(1, 2)], names=["</script><script>alert(1)</script>"])
    sim = simulate(g, Params(decay="none", seeds=[(0, 0, 25)], frames_every=1, max_months=2))
    pb = playback_payload(sim, start_year=1450)
    assert pb["threshold_arrival"]["20"] == [0] and pb["start_year"] == 1450
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "report.html"
        export_html(sim, path, start_year=1450)
        html = path.read_text(encoding="utf-8")
    embedded = html.split('id="obsession-playback-data">', 1)[1].split('</script>', 1)[0]
    assert "<" not in embedded and "\\u003c" in embedded


def test_study_export_includes_importable_playback_and_named_scenario(tmp_path):
    from .study import export_study_run
    g = from_adjacency([()], coords=[(1, 2)], names=["origin"])
    sim = simulate(g, Params(decay="none", seeds=[(0, 0, 25)], frames_every=1, max_months=2))
    scenario = {"seeds": [{"name": "origin", "value": 25}], "parameters": {"p": .004}}
    export_study_run(sim, scenario, tmp_path, "coffee", [])
    playback = json.loads((tmp_path / "coffee.playback.json").read_text(encoding="utf-8"))
    html = (tmp_path / "coffee.html").read_text(encoding="utf-8")
    embedded = json.loads(html.split('id="obsession-playback-data">')[1].split('</script>')[0])
    assert playback["format"] == "obsession_sim.playback/1" and playback == embedded
    assert playback["frames"] and playback["summary"] == sim.summary()
    assert json.loads((tmp_path / "coffee.scenario.json").read_text(encoding="utf-8")) == scenario
    assert (tmp_path / "coffee.json").read_bytes() == (tmp_path / "coffee.scenario.json").read_bytes()


def test_cli_scenario_seed_front_and_final_frame(tmp_path, capsys):
    from .__main__ import main
    g = from_adjacency([(), ()], coords=[(0, 0), (10, 10)], names=["other", "seed"],
                       attrs={"area": ["north", "south"]})
    graph_path = tmp_path / "map.json"
    scenario_path = tmp_path / "scenario.json"
    save_json(g, graph_path)
    scenario_path.write_text(json.dumps({"start_year": 1450, "seeds": [{"name": "seed", "value": 25}]}))
    out = tmp_path / "results" / "result.json"
    html = tmp_path / "results" / "report.html"
    assert main(["run", "--graph", str(graph_path), "--scenario", str(scenario_path),
                 "--preset", "baseline", "--clock-group", "area", "--set", "max_months=3",
                 "--frames-every", "12", "--out", str(out), "--html", str(html)]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["seed_nodes"] == [1] and result["reachable_locations"] == 1
    assert result["graph_meta"]["clock_group"] == "area"
    content = html.read_text(encoding="utf-8")
    payload = json.loads(content.split('id="obsession-playback-data">')[1].split('</script>')[0])
    assert payload["frames"][-1]["month"] == 2
    assert payload["clock"]["join"] == [-1, 0]
    capsys.readouterr()


def test_zero_weight_routes_are_unreachable():
    graph = from_spec({"nodes": [{"id": "a"}, {"id": "b"}], "edges": [["a", "b", 0]]})
    assert hops_from(graph, 0) == [0, -1]
