"""Exercise the complete report with synthetic fit-only data, never old results."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from .acceptance import aggregate_runs
from .experiment import HERE, read_json
from .structural import StructuralRun
from .test_structural import CONFIG, SPEC, tiny_world
from .worlds import Timeline

ROOT=Path(__file__).resolve().parents[2]
ms=importlib.util.spec_from_file_location('round3_report_builder',ROOT/'docs/design/obsession/experiments/build_round3_report.py')
builder=importlib.util.module_from_spec(ms);ms.loader.exec_module(builder)


def synthetic_artifacts(tmp_path):
    g,s=tiny_world();sim=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1).run()
    sample=sim.metrics.report(sim)
    sample.update(identity=dict(code='code',frozen='frozen',fit_only=True),params=CONFIG['params'],country_labels=['TUR','CAS','F_SAFAVID'],end_month=1)
    sample['milestones']=[dict(id='synthetic',name='Synthetic region',good='coffee',grade='B',split='fit',target_year=1500,
        target_month=1956,tolerance_months=120,simulated_year=None,simulated_month=None,within_tolerance=False,within_2tol=False)]
    for k in ('fit_within_tol','fit_within_2tol','fit_p_order','fit_p_order_upper'):sample[k]=0.
    runs=[dict(deepcopy(sample),seed=i,mode='S',world_kind='R') for i in range(30)]
    c=aggregate_runs(runs);c['D_event']=0
    rec=dict(params=CONFIG['params'],metrics={k:0 for k in ('fit_within_tol','fit_within_2tol','fit_p_order','fit_p_order_upper','p_K','triggered_K','violation_count','peak_U','peak_round_delay_months','events_abandoned_budget')},seeds=list(range(10)),runs=['synthetic-run'])
    observer=aggregate_runs([dict(deepcopy(sample),seed=i,world_kind='O') for i in range(10)],kind='O')
    report=dict(params=CONFIG['params'],frozen_hash='frozen',runtime_hash='code',cells={'S×R':c,'H×R':c},
        world_cells={'S×O · test':observer},baseline_10=rec,ablations={'wine':rec},rollbacks={'R1':rec},gates={k:dict(failures=[]) for k in ('L1','L2','L3')},
        budget_sensitivity=dict(double_budget=rec,eligible_milestones=1,moved_fraction=0,blocks_L2=False,milestones=[dict(moved_beyond_tolerance=False)]))
    protocol=dict(grid=[CONFIG['params']],fit_AB_targets=24,mechanics_run_count=2,parameter_names=list(CONFIG['params']))
    mechanical={**sim.mechanics_report(), 'params':CONFIG['params'], 'end_month':1}
    artifacts={'fit_report.json':report,'mechanics_only.json':mechanical,'round3_fit_selection.json':dict(finalists=[rec]),
        'round3_fit_protocol.json':protocol,'world_audit_batch.json':dict(passed=True,zero_impact_errors=[]),
        'round3_fit_phase_a.json':[deepcopy(rec) for _ in range(64)],'selected_params.json':CONFIG['params'],'synthetic-run':runs[0]}
    return artifacts


def prepare(monkeypatch,tmp_path):
    artifacts=synthetic_artifacts(tmp_path)
    monkeypatch.setattr(builder,'OUT',tmp_path)
    monkeypatch.setattr(builder,'TARGET',tmp_path/'27.md')
    monkeypatch.setattr(builder,'freeze_status',lambda:(True,'frozen',{}))
    monkeypatch.setattr(builder,'code_hash',lambda:'code')
    monkeypatch.setattr(builder,'read_json',lambda p:deepcopy(artifacts[Path(p).name]) if Path(p).name in artifacts else read_json(p))
    return artifacts


def test_complete_round3_report_tables_and_offline_html(tmp_path,monkeypatch):
    prepare(monkeypatch,tmp_path);builder.build_report()
    text=(tmp_path/'27.md').read_text(encoding='utf-8')
    assert '| 63 |' in text and '新事实接触次数' in text and 'K2对手从未出现' in text
    assert 're_eng_mocha' in text and 'F_SAFAVID' in text
    assert '未达 L1' in text and '未达 L2' in text
    assert 'obsession-acceptance-gzip' in (tmp_path/'fit_report.html').read_text(encoding='utf-8')


def test_incomplete_or_holdout_report_is_rejected(tmp_path,monkeypatch):
    artifacts=prepare(monkeypatch,tmp_path)
    artifacts['fit_report.json']['cells']['S×R']['runs'].pop()
    with pytest.raises(AssertionError):builder.build_report()


def test_clock_origins_use_earlier_anchor_and_include_pending_retreat():
    def row(country,touch,national):return dict(country=country,first_touch_month=touch,national_month=national)
    h=[row(0,0,1300),row(1,0,900),row(2,5000,None),row(3,4500,None),
       row(4,0,1200),row(5,5999,None),row(1,2000,None)]
    out=builder.clock_origins(h,6000)
    assert (out['national'],out['cap'],out['pending'])==(2,3,2)
    assert out['late_national_episodes']==1 and out['simultaneous_anchor_episodes']==1
    assert sum(out['episodes'].values())==len(h)
