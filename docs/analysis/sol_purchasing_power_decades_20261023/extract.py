"""Extract purchasing-power caches without deserializing population objects."""
from __future__ import annotations

import json
import mmap
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.eu5_save_parser.parser import _metadata_scalar, _parse_country_tags, _top_level_bounds

SERIES = "c681faf6-91c6-45a9-bde4-9d8c22cd321e"
ARCHIVE = ROOT / "data/saves/observer_archive" / SERIES
OUTPUT = ROOT / "data/save_analysis/purchasing_power_decades" / SERIES
STRATA = ("nobles", "clergy", "burghers", "commoners")
SCHEMA = 1
LOCATION = re.compile(rb"(?m)^\t\t(\d+)=\{\r?$")
OWNER = re.compile(rb"(?m)^\t{3}owner=(\d+)\r?$")
LOCAL_VALUE = re.compile(
    rb"(?m)^\t{6}flag=sol_location_(nobles|clergy|burghers|commoners)_(liquid_funds|base_spending|net_income)\r?\n"
    rb"\t{6}data=\{\r?\n\t{7}type=value\r?\n(?:\t{7}identity=(\d+)\r?\n)?"
)
COUNTRY = re.compile(rb"(?m)^(\d+)=\{\r?\n\tcountry_name=")
COUNTRY_VALUE = re.compile(
    rb"(?m)^\t{4}flag=(sol_country_(?:demand_target|base_spending)_(?:nobles|clergy|burghers|commoners)|"
    rb"sol_ls_pop_(?:nobles|clergy|burghers|commoners)|sol_substitute_year)\r?\n"
    rb"\t{4}data=\{\r?\n\t{5}type=value\r?\n(?:\t{5}identity=(\d+)\r?\n)?"
)
ORIGINAL_TAG = re.compile(rb'(?m)^\toriginal_tag="?([^"\r\n]+)"?\r?$')


def signed_int(raw):
    value = int(raw or 0)
    return value - (1 << 64) if value >= (1 << 63) else value


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
        assert playthrough == SERIES and date == f"{year}.4.1", (path.name, date, playthrough)
        country_start, country_end = _top_level_bounds(view, "countries")
        tags = _parse_country_tags(view, country_start, country_end)
        country_records = list(COUNTRY.finditer(view, country_start, country_end))
        country_data = {}
        for i, match in enumerate(country_records):
            cid = int(match.group(1))
            if cid not in tags:
                continue
            end = country_records[i + 1].start() if i + 1 < len(country_records) else country_end
            original = ORIGINAL_TAG.search(view, match.start(), end)
            original_tag = original.group(1).decode() if original else tags[cid]
            values = {m.group(1).decode(): signed_int(m.group(2)) for m in COUNTRY_VALUE.finditer(view, match.start(), end)}
            country_data[cid] = {"tag": tags[cid], "lineage": f"{cid}|{original_tag}", "values": values}
        start, end = _top_level_bounds(view, "locations")
        entries = list(LOCATION.finditer(view, start, end))
        totals = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        owned_count, cached_count = 0, 0
        for i, match in enumerate(entries):
            stop = entries[i + 1].start() if i + 1 < len(entries) else end
            owner = OWNER.search(view, match.start(), stop)
            if owner is None:
                continue
            cid = int(owner.group(1))
            assert cid in tags, (path.name, "unknown owner", cid)
            owned_count += 1
            values = list(LOCAL_VALUE.finditer(view, match.start(), stop))
            if not values:
                continue
            cached_count += 1
            seen = set()
            for value in values:
                stratum, metric = value.group(1).decode(), value.group(2).decode()
                assert (stratum, metric) not in seen
                seen.add((stratum, metric))
                amount = signed_int(value.group(3))
                assert amount >= 0, (path.name, stratum, metric, amount)
                totals[cid][stratum][metric] += amount
        samples = {stratum: [] for stratum in STRATA}
        for cid, strata in totals.items():
            info = country_data.get(cid, {"tag": tags[cid], "lineage": f"{cid}|{tags[cid]}", "values": {}})
            for stratum, values in strata.items():
                base = values.get("base_spending", 0)
                if base <= 0:
                    continue
                native = info["values"]
                population = native.get(f"sol_ls_pop_{stratum}", 0)
                samples[stratum].append({
                    "country_id": cid, "tag": info["tag"], "lineage": info["lineage"],
                    "funds_int": values.get("liquid_funds", 0), "base_int": base,
                    "net_income_int": values.get("net_income", 0),
                    "alpha": values.get("liquid_funds", 0) / base,
                    "cached_population_int": population,
                    "solver_funds_int": native.get(f"sol_country_demand_target_{stratum}", 0),
                    "solver_base_int": native.get(f"sol_country_base_spending_{stratum}", 0),
                    "substitution_year": native.get("sol_substitute_year", 0) / 100000,
                })
    assert len(entries) == 28573, (path.name, "location count", len(entries))
    assert cached_count > 0 and all(samples.values()), f"No usable SOL state: {path.name}"
    result = {"schema": SCHEMA, "year": year, "date": date, "version": version, "playthrough_id": playthrough,
              "source": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
              "location_count": len(entries), "owned_locations": owned_count, "cached_owned_locations": cached_count,
              "owned_countries": len(totals), "samples": samples,
              "elapsed_seconds": time.perf_counter() - started}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.part")
    temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(destination)
    return year, "extracted", result["elapsed_seconds"]


if __name__ == "__main__":
    if "--all" in sys.argv:
        paths = sorted(path for path in ARCHIVE.glob("*.eu5") if 1340 <= int(path.name[:4]) <= 1840 and int(path.name[:4]) % 10 == 0)
        assert [int(path.name[:4]) for path in paths] == list(range(1340, 1841, 10))
        with ProcessPoolExecutor(max_workers=2) as pool:
            jobs = {pool.submit(extract_save, str(path)): path for path in paths}
            for i, job in enumerate(as_completed(jobs), 1):
                year, status, seconds = job.result()
                print(f"[{i:02d}/{len(paths)}] {year} {status} ({seconds:.1f}s)", flush=True)
    else:
        for value in sys.argv[1:] or [str(next(ARCHIVE.glob("1340.*.eu5")))]:
            print(extract_save(value), flush=True)
