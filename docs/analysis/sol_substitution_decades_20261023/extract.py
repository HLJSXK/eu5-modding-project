"""Extract substitution-group state from the d2d1d136 ten-year observer series.

For each save this reads, without deserialising the whole file:
  * every country's substitution caches (multiplier, external, effective, size,
    refresh year/count, summary statistics);
  * owned-location population by (owner, market, pop type);
  * the market-keyed global maps written by the yearly market refresh
    (price weight, supply flag) and the live market list;
  * each live market's current price, recent monthly price history and
    pop demand for the 56 core goods.
It then recomputes algorithm A independently (an oracle written here, not the
generated EU5 code) from the saved populations and maps.

Usage:
  python extract.py --all          # every 1340..1840 decade save, 2 workers
  python extract.py <save> [...]   # specific saves
"""
from __future__ import annotations

import json
import mmap
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from tools.eu5_save_parser.parser import _metadata_scalar, _parse_country_tags, _top_level_bounds  # noqa: E402
from gen_whole_group_baskets import CORE, POPS, groups_for_pop  # noqa: E402

SERIES = "d2d1d136-93dd-480f-860a-b39dbb5ee4f3"
ARCHIVE = ROOT / "data/saves/observer_archive" / SERIES
OUTPUT = ROOT / "data/save_analysis/substitution_decades" / SERIES
SCHEMA = 5
JAN_OFFSET = 5
CORE = tuple(CORE)
GI = {g: i for i, g in enumerate(CORE)}
SIZES = json.loads((ROOT / "data/substitute_groups.json").read_text(encoding="utf-8"))["historical_sizes"]
BASE_ROOT = ROOT.parent / "eu5-modding-base"
if not (BASE_ROOT / "reference_game_files").is_dir():
    BASE_ROOT = ROOT / ".eu5-base"


def read_default_prices():
    prices, current = {}, None
    for path in sorted((BASE_ROOT / "reference_game_files/game/in_game/common/goods").glob("*.txt")):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            head = re.match(r"^([a-z_]+)\s*=\s*\{", line)
            if head:
                current = head.group(1)
            price = re.match(r"^\s*default_market_price\s*=\s*([0-9.]+)", line)
            if price and current:
                prices[current] = float(price.group(1))
    return prices


def read_unit_consumption():
    path = ROOT / "src/stable/in_game/common/script_values/SOL_market_unit_consumption_values.txt"
    text = path.read_text(encoding="utf-8-sig")
    table = defaultdict(dict)
    for pop, good, value in re.findall(r"sol_unit_consumption_([a-z]+)_([a-z_]+) = \{\s*value = ([-0-9.]+)", text):
        table[pop][good] = float(value)
    return table


DEFAULT = read_default_prices()
UNIT = read_unit_consumption()
GROUPS = {pop: groups_for_pop(pop) for pop in POPS}
assert all(g in DEFAULT for g in CORE), [g for g in CORE if g not in DEFAULT]

COUNTRY = re.compile(rb"(?m)^(\d+)=\{\r?\n\tcountry_name=")
CVAR = re.compile(
    rb"(?m)^\t{4}flag=(sol_sub_[a-z_]+|sol_good_effective_[a-z_]+|sol_substitute_[a-z_]+|sol_country_demand_solve_status)\r?\n"
    rb"\t{4}data=\{\r?\n\t{5}type=value\r?\n(?:\t{5}identity=(\d+)\r?\n)?")
LOCATION = re.compile(rb"(?m)^\t\t(\d+)=\{\r?$")
OWNER = re.compile(rb"(?m)^\t{3}owner=(\d+)\r?$")
LMARKET = re.compile(rb"(?m)^\t{3}market=(\d+)\r?$")
LPOPS = re.compile(rb"(?m)^\t{4}pops=\{([^}\r\n]*)\}\r?$")
POPHEAD = re.compile(rb"(?m)^(\d+)=\{\r?\n\ttype=([a-z_]+)\r?$")
POPSIZE = re.compile(rb"(?m)^\tsize=([-+0-9.eE]+)\r?$")
MAPNAME = re.compile(rb'name="([^"]+)"')
PAIR = re.compile(rb"key=\{\s*type=mark\s*(?:identity=(\d+)\s*)?\}\s*value=\{\s*type=(?:value|boolean)\s*(?:identity=(\d+)\s*)?\}")
MARKET = re.compile(rb"(?m)^(\d+)=\{\r?$")
GOODBLOCK = re.compile(rb"(?m)^\t\t([a-z_]+)=\{\r?$")


def signed(raw):
    value = int(raw or 0)
    return (value - (1 << 64) if value >= (1 << 63) else value) / 100000


def global_maps(view):
    a = view.find(b"\nvariables={")
    b = view.find(b"\nlanguage_manager={", a)
    names = [(m.start(), m.group(1).decode()) for m in MAPNAME.finditer(view, a, b)]
    wanted = {}
    for i, (start, name) in enumerate(names):
        if not name.startswith(("sol_market_substitute_weight_", "sol_market_consumes_", "sol_market_price_suppressed_")):
            continue
        end = names[i + 1][0] if i + 1 < len(names) else b
        wanted[name] = {int(p.group(1) or 0): signed(p.group(2)) for p in PAIR.finditer(view, start, end)}
    return wanted


def markets(view):
    a, b = _top_level_bounds(view, "market_manager")
    db = view.find(b"\n\tdatabase={", a, b)
    heads = list(MARKET.finditer(view, db, b))
    out = {}
    for i, head in enumerate(heads):
        mid = int(head.group(1))
        end = heads[i + 1].start() if i + 1 < len(heads) else b
        gstart = view.find(b"\n\tgoods={", head.end(), end)
        if gstart < 0:
            continue
        center = re.compile(rb"(?m)^\tcenter=(\d+)\r?$").search(view, head.end(), gstart)
        blocks = list(GOODBLOCK.finditer(view, gstart, end))
        goods = {}
        for j, block in enumerate(blocks):
            good = block.group(1).decode()
            if good not in GI:
                continue
            bend = blocks[j + 1].start() if j + 1 < len(blocks) else end
            chunk = view[block.end():bend]
            price = re.search(rb"\n\t\t\tprice=([-0-9.e]+)", chunk)
            pops = re.search(rb"\n\t\t\tdemanded=\{[^}]*?\n\t\t\t\tPops=([-0-9.e]+)", chunk)
            supply = re.search(rb"\n\t\t\tsupply=([-0-9.e]+)", chunk)
            demand = re.search(rb"\n\t\t\tdemand=([-0-9.e]+)", chunk)
            hist = re.search(rb"\n\t\t\thistory=\{ ([^}]*)\}", chunk)
            history = [float(x) for x in hist.group(1).split()] if hist else []
            goods[good] = {
                "p": float(price.group(1)) if price else None,
                "pop": float(pops.group(1)) if pops else 0.0,
                "sup": float(supply.group(1)) if supply else 0.0,
                "dem": float(demand.group(1)) if demand else 0.0,
                "h": history[-13:],
            }
        out[mid] = {"center": int(center.group(1)) if center else None, "goods": goods}
    return out


def population(view):
    a, b = _top_level_bounds(view, "population")
    db = view.find(b"\n\tdatabase={", a, b)
    heads = [(m.start(), int(m.group(1)), m.group(2).decode()) for m in POPHEAD.finditer(view, db, b)]
    sizes = [(m.start(), float(m.group(1))) for m in POPSIZE.finditer(view, db, b)]
    result, j = {}, 0
    for i, (start, pid, ptype) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else b
        while j < len(sizes) and sizes[j][0] < start:
            j += 1
        size = sizes[j][1] if j < len(sizes) and sizes[j][0] < end else 0.0
        result[pid] = (ptype, size)
    return result


def locations(view, pops):
    a, b = _top_level_bounds(view, "locations")
    db = view.find(b"\n\tlocations={", a, b)
    entries = list(LOCATION.finditer(view, db, b))
    grid = defaultdict(lambda: defaultdict(float))  # (owner, market) -> pop type -> size
    nloc = defaultdict(int)
    for i, match in enumerate(entries):
        end = entries[i + 1].start() if i + 1 < len(entries) else b
        owner = OWNER.search(view, match.start(), end)
        if owner is None:
            continue
        oid = int(owner.group(1))
        nloc[oid] += 1
        market = LMARKET.search(view, match.start(), end)
        plist = LPOPS.search(view, match.start(), end)
        if market is None or plist is None:
            continue
        cell = grid[(oid, int(market.group(1)))]
        for pid in plist.group(1).split():
            ptype, size = pops.get(int(pid), (None, 0.0))
            if ptype in POPS:
                cell[ptype] += size
    return grid, nloc, len(entries)


def oracle(country_cells, maps, external, jan_ratio):
    """Algorithm A recomputed from saved state; returns base, target, weight/price aggregates."""
    base = [0.0] * len(CORE)
    target = [0.0] * len(CORE)
    wsum = [0.0] * len(CORE)
    psum = [0.0] * len(CORE)
    for market, cell in country_cells.items():
        weights = {}
        for good in CORE:
            w = maps["sol_market_substitute_weight_" + good].get(market)
            c = maps["sol_market_consumes_" + good].get(market)
            if w is not None and c is not None and c > 0 and external[GI[good]] > 0:
                weights[good] = w
        for pop in POPS:
            amount_pop = cell.get(pop, 0.0)
            if amount_pop <= 0:
                continue
            current, neutral = defaultdict(float), defaultdict(float)
            for group, members in GROUPS[pop].items():
                active = [g for g in members if weights.get(g, 0) > 0]
                total = sum(weights[g] for g in active)
                if not active or total <= 0:
                    continue
                for g in active:
                    current[g] += SIZES[group] * weights[g] / total
                    neutral[g] += SIZES[group] / len(active)
            for g, n in neutral.items():
                if n <= 0:
                    continue
                amount = amount_pop * UNIT[pop].get(g, 0.0) * DEFAULT[g]
                k = GI[g]
                base[k] += amount
                target[k] += amount * current[g] / n
                wsum[k] += amount * weights[g]
                ratio = jan_ratio.get((market, g))
                if ratio is not None:
                    psum[k] += amount * ratio
    return base, target, wsum, psum


def extract_save(path_string):
    path = Path(path_string)
    started = time.perf_counter()
    stat = path.stat()
    year = int(path.name[:4])
    destination = OUTPUT / "snapshots" / f"{year}.json"
    if destination.is_file():
        previous = json.loads(destination.read_text(encoding="utf-8"))
        if previous.get("schema") == SCHEMA and previous.get("size") == stat.st_size and previous.get("mtime_ns") == stat.st_mtime_ns:
            return year, "cached", time.perf_counter() - started
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
        assert view[:3] == b"SAV", f"Not a plaintext save: {path.name}"
        a, b = _top_level_bounds(view, "metadata")
        date = _metadata_scalar(view, a, b, "date")
        version = _metadata_scalar(view, a, b, "version")
        playthrough = _metadata_scalar(view, a, b, "playthrough_id")
        assert playthrough == SERIES and date.startswith(f"{year}."), (path.name, date, playthrough)
        maps = global_maps(view)
        market_data = markets(view)
        pops = population(view)
        grid, nloc, location_count = locations(view, pops)
        del pops
        country_start, country_end = _top_level_bounds(view, "countries")
        tags = _parse_country_tags(view, country_start, country_end)
        records = list(COUNTRY.finditer(view, country_start, country_end))
        cvars = {}
        for i, match in enumerate(records):
            cid = int(match.group(1))
            end = records[i + 1].start() if i + 1 < len(records) else country_end
            found = list(CVAR.finditer(view, match.start(), end))
            values = {m.group(1).decode(): signed(m.group(2)) for m in found}
            if values:
                # Approximate save bytes: matched head plus the closing "}\n\t\t\t} {" lines.
                values["__bytes"] = sum(len(m.group(0)) + 12 for m in found)
                cvars[cid] = values
    # Price ratio at the January map refresh. The monthly price history's fifth
    # last entry reproduces every saved weight-map tier (checked in analysis).
    live = set(market_data)
    jan_ratio = {}
    for mid, info in market_data.items():
        for good, row in info["goods"].items():
            if len(row["h"]) >= JAN_OFFSET:
                jan_ratio[(mid, good)] = row["h"][-JAN_OFFSET] / DEFAULT[good]
    cells_by_country = defaultdict(dict)
    for (owner, market), cell in grid.items():
        cells_by_country[owner][market] = cell
    countries = []
    for cid in sorted(set(cvars) | set(nloc)):
        values = cvars.get(cid, {})
        cells = cells_by_country.get(cid, {})
        popsum = {p: sum(c.get(p, 0.0) for c in cells.values()) for p in POPS}
        row = {
            "id": cid, "tag": tags.get(cid), "nloc": nloc.get(cid, 0), "pop": round(sum(popsum.values()), 5),
            "nmk": len(cells),
            "has": "sol_substitute_initialized" in values,
            "solve": "sol_country_demand_solve_status" in values,
            "year": values.get("sol_substitute_year"), "refresh": values.get("sol_sub_perf_refresh_count"),
            "gcount": values.get("sol_substitute_goods_count"), "maxsize": values.get("sol_substitute_max_size"),
            "human": values.get("sol_sub_perf_human"), "bytes": values.get("__bytes", 0),
            "M": [values.get("sol_sub_multiplier_" + g) for g in CORE],
            "E": [values.get("sol_sub_external_" + g) for g in CORE],
            "F": [values.get("sol_good_effective_" + g) for g in CORE],
            "S": [values.get("sol_sub_size_" + g) for g in CORE],
            "stray": sorted(k for k in values if k.startswith(("sol_sub_base_", "sol_sub_target_"))),
        }
        if row["has"] and cells:
            external = [e if e is not None else 0.0 for e in row["E"]]
            base, target, wsum, psum = oracle(cells, maps, external, jan_ratio)
            row["base"] = [round(x, 6) for x in base]
            row["Mo"] = [round(t / bs, 6) if bs > 0 else 1.0 for t, bs in zip(target, base)]
            row["wavg"] = [round(w / bs, 6) if bs > 0 else None for w, bs in zip(wsum, base)]
            row["pjan"] = [round(p / bs, 6) if bs > 0 else None for p, bs in zip(psum, base)]
        countries.append(row)
    map_keys = {name: len(v) for name, v in maps.items()}
    weight_keys = set().union(*(set(maps["sol_market_substitute_weight_" + g]) for g in CORE))
    market_rows = {}
    for mid, info in market_data.items():
        market_rows[mid] = {
            "center": info["center"],
            "goods": {g: {**row, "w": maps["sol_market_substitute_weight_" + g].get(mid),
                          "c": maps["sol_market_consumes_" + g].get(mid),
                          "s": maps["sol_market_price_suppressed_" + g].get(mid)} for g, row in info["goods"].items()},
        }
    result = {
        "schema": SCHEMA, "year": year, "date": date, "version": version, "playthrough_id": playthrough,
        "source": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "goods": list(CORE), "default_price": {g: DEFAULT[g] for g in CORE},
        "location_count": location_count, "live_markets": len(live),
        "weight_map_keys": len(weight_keys), "stale_weight_keys": len(weight_keys - live),
        "live_without_weights": len(live - weight_keys), "map_key_counts": map_keys,
        "countries": countries, "markets": market_rows,
        "elapsed_seconds": time.perf_counter() - started,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.part")
    temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(destination)
    return year, "extracted", result["elapsed_seconds"]


if __name__ == "__main__":
    if "--all" in sys.argv:
        paths = sorted(p for p in ARCHIVE.glob("*.eu5") if 1340 <= int(p.name[:4]) <= 1840 and int(p.name[:4]) % 10 == 0)
        assert [int(p.name[:4]) for p in paths] == list(range(1340, 1841, 10)), [p.name for p in paths]
        workers = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--workers=")), "2"))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs = {pool.submit(extract_save, str(p)): p for p in paths}
            for i, job in enumerate(as_completed(jobs), 1):
                year, status, seconds = job.result()
                print(f"[{i:02d}/{len(paths)}] {year} {status} ({seconds:.1f}s)", flush=True)
    else:
        for value in sys.argv[1:] or [str(next(ARCHIVE.glob("1840.*.eu5")))]:
            print(extract_save(value), flush=True)
