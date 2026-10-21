"""Fit-only handoff 23 workflow. Never runs or reads holdout outcomes."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

from .worlds import canonical_hash, read_timeline
from tools.eu5_save_parser.world_export import atomic_json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def measure_prior(timeline_path, target=HERE / "world_priors.json"):
    manifest, snapshots = read_timeline(timeline_path, lazy=True)
    values, sources, samples = [], [], []
    for index, entry in enumerate(manifest["snapshots"]):
        year = int(entry["date"].split(".")[0])
        if not 1338 <= year <= 1630:
            continue
        snap = snapshots[index]
        territories = {}
        for loc in snap["locations"].values():
            if loc.get("owner") is not None and loc["population"] > 0:
                territories.setdefault(loc.get("market"), set()).add(loc["owner"])
        for market, rec in sorted(snap["markets"].items()):
            center_owner = snap["locations"].get(rec["center"], {}).get("owner")
            for country, share in sorted(rec["merchants"].items()):
                if share > 0 and country != center_owner and country not in territories.get(market, ()):
                    values.append(share)
                    samples.append([entry["date"], market, country, share])
        sources.append(dict(date=entry["date"], file=entry["file"], sha256=entry["sha256"],
                            save_sha256=snap["source"]["sha256"]))
    if not values:
        raise ValueError("no non-territorial foreign merchant observations")
    result = dict(version="2026-10-21-nonterritorial-residency/1", source_world=manifest["id"],
                  source_timeline=str(Path(timeline_path).resolve()), source_snapshots=sources,
                  sample_count=len(values), sample_sha256=canonical_hash(samples),
                  foreign_share_quantiles={str(p):float(np.quantile(values, p)) for p in (.1,.25,.5,.75,.9)},
                  selection_rule="1338–1630, positive foreign saved share with no populated territory in that market; "
                                 "one common median share per documented R community, no renormalization. "
                                 "O retains the original saved share after eligibility filtering; never fitted to target years.")
    write_json(target, result)
    print(json.dumps({k:result[k] for k in ("source_world", "sample_count", "sample_sha256", "foreign_share_quantiles")}), flush=True)
    return result


def prepare_config():
    path = HERE / "structural_config.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    from .structural import FIT_PARAMS
    previous = json.loads((HERE / "selected_params.json").read_text(encoding="utf-8"))
    cfg["version"] = "2026-10-21-handoff23/1"
    cfg["params"] = {k:(cfg["params"][k] if cfg.get("fit_parameters") else previous[k]) for k in FIT_PARAMS}
    cfg["fit_parameters"] = list(FIT_PARAMS)
    cfg["fixed"].update(delta=.01, theta=20, hold_T=240, decay_factor=.98,
                        habit_floor=.3, contact_amount=7, historical_pool_share=.6, event_country_slice=16,
                        ban_multiplier=.2, ban_decay_scale=1.5, ban_duration_scale=4, ban_hold_scale=.5,
                        minimum_origin_population=.001, coefficient_cost=12, aggregate_node_cost=25)
    cfg["event_weights"] = dict(spread_front=1.5, spread_low=1.5, spread_high=.7,
        impact_high=1.8, impact_low=.5, impact_blocked=2.,
        stage_finished=.4, stage_cold=.6, stage_member=1., stage_fashion=1.3, stage_high=1.5,
        phase_finished=.6, phase_cold=1.3, phase_member=1., phase_high=1.1, policy_blocked=1.5)
    for good, floor in (("coffee", .3), ("tea", .3), ("tobacco", .4)):
        cfg["profiles"][good]["habit_floor"] = floor
        cfg["profiles"][good].pop("habit_floor_scale", None)
    cfg.pop("profile_strength_definition", None)
    cfg["secondary_channel"] = "Ownership uses the population share at x≥20 outside the capital market, " \
        "multiplied by lambda_ownership, fixed affinity and 1/(1+preemption). " \
        "Merchant contact uses only non-territorial foreign residents, with its own lambda_contact. " \
        "The yearly hazard is converted to monthly probability by 1-exp(-hazard/12), as in the original controller."
    cfg["wine_definition"] = "Constant C-grade opening background x=30: no clock, retreat, spreading or timer; no-wine sensitivity required."
    cfg["manual_constants"] = []
    def inventory(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                inventory(child, path + "." + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                inventory(child, path + "." + str(i))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            design = any(k in path for k in ("habit_floor", "hold_T", "decay_factor"))
            cfg["manual_constants"].append(dict(path=path, value=value,
                category="设计" if design else "手设",
                basis="03 §2.1 / handoff23 §4.2" if design else "Inherited fixed structural_config table; disclosed by handoff23 §4.3; not historically fitted"))
    for name in ("fixed", "profiles", "events", "initial_customs", "event_weights"):
        inventory(cfg[name], name)
    cfg["manual_constant_count"] = len(cfg["manual_constants"])
    write_json(path, cfg)
    if set(previous) != set(FIT_PARAMS):
        write_json(HERE / "selected_params.json", cfg["params"])
    targets_path = HERE / "regional_targets.json"
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    targets["targets"] = [r for r in targets["targets"] if r["id"] != "tea_0"]
    write_json(targets_path, targets)


def audit_world(facts_path, timeline_path, out, *, seed=0, omit_wc=False):
    """Validate geography and actual applicability without simulating any good."""
    from .graph import load_json
    from .worlds import Timeline, historical_base, religion_groups
    graph = load_json(ROOT / "tmp/obsession_real/eu5_1337.json")
    _, sequence = read_timeline(timeline_path, lazy=True)
    reference = ROOT / ".eu5-base/reference_game_files/game"
    base = historical_base(graph, sequence[0], reference)
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))["facts"]
    priors = json.loads((HERE / "world_priors.json").read_text(encoding="utf-8"))
    share = priors["foreign_share_quantiles"][priors["r_common_share_quantile"]]
    timeline = Timeline(graph, [base], kind="R", facts=facts, seed=seed, omit_wc=omit_wc,
                        faith_groups=religion_groups(reference), residency_power=share)
    months = sorted({0, 5999} | {max(0, f[k]) for f in timeline.facts for k in ("start_month", "end_month")
                               if f[k] < 6000})
    impacts = {f["id"]:0 for f in timeline.facts}
    for index, month in enumerate(months):
        state, _ = timeline.at(month)
        for key, count in state.fact_effects.items():
            impacts[key] = max(impacts[key], count)
        if index % 100 == 0: print(f"world audit {index}/{len(months)}", flush=True)
    errors = [key for key, count in impacts.items() if count == 0]
    result = dict(format="obsession.world-input-audit/1", world_sha256=canonical_hash(facts),
                  snapshot_count=len(months), fact_count=len(timeline.facts), seed=seed, omit_wc=omit_wc, affected_locations=impacts,
                  zero_impact_errors=errors, passed=not errors, scope="World state only; no commodity simulation or targets read.")
    write_json(out, result)
    if not errors:
        from .worlds import bindings_key
        cache = Path(out).parent / "inputs/world_bindings" / (bindings_key(timeline, seed, omit_wc) + ".json")
        atomic_json(cache, dict(key=cache.stem, affected_locations=impacts,
                               bound_nodes={k:v.tolist() for k,v in timeline.bound_fact_nodes.items()}))
    print(json.dumps(dict(passed=not errors, fact_count=len(facts), zero_impact_errors=errors), ensure_ascii=False), flush=True)
    return result


def _audit_request(request):
    return audit_world(**request)


def audit_batch(timeline_path, out, workers):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [dict(facts_path=HERE / "world_facts.json", timeline_path=timeline_path,
                 out=out / f"world_audit_formal_{seed}.json", seed=seed, omit_wc=True) for seed in range(30)]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(_audit_request, job):job["seed"] for job in jobs}
        for future in as_completed(tasks):
            result = future.result()
            results.append(result)
            print(f"AUDIT seed={tasks[future]} {len(results)}/30, errors={len(result['zero_impact_errors'])}", flush=True)
    summary = dict(format="obsession.world-input-audit-batch/1", seeds=list(range(30)), omit_wc=True,
                   passed=all(r["passed"] for r in results),
                   world_sha256=results[0]["world_sha256"],
                   zero_impact_errors=sorted(set().union(*(set(r["zero_impact_errors"]) for r in results))),
                   reports=[str(out / f"world_audit_formal_{seed}.json") for seed in range(30)])
    write_json(out / "world_audit_batch.json", summary)
    return summary


def colonial_facts():
    """Geographic political inputs, compiled before any round-2 fit results."""
    facts = []
    def add(key, actor, location, start, end, description, source, *, where=None, grade="W-B", **extra):
        row = dict(id="am_" + key, kind="ownership_region" if where else "ownership", fact=description,
                   start=start, end=end, grade=grade, source=source, goods="all", **actor, **extra)
        row.update(where=where) if where else row.update(location=location)
        facts.append(row)
    def form(key, name, capital, culture, start, source):
        facts.append(dict(id="am_form_" + key.lower(), kind="formation", fact=f"{name} becomes an independent state.",
            start=start, end=1837, grade="W-A", goods="all", source=source,
            country=dict(key=key, name=name, capital=capital, culture=culture, religion="catholic")))
    cas, por, eng, fra, dutch = [dict(actor_tag=t) for t in ("CAS", "POR", "ENG", "FRA")] + [dict(actor_country="F_DUTCH")]
    mexico = "Archivo General de la Nacion, consummation of independence 1821; https://www.gob.mx/agn/articulos/archivisticaclio-documentos-de-la-consumacion-de-la-independencia-de-mexico?idiom=es"
    peru = "Peruvian Foreign Ministry, historical account, independence 28 July 1821; https://www.gob.pe/institucion/rree/informes-publicaciones/343592-resena-historica"
    brazil = "Brazilian federal bicentenary history, independence 1822 and subsequent territorial consolidation; https://www.gov.br/pt-br/campanhas/bicentenario/historia/view"
    us = "US National Archives, Declaration of Independence and Treaty of Paris; https://www.archives.gov/founding-docs/declaration-history ; https://www.archives.gov/milestone-documents/treaty-of-paris-0"
    add("spanish_havana", cas, "habana", 1519, 1837, "Spain establishes Havana in 1519.", "UNESCO, Old Havana; https://whc.unesco.org/en/list/204/", grade="W-A")
    add("new_spain_central", cas, None, 1521, 1821, "Spain governs the Mexico City central district after the conquest of 1521; province-level boundary approximation.",
        "UNESCO, Historic Centre of Mexico City; https://whc.unesco.org/en/list/412/ ; " + mexico, where=dict(province="anahuac_province"))
    add("spanish_lima", cas, "rimaq", 1535, 1821, "Spain establishes Lima as a colonial government centre in 1535.", "UNESCO, Historic Centre of Lima; https://whc.unesco.org/en/list/500/ ; " + peru)
    form("F_AM_MEXICO", "Mexico", "tenochtitlan", "castilian", 1821, mexico)
    add("mexico_independence", dict(actor_country="F_AM_MEXICO"), None, 1821, 1837, "The independent Mexican government succeeds Spain in the central Mexico district.", mexico, where=dict(province="anahuac_province"))
    form("F_AM_PERU", "Peru", "rimaq", "castilian", 1821, peru)
    add("peru_lima", dict(actor_country="F_AM_PERU"), "rimaq", 1821, 1837, "The independent Peruvian government controls Lima.", peru)
    olinda = "UNESCO, Historic Centre of Olinda, foundation 1535, municipal status 1537 and Dutch occupation 1630-1654; https://whc.unesco.org/en/list/189/ ; https://whc.unesco.org/document/128792"
    add("portuguese_pernambuco", por, None, 1537, 1822, "Portugal governs the coastal Pernambuco captaincy from its established town of Olinda; Capibaribe province is the geographic approximation.", olinda + " ; " + brazil, where=dict(province="capibaribe_province"))
    rio = "Government of Brazil, Rio founded by Portugal in 1565; https://www.gov.br/g20/pt-br/sobre-o-g20/cidades-sede/rio-de-janeiro-rj ; " + brazil
    add("portuguese_rio", por, "goana_para", 1565, 1822, "Portugal establishes the Rio de Janeiro settlement on Guanabara Bay in 1565.", rio)
    union = "UNESCO Curaçao nomination, Iberian union 1580-1640; https://whc.unesco.org/document/154358"
    add("iberian_union_pernambuco", cas, None, 1580, 1640, "The Portuguese crown and its Pernambuco holding share the Spanish monarchy during the Iberian Union.", union, where=dict(province="capibaribe_province"))
    add("iberian_union_rio", cas, "goana_para", 1580, 1640, "The Rio holding of the Portuguese crown shares the Spanish monarchy during the Iberian Union.", union)
    add("dutch_brazil", dutch, None, 1630, 1654, "The Dutch occupy Pernambuco between 1630 and their expulsion in 1654; Capibaribe province is the geographic approximation.", olinda, where=dict(province="capibaribe_province"))
    form("F_AM_BRAZIL", "Brazil", "goana_para", "portuguese", 1822, brazil)
    add("brazil_rio", dict(actor_country="F_AM_BRAZIL"), "goana_para", 1822, 1837, "The independent Brazilian government holds its capital at Rio de Janeiro.", brazil)
    add("brazil_pernambuco", dict(actor_country="F_AM_BRAZIL"), None, 1822, 1837, "Pernambuco forms part of independent Brazil.", brazil, where=dict(province="capibaribe_province"))
    add("english_bermuda", eng, "bermuda", 1612, 1837, "England establishes the permanent town of St George on Bermuda in 1612.", "UNESCO, St George Bermuda; https://whc.unesco.org/en/list/983", grade="W-A")
    add("english_barbados", eng, "ichirouganaim", 1627, 1837, "English settlers establish permanent government on Barbados in 1627.", "Government of Barbados, History of Tourism; https://www.tourism.gov.bb/history", grade="W-A")
    quebec = "US National Park Service, Legacy of Saint Croix Island, Quebec founded 1608 and New France ceded in 1763; https://home.nps.gov/articles/000/legacy-of-saint-croix-island.htm"
    add("french_quebec", fra, "stadacona", 1608, 1763, "France establishes the permanent Quebec settlement in 1608.", quebec, grade="W-A")
    add("british_quebec", eng, "stadacona", 1763, 1837, "Britain receives the Quebec colonial centre under the Treaty of Paris in 1763.", quebec, grade="W-A")
    french = "Archives nationales d'outre-mer, Antilles francaises from 1635; https://archives-nationales-outre-mer.culture.gouv.fr/faire-une-recherche/antilles-francaises ; Institut de France, colonial foundations; https://www.france-memoire.fr/la-martinique-et-la-guadeloupe-integrees-au-domaine-royal/"
    add("french_martinique", fra, "iguanacaera", 1635, 1837, "France establishes a permanent colony on Martinique in 1635; occupations shorter than ten years are omitted under T1.", french, grade="W-A")
    add("french_guadeloupe", fra, "carucairi", 1635, 1837, "France establishes a permanent colony on Guadeloupe in 1635; occupations shorter than ten years are omitted under T1.", "Ministere des Outre-Mer, Guadeloupe; https://www.outre-mer.gouv.fr/territoires/guadeloupe ; " + french, grade="W-A")
    ny = "US National Park Service, Colonial and Early American New York, New Amsterdam founded 1625, English takeover 1664; https://www.nps.gov/elis/learn/historyculture/places_colonial_early_american.htm"
    add("dutch_new_netherland", dutch, "manhattan", 1625, 1664, "The Dutch establish New Amsterdam in lower Manhattan; the brief restoration of 1673-74 is outside T1.", ny, grade="W-A")
    add("english_new_york", eng, "manhattan", 1664, 1783, "England takes Manhattan in 1664 and retains the colonial holding until American independence is recognized.", ny + " ; " + us)
    # Native game keys refer to the same metropolitan map units, not nearby ports.
    form("F_USA", "United States", "shackamaxon", "english", 1776, us)
    facts[-1]["country"].update(religion=None, no_state_religion=True)
    facts[-1]["source"] += " ; US National Archives, First Amendment, no federal establishment of religion; https://www.archives.gov/founding-docs/bill-of-rights-transcript"
    add("usa_philadelphia", dict(actor_country="F_USA"), "shackamaxon", 1776, 1837, "The American government is established at Philadelphia during independence.", us)
    add("usa_new_york", dict(actor_country="F_USA"), "manhattan", 1783, 1837, "The United States succeeds British sovereignty over Manhattan under the 1783 peace.", us)
    add("usa_washington", dict(actor_country="F_USA"), "anacostia", 1800, 1837, "The federal government moves to the permanent seat on the Potomac in 1800.", "US National Park Service, White House, occupied since 1800; https://www.nps.gov/places/white-house.htm", new_capital="anacostia")
    add("dutch_curacao", dutch, "curacaute", 1634, 1837, "The Netherlands establishes the Curacao holding in 1634; British occupations shorter than ten years are omitted under T1.", "UNESCO, Willemstad Curacao; https://whc.unesco.org/en/list/819 ; https://whc.unesco.org/document/154358", grade="W-A")
    return facts


def prepare_world(audit_path):
    original_path = HERE / "world_facts_v2.json"
    original = json.loads(original_path.read_text(encoding="utf-8"))
    changes = []
    corrections = {"mar_eng_henry8_1540_cleves":dict(end=1540.5),
                   "mar_sco_james5_1537_france":dict(end=1537.5),
                   "mar_fra_philip6_1350_navarre":dict(end=1350+8/12),
                   "mar_swe_haakon_1363_denmark":dict(end=1364),
                   "me_cyprus_antalya":dict(start=1361,end=1373)}
    zero_ids = (set(json.loads(Path(audit_path).read_text(encoding="utf-8"))["zero_impact_errors"])
                if Path(audit_path).exists() else set())
    existing = HERE / "world_facts_amendments.json"
    if existing.exists():
        log = json.loads(existing.read_text(encoding="utf-8"))
        if log["source_sha256"] != hashlib.sha256(original_path.read_bytes()).hexdigest():
            raise ValueError("original world timeline changed during input repair")
        zero_ids.update(row["id"] for row in log["amendments"] if "previous_owner_tags" in row.get("before", {}))
    output = []
    for original_row in original["facts"]:
        row = deepcopy(original_row)
        if row["id"] == "me_france_constantine_1837":
            changes.append(dict(id=row["id"], before=row, after=None, reason="T1/horizon ends at 1837 exclusive; a 1837-to-1837 record has no active month."))
            continue
        if row["id"] in corrections:
            before = {key:row[key] for key in corrections[row["id"]]}
            row.update(corrections[row["id"]])
            if row["id"] == "me_cyprus_antalya":
                row["source"] += " ; Cyprus Institute, coinage history, control from 1361 to 1373; https://numismatics-medieval.dioptra.cyi.ac.cy/?q=content%2Ffrankish-period"
            changes.append(dict(id=row["id"], before=before, after=corrections[row["id"]],
                reason="Resolve invalid/overlapping year precision using the dates explicitly given by the cited source; no spread results read."))
        if row["id"] in zero_ids and row.get("previous_owner_tags"):
            previous = row.pop("previous_owner_tags")
            changes.append(dict(id=row["id"], before=dict(previous_owner_tags=previous), after={},
                reason="User-authorized correction: predecessor predicate contradicts the cited territorial scope and prevents all effect; retain the sourced scope and dates."))
        if row["id"] == "sa_ins_dutch_minangkabau":
            # A positive continuous interval may round to zero months near 1837.
            row["start"] = [1832, 1836+11/12]
            changes.append(dict(id=row["id"], before=dict(start=[1832,1837]), after=dict(start=row["start"]),
                reason="Monthly discretization: prevent rounding a sampled pre-1837 start into the excluded 1837 boundary; maximum correction is one month."))
        output.append(row)
    legacy = dict(id="spanish_hispaniola", kind="ownership", actor_tag="CAS", location="magorix",
        start=[1493,1496], end=1795, grade="W-B", goods="all", fact="Spanish settlement and government are established on Hispaniola; map district Magorix.",
        source="Library of Congress, Santo Domingo in Maps; https://blogs.loc.gov/maps/2025/12/colonial-contestations-for-the-first-city-of-america-the-history-of-santo-domingo-in-maps/",
        single_milestone_suspect=True)
    output.extend([legacy, *colonial_facts()])
    result = {**original, "version":"2026-10-21-handoff23-repaired/1", "facts":output,
        "source_v2_sha256":hashlib.sha256(original_path.read_bytes()).hexdigest(),
        "share_rule":"Only cited residency facts create R merchant shares; every community uses the measured non-territorial median, without territorial proxies or normalization.",
        "amendments":changes,
        "unmapped_requested_sites":[
            dict(site="Jamestown", actor_tag="ENG", start=1607,
                 reason="No reliably verified point-to-key mapping in the current graph; Paspahegh/Jamestown is absent as a named unit. Kiskiack or Weyanock must not be substituted without geographic verification.",
                 source="US NPS, Jamestown; https://www.nps.gov/jame/learn/historyculture/a-short-history-of-jamestown.htm"),
            dict(site="Salvador", actor_tag="POR", start=1549,
                 reason="No verified city-to-key mapping; nearby Jiribatuba is not substituted. Pernambuco and Rio are independently sourced holdings, not replacements for Salvador.",
                 source="UNESCO, Salvador de Bahia; https://whc.unesco.org/en/list/309/"),
            dict(site="Saint Christopher French sector", actor_tag="FRA", start=1625,
                 reason="Liamuiga is one indivisible map location; French and English shared sovereignty cannot be represented by the current single-owner world schema. No whole-island French takeover is invented.",
                 source="Institut de France, colonial foundations; https://www.france-memoire.fr/la-martinique-et-la-guadeloupe-integrees-au-domaine-royal/")],
        "groups":dict(Counter(r["id"].split("_")[0] for r in output))}
    write_json(HERE / "world_facts.json", result)
    write_json(HERE / "world_facts_amendments.json", dict(source_sha256=result["source_v2_sha256"], amendments=changes,
        unmapped_requested_sites=result["unmapped_requested_sites"], policy="All changes precede round-2 propagation outcomes; ea_/re_/remaining historical gaps deferred by user."))
    print(f"Prepared {len(output)} world facts; {len(changes)} disclosed input corrections.", flush=True)


def finish_observers():
    """Preserve original runtime identity ids during metadata-only upgrades."""
    for path in sorted((ROOT / "tmp/obsession_worlds_round2").glob("*/timeline.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for entry in manifest["snapshots"]:
            snapshot_path = path.parent / entry["file"]
            original_path = ROOT / "tmp/obsession_worlds" / manifest["id"] / entry["file"]
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            old_hash = entry["sha256"]
            changed = False
            if original_path.exists():
                original = json.loads(original_path.read_text(encoding="utf-8"))
                assert original["source"]["sha256"] == snapshot["source"]["sha256"]
                for name, loc in snapshot["locations"].items():
                    for field in ("culture_instance", "religion_instance"):
                        if field in original["locations"][name] and loc.get(field) != original["locations"][name][field]:
                            loc[field] = original["locations"][name][field]
                            changed = True
            if changed:
                atomic_json(snapshot_path, snapshot)
                entry["sha256"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
                if entry.get("relations_file"):
                    relation_path = path.parent / entry["relations_file"]
                    relation = json.loads(relation_path.read_text(encoding="utf-8"))
                    assert relation["world_snapshot_sha256"] == old_hash
                    assert relation["source_sha256"] == snapshot["source"]["sha256"]
                    relation["world_snapshot_sha256"] = entry["sha256"]
                    atomic_json(relation_path, relation)
                    entry["relations_sha256"] = hashlib.sha256(relation_path.read_bytes()).hexdigest()
        sol = manifest["id"] == "c681faf6-91c6-45a9-bde4-9d8c22cd321e"
        manifest.update(label="SOL 观察者" if sol else "原版观察者", sol_enabled=sol,
                        role="prior_source_and_validation" if sol else "independent_validation",
                        role_evidence="Distinct archived playthrough ids; SOL runtime variable presence checked in both original 1338 saves. Non-SOL playthrough contributes neither R borders nor residency priors.")
        atomic_json(path, manifest)
        print(f"{manifest['label']}: {len(manifest['snapshots'])} snapshots, through {manifest['snapshots'][-1]['date']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("config", "prior", "audit", "audit-batch", "world", "observers"))
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--facts", type=Path, default=HERE / "world_facts.json")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--omit-wc", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=ROOT / "tmp/obsession_round2/world_input_audit.json")
    args = parser.parse_args()
    if args.action == "config":
        prepare_config()
    elif args.action == "prior":
        measure_prior(args.timeline)
    elif args.action == "world":
        prepare_world(args.out)
    elif args.action == "observers":
        finish_observers()
    elif args.action == "audit-batch":
        if not audit_batch(args.timeline, args.out, args.workers)["passed"]:
            raise SystemExit(2)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if not audit_world(args.facts, args.timeline, args.out, seed=args.seed, omit_wc=args.omit_wc)["passed"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
