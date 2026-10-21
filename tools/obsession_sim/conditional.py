"""Online diagnostic implementation of specification 20 §6 (never runtime state).

K definitions are frozen JSON. Cases retain only diagnostic observations and
are explicitly censored; unobserved outcomes cannot turn into passes.
"""
from __future__ import annotations

from collections import Counter
import math

import numpy as np

from .worlds import foreign_merchants


class ConditionalEvaluator:
    def __init__(self, definitions, world_kind="R", start_month=0):
        self.definitions = {d["id"]: d for d in definitions}
        self.padding = 120 if world_kind == "O" else 0
        self.start = start_month
        self.cases = []
        self.seen = {key: set() for key in self.definitions}
        self.first = True
        self.origin_countries = {}
        self.initial_raw = {}

    def add(self, kid, key, month, country=None, **extra):
        if key in self.seen[kid]:
            return
        self.seen[kid].add(key)
        if self.first or month == self.start:
            return  # left censored
        definition = self.definitions[kid]
        self.cases.append({"id": kid, "key": str(key), "level": definition["level"], "country": country,
                           "t0": month, "t1": None, "status": "pending", **extra})

    def observe(self, month, state, country_x, market_x, capital_x, raw_countries, inputs=(), bans=(), origin_market=None,
                market_population=None, market_faith=None):
        if self.first:
            self.initial_raw = {g: set(cs) for g, cs in raw_countries.items()}
            for good,x in country_x.items():
                self.origin_countries.setdefault(good,set()).update(int(c) for c in np.flatnonzero(x>=20))
        nonlocal_by_good = {(i["good"], i["country"]) for i in inputs if i["type"] != "adjacency"}
        population = np.bincount(state.owner[state.owner >= 0], weights=state.population[state.owner >= 0])
        existing = [c for c in range(len(population)) if population[c] > 0]
        existing.sort(key=lambda c: (-population[c], c))
        large = set(existing[:math.ceil(.2 * len(existing))])
        first_inputs={}
        for row in inputs:
            if row["type"] in ("contact", "ownership", "event"):
                first_inputs.setdefault((row["good"],row["country"]),row)
        # K1: only the first eligible residency for a country, irrespective of later moves.
        if "coffee" in market_x:
            for m in np.flatnonzero(market_x["coffee"] >= 20):
                for c in foreign_merchants(state, int(m)):
                    cap = state.capitals.get(c)
                    if cap is not None:
                        if c not in large or capital_x["coffee"][c] >= 20 or state.market[cap] == m:
                            self.seen["K1"].add(c)
                        else:
                            self.add("K1", c, month, c, capital=cap, source_market=int(m))
        # K2: first A stage2 with B below stage2, in either direction.
        for a, b in (("coffee", "tea"), ("tea", "coffee")):
            if a not in country_x or b not in country_x:
                continue
            for c in np.flatnonzero((country_x[a] >= 20) & (country_x[b] < 20)):
                self.add("K2", (int(c), a, b), month, int(c), incumbent=a, rival=b,
                         capital=state.capitals.get(int(c)), maximum=float(country_x[b][c]))
        for good, owners in raw_countries.items():
            for c in owners:
                key = (good, c)
                if key in self.seen["K4"]:
                    continue
                if c in self.initial_raw.get(good, set()) or c in self.origin_countries.get(good,set()) or country_x[good][c] >= 1:
                    self.seen["K4"].add(key)
                else:
                    self.add("K4", key, month, c, good=good, capital=state.capitals.get(c))
        for good, c in first_inputs:
            if good == "tobacco":
                before=first_inputs[(good,c)].get("country_x_before",country_x[good][c])
                if c not in large or before >= 20:
                    self.seen["K5"].add(c)
                else:
                    self.add("K5", c, month, c, good=good, capital=state.capitals.get(c))
        for ban in bans:
            c = ban["country"]
            initial=ban.get("initial",float(country_x["tobacco"][c]))
            if ban["good"] == "tobacco" and initial >= 20:
                self.add("K6", (c, month), month, c, capital=state.capitals.get(c),
                         initial=initial, minimum=initial, source=ban.get('event','action'))
        if origin_market is not None and market_x.get("coffee", [0])[origin_market] >= 20:
            if origin_market not in self.seen["K7"]:
                source = state.markets[origin_market]["merchants"].keys()
                faith = market_faith[origin_market] if market_faith else None
                candidates = [m for m in range(len(state.markets)) if m != origin_market and faith is not None
                              and market_faith[m] == faith and set(source) & state.markets[m]["merchants"].keys()]
                candidates.sort(key=lambda m: (-market_population[m], m))
                if len(candidates) < 3:
                    self.seen["K7"].add(origin_market)
                    self.cases.append({"id": "K7", "level": "B", "country": None, "t0": month, "t1": None,
                                       "status": "untriggered", "reason": "fewer than three eligible markets"})
                else:
                    self.add("K7", origin_market, month, None, candidates=candidates[:3], arrivals={})
        for case in self.cases:
            if case["status"] != "pending":
                continue
            kid, c, t0 = case["id"], case.get("country"), case["t0"]
            if kid=='K4' and c in self.origin_countries.get(case['good'],set()):
                case.update(status='untriggered',reason='origin country for this good')
                continue
            if c is not None and (case.get("capital") is None or state.capitals.get(c) != case["capital"]):
                case.update(status="untriggered", reason="country or original capital lost")
                continue
            elapsed = month - t0
            lo, hi = (v * 12 for v in self.definitions[kid]["interval_years"])
            lower, upper = max(0, lo - self.padding), hi + self.padding
            if kid in ("K2", "K6"):
                upper = max(0, hi - self.padding)
            outcome = False
            if kid == "K1":
                outcome = capital_x["coffee"][c] >= 20
            elif kid == "K5":
                outcome = country_x["tobacco"][c] >= 20
            elif kid == "K7":
                for m in case["candidates"]:
                    if market_x["coffee"][m] >= 20:
                        case["arrivals"].setdefault(m, month)
                if len(case["arrivals"]) >= 2:
                    outcome = True
                    month_result = sorted(case["arrivals"].values())[1]
                    elapsed = month_result - t0
            elif kid == "K2":
                case["maximum"] = max(case["maximum"], float(country_x[case["rival"]][c]))
                if country_x[case["incumbent"]][c] < 20:
                    case.update(status="untriggered", reason="incumbent fell below stage2")
                elif case["maximum"] >= 45:
                    case.update(status="fail", t1=month, reason="rival reached stage3")
                elif elapsed >= upper:
                    case.update(status="pass", t1=month) if case["maximum"] >= 1 else case.update(
                        status="untriggered", t1=month, reason="rival never present")
            elif kid == "K4":
                if (case["good"], c) in nonlocal_by_good:
                    case.update(status="untriggered", reason="nonlocal input confounds raw possession")
                elif country_x[case["good"]][c] >= 20 and elapsed < max(0, hi - self.padding):
                    case.update(status="fail", t1=month, reason="raw possession reached stage2 without contact")
                elif elapsed >= upper:
                    case.update(status="pass", t1=month)
            elif kid == "K6":
                case["minimum"] = min(case["minimum"], float(country_x["tobacco"][c]))
                if case["minimum"] < .5 * case["initial"]:
                    case.update(status="fail", t1=month, reason="ban-period minimum fell below half")
                elif elapsed >= upper:
                    case.update(status="pass", t1=month)
            if kid in ("K1", "K5", "K7"):
                if outcome:
                    case.update(status="pass" if lower <= elapsed <= upper else "fail", t1=t0 + elapsed)
                elif elapsed > upper:
                    case.update(status="fail", reason="outcome absent after upper bound")
        self.first = False

    def report(self):
        rows = []
        for kid, definition in self.definitions.items():
            cases = [dict(c, **({"status": "untriggered", "reason": "right censored"}
                               if c["status"] == "pending" else {})) for c in self.cases if c["id"] == kid]
            decided = [c for c in cases if c["status"] in ("pass", "fail")]
            status = ("fail" if any(c["status"] == "fail" for c in decided) else "pass") if decided else "untriggered"
            rows.append({"id": kid, "level": definition["level"], "triggered": bool(decided), "status": status,
                         "pass": status == "pass" if decided else None, "cases": cases,
                         "reason": definition.get("reason") if not definition["enabled"] else None})
        eligible = [r for r in rows if r["triggered"] and r["level"] in ("A", "B")]
        return {"K": rows, "p_K": sum(r["pass"] for r in eligible) / len(eligible) if eligible else None,
                "triggered_K": len(eligible)}
