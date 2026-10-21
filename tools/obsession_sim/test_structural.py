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
from .worlds import Timeline, canonical_hash, read_timeline,weighted_means

HERE = Path(__file__).parent
SPEC = json.loads((HERE/"acceptance_spec.json").read_text())
CONFIG = json.loads((HERE/"structural_config.json").read_text())


class KFixture:
    def __init__(self, n=4, kind="R"):
        self.e = ConditionalEvaluator(SPEC["K"], kind)
        self.state = SimpleNamespace(capitals={i:i for i in range(n)}, market=np.arange(n),
                                     owner=np.arange(n), population=np.ones(n),
                                     markets=[{"center":i,"merchants":{0:1.,1:1.}} for i in range(n)])
        self.state.population[1] = 2.  # J15: the existing K1/K5 fixture is a large country.
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


def test_k4_origins_are_commodity_specific_and_follow_the_exogenous_origin():
    f=KFixture();f.e.first=True;f.cx['tea'][1]=20;f.obs(0)
    f.raw['coffee']={1};f.obs(1);f.obs(1201)
    assert f.status('K4')['status']=='pass'  # Tea custom does not make it coffee's origin country.
    f=KFixture();f.raw['coffee']={1};f.obs(1)
    f.e.origin_countries['coffee']={1};f.obs(2)
    assert f.status('K4')['status']=='untriggered'
    assert f.status('K4')['cases'][0]['reason']=='origin country for this good'


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


def chain_world(n=9):
    names=[f'n{i}' for i in range(n)]
    g=from_adjacency([tuple(v for v in (i-1,i+1) if 0<=v<n) for i in range(n)],names=names,
        owner=[0]*n,group_names=['A'],attrs={'region':['chain']*n,'continent':['asia']*n,
                                         'subcontinent':['other']*n,'raw_material':[None]*n})
    s=dict(format='obsession.world-snapshot/2',metadata=dict(date='1337.1.1',playthrough_id='test'),
           countries={'A':dict(capital='n0',tag='A')},markets={'m':dict(center='n0',merchants={'A':1.})},roads=[],
           locations={name:dict(owner='A',market='m',population=1.,culture='test',religion='sunni') for name in names})
    return g,s


def test_wine_removal_uses_an_empty_seed_collection_and_removes_preemption():
    g,s=tiny_world();g.attrs['region'][1]='france_region'
    s['locations']['b']['religion']='catholic'
    baseline=StructuralRun(g,Timeline(g,[s],faith_groups={'catholic':'christian'}),CONFIG,SPEC,end_month=2)
    assert baseline.wine_background(1)==30
    assert baseline.preemption_load('coffee',1)>0
    cfg=deepcopy(CONFIG);cfg['disabled_rules']=['wine']
    removed=StructuralRun(g,Timeline(g,[s],faith_groups={'catholic':'christian'}),cfg,SPEC,end_month=2)
    assert all(removed.wine_background(v)==0 for v in range(g.n))
    assert removed.preemption_load('coffee',1)==0
    removed.run()
    assert all(removed.wine_background(v)==0 for v in range(g.n))


def test_constant_weighted_sources_remain_exactly_on_their_threshold():
    x=np.array([45.,45.,45.]);population=np.array([.1,.2,.3]);groups=np.array([0,0,0])
    mean,_=weighted_means(x,groups,population,1)
    assert mean[0]==45
    g,s=chain_world(3)
    for name,pop in zip(g.names,population):s['locations'][name]['population']=float(pop)
    r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1);sim=r.sims['coffee'];sim.x[:]=[45.]*3
    for _ in range(3):sim.refresh_aggregates()
    assert sim.shared_market[0]==45 and sim.shared_country[0]==45


def test_regional_unseeded_audit_uses_the_population_that_reached_the_milestone():
    from .acceptance import RunMetrics
    g,s=chain_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1)
    sim=r.sims['coffee'];sim.entries={0:0}
    values={good:np.zeros(9) for good in ('coffee','tea','tobacco')};values['coffee'][:5]=25
    target=dict(id='chain',good='coffee',where={'region':'chain'},threshold=20,target_year=1400,
                tolerance_months=120,grade='B',split='fit')
    def observe():
        means={good:np.array([float(np.average(x,weights=r.state.population))]) for good,x in values.items()}
        caps={good:np.array([x[0]]) for good,x in values.items()}
        metrics=RunMetrics(g,[target]);metrics.observe(4,r,(means,means,caps,values));return metrics
    metrics=observe()
    # A pure land chain, with one endpoint entry, reaches the population median
    # four hops away. The unattained half must not enter this classification.
    assert metrics.arrival_unseeded['chain']
    assert metrics.arrival_unseeded_evidence['chain']['downstream_share']==pytest.approx(3/5)
    assert not metrics.arrival_unseeded_evidence['chain']['old_all_population_test']
    r.state.population=np.array([49.,1,1,1,1,1,1,1,44])
    assert not observe().arrival_unseeded['chain']  # A planted capital still cannot dominate the score.


@pytest.mark.parametrize('name,good,node,value',[
    ('coffee_europe_before_1500','coffee',1,1),
    ('coffee_east_asia_before_1650','coffee',0,20),
    ('tea_stage3_france_region','tea',1,45),
    ('european_tea_without_contact','tea',1,.5),
    ('tobacco_outside_america_before_possession','tobacco',1,.5),
    ('muslim_wine_and_coffee','coffee',0,60)])
def test_each_historical_negative_constraint_can_detect_a_violation(name,good,node,value):
    g,s=tiny_world();g.attrs['subcontinent'][0]='east_asia';g.attrs['region'][1]='france_region'
    r=StructuralRun(g,Timeline(g,[s],kind='R',faith_groups={'sunni':'muslim'}),CONFIG,SPEC,end_month=1)
    r.sims[good].x[node]=value
    if name=='muslim_wine_and_coffee':r.wine_background=lambda v: 60. if v==0 else 0.  # synthetic invariant breach
    r.metrics.observe(0,r,r.diagnostics())
    assert name in r.metrics.violations


def test_tea_regional_cap_allows_a_local_hotspot_and_preserves_frances_late_cap():
    g,s=chain_world();g.attrs['region'][:]=['france_region']*9
    r=StructuralRun(g,Timeline(g,[s],kind='R'),CONFIG,SPEC,end_month=1)
    r.sims['tea'].x[0]=60;r.metrics.observe(0,r,r.diagnostics())
    assert 'tea_stage3_france_region' not in r.metrics.violations
    assert 'france_region' in r.metrics.tea_local_hotspots
    r.sims['tea'].x[:]=[60.]*9;r.metrics.observe((1810-1337)*12,r,r.diagnostics())
    assert 'tea_stage3_france_region' in r.metrics.violations


def test_actual_cross_boundary_land_contact_is_not_a_spontaneous_european_tea_seed():
    g,s=tiny_world();cfg=deepcopy(CONFIG)
    cfg['initial_customs']['tea']=[]
    r=StructuralRun(g,Timeline(g,[s],kind='R',faith_groups={'sunni':'muslim'}),cfg,SPEC,end_month=1)
    r.sims['tea'].open_wave();r.sims['tea'].inject(0,25,'event');r.run()
    assert r.sims['tea'].x[1]>0
    assert 'european_tea_without_contact' not in r.metrics.violations
    assert r.metrics.contact_evidence['tea']['type']=='adjacency'


def test_worlds_are_stepwise_and_have_an_observed_end():
    g,s=tiny_world();s2=deepcopy(s);s2["metadata"]["date"]="1340.1.1";s2["locations"]["b"]["owner"]="A"
    t=Timeline(g,[s,s2],faith_groups={"sunni":"muslim"})
    assert t.at(35)[0].owner.tolist()==[0,1,2]
    assert t.at(36)[0].owner.tolist()==[0,0,2]
    assert t.end==37


def test_observer_replay_includes_its_actual_first_month():
    g,s=tiny_world();s['metadata']['date']='1338.4.1'
    later=deepcopy(s);later['metadata']['date']='1339.1.1'
    r=StructuralRun(g,Timeline(g,[s,later]),CONFIG,SPEC,frames_every=12).run()
    for sim in r.sims.values():
        assert sim.frames[0][0]==15 and sim.frames[-1][0]==24
        assert sim.series[0]['month']==15


def test_delayed_observer_origin_keeps_its_source_duration_from_actual_activation():
    g,s=tiny_world();s['metadata']['date']='1440.1.1';s['countries']['A']['religion']='catholic'
    later=deepcopy(s);later['metadata']['date']='1500.1.1';later['countries']['A']['religion']='sunni'
    cfg=deepcopy(CONFIG);cfg['profiles']['coffee']['origin_where']={'region':'x'}
    r=StructuralRun(g,Timeline(g,[s,later],faith_groups={'sunni':'muslim','catholic':'christian'}),cfg,SPEC).run()
    sim=r.sims['coffee']
    assert sim.origin_month==(1500-1337)*12 and sim.x[0]>0


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
    config=deepcopy(CONFIG);config['profiles']['coffee']['habit_floor']=.5
    r=StructuralRun(g,t,config,SPEC,end_month=1);sim=r.sims['coffee']
    sim.x[:]=[80.,100.,0.];sim.S[1]=.02;sim.decaying[1]=True;sim.deadline[1]=240
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
    sim.ownership_rng=SimpleNamespace(random=lambda:0.)
    for _ in range(sim.n):sim.refresh_aggregates()
    sim.t=20;r.prepare_good(sim)
    assert sim.wave_start==20 and sim.x[1]>0
    assert any(e['type']=='ownership' for e in sim.nonlocal_log)


def test_merchant_source_theta_does_not_disable_an_existing_owned_habit():
    g,s=tiny_world();s['locations']['b']['owner']='A';s['countries']['A']['capital']='b'
    cfg=deepcopy(CONFIG);cfg['params']['theta']=45
    r=StructuralRun(g,Timeline(g,[s],kind='R'),cfg,SPEC,end_month=1);sim=r.sims['coffee']
    r.disabled_rules={'contact'};sim.x[0]=30;sim.shared_country_source[0]=0
    sim.ownership_rng=SimpleNamespace(random=lambda:0.)
    for _ in range(sim.n):sim.refresh_aggregates()
    r.prepare_good(sim)
    assert sim.spreading and sim.x[1]>0  # Actual stage2 ownership source, not the raw-material attribute.


def test_reverse_contact_remembers_which_country_supplies_the_residents():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    sim.x[0]=40;sim.shared_market[:]=[40,0,0]
    r.state.markets[1]['merchants']={0:.1};sim.contact_rng=SimpleNamespace(random=lambda:1.)
    r.prepare_good(sim,opening=True)
    assert not sim.spreading
    sim.x[2]=40;sim.shared_market[2]=40;r.state.markets[1]['merchants'][2]=.1
    r.prepare_good(sim)
    assert sim.spreading  # A different source country's residents create a genuinely new contact.


def test_a_late_contact_can_open_a_new_wave_without_extending_the_old_one():
    g,s=tiny_world();s['locations']['b']['owner']='A';s['countries']['A']['capital']='b'
    r=StructuralRun(g,Timeline(g,[s],kind='R'),CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    r.disabled_rules={'contact'};sim.x[0]=30;sim.shared_country_source[0]=0
    sim.ownership_rng=SimpleNamespace(random=lambda:0.)
    for _ in range(sim.n):sim.refresh_aggregates()
    sim.t=20;r.prepare_good(sim);end=sim.wave_end
    sim.t=21;r.prepare_good(sim);assert sim.wave_end==end
    sim.t=end;r.prepare_good(sim)
    assert sim.spreading and sim.wave_start==end and len(sim.waves)==2


def test_p3_creates_a_ban_shortens_hold_and_does_not_stack():
    g,s=tiny_world();cfg=deepcopy(CONFIG)
    cfg['events']=[e for e in cfg['events'] if e['id']=='historical_ban']
    cfg['fixed']['event_rate']=1
    r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),cfg,SPEC,events='historical',end_month=1)
    sim=r.sims['tobacco'];sim.x[:]=[70,0,0];sim.shared_country[0]=70
    sim.spreading=True;sim.wave_start=0;sim.deadline[0]=240;sim.finished[0]=False
    r.process_events(20)
    assert sim.deadline[0]==130 and sim.clock_joined(0)
    assert len(r.bans_this_month)==1 and r.event_log[0]['condition_valid']
    sim.t=21;sim._push(0);sim._serve(21);assert sim.deadline[0]==130
    r.effects[('tobacco',0)].append(dict(r.effects[('tobacco',0)][0]))
    assert r.multiplier('tobacco',0,21)==pytest.approx(.2)
    sim.t=130;sim._clocks(130)
    assert sim.decaying[0] and sim.S[0]==pytest.approx(.97)


def test_effect_activation_rejects_stale_aggregate_and_respects_budget():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),CONFIG,SPEC,end_month=1)
    event=next(e for e in CONFIG['events'] if e['id']=='historical_ban')
    sim=r.sims['tobacco'];sim.shared_country[0]=70;sim.x[:]=[0,0,0]
    assert not r.live_event_probe(event,'tobacco',0)
    sim.x[0]=70
    r.month_base_U={g:s.U for g,s in r.sims.items()}
    sim.U+=CONFIG['fixed']['budget']
    assert not r.live_event_probe(event,'tobacco',0)


def test_fixed_affinity_and_preemption_affect_retention_and_contact():
    g,s=tiny_world();cfg=deepcopy(CONFIG)
    cfg['params'].update(p=.003,rho=.995,lambda_contact=3,preemption=.08)
    s['markets']['0']['merchants']={'B':1.}
    r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),cfg,SPEC,end_month=1)
    sim=r.sims['coffee'];r.sims['tea'].shared_country[1]=50
    p,retention,_=sim.local_terms(1,.003,.995)
    assert p==pytest.approx(.006/3.4) and retention==pytest.approx(.995*.976)
    sim.x[0]=30;sim.shared_market[0]=20
    sim.contact_rng=SimpleNamespace(random=lambda:.15)
    r.prepare_good(sim);assert sim.x[1]==0
    r.disabled_rules={'preemption'}
    p,retention,_=sim.local_terms(1,.003,.995)
    assert p==pytest.approx(.006) and retention==pytest.approx(.995)
    r.prepare_good(sim);assert sim.x[1]==7


def test_event_gap_excludes_templates_that_already_fired():
    g,s=tiny_world();cfg=deepcopy(CONFIG)
    cfg['events']=[e for e in cfg['events'] if e['id']=='envoy_gift'];cfg['fixed']['event_rate']=0
    r=StructuralRun(g,Timeline(g,[s]),cfg,SPEC,events='generic',end_month=1)
    sim=r.sims['coffee'];sim.x[0]=5;sim.shared_country[0]=5;sim.spreading=True;sim.wave_start=0
    r.process_events(1);assert r.eligible_months[-1][1]['coffee'] is True
    r.event_done.add(('envoy_gift','coffee',0))
    r.process_events(2);assert r.eligible_months[-1][1]['coffee'] is False


def test_custom_flavor_uses_the_event_budget_without_waking_propagation():
    g,s=tiny_world();cfg=deepcopy(CONFIG)
    cfg['events']=[dict(id='custom_flavor',pool='generic',kind='flavor',condition='local_stage2',effect='flavor',goods=['tobacco'])]
    cfg['fixed']['event_rate']=10
    r=StructuralRun(g,Timeline(g,[s]),cfg,SPEC,events='generic',end_month=1)
    sim=r.sims['tobacco'];before=list(sim.x);r.process_events(1)
    assert len(r.event_log)==1 and r.event_log[0]['phase']=='customs'
    assert not sim.spreading and sim.waves==[] and sim.x==before


def test_market_support_cannot_broadcast_new_members_into_cold_locations():
    g,s=tiny_world();cfg=deepcopy(CONFIG);cfg['params'].update(delta=.001,p=.02,rho=.99,internal_rate=.002)
    r=StructuralRun(g,Timeline(g,[s]),cfg,SPEC,end_month=1)
    sim=r.sims['coffee'];sim.shared_market[:]=100;sim.spreading=True
    sim._push(0);sim._serve(0);assert sim.x[0]==0
    sim.x[0]=1;sim.direct_kind='opening';sim._note(0,1,0);sim.direct_kind=None
    sim._push(0)
    for month in range(200):
        sim.t=month
        for _ in range(sim.length):sim._serve(month)
    assert sim.arrival[1]>=0 and sim.arrival_kind[1]=='adjacency'
    assert sim.arrival[2]>=0 and sim.arrival_kind[2]=='adjacency'
    assert set(sim.entries)=={0}


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
                        goods=['coffee'],condition='local_stage2',effect='flavor') for i in range(9)]
    r=StructuralRun(g,Timeline(g,[s],faith_groups={'sunni':'muslim'}),cfg,SPEC,events='mixed',end_month=1)
    r.sims['coffee'].spreading=True;r.sims['coffee'].wave_start=0;r.sims['coffee'].shared_country[0]=30
    r.sims['coffee'].x[0]=30
    r.event_candidates=lambda event,good,countries=None:[(0,0,True)]
    for month in range(1000):
        r.event_done.clear();r.process_events(month)
    historical=sum(e['pool']=='historical' for e in r.event_log)
    assert len(r.event_log)==1000 and .55<historical/1000<.65
    assert event_weight({'kind':'spread'},20,front=True,weights=CONFIG['event_weights'])==2.25
    assert event_weight({'kind':'impact'},45,blocked=True,weights=CONFIG['event_weights'])==3.6


@pytest.mark.parametrize('values',[{'p':True},{'p':float('nan')},{'theta':0},{'hold_T':1.5},
                                   {'lambda_contact':301},{'unknown':1},{'habit_floor':-1}])
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


def test_observer_relationships_are_bidirectional_and_part_of_the_world_hash(tmp_path):
    import hashlib
    from tools.eu5_save_parser.world_export import atomic_json,digest
    g,s=tiny_world();s['format']='obsession.world-snapshot/2';s['source']={'sha256':'a'*64}
    snapshot=tmp_path/'world.json';atomic_json(snapshot,s)
    relation_path=tmp_path/'relations.json'
    def build(other):
        atomic_json(relation_path,{'format':'obsession.world-relations/1','date':s['metadata']['date'],
            'playthrough_id':'test','source_sha256':'a'*64,'world_snapshot_sha256':digest(snapshot),'complete':True,
            'relations':[{'kind':'marriage','first':'A','second':other}]})
        entry={'file':snapshot.name,'date':s['metadata']['date'],'sha256':digest(snapshot),
               'relations_file':relation_path.name,'relations_sha256':digest(relation_path),'relations_complete':True}
        path=tmp_path/'timeline.json';atomic_json(path,{'format':'obsession.world-timeline/1','id':'test','snapshots':[entry]})
        _,sequence=read_timeline(path,lazy=True)
        return Timeline(g,sequence)
    first=build('B');state,_=first.at(0)
    assert {(r['actor'],r['other']) for r in state.links}=={(0,1),(1,0)}
    second=build('C')
    assert first.hash!=second.hash


def test_future_observer_snapshots_cannot_change_an_already_observed_prefix():
    g,s=tiny_world();common=deepcopy(s);common['metadata']['date']='1350.1.1'
    future=deepcopy(common);future['metadata']['date']='1400.1.1'
    future['countries']['A1']={'tag':'NEW','capital':'a'}
    future['markets']['0a']={'center':'a','merchants':{'A1':1.}}
    future['locations']['a'].update(owner='A1',market='0a')
    s['markets']['0']['merchants']={'A':.5,'B':.25,'C':.25}
    common['markets']['0']['merchants']=deepcopy(s['markets']['0']['merchants'])
    cfg=deepcopy(CONFIG);cfg['initial_customs']['coffee']=[{'where':{'region':'x'},'value':30}]
    cfg['fixed']['event_rate']=1
    def run(snapshots):
        return StructuralRun(g,Timeline(g,snapshots,faith_groups={'sunni':'muslim'}),cfg,SPEC,
                             events='generic',seed=3,end_month=120).run()
    first=run([s,common]);second=run([s,common,future])
    assert first.ledger==second.ledger
    for good in first.sims:assert first.sims[good].x==second.sims[good].x
    def canonical_events(run):
        return [{**e,'country':run.timeline.country_names[e['country']]} for e in run.event_log]
    assert canonical_events(first)==canonical_events(second)


def test_first_membership_fact_ancestry_does_not_become_model_state():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    sim.open_wave()
    sim.inject(0,25,'contact',{'market':0,'resident':0,'facts':['residency_A']})
    sim.inject(1,2,'ownership',{'node':0,'facts':['ownership_B']})
    assert sim.fact_ancestry[0]=={'residency_A'}
    assert sim.fact_ancestry[1]=={'residency_A','ownership_B'}
    assert sim.direct_evidence==set() and sim.direct_kind is None


def test_ownership_return_keeps_the_world_fact_source_label():
    g,s=tiny_world()
    fact=dict(id='conquest',kind='ownership',actor_location='b',location='a',start=1340,end=1400,
              grade='W-A',source='synthetic fixture',goods=['coffee','tea','tobacco'],fact='fixture')
    r=StructuralRun(g,Timeline(g,[s],kind='R',facts=[fact]),CONFIG,SPEC,end_month=1)
    r.state,_=r.timeline.at(36);r.apply_state();r.disabled_rules={'contact'}
    sim=r.sims['coffee'];c=int(r.state.owner[0]);sim.x[0]=30;sim.shared_country_source[c]=0;sim.t=36
    sim.ownership_rng=SimpleNamespace(random=lambda:0.)
    for _ in range(sim.n):sim.refresh_aggregates()
    r.prepare_good(sim)
    # Default dose .5 is below membership, but the input audit still names it.
    assert sim.nonlocal_log[-1]['source']['facts']==['conquest']


def test_budget_admits_country_renewal_and_slices_queue_cleanup():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    sim.x[0]=100;sim.decaying[0]=True;sim.S[0]=.2;sim.open_wave()
    assert sim.serve_shared_tasks(8)==0 and sim.renew_cursor==0
    assert sim.serve_shared_tasks(200)<=200 and sim.renew_cursor==sim.ng
    sim.spreading=False;sim.cleanup_pending=True
    before=sim.length;assert sim.serve_shared_tasks(3)==3 and sim.length==before-1
    assert sum(q!=-1 for q in sim.q)==sim.length


def test_entry_clock_starts_before_queue_service_and_survives_wave_renewal():
    g,s=tiny_world();r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1);sim=r.sims['coffee']
    sim.t=20;sim.open_wave();sim.inject(0,7,'event',{'event':'fixture'})
    assert sim.deadline[0]==1460
    sim.t=21;sim.serve_shared_tasks(1000)
    assert sim.deadline[0]==1460


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
    experiment.graph_hash='a'*64;experiment.code_snapshot=tmp_path/'source.json'
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


def test_runtime_source_bundle_preserves_the_exact_hashed_bytes():
    import hashlib
    from .experiment import code_bundle,code_hash
    bundle=code_bundle()
    assert bundle['runtime_hash']==code_hash()
    assert 'tools/obsession_sim/metrics.py' in bundle['files']
    assert 'tools/obsession_sim/eu5_map.py' in bundle['files']
    for source in bundle['files'].values():
        assert hashlib.sha256(source['source'].encode('utf-8')).hexdigest()==source['sha256']


def test_cache_binds_the_actual_graph_even_when_the_world_state_is_identical(tmp_path):
    import hashlib
    from .experiment import Experiment
    from .graph import save_json
    g,s=tiny_world();s['format']='obsession.world-snapshot/2'
    snapshot=tmp_path/'world.json';snapshot.write_text(json.dumps(s),encoding='utf-8')
    manifest=tmp_path/'timeline.json';manifest.write_text(json.dumps(dict(format='obsession.world-timeline/1',id='test',
        snapshots=[dict(file=snapshot.name,date=s['metadata']['date'],sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())])),encoding='utf-8')
    reference=tmp_path/'reference';setup=reference/'main_menu/setup/1337';setup.mkdir(parents=True)
    (setup/'10_countries.txt').write_text('countries = { countries = { A = { capital = a } B = { capital = b } C = { capital = c } } }')
    (setup/'06_pops.txt').write_text('locations = { a = { define_pop = { size = 1 } } b = { define_pop = { size = 1 } } c = { define_pop = { size = 1 } } }')
    (setup/'09_roads.txt').write_text('road_network = { }')
    graph_path=tmp_path/'graph.json';save_json(g,graph_path)
    def run():
        experiment=Experiment(graph_path,[manifest],reference,tmp_path/'results')
        experiment.targets=[];experiment.facts=[]  # This integration fixture has no historical regions.
        return experiment.one('R','S',0,end_year=1337.1)
    first=run()
    archive=next((tmp_path/'results/inputs/code').glob('*.json'))
    archived_mtime=archive.stat().st_mtime_ns
    g.incoming=[(),(),()];g.outgoing=[(),(),()];save_json(g,graph_path)
    second=run()
    assert archive.stat().st_mtime_ns==archived_mtime  # Workers must not replace an immutable shared archive.
    assert first['world_hash']==second['world_hash']
    assert first['graph_hash']!=second['graph_hash'] and first['cache_file']!=second['cache_file']
    archive.write_text('{}')
    with pytest.raises(ValueError,match='source archive'):
        run()
