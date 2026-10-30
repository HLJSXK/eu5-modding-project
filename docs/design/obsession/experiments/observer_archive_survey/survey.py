"""Survey of the decade observer archive for the obsession offline simulator.

Two steps, both run from the project root:

    $env:PYTHONUTF8='1'
    & $env:EU5_PYTHON docs/design/obsession/experiments/observer_archive_survey/survey.py extract
    & $env:EU5_PYTHON docs/design/obsession/experiments/observer_archive_survey/survey.py report

``extract`` reads every debug save in data/saves/observer_archive/<playthrough>/
and writes one compact JSON per save to tmp/obsession_real/observer_archive/
(about 5 MB each, not committed). It is resumable: existing JSON is skipped.
About 20 s and 1 GB RAM per 0.6 GB save.

``report`` reads those JSON files plus tmp/obsession_real/eu5_1337.json and
writes survey_results.json next to this script. Doc 18 quotes it.

This is an exploration tool, not part of tools/obsession_sim. Field meanings
that were not checked against game code are marked "unverified" in doc 18.
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import collections
import json
import mmap
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from tools.eu5_save_parser import parser as P  # noqa: E402

ARCHIVE = ROOT / "data/saves/observer_archive"
CACHE = ROOT / "tmp/obsession_real/observer_archive"
GRAPH = ROOT / "tmp/obsession_real/eu5_1337.json"
OUT = Path(__file__).with_name("survey_results.json")
GOODS = ("coffee", "tea", "tobacco", "sugar", "cocoa", "porcelain", "silk", "pepper", "cloves")
TOP = re.compile(rb"(?m)^[a-z_]+=\{\r?\n\t")


# ---------------------------------------------------------------- extract
def _section(view, name):
    match = re.compile(rb"(?m)^" + name.encode() + rb"=\{\r?\n").search(view)
    start = match.start()
    return start, TOP.search(view, start + 10).start()


def _ids(text):
    return [int(x) for x in re.findall(r"-?\d+", text)]


def extract_one(path: Path, out: Path, keep_history: bool) -> None:
    t0 = time.time()
    with path.open("rb") as handle:
        view = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        meta, names = P._parse_metadata(view, *_section(view, "metadata"))
        tags = P._parse_country_tags(view, *_section(view, "countries"))
        result = {"meta": meta, "tags": {str(k): v for k, v in tags.items()},
                  "names": names if keep_history else None}

        s, e = _section(view, "locations")
        text = view[s:e].decode("utf-8", "replace")
        locations, history = {}, {}
        for match in re.finditer(r"\n\t\t(\d+)=\{\n(.*?)\n\t\t\}(?=\n)", text, re.S):
            lid, body = int(match.group(1)), "\n" + match.group(2)

            def scalar(key):
                found = re.search(r"\n\t\t\t" + key + r"=([^\s{}]+)", body)
                return found.group(1) if found else None

            rec = {"o": scalar("owner"), "m": scalar("market"), "r": scalar("rank"),
                   "d": scalar("development"), "px": scalar("proximity"),
                   "cu": scalar("culture"), "re": scalar("religion"),
                   "rd": scalar("road_to_capital"), "ma": scalar("market_access"),
                   "pr": scalar("prosperity"), "rm": scalar("raw_material")}
            inst = re.search(r"\n\t\t\tinstitutions=\{(.*?)\n\t\t\t\}", body, re.S)
            if inst:
                rec["inst"] = {k: float(v) for k, v in re.findall(r"(\w+)=([-\d.]+)", inst.group(1))}
            locations[lid] = {k: v for k, v in rec.items() if v is not None}
            if keep_history:
                hist = re.search(r"ownership_history=\{(.*?)\}\s*\n\t\t\t[a-z]", body, re.S)
                if hist:
                    history[lid] = re.findall(r"date=([\d.]+)\s*\n\s*owner=(\d+)", hist.group(1))
        result["locations"] = locations
        if keep_history:
            result["ownership_history"] = history
        del text

        s, e = _section(view, "market_manager")
        text = view[s:e].decode("utf-8", "replace")
        produced = re.search(r"produced_goods=\{(.*?)\n\t\}", text, re.S)
        result["produced_goods"] = {k: float(v) for k, v in re.findall(r"(\w+)=([-\d.]+)", produced.group(1))}
        markets = {}
        database = text.find("\n\tdatabase={")
        for match in re.finditer(r"\n(\d+)=\{\n(.*?)\n\}(?=\n)", text[database:], re.S):
            body = "\n" + match.group(2)
            center = re.search(r"\n\tcenter=(\d+)", body)
            if not center:
                continue
            pop = re.search(r"\n\tpopulation=([-\d.]+)", body)
            members = re.search(r"\n\tmembers=\{([^}]*)\}", body)
            goods = {}
            for good in GOODS:
                block = re.search(r"\n\t\t" + good + r"=\{\n(.*?)\n\t\t\}", body, re.S)
                if not block:
                    continue
                gb = "\n" + block.group(1)

                def num(key):
                    found = re.search(r"\n\t\t\t" + key + r"=([-\d.]+)", gb)
                    return float(found.group(1)) if found else 0.0

                def breakdown(key):
                    found = re.search(r"\n\t\t\t" + key + r"=\{(.*?)\}", gb, re.S)
                    return ({a: float(v) for a, v in re.findall(r"(\w+)=([-\d.]+)", found.group(1))}
                            if found else {})

                hist = re.search(r"history=\{([^}]*)\}", gb)
                goods[good] = {"price": num("price"), "supply": num("supply"), "demand": num("demand"),
                               "stockpile": num("stockpile"), "supplied": breakdown("supplied"),
                               "demanded": breakdown("demanded"),
                               "hist": [float(v) for v in hist.group(1).split()] if hist else []}
            markets[int(match.group(1))] = {"center": int(center.group(1)),
                                            "pop": float(pop.group(1)) if pop else None,
                                            "members": _ids(members.group(1)) if members else [],
                                            "goods": goods}
        result["markets"] = markets
        del text

        s, e = _section(view, "trade_path_manager")
        text = view[s:e].decode()
        paths = {}
        for match in re.finditer(r"\n(\d+)=\{\n\tversion=\d+\n\tfrom=(\d+)\n\tto=(\d+)\n(.*?)\n\}", text, re.S):
            date = re.search(r"date=([\d.]+)", match.group(4))
            paths[int(match.group(1))] = (int(match.group(2)), int(match.group(3)),
                                          date.group(1) if date else None)
        result["paths"] = paths

        s, e = _section(view, "trade_manager")
        text = view[s:e].decode()
        trades = []
        for match in re.finditer(r"\n(\d+)=\{\n(.*?)\n\}", text, re.S):
            body = match.group(2)

            def field(key):
                found = re.search(r"\t" + key + r"=([^\s]+)", body)
                return found.group(1) if found else None

            if field("which") is None:
                continue
            trades.append({"owner": field("trade_owner"), "which": field("which"),
                           "size": float(field("size") or 0), "path": int(field("trade_path") or 0)})
        result["trades"] = trades

        s, e = _section(view, "road_network")
        result["roads"] = [(int(a), int(b), c) for a, b, c in re.findall(
            r"from=(\d+)\s*\n\s*to=(\d+)\s*\n\s*type=(\w+)", view[s:e].decode())]

        s, e = _section(view, "disease_outbreak_manager")
        outbreaks = []
        for rec in re.split(r"\n(?=\d+=\{\n)", view[s:e].decode())[1:]:
            kind = re.search(r"type=(\w+)", rec)
            date = re.search(r"outbreak_date=([\d.]+)", rec)
            origin = re.search(r"origin=(\d+)", rec)
            ever = re.search(r"locations_ever_affected=(\{[^}]*\}|\d+)", rec)
            outbreaks.append({"type": kind.group(1) if kind else None, "date": date.group(1) if date else None,
                              "origin": int(origin.group(1)) if origin else None,
                              "ever": _ids(ever.group(1)) if ever else []})
        result["disease_counts"] = collections.Counter(o["type"] for o in outbreaks)
        result["disease"] = [o for o in outbreaks if len(o["ever"]) >= 300]
        s, e = _section(view, "institution_manager")
        result["institution_manager"] = view[s:e].decode()
        view.close()
    out.write_text(json.dumps(result), encoding="utf-8")
    print(f"{path.name[:10]} locations={len(locations)} markets={len(markets)} trades={len(trades)} "
          f"{time.time() - t0:.0f}s", flush=True)


def extract() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    saves = sorted(ARCHIVE.glob("*/*.eu5"))
    for i, save in enumerate(saves):
        target = CACHE / (save.name[:10] + ".json")
        if target.exists():
            continue
        extract_one(save, target, keep_history=(i == len(saves) - 1))


# ---------------------------------------------------------------- report
def _bfs(nbrs, src):
    dist = [-1] * len(nbrs)
    dist[src] = 0
    queue = [src]
    for u in queue:
        for v in nbrs[u]:
            if dist[v] < 0:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def report() -> None:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    files = sorted(CACHE.glob("*.json"))
    snaps = {int(f.name[:4]): json.loads(f.read_text(encoding="utf-8")) for f in files}
    years = sorted(snaps)
    last = snaps[years[-1]]
    names = {int(k): v for k, v in last["names"].items()}
    by_name = {v: k for k, v in names.items()}
    node_of = {by_name[n["name"]]: n["id"] for n in graph["nodes"]}
    nbrs = [n["nbrs"] for n in graph["nodes"]]
    setup_owner = {by_name[n["name"]]: n.get("owner_tag") for n in graph["nodes"]}
    land = list(node_of)
    edges = {frozenset((n["id"], v)) for n in graph["nodes"] for v in n["nbrs"]}
    res = {"playthrough": last["meta"].get("playthrough_id"), "version": last["meta"].get("version"),
           "dates": [snaps[y]["meta"]["date"] for y in years], "land_nodes": len(land)}

    # A. structure per decade
    rows, prev, first_pairs, prev_pairs = [], None, None, None
    for y in years:
        snap = snaps[y]
        locs, tags = snap["locations"], snap["tags"]
        owner = {l: tags.get(locs[str(l)].get("o")) for l in land if locs[str(l)].get("o")}
        market = {l: locs[str(l)].get("m") for l in land}
        paths = {int(k): v for k, v in snap["paths"].items()}
        pairs = {frozenset(paths[t["path"]][:2]) for t in snap["trades"] if t["path"] in paths}
        roads = [(a, b, c) for a, b, c in snap["roads"]
                 if a in node_of and b in node_of and frozenset((node_of[a], node_of[b])) in edges]
        rows.append({
            "year": y, "owned_land": len(owner), "owner_countries": len(set(owner.values())),
            "owner_tag_differs_from_1337": sum(1 for l in land if owner.get(l) != setup_owner.get(l)
                                               and (owner.get(l) or setup_owner.get(l))),
            "owner_changed_vs_prev_save": sum(1 for l in land if owner.get(l) != prev[0].get(l)) if prev else None,
            "market_changed_vs_prev_save": sum(1 for l in land if market.get(l) != prev[1].get(l)) if prev else None,
            "markets": len(snap["markets"]), "roads_on_graph_edges": len(roads),
            "road_share_of_graph_edges": round(len(roads) / len(edges), 3),
            "paved_roads": sum(1 for r in roads if r[2] == "paved_road"),
            "trade_paths": len(paths), "trades": len(snap["trades"]), "trading_market_pairs": len(pairs),
            "pair_jaccard_vs_prev_save": round(len(pairs & prev_pairs) / len(pairs | prev_pairs), 3) if prev_pairs else None,
            "pair_jaccard_vs_first_save": round(len(pairs & first_pairs) / len(pairs | first_pairs), 3) if first_pairs else None,
        })
        prev, prev_pairs = (owner, market), pairs
        first_pairs = first_pairs or pairs
    res["structure_by_decade"] = rows

    # B. coffee / tea / tobacco presence in the in-game economy
    goods_rows = {}
    for good in ("coffee", "tea", "tobacco"):
        out = []
        for y in years:
            snap = snaps[y]
            centre = {int(k): names[v["center"]] for k, v in snap["markets"].items()}
            paths = {int(k): v for k, v in snap["paths"].items()}
            pop_markets, prod_markets = [], []
            for mid, mk in snap["markets"].items():
                g = mk["goods"].get(good)
                if not g:
                    continue
                if g["demanded"].get("Pops", 0) > 0:
                    pop_markets.append(centre[int(mid)])
                if any(k != "Trade" and v > 0 for k, v in g["supplied"].items()):
                    prod_markets.append(centre[int(mid)])
            flows = collections.Counter()
            for t in snap["trades"]:
                if t["which"] == good and t["path"] in paths:
                    a, b = paths[t["path"]][:2]
                    flows[f"{centre.get(a)}->{centre.get(b)}"] += t["size"]
            out.append({"year": y, "global_production": round(snap["produced_goods"].get(good, 0), 1),
                        "markets_with_pop_demand": len(pop_markets), "markets_producing": sorted(prod_markets),
                        "trades": sum(1 for t in snap["trades"] if t["which"] == good),
                        "top_flows": [[k, round(v, 2)] for k, v in flows.most_common(8)]})
        goods_rows[good] = out
    res["goods"] = goods_rows
    res["price_history_lengths"] = {y: collections.Counter(
        len(g["hist"]) for mk in snaps[y]["markets"].values() for g in mk["goods"].values()).most_common(2)
        for y in years}

    # C. institutions as an in-engine diffusion yardstick
    origins, first_seen, counts = {}, {}, collections.defaultdict(dict)
    owners = {y: {node_of[int(l)]: v.get("o") for l, v in snaps[y]["locations"].items() if int(l) in node_of}
              for y in years}
    for y in years:
        snap = snaps[y]
        for name, origin in re.findall(
                r"\n\t\t(\w+)=\{\n\t\t\tactive=yes(?:\n\t\t\tmonths=\d+)?\n\t\t\torigin=(\d+)",
                snap["institution_manager"]):
            origins.setdefault(name, (int(origin), y))
        c, c100 = collections.Counter(), collections.Counter()
        for lid, rec in snap["locations"].items():
            if int(lid) not in node_of:
                continue
            for name, value in rec.get("inst", {}).items():
                if value > 0:
                    c[name] += 1
                    first_seen.setdefault((name, node_of[int(lid)]), y)
                if value >= 100:
                    c100[name] += 1
        for name in c:
            counts[name][y] = [c[name], c100[name]]
    inst = {}
    for name, (origin, y0) in origins.items():
        fy = {v: y for (n, v), y in first_seen.items() if n == name}
        dist = _bfs(nbrs, node_of[origin])
        bands = collections.defaultdict(list)
        for v, y in fy.items():
            if dist[v] >= 0:
                bands[dist[v] // 10 * 10].append(y)
        later = [(v, y) for v, y in fy.items() if y != y0]
        isolated = sum(1 for v, y in later if all(fy.get(u, 9999) > y for u in nbrs[v]))
        had = collections.defaultdict(set)
        for v, y in fy.items():
            for yy in years:
                if yy >= y:
                    had[yy].add(owners[yy].get(v))
        via_owner = 0
        for v, y in later:
            py = years[years.index(y) - 1]
            if owners[py].get(v) and owners[py].get(v) in had[py]:
                via_owner += 1
        inst[name] = {"origin": names[origin], "first_active_save": y0,
                      "locations_gt0_and_100_by_save": counts[name],
                      "median_first_save_by_hop_band": {b: sorted(v)[len(v) // 2] for b, v in sorted(bands.items())},
                      "arrivals_after_first_save": len(later),
                      "isolated_arrival_share": round(isolated / max(len(later), 1), 3),
                      "owner_already_had_it_share": round(via_owner / max(len(later), 1), 3)}
    res["institutions"] = inst

    # D. ownership history in the last save vs decade snapshots
    def month(date):
        y, m, _ = date.split(".")
        return int(y) * 12 + int(m) - 1

    hist = {int(l): [(month(d), o) for d, o in v] for l, v in last["ownership_history"].items() if int(l) in node_of}

    def owner_at(h, t):
        found = None
        for tm, ow in h:
            if tm > t:
                break
            found = ow
        return found

    agreement = {}
    for y in years[2::5]:
        locs = snaps[y]["locations"]
        t = y * 12 + 3
        tot = sum(1 for l in hist if locs[str(l)].get("o"))
        agreement[y] = [sum(1 for l, h in hist.items() if owner_at(h, t) == locs[str(l)].get("o")), tot]
    stable = total = 0
    for t0 in range(1340 * 12, 1490 * 12 + 1, 60):
        for h in hist.values():
            if owner_at(h, t0) is None:
                continue
            total += 1
            stable += not any(t0 < tm <= t0 + 240 for tm, _ in h)
    tenures = sorted(b - a for h in hist.values() for (a, _), (b, _) in zip(h, h[1:]))
    res["ownership"] = {"locations_with_history": len(hist), "history_vs_snapshot_agreement": agreement,
                        "p_no_owner_change_within_240_months": round(stable / total, 3),
                        "completed_tenures": len(tenures), "median_tenure_months": tenures[len(tenures) // 2],
                        "share_tenures_under_240_months": round(sum(t < 240 for t in tenures) / len(tenures), 3)}

    # E. plague footprint
    res["disease"] = {"counts_last_save": last["disease_counts"], "large_outbreaks": [
        {"type": o["type"], "date": o["date"], "origin": names.get(o["origin"]),
         "ever_affected": len(o["ever"]), "ever_affected_land": sum(1 for l in o["ever"] if l in node_of)}
        for o in last["disease"] if o["type"] == "bubonic_plague"]}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    {"extract": extract, "report": report}[sys.argv[1]]()
