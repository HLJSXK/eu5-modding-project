"""Calibration metrics: arrival timing, front speed and historical milestones.

All inputs come from a finished Simulation; these are diagnostics only.
Month 0 is the simulation start; pass start_year to report calendar years.
"""

from __future__ import annotations

import math

from .graph import hops_from


def quantile(values, frac):
    vals = sorted(values)
    if not vals:
        return None
    k = min(len(vals) - 1, max(0, int(round(frac * (len(vals) - 1)))))
    return vals[k]


def group_arrival(sim, nodes, fraction=0.5, threshold=1, weights=None):
    """Month when at least `fraction` reached the threshold; never excludes unreached nodes."""
    if not nodes:
        raise ValueError("milestone selector matched no locations")
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    arrivals = arrival_column(sim, threshold)
    if weights is not None:
        values = [weights[v] for v in nodes]
        if any(isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0 for w in values):
            raise ValueError("population weights must be finite and nonnegative")
        total = sum(values)
        if total <= 0:
            raise ValueError("population-weighted milestone needs positive total population")
        reached_weight = 0
        for month, weight in sorted((arrivals[v], weights[v]) for v in nodes if arrivals[v] >= 0):
            reached_weight += weight
            if reached_weight >= fraction * total:
                return month
        return None
    arr = [arrivals[v] for v in nodes]
    reached = sorted(a for a in arr if a >= 0)
    need = max(1, math.ceil(fraction * len(arr)))
    return reached[need - 1] if len(reached) >= need else None


def arrival_column(sim, threshold):
    if threshold == "positive":
        return sim.first_positive
    if threshold not in sim.threshold_arrival:
        raise ValueError("threshold must be 'positive' or one of 1, 20, 45, 70, 100")
    return sim.threshold_arrival[threshold]


def resolve_nodes(graph, spec):
    """Select nodes by indices, names, clock group, or attributes (AND; lists mean OR)."""
    if "nodes" in spec:
        nodes = list(spec["nodes"])
        if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < graph.n for v in nodes) or len(set(nodes)) != len(nodes):
            raise ValueError("selector nodes must be unique valid graph indices")
        return nodes
    if "names" in spec:
        idx = {nm: i for i, nm in enumerate(graph.names or [])}
        missing = [nm for nm in spec["names"] if nm not in idx]
        if missing:
            raise KeyError(f"unknown node names: {missing[:5]}")
        if len(set(spec["names"])) != len(spec["names"]):
            raise ValueError("selector names must be unique")
        return [idx[nm] for nm in spec["names"]]
    if "group" in spec:
        g = spec["group"]
        gi = graph.group_names.index(g) if isinstance(g, str) and graph.group_names else int(g)
        return [v for v in range(graph.n) if graph.owner[v] == gi]
    if "where" in spec:
        where = spec["where"]
        if not where:
            raise ValueError("where must contain at least one attribute")
        for key in where:
            if key not in graph.attrs:
                raise KeyError(f"unknown graph attribute: {key}")
        return [v for v in range(graph.n) if all(
            graph.attrs[key][v] in (value if isinstance(value, list) else [value])
            for key, value in where.items())]
    raise KeyError("milestone needs nodes, names, group or where")


def milestones(sim, specs, start_year=None):
    """Compare simulated arrival with targets.

    Each spec: {"name", one of nodes/names/group, "target_month" or "target_year",
                "fraction" (default 0.5), "tolerance_months" (default 120)}
    """
    out = []
    for sp in specs:
        nodes = resolve_nodes(sim.g, sp)
        frac = sp.get("fraction", 0.5)
        threshold = sp.get("threshold", 1)
        aggregation = sp.get("aggregation", "fraction_of_locations")
        if aggregation not in ("fraction_of_locations", "population"):
            raise ValueError("unknown milestone aggregation")
        weights = None
        if aggregation == "population":
            weights = sim.g.attrs.get("population")
            if weights is None:
                raise ValueError("population aggregation requires actual population data")
        got = group_arrival(sim, nodes, frac, threshold, weights)
        if "target_year" in sp:
            if start_year is None:
                raise ValueError("target_year needs start_year")
            target = round((sp["target_year"] - start_year) * 12)
        else:
            target = sp["target_month"]
        tol = sp.get("tolerance_months", 120)
        err = None if got is None else got - target
        row = {"name": sp["name"], "locations": len(nodes), "fraction": frac,
               "threshold": threshold, "tolerance_months": tol,
               "reached": sum(arrival_column(sim, threshold)[v] >= 0 for v in nodes),
               "aggregation": aggregation,
               "target_month": target, "simulated_month": got, "error_months": err,
               "within_tolerance": err is not None and abs(err) <= tol}
        if start_year is not None:
            row["target_year"] = round(start_year + target / 12, 1)
            row["simulated_year"] = None if got is None else round(start_year + got / 12, 1)
        out.append(row)
    return out


def front_profile(sim, sources, max_hops=None):
    """Median arrival month and median peak x per hop distance from sources."""
    dist = hops_from(sim.g, sources)
    by = {}
    for v, dd in enumerate(dist):
        if dd < 0 or (max_hops is not None and dd > max_hops):
            continue
        by.setdefault(dd, []).append(v)
    rows = []
    for dd in sorted(by):
        vs = by[dd]
        arr = [sim.arrival[v] for v in vs if sim.arrival[v] >= 0]
        rows.append({"hops": dd, "locations": len(vs), "reached": len(arr),
                     "median_arrival_month": quantile(arr, 0.5),
                     "median_peak_x": round(quantile([sim.peak_x[v] for v in vs], 0.5), 3)})
    return rows


def front_speed(profile, lo=5, hi=None):
    """Least-squares hops per year from median arrival vs hop distance."""
    pts = [(r["hops"], r["median_arrival_month"]) for r in profile
           if r["median_arrival_month"] is not None and r["hops"] >= lo and (hi is None or r["hops"] <= hi)]
    if len(pts) < 2:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    if sxy <= 0:
        return None
    months_per_hop = sxy / sxx
    return round(12 / months_per_hop, 3)
