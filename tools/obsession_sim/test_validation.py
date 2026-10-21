"""Fast validation must stay bounded and must never invent acceptance coverage."""
from copy import deepcopy
from pathlib import Path
import threading
from unittest.mock import Mock

import pytest

from .experiment import Experiment, code_hash, environment_info, freeze_status
from .structural import StructuralRun
from .test_structural import CONFIG, SPEC, tiny_world
from .validation import bound_observers, cache_screen, quick_check
from .worlds import Timeline, canonical_hash
from tools.eu5_save_parser.world_export import atomic_json


@pytest.fixture
def experiment(tmp_path):
    graph, snapshot = tiny_world()
    snapshot["_snapshot_sha256"] = canonical_hash(snapshot)
    second = deepcopy(snapshot)
    second["metadata"]["date"] = "1340.1.1"
    second["_snapshot_sha256"] = canonical_hash(second)

    class PrefixOnly:
        def __len__(self):
            return 67

        def __getitem__(self, index):
            assert index < 2, "quick checks must not read future snapshots"
            return [snapshot, second][index]

    exp = Experiment.__new__(Experiment)
    exp.graph, exp.base, exp.observers = graph, snapshot, [({"id": "test"}, PrefixOnly())]
    exp.graph_hash = "graph"
    exp.config, exp.spec, exp.faiths, exp.facts = deepcopy(CONFIG), deepcopy(SPEC), {}, []
    exp.priors = {"foreign_share_quantiles": {"0.9": .003}, "r_common_share_quantile":"0.9"}
    exp.frozen_valid, exp.frozen_hash, _ = freeze_status()
    exp.runtime_hash, exp.out = code_hash(), tmp_path
    for name in ("one", "many", "matrix"):
        setattr(exp, name, Mock(side_effect=AssertionError("fast checks cannot run full simulations")))
    return exp


def test_quick_bounds_real_runs_reuses_cache_and_invalidates_params(experiment):
    result = quick_check(experiment)
    assert result["passed"] and not result["cached"] and not result["complete_protocol"]
    assert len(result["rows"]) == 13 and all(r["months"] <= 2 for r in result["rows"])
    assert len(result["transitions"]) == 1
    assert result["transitions"][0]["date"] == "1340.1.1"
    assert not (experiment.out / "runs").exists()
    assert quick_check(experiment)["cached"]
    assert not quick_check(experiment, params={"p": .01})["cached"]
    assert len(list((experiment.out / "quick").glob("*.json"))) == 2


def seed_cache(exp, seeds=range(30), **changes):
    # Deliberately failing full-cell fixture; no full simulation is executed.
    run = StructuralRun(exp.graph, Timeline(exp.graph, [exp.base]), exp.config, exp.spec, end_month=1).run()
    sample = run.metrics.report(run)
    for seed in seeds:
        timeline = exp.timeline("R", seed, omit_wc=True)
        identity = dict(frozen=exp.frozen_hash, world=timeline.hash, graph=exp.graph_hash,
                        environment=environment_info(), mode="S", seed=seed, params=exp.config["params"],
                        disabled=[], omit_wc=True, fit_only=True, end_year=None,
                        code=exp.runtime_hash, disabled_rules=[], budget_multiplier=1, rollbacks=[], mechanics_only=False)
        path = exp.out / "runs" / (canonical_hash(identity) + ".json")
        row = dict(deepcopy(sample), identity=identity, mode="S", world_kind="R", world_id="R", seed=seed,
                   end_month=timeline.end, world_hash=timeline.hash, p_order=.5, fit_p_order=.5, violation_count=0,
                   cache_file=str(path), **changes)
        atomic_json(path, row)


def test_only_complete_exact_cell_can_prove_failure(experiment):
    seed_cache(experiment, range(29))
    partial = cache_screen(experiment)
    assert partial["decision"] == "incomplete" and not partial["cells"]
    assert all(g["status"] == "无法判定" for g in partial["gates"].values())
    seed_cache(experiment, [29])
    complete = cache_screen(experiment)
    assert complete["simulations_started"] == 0 and not complete["complete_protocol"]
    assert complete["decision"] == "early_reject"
    assert complete["gates"]["L1"]["status"] == "无法判定"
    assert any("p_order=0.5" in s for s in complete["gates"]["L2"]["failures"])
    assert complete["coverage"]["H×R"]["completed"] == 0
    assert all(g["status"] != "达到" for g in complete["gates"].values())
    assert cache_screen(experiment, params={"p": .01})["cells"] == {}
    experiment.runtime_hash = "old"
    with pytest.raises(ValueError, match="runtime changed"):
        cache_screen(experiment)


def test_malformed_checkpoint_is_missing_and_cannot_reject(experiment):
    seed_cache(experiment)
    path = next((experiment.out / "runs").glob("*.json"))
    path.write_text("{}")
    result = cache_screen(experiment)
    assert len(result["errors"]) == 1 and not result["cells"]
    assert result["decision"] == "incomplete"


def test_cancelled_quick_does_not_return_cached_success(experiment):
    quick_check(experiment)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        quick_check(experiment, cancel=cancel)


def test_bound_observer_rejects_changed_manifest(tmp_path):
    import hashlib
    manifest = tmp_path / "timeline.json"
    manifest.write_text("{}")
    log = tmp_path / "log.json"
    atomic_json(log, {"observer_manifests": [{"path": str(manifest),
                                            "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}]})
    assert bound_observers(log) == [manifest]
    manifest.write_text('{"changed":true}')
    with pytest.raises(ValueError, match="manifest changed"):
        bound_observers(log)
