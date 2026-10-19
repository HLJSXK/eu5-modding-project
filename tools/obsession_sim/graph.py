"""Map graph input for the obsession simulator.

A MapGraph is static topology plus static per-location attributes. It carries
no simulation state. Incoming/outgoing adjacency are kept separately so that
directed routes (sea lanes, one-way corridors) can be expressed; for an
undirected map both lists are the same tuples, in the same order, which keeps
asynchronous service order reproducible.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import csv
import json
import math
from pathlib import Path
import random


@dataclass
class MapGraph:
    incoming: list            # incoming[v] = tuple of source nodes u (u -> v)
    outgoing: list            # outgoing[u] = tuple of target nodes v (u -> v), notification order
    in_weight: list | None = None   # in_weight[v] = tuple of edge multipliers on p, same order as incoming[v]; None = all 1
    owner: list | None = None       # clock group per node (country index), -1 = no group
    group_names: list | None = None
    names: list | None = None
    coords: list | None = None      # (x, y) for visualisation; any units
    attrs: dict = field(default_factory=dict)   # extra static columns: market, population, culture ...
    meta: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.incoming)

    @property
    def n_groups(self) -> int:
        return (max(self.owner) + 1) if self.owner else 0

    def degree_stats(self) -> dict:
        d_in = [len(a) for a in self.incoming]
        d_out = [len(a) for a in self.outgoing]
        return {"nodes": self.n, "edges_in": sum(d_in), "mean_in_degree": sum(d_in) / self.n,
                "max_in_degree": max(d_in), "max_out_degree": max(d_out),
                "isolated": sum(1 for a, b in zip(d_in, d_out) if a == 0 and b == 0)}

    def validate(self) -> list:
        """Return a list of problems; empty means usable."""
        problems = []
        n = self.n
        if len(self.outgoing) != n:
            problems.append("outgoing length differs from incoming")
        for v in range(n):
            for u in self.incoming[v]:
                if not 0 <= u < n:
                    problems.append(f"node {v}: incoming index {u} out of range")
                elif u == v:
                    problems.append(f"node {v}: self loop")
        inc = {(u, v) for v in range(n) for u in self.incoming[v]}
        out = {(u, v) for u in range(n) for v in self.outgoing[u]}
        if inc != out:
            problems.append(f"incoming/outgoing disagree on {len(inc ^ out)} edges")
        if self.in_weight is not None:
            for v in range(n):
                if len(self.in_weight[v]) != len(self.incoming[v]):
                    problems.append(f"node {v}: weight count differs from incoming count")
                    break
        for name in ("owner", "names", "coords"):
            col = getattr(self, name)
            if col is not None and len(col) != n:
                problems.append(f"{name} length {len(col)} != {n}")
        for k, col in self.attrs.items():
            if len(col) != n:
                problems.append(f"attr {k} length {len(col)} != {n}")
        return problems


# ---------------------------------------------------------------- builders

def from_adjacency(adj, **kw) -> MapGraph:
    """Undirected adjacency lists; order is preserved for both directions."""
    adj = [tuple(int(u) for u in a) for a in adj]
    return MapGraph(incoming=adj, outgoing=adj, **kw)


def hex_grid(width: int = 117, height: int = 116) -> MapGraph:
    """Offset-row hexagonal grid used by every synthetic experiment (13,572 nodes)."""
    adj = []
    coords = []
    for r in range(height):
        for c in range(width):
            ds = (((0, -1), (0, 1), (-1, -1), (-1, 0), (1, -1), (1, 0)) if r % 2 == 0
                  else ((0, -1), (0, 1), (-1, 0), (-1, 1), (1, 0), (1, 1)))
            a = []
            for dr, dc in ds:
                rr, cc = r + dr, c + dc
                if 0 <= rr < height and 0 <= cc < width:
                    a.append(rr * width + cc)
            adj.append(tuple(a))
            coords.append((c + 0.5 * (r % 2), r * math.sqrt(3) / 2))
    g = from_adjacency(adj, coords=coords)
    g.meta.update({"kind": "hex_grid", "width": width, "height": height,
                   "center": (height // 2) * width + width // 2})
    return g


def voronoi_groups(graph: MapGraph, n_groups: int, seed: int = 20261019) -> list:
    """Graph-Voronoi partition (multi-source BFS over outgoing edges).

    Identical to ripple_country_clock_study.partition() for the hex grid, so the
    regression anchors stay valid.
    """
    rng = random.Random(seed)
    seeds = rng.sample(range(graph.n), n_groups)
    owner = [-1] * graph.n
    dq = deque()
    for c, s in enumerate(seeds):
        owner[s] = c
        dq.append(s)
    while dq:
        v = dq.popleft()
        for u in graph.outgoing[v]:
            if owner[u] < 0:
                owner[u] = owner[v]
                dq.append(u)
    return owner


def hops_from(graph: MapGraph, sources) -> list:
    """Hop distance along nonzero outgoing edges; -1 = unreachable."""
    enabled = None if graph.in_weight is None else {
        (u, v) for v, sources_in in enumerate(graph.incoming)
        for u, weight in zip(sources_in, graph.in_weight[v]) if weight > 0}
    dist = [-1] * graph.n
    dq = deque()
    for s in ([sources] if isinstance(sources, int) else sources):
        dist[s] = 0
        dq.append(s)
    while dq:
        v = dq.popleft()
        for u in graph.outgoing[v]:
            if enabled is not None and (v, u) not in enabled:
                continue
            if dist[u] < 0:
                dist[u] = dist[v] + 1
                dq.append(u)
    return dist


# ---------------------------------------------------------------- file formats

def load_json(path) -> MapGraph:
    """Load the graph JSON format described in README.md."""
    return from_spec(json.loads(Path(path).read_text(encoding="utf-8")))


def from_spec(spec: dict) -> MapGraph:
    """Build a MapGraph from an in-memory spec (same layout as the JSON file)."""
    nodes = spec["nodes"]
    n = len(nodes)
    index = {str(nd.get("id", i)): i for i, nd in enumerate(nodes)}

    def ix(ref):
        return index[str(ref)]

    directed = bool(spec.get("directed", False))
    if all("nbrs" in nd for nd in nodes):
        incoming = [tuple(ix(u) for u in nd["nbrs"]) for nd in nodes]
        weights = ([tuple(float(w) for w in nd["nbr_weights"]) for nd in nodes]
                   if all("nbr_weights" in nd for nd in nodes) else None)
        if directed:
            outgoing = [[] for _ in range(n)]
            for v in range(n):
                for u in incoming[v]:
                    outgoing[u].append(v)
            outgoing = [tuple(a) for a in outgoing]
        else:
            outgoing = incoming
    else:
        inc = [[] for _ in range(n)]
        wts = [[] for _ in range(n)]
        out = [[] for _ in range(n)]
        for e in spec["edges"]:
            a, b = ix(e[0]), ix(e[1])
            w = float(e[2]) if len(e) > 2 and e[2] is not None else 1.0
            inc[b].append(a); wts[b].append(w); out[a].append(b)
            if not directed:
                inc[a].append(b); wts[a].append(w); out[b].append(a)
        incoming = [tuple(a) for a in inc]
        outgoing = [tuple(a) for a in out]
        weights = None if all(w == 1.0 for a in wts for w in a) else [tuple(a) for a in wts]
    groups = spec.get("groups")
    owner = None
    if any("group" in nd for nd in nodes):
        names = groups or sorted({str(nd["group"]) for nd in nodes if nd.get("group") not in (None, "")})
        gix = {str(g): i for i, g in enumerate(names)}
        owner = [gix[str(nd["group"])] if nd.get("group") not in (None, "") else -1 for nd in nodes]
        groups = list(names)
    coords = [tuple(nd["xy"]) for nd in nodes] if all("xy" in nd for nd in nodes) else None
    names = [str(nd.get("name", nd.get("id", i))) for i, nd in enumerate(nodes)]
    reserved = {"id", "name", "nbrs", "nbr_weights", "group", "xy"}
    keys = sorted({k for nd in nodes for k in nd} - reserved)
    attrs = {k: [nd.get(k) for nd in nodes] for k in keys}
    return MapGraph(incoming=incoming, outgoing=outgoing, in_weight=weights, owner=owner,
                    group_names=groups, names=names, coords=coords, attrs=attrs,
                    meta=dict(spec.get("meta", {}), directed=directed))


def save_json(graph: MapGraph, path) -> None:
    """Write the per-node adjacency form (keeps exact neighbour order)."""
    nodes = []
    for v in range(graph.n):
        nd = {"id": v, "nbrs": list(graph.incoming[v])}
        if graph.in_weight is not None:
            nd["nbr_weights"] = list(graph.in_weight[v])
        if graph.names:
            nd["name"] = graph.names[v]
        if graph.owner is not None and graph.owner[v] >= 0:
            nd["group"] = graph.group_names[graph.owner[v]] if graph.group_names else str(graph.owner[v])
        if graph.coords:
            nd["xy"] = [round(graph.coords[v][0], 4), round(graph.coords[v][1], 4)]
        for k, col in graph.attrs.items():
            nd[k] = col[v]
        nodes.append(nd)
    directed = graph.incoming is not graph.outgoing and any(
        set(graph.incoming[v]) != set(graph.outgoing[v]) for v in range(graph.n))
    spec = {"format": "obsession_sim.graph/1", "directed": directed, "meta": graph.meta, "nodes": nodes}
    if graph.owner is not None:
        spec["groups"] = list(graph.group_names) if graph.group_names else [str(i) for i in range(graph.n_groups)]
    Path(path).write_text(json.dumps(spec, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def load_csv(nodes_csv, edges_csv, directed: bool = False) -> MapGraph:
    """nodes.csv: id[,name,group,x,y,...]; edges.csv: a,b[,weight]."""
    with open(nodes_csv, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    nodes = []
    for r in rows:
        nd = {k: v for k, v in r.items() if v != ""}
        if "x" in nd and "y" in nd:
            nd["xy"] = [float(nd.pop("x")), float(nd.pop("y"))]
        nodes.append(nd)
    with open(edges_csv, encoding="utf-8-sig", newline="") as fh:
        er = csv.reader(fh)
        header = next(er)
        edges = [[row[0], row[1], (float(row[2]) if len(row) > 2 and row[2] != "" else None)] for row in er]
    if header and header[0] not in ("a", "from", "source"):
        edges.insert(0, [header[0], header[1], float(header[2]) if len(header) > 2 and header[2] else None])
    return from_spec({"directed": directed, "nodes": nodes, "edges": edges})
