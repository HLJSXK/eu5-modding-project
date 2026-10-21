"""Handoff 23 regressions, using synthetic states and no held-out outcomes."""
from copy import deepcopy
import math
from types import SimpleNamespace

import numpy as np
import pytest

from .acceptance import aggregate_runs, event_diagnostics, order_correct
from .structural import FIT_PARAMS, StructuralRun, validate_fit_params
from .test_structural import CONFIG, SPEC, KFixture, tiny_world
from .worlds import Timeline, foreign_merchants


def test_j1_missing_is_infinity_but_both_missing_is_wrong():
    assert order_correct(20, None)
    assert order_correct(20, 20)
    assert not order_correct(None, None)
    assert not order_correct(None, 20)
    assert not order_correct(21, 20)


def test_j3_k1_excludes_territorial_merchants():
    f = KFixture()
    f.state.owner[2], f.state.market[2] = 1, 0
    f.mx["coffee"][0] = 30
    f.obs(1)
    assert not f.status("K1")["cases"]


def test_j4_k5_excludes_market_and_adjacency():
    f = KFixture()
    f.obs(1, inputs=[dict(good="tobacco", country=1, type="market"),
                     dict(good="tobacco", country=2, type="adjacency")])
    assert not f.status("K5")["cases"]
    f.obs(2, inputs=[dict(good="tobacco", country=1, type="ownership")])
    assert f.status("K5")["cases"][0]["t0"] == 2


def test_j5_k4_confounds_only_the_same_good():
    f = KFixture()
    f.raw["tea"] = {1}
    f.obs(1)
    f.obs(2, inputs=[dict(good="coffee", country=1, type="contact")])
    f.obs(1201)
    assert f.status("K4")["status"] == "pass"


@pytest.mark.parametrize("kid,period", [("K2", 90*12), ("K6", 20*12)])
def test_j6_observer_nonoccurrence_window_is_shortened(kid, period):
    f = KFixture(kind="O")
    if kid == "K2":
        f.cx["coffee"][1] = 30
        f.obs(1)
    else:
        f.cx["tobacco"][1] = 30
        f.obs(1, bans=[dict(good="tobacco", country=1)])
    f.obs(period + 1)
    assert f.status(kid)["status"] == "pass"


def test_j9_event_gaps_are_per_good_and_absent_is_unknown():
    months = [(m, dict(coffee=True, tea=True, tobacco=False)) for m in range(25)]
    events = [dict(id="a", good="coffee", country=0, month=m, pool="generic", kind="spread", linked=True)
              for m in range(25)]
    result = event_diagnostics(events, months)
    assert result["E_gap_by_good"]["coffee"] == 0
    assert result["E_gap_by_good"]["tea"] == 25/12
    assert result["E_gap_by_good"]["tobacco"] is None
    assert event_diagnostics([], []) ["E_gap"] is None


def ownership_fixture(population):
    g, s = tiny_world()
    s["locations"]["a"]["owner"] = "B"
    s["locations"]["a"]["population"] = population
    s["locations"]["b"]["population"] = 100 - population
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1)
    r.disabled_rules = {"contact"}
    sim = r.sims["coffee"]
    sim.x[0] = 30
    for _ in range(sim.n):
        sim.refresh_aggregates()
    sim.ownership_rng = SimpleNamespace(random=lambda: 0.)
    r.prepare_good(sim)
    return r, sim


def test_ownership_probability_scales_with_population_and_excludes_capital_market():
    _, small = ownership_fixture(1)
    _, large = ownership_fixture(70)
    assert small.nonlocal_log[-1]["source"]["population_share"] == .01
    assert large.nonlocal_log[-1]["source"]["population_share"] == .7
    assert small.x[1] == large.x[1] == 7
    r, sim = ownership_fixture(70)
    r.state.market[0] = r.state.market[1]
    sim.x[1] = 0
    sim.nonlocal_log.clear()
    for _ in range(sim.n): sim.refresh_aggregates()
    r.prepare_good(sim)
    assert not sim.nonlocal_log


def test_reverse_contact_cannot_contact_itself_or_territorial_residents():
    g, s = tiny_world()
    s["locations"]["b"]["owner"] = "A"
    s["markets"]["1"]["merchants"] = {"A": .7, "C": .3}
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1)
    sim = r.sims["coffee"]
    sim.x[0] = 60
    sim.shared_market[:] = [60, 0, 0]
    sim.contact_rng = SimpleNamespace(random=lambda: 0.)
    r.disabled_rules = {"ownership"}
    r.prepare_good(sim)
    assert not sim.nonlocal_log
    assert 0 not in foreign_merchants(r.state, 1)


def test_tobacco_contact_has_no_continent_gate():
    g, s = tiny_world()
    s["markets"]["2"]["merchants"] = {"B": .1}
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1)
    sim = r.sims["tobacco"]
    sim.shared_market[2] = 30
    sim.seen_pairs.clear()
    sim.contact_rng = SimpleNamespace(random=lambda: 0.)
    r.prepare_good(sim)
    assert sim.x[1] == 7


def test_no_roads_or_straits_have_additional_weight_and_wine_is_constant():
    g, s = tiny_world()
    s["roads"] = [["a", "b", "railroad"]]
    g.meta["special_edges"] = [dict(a=1, b=2, type="strait")]
    cfg = deepcopy(CONFIG)
    cfg["initial_customs"]["wine"] = [dict(where={"region":"x"}, value=30)]
    r = StructuralRun(g, Timeline(g, [s]), cfg, SPEC, end_month=500).run()
    assert all(sim.w is None for sim in r.sims.values())
    wine = r.context_goods["wine"]
    assert wine.x == [30, 0, 0] and not wine.clock and wine.join == [-1]*wine.ng


def test_only_six_historical_parameters_are_exposed():
    assert set(CONFIG["params"]) == set(FIT_PARAMS)
    for key in ("hold_T", "habit_floor", "affinity_strength", "road_scale", "theta"):
        with pytest.raises(ValueError): validate_fit_params({key:1})


def test_j10_coffee_origin_is_first_country_at_stage2():
    g, s = tiny_world()
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1)
    sim = r.sims["coffee"]
    sim.open_wave()
    r.diagnostics()
    assert sim.origin_groups is None
    sim.x[0] = 25
    r.diagnostics()
    assert sim.origin_groups == {0} and sim.external_stage2 is None
    sim.x[1] = 25
    r.diagnostics()
    assert sim.external_stage2 is not None


def test_j12_budget_rejected_event_is_counted():
    g, s = tiny_world()
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1)
    sim = r.sims["tobacco"]
    sim.x[0] = 70
    r.month_base_U = {g:s.U for g,s in {**r.sims, **r.context_goods}.items()}
    sim.U += CONFIG["fixed"]["budget"]
    event = next(e for e in CONFIG["events"] if e["id"] == "historical_ban")
    assert not r.live_event_probe(event, "tobacco", 0)
    assert r.events_abandoned_budget == 1


def test_new_world_fact_kinds_lifetimes_and_country_keys():
    g, s = tiny_world()
    def fact(key, kind, **values):
        return dict(id=key, kind=kind, fact="Synthetic world fixture", start=1340, end=1360,
                    grade="W-A", source="synthetic", goods="all", **values)
    facts = [fact("land", "ownership_region", actor_country="F_TEST", where={"region":["y", "z"]},
                  previous_owner_tags=["B", "C"]),
             fact("new", "formation", country=dict(key="F_TEST", name="New country", capital="c", culture="test", religion="sunni")),
             fact("capital", "capital", actor_country="F_TEST", new_capital="b"),
             fact("faith", "state_religion", actor_country="F_TEST", religion="catholic"),
             fact("marriage", "marriage", actor_country="F_TEST", other_tag="A"),
             fact("network", "diplomacy_network", members=[dict(actor_tag="A"), dict(actor_country="F_TEST")])]
    timeline = Timeline(g, [s], kind="R", facts=facts)
    state, _ = timeline.at(36)
    c = timeline.country_index["F_TEST"]
    assert state.owner[1:].tolist() == [c, c]
    assert state.capitals[c] == 1 and state.countries["F_TEST"]["religion"] == "catholic"
    assert sum(link["kind"] == "marriage" for link in state.links) == 2
    assert sum(link["kind"] == "diplomacy" for link in state.links) == 2
    assert state.fact_effects["land"] == 2
    ended, _ = timeline.at((1360-1337)*12)
    assert "F_TEST" not in ended.countries and c not in ended.capitals
    assert ended.owner.tolist() == [timeline.country_index[n] for n in "ABC"]


def test_empty_world_selectors_fail_instead_of_silently_disappearing():
    g, s = tiny_world()
    row = dict(id="empty", kind="ownership_region", actor_tag="A", where=dict(region="missing"),
               start=1340, end=1400, grade="W-A", source="synthetic", goods="all", fact="Synthetic")
    with pytest.raises(ValueError, match="zero locations"):
        Timeline(g, [s], kind="R", facts=[row])


def test_r_residency_uses_only_facts_at_the_measured_share_without_renormalizing():
    g, s = tiny_world()
    s["markets"]["0"]["merchants"] = {"A": .9, "B": .1}
    row = dict(id="resident", kind="residency", actor_tag="B", location="a", start=1340, end=1400,
               grade="W-A", source="synthetic", goods="all", fact="Synthetic")
    timeline = Timeline(g, [s], kind="R", facts=[row], residency_power=.00066)
    first, _ = timeline.at(0)
    assert not first.markets[0]["merchants"]
    state, _ = timeline.at(36)
    assert state.markets[0]["merchants"] == {timeline.country_index["B"]:.00066}
    observer, _ = Timeline(g, [s]).at(0)
    assert foreign_merchants(observer, 0) == {1:.1}


def test_j8_burst_is_counted_before_the_runtime_cap():
    g, s = tiny_world()
    cfg = deepcopy(CONFIG)
    cfg["events"] = [dict(id="flavor", pool="generic", kind="flavor", condition="local_stage2", effect="flavor", goods=["coffee"])]
    cfg["fixed"].update(event_rate=100, event_cap_per_month=1)
    r = StructuralRun(g, Timeline(g, [s]), cfg, SPEC, events="generic", end_month=1)
    sim = r.sims["coffee"]
    sim.x[:] = [25,25,25]
    sim.shared_country[:] = 25
    r.process_events(1)
    assert len(r.event_log) == 1
    assert event_diagnostics(r.event_log, r.eligible_months, r.candidate_bursts)["B_max"] == 3


def test_j7_religious_event_reads_leader_status_and_live_state():
    g, s = tiny_world()
    for rec in s["countries"].values(): rec["religion"] = "catholic"
    s["countries"]["B"]["religious_leader_for"] = ["catholic"]
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1)
    sim = r.sims["coffee"]
    sim.shared_country[0] = 30
    event = next(e for e in CONFIG["events"] if e["id"] == "religious_legitimation")
    assert [c for c, _, _ in r.event_candidates(event, "coffee")] == [1]
    assert not r.live_event_probe(event, "coffee", 1)
    sim.x[0] = 30
    assert r.live_event_probe(event, "coffee", 1)


def test_successor_binds_predecessor_before_expiry_independently_of_query_order():
    g, s = tiny_world()
    def f(key, actor, start, end, **kw):
        return dict(id=key, kind="ownership", actor_tag=actor, location="a", start=start, end=end,
                    fact="Synthetic transfer", grade="W-A", source="synthetic", goods="all", **kw)
    facts = [f("first", "B", 1340, 1350), f("successor", "C", 1350, 1400, previous_owner_tags=["B"])]
    one = Timeline(g, [s], kind="R", facts=facts)
    one.at(36)
    end, _ = one.at((1351-1337)*12)
    two = Timeline(g, [s], kind="R", facts=facts)
    direct, _ = two.at((1351-1337)*12)
    assert direct.owner.tolist() == end.owner.tolist() == [2,1,2]
    assert one.bound_fact_nodes["successor"].tolist() == [0]


def test_holdout_values_are_removed_before_writing_playback():
    from .export import mask_holdout_playback
    payload = dict(arrival=[1,50], first_positive=[0,40], arrival_kind=["contact", "adjacency"],
        threshold_arrival={"20":[2,60]}, frames=[dict(month=100, stages="dg")],
        clock=dict(join=[5]), structural=dict(sources=[dict(node=1, month=40)], events=[dict(node=1)]))
    mask_holdout_playback(payload, [1])
    assert payload["arrival"] == [1,-1]
    assert payload["first_positive"] == [0,-1]
    assert payload["arrival_kind"] == ["contact",None]
    assert payload["threshold_arrival"]["20"] == [2,-1]
    assert payload["frames"][0]["stages"] == "da"
    assert "clock" not in payload and payload["structural"]["sources"] == payload["structural"]["events"] == []


def test_j11_wc_ancestry_never_removes_a_target_from_the_scoring_denominator():
    from .acceptance import RunMetrics
    g, s = tiny_world()
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1).run()
    target = dict(id="fit", good="coffee", where=dict(region="x"), threshold=20,
                  target_year=1337, tolerance_months=120, grade="B", split="fit")
    r.metrics = RunMetrics(g, [target])
    r.timeline.facts = [dict(id="wc", grade="W-C")]
    r.sims['coffee'].fact_ancestry[0] = {'wc'}
    r.sims['coffee'].x[0] = 25
    r.metrics.observe(0, r, r.diagnostics())
    result = r.metrics.report(r)
    assert result['milestones'][0]['world_evidence']['counts']['W-C'] == 1
    assert result['milestones'][0]['scored'] and result['fit_within_tol'] == 1


def test_j12_budget_diagnostics_are_preserved_in_aggregation():
    g, s = tiny_world()
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1).run()
    r.events_abandoned_budget = 4
    r.sims['coffee'].peak_round_delay = 8
    result = aggregate_runs([r.metrics.report(r), r.metrics.report(r)])
    assert result['peak_round_delay_months'] == 8
    assert result['events_abandoned_budget'] == 8


def test_past_possession_is_remembered_by_diagnostics_after_a_colony_is_lost():
    g, s = tiny_world()
    s['locations']['c']['owner'] = 'A'
    r = StructuralRun(g, Timeline(g, [s], kind='R'), CONFIG, SPEC, end_month=1).run()
    assert r.tobacco_possession_seen
    r.state.owner[2] = 2
    r.sims['tobacco'].x[1] = 2
    r.metrics.observe(100, r, r.diagnostics())
    assert 'tobacco_outside_america_before_possession' not in r.metrics.violations


def test_metadata_updates_preserve_aggregate_progress_and_nonvisual_runs_omit_world_frames():
    g, s = tiny_world()
    r = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1)
    sim = r.sims['coffee']
    sim.x[0] = 30
    sim.refresh_aggregates()
    cursor, weights = sim.aggregate_cursor, sim._aggregate_weights[0].copy()
    r.state.links = [dict(kind='marriage',actor=0,other=1,fact_id='synthetic',good=None)]
    r.apply_state()
    assert sim.aggregate_cursor == cursor
    assert np.array_equal(sim._aggregate_weights[0],weights)
    assert r.country_links[0][0]['kind'] == 'marriage'
    assert r.world_log == []
    replay = StructuralRun(g, Timeline(g, [s]), CONFIG, SPEC, end_month=1, frames_every=1)
    assert len(replay.world_log) == 1


@pytest.mark.parametrize('channel',['contact','ownership'])
def test_initial_eligible_channels_receive_their_annual_trials(channel):
    g,s = tiny_world()
    cfg=deepcopy(CONFIG)
    cfg['initial_customs']['tea']=[dict(where=dict(region='x'),value=25)]
    if channel=='contact':
        s['markets']['0']['merchants']={'B':.1}
    else:
        s['locations']['a']['owner']='B'
    r=StructuralRun(g,Timeline(g,[s]),cfg,SPEC,end_month=1)
    sim=r.sims['tea']
    assert sim.wave_start is None and not sim.contact_started
    sim.contact_rng=sim.ownership_rng=SimpleNamespace(random=lambda:0.)
    sim.t=1
    r.prepare_good(sim)
    assert sim.x[1]==7 and any(row['type']==channel for row in sim.nonlocal_log)


def test_zero_population_hot_territory_cannot_activate_ownership_return():
    g,s=tiny_world()
    s['locations']['a'].update(owner='B',population=0)
    r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1)
    sim=r.sims['coffee'];sim.x[0]=30
    for _ in range(sim.n):sim.refresh_aggregates()
    sim.ownership_rng=SimpleNamespace(random=lambda:0.)
    r.disabled_rules={'contact'}
    r.prepare_good(sim)
    assert sim.owned_hot_population[1]==0 and not sim.spreading and not sim.nonlocal_log


def test_vector_aggregation_matches_effective_population_and_first_maximum_definitions():
    from .test_structural import chain_world
    from .worlds import weighted_means
    g,s=chain_world(9)
    for i,name in enumerate(g.names):
        s['locations'][name]['market']='m' if i<2 else 'other'
        s['locations'][name]['population']=i/10
    s['markets']['other']=dict(center='n2',merchants={'A':1})
    r=StructuralRun(g,Timeline(g,[s]),CONFIG,SPEC,end_month=1)
    sim=r.sims['coffee'];sim.x[:]=[1,.5,40,40,50,20,10,0,2]
    sim.decaying[0]=True;sim.S[0]=.8
    values=np.array([sim.eff(v) for v in range(sim.n)])
    assert sim.effective_values(0,sim.n)==pytest.approx(values)
    sim.reset_aggregation()
    for _ in range(sim.n):sim.refresh_aggregates()
    expected,_=weighted_means(values,r.state.owner,r.state.population,sim.ng)
    assert sim.shared_country==pytest.approx(expected)
    assert sim.shared_country_source[0]==int(np.argmax(values))
    assert sim.shared_front[0] == bool(np.any((values>0)&(values<1)))
    mask=(r.state.market!=r.state.market[0])&(values>=20)&(r.state.population>0)
    assert sim.owned_hot_population[0]==pytest.approx(r.state.population[mask].sum())
