"""Three-layer diffusion on dynamic worlds, using the original FIFO/x core.

The rule controller holds only good/country/market state. Monthly diagnostic
scans, parent labels and K cases are explicitly separate from simulated state.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
import math
import random

import numpy as np

from .core import Params, Simulation
from .graph import MapGraph
from .worlds import canonical_hash, weighted_means
from .conditional import ConditionalEvaluator
from .acceptance import RunMetrics

GOODS = ("coffee", "tea", "tobacco")
PARAM_LIMITS = {"rho":(0,1),"p":(0,1),"delta":(0,100),"hold_T":(0,12000),
                "decay_factor":(0,1),"habit_floor":(0,1),"theta":(.001,100),
                "lambda_contact":(0,10),"contact_amount":(0,100),"preemption":(0,10),
                "internal_rate":(0,1),"road_scale":(0,10)}


def validate_params(values):
    for name,value in values.items():
        if (name not in PARAM_LIMITS or isinstance(value,bool) or not isinstance(value,(int,float))
                or not math.isfinite(value) or not PARAM_LIMITS[name][0]<=value<=PARAM_LIMITS[name][1]
                or (name=="hold_T" and int(value)!=value)):
            raise ValueError("invalid shared parameter: "+name)
    return {k:int(v) if k=="hold_T" else v for k,v in values.items()}


def event_weight(event, intensity, front=False, blocked=False):
    """Stage/kind weights depend only on current state, never geography/date."""
    if event["kind"] == "spread":
        return (1.5 if front else 1.)*(1.5 if intensity < 45 else .7)
    if event["kind"] == "impact":
        return (1.8 if intensity >= 45 else .5)*(2. if blocked else 1.)
    return 1.


def simulation_graph(graph):
    """Copy mutable containers, share immutable geography/raster evidence.

    Structural runs never edit adjacency tuples, coordinates, names or static
    attribute columns. Dynamic columns and road weights are replaced outright.
    """
    return MapGraph(incoming=list(graph.incoming),outgoing=list(graph.outgoing),
                    in_weight=list(graph.in_weight) if graph.in_weight is not None else None,
                    owner=list(graph.owner) if graph.owner is not None else None,
                    group_names=list(graph.group_names) if graph.group_names else None,
                    names=graph.names,coords=graph.coords,attrs=dict(graph.attrs),meta=dict(graph.meta))


def opening_values(good,graph,state,config):
    values={}
    for row in config.get("initial_customs",{}).get(good,()):
        columns={**graph.attrs,"religion_group":state.religion_group,"culture":state.culture,"religion":state.religion,
                 "raw_material":state.raw_material}
        for key in row["where"]:
            if key not in columns:
                raise ValueError("unknown opening-custom attribute: "+key)
        for v in range(graph.n):
            if all(columns[key][v] in (val if isinstance(val,list) else [val]) for key,val in row["where"].items()):
                values[v]=max(values.get(v,0.),float(row["value"]))
    return list(values.items())


class RuleSimulation(Simulation):
    def __init__(self, graph, params, good, controller):
        self.good, self.controller = good, controller
        self.arrival_kind = [None] * graph.n
        self.direct_kind = "opening"
        self.nonlocal_log = []
        self.arrivals_this_month = []
        self.internal_logged = set()
        self.land_speeds = []
        self.task_terms = None
        # First-membership ancestry is diagnostic only; never read by rules.
        self.fact_ancestry = {}
        self.market_evidence, self.country_evidence = defaultdict(set), defaultdict(set)
        self.direct_evidence = set()
        self.distance_signature = None
        self.distance_cache = None
        super().__init__(graph, params)
        self.direct_kind = None
        # All countries in the timeline have stable slots, including unborn ones.
        extra = len(controller.timeline.country_names) - self.ng
        for name, default in (("join", -1), ("decay_start", -1), ("finished_month", -1), ("S", 1.),
                              ("decaying", False), ("finished", False), ("habit", params.habit_floor)):
            getattr(self, name).extend([default] * extra)
        self.members_of.extend([[] for _ in range(extra)])
        self.ng += extra
        self.entries = {v: 0 for v, t in enumerate(self.arrival) if t >= 0}
        self.wave_start = None
        self.first_wave_start = None
        self.spreading = False
        self.wave_end = None
        self.renew_cursor = self.ng
        self.wake_cursor = self.n
        self.cleanup_pending = False
        self.waves = []
        self.seen_pairs = set()
        self.seen_ownership = set()
        self.source_market = None
        self.origin_node = None
        self.origin_month = round((controller.origin_year - 1337) * 12)
        self.contact_rng = random.Random(canonical_hash([controller.seed, good, "contact"]))
        self.origin_rng = random.Random(canonical_hash([controller.seed, good, "origin"]))
        self.origin_groups = None
        self.external_stage2 = None
        self.shared_country = np.zeros(self.ng)
        self.shared_market = np.zeros(len(controller.timeline.market_names))
        self._aggregate_sums = [np.zeros(self.ng), np.zeros(len(self.shared_market))]
        self._aggregate_weights = [np.zeros(self.ng), np.zeros(len(self.shared_market))]
        self.shared_country_source = [-1]*self.ng
        self.shared_front = [False]*self.ng
        self._front_work = [False]*self.ng
        self._source_work = [-1]*self.ng
        self._max_work = [0.]*self.ng
        self.country_wake_until = [-1]*self.ng
        self.market_wake_until = [-1]*len(self.shared_market)
        self.aggregate_cursor = 0

    def _note(self, v, y, t):
        was = self.arrival[v] if hasattr(self, "arrival") else -1
        super()._note(v, y, t)
        if was < 0 and y >= 1:
            kind = self.direct_kind
            if kind is None:
                ctl = self.controller
                p, internal = self.task_terms[1:] if self.task_terms and self.task_terms[0] == v else (self.pp[v],0.)
                adj = sum(p * w * self.eff(u) for u, w in zip(
                    self.g.incoming[v], self.w[v] if self.w else [1.] * len(self.g.incoming[v])))
                parts = {"adjacency": adj, "origin": self.sources.get(v, 0.),
                         "market": internal}
                kind = max(parts, key=parts.get)
            self.arrival_kind[v] = kind
            evidence=set(self.direct_evidence)
            if kind == "adjacency":
                evidence.update(self.fact_ancestry.get(self.arrival_parent[v],()))
            elif kind == "market" and hasattr(self,"shared_market"):
                evidence.update(self.market_evidence[int(self.controller.state.market[v])])
            self.fact_ancestry[v]=frozenset(evidence)
            state=self.controller.state
            self.market_evidence[int(state.market[v])].update(evidence)
            self.country_evidence[int(state.owner[v])].update(evidence)
            self.arrivals_this_month.append(v)
            if kind != "adjacency" and hasattr(self, "entries"):
                self.entries.setdefault(v, t)

    def local_terms(self, v, p, retention):
        ctl, state = self.controller, self.controller.state
        cfg, profile = ctl.config["params"], ctl.config["profiles"][self.good]
        c, m = int(state.owner[v]), int(state.market[v])
        affinity = profile.get("affinity", 1.) * profile.get("religion_group", {}).get(state.religion_group[v], 1.)
        affinity *= profile.get("culture", {}).get(state.culture[v], 1.)
        rival = 0.
        if c >= 0 and self.good in ("coffee", "tea"):
            other = ctl.sims.get("tea" if self.good == "coffee" else "coffee")
            rival = float(other.shared_country[c]) if other else 0.
            rival = max(rival, ctl.context_goods["wine"].eff(v))
        multiplier = ctl.multiplier(self.good, int(c), self.t)
        self.U += 2 * len(ctl.effects.get((self.good,int(c)),()))
        preemption = 0 if "preemption" in ctl.disabled_rules else cfg["preemption"]
        p *= affinity * multiplier / (1. + preemption * max(0., rival - 10.))
        retention = min(1., retention * profile.get("rho_scale", 1.))
        internal = cfg["internal_rate"] * float(self.shared_market[m]) if m >= 0 and "market" not in ctl.disabled_rules else 0.
        # Shared market input also obeys incumbent competition.
        internal *= affinity * multiplier / (1. + preemption * max(0., rival - 10.))
        if internal > 0 and c >= 0 and c not in self.internal_logged:
            row={"good": self.good, "country": int(c), "month": self.t,"type": "market", "node": v}
            if self.good == "tobacco" and c not in ctl.evaluator.seen["K5"]:
                row["country_x_before"] = self.country_value(c)
            ctl.inputs_this_month.append(row)
            self.internal_logged.add(int(c))
        self.task_terms = (v,p,internal)
        return p, retention, internal

    def _serve(self, t):
        try:
            return super()._serve(t)
        finally:
            # Calculation scratch is never carried to the next node/month.
            self.task_terms = None

    def clock_decay_multiplier(self, country):
        multiplier = 1.
        for effect in self.controller.effects.get((self.good,country),()):
            if self.t < effect["until"]:
                multiplier *= effect.get("decay_scale", 1.)
                self.U += 2
        return multiplier

    def reservation(self, v):
        return super().reservation(v) + 2*len(self.controller.effects.get((self.good,self.owner[v]),()))

    def inject(self, v, amount, kind, source=None):
        if v < 0 or not self.spreading:
            return False
        c = self.owner[v]
        if self.clock and c >= 0 and self.decaying[c]:
            return False
        old = self.eff(v)
        if min(100.,old+amount) == old:
            self.U += 1
            return False
        before = self.country_value(c) if self.good == "tobacco" and c not in self.controller.evaluator.seen["K5"] else None
        self.x[v] = min(100., old + amount)
        self.direct_kind = kind
        self.direct_evidence=set((source or {}).get("facts",()))
        if kind == "ownership":
            self.direct_evidence.update(self.fact_ancestry.get((source or {}).get("node"),()))
        elif kind == "contact":
            if (source or {}).get("reverse"):
                self.direct_evidence.update(self.country_evidence[(source or {})['resident']])
            else:
                self.direct_evidence.update(self.market_evidence[(source or {})['market']])
        self._note(v, self.x[v], self.t)
        self.direct_kind = None
        self.direct_evidence=set()
        self.U += 3 + self._push(v)
        for u in self.g.outgoing[v]:
            self.U += 1 + self._push(u)
        row = {"good": self.good, "country": int(c), "node": int(v), "month": self.t,
               "type": kind, "source": source, "amount": amount}
        if before is not None:
            row["country_x_before"] = before
        self.nonlocal_log.append(row)
        self.controller.inputs_this_month.append(row)
        self.input_log.append(row)
        return True

    def country_value(self, c):
        """Exact pre-effect observation, used by diagnostics only."""
        if c < 0:
            return 0.
        vs=self.members_of[c]
        weights=self.controller.state.population[vs]
        total=float(weights.sum())
        values=np.fromiter((self.eff(v) for v in vs),dtype=float,count=len(vs))
        return float(values@weights/total) if total else 0.

    def refresh_aggregates(self):
        """A sliced, charged world traversal; no per-location contribution cache."""
        state, parts = self.controller.state, self.controller.config["fixed"]["aggregate_slices"]
        width = max(1, math.ceil(self.n / parts))
        a, b = self.aggregate_cursor, min(self.n, self.aggregate_cursor + width)
        values = np.fromiter((self.eff(v) for v in range(a, b)), dtype=float, count=b-a)
        for k, groups in enumerate((state.owner[a:b], state.market[a:b])):
            valid = groups >= 0
            self._aggregate_sums[k] += np.bincount(groups[valid], weights=state.population[a:b][valid] * values[valid],
                                                  minlength=len(self._aggregate_sums[k]))
            self._aggregate_weights[k] += np.bincount(groups[valid], weights=state.population[a:b][valid],
                                                     minlength=len(self._aggregate_weights[k]))
        wine=self.controller.context_goods["wine"]
        for v,c,m,value in zip(range(a,b),state.owner[a:b].tolist(),state.market[a:b].tolist(),values.tolist()):
            if c >= 0 and 0 < value < 1:
                self._front_work[c] = True
            if c >= 0 and value > self._max_work[c]:
                self._max_work[c],self._source_work[c] = value,v
            dirty_country = c >= 0 and (self.country_wake_until[c] >= self.t or (wine.decaying[c] and not wine.finished[c]))
            if dirty_country or (m >= 0 and self.market_wake_until[m] >= self.t):
                self.U += self._push(v)
        self.U += 16 * (b-a)
        self.aggregate_cursor = b
        if b == self.n:
            country,market = [np.divide(s,w,out=np.zeros_like(s),where=w>0)
                              for s,w in zip(self._aggregate_sums,self._aggregate_weights)]
            for m in np.flatnonzero(np.abs(market-self.shared_market)>1e-9):
                self.market_wake_until[int(m)] = self.t+parts
            if self.good in ("coffee","tea"):
                other=self.controller.sims.get("tea" if self.good == "coffee" else "coffee")
                if other:
                    for c in np.flatnonzero(np.abs(country-self.shared_country)>1e-9):
                        other.country_wake_until[int(c)] = self.t+parts
            self.shared_country,self.shared_market = country,market
            self.shared_country_source = self._source_work.copy()
            self.shared_front = self._front_work.copy()
            self.U += 2*(self.ng+len(market))
            self.reset_aggregation()

    def reset_aggregation(self):
        self.aggregate_cursor = 0
        for array in self._aggregate_sums + self._aggregate_weights:
            array.fill(0.)
        self._max_work = [0.]*self.ng
        self._source_work = [-1]*self.ng
        self._front_work = [False]*self.ng

    def begin_month(self):
        if self.done or self.t >= self.P.max_months:
            return False
        self.month_start_U = self.U
        self.internal_logged.clear()
        self.arrivals_this_month.clear()
        self.controller.prepare_good(self)
        self.refresh_aggregates()
        if self.clock:
            self._clocks(self.t)
        return True

    def serve_month(self):
        if not self.spreading:
            self._finish_month(self.month_start_U,0)
            return True
        return super().serve_month()

    def open_wave(self):
        if self.wave_end is not None and self.t < self.wave_end:
            return
        self.wave_start = self.t
        if self.first_wave_start is None:
            self.first_wave_start=self.t
        self.wave_end = self.t + self.controller.config["fixed"]["wave_months"]
        self.waves.append([self.t, self.wave_end])
        self.spreading = True
        self.renew_cursor = self.wake_cursor = 0
        self.cleanup_pending = False

    def serve_shared_tasks(self, budget):
        """Admit atomic country renewals and bounded frontier/cleanup walks.

        Progress is good-level cursors. No per-location dirty or visited flag
        is introduced; all writes and queue primitives enter the same ledger.
        """
        start=self.U
        if self.cleanup_pending:
            while self.length and self.U-start+3 <= budget:
                self._pop();self.U += 3
            self.cleanup_pending = self.length > 0
            return self.U-start
        if not self.spreading:
            return 0
        while self.renew_cursor < self.ng:
            c=self.renew_cursor
            materialise=self.decaying[c] and not self.finished[c]
            cost=6+(4*len(self.members_of[c]) if materialise else 0)
            if self.U-start+cost > budget:
                return self.U-start
            if materialise:
                for v in self.members_of[c]:
                    self.x[v]=self.eff(v)
            self.join[c],self.S[c],self.habit[c] = -1,1.,self.P.habit_floor
            self.decaying[c]=self.finished[c]=False
            self.U += cost
            self.renew_cursor += 1
        while self.wake_cursor < self.n:
            v=self.wake_cursor
            reserve=1+(self.price['push_new']*(1+len(self.g.outgoing[v])) if self.x[v]>0 else 0)
            if self.U-start+reserve > budget:
                break
            self.U += 1
            if self.x[v]>0:
                self.U += self._push(v)
                for u in self.g.outgoing[v]:
                    self.U += self._push(u)
            self.wake_cursor += 1
        return self.U-start


class StructuralRun:
    def __init__(self, graph, timeline, config, spec, *, events="none", seed=0, disabled_events=(),
                 frames_every=0, end_month=None, cancel=None):
        if events not in ("none", "historical", "generic", "mixed"):
            raise ValueError("events must be none, historical, generic or mixed")
        validate_params(config["params"])
        self.timeline, self.config, self.spec, self.seed = timeline, deepcopy(config), spec, seed
        self.state, _ = timeline.at(timeline.start)
        self.events_mode, self.disabled_events = events, set(disabled_events)
        self.end = min(timeline.end, end_month) if end_month is not None else timeline.end
        self.cancel = cancel
        self.inputs_this_month, self.bans_this_month, self.event_log = [], [], []
        self.cooldowns, self.event_done, self.global_cooldown, self.effects = {}, set(), {}, {}
        self.disabled_rules = set(config.get("disabled_rules",()))
        self.event_rng = {}
        self.eligible_months = []
        self.world_log = []
        self.country_neighbors = {}
        self.country_markets = {}
        self.country_faith = {}
        self.foreign_members = {}
        self.last_roads = {}
        self.straits = {tuple(sorted((e["a"],e["b"]))) for e in graph.meta.get("special_edges",[]) if e["type"] == "strait"}
        self.market_faith = []
        self.tobacco_possession_seen = False
        self.ledger = []
        self.overruns = []
        self.sims = {}
        # An unqueued 1337 wine custom is still the single x of another good,
        # rather than an additional resistance variable attached to coffee.
        # Its uncertain magnitude is exposed and removed in the prior ablation.
        wine = opening_values("wine",graph,self.state,config) if "wine" not in self.disabled_rules else [0.]*graph.n
        wine_graph = simulation_graph(graph)
        wine_graph.owner = self.state.owner.tolist()
        wine_graph.group_names = list(timeline.country_names)
        p = config["params"]
        self.context_goods = {"wine": Simulation(wine_graph, Params(initial_values=wine,
            **{k:p[k] for k in ("rho","p","delta","hold_T","decay_factor","habit_floor")},
            max_months=self.end,series_every=0,stop_when_calm=False))}
        context = self.context_goods["wine"]
        extra = len(timeline.country_names)-context.ng
        for name,default in (("join",-1),("decay_start",-1),("finished_month",-1),("S",1.),("decaying",False),("finished",False),("habit",p["habit_floor"])):
            getattr(context,name).extend([default]*extra)
        context.members_of.extend([[] for _ in range(extra)])
        context.ng += extra
        context.spreading = False
        context.t = timeline.start
        self.origin_year = random.Random(canonical_hash([seed, "recipe"])).uniform(*config["fixed"]["origin_start"])
        self.evaluator = ConditionalEvaluator(spec["K"], timeline.kind, timeline.start)
        self.metrics = RunMetrics(graph, spec.get("targets", []), timeline.kind)
        self.raw_nodes = {good: [v for v, r in enumerate(self.state.raw_material) if r == good] for good in GOODS}
        self.observations = []
        self.region_series = []
        for good in GOODS:
            g = simulation_graph(graph)
            g.group_names = list(timeline.country_names)
            g.owner = self.state.owner.tolist()
            initial = opening_values(good,g,self.state,config)
            p = config["params"]
            params = Params(**{k: p[k] for k in ("rho", "p", "delta", "hold_T", "decay_factor", "habit_floor")},
                            initial_values=initial, max_months=self.end, stop_when_calm=False, series_every=12 if frames_every else 0,
                            frames_every=frames_every, coefficient_cost=10)
            sim = RuleSimulation(g, params, good, self)
            sim.t = timeline.start
            for col in sim.threshold_arrival.values():
                for v, t in enumerate(col):
                    if t == 0:
                        col[v] = timeline.start
            sim.first_positive = [timeline.start if t == 0 else t for t in sim.first_positive]
            sim.entries = {v: timeline.start for v, t in enumerate(sim.arrival) if t >= 0}
            self.sims[good] = sim
        self.apply_state(first=True)
        # Opening customs are already nonlocal input at the left boundary,
        # even when the country's weighted mean is below stage2.
        self.evaluator.seen["K5"].update(self.sims["tobacco"].owner[v]
            for v,value in self.sims["tobacco"].P.initial_values if value > 0 and self.sims["tobacco"].owner[v] >= 0)
        self.last_diagnostic = None
        # Existing customs are settled facts, not a new 1337 enthusiasm wave.
        # Learn the opening contact/ownership frontier without activating it.
        # A later change in eligible structural links can awaken any good.
        for good in ("tea","tobacco"):
            sim=self.sims[good]
            for _ in range(self.config["fixed"]["aggregate_slices"]):
                sim.refresh_aggregates()
            sim.join[:]=[-1]*sim.ng
            sim.decaying[:]=[False]*sim.ng
            sim.finished[:]=[True]*sim.ng
            self.prepare_good(sim,opening=True)
            sim.wave_start=sim.wave_end=None
            sim.first_wave_start=None
            sim.spreading=False
            sim.waves.clear()
            sim.renew_cursor,sim.wake_cursor=sim.ng,sim.n
            sim.sources={}
            sim.U=0
            while sim.length:
                sim._pop()
            sim.round_remaining=0

    def multiplier(self, good, country, month):
        value = 1.
        for effect in self.effects.get((good,country),()):
            if month < effect["until"]:
                value *= effect["multiplier"]
        return value

    def apply_state(self, first=False):
        state = self.state
        self.raw_nodes = {good:[v for v,r in enumerate(state.raw_material) if r == good] for good in GOODS}
        changed_roads = {edge for edge in self.last_roads.keys() | state.roads.keys()
                         if self.last_roads.get(edge) != state.roads.get(edge)}
        self.country_neighbors = {c: set() for c in state.capitals}
        self.country_faith = {c:state.countries.get(self.timeline.country_names[c],{}).get('religion_group') or self.timeline.faith_groups.get(
            state.countries.get(self.timeline.country_names[c],{}).get("religion")) or state.religion_group[v]
            for c,v in state.capitals.items()}
        for v, neighbors in enumerate(self.timeline.graph.incoming):
            c = int(state.owner[v])
            if c in self.country_neighbors:
                self.country_neighbors[c].update(int(state.owner[u]) for u in neighbors
                                                 if state.owner[u] >= 0 and state.owner[u] != c)
        self.country_markets = {c: [] for c in state.capitals}
        for m, rec in enumerate(state.markets):
            for c in rec["merchants"]:
                if c in self.country_markets:
                    self.country_markets[c].append(m)
        self.foreign_members = {c: [] for c in state.capitals}
        continent = self.timeline.graph.attrs["continent"]
        faith = [defaultdict(float) for _ in state.markets]
        for v, c in enumerate(state.owner):
            if c in state.capitals and continent[v] != continent[state.capitals[c]]:
                self.foreign_members[c].append(v)
            m = state.market[v]
            if m >= 0 and state.religion_group[v] is not None:
                faith[m][state.religion_group[v]] += state.population[v]
        self.market_faith = [max(row, key=row.get) if row else None for row in faith]
        for sim in list(self.sims.values()) + list(self.context_goods.values()):
            changed = [v for v in range(sim.n) if int(state.owner[v]) != sim.owner[v]]
            # Materialise incoming land before changing the owner. Rebase a new
            # country's lazy scale if division would overflow the one-x range.
            incoming_values = {v: sim.eff(v) for v in changed}
            rebase = set()
            for v, value in incoming_values.items():
                c = int(state.owner[v])
                if c >= 0 and sim.decaying[c] and value > 100 * (sim.habit[c] + (1-sim.habit[c])*sim.S[c]):
                    rebase.add(c)
            for c in rebase:
                factor=sim.habit[c]+(1-sim.habit[c])*sim.S[c]
                for v in sim.members_of[c]:
                    sim.x[v] = sim.eff(v)
                    sim.U += 4
                sim.habit[c] = min(1.,sim.habit[c]/factor) if factor > 0 else 0.
                sim.S[c] = 1.
                sim.U += 3
            sim.owner = state.owner.tolist()
            sim.g.owner = sim.owner
            sim.members_of = [[] for _ in range(sim.ng)]
            for v, c in enumerate(sim.owner):
                if c >= 0:
                    sim.members_of[c].append(v)
            for v, value in incoming_values.items():
                c = sim.owner[v]
                scale = (sim.habit[c] + (1-sim.habit[c])*sim.S[c]) if c >= 0 and sim.decaying[c] else 1.
                sim.x[v] = value / scale
                sim.U += 7 + sim._push(v)
            sim.g.attrs.update(population=state.population.tolist(), market=state.market.tolist(),
                               culture=state.culture, religion=state.religion)
            weights = []
            for v in range(sim.n):
                ws = []
                for u in sim.g.incoming[v]:
                    kind = state.roads.get((min(u, v), max(u, v)))
                    enabled = "roads" not in self.disabled_rules
                    scale = self.config["params"]["road_scale"] if kind and enabled else 1.5 if (min(u,v),max(u,v)) in self.straits else 1.
                    if enabled and kind in ("paved_road", "modern_road", "railroad"):
                        scale *= self.config["params"]["road_scale"]
                    ws.append(scale)
                weights.append(tuple(ws))
            sim.g.in_weight = sim.w = weights
            if hasattr(sim,"reset_aggregation"):
                sim.reset_aggregation()
            # These are imported engine relationships, not simulated state.
            # Only the effects of ownership hooks and shared-aggregate reset
            # are simulated work; copying a Python snapshot is not an EU5 scan.
            if not first:
                sim.U += 2 * (sim.ng + len(state.markets))
                for a,b in changed_roads:
                    sim.U += 4 + sim._push(a) + sim._push(b)
        self.last_roads = dict(state.roads)
        self.world_log.append({"month": next(iter(self.sims.values())).t, "date": state.snapshot_date,
                               "owner": state.owner.tolist(), "market": state.market.tolist(),
                               "group_labels": [state.countries.get(c,{}).get("tag") or c for c in self.timeline.country_names],
                               "facts": state.facts_active})

    def prepare_good(self, sim, opening=False):
        t, state, cfg, fixed = sim.t, self.state, self.config["params"], self.config["fixed"]
        # At most 100 years in one wave; no named or calendar wave registry.
        if sim.wave_end is not None and t >= sim.wave_end and sim.spreading:
            sim.spreading = False
            sim.cleanup_pending = sim.length > 0
            sim.round_remaining = 0
            sim.renew_cursor,sim.wake_cursor=sim.ng,sim.n
        if sim.good == "coffee" and sim.origin_node is None and t >= sim.origin_month:
            where=self.config["profiles"]["coffee"].get("origin_where",{})
            candidates = [v for v in self.raw_nodes["coffee"] if self.country_faith.get(int(state.owner[v])) == "muslim"
                          and all(sim.g.attrs[k][v] in (val if isinstance(val,list) else [val]) for k,val in where.items())]
            sim.U += len(self.raw_nodes["coffee"]) * 4
            if candidates:
                sim.origin_node = sim.origin_rng.choices(candidates, weights=[max(.001, state.population[v]) for v in candidates])[0]
                sim.source_market = int(state.market[sim.origin_node]) if state.market[sim.origin_node] >= 0 else None
                sim.open_wave()
        if (sim.good == "coffee" and sim.origin_node is not None and
                sim.origin_month <= t < sim.origin_month + fixed["origin_duration"] and
                state.raw_material[sim.origin_node] == "coffee" and
                self.country_faith.get(int(state.owner[sim.origin_node])) == "muslim"):
            sim.sources = {sim.origin_node: fixed["origin_amount"]}
            sim.U += 2 + sim._push(sim.origin_node)
        else:
            sim.sources = {}
        pairs = [(m, c, share, state.capitals[c],c) for m, rec in enumerate(state.markets) if sim.shared_market[m] >= cfg["theta"]
                 for c, share in rec["merchants"].items() if c in state.capitals
                 and rec["center"] >= 0 and state.owner[rec["center"]] != c
                 and state.market[state.capitals[c]] != m]
        # Reverse residency: the owner of an obsessed market has residents abroad.
        source_countries = {int(state.owner[rec["center"]]) for m,rec in enumerate(state.markets)
                            if sim.shared_market[m] >= cfg["theta"] and rec["center"] >= 0 and state.owner[rec["center"]] >= 0}
        for m, rec in enumerate(state.markets):
            for c, share in rec["merchants"].items():
                if c in source_countries and rec["center"] >= 0 and sim.shared_market[m] < cfg["theta"]:
                    center_owner = int(state.owner[rec["center"]])
                    if center_owner >= 0:
                        pairs.append((m, center_owner, share, rec["center"],c))
        if sim.good == "tobacco":
            continent = sim.g.attrs["continent"]
            transatlantic = any(state.owner[v] in state.capitals and continent[v] == "america" and
                continent[state.capitals[int(state.owner[v])]] != "america" for v in self.raw_nodes["tobacco"])
            sim.U += 4*len(self.raw_nodes["tobacco"])
            self.tobacco_possession_seen |= transatlantic
            if not self.tobacco_possession_seen:
                pairs = [row for row in pairs if continent[row[3]] == "america"]
        sim.U += 3 * len(state.markets) + 4 * sum(len(m["merchants"]) for m in state.markets)
        if "contact" in self.disabled_rules:
            pairs = []
        ownership = []
        for c, cap in state.capitals.items():
            sim.U += 5
            source=sim.shared_country_source[c]
            if ("ownership" not in self.disabled_rules and source >= 0 and state.owner[source] == c and
                    sim.eff(cap) < cfg["theta"] and sim.eff(source) >= cfg["theta"]):
                ownership.append((c,cap,source))
        new_pairs = {(m,c,target) for m,c,_,target,_ in pairs} - sim.seen_pairs
        new_ownership = {(c,int(state.market[source])) for c,_,source in ownership} - sim.seen_ownership
        if not opening and (new_pairs or new_ownership):
            sim.open_wave()
        sim.seen_pairs.update((m,c,target) for m,c,_,target,_ in pairs)
        sim.seen_ownership.update((c,int(state.market[source])) for c,_,source in ownership)
        if opening:
            return
        if not sim.spreading:
            return
        for m, c, share, cap,resident in pairs:
            profile = self.config["profiles"][sim.good]
            affinity = profile.get("affinity",1.) * profile.get("religion_group", {}).get(self.country_faith.get(c), 1.)
            culture = state.countries.get(self.timeline.country_names[c],{}).get("culture") or state.culture[cap]
            affinity *= profile.get("culture",{}).get(culture,1.)
            sim.U += 5
            if sim.contact_rng.random() < -math.expm1(-cfg["lambda_contact"] * share * affinity / 12):
                evidence=[f['id'] for f in self.timeline.facts if f['id'] in state.facts_active and f['kind']=='residency'
                          and state.owner[self.timeline.names[f['actor_location']]]==resident
                          and state.market[self.timeline.names[f['location']]]==m]
                sim.inject(cap, cfg["contact_amount"], "contact", {"market":m,"facts":evidence,"resident":int(resident),
                           "reverse":bool(sim.shared_market[m]<cfg['theta'])})
        # Ownership is an actual-intensity channel, never raw-material => habit.
        for c,cap,source in ownership:
            if sim.contact_rng.random() < -math.expm1(-cfg["lambda_contact"] / 12):
                sim.inject(cap, cfg["contact_amount"], "ownership", {"node": int(source)})

    def diagnostics(self):
        state, country_x, market_x, capital_x, values = self.state, {}, {}, {}, {}
        market_population = np.zeros(len(state.markets))
        ng = len(self.timeline.country_names)
        for good, sim in self.sims.items():
            scales = np.array([sim.habit[c] + (1-sim.habit[c])*sim.S[c]
                               if sim.decaying[c] else 1. for c in range(sim.ng)] + [1.])
            x = np.asarray(sim.x) * scales[state.owner]
            values[good] = x
            reached = [v for v in sim.arrivals_this_month if sim.arrival_kind[v] == "adjacency"]
            if reached:
                entries = [(v, t) for v, t in sim.entries.items() if x[v] >= 1 and t <= sim.t-1]
                signature = tuple(entries)
                if signature != sim.distance_signature:
                    dist, root = [-1]*sim.n, [-1]*sim.n
                    queue = deque()
                    for v, t in sorted(entries, key=lambda row: (row[1], row[0])):
                        dist[v], root[v] = 0, v
                        queue.append(v)
                    while queue:
                        v = queue.popleft()
                        for u in sim.g.outgoing[v]:
                            if dist[u] < 0:
                                dist[u], root[u] = dist[v]+1, root[v]
                                queue.append(u)
                    sim.distance_signature, sim.distance_cache = signature, (dist, root)
                dist, root = sim.distance_cache
                for v in reached:
                    if root[v] >= 0:
                        dt = sim.arrival[v] - sim.entries[root[v]]
                        if dt >= 12:
                            sim.land_speeds.append(dist[v] * 12 / dt)
            country_x[good], _ = weighted_means(x, state.owner, state.population, ng)
            market_x[good], market_population = weighted_means(x, state.market, state.population, len(state.markets))
            cap_x = np.zeros(ng)
            for c, v in state.capitals.items():
                cap_x[c] = x[v]
            capital_x[good] = cap_x
        market_faith = self.market_faith
        raw_countries = {g: {int(state.owner[v]) for v in vs if state.owner[v] >= 0} for g, vs in self.raw_nodes.items()}
        t = next(iter(self.sims.values())).t - 1
        self.evaluator.observe(t, state, country_x, market_x, capital_x, raw_countries,
                               self.inputs_this_month, self.bans_this_month, self.sims["coffee"].source_market,
                               market_population, market_faith)
        for good, sim in self.sims.items():
            if sim.origin_groups is None and sim.wave_start is not None:
                sim.origin_groups = set(np.flatnonzero(country_x[good] >= 20))
            if sim.origin_groups is not None and sim.external_stage2 is None:
                if any(c not in sim.origin_groups for c in np.flatnonzero(country_x[good] >= 20)):
                    sim.external_stage2 = t
        self.last_diagnostic = (country_x, market_x, capital_x, values, market_population, market_faith)
        return country_x, market_x, capital_x, values

    def event_candidates(self, event, good, countries=None):
        state = self.state
        sim = self.sims[good]
        cx, mx = sim.shared_country, sim.shared_market
        condition = event["condition"]
        out = []
        for c, cap in state.capitals.items():
            if countries is not None and c not in countries:
                continue
            if event["effect"] == "boost" and sim.decaying[c]:
                continue
            linked = any(mx[m] >= 20 for m in self.country_markets.get(c, ()))
            source = sim.shared_country_source[c]
            linked |= source >= 0 and sim.eff(source) >= 1
            neighbors = self.country_neighbors.get(c, ())
            linked |= any(cx[n] >= 20 for n in neighbors)
            links = [r for r in state.links if r["actor"] == c and (r.get("good") in (None, good))]
            ok = False
            if condition in ("marriage_to_stage2_country", "diplomacy_to_stage2_country"):
                kind = "marriage" if condition.startswith("marriage") else "diplomacy"
                ok = any(r["kind"] == kind and r["other"] is not None and cx[r["other"]] >= 20 for r in links)
            elif condition == "religious_capital_with_contact":
                rec = state.countries.get(self.timeline.country_names[c], {})
                ok = rec.get("tag") == "PAP" and rec.get("religion") == "catholic" and cx[c] >= 1
            elif condition == "declared_ban_at_stage2":
                ok = any(r["kind"] == "ban" for r in links) and cx[c] >= 20
            elif condition == "declared_ceremony_at_stage2":
                ok = any(r["kind"] == "ceremony" for r in links) and cx[c] >= 20
            elif condition == "linked_stage2_source":
                ok = linked and cx[c] < 30
            elif condition == "linked_source_and_local_contact":
                ok = linked and 0 < cx[c] < 20
            elif condition == "local_stage2":
                ok = cx[c] >= 20
            elif condition == "local_stage3":
                ok = cx[c] >= 45
            if ok:
                out.append((c, cap, bool(linked or links)))
        return out

    def process_events(self, month):
        if self.events_mode == "none":
            return
        pools = {"historical", "generic"} if self.events_mode == "mixed" else {self.events_mode}
        qualified = False
        audit = {}
        for good,sim in self.sims.items():
            # This full observation is diagnostic only. It does not supply the
            # event scheduler's bounded, charged country service.
            scales = np.array([sim.habit[c]+(1-sim.habit[c])*sim.S[c]
                               if sim.decaying[c] else 1. for c in range(sim.ng)] + [1.])
            values = np.asarray(sim.x)*scales[self.state.owner]
            cx,_ = weighted_means(values,self.state.owner,self.state.population,sim.ng)
            mx,_ = weighted_means(values,self.state.market,self.state.population,len(self.state.markets))
            members = {int(c) for c in self.state.owner[values >= 1] if c >= 0}
            audit[good] = (cx,mx,members)
        countries = sorted(self.state.capitals)
        width = 16
        selected = {countries[(month * width + k) % len(countries)] for k in range(min(width, len(countries)))} if countries else set()
        per_event = defaultdict(int)
        candidates_by_row, eligible = {}, defaultdict(list)
        for event in self.config["events"]:
            if event["pool"] not in pools:
                continue
            for good in event["goods"]:
                sim = self.sims[good]
                if not sim.spreading or sim.wave_start is None:
                    continue
                candidates = self.event_candidates(event,good,selected)
                sim.U += sum(14 + len(self.country_neighbors.get(c,())) + len(self.country_markets.get(c,())) for c in selected)
                candidates_by_row[event["id"],good] = candidates
                for c,_,_ in candidates:
                    if ((event["id"],good,c) in self.event_done or (event.get("global_unique") and any(k[0]==event["id"] for k in self.event_done)) or self.cooldowns.get((good,c),-1)>month
                            or self.global_cooldown.get(c,-1)>month):
                        continue
                    eligible[good,c,event["pool"]].append(event)
        chosen = {}
        for good,c,_ in eligible:
            if (good,c) in chosen:
                continue
            sim = self.sims[good]
            rng = random.Random(canonical_hash([self.seed,good,c,month,"event"]))
            x = sim.shared_country[c]
            stage_scale = .4 if sim.finished[c] else .6 if x<20 else 1. if x<45 else 1.3 if x<70 else 1.5
            phase_scale = .6 if sim.decaying[c] else 1.3 if x<20 else 1. if x<45 else 1.1
            blocked = any(e.get("multiplier",1)<1 for e in self.effects.get((good,c),()))
            policy_scale = 1.5 if blocked else 1.
            sim.U += 10
            if rng.random() >= min(1.,self.config["fixed"]["event_rate"]*stage_scale*phase_scale*policy_scale):
                chosen[good,c] = None
                continue
            available = [p for p in ("historical","generic") if eligible.get((good,c,p))]
            pool = ("historical" if rng.random()<.6 else "generic") if len(available)==2 else available[0]
            rows = eligible[good,c,pool]
            kinds = sorted({e["kind"] for e in rows})
            kind_weights = [event_weight({"kind":kind},x,sim.shared_front[c],blocked) for kind in kinds]
            kind = rng.choices(kinds,weights=kind_weights)[0]
            chosen[good,c] = rng.choice([e for e in rows if e["kind"]==kind])["id"]
        for event in self.config["events"]:
            if event["pool"] not in pools:
                continue
            for good in event["goods"]:
                sim = self.sims[good]
                if not sim.spreading or sim.wave_start is None:
                    continue
                candidates = candidates_by_row.get((event["id"],good),[])
                if event["pool"] == "generic" and event["kind"] == "spread":
                    # E_gap concerns every eligible country, including those
                    # outside the scheduler slice in this particular month.
                    _,_,members = audit[good]
                    linked_all = set(members)
                    for m,rec in enumerate(self.state.markets):
                        if sim.shared_market[m] >= 20:
                            linked_all.update(rec["merchants"])
                    linked_all.update(c for c,neighbors in self.country_neighbors.items()
                                      if any(sim.shared_country[n] >= 20 for n in neighbors))
                    if event["condition"] == "linked_stage2_source":
                        qualified |= any(c in self.state.capitals and not sim.decaying[c] and sim.shared_country[c] < 30 for c in linked_all)
                    elif event["condition"] == "linked_source_and_local_contact":
                        qualified |= any(c in self.state.capitals and not sim.decaying[c] and 0 < sim.shared_country[c] < 20 for c in linked_all)
                # Fair cyclic service; at most three countries per event/month.
                candidates.sort(key=lambda row: (row[0] - month) % max(1, sim.ng))
                for c, cap, linked in candidates:
                    key = (event["id"], good, c)
                    if key in self.event_done or self.cooldowns.get((good, c), -1) > month or self.global_cooldown.get(c, -1) > month:
                        continue
                    if chosen.get((good,c)) != event["id"]:
                        continue
                    sim.U += 5
                    if per_event[event["id"]] >= self.config["fixed"]["event_cap_per_month"]:
                        continue
                    if event["id"] in self.disabled_events:
                        # Effect-only ablation retains discovery/admission U.
                        # A never-activated event is then exactly identical.
                        continue
                    # Eligibility is re-evaluated at the effect boundary.
                    if c not in {r[0] for r in self.event_candidates(event, good, {c})}:
                        continue
                    row = {"id": event["id"], "good": good, "month": month, "country": c, "node": cap,
                           "kind": event["kind"], "pool": event["pool"], "linked": linked, "condition_valid": True,
                           "condition": event["condition"]}
                    acx,amx,_ = audit[good]
                    row["linked"] = (any(sim.eff(v) >= 1 for v in sim.members_of[c]) or
                        any(amx[m] >= 20 for m in self.country_markets.get(c,())) or
                        any(acx[n] >= 20 for n in self.country_neighbors.get(c,())) or
                        any(r["actor"] == c for r in self.state.links))
                    if event["effect"] == "boost":
                        evidence=[r['fact_id'] for r in self.state.links if r['actor']==c]
                        sim.inject(cap, self.config["fixed"]["event_amount"], "event", {"event":event['id'],"facts":evidence})
                    elif event["effect"] in ("multiplier", "ban"):
                        scale = .2 if event["effect"] == "ban" else self.config["fixed"]["event_multiplier"]
                        self.effects.setdefault((good,c),[]).append({"good": good, "country": c, "multiplier": scale,
                                             "decay_scale": 1.5 if event["effect"] == "ban" else 1.,
                                             "until": month + self.config["fixed"]["event_duration"] * (4 if event["effect"] == "ban" else 1)})
                        sim.country_wake_until[c] = month+self.config["fixed"]["aggregate_slices"]
                        if event["effect"] == "ban":
                            self.bans_this_month.append({"good":good,"country":c,"initial":sim.country_value(c)})
                    self.event_done.add(key)
                    self.cooldowns[(good, c)] = month + self.config["fixed"]["event_cooldown"]
                    self.global_cooldown[c] = month + self.config["fixed"]["country_cooldown"]
                    self.event_log.append(row)
                    per_event[event["id"]] += 1
        self.eligible_months.append((month, qualified))

    def run(self, progress=None):
        for month in range(self.timeline.start, self.end):
            if self.cancel and self.cancel.is_set():
                raise InterruptedError("simulation cancelled")
            self.inputs_this_month, self.bans_this_month = [], []
            all_sims = {**self.sims,**self.context_goods}
            before = {g: sim.U for g, sim in all_sims.items()}
            for key in list(self.effects):
                self.sims[key[0]].U += 2*len(self.effects[key])
                self.effects[key] = [e for e in self.effects[key] if month < e["until"]]
                if not self.effects[key]:
                    del self.effects[key]
            self.state, changed = self.timeline.at(month)
            if changed:
                self.apply_state()
            wine = self.context_goods["wine"]
            wine.begin_month()
            wine.month_start_U = before["wine"]
            # A competing drink reopens attention to a dormant wine custom.
            # Its subsequent retreat uses wine's ordinary country clock/x.
            for c in self.state.capitals:
                wine.U += 3
                if wine.join[c] < 0 and max(self.sims[g].shared_country[c] for g in ("coffee","tea")) >= 1:
                    members = wine.members_of[c]
                    wine.U += len(members)
                    if any(wine.eff(v) >= 1 for v in members):
                        wine.join[c] = month
                        wine.U += 2
            wine.serve_month()
            prepared = []
            for sim in self.sims.values():
                sim.begin_month()
                prepared.append(sim)
            self.process_events(month)
            spent = sum(sim.U - before[g] for g, sim in all_sims.items())
            for k in range(len(prepared)):
                sim=prepared[(month+k)%len(prepared)]
                spent += sim.serve_shared_tasks(max(0,self.config['fixed']['budget']-spent))
            for k in range(len(prepared)):
                sim = prepared[(month + k) % len(prepared)]
                maintenance = sim.U - before[sim.good]
                # State changes precede begin_month, but belong in the same ledger.
                sim.month_start_U = before[sim.good]
                sim.P.budget = maintenance + max(0, self.config["fixed"]["budget"] - spent)
                old = sim.U
                sim.serve_month()
                spent += sim.U - old
            self.ledger.append(spent)
            if spent > self.config["fixed"]["budget"]:
                self.overruns.append({"month": month, "U": spent})
            self.metrics.observe(month, self, self.diagnostics())
            if progress and month % 120 == 0:
                progress(month, self)
        for sim in self.sims.values():
            if sim.P.frames_every and (not sim.frames or sim.frames[-1][0] != sim.t-1):
                sim.frames.append((sim.t-1, sim.stage_string()))
        return self
