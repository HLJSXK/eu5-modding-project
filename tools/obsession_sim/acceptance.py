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


def order_correct(earlier, later):
    return earlier is not None and (later is None or earlier <= later)


def event_diagnostics(events, eligible_months, candidate_bursts=()):
    generic = [e for e in events if e["pool"] == "generic" and e["kind"] == "spread"]
    bursts = {}
    for e in events:
        bursts.setdefault((e["id"], e["month"]), set()).add(e["country"])
    gaps = {}
    goods = {e.get("good", "all") for e in generic}
    goods.update(g for _, row in eligible_months for g in (row if isinstance(row, dict) else ["all"]))
    for good in sorted(goods):
        hit = {e["month"] for e in generic if e.get("good", "all") == good}
        gap = longest = qualified = 0
        previous = None
        for month, row in eligible_months:
            eligible = row.get(good, False) if isinstance(row, dict) else row
            qualified += bool(eligible)
            if not eligible or month in hit:
                gap = 0
            else:
                gap = gap+1 if previous == month-1 else 1
                longest = max(longest, gap)
            previous = month
        gaps[good] = longest/12 if qualified else None
    determined = [v for v in gaps.values() if v is not None]
    return {"p_link": sum(e["linked"] for e in generic)/len(generic) if generic else None,
            "B_max": max(candidate_bursts, default=max(map(len, bursts.values()), default=0)),
            "E_gap": max(determined) if determined else None, "E_gap_by_good": gaps,
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
        self.arrival_unseeded_evidence = {}
        self.arrival_evidence = {}
        self.violations = {}
        self.europe = [i for i, c in enumerate(graph.attrs["continent"]) if c == "europe"]
        self.east_asia = [i for i, c in enumerate(graph.attrs.get("subcontinent", [])) if c == "east_asia"]
        self.europe_set=set(self.europe)
        self.east_asia_set=set(self.east_asia)
        self.outside_america=[i for i,c in enumerate(graph.attrs["continent"]) if c != "america"]
        self.tea_regions={region:[i for i,r in enumerate(graph.attrs['region']) if r==region]
                          for region in ('anatolia_region','france_region','italy_region')}
        self.tea_local_hotspots={}
        self.external_first = {}
        self.contact_evidence={}
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
                attained=float(w[met].sum());away=float(w[met & downstream].sum())
                self.arrival_unseeded[row["id"]] = bool(away >= .5*attained)
                self.arrival_unseeded_evidence[row['id']]={'attained_population':attained,'downstream_population':away,
                    'downstream_share':away/attained,'region_population':float(w.sum()),
                    'old_all_population_test':bool(away>=.5*w.sum())}
                facts=set().union(*(sim.fact_ancestry.get(int(v),()) for v in np.asarray(vs)[met]))
                self.arrival_evidence[row['id']]=sorted(facts)
        if self.kind != "R":
            return
        if month < (1500-1337)*12:
            bad=[c for c,v in state.capitals.items() if v in self.europe_set and country_x["coffee"][c] >= 1]
            if bad:
                self.violations.setdefault("coffee_europe_before_1500", {"month":month,"countries":bad})
        if month < (1650-1337)*12:
            bad=[c for c,v in state.capitals.items() if v in self.east_asia_set and country_x["coffee"][c] >= 20]
            if bad:
                self.violations.setdefault("coffee_east_asia_before_1650", {"month":month,"countries":bad})
        for region,vs in self.tea_regions.items():
            if region=='anatolia_region' and month>=(1800-1337)*12:
                continue
            x,w=values['tea'][vs],state.population[vs]
            high=x>=45
            if np.any(high):
                self.tea_local_hotspots.setdefault(region,{'month':month,'locations':np.asarray(vs)[high].tolist()[:50]})
            if w.sum()>0 and w[high].sum()>=.5*w.sum():
                self.violations.setdefault('tea_stage3_'+region,{'month':month,'region':region,
                    'population_share':float(w[high].sum()/w.sum()),'locations':np.asarray(vs)[high].tolist()[:50]})
        for row in run.inputs_this_month:
            if row["good"] in ("tea", "tobacco") and row.get("node") is not None:
                if row["node"] in self.europe_set:
                    self.external_first.setdefault(row["good"], month)
                    self.contact_evidence.setdefault(row['good'],{'month':month,'type':row['type'],'node':row['node']})
        tea=run.sims['tea']
        if 'tea' not in self.external_first and tea.spreading:
            for v in self.europe:
                c=int(state.owner[v])
                if values['tea'][v]<=0 or tea.pp[v]<=0 or (c>=0 and tea.decaying[c]):
                    continue
                for k,u in enumerate(tea.g.incoming[v]):
                    weight=tea.w[v][k] if tea.w else 1.
                    if u not in self.europe_set and weight>0 and values['tea'][u]>0:
                        self.external_first['tea']=month
                        self.contact_evidence['tea']={'month':month,'type':'adjacency','node':v,'source_node':u}
                        break
                if 'tea' in self.external_first:break
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
                         'unseeded_evidence':self.arrival_unseeded_evidence.get(target['id']),
                         "world_evidence":{"facts":evidence,"counts":{g:grades[g] for g in ('W-A','W-B','W-C')},
                                           "trace":"first-membership parent ancestry; not a counterfactual necessity claim"},
                         "scored": True})
        result = {"milestones": rows, "violations": list(self.violations.items()), "violation_count": len(self.violations),
                  'contact_evidence':self.contact_evidence,'tea_local_hotspots':self.tea_local_hotspots}
        for split, prefix in ((None, ""), ("fit", "fit_"), ("holdout", "holdout_")):
            eligible = [r for r in rows if r["grade"] in ("A", "B") and r['scored'] and (split is None or r["split"] == split)]
            pairs = [(a,b) for a in eligible for b in eligible if a["good"] == b["good"] and a["target_month"] < b["target_month"]]
            result[prefix+"within_tol"] = sum(r["within_tolerance"] for r in eligible)/len(eligible) if eligible else None
            result[prefix+"within_2tol"] = sum(r["within_2tol"] for r in eligible)/len(eligible) if eligible else None
            result[prefix+"p_order"] = sum(order_correct(a["simulated_month"], b["simulated_month"])
                                          for a,b in pairs)/len(pairs) if pairs else None
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
        result['ban_trials']['by_scenario']={}
        for source in sorted({c.get('source','action') for c in ban_cases}):
            cases=[c for c in ban_cases if c.get('source','action')==source]
            decided=[c for c in cases if c['status'] in ('pass','fail')]
            rate=sum(c['status']=='pass' for c in decided)/len(decided) if decided else None
            result['ban_trials']['by_scenario'][source]={'observed':len(decided),'censored':len(cases)-len(decided),
                'failure_rate':rate,'diagnostic_target':.7,'target_met':rate>=.7 if rate is not None else None}
        result.update(event_diagnostics(run.event_log, run.eligible_months, run.candidate_bursts))
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
                      peak_round_delay_months=max((s.peak_round_delay for s in run.sims.values()), default=0),
                      events_abandoned_budget=run.events_abandoned_budget,
                      overruns=run.overruns, wave_years=max((b-a)/12 for s in run.sims.values() for a,b in s.waves) if any(s.waves for s in run.sims.values()) else 0,
                      events=run.event_log, summaries={g:s.summary() for g,s in run.sims.items()})
        result["channel_audit"] = {}
        for good, sim in run.sims.items():
            result["channel_audit"][good] = {}
            for kind in ("contact", "ownership", "event"):
                inputs = [r for r in sim.nonlocal_log if r["type"] == kind]
                shares = [r["source"]["population_share"] for r in inputs if (r.get("source") or {}).get("population_share") is not None]
                result["channel_audit"][good][kind] = dict(inputs=len(inputs), receiving_countries=len({r['country'] for r in inputs}),
                    ownership_population_share_median=q(shares), ownership_population_share_max=max(shares, default=None))
        result["ownership_case_studies"] = []
        if run.timeline.kind == "R":
            for tag, good, fact_id, historical_lag in (("TUR", "coffee", "me_ott_yemen_1539", 17),
                                                       ("CAS", "tobacco", "spanish_hispaniola", [40,50])):
                c = run.timeline.country_index.get(tag)
                fact = next((f for f in run.timeline.facts if f['id'] == fact_id), None)
                if c is not None and fact is not None:
                    got = run.sims[good].capital_stage2.get(c)
                    result["ownership_case_studies"].append(dict(country=tag, good=good, fact=fact_id,
                        exposure_month=fact['start_month'], capital_stage2=got,
                        lag_years=(got['month']-fact['start_month'])/12 if got else None,
                        historical_context_lag_years=historical_lag,
                        interpretation="Report-only contextual comparison, not a fit target or attribution; other owned routes may act concurrently."))
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
    for key in ("B_max", "peak_U", "wave_years", "peak_round_delay_months"):
        out[key] = max((r.get(key, 0) for r in runs), default=0)
    out["events_abandoned_budget"] = sum(r.get("events_abandoned_budget", 0) for r in runs)
    out["E_gap_by_good"] = {good: q([r.get("E_gap_by_good", {}).get(good) for r in runs])
                            for good in ("coffee", "tea", "tobacco")}
    out["M_mis"] = sum(r.get("M_mis", 0) for r in runs)
    out['ban_scenarios']={}
    sources={source for r in runs for source in r.get('ban_trials',{}).get('by_scenario',{})}
    for source in sorted(sources):
        cases=[c for r in runs for k in r.get('K',[]) if k['id']=='K6' for c in k.get('cases',[]) if c.get('source','action')==source]
        decided=[c for c in cases if c['status'] in ('pass','fail')]
        rate=sum(c['status']=='pass' for c in decided)/len(decided) if decided else None
        out['ban_scenarios'][source]={'observed':len(decided),'censored':len(cases)-len(decided),
            'failure_rate':rate,'diagnostic_target':.7,'target_met':rate>=.7 if rate is not None else None}
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
