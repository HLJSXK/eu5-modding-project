"""World state timelines. Rules receive state, never fact dates or place names."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random

import numpy as np

from .eu5_map import _parse, _pairs, _field


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def snapshot_hash(entry):
    return (canonical_hash({'world':entry['sha256'],'relations':entry['relations_sha256']})
            if entry.get('relations_sha256') else entry['sha256'])


def month_of(date, start=1337):
    y, m, *_ = map(int, date.split("."))
    if not 1 <= m <= 12:
        raise ValueError("invalid world snapshot month")
    return (y - start) * 12 + m - 1


def religion_groups(root):
    result = {}
    for path in sorted((Path(root) / "in_game/common/religions").glob("*.txt")):
        for key, body in _pairs(_parse(path)):
            if isinstance(body, list):
                group = _field(body, "group")
                if group:
                    result[key] = group
    return result


class SnapshotSequence:
    """Load an observer snapshot only when its world is actually needed.

    Historical parameter scans need the initial allocation only. Loading every
    late observer world in every worker would waste gigabytes beside the game.
    """
    def __init__(self,path,manifest):
        self.path,self.manifest,self.cache=Path(path),manifest,{}
        self.index = None
        entries=manifest["snapshots"]
        dates=[month_of(e["date"]) for e in entries]
        if not dates or any(a>=b for a,b in zip(dates,dates[1:])):
            raise ValueError("timeline must contain strictly increasing snapshot dates")

    def __len__(self):
        return len(self.manifest["snapshots"])

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]

    def __getitem__(self,index):
        if index<0:
            index+=len(self)
        if index in self.cache:
            return self.cache[index]
        entry=self.manifest["snapshots"][index]
        target = (self.path.parent / entry["file"]).resolve()
        if not target.is_relative_to(self.path.parent.resolve()):
            raise ValueError("snapshot path escapes timeline directory")
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("world snapshot hash mismatch: " + entry["file"])
        snap = json.loads(raw)
        if snap.get("format") != "obsession.world-snapshot/2" or snap["metadata"]["date"] != entry["date"]:
            raise ValueError("world snapshot metadata mismatch")
        if snap["metadata"].get("playthrough_id") != self.manifest["id"]:
            raise ValueError("mixed playthroughs in one world")
        if bool(entry.get('relations_file'))!=bool(entry.get('relations_sha256')):
            raise ValueError('incomplete relationship supplement reference')
        if entry.get('relations_file'):
            relation_path=(self.path.parent/entry['relations_file']).resolve()
            if not relation_path.is_relative_to(self.path.parent.resolve()):
                raise ValueError('relationship supplement escapes timeline directory')
            relation_raw=relation_path.read_bytes()
            if hashlib.sha256(relation_raw).hexdigest()!=entry['relations_sha256']:
                raise ValueError('relationship supplement hash mismatch')
            relations=json.loads(relation_raw)
            if (relations.get('format')!='obsession.world-relations/1' or relations.get('date')!=entry['date']
                    or relations.get('playthrough_id')!=self.manifest['id'] or relations.get('world_snapshot_sha256')!=entry['sha256']
                    or relations.get('source_sha256')!=snap.get('source',{}).get('sha256')):
                raise ValueError('relationship source/world/date mismatch')
            links=list(snap.get('links',[]))
            for relation in relations['relations']:
                a,b=relation['first'],relation['second'];kind=relation['kind']
                if kind not in ('marriage','diplomacy') or a not in snap['countries'] or b not in snap['countries']:
                    raise ValueError('invalid relationship endpoints/kind')
                for actor,other in ((a,b),(b,a)):
                    links.append({'kind':kind,'actor':actor,'other':other,'good':None,
                                  'fact_id':f'O:{kind}:{a}:{b}'})
            snap['links']=links
        snap["_snapshot_sha256"] = snapshot_hash(entry)
        self.cache[index]=snap
        while len(self.cache)>2:
            del self.cache[next(iter(self.cache))]
        return snap

    def summary(self):
        """Retain small identifier indexes, rather than every population dict."""
        if self.index is None:
            countries,markets,faiths=set(),set(),{}
            for snapshot in self:
                countries.update(snapshot['countries'])
                countries.update(loc['owner'] for loc in snapshot['locations'].values() if loc.get('owner'))
                markets.update(snapshot['markets'])
                faiths.update(snapshot.get('religion_groups',{}))
            self.index=(sorted(countries),sorted(markets),faiths)
        return self.index


def read_timeline(path,*,lazy=False):
    path=Path(path)
    manifest=json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("format") != "obsession.world-timeline/1":
        raise ValueError("unsupported world timeline")
    sequence=SnapshotSequence(path,manifest)
    return manifest,sequence if lazy else list(sequence)


def historical_base(graph, observed_initial, reference_root):
    """1337 ownership, capitals, populations, faiths and roads from engine setup.

    Market boundaries use the earliest observed engine allocation, a declared
    near-start approximation. Foreign residency comes ONLY from cited facts.
    """
    root = Path(reference_root)
    setup = root / "main_menu/setup/1337"
    result = deepcopy(observed_initial)
    result["metadata"] = {"date": "1337.1.1", "playthrough_id": "R"}
    result["source"] = {"kind": "engine 1337 setup", "market_boundary_proxy": observed_initial["metadata"]["date"],
                         "reference_root": str(root), "grade": "W-C", "market_only": True}
    countries = _field(_field(_parse(setup / "10_countries.txt"), "countries", []), "countries", [])
    definitions={}
    for path in sorted((root/'in_game/setup/countries').glob('*.txt')):
        for tag,body in _pairs(_parse(path)):
            if isinstance(body,list):
                definitions[tag]={'culture':_field(body,'culture_definition'),'religion':_field(body,'religion_definition')}
    result["countries"] = {tag: {"tag": tag, "capital": _field(body, "capital"),
                                  "culture": _field(body, "culture") or definitions.get(tag,{}).get('culture'),
                                  "religion": _field(body, "religion") or definitions.get(tag,{}).get('religion')}
                           for tag, body in _pairs(countries) if isinstance(body, list)}
    pops = _field(_parse(setup / "06_pops.txt"), "locations", [])
    population = {}
    for name, body in _pairs(pops):
        if isinstance(body, list):
            population[name] = sum(float(_field(pop, "size", 0)) for key, pop in _pairs(body)
                                   if key == "define_pop" and isinstance(pop, list))
    static_columns = {key:graph.attrs.get(key) or [None]*graph.n for key in ("culture","religion","raw_material")}
    for v, name in enumerate(graph.names):
        loc = result["locations"][name]
        loc["owner"] = graph.group_names[graph.owner[v]] if graph.owner[v] >= 0 else None
        loc["population"] = population.get(name, 0.)
        for key in ("culture", "religion", "raw_material"):
            loc[key] = static_columns[key][v]
    result["roads"] = [[a, b, "gravel_road"] for a, b in _pairs(
        _field(_parse(setup / "09_roads.txt"), "road_network", [])) if isinstance(b, str)]
    for rec in result["markets"].values():
        # Domestic residency is structural, independent of any one commodity.
        center = result["locations"].get(rec["center"], {})
        rec["merchants"] = {center["owner"]: 1.} if center.get("owner") else {}
        rec["domestic"] = True
    result["links"], result["facts_active"] = [], []
    result.pop("_snapshot_sha256", None)
    result["_snapshot_sha256"] = canonical_hash(result)
    return result


def sample_facts(facts, seed, omit_wc=False):
    out = []
    for row in facts:
        required = {"id", "fact", "actor_location", "start", "end", "grade", "source", "goods", "kind"}
        if not required <= row.keys():
            raise ValueError("incomplete world fact: " + str(row.get("id")))
        if row["grade"] not in ("W-A", "W-B", "W-C"):
            raise ValueError("invalid fact evidence grade")
        if omit_wc and row["grade"] == "W-C":
            continue
        rec = deepcopy(row)
        # Keyed streams keep the other facts unchanged during ablations.
        rng = random.Random(canonical_hash([seed, "world", row["id"]]))
        for key in ("start", "end"):
            value = row[key]
            if isinstance(value, list):
                if len(value) != 2 or value[1] < value[0]:
                    raise ValueError("invalid world fact interval")
                value = rng.uniform(*value)
            rec[key + "_month"] = round((value - 1337) * 12)
        out.append(rec)
    return out


@dataclass
class WorldState:
    owner: np.ndarray
    population: np.ndarray
    market: np.ndarray
    capitals: dict
    countries: dict
    markets: list
    roads: dict
    culture: list
    religion: list
    religion_group: list
    raw_material: list
    links: list
    facts_active: list
    snapshot_date: str


class Timeline:
    def __init__(self, graph, snapshots, *, kind="O", world_id=None, facts=(), seed=0, faith_groups=None, omit_wc=False,
                 residency_power=1.):
        self.graph = graph
        self.kind = kind
        self.residency_power = residency_power
        self.snapshots = snapshots
        self.id = world_id or ("R" if kind == "R" else snapshots[0]["metadata"]["playthrough_id"])
        sequence=isinstance(snapshots,SnapshotSequence)
        self.dates = ([month_of(e['date']) for e in snapshots.manifest['snapshots']] if sequence else
                      [month_of(s["metadata"]["date"]) for s in snapshots])
        self.start = 0 if kind == "R" else self.dates[0]
        self.end = (1837 - 1337) * 12 if kind == "R" else self.dates[-1] + 1
        self.facts = sample_facts(facts, seed, omit_wc) if kind == "R" else []
        self.faith_groups = dict(faith_groups or {})
        if sequence:
            country_names,market_names,faiths=snapshots.summary()
            self.faith_groups.update(faiths)
        else:
            for snap in snapshots:
                self.faith_groups.update(snap.get('religion_groups',{}))
        self.names = {name: i for i, name in enumerate(graph.names)}
        self.country_names = country_names if sequence else sorted({c for s in snapshots for c in s["countries"]} |
                                    {loc["owner"] for s in snapshots for loc in s["locations"].values() if loc.get("owner")})
        self.country_index = {name: i for i, name in enumerate(self.country_names)}
        self.market_names = market_names if sequence else sorted({m for s in snapshots for m in s["markets"]})
        self.market_index = {name: i for i, name in enumerate(self.market_names)}
        self.hash = canonical_hash({"snapshots": ([snapshot_hash(e) for e in snapshots.manifest['snapshots']] if sequence else
                                                [s.get("_snapshot_sha256") or canonical_hash(s) for s in snapshots]),
                                   "facts": list(facts), "faiths": self.faith_groups,"residency_power":residency_power})
        self.cursor = -1
        self.signature = None
        self.state = None

    def at(self, month):
        cursor = max((i for i, t in enumerate(self.dates) if t <= month), default=-1)
        if cursor < 0:
            raise ValueError("no world snapshot at or before requested month")
        active = [f for f in self.facts if f["start_month"] <= month < f["end_month"]]
        signature = (cursor, tuple(f["id"] for f in active))
        if signature == self.signature:
            return self.state, False
        snap = self.snapshots[cursor]
        locs = snap["locations"]
        missing = set(self.names) - locs.keys()
        if missing:
            raise ValueError(f"world snapshot misses {len(missing)} graph locations")
        owner = np.array([self.country_index.get(locs[n].get("owner"), -1) for n in self.graph.names], dtype=int)
        pop = np.array([locs[n]["population"] for n in self.graph.names], dtype=float)
        if np.any(~np.isfinite(pop)) or np.any(pop < 0):
            raise ValueError("invalid world population")
        market = np.array([self.market_index.get(locs[n].get("market"), -1) for n in self.graph.names], dtype=int)
        capitals = {self.country_index[c]: self.names[rec["capital"]] for c, rec in snap["countries"].items()
                    if rec.get("capital") in self.names and c in self.country_index}
        markets = [{"merchants": {}, "center": -1,'present':False} for _ in self.market_names]
        for m, rec in snap["markets"].items():
            markets[self.market_index[m]] = {"center": self.names.get(rec["center"], -1),'present':True,
                "merchants": {self.country_index[c]: float(s) for c, s in rec["merchants"].items()
                              if c in self.country_index and s > 0}}
        links=[{'kind':r['kind'],'actor':self.country_index[str(r['actor'])],
                'other':self.country_index.get(str(r.get('other'))),'fact_id':r['fact_id'],'good':r.get('good')}
               for r in snap.get('links',[]) if str(r.get('actor')) in self.country_index]
        for fact in sorted(active,key=lambda f:f["start_month"]):
            if fact["kind"] not in ("ownership","ownership_region"):
                continue
            actor = owner[self.names[fact["actor_location"]]]
            if actor < 0:
                continue
            targets = [self.names[fact["location"]]] if fact["kind"] == "ownership" else [
                v for v in range(self.graph.n) if self.graph.names[v] not in fact.get("exclude_locations",()) and all(self.graph.attrs[k][v] in (val if isinstance(val,list) else [val])
                                                     for k,val in fact["where"].items()) and
                (not fact.get("previous_owner_tag") or (owner[v] >= 0 and
                 snap["countries"].get(self.country_names[owner[v]],{}).get("tag") == fact["previous_owner_tag"]))]
            owner[targets] = actor
            if fact.get("new_capital"):
                capitals[int(actor)] = self.names[fact["new_capital"]]
        # Residency refers to the current political world after all ownership
        # facts, rather than to whichever actor happened to be read first.
        if self.kind == "R":
            resident_population = {}
            for v,c in enumerate(owner):
                m = int(market[v])
                if c >= 0 and m >= 0 and pop[v] > 0:
                    table = resident_population.setdefault(m,{})
                    table[int(c)] = table.get(int(c),0.) + float(pop[v])
            for mid,original in snap["markets"].items():
                if original.get("domestic"):
                    m = self.market_index[mid]
                    rec = markets[m]
                    c = int(owner[rec["center"]]) if rec["center"] >= 0 else -1
                    residents = resident_population.get(m,{})
                    total = sum(residents.values())
                    rec["merchants"] = {c:w/total for c,w in residents.items()} if total else ({c:1.} if c >= 0 else {})
        for fact in active:
            actor = owner[self.names[fact["actor_location"]]]
            target = self.names.get(fact.get("location"), -1)
            if actor < 0:
                continue
            if fact["kind"] == "residency" and target >= 0 and market[target] >= 0:
                table = markets[market[target]]["merchants"]
                table[int(actor)] = max(table.get(int(actor),0.),self.residency_power)
            elif fact["kind"] in ("marriage", "diplomacy", "reform", "ban", "ceremony"):
                links.append({"kind": fact["kind"], "actor": int(actor),
                              "other": int(owner[target]) if target >= 0 else None,
                              "fact_id": fact["id"], "good": fact.get("good")})
        for rec in markets:
            total = sum(rec["merchants"].values())
            if total:
                rec["merchants"] = {c: s / total for c, s in rec["merchants"].items()}
        capitals = {c: v for c, v in capitals.items() if owner[v] == c}
        roads = {}
        for a, b, kind in snap["roads"]:
            if a in self.names and b in self.names:
                u, v = self.names[a], self.names[b]
                if u in self.graph.incoming[v]:
                    roads[(min(u, v), max(u, v))] = kind
        culture = [locs[n].get("culture") for n in self.graph.names]
        religion = [locs[n].get("religion") for n in self.graph.names]
        if any(pop[v]>0 and isinstance(religion[v],str) and religion[v].isdecimal() for v in range(self.graph.n)):
            raise ValueError('Unresolved runtime religion ids; refresh formal world exports before simulating')
        base_raw = self.graph.attrs.get("raw_material") or [None]*self.graph.n
        self.state = WorldState(owner, pop, market, capitals, snap["countries"], markets, roads, culture,
                                religion, [self.faith_groups.get(r) for r in religion],
                                [locs[n].get("raw_material",base_raw[v])
                                 for v,n in enumerate(self.graph.names)], links,
                                [f["id"] for f in active], snap["metadata"]["date"])
        self.signature, self.cursor = signature, cursor
        return self.state, True


def weighted_means(values, groups, population, size):
    valid = groups >= 0
    weights = np.bincount(groups[valid], weights=population[valid], minlength=size)
    sums = np.bincount(groups[valid], weights=population[valid] * values[valid], minlength=size)
    means=np.divide(sums,weights,out=np.zeros(size),where=weights>0)
    positive=valid & (population>0)
    lower,upper=np.full(size,np.inf),np.full(size,-np.inf)
    np.minimum.at(lower,groups[positive],values[positive])
    np.maximum.at(upper,groups[positive],values[positive])
    # A weighted mean is in its contributors' convex hull. In particular,
    # constant 45 must remain exactly 45, not 44.99999999999998.
    means=np.where(weights>0,np.clip(means,lower,upper),0.)
    return means, weights
