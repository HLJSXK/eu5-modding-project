"""Report boundaries: fit-only data cannot determine the full-set L1 gate."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=json.loads((ROOT/'tools/obsession_sim/acceptance_spec.json').read_text(encoding='utf-8'))
module_spec=importlib.util.spec_from_file_location('round2_report_builder',
    ROOT/'docs/design/obsession/experiments/build_round2_report.py')
builder=importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(builder)


def test_fit_failure_does_not_claim_a_full_set_l1_verdict():
    s=dict(fit_p_order=0.,fit_within_2tol=0.,violation_count=0)
    failures=builder.fit_failures(SPEC,s,dict(D_event=0.),False)
    assert failures['L1']==[]
    assert len(failures['L2'])==2 and len(failures['L3'])==2


def test_budget_sensitivity_blocks_l2_and_l3_without_changing_l1():
    s=dict(fit_p_order=1.,fit_within_2tol=1.,violation_count=0)
    assert not any(builder.fit_failures(SPEC,s,dict(D_event=0.),False).values())
    failures=builder.fit_failures(SPEC,s,dict(D_event=0.),True)
    assert failures['L1']==[]
    assert len(failures['L2'])==len(failures['L3'])==1
    assert '预算' in failures['L2'][0]
