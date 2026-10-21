"""Cheap engineering probes and cache-only rejection, separate from acceptance.

These helpers never call Experiment.one/many/matrix. They do not change the
simulation runtime hash or turn a partial result into an acceptance pass.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import time

from .acceptance import aggregate_runs, gates
from .experiment import MODES, code_hash, environment_info, freeze_status, read_json
from .structural import StructuralRun, validate_params
from .worlds import Timeline, canonical_hash
from tools.eu5_save_parser.world_export import atomic_json


def bound_observers(log_path):
    """Bind formal checks to the selected batch, even while new saves arrive."""
    paths = []
    for entry in read_json(log_path).get("observer_manifests", []):
        path = Path(entry["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("selected observer manifest changed: " + str(path))
        paths.append(path)
    return paths


def _current(exp):
    valid, digest, _ = freeze_status()
    if not valid or digest != exp.frozen_hash or code_hash() != exp.runtime_hash:
        raise ValueError("frozen inputs or simulation runtime changed")


def _params(exp, params):
    return {**exp.config["params"], **validate_params(params or {})}


def quick_check(exp, params=None, progress=lambda *a, **k: None, cancel=None):
    """Run two months per case on the real graph; inspect only two O snapshots.

    The separate transition probe reads world state at the second snapshot. It
    does not skip months inside a historical simulation or score target dates.
    """
    start = time.perf_counter()
    _current(exp)
    problems = exp.graph.validate()
    if problems:
        raise ValueError("invalid graph: " + "; ".join(problems[:3]))
    params = _params(exp, params)
    prefixes = [(manifest, [snapshots[i] for i in range(min(2, len(snapshots)))])
                for manifest, snapshots in exp.observers]
    identity = dict(code=exp.runtime_hash, frozen=exp.frozen_hash, graph=exp.graph_hash,
                    environment=environment_info(), params=params,
                    base=canonical_hash(exp.base), faiths=exp.faiths,
                    prefixes=[dict(id=m["id"], snapshots=[s["_snapshot_sha256"] for s in snaps])
                              for m, snaps in prefixes],
                    validator=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    key = canonical_hash(identity)
    cache = exp.out / "quick" / (key + ".json")
    if cancel and cancel.is_set():
        raise InterruptedError("quick check cancelled")
    if cache.exists():
        result = read_json(cache)
        if result.get("identity") == identity and result.get("passed") is True:
            result.update(cached=True, elapsed_seconds=time.perf_counter()-start)
            atomic_json(exp.out / "quick_check.json", result)
            return result

    def observer(manifest, snapshots):
        return Timeline(exp.graph, snapshots, kind="O", world_id=manifest["id"], seed=0,
                        faith_groups=exp.faiths)

    factories = [("R", lambda: exp.timeline("R", 0, omit_wc=True))]
    factories += [("O:"+m["id"], lambda m=m, s=s: observer(m, s)) for m, s in prefixes]
    rows = []
    for world, factory in factories:
        cases = [(mode, []) for mode in MODES]
        if world == "R":
            cases += [("S", [rule]) for rule in ("wine", "contact", "ownership", "market", "preemption")]
        for mode, disabled in cases:
            if cancel and cancel.is_set():
                raise InterruptedError("quick check cancelled")
            progress(f"快速检查 {world} / {mode} / {','.join(disabled) or '基础'}")
            timeline = factory()
            config = deepcopy(exp.config)
            config.update(params=params, disabled_rules=disabled)
            spec = {**exp.spec, "targets": []}
            run = StructuralRun(exp.graph, timeline, config, spec, events=MODES[mode], seed=0,
                                end_month=min(timeline.start+2, timeline.end), cancel=cancel).run()
            if not run.ledger or len(run.ledger) > 2:
                raise ValueError("short probe exceeded its two-month scope")
            if any(not math.isfinite(float(x)) or not 0 <= x <= 100
                   for sim in (*run.sims.values(), *run.context_goods.values()) for x in sim.x):
                raise ValueError("invalid x in short probe")
            if "wine" in disabled and any(run.context_goods["wine"].x):
                raise ValueError("wine removal left initial customs")
            rows.append(dict(world=world, mode=mode, disabled_rules=disabled, months=len(run.ledger),
                             peak_U=max(run.ledger), passed=True))

    transitions = []
    for manifest, snapshots in prefixes:
        if cancel and cancel.is_set():
            raise InterruptedError("quick check cancelled")
        timeline = observer(manifest, snapshots)
        timeline.at(timeline.start)
        if len(snapshots) > 1:
            timeline.at(timeline.dates[1]-1)
            state, changed = timeline.at(timeline.dates[1])
            if not changed or state.snapshot_date != snapshots[1]["metadata"]["date"]:
                raise ValueError("observer transition did not apply the next snapshot")
            transitions.append(dict(world=timeline.id, date=state.snapshot_date, passed=True))
    _current(exp)
    result = dict(format="obsession.quick-check/1", passed=True, cached=False,
                  identity=identity, params=params, rows=rows, transitions=transitions,
                  elapsed_seconds=time.perf_counter()-start, complete_protocol=False,
                  limitation="两个月工程冒烟检查及首个世界更新；不计历史目标、不判定 L1/L2/L3。")
    atomic_json(cache, result)
    atomic_json(exp.out / "quick_check.json", result)
    return result


def cache_screen(exp, params=None, progress=lambda *a, **k: None, cancel=None, *, fit_only=True):
    """Read exact-identity R checkpoints only. A missing seed cannot prove failure.

    Whole-cell medians need all 30 seeds. Partial cells, old runtimes, fit-only
    runs and counterfactuals cannot contribute. No new long simulation runs.
    """
    start = time.perf_counter()
    _current(exp)
    params = _params(exp, params)
    cells, coverage, errors = {}, {}, []
    timelines = {seed: exp.timeline("R", seed, omit_wc=True) for seed in exp.spec["seeds"]}
    for mode in MODES:
        runs, missing = [], []
        for seed in exp.spec["seeds"]:
            if cancel and cancel.is_set():
                raise InterruptedError("cache screen cancelled")
            timeline = timelines[seed]
            identity = dict(frozen=exp.frozen_hash, world=timeline.hash, graph=exp.graph_hash,
                            environment=environment_info(), mode=mode, seed=seed, params=params,
                            disabled=[], omit_wc=True, fit_only=fit_only, end_year=None,
                            code=exp.runtime_hash, disabled_rules=[], budget_multiplier=1)
            path = exp.out / "runs" / (canonical_hash(identity) + ".json")
            if not path.exists():
                missing.append(seed)
                continue
            try:
                row = read_json(path)
                if (row["identity"] != identity or row["world_kind"] != "R" or row["world_id"] != "R"
                        or row["mode"] != mode or row["seed"] != seed or row["end_month"] != timeline.end
                        or row["world_hash"] != timeline.hash):
                    raise ValueError("checkpoint metadata mismatch")
                runs.append(row)
            except (ValueError, KeyError, TypeError) as exc:
                missing.append(seed)
                errors.append(dict(file=str(path), error=str(exc)))
        cell = mode + "×R"
        coverage[cell] = dict(completed=len(runs), required=len(exp.spec["seeds"]), missing_seeds=missing)
        if not missing and len(runs) == 30 and exp.spec["seeds"] == list(range(30)):
            cells[cell] = aggregate_runs(runs)
        progress(f"缓存筛查 {cell} · {len(runs)}/30")
    _current(exp)
    result_gates = gates(cells, exp.spec, frozen_valid=True, world_count=len(exp.observers),
                         independent_worlds=sum(m.get("role")=="independent_validation" for m, _ in exp.observers),
                         complete_protocol=False)
    if fit_only:
        result_gates["L1"] = dict(status="无法判定", failures=[], missing=["全集及留出由审计方判定"], cells={})
    for gate in result_gates.values():
        # A necessary threshold can disprove a level with other cells missing.
        # No partial report can prove any level passed.
        gate["status"] = "未达" if gate["failures"] else "无法判定"
    result = dict(format="obsession.cache-screen/1", cells=cells, coverage=coverage, errors=errors,
                  gates=result_gates, params=params, frozen_valid=True, frozen_hash=exp.frozen_hash,
                  runtime_hash=exp.runtime_hash, graph_hash=exp.graph_hash,
                  complete_protocol=False, fit_only=fit_only, simulations_started=0,
                  decision="early_reject" if any(g["failures"] for g in result_gates.values()) else "incomplete",
                  elapsed_seconds=time.perf_counter()-start,
                  limitation="只读本轮拟合集的完整 30 种子缓存；不读取留出或判定 L1，不替代审计。")
    atomic_json(exp.out / "cache_screen.json", result)
    return result
