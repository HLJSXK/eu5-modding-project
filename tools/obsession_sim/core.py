"""Monthly simulation core for the obsession system.

Game-state contract (what the EU5 implementation may persist):
  per location x good : x (float) and, only while queued, the queue pointer q
  per clock group x good : join month, decaying flag, finished flag, lazy factor S
  per good : queue head/tail/length/round_remaining, shared parameters
Everything else recorded here (arrival month, peak x, frames, series) is
simulator diagnostics for calibration and is NOT game state.

Update rule for a served location v (current plan):
  y = rho_v * x_v + sum_u p_v * w_uv * x_eff(u),   clamp to [0, 100], y < eps -> 0
  write and enqueue self + out-neighbours only if |y - x_v| > delta or y hits 0
x_eff(u) = x_u * S[group(u)] when u's group is decaying, else x_u.

Decay ("退潮") modes:
  country_clock  current plan: a group joins when its first location reaches
                 x >= 1; after hold_T months the whole group decays lazily
                 (S <- factor * S each month, renormalise below 0.1) and its
                 locations stop receiving input. With habit_floor h > 0 the
                 effective value is x * (h + (1-h) S) and the group settles at
                 h * x (custom) once S < habit_finish_S.
  none           growth only.
  global_node    comparison: from global_decay_start every location switches
                 to (global_rho, global_p) and is served node by node.
  global_lazy    comparison: from global_decay_start the whole good decays by
                 one shared S (factor = global_rho + 6 * global_p).

Abstract U pricing reproduces the experiment scripts so that results stay
comparable: PRICE_QUEUE for modes without clocks, PRICE_CLOCK for
country_clock (it adds the owner / S lookups). These are offline counts, not
EU5 instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

EPS_ZERO = 0.00001

PRICE_QUEUE = {"serve_fixed": 3 + 8, "per_in_edge": 4, "changed_fixed": 1, "per_out_edge": 1,
               "push_new": 4, "push_pending": 1, "push_rejected": 0}
PRICE_CLOCK = {"serve_fixed": 5 + 8, "per_in_edge": 6, "changed_fixed": 1, "per_out_edge": 1,
               "push_new": 6, "push_pending": 3, "push_rejected": 2,
               "clock_active": 2, "clock_tick": 1, "renorm_per_node": 4, "join_write": 2}


@dataclass
class Params:
    rho: float = 0.99
    p: float = 0.02
    delta: float = 0.1
    eps: float = EPS_ZERO
    decay: str = "country_clock"            # country_clock | none | global_node | global_lazy
    hold_T: int = 240
    decay_factor: float = 0.98
    habit_floor: float = 0.0                # share of x kept as custom after decay (per good, shared)
    habit_finish_S: float = 0.01            # with habit_floor > 0: settle the group once S drops below this
    global_decay_start: int = -1
    global_rho: float = 0.95
    global_p: float = 0.005
    seeds: list = field(default_factory=list)   # [(node, month, value)]; month-0 seeds are unpriced initial state
    init_all: float = 0.0                       # >0: every location starts at this x and is queued
    rho_by_node: list | None = None             # per-location overrides (static geography / policy)
    p_by_node: list | None = None
    max_months: int = 3000
    budget: int | None = None                   # node-service admission limit; clock/seed work may exceed it
    stop_when_calm: bool = True
    frames_every: int = 0                       # >0: record stage frames for playback every k months
    series_every: int = 1                       # record O(N) counts every k months (1 for small maps)
    initial_values: list = field(default_factory=list)  # existing customs, no growth queue
    input_events: list = field(default_factory=list)    # finite shared inputs / topology changes
    spread_windows: list | None = None                # half-open month intervals; clocks keep ticking
    constraints: list = field(default_factory=list)    # offline checks only; never engine state
    coefficient_cost: int = 0                         # optional conservative 10+d input evaluation audit


class Simulation:
    def __init__(self, graph, params: Params):
        self.g = graph
        self.P = params
        n = graph.n
        self.n = n
        self.x = [0.0] * n
        self.q = [-1] * n
        self.head = self.tail = -1
        self.length = 0
        self.round_remaining = 0
        self.rho = list(params.rho_by_node) if params.rho_by_node else [params.rho] * n
        self.pp = list(params.p_by_node) if params.p_by_node else [params.p] * n
        self.w = graph.in_weight
        self.clock = params.decay == "country_clock"
        if self.clock and graph.owner is None:
            raise ValueError("country_clock needs graph.owner (clock groups)")
        self.price = PRICE_CLOCK if self.clock else PRICE_QUEUE
        self.owner = graph.owner if graph.owner is not None else [-1] * n
        ng = graph.n_groups if graph.owner is not None else 0
        self.ng = ng
        self.init_country_clocks(ng)
        self.decay_start = [-1] * ng
        self.finished_month = [-1] * ng
        self.S = [1.0] * ng
        # Shared clock-group parameter. It equals the good's kappa except when
        # rebasing a lazy scale to preserve one bounded x during ownership IO.
        self.habit = [params.habit_floor] * ng
        self.decaying = [False] * ng
        self.finished = [False] * ng
        self.members_of = [[] for _ in range(ng)]
        for v in range(n):
            if self.owner[v] >= 0:
                self.members_of[self.owner[v]].append(v)
        self.phase = "growth"
        self.gS = 1.0
        self.g_factor = None
        self.t = 0
        self.U = 0
        self.rounds = 0
        self.peak_queue = 0
        self.peak_month_U = 0
        self.calm_month = None
        self.done = False
        self.arrival = [-1] * n         # diagnostics: first month x >= 1
        self.first_positive = [-1] * n
        self.threshold_arrival = {1: self.arrival, **{a: [-1] * n for a in (20, 45, 70, 100)}}
        self.peak_x = [0.0] * n
        self.peak_t = [-1] * n
        self.series = []
        self.frames = []
        self.month_U = []
        self.served_last = 0
        # Shared input configuration, not per-location pressure/history caches.
        self.events = sorted(params.input_events, key=lambda row: row["month"])
        self.event_cursor = 0
        self.sources = {}
        self.spreading = params.spread_windows is None or any(a <= 0 < b for a, b in params.spread_windows)
        self.input_log = []                 # offline audit only
        self.arrival_parent = [-1] * n       # offline connectivity diagnostic only
        self.peak_round_delay = 0
        self.round_started = 0
        self.constraint_violations = [dict() for _ in params.constraints]
        self.constraint_nodes = [set(row["nodes"]) for row in params.constraints]
        for v, value in params.initial_values:
            self.x[v] = float(value)
            self._note(v, self.x[v], 0)
        seeds = sorted(params.seeds, key=lambda s: s[1])
        self.pending = [s for s in seeds if s[1] > 0]
        if params.init_all > 0:
            for v in range(n):
                self.x[v] = params.init_all
                self._note(v, self.x[v], 0)
                self._push(v)
        for v, m, val in seeds:
            if m <= 0:
                self.x[v] = max(self.x[v], float(val))
                self._note(v, self.x[v], 0)
                self._push(v)
                for u in graph.outgoing[v]:
                    self._push(u)

    # ---- queue (transient pointer q; tail points to itself) ----
    def _push(self, v):
        if not self.spreading:
            return self.price["push_rejected"]
        c = self.owner[v]
        if self.clock and c >= 0 and self.decaying[c]:
            return self.price["push_rejected"]
        if self.q[v] != -1:
            return self.price["push_pending"]
        self.q[v] = v
        if self.length == 0:
            self.head = v
        else:
            self.q[self.tail] = v
        self.tail = v
        self.length += 1
        return self.price["push_new"]

    def _pop(self):
        v = self.head
        if self.length == 1:
            self.head = self.tail = -1
        else:
            self.head = self.q[v]
        self.q[v] = -1
        self.length -= 1
        return v

    def eff(self, v):
        if self.phase == "lazy":
            return self.x[v] * self.gS
        c = self.owner[v]
        if self.clock and c >= 0 and self.decaying[c]:
            h = self.habit[c]
            if h <= 0:
                return self.x[v] * self.S[c]
            return self.x[v] * (h + (1 - h) * self.S[c])
        return self.x[v]

    def _note(self, v, y, t):
        for i, check in enumerate(self.P.constraints):
            if t < check["before_month"] and v in self.constraint_nodes[i] and (
                    y > 0 if check["threshold"] == "positive" else y >= check["threshold"]):
                self.constraint_violations[i].setdefault(v, t)
        if y > 0 and self.first_positive[v] < 0:
            self.first_positive[v] = t
        for threshold, arrivals in self.threshold_arrival.items():
            if y >= threshold and arrivals[v] < 0:
                arrivals[v] = t
                if threshold == 1:
                    weights = self.g.in_weight[v] if self.g.in_weight else [1] * len(self.g.incoming[v])
                    parents = [u for u, w in zip(self.g.incoming[v], weights)
                               if w > 0 and self.arrival[u] >= 0 and self.eff(u) > 0]
                    if parents:
                        self.arrival_parent[v] = parents[0]
        if y > self.peak_x[v]:
            self.peak_x[v] = y
            self.peak_t[v] = t

    def reservation(self, v):
        pr = self.price
        d_in, d_out = len(self.g.incoming[v]), len(self.g.outgoing[v])
        return (pr["serve_fixed"] + pr["per_in_edge"] * d_in + pr["changed_fixed"] + pr["per_out_edge"] * d_out
                + pr["push_new"] * (1 + d_out) + (pr.get("join_write", 0))
                + (2 if self.sources else 0)
                + (self.P.coefficient_cost + d_in if self.P.coefficient_cost else 0))

    def _inputs(self, t):
        """Process changes once, wake affected targets even if sources are stationary.

        Edges are inserted only while open: closed routes add no per-service reads
        or fan-out. No all-world monthly route/source discovery pass is used.
        """
        if self.P.spread_windows is not None:
            spreading = any(a <= t < b for a, b in self.P.spread_windows)
            self.U += len(self.P.spread_windows)  # shared calendar checks
            if self.spreading and not spreading:
                while self.length:
                    self._pop()
                    self.U += 3
                self.round_remaining = 0
            self.spreading = spreading
        while self.event_cursor < len(self.events) and self.events[self.event_cursor]["month"] <= t:
            row = self.events[self.event_cursor]
            self.event_cursor += 1
            kind = row["kind"]
            self.U += 1
            if kind == "edge":
                u, v, weight = row["from"], row["to"], row["weight"]
                inc = list(self.g.incoming[v])
                weights = list(self.g.in_weight[v])
                out = list(self.g.outgoing[u])
                if u in inc:
                    k = inc.index(u)
                    if weight:
                        weights[k] = weight
                    else:
                        inc.pop(k); weights.pop(k); out.remove(v)
                elif weight:
                    inc.append(u); weights.append(weight); out.append(v)
                self.g.incoming[v], self.g.in_weight[v], self.g.outgoing[u] = tuple(inc), tuple(weights), tuple(out)
                self.U += 3 + len(inc) + len(out) + self._push(v)
            elif kind == "source":
                v = row["node"]
                if row["amount"]:
                    self.sources[v] = row["amount"]
                else:
                    self.sources.pop(v, None)
                self.U += 1 + self._push(v)
            elif kind == "wake":
                for v in row["nodes"]:
                    self.U += 1 + self._push(v)
            elif kind == "renew":
                for c in sorted({self.owner[v] for v in row["nodes"] if self.owner[v] >= 0}):
                    # A new wave renews group timing, never the local intensity.
                    # Materialise effective x first so resetting S cannot jump x.
                    if self.decaying[c] and not self.finished[c]:
                        for v in self.members_of[c]:
                            self.x[v] = self.eff(v)
                            self.U += 4
                    self.join[c] = -1
                    self.S[c] = 1.0
                    self.habit[c] = self.P.habit_floor
                    self.decaying[c] = self.finished[c] = False
                    self.U += 5
                for v in row["nodes"]:
                    self.U += 1 + self._push(v)
            elif kind == "contact":
                self.U += 3
                v = row["to"]
                if self.eff(row["from"]) >= row["minimum"]:
                    self.x[v] = max(self.x[v], row["value"])
                    self._note(v, self.eff(v), t)
                    self.U += 1 + self._push(v)
                    for u in self.g.outgoing[v]:
                        self.U += self._push(u)
            elif kind == "coefficient":
                for v in row["nodes"]:
                    if "p" in row:
                        self.pp[v] = row["p"]
                    if "rho" in row:
                        self.rho[v] = row["rho"]
                    self.U += 2
                    if row.get("p", self.pp[v]) > 0 or self.x[v] > 0:
                        self.U += self._push(v)
            else:
                raise ValueError(f"unknown input event kind: {kind}")
            self.input_log.append({"month": t, **row})
        # Only a finite set of origin inputs is polled. A sub-delta force may
        # not otherwise keep its node alive; every wake/read is charged.
        for v in self.sources:
            self.U += 1 + self._push(v)

    # ---- one month ----
    def step(self):
        if not self.begin_month():
            return False
        return self.serve_month()

    def begin_month(self):
        """Run shared inputs/clocks first, so a batch can reserve all maintenance."""
        if self.done:
            return False
        P, g, t = self.P, self.g, self.t
        if t >= P.max_months:
            self.done = True
            return False
        U0 = self.U
        self.month_start_U = U0
        if self.events or self.sources or P.spread_windows is not None:
            self._inputs(t)
        # scheduled external seeds (events, actions, fashions): priced write + pushes
        while self.pending and self.pending[0][1] <= t:
            v, _, val = self.pending.pop(0)
            if self.phase == "lazy":
                self.x[v] = max(self.x[v] * self.gS, float(val)) / self.gS
                self._note(v, self.eff(v), t)
                continue
            self.x[v] = max(self.x[v], float(val))
            self._note(v, self.eff(v), t)
            self.U += 1 + self._push(v)
            for u in g.outgoing[v]:
                self.U += self._push(u)
        # comparison modes: global decay switch
        if P.decay in ("global_node", "global_lazy") and self.phase == "growth" and 0 <= P.global_decay_start <= t:
            self._enter_global_decay()
        if self.phase == "lazy":
            self._lazy_tick()
            return True
        # country clocks
        if self.clock:
            self._clocks(t)
        return True

    def serve_month(self):
        """Complete a prepared month. P.budget includes this good's maintenance."""
        P, g, t, U0 = self.P, self.g, self.t, self.month_start_U
        if self.phase == "lazy":
            self._finish_month(U0, 0)
            return True
        # node service: at most one logical round per month
        if self.round_remaining == 0:
            self.round_remaining = self.length
            if self.length:
                self.rounds += 1
                self.round_started = t
        self.peak_queue = max(self.peak_queue, self.length)
        served = 0
        budget = P.budget
        while self.round_remaining:
            v = self.head
            if budget is not None and (self.U - U0) + self.reservation(v) > budget:
                break
            self._serve(t)
            self.round_remaining -= 1
            served += 1
        if self.round_remaining:
            self.peak_round_delay = max(self.peak_round_delay, t - self.round_started + 1)
        self._finish_month(U0, served)
        # termination
        if P.stop_when_calm and self.event_cursor == len(self.events) and not self.sources:
            if self.clock:
                if t > 0 and self.length == 0 and not self.pending and all(
                        self.finished[c] or not self.clock_joined(c) for c in range(self.ng)):
                    self.calm_month = t
                    self.done = True
            elif self.length == 0 and not self.pending and self.phase != "lazy" and not (
                    P.decay in ("global_node", "global_lazy") and self.phase == "growth" and P.global_decay_start > t):
                self.calm_month = t
                self.done = True
        return True

    def _serve(self, t):
        g, pr = self.g, self.price
        v = self._pop()
        c = self.owner[v]
        if self.clock and c >= 0 and self.decaying[c]:
            self.U += pr["serve_fixed"] - 8
            return
        inc = g.incoming[v]
        d = len(inc)
        old = self.x[v]
        p = self.pp[v]
        p, retention, shared_input = self.local_terms(v, p, self.rho[v],old)
        y = retention * old + shared_input
        if self.sources:
            y += self.sources.get(v, 0.0)
            self.U += 2
        if self.w is None:
            if self.clock:
                for u in inc:
                    y += p * self.eff(u)
            else:
                xx = self.x
                for u in inc:
                    y += p * xx[u]
        else:
            ws = self.w[v]
            for k, u in enumerate(inc):
                y += p * ws[k] * self.eff(u)
        if y > 100:
            y = 100.0
        if y < self.P.eps:
            y = 0.0
        self.U += pr["serve_fixed"] + pr["per_in_edge"] * d
        if self.P.coefficient_cost:
            self.U += self.P.coefficient_cost + d
        if abs(y - old) > self.P.delta or (y == 0.0 and old != 0.0):
            self.x[v] = y
            outs = g.outgoing[v]
            self.U += pr["changed_fixed"] + pr["per_out_edge"] * len(outs) + self._push(v)
            for u in outs:
                self.U += self._push(u)
            self._note(v, y, t)
        # A seeded member can be stationary (delta suppresses its write). It
        # still joins, dated by first adoption rather than delayed queue service.
        if self.clock and c >= 0 and not self.clock_joined(c) and self.x[v] >= 1:
            # Runtime never reads offline arrival history. An explicit member
            # seed already supplied its month in the shared event definition;
            # new propagation and reawakened customs join when actually served.
            wave_start = (max(a for a, b in self.P.spread_windows if a <= t < b)
                          if self.P.spread_windows is not None else 0)
            configured = [max(0, month) for node, month, value in self.P.seeds
                          if node == v and value >= 1 and wave_start <= max(0, month) <= t]
            self.clock_first_touch(c, min([t] + configured))
            self.U += pr["join_write"]

    def local_terms(self, v, p, retention, old=None):
        """Optional structural rules; default preserves the reference experiments."""
        return p, retention, 0.0

    def init_country_clocks(self, count):
        self.join = [-1] * count

    def clock_first_touch(self, country, month):
        self.join[country] = month

    def clock_due(self, country, month):
        return month >= self.join[country] + self.P.hold_T

    def materialize_node(self, node):
        return True

    def _clocks(self, t):
        pr = self.price
        for c in range(self.ng):
            if self.finished[c] or not self.clock_joined(c):
                continue
            self.U += pr["clock_active"]
            if not self.decaying[c] and self.clock_due(c, t):
                self.decaying[c] = True
                self.decay_start[c] = t
                self.S[c] = 1.0
            if self.decaying[c]:
                multiplier = self.clock_decay_multiplier(c)
                self.S[c] *= self.P.decay_factor if multiplier == 1 else self.P.decay_factor ** multiplier
                self.U += pr["clock_tick"]
                h = self.habit[c]
                if h > 0:
                    cut = self.P.habit_finish_S
                    original = self.P.habit_floor
                    if h != original and 0 < original < 1 and h < 1:
                        # Convert the original cutoff to the rebased S axis.
                        cut /= original*(1-h)/(h*(1-original))
                        self.U += 6
                    if self.S[c] < cut:      # settle: keep the custom share, stop ticking
                        k = h + (1 - h) * self.S[c]
                        for v in self.members_of[c]:
                            if not self.materialize_node(v):
                                continue
                            self.U += pr["renorm_per_node"]
                            y = self.x[v] * k
                            self.x[v] = y if y >= self.P.eps else 0.0
                        self.S[c] = 1.0
                        self.finished[c] = True
                        self.finished_month[c] = t

                elif self.S[c] < 0.1:
                    alive = False
                    Sc = self.S[c]
                    for v in self.members_of[c]:
                        if not self.materialize_node(v):
                            continue
                        self.U += pr["renorm_per_node"]
                        y = self.x[v] * Sc
                        self.x[v] = y if y >= self.P.eps else 0.0
                        alive = alive or self.x[v] > 0
                    self.S[c] = 1.0
                    if not alive:
                        self.finished[c] = True
                        self.finished_month[c] = t

    def clock_decay_multiplier(self, country):
        return 1

    def clock_joined(self, country):
        return self.join[country] >= 0

    def _enter_global_decay(self):
        P = self.P
        gain = P.global_rho + 6 * P.global_p
        if P.decay == "global_lazy":
            while self.length:
                self._pop()
                self.U += 3
            self.round_remaining = 0
            self.gS = 1.0
            self.g_factor = gain
            self.phase = "lazy"
            return
        for v in range(self.n):
            self.rho[v] = P.global_rho
            self.pp[v] = P.global_p
            self.U += 2
            if self.x[v] > 0:
                self.U += self._push(v)
        self.phase = "decay"

    def _lazy_tick(self):
        self.gS *= self.g_factor
        self.U += 1
        if self.gS < 0.1:
            alive = False
            for v in range(self.n):
                self.U += 2
                if self.x[v] > 0:
                    y = self.x[v] * self.gS
                    self.x[v] = y if y >= self.P.eps else 0.0
                    self.U += 2
                    alive = alive or self.x[v] > 0
            self.gS = 1.0
            if not alive and not self.pending:
                self.calm_month = self.t
                self.done = True

    def _finish_month(self, U0, served):
        mu = self.U - U0
        self.month_U.append(mu)
        self.peak_month_U = max(self.peak_month_U, mu)
        self.served_last = served
        t = self.t
        P = self.P
        if P.series_every and t % P.series_every == 0:
            self.series.append(self.snapshot_counts())
        if P.frames_every and t % P.frames_every == 0:
            self.frames.append((t, self.stage_string()))
        self.t += 1

    # ---- observation helpers (diagnostics, O(N)) ----
    def snapshot_counts(self):
        mem = hot = sat = pos = 0
        for v in range(self.n):
            a = self.eff(v)
            if a > 0:
                pos += 1
                if a >= 1:
                    mem += 1
                    if a >= 45:
                        hot += 1
                        if a >= 100:
                            sat += 1
        dec = sum(1 for c in range(self.ng) if self.decaying[c] and not self.finished[c])
        return {"month": self.t, "served": self.served_last, "queue": self.length, "U": self.month_U[-1],
                "positive": pos, "members": mem, "x_ge_45": hot, "saturated": sat, "decaying_groups": dec}

    def stage_string(self):
        """One char per node: 'a'+stage (0..6), +7 if its clock group is decaying."""
        out = []
        for v in range(self.n):
            a = self.eff(v)
            s = 0 if a <= 0 else 1 if a < 1 else 2 if a < 20 else 3 if a < 45 else 4 if a < 70 else 5 if a < 100 else 6
            c = self.owner[v]
            if (self.clock and c >= 0 and self.decaying[c]) or self.phase == "lazy":
                s += 7
            out.append(chr(97 + s))
        return "".join(out)

    def run(self):
        while self.step():
            pass
        if self.P.frames_every and self.t and (not self.frames or self.frames[-1][0] != self.t - 1):
            self.frames.append((self.t - 1, self.stage_string()))
        return self

    def summary(self):
        final = self.snapshot_counts()
        ever = sum(1 for a in self.arrival if a >= 0)
        active = [u for u in self.month_U if u > 0]
        return {"months": self.t, "rounds": self.rounds, "total_U": self.U, "peak_queue": self.peak_queue,
                "peak_monthly_U": self.peak_month_U,
                "mean_monthly_U_active": round(sum(active) / len(active)) if active else 0,
                "calm_month": self.calm_month, "ever_member": ever,
                "final_members": final["members"], "final_saturated": final["saturated"],
                "final_positive": final["positive"],
                "groups_joined": sum(self.clock_joined(c) for c in range(self.ng)),
                "groups_finished": sum(self.finished),
                "peak_round_delay_months": self.peak_round_delay,
                "input_events_processed": self.event_cursor}


def simulate(graph, params: Params) -> Simulation:
    return Simulation(graph, params).run()
