"""The single-wave overlay must never alias the legacy fit cache identity."""
from copy import deepcopy

from .single_wave_fit import binding, request


def test_effective_config_and_workflow_are_bound_into_cache_namespace():
    config = {"fixed": {"uniform_ebb": True, "wave_months": 1200}}
    key = binding("frozen", config, "workflow")
    legacy = deepcopy(config)
    legacy["fixed"]["uniform_ebb"] = False
    longer = deepcopy(config)
    longer["fixed"]["wave_months"] = 2400
    assert len({key, binding("frozen", legacy, "workflow"),
                binding("frozen", longer, "workflow"),
                binding("frozen", config, "edited workflow"), "frozen"}) == 5


def test_every_selection_request_excludes_holdout_and_weak_facts():
    for mode in ("S", "H"):
        row = request({"p": .01}, 4, mode, budget_multiplier=2)
        assert row["fit_only"] is True and row["omit_wc"] is True
        assert row["world"] == "R" and row["seed"] == 4
        assert row["mode"] == mode and row["budget_multiplier"] == 2
