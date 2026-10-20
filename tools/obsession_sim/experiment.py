"""Frozen three-layer experiments, fixed-seed MC, ablations and matrix reports.

Run --help for reproducible command lines. All outputs are resumable checkpoints
under --out. An observer world stops at its last available snapshot, never at an
invented future date. Parameter selection evaluates the fit split only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
import hashlib
import itertools
import json
import multiprocessing
from pathlib import Path
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .acceptance import aggregate_runs, event_dependence, gates, moved, q
from .export import export_html, playback_payload
from .graph import load_json
from .structural import StructuralRun, validate_params
from .worlds import Timeline, canonical_hash, historical_base, read_timeline, religion_groups
from tools.eu5_save_parser.world_export import atomic_json, json_scalar

HERE = Path(__file__).resolve().parent
FROZEN = ("acceptance_spec.json", "regional_targets.json", "world_facts.json", "structural_config.json", "world_priors.json")
MODES = {"S":"none", "H":"historical", "G":"generic", "F":"mixed"}
RUNTIME_NAMES=("__init__.py","acceptance.py","conditional.py","core.py","eu5_map.py","experiment.py","export.py","graph.py","metrics.py","presets.py","structural.py","worlds.py")
_WORKER = None
_WORKER_CANCEL = None


def _init_worker(graph, observers, reference, out, cancel):
    global _WORKER, _WORKER_CANCEL
    _WORKER = Experiment(graph, observers, reference, out)
    _WORKER_CANCEL = cancel


def _worker_one(request):
    return _WORKER.one(**request,cancel=_WORKER_CANCEL)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def freeze_status():
    frozen = read_json(HERE / "frozen_manifest.json")
    canonical = frozen.get("hash_mode") == "canonical-json"
    actual = {name: canonical_hash(read_json(HERE/name)) if canonical else hashlib.sha256((HERE/name).read_bytes()).hexdigest()
              for name in FROZEN}
    return actual == frozen["files"], canonical_hash(frozen), actual


def code_hash():
    return code_bundle()['runtime_hash']


def code_bundle():
    files={}
    paths={f'tools/obsession_sim/{name}':HERE/name for name in RUNTIME_NAMES}
    paths.update({f'tools/eu5_save_parser/{name}':HERE.parent/'eu5_save_parser'/name
                  for name in ('__init__.py','parser.py','world_export.py','relationships_export.py')})
    for name,path in paths.items():
        raw=path.read_bytes()
        files[name]={'sha256':hashlib.sha256(raw).hexdigest(),'source':raw.decode('utf-8')}
    return {'format':'obsession.runtime-source/1','files':files,
            'runtime_hash':canonical_hash({name:r['sha256'] for name,r in files.items()})}


def environment_info():
    return {'python':sys.version.split()[0],'numpy':getattr(sys.modules.get('numpy'),'__version__',None),'platform':sys.platform}


class Experiment:
    def __init__(self, graph_path, observer_paths, reference, out):
        self.graph_path = Path(graph_path).resolve()
        self.graph_hash=hashlib.sha256(self.graph_path.read_bytes()).hexdigest()
        self.graph = load_json(graph_path)
        self.observers = [read_timeline(p,lazy=True) for p in observer_paths]
        self.observer_paths = [str(Path(p).resolve()) for p in observer_paths]
        if not self.observers:
            raise ValueError("the initial engine world requires an exported near-start snapshot")
        self.reference = Path(reference).resolve()
        self.faiths = religion_groups(self.reference)
        self.out = Path(out).resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.spec = read_json(HERE/"acceptance_spec.json")
        self.targets = read_json(HERE/"regional_targets.json")["targets"]
        self.config = read_json(HERE/"structural_config.json")
        self.facts = read_json(HERE/"world_facts.json")["facts"]
        self.priors = read_json(HERE/"world_priors.json")
        self.frozen_valid, self.frozen_hash, self.actual_hashes = freeze_status()
        bundle=code_bundle();self.runtime_hash=bundle['runtime_hash']
        self.code_snapshot=self.out/'inputs'/'code'/(self.runtime_hash+'.json')
        # The parent creates this immutable archive before starting workers.
        # Replacing the same file in every Windows worker races with readers.
        if self.code_snapshot.exists():
            if read_json(self.code_snapshot) != bundle:
                raise ValueError("runtime source archive does not match its hash")
        else:
            atomic_json(self.code_snapshot,bundle)
        signature = canonical_hash({"initial": self.observers[0][1][0]["_snapshot_sha256"],
                                    "builder":{name:bundle['files']['tools/obsession_sim/'+name]['sha256'] for name in ('worlds.py','eu5_map.py')},
                                    "graph":self.graph_hash,
                                    "setup": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                              list((self.reference/"main_menu/setup/1337").glob("*.txt"))+
                                              list((self.reference/"in_game/setup/countries").glob("*.txt"))}})
        cached = self.out/"inputs"/"R_base.json"
        if cached.exists() and read_json(cached).get("build_signature") == signature:
            self.base = read_json(cached)["snapshot"]
        else:
            self.base = historical_base(self.graph, self.observers[0][1][0], self.reference)
            atomic_json(cached, {"build_signature":signature, "snapshot":self.base})

    def timeline(self, world, seed, omit_wc=False):
        if world == "R":
            share = self.priors["foreign_share_quantiles"]["0.5"]
            return Timeline(self.graph, [self.base], kind="R", facts=self.facts, seed=seed,
                            faith_groups=self.faiths, omit_wc=omit_wc,residency_power=share/(1-share))
        match = next(((m,s) for m,s in self.observers if world in ("O", "O:"+m["id"])), None)
        if match is None:
            raise ValueError("unknown observer world")
        manifest, snapshots = match
        return Timeline(self.graph, snapshots, kind="O", world_id=manifest["id"], seed=seed, faith_groups=self.faiths)

    def one(self, world, mode, seed, *, params=None, disabled_events=(), omit_wc=False, fit_only=False,
            frames=0, end_year=None, progress=None, cancel=None, disabled_rules=()):
        timeline = self.timeline(world, seed, omit_wc)
        config = deepcopy(self.config)
        allowed_rules = {"contact","preemption","ownership","roads","market","wine"}
        if set(disabled_rules) - allowed_rules:
            raise ValueError("unknown structural rule")
        config["disabled_rules"] = list(disabled_rules)
        for name,value in validate_params(params or {}).items():
            config["params"][name] = value
        if seed not in self.spec["seeds"] or isinstance(seed,bool):
            raise ValueError("seed must be a fixed ID 0–29")
        spec = deepcopy(self.spec)
        spec["targets"] = [r for r in self.targets if not fit_only or r["split"] == "fit"]
        identity = {"frozen":self.frozen_hash, "world":timeline.hash,'graph':self.graph_hash,'environment':environment_info(), "mode":mode, "seed":seed,
                    "params":config["params"], "disabled":list(disabled_events), "omit_wc":omit_wc,
                    "fit_only":fit_only, "end_year":end_year, "code":self.runtime_hash,"disabled_rules":list(disabled_rules)}
        key = canonical_hash(identity)
        cache = self.out/"runs"/(key+".json")
        if cache.exists() and not frames:
            return read_json(cache)
        start = time.perf_counter()
        run = StructuralRun(self.graph, timeline, config, spec, events=MODES.get(mode,mode), seed=seed,
                            disabled_events=disabled_events, frames_every=frames,
                            end_month=round((end_year-1337)*12) if end_year else None, cancel=cancel)
        run.run(progress)
        result = run.metrics.report(run)
        result.update(identity=identity, world_id=timeline.id, world_kind=timeline.kind, mode=mode, seed=seed,
                      elapsed_seconds=time.perf_counter()-start, end_month=run.end, world_hash=timeline.hash,
                      world_dates=[s["metadata"]["date"] for s in timeline.snapshots],
                      params=config["params"], frozen_hash=self.frozen_hash, cache_file=str(cache))
        result.update(graph_hash=self.graph_hash,code_snapshot=str(self.code_snapshot),environment=environment_info())
        result['country_labels']=[run.state.countries.get(c,{}).get('tag') or c for c in timeline.country_names]
        result = json.loads(json.dumps(result,allow_nan=False,default=json_scalar))
        atomic_json(cache,result)
        if frames:
            result["replays"] = {}
            for good,sim in run.sims.items():
                path = self.out/"replays"/f"{timeline.id}_{mode}_{seed}_{key[:12]}_{good}.json"
                payload = playback_payload(sim, title=f"{mode}×{timeline.kind} · {good} · seed {seed}", start_year=1337,
                                           milestone_results=[r for r in result["milestones"] if r["good"] == good])
                payload.update(world_frames=run.world_log, arrival_kind=sim.arrival_kind,
                               structural={"events":run.event_log, "K":result["K"], "world_hash":timeline.hash,
                                           "world_kind":timeline.kind,"world_id":timeline.id,"mode":mode,
                                           "sources":sim.nonlocal_log,"waves":sim.waves})
                initial=run.world_log[0]
                payload['group']=initial['owner']
                payload['attrs']={**payload['attrs'],'owner_tag':[initial['group_labels'][c] if c>=0 else None for c in initial['owner']],
                                  'market':initial['market']}
                payload['graph_meta']={**payload['graph_meta'],'source_date':initial['date'],
                    'owner_source':('1337 setup plus sourced political facts' if timeline.kind=='R' else 'Observed /2 world snapshots: '+timeline.id)}
                payload = json.loads(json.dumps(payload,allow_nan=False,default=json_scalar))
                atomic_json(path,payload)
                # Existing map viewer remains the renderer for this new engine.
                template = Path(__file__).resolve().parents[2]/"docs/design/obsession/experiments/immunity_lock_viz.html"
                data = json.dumps(payload,ensure_ascii=False,separators=(",",":"),allow_nan=False).replace("<","\\u003c")
                path.with_suffix(".html").write_text(template.read_text(encoding="utf-8").replace("</body>",
                    '<script type="application/json" id="obsession-playback-data">'+data+'</script></body>'),encoding="utf-8")
                result["replays"][good] = str(path)
        result = json.loads(json.dumps(result,allow_nan=False,default=json_scalar))
        atomic_json(cache,result)
        return result

    def many(self, requests, workers=1, progress=print, cancel=None):
        if workers <= 1:
            return [self.one(**request,cancel=cancel) for request in requests]
        context = multiprocessing.get_context("spawn")
        shared_cancel = context.Event()
        results = [None]*len(requests)
        done = 0
        with ProcessPoolExecutor(max_workers=workers,initializer=_init_worker,mp_context=context,
                                 initargs=(str(self.graph_path),self.observer_paths,str(self.reference),str(self.out),shared_cancel)) as pool:
            pending = {pool.submit(_worker_one,request):i for i,request in enumerate(requests)}
            while pending:
                if cancel and cancel.is_set():
                    shared_cancel.set()
                    for task in pending:
                        task.cancel()
                    raise InterruptedError("experiment cancelled")
                ready,_ = wait(pending,timeout=.5,return_when=FIRST_COMPLETED)
                for future in ready:
                    index = pending.pop(future)
                    result = future.result()
                    results[index] = result
                    done += 1
                    progress(f"{result['mode']}×{result['world_kind']} seed={result['seed']} · {done}/{len(requests)}",flush=True)
        return results

    def matrix(self, seeds=range(30), params=None, mixed=True, progress=print, cancel=None, workers=1):
        seeds = list(seeds)
        worlds = ["R"]+["O:"+m["id"] for m,_ in self.observers]
        cells, world_cells = {}, {}
        completed = {}
        if workers > 1:
            requests = [{"world":world,"mode":mode,"seed":seed,"params":params,"omit_wc":world=="R"}
                        for world in worlds for mode in (list(MODES) if mixed else ["S","H","G"]) for seed in seeds]
            results = self.many(requests,workers,progress,cancel)
            completed = {(request["world"],request["mode"],request["seed"]):result for request,result in zip(requests,results)}
        for world in worlds:
            kind = "R" if world == "R" else "O"
            local = {}
            modes = list(MODES) if mixed else ["S","H","G"]
            for mode in modes:
                runs = []
                for seed in seeds:
                    if cancel and cancel.is_set():
                        raise InterruptedError("matrix cancelled")
                    r = completed.get((world,mode,seed)) or self.one(world, mode, seed, params=params, cancel=cancel,omit_wc=world=="R")
                    runs.append(r)
                    progress(f"{mode}×{kind} {r['world_id']} seed={seed} {r['elapsed_seconds']:.1f}s",flush=True)
                local[mode] = runs
            for h,s in zip(local["H"],local["S"]):
                h["D_event"] = event_dependence(h["milestones"],s["milestones"]) if kind == "R" else None
                s["D_event"] = h["D_event"]
            for mode,runs in local.items():
                cell = aggregate_runs(runs,kind)
                if mode in ("H","F") and kind == "O":
                    base = aggregate_runs(local["S" if mode == "H" else "G"],kind)
                    key = "delta_K" if mode == "H" else "delta_K_G"
                    cell[key] = cell["p_K"]-base["p_K"] if cell["p_K"] is not None and base["p_K"] is not None else None
                if mode == "H" and kind == "R":
                    ablations = []
                    for event in [e for e in self.config["events"] if e["pool"] == "historical"]:
                        counts, moved_rows, shifts = [], [], []
                        affected=[seed for seed,baseline in zip(seeds,runs) if any(e['id']==event['id'] for e in baseline['events'])]
                        requests=[dict(world=world,mode='H',seed=seed,params=params,disabled_events=[event['id']],omit_wc=True)
                                  for seed in affected]
                        ablated=dict(zip(affected,self.many(requests,workers,progress,cancel))) if requests else {}
                        for seed, baseline in zip(seeds,runs):
                            without=ablated.get(seed,baseline)  # no activation => provably identical
                            changed = [a["id"] for a,b in zip(baseline["milestones"],without["milestones"])
                                       if a["grade"] in ("A","B") and moved(a["simulated_month"],b["simulated_month"],a["tolerance_months"])]
                            counts.append(len(changed)); moved_rows.append(changed)
                            shifts.append({'seed':seed,'milestones':[{'id':a['id'],'baseline_year':a['simulated_year'],
                                'without_year':b['simulated_year'],'delta_years':(b['simulated_month']-a['simulated_month'])/12
                                if a['simulated_month'] is not None and b['simulated_month'] is not None else None}
                                for a,b in zip(baseline['milestones'],without['milestones']) if a['id'] in changed]})
                        ablations.append({"event":event["id"],"median_moved":q(counts),"moved":moved_rows,'shifts':shifts})
                    cell["A_max"] = max((r["median_moved"] for r in ablations),default=0)
                    cell["ablation"] = ablations
                world_cells[f"{mode}×{kind}:{world}"] = cell
                cells.setdefault(f"{mode}×{kind}",cell)
        # The first O world supplies L2. Independent validation requires another
        # playthrough, explicitly kept outside parameter selection.
        valid_now, hash_now, _ = freeze_status()
        valid = self.frozen_valid and valid_now and hash_now == self.frozen_hash
        protocol = seeds == self.spec["seeds"] and code_hash() == self.runtime_hash
        gate_result = gates(cells,self.spec,frozen_valid=valid,world_count=len(self.observers),
                            independent_worlds=sum(m.get("role")=="independent_validation" for m,_ in self.observers),
                            complete_protocol=protocol)
        incomplete=[m['id'] for m,_ in self.observers if not m.get('relations_complete')]
        for level in ('L2','L3'):
            if incomplete:
                gate_result[level]['missing'].append('observer marriage/alliance inputs incomplete: '+', '.join(incomplete))
                gate_result[level]['status']='无法判定'
        primary_gate=deepcopy(gate_result)
        independent=[m for m,_ in self.observers if m.get('role')=='independent_validation' and m['id']!=self.observers[0][0]['id']]
        if independent:
            first=independent[0]
            selected={**cells,**{f'{mode}×O':world_cells[f"{mode}×O:O:{first['id']}"] for mode in (list(MODES) if mixed else ['S','H','G'])}}
            gate_result['L3']=gates(selected,self.spec,frozen_valid=valid,world_count=len(self.observers),
                                   independent_worlds=len(independent),complete_protocol=protocol)['L3']
            # The development world needs its L2 O thresholds, while every
            # independent validation world needs the stricter L3 thresholds.
            for level,prefixes in (('L2',('S×O','G×O','H×O')),('L3',('H×O','F×O'))):
                for field in ('failures','missing'):
                    gate_result['L3'][field].extend('development world: '+s for s in primary_gate[level][field] if s.startswith(prefixes))
        for manifest,_ in self.observers:
            if manifest not in independent:
                continue
            other = {**cells,**{f"{mode}×O":world_cells[f"{mode}×O:O:{manifest['id']}"] for mode in (list(MODES) if mixed else ["S","H","G"])}}
            check = gates(other,self.spec,frozen_valid=valid,world_count=len(self.observers),
                          independent_worlds=1,complete_protocol=protocol)["L3"]
            if check["status"] != "达到":
                current=gate_result["L3"]
                current["failures"].extend(f"{manifest['id']}: {f}" for f in check["failures"])
                current["missing"].extend(f"{manifest['id']}: {f}" for f in check["missing"])
                current["status"]="无法判定" if current["missing"] else "未达"
        if incomplete:
            message='observer marriage/alliance inputs incomplete: '+', '.join(incomplete)
            if message not in gate_result['L3']['missing']:gate_result['L3']['missing'].append(message)
        gate_result['L3']['status']='无法判定' if gate_result['L3']['missing'] else '未达' if gate_result['L3']['failures'] else '达到'
        effective_params={**self.config["params"],**(params or {})}
        report = {"format":"obsession.acceptance/1", "frozen_hash":self.frozen_hash,"frozen_valid":valid,
                  "input_hashes":self.actual_hashes,"runtime_hash":self.runtime_hash,"params":effective_params,
                  'graph_hash':self.graph_hash,'code_snapshot':str(self.code_snapshot),'environment':environment_info(),
                  "fixed":self.config["fixed"],"profiles":self.config["profiles"],"seeds":seeds,
                  "adjustable_numbers":len(self.config["params"]),"cells":cells,
                  "world_cells":{key:({**{k:v for k,v in cell.items() if k!='runs'},'runs_from_cell':key.split(':')[0]}
                                      if cell is cells.get(key.split(':')[0]) else cell) for key,cell in world_cells.items()},
                  "gates":gate_result,
                  "worlds":[{"id":m["id"],"dates":[e["date"] for e in m["snapshots"]],
                             'relations_complete':bool(m.get('relations_complete'))} for m,_ in self.observers],
                  "limits":["R uses 1337 populations/owners but near-start observed market boundaries.",
                            "World facts with W-C evidence require removal sensitivity; wine custom magnitude is a prior.",
                            "K3 is intentionally untriggered pending a designed supply/tax rule.",
                            "Offline U is not engine time; no game code or live-game acceptance is claimed."]}
        atomic_json(self.out/"matrix.json",report)
        template=Path(__file__).resolve().parents[2]/'docs/design/obsession/experiments/structural_workbench.html'
        embedded=json.dumps(report,ensure_ascii=False,separators=(',',':'),allow_nan=False,default=json_scalar).replace('<','\\u003c')
        (self.out/'matrix.html').write_text(template.read_text(encoding='utf-8').replace('</html>',
            '<script type="application/json" id="obsession-acceptance-data">'+embedded+'</script></html>'),encoding='utf-8')
        return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action",choices=("run","matrix","scan","stages","freeze-check"))
    ap.add_argument("--graph",type=Path,default=Path("tmp/obsession_real/eu5_1337.json"))
    ap.add_argument("--observer",type=Path,action="append")
    ap.add_argument("--reference",type=Path,default=Path(".eu5-base/reference_game_files/game"))
    ap.add_argument("--out",type=Path,default=Path("tmp/obsession_structural"))
    ap.add_argument("--world",default="R")
    ap.add_argument("--mode",choices=tuple(MODES),default="S")
    ap.add_argument("--seeds",default="0:30",help="half-open range, or comma-separated fixed seed IDs")
    ap.add_argument("--params",type=Path)
    ap.add_argument("--frames",type=int,default=0)
    ap.add_argument("--end-year",type=float)
    ap.add_argument("--omit-wc",action="store_true")
    ap.add_argument("--fit-only",action="store_true")
    ap.add_argument("--disable-rules",default="")
    ap.add_argument("--workers",type=int,choices=range(1,5),default=2)
    ap.add_argument("--theta",default="1,10,20,45")
    ap.add_argument("--contact-rates",default="0.08,0.3,1")
    args = ap.parse_args(argv)
    if args.action == "freeze-check":
        valid,hash,_ = freeze_status();print(json.dumps({"valid":valid,"hash":hash}));return 0 if valid else 1
    observers = args.observer or sorted(Path("tmp/obsession_worlds").glob("*/timeline.json"))
    exp = Experiment(args.graph,observers,args.reference,args.out)
    seeds = list(range(*map(int,args.seeds.split(":")))) if ":" in args.seeds else list(map(int,args.seeds.split(",")))
    if not seeds or len(set(seeds)) != len(seeds) or any(s not in range(30) for s in seeds):
        ap.error("seeds must be unique fixed IDs 0–29")
    params = read_json(args.params) if args.params else {}
    if args.action == "matrix":
        result = exp.matrix(seeds,params,workers=args.workers)
        print(json.dumps(result["gates"],ensure_ascii=False,indent=2))
    elif args.action == "run":
        for seed in seeds:
            r=exp.one(args.world,args.mode,seed,params=params,frames=args.frames,end_year=args.end_year,
                      omit_wc=args.omit_wc,fit_only=args.fit_only,
                      disabled_rules=[r for r in args.disable_rules.split(',') if r],
                      progress=lambda m,r:print(f"year={1337+m/12:.0f}",flush=True))
            atomic_json(args.out/f"latest_{args.mode}_{args.world.split(':')[0]}.json",r)
            keys=("fit_within_2tol","fit_p_order","p_K","peak_U","violation_count","elapsed_seconds")
            print(json.dumps({k:r[k] for k in keys},ensure_ascii=False),flush=True)
    elif args.action == "stages":
        results=[]
        stages=[("inherent",["contact","preemption","ownership","roads","market"]),
                ("contact",["preemption","ownership","roads"]),("preemption",["ownership","roads"]),("ownership_roads",[])]
        for name,disabled in stages:
            runs=[exp.one("R","S",seed,params=params,fit_only=True,disabled_rules=disabled,omit_wc=args.omit_wc) for seed in seeds]
            agg=aggregate_runs(runs)
            row={"stage":name,"disabled_rules":disabled,**{k:agg[k] for k in ("fit_within_2tol","fit_p_order","p_K","violation_count")}}
            results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
            atomic_json(args.out/"mechanism_stages_fit_only.json",results)
    else:
        results=[]
        grid = list(itertools.product(map(float,args.theta.split(",")),map(float,args.contact_rates.split(","))))
        requests=[dict(world="R",mode="S",seed=seed,params={**params,"theta":theta,"lambda_contact":rate},
                       fit_only=True,end_year=args.end_year,omit_wc=True) for theta,rate in grid for seed in seeds]
        all_runs = exp.many(requests,args.workers)
        for i,(theta,rate) in enumerate(grid):
            config={**params,"theta":theta,"lambda_contact":rate}
            rows=all_runs[i*len(seeds):(i+1)*len(seeds)]
            agg=aggregate_runs(rows)
            record={"params":config,**{k:agg[k] for k in ("fit_within_2tol","fit_p_order","p_K","violation_count")}}
            results.append(record);atomic_json(args.out/"selection_fit_only.json",results)
            print(json.dumps(record,ensure_ascii=False),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
