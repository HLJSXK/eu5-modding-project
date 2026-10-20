"""Reproduce the frozen fit protocol, then the selected-parameter validation.

Run from the repository root with the project's eu5 Python environment.
`fit` never reads holdout outcomes. Commit selected_params.json and its
selection_log.json before invoking `matrix`; the runner checks this boundary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from tools.obsession_sim.acceptance import aggregate_runs
from tools.obsession_sim.experiment import Experiment, code_hash, freeze_status
from tools.eu5_save_parser.world_export import atomic_json


def rank(row):
    m = row['metrics']
    return (m['violation_count'], int(m['peak_U'] > 480000),
            -min((m['fit_within_2tol'] or 0) / .5, (m['fit_p_order'] or 0) / .7),
            -(m['fit_within_2tol'] or 0), -(m['fit_p_order'] or 0), -(m['p_K'] or 0))


def record(exp, params, runs):
    agg = aggregate_runs(runs)
    return dict(params={**exp.config['params'], **params},
                metrics={k: agg[k] for k in ('fit_within_tol', 'fit_within_2tol', 'fit_p_order',
                         'p_K', 'violation_count', 'peak_U', 'p_unseeded', 'p_conn')},
                seeds=[r['seed'] for r in runs], runs=[r['cache_file'] for r in runs],
                runtime_hash=exp.runtime_hash, frozen_hash=exp.frozen_hash)


def fit(exp, workers, protocol_path):
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    assert protocol['runtime_hash'] == exp.runtime_hash and protocol['frozen_hash'] == exp.frozen_hash
    grid = protocol['grid']
    phase_a = exp.many([dict(world='R', mode='S', seed=0, params=p, fit_only=True, omit_wc=True)
                        for p in grid], workers=workers)
    rows = [record(exp, p, [r]) for p, r in zip(grid, phase_a)]
    atomic_json(exp.out/'bounded_fit_phase_a.json', rows)
    assert code_hash() == exp.runtime_hash
    finalists = sorted(range(len(grid)), key=lambda i: rank(rows[i]))[:protocol['finalist_count']]
    extra_seeds = [s for s in protocol['seeds_finalists'] if s not in protocol['seeds_phase_a']]
    phase_b = exp.many([dict(world='R', mode='S', seed=s, params=grid[i], fit_only=True, omit_wc=True)
                        for i in finalists for s in extra_seeds], workers=workers)
    for j, i in enumerate(finalists):
        rows[i] = record(exp, grid[i], [phase_a[i], *phase_b[j*len(extra_seeds):(j+1)*len(extra_seeds)]])
    ranked = sorted((rows[i] for i in finalists), key=rank)
    valid, frozen, _ = freeze_status()
    assert valid and frozen == exp.frozen_hash and code_hash() == exp.runtime_hash
    result = dict(format='obsession.fit-selection/1', protocol=str(protocol_path),
                  policy=protocol['ranking'], frozen_hash=frozen, runtime_hash=exp.runtime_hash,
                  candidates=rows, finalists=ranked, recommended=ranked[0])
    atomic_json(exp.out/'bounded_fit_comparison.json', result)
    print(json.dumps(result['recommended'], ensure_ascii=False), flush=True)


def selected(exp):
    paths = ['tools/obsession_sim/selected_params.json', 'tools/obsession_sim/selection_log.json']
    for name in paths:
        committed = subprocess.check_output(['git', 'show', 'HEAD:'+name], cwd=ROOT)
        assert json.loads(committed) == json.loads((ROOT/name).read_text(encoding='utf-8')), 'Commit parameter selection before holdout validation'
    log = json.loads((ROOT/paths[1]).read_text(encoding='utf-8'))
    assert log['runtime_hash'] == exp.runtime_hash and log['frozen_hash'] == exp.frozen_hash
    return json.loads((ROOT/paths[0]).read_text(encoding='utf-8'))


def jointfit(exp, workers):
    protocol = json.loads(Path(__file__).with_name('structural_joint_fit_protocol.json').read_text(encoding='utf-8'))
    assert protocol['runtime_hash'] == exp.runtime_hash and protocol['frozen_hash'] == exp.frozen_hash
    candidates = {}
    for name in protocol['studies']:
        study = json.loads((ROOT/name).read_text(encoding='utf-8'))
        assert study['runtime_hash'] == exp.runtime_hash and study['frozen_hash'] == exp.frozen_hash
        for row in study['finalists']:
            candidates[json.dumps(row['params'], sort_keys=True)] = row
    finalists = sorted(candidates.values(), key=rank)[:protocol['finalist_count']]
    runs = exp.many([dict(world='R', mode='H', seed=s, params=row['params'], fit_only=True, omit_wc=True)
                     for row in finalists for s in protocol['seeds']], workers=workers)
    rows = []
    n = len(protocol['seeds'])
    for i, candidate in enumerate(finalists):
        historical = record(exp, candidate['params'], runs[i*n:(i+1)*n])
        s, h = candidate['metrics'], historical['metrics']
        ratios = [s['fit_p_order']/.6, h['fit_within_2tol']/.5, h['fit_p_order']/.7,
                  (h['p_K'] or 0)/.6, (h['p_unseeded'] or 0)/.5, (h['p_conn'] or 0)/.95]
        rows.append(dict(params=candidate['params'], structural=candidate, historical=historical,
                         violations=s['violation_count']+h['violation_count'],
                         budget_over=max(s['peak_U'],h['peak_U'])>480000, minimum_ratio=min(ratios)))
    rows.sort(key=lambda r:(r['violations'],r['budget_over'],-r['minimum_ratio'],
                           -r['historical']['metrics']['fit_within_2tol']))
    assert code_hash() == exp.runtime_hash
    result = dict(format='obsession.joint-fit-selection/1', runtime_hash=exp.runtime_hash,
                  frozen_hash=exp.frozen_hash, protocol=protocol, candidates=rows, recommended=rows[0],
                  limitation='Fit-only search diagnostics; no L1 claim and no holdout outcomes read.')
    atomic_json(exp.out/'joint_fit_comparison.json',result)
    print(json.dumps(result['recommended'], ensure_ascii=False), flush=True)


def checks(exp, params, workers):
    stages = [('inherent', ['contact', 'preemption', 'ownership', 'roads', 'market']),
              ('contact', ['preemption', 'ownership', 'roads']),
              ('preemption', ['ownership', 'roads']), ('ownership_roads', [])]
    rows = exp.many([dict(world='R', mode='S', seed=s, params=params, fit_only=True, omit_wc=True, disabled_rules=disabled)
                     for _, disabled in stages for s in range(3)], workers=workers)
    atomic_json(exp.out/'mechanism_stages_fit_only.json',
                [dict(stage=name, disabled_rules=disabled, **record(exp, params, rows[i*3:(i+1)*3]))
                 for i, (name, disabled) in enumerate(stages)])
    comparisons = [('formal', True, []), ('with_wc', False, []), ('without_wine', True, ['wine'])]
    rows = exp.many([dict(world='R', mode='H', seed=s, params=params, omit_wc=wc, disabled_rules=disabled)
                     for _, wc, disabled in comparisons for s in range(3)], workers=workers)
    atomic_json(exp.out/'prior_sensitivity.json',
                [dict(variant=name, seeds=list(range(3)), diagnostic_only=True,
                      aggregate=aggregate_runs(rows[i*3:(i+1)*3])) for i, (name, _, _) in enumerate(comparisons)])


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['fit', 'jointfit', 'matrix', 'checks', 'replays'])
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--protocol', type=Path, default=Path(__file__).with_name('structural_fit_protocol.json'))
    ap.add_argument('--out', type=Path, default=ROOT/'tmp/obsession_structural')
    args = ap.parse_args()
    exp = Experiment(ROOT/'tmp/obsession_real/eu5_1337.json', sorted((ROOT/'tmp/obsession_worlds').glob('*/timeline.json')),
                     ROOT/'.eu5-base/reference_game_files/game', args.out)
    if args.action == 'fit':
        fit(exp, args.workers, args.protocol)
    elif args.action == 'jointfit':
        jointfit(exp, args.workers)
    else:
        params = selected(exp)
        if args.action == 'matrix':
            print(json.dumps(exp.matrix(params=params, workers=args.workers)['gates'], ensure_ascii=False), flush=True)
        elif args.action == 'checks':
            checks(exp, params, args.workers)
        else:
            exp.many([dict(world=w, mode=m, seed=0, params=params, omit_wc=w=='R', frames=12)
                      for w, m in [('R', 'H'), ('O', 'G')]], workers=2)
