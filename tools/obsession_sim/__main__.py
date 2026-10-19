"""Command line: python -m tools.obsession_sim <command> ...

  presets                              list parameter sets
  graph-info  --graph G                degree stats and validation
  serve       --graph G               shared real/hex map editor and Python recomputation
  run         --graph G --preset P     run one scenario, write summary/series JSON
              [--groups N] [--seed-node V | --seed-name NAME] [--set key=value ...]
              [--milestones M.json --start-year Y] [--playback out.json --frames-every K]
              [--budget U] [--out result.json]

G is "hex" (synthetic 117x116 grid) or a graph JSON file (see README.md).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from . import graph as G
from .core import Simulation
from .export import export_playback, export_html
from .metrics import milestones, front_profile, front_speed
from .presets import PRESETS, make_params
from .scenario import apply_scenario


def load_graph(arg, groups=None, group_seed=20261019):
    g = G.hex_grid() if arg == "hex" else G.load_json(arg)
    if groups:
        g.owner = G.voronoi_groups(g, groups, seed=group_seed)
        g.group_names = [f"g{i}" for i in range(groups)]
    return g


def parse_value(v):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return {"true": True, "false": False, "none": None}.get(v.lower(), v)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tools.obsession_sim", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("presets")
    gi = sub.add_parser("graph-info")
    gi.add_argument("--graph", required=True)
    imp = sub.add_parser("import-eu5", help="extract real location topology and map geometry from installed game")
    imp.add_argument("--game", type=Path, required=True, help="EU5 installation, game, or map_data directory")
    imp.add_argument("--out", type=Path, required=True)
    imp.add_argument("--locations-csv", type=Path)
    imp.add_argument("--allow-partial-csv", action="store_true", help="explicitly allow a save/1337 mixed snapshot")
    imp.add_argument("--no-straits", action="store_true")
    imp.add_argument("--raster-width", type=int, default=2048)
    serve = sub.add_parser("serve", help="shared real/hex map controls with the same Python simulation core")
    serve.add_argument("--graph", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--scenario", type=Path)
    serve.add_argument("--preset", default="baseline", choices=sorted(PRESETS))
    r = sub.add_parser("run")
    r.add_argument("--graph", required=True)
    r.add_argument("--preset", default="baseline", choices=sorted(PRESETS))
    r.add_argument("--groups", type=int, help="synthesise N Voronoi clock groups (hex grid has none)")
    r.add_argument("--clock-group", choices=("owner", "province", "area"), default="owner",
                   help="explicit offline sensitivity experiment; default keeps actual owners")
    r.add_argument("--seed-node", type=int)
    r.add_argument("--seed-name")
    r.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    r.add_argument("--budget", type=int)
    r.add_argument("--milestones", type=Path)
    r.add_argument("--start-year", type=float)
    r.add_argument("--playback", type=Path)
    r.add_argument("--html", type=Path, help="standalone offline viewer with embedded replay")
    r.add_argument("--scenario", type=Path, help="explicit seeds, corridors, routes and milestone targets")
    r.add_argument("--frames-every", type=int, default=12)
    r.add_argument("--series-every", type=int, default=12)
    r.add_argument("--out", type=Path)
    a = ap.parse_args(argv)

    if a.cmd == "presets":
        for k, v in PRESETS.items():
            print(f"{k:18s} {v['doc']}")
        return 0
    if a.cmd == "serve":
        from .server import build_server
        server = build_server(a.graph, host="127.0.0.1", port=a.port, scenario=a.scenario, preset=a.preset)
        print(f"Map simulator: http://127.0.0.1:{server.server_address[1]}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    if a.cmd == "import-eu5":
        from .eu5_map import import_eu5
        g = import_eu5(a.game, locations_csv=a.locations_csv, include_straits=not a.no_straits,
                       raster_width=a.raster_width, allow_partial_csv=a.allow_partial_csv)
        probs = g.validate()
        if probs:
            raise ValueError("invalid imported graph: " + "; ".join(probs[:10]))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        G.save_json(g, a.out)
        print(json.dumps({"out": str(a.out), **g.degree_stats(), "meta": {k: v for k, v in g.meta.items()
                         if k not in ("geometry", "map_raster")}}, ensure_ascii=False))
        return 0
    if a.cmd == "graph-info":
        g = load_graph(a.graph)
        print(json.dumps(g.degree_stats(), ensure_ascii=False))
        probs = g.validate()
        print("valid" if not probs else "\n".join(probs[:50]))
        return 0 if not probs else 1

    g = load_graph(a.graph, a.groups)
    if a.clock_group != "owner":
        if a.groups:
            ap.error("--clock-group and --groups are mutually exclusive")
        values = g.attrs.get(a.clock_group)
        if not values or any(not v for v in values):
            ap.error(f"graph must have complete {a.clock_group} attributes")
        groups = sorted(set(values))
        group_index = {name: i for i, name in enumerate(groups)}
        g.owner = [group_index[value] for value in values]
        g.group_names = groups
        g.meta["clock_group"] = a.clock_group
    probs = g.validate()
    if probs:
        print("graph problems:\n" + "\n".join(probs[:20]))
        return 1
    scenario = json.loads(a.scenario.read_text(encoding="utf-8-sig")) if a.scenario else {}
    start_year = a.start_year if a.start_year is not None else scenario.get("start_year")
    if a.seed_name:
        seed = (g.names or []).index(a.seed_name)
    elif a.seed_node is not None:
        seed = a.seed_node
    else:
        seed = g.meta.get("center", 0)
    over = {k: parse_value(v) for k, v in (s.split("=", 1) for s in a.set)}
    over = dict(scenario.get("parameters", {}), **over)
    if a.budget is not None:
        over["budget"] = a.budget
    over.setdefault("series_every", a.series_every)
    if a.playback or a.html:
        over["frames_every"] = a.frames_every
    base = make_params(a.preset, **over)
    scenario_over = apply_scenario(g, scenario, base.p, base.rho, start_year) if scenario else {}
    over.update(scenario_over)
    if (a.seed_name or a.seed_node is not None) and "seeds" in scenario_over:
        ap.error("use either scenario seeds or --seed-name/--seed-node")
    P = make_params(a.preset, center=seed, **over)
    sources = sorted({v for v, _, _ in P.seeds})
    if any(not 0 <= v < g.n for v in sources):
        ap.error("seed index outside graph")
    sim = Simulation(g, P).run()
    profile = front_profile(sim, sources) if sources else []
    reachable = sum(row["locations"] for row in profile)
    res = {"preset": a.preset, "graph": a.graph, "seed_nodes": sources, "summary": sim.summary(),
           "front_speed_hops_per_year": front_speed(profile), "front_profile": profile,
           "reachable_locations": reachable, "unreachable_locations": g.n - reachable,
           "graph_meta": {k: v for k, v in g.meta.items() if k != "geometry"},
           "params": {k: v for k, v in vars(P).items() if k not in ("rho_by_node", "p_by_node")},
           "start_year": start_year, "scenario": scenario, "series": sim.series}
    specs = json.loads(a.milestones.read_text(encoding="utf-8-sig")) if a.milestones else scenario.get("milestones", [])
    if specs:
        res["milestones"] = milestones(sim, specs, start_year=start_year)
    print(json.dumps(res["summary"], ensure_ascii=False))
    if "milestones" in res:
        for m in res["milestones"]:
            print(m)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    title = scenario.get("title", f"{a.graph}") + f" · {a.preset}"
    if P.budget is not None:
        title += f" · 服务额度 {P.budget} U/月"
    if a.playback:
        a.playback.parent.mkdir(parents=True, exist_ok=True)
        export_playback(sim, a.playback, title=title,
                        note=scenario.get("note", ""), start_year=start_year, milestone_results=res.get("milestones"))
        print(f"playback written: {a.playback}")
    if a.html:
        a.html.parent.mkdir(parents=True, exist_ok=True)
        export_html(sim, a.html, title=title,
                    note=scenario.get("note", ""), start_year=start_year, milestone_results=res.get("milestones"))
        print(f"offline report written: {a.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
