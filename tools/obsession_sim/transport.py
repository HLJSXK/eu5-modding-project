"""Sparse transport inputs; static assumptions remain separate from save evidence.

The graph contains only open links. Opening/closing one notifies its target,
including when its source has long been stationary. Runtime work is O(changes)
plus the actual served in/out degree, with no market clique or edge-pressure cache.
"""
from __future__ import annotations

import math
from collections import deque

from .metrics import resolve_nodes


def _number(value, label, low=0, high=float("inf")):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be finite in [{low}, {high}]")
    return float(value)


def _month(row, key, start_year, default=None):
    if key + "_month" in row:
        value = row[key + "_month"]
    elif key + "_year" in row:
        if start_year is None:
            raise ValueError("calendar inputs need start_year")
        value = round((_number(row[key + "_year"], key + "_year") - start_year) * 12)
    elif default is not None:
        value = default
    else:
        raise ValueError(f"input needs {key}_year or {key}_month")
    if isinstance(value, bool) or value < 0 or int(value) != value:
        raise ValueError(f"{key} month must be a nonnegative integer")
    return int(value)


def market_routes(graph, config):
    """Save-backed bounded-degree hub ring, never an N² market clique.

    At most max_hubs populous locations per market participate in nonlocal
    transport; all other locations retain their geographic links. No pixel area
    or harbor score is substituted for population. Flows name actual markets.
    """
    markets = graph.attrs.get("market")
    pop = graph.attrs.get("population")
    if markets is None or pop is None:
        raise ValueError("market transport requires market and population from a save CSV")
    count = config.get("max_hubs", 6)
    if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 32:
        raise ValueError("max_hubs must be an integer between 2 and 32")
    grouped = {}
    for v, (market, population) in enumerate(zip(markets, pop)):
        if market is None or population is None:
            raise ValueError("market transport requires complete market/population coverage")
        population = _number(float(population), "population")
        if population > 0:
            grouped.setdefault(str(market), []).append((population, v))
    hubs = {name: [v for _, v in sorted(nodes, key=lambda a: (-a[0], a[1]))[:count]]
            for name, nodes in grouped.items()}
    weight = _number(config.get("weight", .25), "market weight")
    routes = []
    for name, nodes in sorted(hubs.items()):
        # Each hub has at most two same-market transport neighbors. Population
        # shares normalise weights against market size, including non-hubs.
        total = sum(p for p, _ in grouped[name])
        if len(nodes) < 2:
            continue
        pairs = set()
        for i, a in enumerate(nodes):
            b = nodes[(i + 1) % len(nodes)]
            pairs.add(tuple(sorted((a, b))))
        for a, b in sorted(pairs):
            share = math.sqrt(float(pop[a]) * float(pop[b])) / total
            routes.append({"from": graph.names[a], "to": graph.names[b],
                           "weight": weight * share, "evidence": f"save market {name}: population-weighted hub ring",
                           "start_month": config.get("start_month", 0)})
    for flow in config.get("flows", []):
        a, b = str(flow["from_market"]), str(flow["to_market"])
        if a not in hubs or b not in hubs:
            raise ValueError(f"flow refers to empty or unknown market {a} -> {b}")
        volume = _number(flow["volume"], "trade volume")
        scale = _number(config.get("volume_scale", 1), "volume_scale", 1e-12)
        routes.append({"from": graph.names[hubs[a][0]], "to": graph.names[hubs[b][0]],
                       "weight": weight * volume / (scale + volume), "directed": True,
                       "evidence": flow["evidence"],
                       **{k: v for k, v in flow.items() if k.startswith(("start_", "end_"))}})
    return routes


def compile_inputs(graph, spec, base_p, base_rho, start_year):
    index = {name: v for v, name in enumerate(graph.names or [])}
    events, windows = [], None
    # Break aliased undirected adjacency before inserting one-way links.
    graph.incoming = list(graph.incoming)
    graph.outgoing = list(graph.outgoing)
    graph.in_weight = (list(graph.in_weight) if graph.in_weight is not None else
                       [tuple(1.0 for _ in row) for row in graph.incoming])
    # Road/caravan corridors multiply existing geographic links along an actual
    # shortest path. They never turn an inland city pair into a teleport edge.
    corridor_edges = set()
    for corridor in spec.get("land_corridors", []):
        if not corridor.get("evidence"):
            raise ValueError("land corridor requires evidence")
        a, b = index[corridor["from"]], index[corridor["to"]]
        previous, queue = {a: None}, deque([a])
        while queue and b not in previous:
            u = queue.popleft()
            for v in graph.outgoing[u]:
                if v not in previous:
                    previous[v] = u
                    queue.append(v)
        if b not in previous:
            raise ValueError(f"land corridor is disconnected: {corridor['from']} -> {corridor['to']}")
        scale = _number(corridor["weight"], "corridor weight")
        v = b
        while previous[v] is not None:
            u = previous[v]
            for src, dst in ((u, v), (v, u)):
                if (src, dst) not in corridor_edges:
                    weights = list(graph.in_weight[dst])
                    weights[graph.incoming[dst].index(src)] *= scale
                    graph.in_weight[dst] = tuple(weights)
                    corridor_edges.add((src, dst))
            v = u
    # Apply strait policy before capturing geographic weights for temporary
    # additive transport, so closing a market link restores the sea weight.
    transport = spec.get("transport", {})
    if "strait_weight" in transport:
        weight = _number(transport["strait_weight"], "strait weight")
        for edge in graph.meta.get("special_edges", []):
            a, b = edge["a"], edge["b"]
            for u, v in ((a, b), (b, a)):
                weights = list(graph.in_weight[v])
                weights[graph.incoming[v].index(u)] = weight
                graph.in_weight[v] = tuple(weights)
    if "waves" in spec:
        windows = []
        for wave in spec["waves"]:
            a, b = _month(wave, "start", start_year), _month(wave, "end", start_year)
            if not 0 < b - a <= 1200:
                raise ValueError("each spread wave must be positive and at most 100 years")
            windows.append((a, b))
        windows.sort()
        if any(a < d for (_, d), (a, _) in zip(windows, windows[1:])):
            raise ValueError("spread waves of a good must not overlap")

    def in_window(month):
        return windows is None or any(a <= month < b for a, b in windows)

    def add(row):
        if not row.get("closing") and (row["kind"] != "edge" or row["weight"] > 0):
            if not in_window(row["month"]):
                # source end and coefficient changes may also occur at cutoff.
                if not (row["kind"] == "source" and row["amount"] == 0):
                    raise ValueError("new input/wake outside spread windows")
        events.append(row)

    routes = list(transport.get("routes", []))
    if "markets" in transport:
        routes += market_routes(graph, transport["markets"])
    seen = {}
    for route in routes:
        if not route.get("evidence"):
            raise ValueError("transport route requires auditable evidence")
        a, b = index[route["from"]], index[route["to"]]
        weight = _number(route["weight"], "route weight")
        start = _month(route, "start", start_year, 0)
        end = _month(route, "end", start_year) if any(k in route for k in ("end_year", "end_month")) else None
        if a == b or (end is not None and end <= start):
            raise ValueError("transport needs distinct nodes and end > start")
        for u, v in ([(a, b)] if route.get("directed", False) else [(a, b), (b, a)]):
            intervals = seen.setdefault((u, v), [])
            if any(start < z and x < (end if end is not None else float("inf")) for x, z in intervals):
                raise ValueError("transport must not duplicate an overlapping route")
            intervals.append((start, end if end is not None else float("inf")))
            base_weight = graph.in_weight[v][graph.incoming[v].index(u)] if u in graph.incoming[v] else 0
            add({"month": start, "kind": "edge", "from": u, "to": v, "weight": base_weight + weight,
                 "evidence": route["evidence"]})
            if end is not None:
                add({"month": end, "kind": "edge", "from": u, "to": v, "weight": base_weight,
                     "evidence": route["evidence"], "closing": True})
    for source in spec.get("sources", []):
        if not source.get("evidence"):
            raise ValueError("finite origin input requires evidence")
        node = index[source["name"]]
        requires = source.get("requires", {})
        if requires and node not in resolve_nodes(graph, {"where": requires}):
            raise ValueError("origin input does not satisfy required graph attributes")
        a, b = _month(source, "start", start_year), _month(source, "end", start_year)
        amount = _number(source["amount"], "origin input", 1e-12, .99999)
        if b <= a or b - a > 1200:
            raise ValueError("origin input must have a finite window <= 100 years")
        add({"month": a, "kind": "source", "node": node, "amount": amount,
             "evidence": source["evidence"]})
        add({"month": b, "kind": "source", "node": node, "amount": 0,
             "evidence": source["evidence"]})
    for row in spec.get("wake", []):
        add({"month": _month(row, "start", start_year), "kind": "renew" if row.get("renew_clock") else "wake", "nodes": resolve_nodes(graph, row)})
    for row in spec.get("contacts", []):
        value = _number(row["value"], "contact value", 1e-12, .99999)
        if not row.get("evidence"):
            raise ValueError("conditional contact requires evidence")
        add({"month": _month(row, "start", start_year), "kind": "contact", "from": index[row["from"]],
             "to": index[row["to"]], "minimum": _number(row.get("source_minimum", 1), "source minimum", 1, 100),
             "value": value, "evidence": row["evidence"]})
    for row in spec.get("coefficient_events", []):
        change = {"month": _month(row, "start", start_year), "kind": "coefficient",
                  "nodes": resolve_nodes(graph, row)}
        if "p_scale" in row:
            change["p"] = base_p * _number(row["p_scale"], "p_scale")
        if "rho" in row:
            change["rho"] = _number(row["rho"], "rho", 0, 1)
        add(change)
    graph.meta["transport"] = {"routes": len(routes), "directed_edges": len(seen),
                               "events": len(events), "corridor_directed_edges": len(corridor_edges),
                               "source": transport.get("source", "explicit scenario"),
                               "strait_weight": transport.get("strait_weight", "unchanged")}
    return {"input_events": events, "spread_windows": windows}
