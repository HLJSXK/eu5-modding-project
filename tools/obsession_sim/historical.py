"""Reproducible first-batch transport study. Targets are frozen before fitting.

This is an explicitly permitted historical-network approximation, not an export
of 17th-century trade volumes or populations. Point proxies do not certify L2.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .batch import run_batch
from .core import Params, Simulation
from .graph import load_json, hops_from
from .metrics import milestones
from .scenario import apply_scenario

TARGET_PATH = Path(__file__).with_name("history_targets.json")
START = 1337
END = 1800
SHARED = dict(rho=.99, p=.004, delta=.1, decay="country_clock", hold_T=600,
              decay_factor=.98, habit_floor=.75, max_months=(END - START) * 12,
              series_every=0, stop_when_calm=False, coefficient_cost=10)
SOURCES = {
    "coffee": "https://www.aboutcoffee.org/origins/history-of-coffee/ (15th/16th century Middle East; 17th century Europe)",
    "tea": "https://www.tea.co.uk/history-of-tea (Dutch maritime imports and English tea consumption)",
    "tobacco": "https://www.ncbi.nlm.nih.gov/books/NBK316400/ (Americas origin and global diffusion); dates from design 09, grade B pending row-level sources",
}


def scenario(good, graph, *, transport=True, corridors=True):
    targets = json.loads(TARGET_PATH.read_text(encoding="utf-8"))[good]
    sp = {"name": f"first_batch_{good}", "good": good, "start_year": START,
          "parameters": {k: v for k, v in SHARED.items() if k not in ("series_every", "stop_when_calm")},
          "evidence": SOURCES[good], "data_boundary": "1337 static ownership; historical transport fixture; no inferred population/markets",
          "seeds": [], "milestones": [dict(name=n, names=[v], threshold=t, target_year=y,
                                          tolerance_months=tol, grade="C" if good == "coffee" and i == 0 else "B",
                                          split="holdout" if i % 4 == 2 else "fit")
                                         for i, (n, v, t, y, tol) in enumerate(targets)],
          "transport": {"source": "historical sparse port/caravan backbone; weights are model assumptions (C)",
                        "strait_weight": .5, "routes": []}, "coefficients": [], "wake": []}
    if corridors:
        sp["land_corridors"] = [dict(**{"from": a, "to": b}, weight=4 if b == "vienna" else 7,
                                    evidence="static domestic trade/road approximation along actual map adjacency (C)")
                                for a, b in [("bordeaux", "paris"), ("marseille", "paris"),
                                             ("goa", "agra"), ("hakata", "kyoto"), ("novgorod", "moscow"),
                                             ("venice", "vienna")]]

    def path(names, start, end, weight=.18, directed=False, evidence=""):
        if not transport:
            return
        for a, b in zip(names, names[1:]):
            # Adjacent hubs already communicate geographically; do not duplicate.
            if graph.names.index(a) in graph.incoming[graph.names.index(b)]:
                continue
            sp["transport"]["routes"].append(dict(
                **{"from": a, "to": b}, start_year=start, end_year=end,
                weight=weight * 5, directed=directed,
                evidence=evidence or SOURCES[good] + "; backbone route is an explicit C-grade approximation"))

    def coef(where, scale, rho=None):
        if corridors:
            row = {"where": where, "p_scale": scale}
            if rho is not None:
                row["rho"] = rho
            sp["coefficients"].append(row)

    if good == "coffee":
        sp["constraints"] = [dict(name="no European adoption before 1500", where={"continent": "europe"}, threshold=1, before_year=1500),
                             dict(name="no East Asian fashion before 1650", where={"subcontinent": "east_asia"}, threshold=20, before_year=1650)]
        sp["waves"] = [dict(start_year=1450, end_year=1530), dict(start_year=1540, end_year=1590),
                       dict(start_year=1610, end_year=1700)]
        sp["seeds"] = [dict(name="al_mukha", year=1450, value=.5)]
        sp["sources"] = [dict(name="al_mukha", start_year=1450, end_year=1470, amount=.5,
                               requires={"raw_material": "coffee", "religion": ["sunni", "shia"], "owner_tag": "YEM"},
                               evidence=SOURCES[good] + "; finite cultivation/ritual input at origin; no target seed")]
        coef({"region": ["arabia_region", "egypt_region", "crescent_region", "anatolia_region"]}, 2)
        coef({"region": ["italy_region", "balkan_region"]}, 1.5)
        coef({"area": ["provence_area", "austria_area"]}, 1.5)
        coef({"subcontinent": "east_asia"}, .01)
        path(["jeddah", "suez", "alexandria", "beirut"], 1490, 1530, .6)
        path(["damascus", "aleppo", "constantinople"], 1540, 1590, .6)
        path(["aleppo", "tabriz", "isfahan"], 1540, 1590, .26, True)
        path(["alexandria", "venice"], 1610, 1625, .1, True)
        path(["alexandria", "venice"], 1625, 1700, .26, True,
             SOURCES[good] + "; assumed early-17th-century growth in European import volume (C)")
        path(["venice", "livorno", "marseille", "lisbon", "london", "amsterdam", "hamburg"], 1610, 1700, .26, True)
        sp["wake"] = [dict(start_year=y, names=ns) for y, ns in
                      [(1540, ["damascus", "jeddah"]), (1610, ["alexandria", "constantinople"])]]
    elif good == "tobacco":
        sp["waves"] = [dict(start_year=1530, end_year=1620), dict(start_year=1630, end_year=1670)]
        sp["initial"] = [dict(where={"raw_material": "tobacco", "continent": "america"}, value=30)]
        sp["constraints"] = [dict(name="no tobacco outside Americas before contact", nodes=[i for i, c in enumerate(graph.attrs["continent"]) if c != "america"],
                                  threshold="positive", before_year=1530)]
        path(["magorix", "sevilla"], 1530, 1620, .8, True,
             SOURCES[good] + "; assumed export contact at 1530; 1337 owners cannot establish colonial possession")
        path(["sevilla", "lisbon", "bordeaux"], 1550, 1620, .8, True)
        path(["bordeaux", "london", "amsterdam"], 1580, 1620, .8, True)
        path(["amsterdam", "hamburg"], 1615, 1620, .8, True)
        path(["sevilla", "marseille", "venice", "constantinople"], 1590, 1620, .8, True)
        path(["lisbon", "cacheu", "cabo_corso"], 1600, 1620, .8, True)
        path(["lisbon", "goa", "malacca", "guangzhou", "hakata"], 1580, 1620, .8, True)
        # Coastal cabotage reaches the Osaka merchant port without requiring
        # every overland village between Kyushu and Kinai to adopt tobacco.
        path(["hakata", "osaka"], 1580, 1620, .8, True,
             "Japanese coastal cabotage between two merchant ports (C network approximation); Kyoto still reached through land adjacency")
        # Continental second wave reuses customs, rather than reseeding targets.
        path(["hamburg", "stockholm", "novgorod"], 1630, 1670, .8)
        sp["wake"] = [dict(start_year=1630, names=["hamburg", "constantinople", "goa", "hakata"])]
    elif good == "tea":
        sp["constraints"] = [dict(name="no European tea before maritime contact", where={"continent": "europe"}, threshold="positive", before_year=1610),
                             dict(name="Anatolia not above fashion", where={"region": "anatolia_region"}, threshold=45, before_year=1800),
                             dict(name="France/Italy not above fashion", where={"region": ["france_region", "italy_region"]}, threshold=45, before_year=1800)]
        sp["waves"] = [dict(start_year=1390, end_year=1490), dict(start_year=1570, end_year=1590),
                       dict(start_year=1610, end_year=1700), dict(start_year=1710, end_year=1770)]
        sp["initial"] = [dict(where={"region": ["east_china_region", "north_china_region", "south_china_region", "west_china_region"]}, value=45),
                         dict(where={"region": ["tibet_region", "mongolia_region"]}, value=35),
                         dict(where={"region": "japan_region"}, value=25),
                         dict(where={"region": "korea_region"}, value=20)]
        coef({"region": ["south_china_region", "west_china_region", "tibet_region"]}, 2)
        coef({"region": ["mongolia_region", "xinjiang_region", "khorasan_region", "steppes_region", "russian_region"]}, 1.8)
        coef({"region": ["persia_region", "crescent_region"]}, 1.3)
        coef({"region": ["indonesia_region", "great_britain_region", "north_german_region", "scandinavian_region"]}, 2)
        # Static preference barriers must dominate vanilla affinity. With at
        # most 10 neighbors of x<=100, p=.00002 bounds equilibrium below 2.
        coef({"region": ["anatolia_region", "france_region", "italy_region", "iberia_region"]}, .001)
        # Europe cannot receive tea over a fictitious medieval land connection.
        # This changes shared regional eligibility, never writes target x.
        sp["coefficient_events"] = [dict(start_year=1390, where={"continent": "europe"}, p_scale=0),
                                     dict(start_year=1390, where={"region": ["persia_region", "crescent_region"]}, p_scale=0),
                                     dict(start_year=1645, where={"region": ["persia_region", "crescent_region"]}, p_scale=1.3),
                                     dict(start_year=1610, where={"region": ["north_german_region", "scandinavian_region"]}, p_scale=1),
                                     dict(start_year=1638, where={"region": "russian_region"}, p_scale=1.8),
                                     dict(start_year=1658, where={"region": "great_britain_region"}, p_scale=2)]
        path(["lhasa", "kashgar", "samarkand"], 1410, 1490, .4, True)
        path(["guangzhou", "malacca", "amsterdam"], 1610, 1700, .26, True)
        path(["amsterdam", "london"], 1658, 1700, .36, True)
        path(["amsterdam", "hamburg", "kobenhavn", "stockholm"], 1675, 1700, .4, True)
        path(["samarkand", "isfahan"], 1645, 1700, .4, True)
        path(["kashgar", "astrakhan", "moscow"], 1710, 1770, .4, True)
        path(["amsterdam", "london"], 1710, 1770, .4, True)
        sp["contacts"] = [dict(**{"from": "kashgar", "to": "moscow"}, start_year=1638, value=.5,
                                source_minimum=1, evidence="design 09: 1638 Mongol diplomatic gift; conditional on actual upstream tea")]
        sp["coefficient_events"] += [dict(start_year=1570, where={"region": "japan_region"}, p_scale=2),
                                      dict(start_year=1658, where={"region": "great_britain_region"}, p_scale=.75),
                                      dict(start_year=1710, where={"region": "steppes_region"}, p_scale=1.8),
                                      dict(start_year=1710, where={"region": "great_britain_region"}, p_scale=.78)]
        sp["wake"] = [dict(start_year=1570, names=["kyoto"]),
                      dict(start_year=1710, names=["astrakhan", "moscow", "london", "amsterdam"], renew_clock=True)]
    else:
        raise ValueError(good)
    return sp


def prepare(graph, *, transport=True, corridors=True, params=None):
    sims, specs = {}, {}
    for good in ("coffee", "tea", "tobacco"):
        g = deepcopy(graph)
        sp = scenario(good, g, transport=transport, corridors=corridors)
        config = dict(SHARED, **(params or {}))
        config.update(apply_scenario(g, sp, config["p"], config["rho"], START))
        sims[good], specs[good] = Simulation(g, Params(**config)), sp
    return sims, specs


def evaluate(sims, specs, ledger):
    results = {}
    for good, sim in sims.items():
        rows = milestones(sim, specs[good]["milestones"], START)
        for row, target in zip(rows, specs[good]["milestones"]):
            row.update(grade=target["grade"], split=target["split"])
        pairs = [(a, b) for a in rows for b in rows if a["target_month"] < b["target_month"]]
        order = sum(a["simulated_month"] is not None and b["simulated_month"] is not None and
                    a["simulated_month"] <= b["simulated_month"] for a, b in pairs) / max(1, len(pairs))
        loss = sum(100 if r["error_months"] is None else
                   (r["error_months"] / max(1, r["tolerance_months"])) ** 2 for r in rows)
        origin = {v for v, _, _ in sim.P.seeds} | {v for v, _ in sim.P.initial_values}
        origin.update(e["node"] for e in sim.P.input_events if e["kind"] == "source" and e["amount"] > 0)
        origin.update(e["to"] for e in sim.P.input_events if e["kind"] == "contact")
        distance = hops_from(sim.g, origin)
        reached = [r for r in rows if r["simulated_month"] is not None]
        unseeded = sum(all(distance[v] < 0 or distance[v] > 1 for v in specs[good]["milestones"][i].get("nodes", []) or
                          [sim.g.names.index(specs[good]["milestones"][i]["names"][0])])
                       for i, r in enumerate(rows) if r["simulated_month"] is not None) / max(1, len(reached))
        new_members = [v for v, t in enumerate(sim.arrival) if t > 0 and v not in origin]
        conn = sum(sim.arrival_parent[v] >= 0 for v in new_members) / max(1, len(new_members))
        results[good] = {"summary": sim.summary(), "milestones": rows, "loss": loss,
                         "within_tolerance": sum(r["within_tolerance"] for r in rows),
                         "within_2tol": sum(r["error_months"] is not None and abs(r["error_months"]) <= 2 * r["tolerance_months"] for r in rows),
                         "p_order": order, "p_unseeded": unseeded, "p_conn": conn,
                         "fit_within": sum(r["within_tolerance"] for r in rows if r["split"] == "fit"),
                         "holdout_within": sum(r["within_tolerance"] for r in rows if r["split"] == "holdout"),
                         "transport": sim.g.meta["transport"],
                         "constraints": [{"name": check["name"], "violations": len(violations),
                                          "first_year": None if not violations else START + min(violations.values()) / 12,
                                          "locations": [sim.g.names[v] for v in violations]}
                                         for check, violations in zip(sim.P.constraints, sim.constraint_violations)]}
    return {"target_version": json.loads(TARGET_PATH.read_text(encoding="utf-8"))["version"],
            "target_sha256": hashlib.sha256(TARGET_PATH.read_bytes()).hexdigest(),
            "shared_params": {k: getattr(next(iter(sims.values())).P, k) for k in SHARED}, "calendar_start": START,
            "data_boundary": "Named-city timing proxies on a 1337 static map; not regional population-weighted acceptance.",
            "formal_gate": "not certified: regional population, joint wine/coffee, tobacco ban trials, MC and independent snapshots required",
            "holdout_status": "exposed diagnostic split; all listed targets have been inspected during development, not blind validation",
            "point_target_acceptance": all(r["within_tolerance"] == len(r["milestones"]) for r in results.values()),
            "checked_constraints_pass": not any(c["violations"] for r in results.values() for c in r["constraints"]),
            "shared_budget": ledger, "goods": results}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--budget", type=int, default=50_000)
    ap.add_argument("--no-transport", action="store_true")
    ap.add_argument("--no-corridors", action="store_true")
    ap.add_argument("--params", type=Path)
    a = ap.parse_args(argv)
    graph = load_json(a.graph)
    overrides = json.loads(a.params.read_text(encoding="utf-8")) if a.params else {}
    sims, specs = prepare(graph, transport=not a.no_transport, corridors=not a.no_corridors, params=overrides)
    ledger = run_batch(sims.values(), a.budget)
    report = evaluate(sims, specs, ledger)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for good, result in report["goods"].items():
        print(good, result["within_tolerance"], "/", len(result["milestones"]), "loss", round(result["loss"], 2))
        print([(r["name"], r["simulated_year"], r["error_months"]) for r in result["milestones"]])
    print("shared peak", ledger["peak_monthly_U"], "overruns", len(ledger["overruns"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
