"""Small graphs/cases exercise the independent acceptance definitions."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from .acceptance import coverage_50, event_dependence, event_diagnostics, gates, aggregate_runs
from .conditional import ConditionalEvaluator
from .experiment import freeze_status
from .graph import from_adjacency
from .structural import StructuralRun, event_weight, validate_params
from .worlds import Timeline, canonical_hash, read_timeline

HERE = Path(__file__).parent
SPEC = json.loads((HERE/"acceptance_spec.json").read_text())
CONFIG = json.loads((HERE/"structural_config.json").read_text())


class KFixture:
    def __init__(self, n=4, kind="R"):
        self.e = ConditionalEvaluator(SPEC["K"], kind)
        self.state = SimpleNamespace(capitals={i:i for i in range(n)}, market=np.arange(n),
                                     markets=[{"merchants":{0:1.,1:1.}} for _ in range(n)])
        self.cx = {g:np.zeros(n) for g in ("coffee","tea","tobacco")}
        self.mx = deepcopy(self.cx)
        self.cap = deepcopy(self.cx)
        self.raw = {g:set() for g in self.cx}
        self.obs(0)

    def obs(self, t, inputs=(), bans=(), origin=None):
        n=len(self.state.markets)
        self.e.observe(t,self.state,self.cx,self.mx,self.cap,self.raw,inputs,bans,origin,
                       np.arange(n,0,-1),["muslim"]*n)

    def status(self,k):
        return next(r for r in self.e.report()["K"] if r["id"]==k)


def test_k1_interval_left_and_right_censoring():
    f=KFixture();f.mx["coffee"][0]=20;f.obs(1)
    assert f.status("K1")["status"]=="untriggered"
    f.cap["coffee"][1]=20;f.obs(601)
    assert f.status("K1")["status"]=="pass"
    g=KFixture();g.mx["coffee"][0]=20;g.obs(1);g.cap["coffee"][1]=20;g.obs(50)
    assert g.status("K1")["status"]=="fail"
    h=KFixture();h.mx["coffee"][0]=20;h.obs(1);h.obs(2162)
    assert h.status("K1")["status"]=="fail"


def test_k1_country_disappears():
    f=KFixture();f.mx["coffee"][0]=20;f.obs(1);f.state.capitals.pop(1);f.obs(700)
    assert f.status("K1")["status"]=="untriggered"


def test_k2_preemption_and_interruption():
    f=KFixture();f.cx["coffee"][1]=20;f.obs(1);f.cx["tea"][1]=44;f.obs(1201)
    assert f.status("K2")["status"]=="pass"
    f=KFixture();f.cx["coffee"][1]=20;f.obs(1);f.cx["tea"][1]=45;f.obs(20)
    assert f.status("K2")["status"]=="fail"
    f=KFixture();f.cx["coffee"][1]=20;f.obs(1);f.cx["coffee"][1]=19;f.obs(1201)
    assert f.status("K2")["status"]=="untriggered"


def test_k3_is_explicitly_unavailable():
    assert KFixture().status("K3")["status"]=="untriggered"
    assert KFixture().status("K3")["reason"]


def test_k4_raw_material_not_contact_and_confounding():
    f=KFixture();f.raw["tea"]={1};f.obs(1);f.obs(1201)
    assert f.status("K4")["status"]=="pass"
    f=KFixture();f.raw["tea"]={1};f.obs(1);f.cx["tea"][1]=20;f.obs(100)
    assert f.status("K4")["status"]=="fail"
    f=KFixture();f.raw["tea"]={1};f.obs(1)
    f.obs(2,inputs=[{"good":"tea","country":1,"type":"contact"}]);f.obs(1201)
    assert f.status("K4")["status"]=="untriggered"


def test_k5_first_input_and_observer_padding():
    f=KFixture();f.obs(1,inputs=[{"good":"tobacco","country":1,"type":"contact"}])
    f.cx["tobacco"][1]=20;f.obs(61)
    assert f.status("K5")["status"]=="pass"


def test_k5_uses_intensity_before_the_input():
    f=KFixture();f.cx["tobacco"][1]=25
    f.obs(1,inputs=[{"good":"tobacco","country":1,"type":"contact","country_x_before":0}])
    assert f.status("K5")["status"]=="fail"  # immediate stage2 violates the five-year lower bound
    f=KFixture(kind="O");f.obs(1,inputs=[{"good":"tobacco","country":1,"type":"ownership"}])
    f.cx["tobacco"][1]=20;f.obs(2)
    assert f.status("K5")["status"]=="pass"


def test_k6_minimum_and_right_censoring():
    f=KFixture();f.cx["tobacco"][1]=30;f.obs(1,bans=[{"good":"tobacco","country":1}])
    assert f.status("K6")["status"]=="untriggered"
    f.cx["tobacco"][1]=15;f.obs(361)
    assert f.status("K6")["status"]=="pass"
    g=KFixture();g.cx["tobacco"][1]=30;g.obs(1,bans=[{"good":"tobacco","country":1}]);g.cx["tobacco"][1]=14;g.obs(2)
    assert g.status("K6")["status"]=="fail"


def test_k7_fixed_three_candidates_second_arrival():
    f=KFixture();f.mx["coffee"][0]=20;f.obs(1,origin=0)
    f.mx["coffee"][1:3]=20;f.obs(241,origin=0)
    assert f.status("K7")["status"]=="pass"
    g=KFixture(n=3);g.mx["coffee"][0]=20;g.obs(1,origin=0)
    assert g.status("K7")["status"]=="untriggered"


def test_missing_arrival_is_in_event_dependency_denominator():
    h=[{"grade":"B","simulated_month":12,"tolerance_months":3}]
    s=[{"grade":"B","simulated_month":None,"tolerance_months":3}]
    assert event_dependence(h,s)==1
    assert event_dependence(s,s)==0


def test_bursts_are_distinct_countries_and_empty_months_are_consecutive():
    events=[dict(id="a",month=1,country=c,pool="generic",kind="spread",linked=c<4,condition_valid=True) for c in range(5)]
    r=event_diagnostics(events,[(m,True) for m in range(14)])
    assert r["B_max"]==5 and r["p_link"]==.8 and r["E_gap"]==1
    assert coverage_50([0,1,1,600,601],10)==.3


def tiny_world():
    g=from_adjacency([(1,),(0,2),(1,)],names=list("abc"),coords=[(0,0),(1,0),(2,0)],owner=[0,1,2],group_names=list("ABC"),
                     attrs={"raw_material":["coffee","tea","tobacco"],"continent":["asia","europe","america"],
                            "region":["x","y","z"],"subcontinent":["a","b","c"]})
    snap={"format":"obsession.world-snapshot/1","metadata":{"date":"1337.1.1","playthrough_id":"test"},
          "countries":{c:{"capital":n,"tag":c} for c,n in zip("ABC","abc")},
          "markets":{str(i):{"center":n,"merchants":{c:1.}} for i,(c,n) in enumerate(zip("ABC","abc"))},
          "roads":[],"locations":{n:{"owner":c,"market":str(i),"population":1.,"religion":"sunni","culture":"test"}
                                    for i,(n,c) in enumerate(zip("abc","ABC"))}}
    return g,snap


def test_worlds_are_stepwise_and_have_an_observed_end():
    g,s=tiny_world();s2=deepcopy(s);s2["metadata"]["date"]="1340.1.1";s2["locations"]["b"]["owner"]="A"
    t=Timeline(g,[s,s2],faith_groups={"sunni":"muslim"})
    assert t.at(35)[0].owner.tolist()==[0,1,2]
    assert t.at(36)[0].owner.tolist()==[0,0,2]
    assert t.end==37


def test_ownership_preserves_effective_x_and_bounds():
    g,s=tiny_world();t=Timeline(g,[s],faith_groups={"sunni":"muslim"})
    r=StructuralRun(g,t,CONFIG,SPEC,end_month=1)
    sim=r.sims["coffee"]
    sim.x[:]=[50,100,0];sim.S[:]=[.2,.01,1];sim.decaying[:]=[True,True,False]
    old=[sim.eff(v) for v in range(3)]
    r.state.owner[0]=1;r.apply_state()
    assert [sim.eff(v) for v in range(3)]==pytest.approx(old)
    assert all(0<=x<=100 for x in sim.x)


def test_positive_habit_rebase_preserves_the_entire_future_curve():
    g,s=tiny_world();t=Timeline(g,[s],faith_groups={"sunni":"muslim"})
    config=deepcopy(CONFIG);config['params']['habit_floor']=.5
    r=StructuralRun(g,t,config,SPEC,end_month=1);sim=r.sims['coffee']
    sim.x[:]=[80.,100.,0.];sim.S[1]=.02;sim.decaying[1]=True;sim.join[1]=0
    r.state.owner[0]=1;r.apply_state()
    assert sim.habit[1]==pytest.approx(.5/.51)
    stop=next(k for k in range(1,100) if .02*.98**k<.01)
    for k in range(1,61):
        sim._clocks(k)
        factor=.5+.5*.02*.98**min(k,stop)
        assert sim.eff(1)==pytest.approx(100*factor,abs=1e-10)
        assert sim.eff(0)==pytest.approx(80*factor/.51,abs=1e-10)
        assert all(0<=x<=100 for x in sim.x)
    assert sim.finished_month[1]==stop


def test_ownership_channel_also_connects_distant_land_on_one_continent():
    g,s=tiny_world();g.attrs['continent']=['asia','asia','america']
    s['locations']['b']['owner']='A';s['countries']['A']['capital']='b'
    t=Timeline(g,[s],kind='R',faith_groups={'sunni':'muslim'})
    r=StructuralRun(g,t,CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    r.disabled_rules={'contact'};sim.x[0]=30;sim.shared_country_source[0]=0
    sim.contact_rng=SimpleNamespace(random=lambda:0.)
    sim.t=20;r.prepare_good(sim)
    assert sim.wave_start==20 and sim.x[1]>0
    assert any(e['type']=='ownership' for e in sim.nonlocal_log)


def test_aggregate_change_wakes_market_without_a_location_history_cache():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),CONFIG,SPEC,end_month=1)
    sim=r.sims['coffee'];sim.x[0]=30;sim.spreading=True
    for month in range(4):
        sim.t=month;sim.refresh_aggregates()
    assert sim.shared_country_source[0]==0 and sim.shared_market[0]==30
    assert sim.q[0]>=0 and sim.task_terms is None


def test_opening_native_custom_left_censors_first_tobacco_input():
    g,s=tiny_world();s['locations']['b'].update(owner='C',population=9.)
    r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),CONFIG,SPEC,end_month=1)
    assert r.sims['tobacco'].country_value(2)==3
    assert 2 in r.evaluator.seen['K5']


def test_dynamic_runner_shares_budget_and_only_queue_pointer_is_transient():
    g,s=tiny_world();s["metadata"]["date"]="1440.1.1"
    t=Timeline(g,[s],kind="R",faith_groups={"sunni":"muslim"})
    t.start=1236;t.end=1248
    r=StructuralRun(g,t,CONFIG,SPEC).run()
    assert len(r.ledger)==12
    for sim in r.sims.values():
        assert sum(v!=-1 for v in sim.q)==sim.length
        assert all(0<=x<=100 for x in sim.x)
    assert r.metrics.report(r)["K"]


def test_missing_cells_and_incomplete_mc_cannot_pass():
    r=gates({},SPEC,frozen_valid=True,world_count=1,complete_protocol=False)
    assert all(g["status"]=="无法判定" for g in r.values())
    assert any("second" in s for s in r["L3"]["missing"])
    assert freeze_status()[0]


def test_opening_customs_stay_settled_until_a_new_structural_link():
    g,s=tiny_world();cfg=deepcopy(CONFIG)
    cfg['initial_customs']['tea']=[{'where':{'region':'x'},'value':25}]
    fact=dict(id='new_resident',kind='residency',actor_location='b',location='a',start=1347,end=1400,
              grade='W-A',source='synthetic fixture',goods=['tea','coffee','tobacco'],fact='fixture')
    r=StructuralRun(g,Timeline(g,[s],kind='R',facts=[fact],faith_groups={'sunni':'muslim'}),cfg,SPEC,end_month=120).run()
    sim=r.sims['tea']
    assert sim.x==pytest.approx([25,0,0]) and sim.waves==[]
    r.state,_=r.timeline.at(120);r.apply_state();sim.t=120;r.prepare_good(sim)
    assert sim.wave_start==120 and sim.spreading


def test_mixed_pool_ratio_does_not_depend_on_template_count():
    g,s=tiny_world();cfg=deepcopy(CONFIG)
    cfg['fixed'].update(event_rate=1,event_cooldown=0,country_cooldown=0)
    cfg['events']=[dict(id=f'e{i}',pool='historical' if i<2 else 'generic',kind='spread',
                        goods=['coffee'],condition='fixture',effect='flavor') for i in range(9)]
    r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),cfg,SPEC,events='mixed',end_month=1)
    r.sims['coffee'].spreading=True;r.sims['coffee'].wave_start=0;r.sims['coffee'].shared_country[0]=30
    r.event_candidates=lambda event,good,countries=None:[(0,0,True)]
    for month in range(1000):
        r.event_done.clear();r.process_events(month)
    historical=sum(e['pool']=='historical' for e in r.event_log)
    assert len(r.event_log)==1000 and .55<historical/1000<.65
    assert event_weight({'kind':'spread'},20,front=True)==2.25
    assert event_weight({'kind':'impact'},45,blocked=True)==3.6


@pytest.mark.parametrize('values',[{'p':True},{'p':float('nan')},{'theta':0},{'hold_T':1.5},
                                   {'lambda_contact':11},{'unknown':1},{'habit_floor':-1}])
def test_shared_parameter_validation(values):
    with pytest.raises(ValueError):
        validate_params(values)


def test_lazy_worlds_preserve_identifiers_hashes_and_only_keep_two_snapshots(tmp_path):
    import hashlib
    g,s=tiny_world();entries=[]
    for i in range(4):
        snapshot=deepcopy(s);snapshot['format']='obsession.world-snapshot/2'
        snapshot['metadata']['date']=f'{1337+i}.1.1'
        path=tmp_path/f'{i}.json';path.write_text(json.dumps(snapshot),encoding='utf-8')
        entries.append(dict(file=path.name,date=snapshot['metadata']['date'],sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    path=tmp_path/'timeline.json'
    path.write_text(json.dumps(dict(format='obsession.world-timeline/1',id='test',snapshots=entries)),encoding='utf-8')
    _,lazy=read_timeline(path,lazy=True);_,eager=read_timeline(path)
    a=Timeline(g,lazy);b=Timeline(g,eager)
    assert a.hash==b.hash and a.country_names==b.country_names and a.market_names==b.market_names
    assert len(lazy.cache)<=2
    for month in (0,12,24,36):
        assert a.at(month)[0].owner.tolist()==b.at(month)[0].owner.tolist()
        assert len(lazy.cache)<=2


def test_first_membership_fact_ancestry_does_not_become_model_state():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    sim.open_wave()
    sim.inject(0,25,'contact',{'market':0,'resident':0,'facts':['residency_A']})
    sim.inject(1,2,'ownership',{'node':0,'facts':['ownership_B']})
    assert sim.fact_ancestry[0]=={'residency_A'}
    assert sim.fact_ancestry[1]=={'residency_A','ownership_B'}
    assert sim.direct_evidence==set() and sim.direct_kind is None


def test_budget_admits_country_renewal_and_slices_queue_cleanup():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    sim.x[0]=100;sim.decaying[0]=True;sim.S[0]=.2;sim.open_wave()
    assert sim.serve_shared_tasks(8)==0 and sim.renew_cursor==0
    assert sim.serve_shared_tasks(200)<=200 and sim.renew_cursor==sim.ng
    sim.spreading=False;sim.cleanup_pending=True
    before=sim.length;assert sim.serve_shared_tasks(3)==3 and sim.length==before-1
    assert sum(q!=-1 for q in sim.q)==sim.length


def test_t_alive_uses_first_wave_and_missing_losses_remain_infinite():
    from .acceptance import RunMetrics
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1).run()
    sim=r.sims['coffee'];sim.first_wave_start=1200;sim.wave_start=3000;sim.external_stage2=1500
    target=dict(id='m',good='coffee',where={'region':'x'},threshold=20,target_year=1400,
                tolerance_months=120,grade='B',split='fit')
    r.metrics=RunMetrics(g,[target])
    result=r.metrics.report(r)
    assert result['sanity']['coffee']['T_alive']==25
    assert result['loss_infinite'] and result['loss'] is None
    aggregated=aggregate_runs([result])
    assert aggregated['loss_median_infinite'] and aggregated['loss_median'] is None


def test_full_matrix_exports_embedded_report_with_effective_parameters(tmp_path):
    from .experiment import Experiment,code_hash
    g,s=tiny_world();run=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1).run()
    sample=run.metrics.report(run)
    experiment=Experiment.__new__(Experiment)
    experiment.observers=[({'id':'test','snapshots':[{'date':'1337.1.1'}]},None)]
    experiment.config=deepcopy(CONFIG);experiment.spec=SPEC;experiment.out=tmp_path
    experiment.frozen_valid,experiment.frozen_hash,experiment.actual_hashes=freeze_status()
    experiment.runtime_hash=code_hash()
    def one(world,mode,seed,**kwargs):
        return dict(deepcopy(sample),mode=mode,seed=seed,world_kind='R' if world=='R' else 'O',
                    world_id=world,elapsed_seconds=0)
    experiment.one=one
    report=experiment.matrix(params={'p':.012},progress=lambda *args,**kwargs:None)
    assert len(report['cells'])==8 and all(c['run_count']==30 for c in report['cells'].values())
    assert report['params']=={**CONFIG['params'],'p':.012}
    assert report['gates']['L1']['status']=='无法判定'
    html=(tmp_path/'matrix.html').read_text(encoding='utf-8')
    assert 'id="obsession-acceptance-data"' in html
    assert json.loads((tmp_path/'matrix.json').read_text())['seeds']==list(range(30))
