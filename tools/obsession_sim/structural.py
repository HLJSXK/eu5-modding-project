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
from .worlds import canonical_hash, weighted_means, foreign_merchants
from .conditional import ConditionalEvaluator
from .acceptance import RunMetrics

GOODS = ("coffee", "tea", "tobacco")
FIT_PARAMS = ("p", "rho", "lambda_contact", "lambda_ownership", "preemption", "internal_rate")
PARAM_LIMITS = {"rho":(0,1),"p":(0,1),"delta":(0,100),"hold_T":(0,12000),
                "decay_factor":(0,1),"habit_floor":(0,1),"theta":(.001,100),
                "lambda_contact":(0,300),"lambda_ownership":(0,300),"contact_amount":(0,100),"preemption":(0,10),
                "internal_rate":(0,1)}


def validate_params(values):
    for name,value in values.items():
        if (name not in PARAM_LIMITS or isinstance(value,bool) or not isinstance(value,(int,float))
                or not math.isfinite(value) or not PARAM_LIMITS[name][0]<=value<=PARAM_LIMITS[name][1]
                or (name=="hold_T" and int(value)!=value)):
            raise ValueError("invalid shared parameter: "+name)
    return {k:int(v) if k=="hold_T" else v for k,v in values.items()}


def validate_fit_params(values):
    if set(values) - set(FIT_PARAMS):
        raise ValueError("only six historical fit parameters may vary: " + ", ".join(FIT_PARAMS))
    return validate_params(values)


def model_params(config):
    return {**{k:v for k,v in config.get("fixed", {}).items() if k in PARAM_LIMITS}, **config["params"]}


def event_weight(event, intensity, front=False, blocked=False, *, weights):
    """Stage/kind weights depend only on current state, never geography/date."""
    if event["kind"] == "spread":
        return (weights["spread_front"] if front else 1.)*(weights["spread_low"] if intensity < 45 else weights["spread_high"])
    if event["kind"] == "impact":
        return (weights["impact_high"] if intensity >= 45 else weights["impact_low"])*(weights["impact_blocked"] if blocked else 1.)
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
        columns=graph.attrs
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
        self.zones = dict(params.initial_values) if "R1" not in controller.rollbacks else {}
        self.zone_mask = np.array([v in self.zones for v in range(graph.n)])
        if self.zones:
            graph.incoming = [tuple(u for u in incoming if u not in self.zones) for incoming in graph.incoming]
            graph.outgoing = [() if v in self.zones else out for v,out in enumerate(graph.outgoing)]
        self.zone_rejected_inputs = 0
        self.zone_adjacency_arrivals = 0
        self.zone_values_constant = True
        self.clock_history, self.clock_current = [], {}
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
        for name, default in (("deadline", -1), ("decay_start", -1), ("finished_month", -1), ("S", 1.),
                              ("decaying", False), ("finished", False), ("habit", params.habit_floor)):
            getattr(self, name).extend([default] * extra)
        self.members_of.extend([[] for _ in range(extra)])
        self.ng += extra
        self.entries = {v: 0 for v, t in enumerate(self.arrival) if t >= 0}
        self.wave_start = None
        self.first_wave_start = None
        self.spreading = False
        self.contact_started = False
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
        self.ownership_rng = random.Random(canonical_hash([controller.seed, good, "ownership"]))
        self.origin_rng = random.Random(canonical_hash([controller.seed, good, "origin"]))
        self.origin_groups = None
        self.external_stage2 = None
        self.capital_stage2 = {}  # Diagnostic observations only; never read by propagation.
        self.shared_country = np.zeros(self.ng)
        self.shared_market = np.zeros(len(controller.timeline.market_names))
        self.shared_open_country = np.zeros(self.ng)
        self.shared_open_market = np.zeros(len(self.shared_market))
        sizes = [self.ng, len(self.shared_market)] * 2
        self._aggregate_sums = [np.zeros(n) for n in sizes]
        self._aggregate_weights = [np.zeros(n) for n in sizes]
        self._aggregate_lower = [np.full(n,np.inf) for n in sizes]
        self._aggregate_upper = [np.full(n,-np.inf) for n in sizes]
        self.shared_country_source = [-1]*self.ng
        self.shared_front = [False]*self.ng
        self._front_work = np.zeros(self.ng,dtype=bool)
        self._source_work = np.full(self.ng,-1,dtype=int)
        self._max_work = np.zeros(self.ng)
        self.owned_hot_population = np.zeros(self.ng)
        self.ownership_source = [-1]*self.ng
        self._owned_hot_work = np.zeros(self.ng)
        self._ownership_source_work = np.full(self.ng,-1,dtype=int)
        self.country_wake_until = [-1]*self.ng
        self.market_wake_until = [-1]*len(self.shared_market)
        self.aggregate_cursor = 0

    def init_country_clocks(self, count):
        self.deadline = [-1] * count

    def clock_joined(self, country):
        return self.deadline[country] != -1

    def clock_first_touch(self, country, month):
        self.deadline[country] = month + self.P.hold_T + (0 if "R2" in self.controller.rollbacks else self.controller.config["fixed"]["first_touch_limit"])
        row = dict(country=int(country), first_touch_month=int(month), national_month=None,
                   decay_start_month=None, finished_month=None, deadline=self.deadline[country])
        self.clock_history.append(row)
        self.clock_current[country] = row

    def clock_due(self, country, month):
        return month >= self.deadline[country]

    def apply_ban(self, country, month, scale):
        deadline = round(month + scale * max(0, self.deadline[country] - month))
        self.deadline[country] = -2 if deadline == -1 else deadline
        if country in self.clock_current:
            self.clock_current[country]["deadline"] = self.deadline[country]

    def materialize_node(self, node):
        return node not in self.zones

    def eff(self, v):
        return self.zones[v] if v in self.zones else super().eff(v)

    def _push(self, v):
        return self.price["push_rejected"] if v in self.zones else super()._push(v)

    def stage_string(self):
        stages = list(super().stage_string())
        for v in self.zones:
            if ord(stages[v]) >= ord('a') + 7:
                stages[v] = chr(ord(stages[v]) - 7)
        return ''.join(stages)

    def _clocks(self, t):
        for c in range(self.ng):
            if not self.clock_joined(c) or self.decaying[c] or self.finished[c]:
                continue
            if "R2" not in self.controller.rollbacks and self.shared_open_country[c] >= self.controller.config["params"]["theta"]:
                self.deadline[c] = min(self.deadline[c], t + self.P.hold_T)
                row = self.clock_current.get(c)
                if row is not None and row["national_month"] is None:
                    row["national_month"] = t
            row = self.clock_current.get(c)
            if row is not None:
                row["deadline"] = self.deadline[c]
        super()._clocks(t)
        for c, row in self.clock_current.items():
            if self.decaying[c] and row["decay_start_month"] is None:
                row["decay_start_month"] = t
            if self.finished[c] and row["finished_month"] is None:
                row["finished_month"] = t

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
            if kind == "adjacency" and self.arrival_parent[v] in self.zones:
                self.zone_adjacency_arrivals += 1
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

    def local_terms(self, v, p, retention, old=None):
        ctl, state = self.controller, self.controller.state
        cfg, profile = ctl.config["params"], ctl.config["profiles"][self.good]
        c, m = int(state.owner[v]), int(state.market[v])
        affinity = profile.get("affinity", 1.) * profile.get("religion_group", {}).get(state.religion_group[v], 1.)
        affinity *= profile.get("culture", {}).get(state.culture[v], 1.)
        barrier=ctl.preemption_load(self.good,v)
        multiplier = ctl.multiplier(self.good, int(c), self.t)
        self.U += 2 * len(ctl.effects.get((self.good,int(c)),()))
        p *= affinity * multiplier / (1. + barrier)
        retention = min(1., retention * profile.get("rho_scale", 1.))
        retention *= max(0.,1-barrier/100.)
        ban=max((e.get('decay_scale',1.) for e in ctl.effects.get((self.good,c),()) if e.get('policy')=='P3'),default=1.)
        retention=max(0.,1-(1-retention)*ban)
        member=(self.eff(v) if old is None else old)>=1
        internal = (cfg["internal_rate"] * float(self.shared_open_market[m])
                    if member and m >= 0 and "market" not in ctl.disabled_rules else 0.)
        # Shared market input also obeys incumbent competition.
        internal *= affinity * multiplier / (1. + barrier)
        if internal > 0 and c >= 0 and c not in self.internal_logged:
            row={"good": self.good, "country": int(c), "month": self.t,"type": "market", "node": v}
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
                multiplier = max(multiplier,effect.get("decay_scale", 1.))
                self.U += 2
        g=self.P.decay_factor
        desired=max(0.,1-(1-g)*multiplier)
        return math.log(desired)/math.log(g) if 0<g<1 and desired>0 else math.inf if 0<g<1 else 1.

    def reservation(self, v):
        return super().reservation(v) + 2*len(self.controller.effects.get((self.good,self.owner[v]),()))

    def inject(self, v, amount, kind, source=None):
        if v in self.zones:
            self.zone_rejected_inputs += 1
            return False
        if v < 0 or not self.spreading:
            return False
        c = self.owner[v]
        if self.clock and c >= 0 and self.decaying[c]:
            return False
        old = self.eff(v)
        if min(100.,old+amount) == old:
            self.U += 1
            return False
        before = self.country_value(c) if self.controller.evaluator is not None and self.good == "tobacco" and c not in self.controller.evaluator.seen["K5"] else None
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
        if self.clock and c>=0 and self.x[v]>=1 and not self.clock_joined(c):
            self.clock_first_touch(c, self.t)
            self.U+=self.price['join_write']
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

    def effective_values(self, a, b):
        if self.phase == 'lazy':
            return np.fromiter((self.eff(v) for v in range(a,b)),dtype=float,count=b-a)
        values = np.asarray(self.x[a:b],dtype=float)
        if self.clock:
            habit,S = np.asarray(self.habit),np.asarray(self.S)
            scales = np.r_[np.where(self.decaying,habit+(1-habit)*S,1.),1.]
            values = values*scales[np.asarray(self.owner[a:b],dtype=int)]
        if self.zones:
            values[self.zone_mask[a:b]] = np.asarray(self.x[a:b])[self.zone_mask[a:b]]
        return values

    def refresh_aggregates(self):
        """A sliced, charged world traversal; no per-location contribution cache."""
        state, parts = self.controller.state, self.controller.config["fixed"]["aggregate_slices"]
        width = max(1, math.ceil(self.n / parts))
        a, b = self.aggregate_cursor, min(self.n, self.aggregate_cursor + width)
        values = self.effective_values(a,b)
        for k, groups in enumerate((state.owner[a:b], state.market[a:b]) * 2):
            valid = groups >= 0
            if k >= 2:
                valid &= ~self.zone_mask[a:b]
            self._aggregate_sums[k] += np.bincount(groups[valid], weights=state.population[a:b][valid] * values[valid],
                                                  minlength=len(self._aggregate_sums[k]))
            self._aggregate_weights[k] += np.bincount(groups[valid], weights=state.population[a:b][valid],
                                                     minlength=len(self._aggregate_weights[k]))
            positive=valid & (state.population[a:b]>0)
            np.minimum.at(self._aggregate_lower[k],groups[positive],values[positive])
            np.maximum.at(self._aggregate_upper[k],groups[positive],values[positive])
        owners,markets,vertices = state.owner[a:b],state.market[a:b],np.arange(a,b)
        valid = owners>=0
        if np.any(valid):
            hot = valid & (values>=20) & (state.population[a:b]>0)
            hot &= (self.controller.capital_market[owners] != -2) & (markets != self.controller.capital_market[owners])
            np.add.at(self._owned_hot_work,owners[hot],state.population[a:b][hot])
            np.maximum.at(self._ownership_source_work,owners[hot],vertices[hot])
            self._front_work[owners[valid & (values>0) & (values<1)]] = True
            previous = self._max_work.copy()
            np.maximum.at(self._max_work,owners[valid],values[valid])
            better = valid & (values>previous[owners]) & (values==self._max_work[owners])
            first = np.full(self.ng,self.n,dtype=int)
            np.minimum.at(first,owners[better],vertices[better])
            improved = self._max_work>previous
            self._source_work[improved] = first[improved]
        country_dirty = np.r_[np.asarray(self.country_wake_until)>=self.t,False]
        market_dirty = np.r_[np.asarray(self.market_wake_until)>=self.t,False]
        dirty = country_dirty[owners] | ((values>=1) & market_dirty[markets])
        for v in vertices[dirty].tolist():self.U += self._push(v)
        self.U += self.controller.config['fixed']['aggregate_node_cost'] * (b-a)
        self.aggregate_cursor = b
        if b == self.n:
            country,market,open_country,open_market = [np.where(w>0,np.clip(np.divide(s,w,out=np.zeros_like(s),where=w>0),lo,hi),0.)
                              for s,w,lo,hi in zip(self._aggregate_sums,self._aggregate_weights,self._aggregate_lower,self._aggregate_upper)]
            for m in np.flatnonzero(np.abs(market-self.shared_market)>1e-9):
                self.market_wake_until[int(m)] = self.t+parts
            if self.good in ("coffee","tea"):
                other=self.controller.sims.get("tea" if self.good == "coffee" else "coffee")
                if other:
                    for c in np.flatnonzero(np.abs(country-self.shared_country)>1e-9):
                        other.country_wake_until[int(c)] = self.t+parts
            self.shared_country,self.shared_market = country,market
            self.shared_open_country,self.shared_open_market = open_country,open_market
            self.shared_country_source = self._source_work.tolist()
            self.owned_hot_population = self._owned_hot_work.copy()
            self.ownership_source = self._ownership_source_work.tolist()
            self.shared_front = self._front_work.tolist()
            self.U += 4*(len(self.controller.current_countries)+len(self.controller.current_markets))
            self.reset_aggregation()

    def reset_aggregation(self):
        self.aggregate_cursor = 0
        for array in self._aggregate_sums + self._aggregate_weights:
            array.fill(0.)
        for array in self._aggregate_lower:array.fill(np.inf)
        for array in self._aggregate_upper:array.fill(-np.inf)
        self._max_work.fill(0.)
        self._source_work.fill(-1)
        self._front_work.fill(False)
        self._owned_hot_work.fill(0.)
        self._ownership_source_work.fill(-1)

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

    def open_wave(self, reason="origin"):
        if self.wave_end is not None and self.t < self.wave_end:
            return
        self.wave_start = self.t
        if self.first_wave_start is None:
            self.first_wave_start=self.t
        self.wave_end = self.t + self.controller.config["fixed"]["wave_months"]
        self.waves.append([self.t, self.wave_end])
        self.controller.wave_log[self.good].append(dict(start_month=self.t,end_month=self.wave_end,reason=reason))
        self.spreading = True
        self.contact_started = True
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
            if c not in self.controller.current_countries:
                self.renew_cursor+=1
                continue
            materialise=self.decaying[c] or self.finished[c]
            nodes = [v for v in self.members_of[c] if v not in self.zones] if materialise else ()
            cost=7+4*len(nodes)
            if self.U-start+cost > budget:
                return self.U-start
            if materialise:
                for v in nodes:
                    self.x[v]=self.eff(v)
                self.deadline[c] = -1
                self.clock_current.pop(c, None)
            if "R2" in self.controller.rollbacks and self.clock_joined(c) and self.deadline[c] - self.P.hold_T < self.wave_start:
                self.deadline[c] = -1
                self.clock_current.pop(c, None)
            self.S[c],self.habit[c] = 1.,self.P.habit_floor
            self.decaying[c]=self.finished[c]=False
            self.U += cost
            self.renew_cursor += 1
        while self.wake_cursor < self.n:
            v=self.wake_cursor
            if v in self.zones:
                self.wake_cursor += 1
                continue
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
                 frames_every=0, end_month=None, cancel=None, mechanics_only=False):
        if events not in ("none", "historical", "generic", "mixed"):
            raise ValueError("events must be none, historical, generic or mixed")
        config = deepcopy(config)
        config["params"] = model_params(config)
        validate_params(config["params"])
        self.timeline, self.config, self.spec, self.seed = timeline, config, spec, seed
        self.state, _ = timeline.at(timeline.start)
        self.events_mode, self.disabled_events = events, set(disabled_events)
        self.end = min(timeline.end, end_month) if end_month is not None else timeline.end
        self.cancel = cancel
        self.inputs_this_month, self.bans_this_month, self.event_log = [], [], []
        self.cooldowns, self.event_done, self.global_cooldown, self.effects = {}, set(), {}, {}
        self.disabled_rules = set(config.get("disabled_rules",()))
        self.rollbacks = set(config.get("rollbacks", ()))
        self.mechanics_only = mechanics_only
        self.wave_log = {g: [] for g in GOODS}
        self.fact_contacts = defaultdict(int)
        self.fact_contact_inputs = defaultdict(int)
        self.fact_contact_by_good = {g:defaultdict(int) for g in GOODS}
        self.event_rng = {}
        self.eligible_months = []
        self.candidate_bursts = []
        self.events_abandoned_budget = 0
        self.world_log = []
        self.country_neighbors = {}
        self.country_markets = {}
        self.country_links = {}
        self.current_countries,self.current_markets=set(),set()
        self.market_members = []
        self.country_faith = {}
        self.foreign_members = {}
        self.market_faith = []
        self.tobacco_possession_seen = False
        self.ledger = []
        self.overruns = []
        self.sims = {}
        self.origin_year = random.Random(canonical_hash([seed, "recipe"])).uniform(*config["fixed"]["origin_start"])
        self.evaluator = None if mechanics_only else ConditionalEvaluator(spec["K"], timeline.kind, timeline.start)
        self.metrics = None if mechanics_only else RunMetrics(graph, spec.get("targets", []), timeline.kind)
        self.raw_nodes = {good: [v for v, r in enumerate(self.state.raw_material) if r == good] for good in GOODS}
        self.observations = []
        self.region_series = []
        for good in GOODS:
            g = simulation_graph(graph)
            g.group_names = list(timeline.country_names)
            g.owner = self.state.owner.tolist()
            initial = opening_values(good,g,self.state,config)
            p = config["params"]
            effective = {k: p[k] for k in ("rho", "p", "delta", "hold_T", "decay_factor")}
            effective["habit_floor"] = config["profiles"][good].get("habit_floor", p["habit_floor"])
            params = Params(**effective,
                            initial_values=initial, max_months=self.end, stop_when_calm=False, series_every=12 if frames_every else 0,
                            frames_every=frames_every, coefficient_cost=config['fixed']['coefficient_cost'])
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
        if self.evaluator is not None:
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
            sim.deadline[:]=[-1]*sim.ng
            sim.decaying[:]=[False]*sim.ng
            customs={sim.owner[v] for v,value in sim.P.initial_values if value>=1 and sim.owner[v]>=0}
            sim.finished[:]=["R1" in self.rollbacks and c in customs for c in range(sim.ng)]
            self.prepare_good(sim,opening=True)
            sim.wave_start=sim.wave_end=None
            sim.first_wave_start=None
            sim.spreading=False
            sim.waves.clear()
            self.wave_log[good].clear()
            sim.renew_cursor,sim.wake_cursor=sim.ng,sim.n
            sim.sources={}
            sim.U=0
            while sim.length:
                sim._pop()
            sim.round_remaining=0

    def multiplier(self, good, country, month):
        value,policy = 1.,1.
        for effect in self.effects.get((good,country),()):
            if month < effect["until"]:
                if effect.get('policy')=='P3':
                    policy=min(policy,effect['multiplier'])
                else:
                    value *= effect["multiplier"]
        return value*policy

    def preemption_load(self,good,v):
        if good not in ('coffee','tea') or 'preemption' in self.disabled_rules:
            return 0.
        c=int(self.state.owner[v])
        if c<0:
            return 0.
        other=self.sims.get('tea' if good=='coffee' else 'coffee')
        rival=max(float(other.shared_country[c]) if other else 0.,self.wine_background(v))
        return self.config['params']['preemption']*max(0.,rival-20.)

    def wine_background(self, v):
        if "wine" in self.disabled_rules:
            return 0.
        cfg = self.config["wine_background"]
        geographic = (self.timeline.graph.attrs["continent"][v] == "europe" if "R3" in self.rollbacks else
                      self.timeline.graph.attrs["region"][v] in cfg["regions"])
        return float(cfg["value"]) if geographic and self.state.religion_group[v] == cfg["religion_group"] else 0.

    def ownership_evidence(self,c,v):
        """Diagnostic labels for the current political input, never a rule."""
        name=self.timeline.graph.names[v]
        out=[]
        for fact in self.timeline.facts:
            if fact['id'] not in self.state.facts_active or fact['kind'] not in ('ownership','ownership_region'):
                continue
            if self.timeline.resolve_actor(fact, self.state.owner, self.state.countries)!=c:
                continue
            if fact['kind']=='ownership':
                matches=fact['location']==name
            else:
                matches=(name not in fact.get('exclude_locations',()) and all(self.timeline.graph.attrs[k][v] in
                    (value if isinstance(value,list) else [value]) for k,value in fact['where'].items()))
                if fact.get('previous_owner_tag'):
                    previous=self.timeline.graph.attrs.get('owner_tag')
                    matches &= previous is not None and previous[v]==fact['previous_owner_tag']
            if matches:
                out.append(fact['id'])
        return out

    def apply_state(self, first=False):
        state = self.state
        previous_sim = next(iter(self.sims.values()))
        old = previous_sim.g.attrs
        physical = (first or not np.array_equal(state.owner, previous_sim.owner)
                    or not np.array_equal(state.population, old.get('population'))
                    or not np.array_equal(state.market, old.get('market'))
                    or state.culture != old.get('culture') or state.religion != old.get('religion')
                    or state.religion_group != old.get('religion_group')
                    or state.capitals != getattr(self, 'applied_capitals', None))
        market_demography = (first or not np.array_equal(state.population,old.get('population'))
                             or not np.array_equal(state.market,old.get('market'))
                             or state.religion_group != old.get('religion_group'))
        previous_countries,previous_markets=self.current_countries,self.current_markets
        self.current_countries={self.timeline.country_index[name] for name in state.countries}
        self.current_markets={m for m,rec in enumerate(state.markets) if rec.get('present',rec['center']>=0)}
        reset_groups=len(previous_countries|self.current_countries)+len(previous_markets|self.current_markets)
        self.raw_nodes = {good:[v for v,r in enumerate(state.raw_material) if r == good] for good in GOODS}
        valid = state.owner >= 0
        self.country_population = np.bincount(state.owner[valid], weights=state.population[valid],
                                               minlength=len(self.timeline.country_names))
        self.capital_market = np.full(len(self.timeline.country_names)+1,-2,dtype=int)
        for c,v in state.capitals.items():self.capital_market[c] = state.market[v]
        self.country_faith = {}
        for c, v in state.capitals.items():
            rec = state.countries.get(self.timeline.country_names[c], {})
            self.country_faith[c] = (None if rec.get('no_state_religion') else
                rec.get('religion_group') or self.timeline.faith_groups.get(rec.get('religion')) or state.religion_group[v])
        self.country_markets = {c: [] for c in state.capitals}
        self.country_links=defaultdict(list)
        for link in state.links:self.country_links[link['actor']].append(link)
        for m, rec in enumerate(state.markets):
            for c in rec["merchants"]:
                if c in self.country_markets:
                    self.country_markets[c].append(m)
        if not physical:
            # Marriage/residency/official-faith metadata cannot discard a
            # partially completed physical population/x aggregation.
            for sim in self.sims.values():
                sim.U += 2*reset_groups
            self.record_world_state()
            return
        self.country_neighbors = {c: set() for c in state.capitals}
        for v, neighbors in enumerate(self.timeline.graph.incoming):
            c = int(state.owner[v])
            if c in self.country_neighbors:
                self.country_neighbors[c].update(int(state.owner[u]) for u in neighbors
                                                 if state.owner[u] >= 0 and state.owner[u] != c)
        self.market_members=[[] for _ in state.markets]
        for v,m in enumerate(state.market):
            if m>=0:
                self.market_members[int(m)].append(v)
        new_owner = state.owner.tolist()
        moved = np.flatnonzero(state.owner != np.asarray(previous_sim.owner,dtype=int)).tolist()
        members = [[] for _ in range(previous_sim.ng)]
        for v,c in enumerate(new_owner):
            if c>=0:members[c].append(v)
        continent = self.timeline.graph.attrs["continent"]
        self.foreign_members = {c:[v for v in members[c] if continent[v] != continent[cap]]
                                for c,cap in state.capitals.items()}
        if market_demography:
            faith = [defaultdict(float) for _ in state.markets]
            for v,m in enumerate(state.market):
                if m>=0 and state.religion_group[v] is not None:
                    faith[m][state.religion_group[v]] += state.population[v]
            self.market_faith = [max(row,key=row.get) if row else None for row in faith]
        population_list,market_list = state.population.tolist(),state.market.tolist()
        for sim in self.sims.values():
            changed = [v for v in moved if v not in sim.zones]
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
                    if v in sim.zones:
                        continue
                    sim.x[v] = sim.eff(v)
                    sim.U += 4
                sim.habit[c] = min(1.,sim.habit[c]/factor) if factor > 0 else 0.
                sim.S[c] = 1.
                sim.U += 3
            sim.owner = new_owner
            sim.g.owner = sim.owner
            sim.members_of = [vs.copy() for vs in members]
            for v, value in incoming_values.items():
                c = sim.owner[v]
                scale = (sim.habit[c] + (1-sim.habit[c])*sim.S[c]) if c >= 0 and sim.decaying[c] else 1.
                sim.x[v] = value / scale
                sim.U += 7 + sim._push(v)
            sim.g.attrs.update(population=population_list, market=market_list,
                               culture=state.culture, religion=state.religion, religion_group=state.religion_group)
            sim.g.in_weight = sim.w = None  # Every adjacency, including straits, has weight one.
            if hasattr(sim,"reset_aggregation"):
                sim.reset_aggregation()
            # These are imported engine relationships, not simulated state.
            # Only the effects of ownership hooks and shared-aggregate reset
            # are simulated work; copying a Python snapshot is not an EU5 scan.
            if not first:
                sim.U += 2*reset_groups
        self.applied_capitals = dict(state.capitals)
        self.record_world_state()

    def record_world_state(self):
        if not any(sim.P.frames_every for sim in self.sims.values()):
            return
        state = self.state
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
                sim.origin_node = sim.origin_rng.choices(candidates, weights=[max(fixed['minimum_origin_population'], state.population[v]) for v in candidates])[0]
                sim.origin_month=t  # The finite source lasts from actual activation, including delayed conditions in O.
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
        if self.evaluator is not None and sim.good=='coffee' and sim.origin_node is not None:
            c=int(state.owner[sim.origin_node])
            self.evaluator.origin_countries['coffee']={c} if c>=0 else set()
        pairs = [(m, c, share, state.capitals[c],c) for m, rec in enumerate(state.markets) if sim.shared_market[m] >= cfg["theta"]
                 for c, share in foreign_merchants(state, m).items() if c in state.capitals
                 and rec["center"] >= 0 and state.owner[rec["center"]] != c
                 and state.market[state.capitals[c]] != m]
        # Reverse residency: the owner of an obsessed market has residents abroad.
        source_countries = {int(state.owner[rec["center"]]) for m,rec in enumerate(state.markets)
                            if sim.shared_market[m] >= cfg["theta"] and rec["center"] >= 0 and state.owner[rec["center"]] >= 0}
        for m, rec in enumerate(state.markets):
            for c, share in foreign_merchants(state, m).items():
                if c in source_countries and rec["center"] >= 0 and sim.shared_market[m] < cfg["theta"]:
                    center_owner = int(state.owner[rec["center"]])
                    if center_owner >= 0 and center_owner != c:
                        pairs.append((m, center_owner, share, rec["center"],c))
        sim.U += 3*len(self.current_markets)+4*sum(len(m["merchants"]) for m in state.markets)
        if "contact" in self.disabled_rules:
            pairs = []
        ownership = []
        for c, cap in state.capitals.items():
            sim.U += 5
            source=sim.ownership_source[c]
            if ("ownership" not in self.disabled_rules and source >= 0 and state.owner[source] == c and
                    state.market[source] != state.market[cap] and sim.eff(cap) < 20 and sim.eff(source) >= 20
                    and self.country_population[c] > 0 and sim.owned_hot_population[c] > 0):
                ownership.append((c,cap,source,sim.owned_hot_population[c]/self.country_population[c]))
        new_pairs = {(m,c,target,resident) for m,c,_,target,resident in pairs} - sim.seen_pairs
        new_ownership = {(c,int(state.market[source])) for c,_,source,_ in ownership} - sim.seen_ownership
        if not opening and (new_pairs or new_ownership):
            sim.open_wave("contact_pair" if new_pairs else "ownership_pair")
        sim.seen_pairs.update((m,c,target,resident) for m,c,_,target,resident in pairs)
        sim.seen_ownership.update((c,int(state.market[source])) for c,_,source,_ in ownership)
        if opening:
            return
        for m, c, share, cap,resident in pairs:
            profile = self.config["profiles"][sim.good]
            affinity = profile.get("affinity",1.) * profile.get("religion_group", {}).get(self.country_faith.get(c), 1.)
            culture = state.countries.get(self.timeline.country_names[c],{}).get("culture") or state.culture[cap]
            affinity *= profile.get("culture",{}).get(culture,1.)
            barrier=self.preemption_load(sim.good,cap)
            sim.U += 8
            if sim.contact_rng.random() < -math.expm1(-cfg["lambda_contact"] * share * affinity / (12*(1+barrier))):
                if not sim.spreading and sim.eff(cap) < cfg['theta']:
                    sim.open_wave("contact_success")
                evidence=[f['id'] for f in self.timeline.facts if f['id'] in state.facts_active and f['kind']=='residency'
                          and self.timeline.resolve_actor(f, state.owner, state.countries)==resident
                          and state.market[self.timeline.names[f['location']]]==m]
                center=state.markets[m]['center']
                if center>=0 and state.owner[center]==resident:
                    evidence+=self.ownership_evidence(resident,center)
                for fact_id in evidence:
                    self.fact_contacts[fact_id] += 1
                accepted = sim.inject(cap, cfg["contact_amount"], "contact", {"market":m,"facts":evidence,"resident":int(resident),
                           "reverse":bool(sim.shared_market[m]<cfg['theta'])})
                if accepted:
                    for fact_id in evidence:
                        self.fact_contact_inputs[fact_id] += 1
                        self.fact_contact_by_good[sim.good][fact_id] += 1
        # Ownership is an actual-intensity channel, never raw-material => habit.
        for c,cap,source,fraction in ownership:
            profile = self.config["profiles"][sim.good]
            affinity = profile.get("affinity", 1.) * profile.get("religion_group", {}).get(self.country_faith.get(c), 1.)
            culture = state.countries.get(self.timeline.country_names[c], {}).get("culture") or state.culture[cap]
            affinity *= profile.get("culture", {}).get(culture, 1.)
            sim.U+=8
            if sim.ownership_rng.random() < -math.expm1(-cfg["lambda_ownership"] * fraction * affinity / (12*(1+self.preemption_load(sim.good,cap)))):
                if not sim.spreading:
                    sim.open_wave("ownership_success")
                sim.inject(cap, cfg["contact_amount"], "ownership", {"node":int(source), "population_share":float(fraction),
                           'facts':self.ownership_evidence(c,source)})

    def diagnostics(self):
        state, country_x, market_x, capital_x, values = self.state, {}, {}, {}, {}
        market_population = np.zeros(len(state.markets))
        ng = len(self.timeline.country_names)
        for good, sim in self.sims.items():
            x = sim.effective_values(0, sim.n)
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
                if x[v] >= 20:
                    sim.capital_stage2.setdefault(int(c), dict(month=sim.t-1, node=int(v)))
            capital_x[good] = cap_x
        market_faith = self.market_faith
        raw_countries = {g: {int(state.owner[v]) for v in vs if state.owner[v] >= 0} for g, vs in self.raw_nodes.items()}
        t = next(iter(self.sims.values())).t - 1
        if self.evaluator is not None:
            self.evaluator.observe(t, state, country_x, market_x, capital_x, raw_countries,
                                   self.inputs_this_month, self.bans_this_month, self.sims["coffee"].source_market,
                                   market_population, market_faith)
        for good, sim in self.sims.items():
            if sim.origin_groups is None and sim.wave_start is not None and np.any(country_x[good] >= 20):
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
        for c in (state.capitals if countries is None else countries):
            cap=state.capitals.get(c)
            if cap is None:
                continue
            if event["effect"] == "boost" and sim.decaying[c]:
                continue
            linked = any(mx[m] >= 20 for m in self.country_markets.get(c, ()))
            source = sim.shared_country_source[c]
            linked |= source >= 0 and sim.eff(source) >= 1
            neighbors = self.country_neighbors.get(c, ())
            linked |= any(cx[n] >= 20 for n in neighbors)
            links = [r for r in self.country_links.get(c,()) if r.get("good") in (None,good)]
            ok = False
            if condition in ("marriage_to_stage2_country", "diplomacy_to_stage2_country"):
                kind = "marriage" if condition.startswith("marriage") else "diplomacy"
                ok = any(r["kind"] == kind and r["other"] is not None and cx[r["other"]] >= 20 for r in links)
            elif condition == "religious_capital_with_contact":
                rec = state.countries.get(self.timeline.country_names[c], {})
                ok = 'catholic' in rec.get('religious_leader_for', ()) and rec.get('religion')=='catholic' and any(cx[n]>=event['min_intensity']
                    for n in state.capitals if state.countries.get(self.timeline.country_names[n],{}).get('religion')=='catholic')
            elif condition == "declared_ban_at_stage2":
                ok = any(r["kind"] == "ban" for r in links) and cx[c] >= 20
            elif condition == 'muslim_stage3':
                ok = self.country_faith.get(c)=='muslim' and cx[c]>=event['min_intensity']
            elif condition == 'culture_stage':
                rec=state.countries.get(self.timeline.country_names[c],{})
                ok = rec.get('culture') in event['cultures'] and cx[c]>=event['min_intensity']
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

    def live_event_probe(self,event,good,c,evidence=None):
        """Charge and independently recheck current intensities at activation.

        Shared sliced aggregates discover candidates. An admitted effect uses
        exact current values, so aggregation lag cannot make a historical event
        violate its declared condition. No per-location cache is introduced.
        """
        sim,state=self.sims[good],self.state
        condition=event['condition']
        links=[r for r in self.country_links.get(c,()) if r.get('good') in (None,good)]
        countries={c}
        if condition=='religious_capital_with_contact':
            countries.update(n for n in state.capitals if state.countries.get(self.timeline.country_names[n],{}).get('religion')=='catholic')
        if condition in ('marriage_to_stage2_country','diplomacy_to_stage2_country'):
            countries.update(r['other'] for r in links if r.get('other') is not None)
        generic=event['pool']=='generic'
        markets=self.country_markets.get(c,()) if generic else ()
        if generic:
            countries.update(self.country_neighbors.get(c,()))
        cost=20+3*len(links)+sum(8*len(sim.members_of[n])+8 for n in countries)+sum(8*len(self.market_members[m])+8 for m in markets)
        base=getattr(self,'month_base_U',{g:s.U for g,s in self.sims.items()})
        spent=sum(s.U-base[g] for g,s in self.sims.items())
        cap=state.capitals[c]
        reserve=(20+3+sim.price['push_new']*(1+len(sim.g.outgoing[cap]))+len(sim.g.outgoing[cap])+sim.price.get('join_write',0)
                 if event['effect']=='boost' else 20+5*(len(countries) if event.get('religion_scope') else 1))
        if spent+cost+reserve>self.config['fixed']['budget']:
            self.events_abandoned_budget += 1
            return False
        sim.U+=cost
        cx={n:sim.country_value(n) for n in countries}
        own=any(sim.eff(v)>=1 for v in sim.members_of[c])
        linked=own or any(cx[n]>=20 for n in self.country_neighbors.get(c,()) if n in cx)
        for m in markets:
            vs=self.market_members[m];weights=state.population[vs];total=float(weights.sum())
            mean=sum(sim.eff(v)*w for v,w in zip(vs,weights))/total if total else 0.
            linked |= mean>=20
        if evidence is not None:
            evidence['linked']=bool(linked or any(r.get('other') in cx and cx[r['other']]>=20 for r in links))
        if condition in ('marriage_to_stage2_country','diplomacy_to_stage2_country'):
            kind='marriage' if condition.startswith('marriage') else 'diplomacy'
            return any(r['kind']==kind and r.get('other') in cx and cx[r['other']]>=20 for r in links)
        if condition=='religious_capital_with_contact':
            rec=state.countries.get(self.timeline.country_names[c],{})
            return 'catholic' in rec.get('religious_leader_for', ()) and rec.get('religion')=='catholic' and any(cx[n]>=event['min_intensity'] for n in countries)
        if condition in ('declared_ban_at_stage2','declared_ceremony_at_stage2'):
            kind='ban' if condition.startswith('declared_ban') else 'ceremony'
            return cx[c]>=20 and any(r['kind']==kind for r in links)
        if condition=='muslim_stage3':
            return self.country_faith.get(c)=='muslim' and cx[c]>=event['min_intensity']
        if condition=='culture_stage':
            rec=state.countries.get(self.timeline.country_names[c],{})
            return rec.get('culture') in event['cultures'] and cx[c]>=event['min_intensity']
        if condition=='linked_stage2_source':
            return linked and cx[c]<30
        if condition=='linked_source_and_local_contact':
            return linked and 0<cx[c]<20
        if condition=='local_stage2':
            return cx[c]>=20
        if condition=='local_stage3':
            return cx[c]>=45
        raise ValueError('unknown event condition: '+condition)

    def process_events(self, month):
        if self.events_mode == "none":
            return
        pools = {"historical", "generic"} if self.events_mode == "mixed" else {self.events_mode}
        qualified = {good: False for good in GOODS}
        audit = {}
        for good,sim in self.sims.items():
            # This full observation is diagnostic only. It does not supply the
            # event scheduler's bounded, charged country service.
            values = sim.effective_values(0, sim.n)
            cx,_ = weighted_means(values,self.state.owner,self.state.population,sim.ng)
            mx,_ = weighted_means(values,self.state.market,self.state.population,len(self.state.markets))
            members = {int(c) for c in self.state.owner[values >= 1] if c >= 0}
            audit[good] = (cx,mx,members)
        countries = sorted(self.state.capitals)
        country_order={c:i for i,c in enumerate(countries)}
        width = self.config['fixed']['event_country_slice']
        selected = {countries[(month * width + k) % len(countries)] for k in range(min(width, len(countries)))} if countries else set()
        per_event = defaultdict(int)
        candidates_by_row, eligible = {}, defaultdict(list)
        for event in self.config["events"]:
            if event["pool"] not in pools:
                continue
            for good in event["goods"]:
                sim = self.sims[good]
                if (not sim.spreading or sim.wave_start is None) and event['effect']!='flavor':
                    continue
                candidates = self.event_candidates(event,good,selected)
                sim.U += sum(14 + len(self.country_neighbors.get(c,())) + len(self.country_markets.get(c,()))
                             +3*len(self.country_links.get(c,())) for c in selected)
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
            rng = random.Random(canonical_hash([self.seed,good,self.timeline.country_names[c],month,"event"]))
            x = sim.shared_country[c]
            weights = self.config['event_weights']
            stage_scale = weights['stage_finished'] if sim.finished[c] else weights['stage_cold'] if x<20 else weights['stage_member'] if x<45 else weights['stage_fashion'] if x<70 else weights['stage_high']
            phase_scale = weights['phase_finished'] if sim.finished[c] or sim.decaying[c] else weights['phase_cold'] if x<20 else weights['phase_member'] if x<45 else weights['phase_high']
            blocked = any(e.get("multiplier",1)<1 for e in self.effects.get((good,c),()))
            policy_scale = weights['policy_blocked'] if blocked else 1.
            sim.U += 10
            if rng.random() >= min(1.,self.config["fixed"]["event_rate"]*stage_scale*phase_scale*policy_scale):
                chosen[good,c] = None
                continue
            available = [p for p in ("historical","generic") if eligible.get((good,c,p))]
            pool = ("historical" if rng.random()<self.config['fixed']['historical_pool_share'] else "generic") if len(available)==2 else available[0]
            rows = eligible[good,c,pool]
            kinds = sorted({e["kind"] for e in rows})
            kind_weights = [event_weight({"kind":kind},x,sim.shared_front[c],blocked,weights=weights) for kind in kinds]
            kind = rng.choices(kinds,weights=kind_weights)[0]
            chosen[good,c] = rng.choice([e for e in rows if e["kind"]==kind])["id"]
        pre_cap = defaultdict(set)
        for (good, c), event_id in chosen.items():
            if event_id is not None:
                pre_cap[event_id].add(c)
        self.candidate_bursts.extend(len(cs) for cs in pre_cap.values())
        for event in self.config["events"]:
            if event["pool"] not in pools:
                continue
            for good in event["goods"]:
                sim = self.sims[good]
                if (not sim.spreading or sim.wave_start is None) and event['effect']!='flavor':
                    continue
                candidates = candidates_by_row.get((event["id"],good),[])
                if event["pool"] == "generic" and event["kind"] == "spread":
                    # E_gap concerns every eligible country, including those
                    # outside the scheduler slice in this particular month.
                    acx,amx,members = audit[good]
                    linked_all = set(members)
                    for m,rec in enumerate(self.state.markets):
                        if amx[m] >= 20:
                            linked_all.update(rec["merchants"])
                    linked_all.update(c for c,neighbors in self.country_neighbors.items()
                                      if any(acx[n] >= 20 for n in neighbors))
                    available={c for c in linked_all if c in self.state.capitals and not sim.decaying[c]
                               and (event['id'],good,c) not in self.event_done
                               and self.cooldowns.get((good,c),-1)<=month and self.global_cooldown.get(c,-1)<=month}
                    if event["condition"] == "linked_stage2_source":
                        qualified[good] |= any(acx[c] < 30 for c in available)
                    elif event["condition"] == "linked_source_and_local_contact":
                        qualified[good] |= any(0 < acx[c] < 20 for c in available)
                # Fair cyclic service; at most three countries per event/month.
                candidates.sort(key=lambda row: (country_order[row[0]]-month)%max(1,len(countries)))
                for c, cap, linked in candidates:
                    key = (event["id"], good, c)
                    if key in self.event_done or self.cooldowns.get((good, c), -1) > month or self.global_cooldown.get(c, -1) > month:
                        continue
                    if chosen.get((good,c)) != event["id"]:
                        continue
                    sim.U += 5
                    if per_event[event["id"]] >= self.config["fixed"]["event_cap_per_month"]:
                        continue
                    proof={}
                    condition_valid = self.live_event_probe(event,good,c,proof)
                    if not condition_valid:
                        continue
                    if event["id"] in self.disabled_events:
                        # Effect-only ablation retains discovery/admission U.
                        # A never-activated event is then exactly identical.
                        continue
                    row = {"id": event["id"], "good": good, "month": month, "country": c, "node": cap,
                           "kind": event["kind"], "pool": event["pool"], "linked": linked, "condition_valid": condition_valid,
                           "condition": event["condition"],'phase':'active' if sim.spreading else 'customs'}
                    row['linked']=proof['linked']
                    if event["effect"] == "boost":
                        evidence=[r['fact_id'] for r in self.country_links.get(c,())]
                        sim.inject(cap, self.config["fixed"]["event_amount"], "event", {"event":event['id'],"facts":evidence})
                    elif event["effect"] in ("multiplier", "ban"):
                        fixed = self.config['fixed']
                        scale = fixed['ban_multiplier'] if event["effect"] == "ban" else fixed["event_multiplier"]
                        if event['effect']=='ban' and not sim.decaying[c] and sim.clock_joined(c) and not any(e.get('policy')=='P3' for e in self.effects.get((good,c),())):
                            sim.apply_ban(c, month, fixed['ban_hold_scale'])
                            sim.U+=5
                        targets=([n for n in self.state.capitals if self.state.countries.get(self.timeline.country_names[n],{}).get('religion')==event['religion_scope']]
                                 if event.get('religion_scope') else [c])
                        for target in targets:
                            sim.U+=5
                            self.effects.setdefault((good,target),[]).append({"good": good, "country": target, "multiplier": scale,
                                             "decay_scale": fixed['ban_decay_scale'] if event["effect"] == "ban" else 1.,
                                             "policy":'P3' if event['effect']=='ban' else None,
                                             "until": month + fixed["event_duration"] * (fixed['ban_duration_scale'] if event["effect"] == "ban" else 1)})
                            sim.country_wake_until[target] = month+self.config["fixed"]["aggregate_slices"]
                        if event["effect"] == "ban":
                            self.bans_this_month.append({"good":good,"country":c,"initial":sim.country_value(c),"event":event['id']})
                    self.event_done.add(key)
                    self.cooldowns[(good, c)] = month + self.config["fixed"]["event_cooldown"]
                    self.global_cooldown[c] = month + self.config["fixed"]["country_cooldown"]
                    self.event_log.append(row)
                    per_event[event["id"]] += 1
        self.eligible_months.append((month, qualified))

    def mechanics_report(self):
        return dict(zone_rejected_inputs={g:s.zone_rejected_inputs for g,s in self.sims.items()},
            zone_values_constant={g:s.zone_values_constant for g,s in self.sims.items()},
            zone_adjacency_arrivals={g:s.zone_adjacency_arrivals for g,s in self.sims.items()},
            zone_sizes={g:len(s.zones) for g,s in self.sims.items()},
            clocks={g:dict(history=s.clock_history,final_deadlines=s.deadline) for g,s in self.sims.items()},
            waves=self.wave_log, fact_contacts=dict(self.fact_contacts), fact_contact_inputs=dict(self.fact_contact_inputs),
            fact_contact_by_good={g:dict(rows) for g,rows in self.fact_contact_by_good.items()},
            ever_member={g:sum(t>=0 for t in s.arrival) for g,s in self.sims.items()},
            peak_U=max(self.ledger,default=0), peak_round_delay_months=max(s.peak_round_delay for s in self.sims.values()),
            events_abandoned_budget=self.events_abandoned_budget,
            clock_counts={g:dict(national=len({r['country'] for r in s.clock_history if r['national_month'] is not None}),
                cap=len({r['country'] for r in s.clock_history if r['national_month'] is None and r['decay_start_month'] is not None}),
                national_episodes=sum(r['national_month'] is not None for r in s.clock_history),
                cap_episodes=sum(r['national_month'] is None and r['decay_start_month'] is not None for r in s.clock_history)) for g,s in self.sims.items()})

    def run(self, progress=None):
        for month in range(self.timeline.start, self.end):
            if self.cancel and self.cancel.is_set():
                raise InterruptedError("simulation cancelled")
            self.inputs_this_month, self.bans_this_month = [], []
            all_sims = self.sims
            before = {g: sim.U for g, sim in all_sims.items()}
            self.month_base_U=before
            for key in list(self.effects):
                self.sims[key[0]].U += 2*len(self.effects[key])
                self.effects[key] = [e for e in self.effects[key] if month < e["until"]]
                if not self.effects[key]:
                    del self.effects[key]
            self.state, changed = self.timeline.at(month)
            if changed:
                self.apply_state()
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
            if self.metrics is not None:
                self.metrics.observe(month, self, self.diagnostics())
            for sim in self.sims.values():
                sim.zone_values_constant &= all(sim.x[v] == value for v,value in sim.zones.items())
            # A first observer snapshot can be in April rather than January.
            # Include that real starting month in replay-only diagnostics.
            if month==self.timeline.start:
                for sim in self.sims.values():
                    if sim.P.frames_every and not sim.frames:
                        sim.frames.append((month,sim.stage_string()))
                    if sim.P.series_every and not sim.series:
                        sim.series.append({**sim.snapshot_counts(),'month':month})
            if progress and month % 120 == 0:
                progress(month, self)
        for sim in self.sims.values():
            if sim.P.frames_every and (not sim.frames or sim.frames[-1][0] != sim.t-1):
                sim.frames.append((sim.t-1, sim.stage_string()))
        return self
