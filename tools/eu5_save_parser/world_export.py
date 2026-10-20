"""Versioned, resumable world inputs for diffusion; deliberately excludes goods trade.

python -m tools.eu5_save_parser.world_export --archive data/saves/observer_archive --out tmp/obsession_worlds
Only completed archived saves are read. Original saves and the archiver are untouched.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import sys
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from . import parser as P

FORMAT = "obsession.world-snapshot/2"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
                               default=json_scalar), encoding="utf-8")
    temp.replace(path)


def json_scalar(value):
    """Scientific diagnostic scalars have the same JSON value as Python ones."""
    if type(value).__module__.startswith("numpy") and hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def records(view, section):
    a, b = P._top_level_bounds(view, section)
    matches = list(re.finditer(rb"(?m)^(\d+)=\{\r?$", view[a:b]))
    for i, match in enumerate(matches):
        yield str(int(match.group(1))), view[a + match.end():a + (matches[i + 1].start() if i + 1 < len(matches) else b - a)]


def scalar(body, key, default=None):
    found = re.search(rb"(?m)^\t" + key.encode() + rb"=([^\s{}]+)\r?$", body)
    return found.group(1).decode().strip('"') if found else default


def identity_tables(view):
    cultures,_=P._parse_identity_definitions(view,"culture_manager","culture_definition")
    religions,groups=P._parse_identity_definitions(view,"religion_manager","definition")
    return cultures,religions,groups


def extra_world(view, location_names, country_tags, tables=None):
    cultures,religions,groups=tables or identity_tables(view)
    countries, markets = {}, {}
    for cid, body in records(view, "countries"):
        cap = scalar(body, "capital")
        if cap is not None:
            culture=scalar(body,"primary_culture",scalar(body,"culture"))
            religion=scalar(body,"primary_religion",scalar(body,"religion"))
            countries[cid] = {"tag": country_tags.get(int(cid)), "capital": location_names.get(int(cap)),
                              "culture_instance":culture,"religion_instance":religion,
                              "culture":cultures.get(culture,culture),"religion":religions.get(religion,religion),
                              "religion_group":groups.get(religions.get(religion,religion))}
    for mid, body in records(view, "market_manager"):
        center = scalar(body, "center")
        if center is None:
            continue
        powers = {}
        for merchant in re.finditer(rb"(?m)^\tmerchant=\{(.*?)^\t\}", body, re.S | re.M):
            rec = merchant.group(1)
            c = re.search(rb"(?m)^\t\tcountry=(\d+)", rec)
            p = re.search(rb"(?m)^\t\tpower=([-+0-9.eE]+)", rec)
            if c and p:
                key, power = c.group(1).decode(), float(p.group(1))
                if power > 0:
                    powers[key] = powers.get(key, 0) + power
        total = sum(powers.values())
        markets[mid] = {"center": location_names.get(int(center)),
                        "merchants": {c: power / total for c, power in powers.items()} if total else {}}
    a, b = P._top_level_bounds(view, "road_network")
    roads = [[location_names.get(int(a)), location_names.get(int(b)), kind.decode()]
             for a, b, kind in re.findall(rb"from=(\d+)\s+to=(\d+)\s+type=(\w+)", view[a:b])]
    return countries, markets, roads


def export_world(save, out):
    save, out = Path(save), Path(out)
    before = (save.stat().st_size, save.stat().st_mtime_ns)
    parsed = P.parse_save(save)
    tables=(parsed.culture_names,parsed.religion_names,parsed.religion_groups)
    with save.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
        countries, markets, roads = extra_world(view, parsed.location_names, parsed.country_tags,tables)
    locations = {}
    for loc in parsed.locations:
        if loc.name is None:
            continue
        locations[loc.name] = {
            "owner": str(loc.owner_id) if loc.owner_id is not None else None,
            "market": str(loc.market_id) if loc.market_id is not None else None,
            "population": sum(parsed.populations[p].size for p in loc.pop_ids if p in parsed.populations),
            **{key: getattr(loc, key) for key in ("culture", "religion", "rank", "raw_material", "proximity",
                                                "market_access", "road_to_capital", "institutions")}}
        locations[loc.name].update(culture_instance=loc.culture,religion_instance=loc.religion,
                                  culture=parsed.culture_names.get(loc.culture,loc.culture),
                                  religion=parsed.religion_names.get(loc.religion,loc.religion))
    source_hash = digest(save)
    if before != (save.stat().st_size, save.stat().st_mtime_ns):
        raise P.SaveFormatError("Save changed while extracting; retry after archive completes")
    result = {"format": FORMAT, "metadata": dict(parsed.metadata),
              "source": {"name": save.name, "size": before[0], "mtime_ns": before[1], "sha256": source_hash},
              "locations": locations, "countries": countries, "markets": markets, "roads": roads,
              "identity_tables":{"culture":dict(tables[0]),"religion":dict(tables[1])},"religion_groups":dict(tables[2]),
              "boundary": "Merchant share = positive saved power / total positive power. No commodity quantities or routes."}
    write_world(out,result)
    return result


def write_world(out,result):
    out=Path(out)
    atomic_json(out, result)
    # Formal tabular export is useful to consumers other than this simulator.
    for name, rows, columns in (
        ("roads", [{"from": a, "to": b, "type": k} for a, b, k in result['roads']], ["from", "to", "type"]),
        ("merchants", [{"market": m, "country": c, "share": s} for m, rec in result['markets'].items()
                       for c, s in rec["merchants"].items()], ["market", "country", "share"])):
        with out.with_suffix("." + name + ".csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)


def upgrade_world(save,existing,out):
    """Resolve v1 runtime ids without rereading millions of population objects."""
    save=Path(save)
    before=(save.stat().st_size,save.stat().st_mtime_ns)
    with save.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as view:
        metadata,names=P._parse_metadata(view,*P._top_level_bounds(view,'metadata'))
        tags=P._parse_country_tags(view,*P._top_level_bounds(view,'countries'))
        tables=identity_tables(view)
        countries,markets,roads=extra_world(view,names,tags,tables)
    if digest(save)!=existing['source']['sha256'] or before!=(save.stat().st_size,save.stat().st_mtime_ns):
        raise P.SaveFormatError('Source save changed; cannot reuse v1 population extraction')
    for loc in existing['locations'].values():
        culture,religion=loc.get('culture'),loc.get('religion')
        loc.update(culture_instance=culture,religion_instance=religion,
                   culture=tables[0].get(culture,culture),religion=tables[1].get(religion,religion))
    existing.update(format=FORMAT,metadata=metadata,countries=countries,markets=markets,roads=roads,
                    identity_tables={'culture':dict(tables[0]),'religion':dict(tables[1])},religion_groups=dict(tables[2]))
    write_world(out,existing)
    return existing


def archive_worlds(archive, out, progress=print):
    manifests = []
    for folder in sorted(Path(archive).iterdir()):
        if not folder.is_dir():
            continue
        entries = []
        manifest=Path(out)/folder.name/'timeline.json'
        previous=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
        old_entries={e['file']:e for e in previous.get('snapshots',[])}
        for save in sorted(folder.glob("*.eu5")):
            target = Path(out) / folder.name / (save.stem + ".json")
            existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
            signature = {"name": save.name, "size": save.stat().st_size, "mtime_ns": save.stat().st_mtime_ns}
            same=existing is not None and all(existing.get('source',{}).get(k)==v for k,v in signature.items())
            if same and existing.get('format')=='obsession.world-snapshot/1':
                existing=upgrade_world(save,existing,target)
                progress(f"Upgraded identity keys {save.name}",flush=True)
            elif not same or existing.get("format") != FORMAT:
                existing = export_world(save, target)
                progress(f"Extracted {save.name}: {len(existing['locations'])} locations", flush=True)
            entry={"date": existing["metadata"]["date"], "file": target.name, "sha256": digest(target)}
            old=old_entries.get(target.name,{})
            if old.get('sha256')==entry['sha256']:
                entry.update({k:old[k] for k in ('relations_file','relations_sha256','relations_complete') if k in old})
            entries.append(entry)
        if entries:
            entries.sort(key=lambda e: tuple(map(int, e["date"].split("."))))
            manifest = Path(out) / folder.name / "timeline.json"
            atomic_json(manifest, {**previous,"format": "obsession.world-timeline/1", "kind": "O", "id": folder.name,
                                   "resolution_years": 10, "snapshots": entries,
                                   'relations_complete':all(e.get('relations_complete') is True for e in entries)})
            manifests.append(str(manifest))
    from .relationships_export import archive_relationships
    archive_relationships(archive,out,progress)
    return manifests


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path)
    ap.add_argument("--save", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if bool(args.archive) == bool(args.save):
        ap.error("specify exactly one of --archive or --save")
    if args.archive:
        print(json.dumps(archive_worlds(args.archive, args.out)))
    else:
        export_world(args.save, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
