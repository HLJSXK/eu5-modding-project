"""Committed, fit-only selection and diagnostics for handoff 26."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from functools import cmp_to_key
from pathlib import Path
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

from .acceptance import aggregate_runs, event_dependence, moved, q
from .experiment import Experiment, HERE, code_hash, freeze_status, read_json
from .round2 import ROOT, write_json
from .structural import FIT_PARAMS
from .worlds import canonical_hash
from tools.eu5_save_parser.world_export import atomic_json

PROTOCOL = ROOT / "docs/design/obsession/experiments/round3_fit_protocol.json"
REPORT = ROOT / "docs/design/obsession/27_Round3_Results.md"
METRICS = ("fit_within_tol", "fit_within_2tol", "fit_p_order", "p_K", "p_conn", "p_unseeded",
           "violation_count", "peak_U", "peak_round_delay_months", "events_abandoned_budget", "triggered_K", "fit_p_order_upper", "healthy_rate")


def compare(a, b):
    x,y=a['metrics'],b['metrics']
    def main(m):return (m['violation_count'],int(m['peak_U']>480000),
        -min((m['fit_within_2tol'] or 0)/.5,(m['fit_p_order'] or 0)/.7),-(m['fit_within_tol'] or 0))
    ax,by=main(x),main(y)
    if ax!=by:return -1 if ax<by else 1
    if min(x.get('triggered_K') or 0,y.get('triggered_K') or 0)>=3:
        if x['p_K']!=y['p_K']:return -1 if (x['p_K'] or 0)>(y['p_K'] or 0) else 1
    def tail(r):
        m=r['metrics'];return (m['peak_round_delay_months'],m['events_abandoned_budget'],canonical_hash(r['params']))
    return (tail(a)>tail(b))-(tail(a)<tail(b))


rank=cmp_to_key(compare)

def assert_fit(runs):
    for run in runs:
        if not run["identity"]["fit_only"] or any(m["split"] != "fit" for m in run["milestones"]):
            raise ValueError("implementation must never read full/holdout outcomes")


def committed(path):
    name = Path(path).resolve().relative_to(ROOT).as_posix()
    stored = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
    if json.loads(stored) != read_json(path):
        raise ValueError("commit before continuing: " + name)


def current(exp, protocol):
    valid, frozen, _ = freeze_status()
    if not valid or frozen != exp.frozen_hash or code_hash() != exp.runtime_hash:
        raise ValueError("frozen inputs or runtime changed")
    if protocol['runtime_hash'] != exp.runtime_hash or protocol['frozen_hash'] != exp.frozen_hash:
        raise ValueError("protocol does not bind this runtime and input set")
    if protocol['workflow_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('selection workflow changed after protocol publication')


def make_protocol(exp):
    if not exp.frozen_valid:
        raise ValueError('finish and freeze world inputs before publishing a fit protocol')
    audit = read_json(exp.out / 'world_audit_batch.json')
    if not audit['passed'] or audit['world_sha256'] != canonical_hash(exp.facts) or audit['seeds'] != list(range(30)):
        raise ValueError('all 30 formal world inputs must pass before fitting')
    targets = [r for r in exp.targets if r['split']=='fit' and r['grade'] in ('A','B') and r.get('scored',True)]
    assert len(FIT_PARAMS)*3 <= len(targets)
    ranges = dict(p=[.003,.03,'log'], rho=[.985,.9995,'linear'], lambda_contact=[2,300,'log'],
                  lambda_ownership=[.3,300,'log'], preemption=[0,.2,'linear'], internal_rate=[.0001,.005,'log'])
    # One six-dimensional Latin stratified batch, registered before outcomes.
    generation_seed = 2026102201
    rng = np.random.default_rng(generation_seed)
    n = 64
    columns = {}
    for key,(lo,hi,scale) in ranges.items():
        positions = (rng.permutation(n)+rng.random(n))/n
        columns[key] = np.exp(np.log(lo)+positions*np.log(hi/lo)) if scale=='log' else lo+positions*(hi-lo)
    grid = [{key:round(float(columns[key][i]),8) for key in FIT_PARAMS} for i in range(n)]
    result = dict(format='obsession.round3-fit-protocol/1', runtime_hash=exp.runtime_hash, frozen_hash=exp.frozen_hash,
        graph_hash=exp.graph_hash, workflow_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        parameter_names=list(FIT_PARAMS), fit_AB_targets=len(targets), generation_seed=generation_seed, ranges=ranges,
        grid=grid, candidate_count=len(grid), seeds_phase_a=[0], finalist_count=6, seeds_finalists=list(range(5)),
        ranking=['fewest negative constraints','median peak monthly U within 480000',
                 'maximize min(fit_within_2tol/.5,fit_p_order/.7)','maximize fit_within_tol',
                 'maximize p_K only when both compared candidates have at least three decidable K rules',
                 'least peak round delay, least budget-abandoned events, canonical parameter hash'],
        prior_round_candidate_lower_bound=129,
        earlier_round2_batches=[dict(candidate_count=49,status='completed'),dict(candidate_count=147,status='invalidated_or_aborted')],
        mechanics_run_count=len(read_json(exp.out/'mechanics_runs.json')) if (exp.out/'mechanics_runs.json').exists() else 1,
        mechanics_sha256=canonical_hash(read_json(exp.out/'mechanics_only.json')),
        aggregation='Five-seed medians for every ranked scalar; K comparisons skipped if either candidate has <3 decidable rules. Deterministic canonical-hash input order resolves sparse-K ties.',
        validation_seeds=list(range(30)), ablation_seeds=list(range(10)),
        diagnostics=dict(R_modes=['S','H'], O_modes=['S','G'],
                         rule_ablations=['contact','ownership','market','preemption','wine'], rollbacks=['R1','R2','R3','R4'],budget_multiplier=2),
        selection_boundary='All selection is S×R fit-only, omit W-C. Historical channel case lags are report-only. '
            'After selection is committed, use both observer playthroughs without retuning. '
            'No holdout/full scoring or L1 verdict is performed by the implementer.')
    write_json(PROTOCOL,result)
    print(f'Wrote protocol for {len(grid)} candidates. Commit it before invoking fit.',flush=True)


def record(exp, params, runs):
    assert_fit(runs)
    agg = aggregate_runs(runs)
    return dict(params=params, metrics={k:(agg['healthy_rate'] if k=='healthy_rate' else q([r.get(k) for r in runs])) for k in METRICS}, seeds=[r['seed'] for r in runs],
                runs=[r['cache_file'] for r in runs], runtime_hash=exp.runtime_hash, frozen_hash=exp.frozen_hash)


def fit(exp, protocol, workers):
    committed(PROTOCOL)
    current(exp, protocol)
    grid = protocol['grid']
    requests=[dict(world='R', mode='S', seed=0, params=params, fit_only=True, omit_wc=True) for params in grid]
    runs = exp.many(requests,workers)
    current(exp,protocol)
    rows = [record(exp, params, [run]) for params,run in zip(grid,runs)]
    atomic_json(exp.out/'round3_fit_phase_a.json',rows)
    stable_order = sorted(range(len(rows)),key=lambda i:canonical_hash(rows[i]['params']))
    finalists = sorted(stable_order,key=lambda i:rank(rows[i]))[:protocol['finalist_count']]
    extras=[s for s in protocol['seeds_finalists'] if s!=0]
    more=exp.many([dict(world='R',mode='S',seed=s,params=grid[i],fit_only=True,omit_wc=True)
                   for i in finalists for s in extras], workers)
    for j,i in enumerate(finalists):
        rows[i]=record(exp,grid[i],[runs[i],*more[j*len(extras):(j+1)*len(extras)]])
    ranked=sorted(sorted([rows[i] for i in finalists],key=lambda r:canonical_hash(r['params'])),key=rank)
    current(exp,protocol)
    result=dict(format='obsession.round3-fit-selection/1',runtime_hash=exp.runtime_hash,frozen_hash=exp.frozen_hash,
                protocol_sha256=canonical_hash(protocol),candidate_count=len(grid),
                selection_run_count=len(requests)+len(more),candidates=rows,finalists=ranked,recommended=ranked[0])
    atomic_json(exp.out/'round3_fit_selection.json',result)
    print(json.dumps(result['recommended'],ensure_ascii=False),flush=True)


def select(exp, protocol):
    current(exp,protocol)
    committed(PROTOCOL)
    result=read_json(exp.out/'round3_fit_selection.json')
    assert result['runtime_hash']==exp.runtime_hash and result['frozen_hash']==exp.frozen_hash
    write_json(HERE/'selected_params.json',result['recommended']['params'])
    log=dict(format='obsession.round3-selection-log/1',runtime_hash=exp.runtime_hash,frozen_hash=exp.frozen_hash,
        graph_hash=exp.graph_hash,protocol=str(PROTOCOL.relative_to(ROOT)),protocol_sha256=canonical_hash(protocol),
        candidate_count=result['candidate_count'],selection_run_count=result['selection_run_count'],
        total_scheduled_candidates=result['candidate_count']+sum(b['candidate_count'] for b in protocol['earlier_round2_batches']),
        earlier_round2_batches=protocol['earlier_round2_batches'],prior_round_candidate_lower_bound=129,
        selected=result['recommended'],all_candidates=result['candidates'],fit_only=True,
        observer_manifests=[dict(path=p,sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest()) for p in exp.observer_paths],
        limitation='No holdout outcomes inspected. Selected parameters and this log must be committed before auditor notification or diagnostics; observer outcomes never retune these values.')
    write_json(HERE/'selection_log.json',log)
    print('Selection written. Commit selected_params.json and selection_log.json before diagnostics/auditor notification.',flush=True)


def median_arrival(values):
    a=sorted(float('inf') if v is None else v for v in values)
    if not a:return None
    middle=(a[(len(a)-1)//2]+a[len(a)//2])/2
    return middle if math.isfinite(middle) else None


def budget_comparison(base, doubled, exp, params):
    assert_fit([*base,*doubled])
    rows=[]
    targets=[r for r in base[0]['milestones'] if r['grade'] in ('A','B')]
    for target in targets:
        def times(runs):return [next(m['simulated_month'] for m in r['milestones'] if m['id']==target['id']) for r in runs]
        a,b=median_arrival(times(base)),median_arrival(times(doubled))
        rows.append(dict(id=target['id'],good=target['good'],tolerance_months=target['tolerance_months'],
                         baseline_median_month=a,double_median_month=b,
                         moved_beyond_tolerance=moved(a,b,target['tolerance_months'])))
    fraction=sum(r['moved_beyond_tolerance'] for r in rows)/len(rows)
    return dict(format='obsession.budget-sensitivity/1',runtime_hash=exp.runtime_hash,frozen_hash=exp.frozen_hash,
                graph_hash=exp.graph_hash,params=params,seeds=list(range(10)),eligible_milestones=len(rows),
                moved_fraction=fraction,blocks_L2=fraction>1/3,milestones=rows,
                baseline=record(exp,params,base),double_budget=record(exp,params,doubled))


def diagnostics(exp, protocol, workers):
    current(exp,protocol)
    for path in (HERE/'selected_params.json',HERE/'selection_log.json'):committed(path)
    log=read_json(HERE/'selection_log.json')
    assert log['runtime_hash']==exp.runtime_hash and log['frozen_hash']==exp.frozen_hash
    params=read_json(HERE/'selected_params.json')
    requests=[dict(world='R',mode=mode,seed=s,params=params,fit_only=True,omit_wc=True)
              for mode in protocol['diagnostics']['R_modes'] for s in range(30)]
    requests += [dict(world='O:'+m['id'],mode=mode,seed=s,params=params,fit_only=True,omit_wc=True)
                 for m,_ in exp.observers for mode in protocol['diagnostics']['O_modes'] for s in range(10)]
    runs=exp.many(requests,workers)
    assert_fit(runs)
    base=[r for r in runs if r['world_kind']=='R' and r['mode']=='S']
    variants=protocol['diagnostics']['rule_ablations']
    counter=exp.many([dict(world='R',mode='S',seed=s,params=params,fit_only=True,omit_wc=True,disabled_rules=[rule])
                      for rule in variants for s in range(10)] +
                     [dict(world='R',mode='S',seed=s,params=params,fit_only=True,omit_wc=True,budget_multiplier=2) for s in range(10)],workers)
    rollback_runs=exp.many([dict(world='R',mode='S',seed=s,params=params,fit_only=True,omit_wc=True,rollbacks=[r])
                      for r in protocol['diagnostics']['rollbacks'] for s in range(10)],workers)
    current(exp,protocol)
    budget=budget_comparison(base[:10],counter[-10:],exp,params)
    atomic_json(exp.out/'budget_sensitivity.json',budget)
    ablations={name:record(exp,params,counter[i*10:(i+1)*10]) for i,name in enumerate(variants)}
    report=dict(format='obsession.fit-diagnostics/1',fit_only=True,runtime_hash=exp.runtime_hash,frozen_hash=exp.frozen_hash,
        graph_hash=exp.graph_hash,params=params,budget_sensitivity=budget,ablations=ablations,
        rollbacks={r:record(exp,params,rollback_runs[i*10:(i+1)*10]) for i,r in enumerate(protocol['diagnostics']['rollbacks'])},
        baseline_10=record(exp,params,base[:10]),cells={},world_cells={},
        worlds=[dict(id=m['id'],label=m.get('label'),dates=[e['date'] for e in m['snapshots']]) for m,_ in exp.observers],
        gates={level:dict(status='无法判定',failures=[],missing=['全集/留出及正式闸门由审计方执行']) for level in ('L1','L2','L3')})
    for mode in protocol['diagnostics']['R_modes']:
        members=[r for r in runs if r['world_kind']=='R' and r['mode']==mode]
        if mode=='H':
            for h,s in zip(members,base):h['D_event']=event_dependence(h['milestones'],s['milestones'])
        report['cells'][mode+'×R']=aggregate_runs(members)
    for manifest,_ in exp.observers:
        for mode in protocol['diagnostics']['O_modes']:
            members=[r for r in runs if r['world_id']==manifest['id'] and r['mode']==mode]
            cell=aggregate_runs(members,kind='O')
            report['world_cells'][mode+'×O · '+manifest.get('label',manifest['id'])]=cell
            report['cells'].setdefault(mode+'×O',cell)
    report['complete_protocol'] = True
    atomic_json(exp.out/'fit_report.json',report)
    template=ROOT/'docs/design/obsession/experiments/structural_workbench.html'
    embedded=json.dumps(report,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    (exp.out/'fit_report.html').write_text(template.read_text(encoding='utf-8').replace('</body>',
        '<script type="application/json" id="obsession-acceptance-data">'+embedded+'</script></body>'),encoding='utf-8')
    print(json.dumps(dict(cells={k:{metric:v.get(metric) for metric in METRICS} for k,v in report['cells'].items()},
                         budget_blocks_L2=budget['blocks_L2']),ensure_ascii=False),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['mechanics','protocol','fit','select','diagnostics'])
    parser.add_argument('--out',type=Path,default=ROOT/'tmp/obsession_round3')
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    exp=Experiment(ROOT/'tmp/obsession_real/eu5_1337.json',sorted((ROOT/'tmp/obsession_worlds_round2').glob('*/timeline.json')),
                   ROOT/'.eu5-base/reference_game_files/game',args.out,mechanics_only=args.action=='mechanics')
    if args.action=='mechanics':
        params=read_json(exp.out/'round2_params.json')
        result=exp.one('R','S',0,params=params,omit_wc=True,mechanics_only=True,progress=lambda m,r:print(f'mechanics month={m}',flush=True))
        atomic_json(exp.out/'mechanics_only.json',result)
        ledger=read_json(exp.out/'mechanics_runs.json') if (exp.out/'mechanics_runs.json').exists() else []
        filename=f'mechanics_only_{len(ledger)+1}.json'
        atomic_json(exp.out/filename,result)
        ledger.append(dict(file=filename,code=result['identity']['code'],sha256=canonical_hash(result)))
        atomic_json(exp.out/'mechanics_runs.json',ledger)
        print(json.dumps({k:result[k] for k in ('zone_values_constant','zone_adjacency_arrivals','peak_U','clock_counts','ever_member')},ensure_ascii=False),flush=True)
    elif args.action=='protocol':make_protocol(exp)
    else:
        protocol=read_json(PROTOCOL)
        if args.action=='fit':fit(exp,protocol,args.workers)
        elif args.action=='select':select(exp,protocol)
        else:diagnostics(exp,protocol,args.workers)


if __name__=='__main__':main()
