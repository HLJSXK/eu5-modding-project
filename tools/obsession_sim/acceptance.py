"""Population milestones, diagnostic metrics and conservative matrix gates."""
from __future__ import annotations

from collections import Counter
import math

import numpy as np

from .metrics import resolve_nodes


def q(values, p=.5):
    values = [v for v in values if v is not None and math.isfinite(v)]
    return float(np.quantile(values, p)) if values else None


def moved(a, b, tolerance):
    if a is None and b is None:
        return False
    return a is None or b is None or abs(a-b) > tolerance


def event_dependence(historical, structural):
    rows = [(a, b) for a, b in zip(historical, structural) if a["grade"] in ("A", "B")]
    return sum(moved(a["simulated_month"], b["simulated_month"], a["tolerance_months"]) for a, b in rows) / len(rows) if rows else None


def event_diagnostics(events, eligible_months):
    generic = [e for e in events if e["pool"] == "generic" and e["kind"] == "spread"]
    bursts = {}
    for e in events:
        bursts.setdefault((e["id"], e["month"]), set()).add(e["country"])
    hit = {e["month"] for e in generic}
    gap = longest = 0
    previous = None
    for month, eligible in eligible_months:
        if not eligible or month in hit:
            gap = 0
        else:
            gap = gap+1 if previous == month-1 else 1
            longest = max(longest, gap)
        previous = month
    return {"p_link": sum(e["linked"] for e in generic)/len(generic) if generic else None,
            "B_max": max(map(len, bursts.values()), default=0), "E_gap": longest/12,
            "M_mis": sum(not e["condition_valid"] for e in events if e["pool"] == "historical")}


def coverage_50(arrivals, n):
    months = sorted(t for t in arrivals if t > 0)
    left = maximum = 0
    for right, t in enumerate(months):
        while months[left] <= t-600:
            left += 1
        maximum = max(maximum, right-left+1)
    return maximum/n if n else None


class RunMetrics:
    def __init__(self, graph, targets, kind="R"):
        self.kind = kind
        self.targets = targets if kind == "R" else []
        self.nodes = {r["id"]: resolve_nodes(graph, r) for r in self.targets}
        if any(not vs for vs in self.nodes.values()):
            raise ValueError("regional milestone has an empty selector")
        self.arrivals = {}
        self.arrival_unseeded = {}
        self.arrival_evidence = {}
        self.violations = {}
        self.europe = [i for i, c in enumerate(graph.attrs["continent"]) if c == "europe"]
        self.east_asia = [i for i, c in enumerate(graph.attrs.get("subcontinent", [])) if c == "east_asia"]
        self.europe_set=set(self.europe)
        self.east_asia_set=set(self.east_asia)
        self.outside_america=[i for i,c in enumerate(graph.attrs["continent"]) if c != "america"]
        self.tea_capped = [i for i, r in enumerate(graph.attrs["region"]) if r in ("anatolia_region", "france_region", "italy_region")]
        self.external_first = {}
        self.yearly = []

    def observe(self, month, run, diagnostics):
        country_x, market_x, capital_x, values = diagnostics
        state = run.state
        for row in self.targets:
            if row["id"] in self.arrivals:
                continue
            vs = self.nodes[row["id"]]
            threshold = row["threshold"]
            x, w = values[row["good"]][vs], state.population[vs]
            met = x > 0 if threshold == "positive" else x >= threshold
            if w.sum() > 0 and w[met].sum() >= .5 * w.sum():
                self.arrivals[row["id"]] = month
                sim = run.sims[row["good"]]
                entries = {v for v,t in sim.entries.items() if t <= month}
                near = entries | {u for v in entries for u in sim.g.outgoing[v]}
                downstream = np.array([v not in near for v in vs])
                self.arrival_unseeded[row["id"]] = bool(w[met & downstream].sum() >= .5*w.sum())
                facts=set().union(*(sim.fact_ancestry.get(int(v),()) for v in np.asarray(vs)[met]))
                self.arrival_evidence[row['id']]=sorted(facts)
        if self.kind != "R":
            return
        checks = []
        if month < (1500-1337)*12:
            bad=[c for c,v in state.capitals.items() if v in self.europe_set and country_x["coffee"][c] >= 1]
            if bad:
                self.violations.setdefault("coffee_europe_before_1500", {"month":month,"countries":bad})
        if month < (1650-1337)*12:
            bad=[c for c,v in state.capitals.items() if v in self.east_asia_set and country_x["coffee"][c] >= 20]
            if bad:
                self.violations.setdefault("coffee_east_asia_before_1650", {"month":month,"countries":bad})
        if month < (1800-1337)*12:
            checks.append(("tea_capped_regions", "tea", self.tea_capped, 45))
        for name, good, vs, threshold in checks:
            bad = [v for v in vs if values[good][v] >= threshold]
            if bad:
                self.violations.setdefault(name, {"month": month, "locations": bad[:50], "count": len(bad)})
        for row in run.inputs_this_month:
            if row["good"] in ("tea", "tobacco") and row.get("node") is not None:
                if row["node"] in self.europe_set:
                    self.external_first.setdefault(row["good"], month)
        if "tea" not in self.external_first and np.any(values["tea"][self.europe] > 0):
            self.violations.setdefault("european_tea_without_contact", {"month": month})
        continent=run.timeline.graph.attrs["continent"]
        transatlantic=any(state.owner[v] in state.capitals and continent[v] == "america" and
                         continent[state.capitals[int(state.owner[v])]] != "america" for v in run.raw_nodes["tobacco"])
        if not run.tobacco_possession_seen and not transatlantic and np.any(values["tobacco"][self.outside_america] > 0):
            self.violations.setdefault("tobacco_outside_america_before_possession", {"month":month})
        # Wine is an explicitly modelled, dormant opening custom, with one x.
        wine = run.context_goods["wine"]
        scales=np.array([wine.habit[c]+(1-wine.habit[c])*wine.S[c]
                         if wine.decaying[c] else 1. for c in range(wine.ng)]+[1.])
        wine_values=np.asarray(wine.x)*scales[state.owner]
        from .worlds import weighted_means
        wine_country,_=weighted_means(wine_values,state.owner,state.population,wine.ng)
        for c in np.flatnonzero((country_x["coffee"] >= 45)&(wine_country >= 45)):
            if run.country_faith.get(int(c)) == "muslim":
                self.violations.setdefault("muslim_wine_and_coffee", {"month": month, "country":int(c)})

    def report(self, run):
        rows = []
        for target in self.targets:
            got = self.arrivals.get(target["id"])
            month = round((target["target_year"]-1337)*12)
            error = got-month if got is not None else None
            sim = run.sims[target["good"]]
            vs = self.nodes[target["id"]]
            entries = set(sim.entries)
            near = entries | {u for v in entries for u in sim.g.outgoing[v]}
            evidence=self.arrival_evidence.get(target['id'],[])
            grades=Counter(f['grade'] for f in run.timeline.facts if f['id'] in evidence)
            rows.append({**target, "target_month": month, "simulated_month": got,
                         "simulated_year": 1337+got/12 if got is not None else None,
                         "error_months": error, "locations": len(vs),
                         "within_tolerance": error is not None and abs(error) <= target["tolerance_months"],
                         "within_2tol": error is not None and abs(error) <= 2*target["tolerance_months"],
                         "unseeded": self.arrival_unseeded.get(target["id"], False),
                         "world_evidence":{"facts":evidence,"counts":{g:grades[g] for g in ('W-A','W-B','W-C')},
                                           "trace":"first-membership parent ancestry; not a counterfactual necessity claim"},
                         "scored": not (grades['W-C'] and not (grades['W-A'] or grades['W-B']))})
        result = {"milestones": rows, "violations": list(self.violations.items()), "violation_count": len(self.violations)}
        for split, prefix in ((None, ""), ("fit", "fit_"), ("holdout", "holdout_")):
            eligible = [r for r in rows if r["grade"] in ("A", "B") and r['scored'] and (split is None or r["split"] == split)]
            pairs = [(a,b) for a in eligible for b in eligible if a["good"] == b["good"] and a["target_month"] < b["target_month"]]
            result[prefix+"within_tol"] = sum(r["within_tolerance"] for r in eligible)/len(eligible) if eligible else None
            result[prefix+"within_2tol"] = sum(r["within_2tol"] for r in eligible)/len(eligible) if eligible else None
            result[prefix+"p_order"] = sum(a["simulated_month"] is not None and b["simulated_month"] is not None
                                          and a["simulated_month"] <= b["simulated_month"] for a,b in pairs)/len(pairs) if pairs else None
            missing = sum(r["simulated_month"] is None for r in eligible)
            result[prefix+"loss_missing"] = missing
            result[prefix+"loss_infinite"] = bool(missing)
            result[prefix+"loss"] = (sum((r["error_months"]/r["tolerance_months"])**2 for r in eligible)/len(eligible)
                                    if eligible and not missing else None)
        arrived = [r for r in rows if r["grade"] in ("A", "B") and r["simulated_month"] is not None]
        result["p_unseeded"] = sum(r["unseeded"] for r in arrived)/len(arrived) if arrived else None
        new = [(sim,v) for sim in run.sims.values() for v,t in enumerate(sim.arrival)
               if t >= run.timeline.start and sim.arrival_kind[v] != 'opening']
        result["p_conn"] = sum(any(sim.arrival[u] >= 0 and sim.arrival[u] <= sim.arrival[v] for u in sim.g.incoming[v])
                               for sim,v in new)/len(new) if new else None
        result.update(run.evaluator.report())
        ban_cases=next(r["cases"] for r in result["K"] if r["id"] == "K6")
        decided_bans=[c for c in ban_cases if c["status"] in ("pass","fail")]
        result["ban_trials"]={"observed":len(decided_bans),"censored":len(ban_cases)-len(decided_bans),
            "failure_rate":sum(c["status"]=="pass" for c in decided_bans)/len(decided_bans) if decided_bans else None,
            "interpretation":"ban failed when intensity remained at least half over the specified observation window"}
        result.update(event_diagnostics(run.event_log, run.eligible_months))
        sanity = {}
        for good, sim in run.sims.items():
            if sim.external_stage2 is not None:
                alive = (sim.external_stage2-sim.first_wave_start)/12
            elif sim.first_wave_start is not None and sim.t-sim.first_wave_start >= 1200:
                alive = float("inf")
            else:
                alive = None
            sanity[good] = {"V_land": q(sim.land_speeds), "C50": coverage_50(
                [t-run.timeline.start+1 if t >= 0 and sim.arrival_kind[v] != "opening" else -1
                 for v,t in enumerate(sim.arrival)], sim.n),
                            "T_alive": alive if alive != float("inf") else None,
                            "T_alive_failed": alive == float("inf"), "origin_countries": sorted(map(int,sim.origin_groups or ())) }
        meaningful = any(any(row[k] is not None for k in ("V_land", "C50", "T_alive")) or row["T_alive_failed"]
                         for row in sanity.values())
        result["healthy"] = (all((r["V_land"] is None or r["V_land"] <= 1.5) and r["C50"] <= .5 and
                                  not r["T_alive_failed"] and (r["T_alive"] is None or r["T_alive"] <= 100)
                                  for r in sanity.values()) if meaningful else None)
        result.update(sanity=sanity, peak_U=max(run.ledger, default=0), total_U=sum(run.ledger),
                      overruns=run.overruns, wave_years=max((b-a)/12 for s in run.sims.values() for a,b in s.waves) if any(s.waves for s in run.sims.values()) else 0,
                      events=run.event_log, summaries={g:s.summary() for g,s in run.sims.items()})
        return result


def aggregate_runs(runs, kind="R"):
    out = {"run_count": len(runs), "runs": runs}
    metrics = ("within_tol", "within_2tol", "p_order", "fit_within_tol", "fit_within_2tol", "fit_p_order",
               "holdout_within_tol", "holdout_within_2tol", "p_unseeded", "p_conn", "p_K", "p_link", "E_gap", "D_event")
    for key in metrics:
        out[key] = q([r.get(key) for r in runs])
        out[key+"_p10"] = q([r.get(key) for r in runs], .1)
        out[key+"_p90"] = q([r.get(key) for r in runs], .9)
    out["violation_count"] = max((r["violation_count"] for r in runs), default=0)
    out["healthy_rate"] = sum(r["healthy"] is True for r in runs)/len(runs) if runs and any(r["healthy"] is not None for r in runs) else None
    for key in ("B_max", "peak_U", "wave_years"):
        out[key] = max((r.get(key, 0) for r in runs), default=0)
    out["M_mis"] = sum(r.get("M_mis", 0) for r in runs)
    out["triggered_K_median"] = q([r.get("triggered_K") for r in runs])
    for prefix in ("","fit_","holdout_"):
        out[prefix+"loss_infinite_runs"] = sum(r.get(prefix+"loss_infinite",False) for r in runs)
        for label,percentile in (("p10",.1),("median",.5),("p90",.9)):
            # An infinite missing-target loss must not disappear from quantiles.
            losses = sorted(float("inf") if r.get(prefix+"loss_infinite") else r[prefix+"loss"]
                            for r in runs if r.get(prefix+"loss") is not None or r.get(prefix+"loss_infinite"))
            value = losses[min(len(losses)-1,math.ceil(percentile*len(losses))-1)] if losses else None
            out[prefix+"loss_"+label] = value if value is not None and math.isfinite(value) else None
            out[prefix+"loss_"+label+"_infinite"] = value is not None and not math.isfinite(value)
    out["K_determinable"] = kind != "O" or (out["triggered_K_median"] is not None and out["triggered_K_median"] >= 3)
    if not out["K_determinable"]:
        out["p_K"] = out["p_K_p10"] = None
    return out


def gates(cells, spec, *, frozen_valid, world_count, independent_worlds=0, complete_protocol=True):
    result = {}
    for level, requirements in spec["thresholds"].items():
        requirements = {cell: dict(thresholds) for cell, thresholds in requirements.items()}
        if level == "L3":
            requirements["H×R"] = {**spec["thresholds"]["L2"]["H×R"], **requirements["H×R"]}
        failures, missing = [], []
        if not frozen_valid:
            missing.append("frozen input hash changed")
        if not complete_protocol:
            missing.append("requires fixed seeds 0–29")
        if sum(d["enabled"] and d["level"] in ("A","B") for d in spec["K"]) < 5:
            missing.append("fewer than five eligible K definitions")
        if level in ("L2", "L3") and world_count < 1:
            missing.append("no observer world")
        if level == "L3" and (independent_worlds < 1 or world_count < 2):
            missing.append("no second independent, untuned observer world")
        details = {}
        for cell, thresholds in requirements.items():
            data = cells.get(cell)
            issues = []
            if data is None:
                missing.append(cell+": missing cell")
                details[cell] = ["missing cell"]
                continue
            for name, threshold in thresholds.items():
                maximum = name.endswith("_max")
                key = name[:-4] if maximum else name
                if key == "violations":
                    key = "violation_count"
                # L2/L3 main timing metrics use ONLY the fit split.
                actual_key = "fit_"+key if cell.endswith("×R") and cell != "F×R" and level != "L1" and key in ("within_tol","within_2tol","p_order","within_tol_p10") else key
                value = data.get(actual_key)
                if value is None:
                    missing.append(cell+": "+name+" unavailable")
                    issues.append(name+" unavailable")
                elif value > threshold if maximum else value < threshold:
                    failures.append(f"{cell}: {name}={value:.4g}, requires {'≤' if maximum else '≥'}{threshold}")
                    issues.append(f"{name}={value:.4g}")
            details[cell] = issues
        result[level] = {"status": "无法判定" if missing else "未达" if failures else "达到",
                         "failures": failures, "missing": missing, "cells": details}
    return result
