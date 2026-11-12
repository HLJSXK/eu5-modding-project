"""Reproducible fit-only refit for the workspace's single-wave mechanism.

Keeps the round-three frozen inputs and candidate cloud intact. An explicit,
hash-bound overlay enables uniform_ebb; it never reuses legacy run caches.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .acceptance import aggregate_runs
from .experiment import Experiment, HERE, code_hash, freeze_status, read_json
from .round2 import ROOT
from .round3_workflow import assert_fit, rank, record
from .worlds import canonical_hash
from tools.eu5_save_parser.world_export import atomic_json

OUT = ROOT / "tmp/obsession_single_wave_20261104"
PUBLISHED = ROOT / "docs/design/obsession/experiments/single_wave_fit_protocol.json"
OVERLAY = {"uniform_ebb": True}
_EXP = None


def workflow_hash():
    return canonical_hash({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (Path(__file__), HERE / "round3_workflow.py")})


def binding(base_hash, config, workflow):
    return canonical_hash(dict(base_frozen_hash=base_hash, effective_config=config,
                               workflow_sha256=workflow))


class SingleWaveExperiment(Experiment):
    def __init__(self, out, mechanics_only=False):
        super().__init__(ROOT / "tmp/obsession_real/eu5_1337.json",
                         sorted((ROOT / "tmp/obsession_worlds_round2").glob("*/timeline.json")),
                         ROOT / ".eu5-base/reference_game_files/game", out,
                         mechanics_only=mechanics_only)
        if not self.frozen_valid:
            raise ValueError("the inherited frozen inputs changed")
        self.base_frozen_hash = self.frozen_hash
        self.config = deepcopy(self.config)
        self.config["fixed"].update(OVERLAY)
        self.workflow_sha256 = workflow_hash()
        self.frozen_hash = binding(self.base_frozen_hash, self.config, self.workflow_sha256)


def init_worker(out):
    global _EXP
    _EXP = SingleWaveExperiment(out)


def worker(request):
    return _EXP.one(**request)


def many(exp, requests, workers):
    if workers == 1:
        return [exp.one(**r) for r in requests]
    results = [None] * len(requests)
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                             initializer=init_worker, initargs=(str(exp.out),)) as pool:
        pending = {pool.submit(worker, r): i for i, r in enumerate(requests)}
        for n, future in enumerate(as_completed(pending), 1):
            i = pending[future]
            results[i] = future.result()
            r = results[i]
            print(f"{n}/{len(requests)} {r['mode']} seed={r['seed']} elapsed={r['elapsed_seconds']:.1f}s", flush=True)
    return results


def current(exp, protocol):
    valid, base, _ = freeze_status()
    if (not valid or base != exp.base_frozen_hash or code_hash() != exp.runtime_hash
            or protocol["runtime_hash"] != exp.runtime_hash
            or protocol["frozen_hash"] != exp.frozen_hash
            or protocol["workflow_sha256"] != workflow_hash()):
        raise ValueError("runtime, inputs or workflow changed; invalidate this batch before continuing")
    if canonical_hash(read_json(PUBLISHED)) != canonical_hash(protocol):
        raise ValueError("published protocol changed")


def mechanics(exp):
    params = read_json(HERE / "selected_params.json")
    result = exp.one("R", "S", 0, params=params, omit_wc=True, mechanics_only=True,
                     progress=lambda m, r: print(f"mechanics month={m}", flush=True))
    if not all(result["zone_values_constant"].values()) or any(result["zone_adjacency_arrivals"].values()):
        raise ValueError("immutable customs failed")
    if any(len(w) > 1 for w in result["waves"].values()):
        raise ValueError("single-wave mode reopened a wave")
    for good, rows in result["clocks"].items():
        waves = result["waves"][good]
        if waves and any(r["decay_start_month"] is not None and r["decay_start_month"] < waves[0]["end_month"]
                         for r in rows["history"]):
            raise ValueError("country ebbed before the single window closed")
    atomic_json(exp.out / "mechanics_only.json", result)
    print(json.dumps({k: result[k] for k in ("waves", "peak_U", "ever_member")}), flush=True)


def protocol(exp):
    previous = read_json(ROOT / "docs/design/obsession/experiments/round3_fit_protocol.json")
    m = read_json(exp.out / "mechanics_only.json")
    if m["identity"]["frozen"] != exp.frozen_hash or m["identity"]["code"] != exp.runtime_hash:
        raise ValueError("mechanics must run under the current binding first")
    result = dict(format="obsession.single-wave-fit-protocol/1", date="2026-11-04",
        runtime_hash=exp.runtime_hash, base_frozen_hash=exp.base_frozen_hash,
        frozen_hash=exp.frozen_hash, graph_hash=exp.graph_hash, workflow_sha256=workflow_hash(),
        overlay=OVERLAY, effective_config=exp.config, mechanics_sha256=canonical_hash(m),
        mechanics_run_count=1, parameter_names=previous["parameter_names"], ranges=previous["ranges"],
        grid=previous["grid"], candidate_count=len(previous["grid"]),
        generation_seed=previous["generation_seed"], seeds_phase_a=[0], finalist_count=6,
        seeds_finalists=list(range(5)), validation_seeds=list(range(30)), historical_diagnostic_seeds=list(range(5)),
        ranking=previous["ranking"], prior_round3_protocol_sha256=canonical_hash(previous),
        prior_candidate_batches=[49, 147, 64],
        selection_boundary="S×R fit-only, omit W-C. Reuse the registered 64-point cloud for a paired mechanism refit. "
            "Do not expand ranges, tune fixed window lengths, inspect holdout scores or retune after selection.",
        publication="Content-hashed protocol is written before any scored runs. No automatic Git commit; "
            "this is an independent refit, not completion of the historical handoff26 commit protocol.",
        fixed_window_note="Retains 1200 months per good from its first wave, with no per-good override. "
            "Late historical arrivals can therefore be structurally unreachable.")
    if PUBLISHED.exists() and read_json(PUBLISHED) != result:
        raise ValueError("refusing to overwrite a different published protocol")
    atomic_json(PUBLISHED, result)
    atomic_json(exp.out / "protocol.json", result)
    atomic_json(exp.out / "inputs/effective_config.json", exp.config)
    atomic_json(exp.out / "inputs/workflow_source.json", {p.name: p.read_text(encoding="utf-8")
                                                        for p in (Path(__file__), HERE / "round3_workflow.py")})
    print(f"Published {len(result['grid'])} candidates; binding {exp.frozen_hash}", flush=True)


def request(params, seed=0, mode="S", budget_multiplier=1):
    return dict(world="R", mode=mode, seed=seed, params=params, fit_only=True,
                omit_wc=True, budget_multiplier=budget_multiplier)


def fit(exp, p, workers):
    current(exp, p)
    runs = many(exp, [request(params) for params in p["grid"]], workers)
    assert_fit(runs)
    rows = [record(exp, params, [r]) for params, r in zip(p["grid"], runs)]
    atomic_json(exp.out / "phase_a.json", rows)
    stable = sorted(range(len(rows)), key=lambda i: canonical_hash(rows[i]["params"]))
    finalists = sorted(stable, key=lambda i: rank(rows[i]))[:p["finalist_count"]]
    extra_seeds = p["seeds_finalists"][1:]
    more = many(exp, [request(p["grid"][i], s) for i in finalists for s in extra_seeds], workers)
    for j, i in enumerate(finalists):
        rows[i] = record(exp, p["grid"][i], [runs[i], *more[j*len(extra_seeds):(j+1)*len(extra_seeds)]])
    ranked = sorted(sorted([rows[i] for i in finalists], key=lambda r: canonical_hash(r["params"])), key=rank)
    current(exp, p)
    result = dict(format="obsession.single-wave-fit-selection/1", runtime_hash=exp.runtime_hash,
                  frozen_hash=exp.frozen_hash, protocol_sha256=canonical_hash(p), candidate_count=len(rows),
                  selection_run_count=len(runs)+len(more), candidates=rows, finalists=ranked,
                  recommended=ranked[0], fit_only=True)
    atomic_json(exp.out / "selection.json", result)
    atomic_json(exp.out / "selected_params.json", ranked[0]["params"])
    # Selection is persisted before validation is allowed to run.
    atomic_json(exp.out / "selection_lock.json", dict(selection_sha256=canonical_hash(result),
                                                     params_sha256=canonical_hash(ranked[0]["params"])))
    print(json.dumps(result["recommended"], ensure_ascii=False), flush=True)


def diagnostics(exp, p, workers):
    current(exp, p)
    selection = read_json(exp.out / "selection.json")
    lock = read_json(exp.out / "selection_lock.json")
    params = read_json(exp.out / "selected_params.json")
    if lock != dict(selection_sha256=canonical_hash(selection), params_sha256=canonical_hash(params)):
        raise ValueError("selection lock changed")
    old = read_json(HERE / "selected_params.json")
    groups = {
        "selected_S30": [request(params, s) for s in p["validation_seeds"]],
        "selected_H5": [request(params, s, "H") for s in p["historical_diagnostic_seeds"]],
        "previous_params_S5": [request(old, s) for s in p["seeds_finalists"]],
        "double_budget_S5": [request(params, s, budget_multiplier=2) for s in p["seeds_finalists"]],
    }
    requests = [r for group in groups.values() for r in group]
    runs = many(exp, requests, workers)
    assert_fit(runs)
    result = dict(format="obsession.single-wave-fit-diagnostics/1", fit_only=True,
                  protocol_sha256=canonical_hash(p), runtime_hash=exp.runtime_hash,
                  frozen_hash=exp.frozen_hash, params=params, selection_sha256=canonical_hash(selection),
                  cells={}, runs={}, waves={}, all_single_wave=True,
                  limitation="Fit split only; no holdout/full/observer acceptance verdict. H and budget contrasts use five seeds.")
    offset = 0
    for name, group in groups.items():
        members = runs[offset:offset+len(group)]
        offset += len(group)
        result["cells"][name] = aggregate_runs(members)
        result["runs"][name] = [r["cache_file"] for r in members]
        result["waves"][name] = [r["waves"] for r in members]
        result["all_single_wave"] &= all(len(w) <= 1 for r in members for w in r["waves"].values())
    if not result["all_single_wave"]:
        raise ValueError("a scored run reopened a wave")
    base = runs[:len(groups["selected_S30"])]
    targets = []
    for row in base[0]["milestones"]:
        if row["grade"] not in ("A", "B"):
            continue
        members = [next(m for m in r["milestones"] if m["id"] == row["id"]) for r in base]
        targets.append(dict(id=row["id"], good=row["good"], label=row.get("label", row.get("name", row["id"])),
                            historical_month=row.get("target_month"), tolerance_months=row["tolerance_months"],
                            arrivals=[m["simulated_month"] for m in members]))
    result["fit_targets"] = targets
    current(exp, p)
    atomic_json(exp.out / "diagnostics.json", result)
    print(json.dumps(result["cells"], ensure_ascii=False)[:4000], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("mechanics", "protocol", "fit", "diagnostics"))
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    exp = SingleWaveExperiment(args.out, mechanics_only=args.action == "mechanics")
    if args.action == "mechanics":
        mechanics(exp)
    elif args.action == "protocol":
        protocol(exp)
    elif args.action == "fit":
        fit(exp, read_json(PUBLISHED), args.workers)
    else:
        diagnostics(exp, read_json(PUBLISHED), args.workers)


if __name__ == "__main__":
    main()
