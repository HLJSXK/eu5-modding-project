"""Handoff 26 boundaries; synthetic inputs never expose holdout outcomes."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from . import structural
from .experiment import Experiment, read_json, HERE
from .structural import StructuralRun, opening_values
from .test_structural import CONFIG, SPEC, KFixture, tiny_world, chain_world
from .worlds import Timeline


def custom_run(n=3, **kw):
    g,s=chain_world(n)
    g.attrs['region'][0]='custom'
    cfg=deepcopy(CONFIG)
    cfg['initial_customs']={'tea':[dict(where={'region':'custom'},value=45)]}
    cfg['disabled_rules']=['contact','ownership']
    return StructuralRun(g,Timeline(g,[s]),cfg,SPEC,**kw)


@pytest.mark.parametrize('region,value',[(r,30 if r in ('italy_region','france_region','iberia_region') else 0)
    for r in ('italy_region','france_region','iberia_region','great_britain_region','north_german_region','russia_region','balkan_region')])
def test_wine_static_regions(region,value):
    g,s=tiny_world();g.attrs['region'][0]=region;s['locations']['a']['religion']='catholic'
    r=StructuralRun(g,Timeline(g,[s],faith_groups={'catholic':'christian'}),CONFIG,SPEC)
    assert r.wine_background(0)==value


def test_wine_requires_christian():
    g,s=tiny_world();g.attrs['region'][0]='iberia_region'
    r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),CONFIG,SPEC)
    assert r.wine_background(0)==0


def test_wine_follows_state_religion():
    g,s=tiny_world();g.attrs['region'][0]='italy_region'
    r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC)
    r.state.religion_group[0]='christian';assert r.wine_background(0)==30
    r.state.religion_group[0]='muslim';assert r.wine_background(0)==0


def test_no_wine_simulator():
    r=custom_run(end_month=5).run()
    assert set(r.sims)=={'coffee','tea','tobacco'}
    assert not hasattr(r,'context_goods')
    assert sum(r.ledger)==sum(s.U for s in r.sims.values())


def test_wine_ablation_zero():
    r=custom_run();r.disabled_rules.add('wine');r.state.religion_group[:]=['christian']*3
    assert all(r.wine_background(v)==0 for v in range(3))


def test_zone_static_membership():
    r=custom_run();sim=r.sims['tea'];before=dict(sim.zones)
    r.state.owner[:]=-1;r.state.market[:]=-1
    assert dict(opening_values('tea',r.timeline.graph,r.state,r.config))==before
    assert sim.zones=={0:45}


def test_zone_values_frozen():
    r=custom_run(end_month=600);sim=r.sims['tea'];sim.open_wave();r.run()
    assert sim.zone_values_constant and sim.x[0]==sim.eff(0)==45
    assert sim.q[0]==-1


def test_zone_no_adjacency_export():
    r=custom_run(end_month=600);sim=r.sims['tea'];sim.open_wave();r.run()
    assert sim.x==[45,0,0]
    assert all(0 not in inc for inc in sim.g.incoming)
    assert sim.zone_adjacency_arrivals==0


def test_zone_no_market_export():
    r=custom_run();sim=r.sims['tea'];sim.x[1]=2
    for _ in range(12):sim.refresh_aggregates()
    assert sim.shared_market[0]==pytest.approx(47/3)
    assert sim.shared_open_market[0]==1
    assert sim.local_terms(1,.01,.99)[2]==pytest.approx(r.config['params']['internal_rate'])


def test_zone_source_for_contact_and_ownership():
    g,s=tiny_world();cfg=deepcopy(CONFIG);cfg['initial_customs']={'tea':[dict(where={'region':'x'},value=45)]}
    s['markets']['0']['merchants']={'B':.1}
    r=StructuralRun(g,Timeline(g,[s]),cfg,SPEC);sim=r.sims['tea']
    assert sim.shared_market[0]==45
    sim.seen_pairs.clear();sim.contact_rng=SimpleNamespace(random=lambda:0.)
    r.prepare_good(sim);assert sim.x[1]==7
    r.state.owner[0]=1;r.apply_state()
    for _ in range(12):sim.refresh_aggregates()
    assert sim.owned_hot_population[1]==1 and sim.ownership_source[1]==0


def test_zone_rejects_inputs():
    r=custom_run();sim=r.sims['tea'];sim.open_wave()
    for kind in ('contact','ownership','event','seed','market','adjacency'):
        assert not sim.inject(0,7,kind)
    assert sim.zone_rejected_inputs==6 and sim.x[0]==45
    assert sim._push(0)==sim.price['push_rejected'] and sim.length==0
    assert r.events_abandoned_budget==0


def test_zone_exempt_from_decay():
    r=custom_run();sim=r.sims['tea'];sim.x[1]=60;sim.clock_first_touch(0,0);sim.deadline[0]=0
    for t in range(400):sim.t=t;sim._clocks(t)
    assert sim.finished[0] and sim.eff(0)==45 and sim.x[0]==45
    assert sim.eff(1)<20


def test_zone_does_not_start_clock():
    r=custom_run();sim=r.sims['tea'];sim.open_wave();sim.serve_shared_tasks(10000)
    assert sim.deadline==[-1]
    sim.t=17;sim.inject(1,7,'event');assert sim.deadline==[1457]


def test_deadline_first_touch():
    r=custom_run();sim=r.sims['coffee'];sim.t=10;sim.open_wave();sim.inject(1,7,'event')
    assert sim.deadline[0]==1450 and not hasattr(sim,'join')
    assert sim.clock_history[0]['first_touch_month']==10


def test_deadline_national():
    r=custom_run();sim=r.sims['coffee'];sim.clock_first_touch(0,0)
    sim.shared_open_country[0]=20;sim._clocks(100)
    assert sim.deadline[0]==340
    sim._clocks(101);assert sim.deadline[0]==340
    assert sim.clock_history[0]['national_month']==100


def test_deadline_cap():
    r=custom_run();sim=r.sims['coffee'];sim.clock_first_touch(0,4)
    sim._clocks(1443);assert not sim.decaying[0]
    sim._clocks(1444);assert sim.decaying[0] and sim.decay_start[0]==1444


def test_deadline_renewal():
    r=custom_run();sim=r.sims['tea'];sim.clock_first_touch(0,4);sim.x[1]=50
    sim.decaying[0]=True;sim.S[0]=.2;before=sim.eff(1)
    sim.t=200;sim.open_wave('contact_success');sim.serve_shared_tasks(10000)
    assert sim.deadline[0]==-1 and sim.x[1]==before and sim.x[0]==45
    sim.clock_first_touch(0,201);sim.spreading=False;sim.wave_end=202;sim.t=202
    sim.open_wave('ownership_pair');sim.serve_shared_tasks(10000)
    assert sim.deadline[0]==1641


@pytest.mark.parametrize('month,adoption,scale',[(20,0,.5),(100,80,.5),(230,10,.5)])
def test_deadline_ban_equivalence(month,adoption,scale):
    r=custom_run();sim=r.sims['coffee'];sim.deadline[0]=adoption+240
    sim.apply_ban(0,month,scale)
    old=month+scale*max(0,adoption+240-month)-240
    assert sim.deadline[0]==round(old+240)


def test_r_share_quantile():
    g,s=tiny_world();exp=Experiment.__new__(Experiment)
    exp.graph,exp.base,exp.facts,exp.faiths=g,s,[],{}
    exp.out=HERE/'nonexistent-test-output';exp.priors=read_json(HERE/'world_priors.json')
    assert exp.timeline('R',0).residency_power==.01605427509424987
    assert Timeline(g,[s]).at(0)[0].markets[0]['merchants']=={0:1.}


def test_k2_vacuous_untriggered():
    f=KFixture();f.cx['coffee'][1]=20;f.obs(1);f.obs(1201)
    assert f.status('K2')['cases'][0]['reason']=='rival never present'


def test_k2_present_pass():
    f=KFixture();f.cx['coffee'][1]=20;f.obs(1);f.cx['tea'][1]=1;f.obs(1201)
    assert f.status('K2')['status']=='pass'


def test_k_case_population_rank():
    f=KFixture(n=10);f.state.population[:]=np.arange(10,0,-1)
    f.state.markets[3]['merchants'][2]=.1
    inputs=[dict(good='tobacco',country=c,type='contact') for c in (0,1,2)]
    f.mx['coffee'][3]=20;f.obs(1,inputs=inputs)
    assert {c['country'] for c in f.status('K5')['cases']}=={0,1}
    assert 2 in f.e.seen['K5'] and 2 in f.e.seen['K1']
    f.state.population[2]=100;f.obs(2,inputs=inputs)
    assert {c['country'] for c in f.status('K5')['cases']}=={0,1}


def test_mechanics_only_does_not_construct_scorers(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('mechanics must not load scorers')
    monkeypatch.setattr(structural,'RunMetrics',forbidden)
    monkeypatch.setattr(structural,'ConditionalEvaluator',forbidden)
    r=custom_run(end_month=5,mechanics_only=True).run()
    assert r.evaluator is r.metrics is None
    result=r.mechanics_report();assert 'milestones' not in result and 'K' not in result
    assert result['zone_values_constant']['tea']


def test_round3_ranking_does_not_use_k_in_primary_score():
    from .round3_workflow import compare
    m=dict(violation_count=0,peak_U=480000,fit_within_2tol=.5,fit_p_order=.7,
           fit_within_tol=.2,p_K=0,triggered_K=2,peak_round_delay_months=1,events_abandoned_budget=0)
    a=dict(params={'p':.01},metrics=m)
    b=dict(params={'p':.02},metrics={**m,'fit_within_2tol':.4,'p_K':1})
    assert compare(a,b)<0
    b=dict(params=a['params'],metrics={**m,'p_K':1})
    assert compare(a,b)==0  # Fewer than 3 K rules: this level is equal.
    a['metrics']={**m,'triggered_K':3};b['metrics']['triggered_K']=3
    assert compare(a,b)>0


def test_round3_protocol_exact_ranges_and_one_latin_batch(tmp_path, monkeypatch):
    from . import round3_workflow as w
    from .round2 import write_json
    from .worlds import canonical_hash
    out=tmp_path
    write_json(out/'world_audit_batch.json',dict(passed=True,world_sha256=canonical_hash([]),seeds=list(range(30))))
    write_json(out/'mechanics_only.json',{'mechanics_only':True})
    targets=[dict(split='fit',grade='B') for _ in range(24)]
    exp=SimpleNamespace(frozen_valid=True,out=out,facts=[],targets=targets,runtime_hash='code',frozen_hash='frozen',graph_hash='graph')
    monkeypatch.setattr(w,'PROTOCOL',out/'protocol.json');w.make_protocol(exp)
    p=read_json(out/'protocol.json')
    assert p['generation_seed']==2026102201 and p['candidate_count']==64
    assert p['finalist_count']==6 and p['seeds_finalists']==list(range(5))
    assert p['fit_AB_targets']==24 and p['mechanics_run_count']==1
    assert p['ranges']['lambda_contact']==[2,300,'log']
    assert p['ranges']['lambda_ownership']==[.3,300,'log']
    assert p['ranges']['p']==[.003,.03,'log'] and p['ranges']['preemption']==[0,.2,'linear']
    for k,(lo,hi,scale) in p['ranges'].items():
        values=np.array([r[k] for r in p['grid']])
        positions=(np.log(values/lo)/np.log(hi/lo) if scale=='log' else (values-lo)/(hi-lo))
        assert sorted(np.floor(positions*64).astype(int))==list(range(64))
