"""Auditable static scenario inputs for real-map calibration; no hidden historical teleports."""

from __future__ import annotations

import math

from .metrics import resolve_nodes


def apply_scenario(graph, spec, base_p, base_rho, start_year=None):
    """Return parameter overrides. Explicit route changes mutate this run's graph only.

    `seeds`: {name, month|year, value}; `coefficients`: {where|names|group, p_scale, rho};
    `routes`: {from, to, weight, directed, note}. Geography is never inferred as trade.
    """
    index = {name: v for v, name in enumerate(graph.names or [])}
    seeds = []
    for row in spec.get("seeds", []):
        if row["name"] not in index:
            raise ValueError(f"unknown seed location: {row['name']}")
        month = row.get("month", 0)
        if "year" in row:
            if start_year is None:
                raise ValueError("seed year requires start_year")
            month = round((row["year"] - start_year) * 12)
        value = float(row["value"])
        if month < 0 or int(month) != month or not math.isfinite(value) or not 0 < value <= 100:
            raise ValueError("seed requires nonnegative integer month and 0 < value <= 100")
        seeds.append((index[row["name"]], int(month), value))
    result = {"seeds": seeds} if "seeds" in spec else {}
    if spec.get("constraints"):
        checks = []
        for row in spec["constraints"]:
            before = row.get("before_month")
            if "before_year" in row:
                if start_year is None:
                    raise ValueError("constraint year requires start_year")
                before = round((row["before_year"] - start_year) * 12)
            nodes = resolve_nodes(graph, row)
            if not nodes or not isinstance(before, int) or before < 0 or row["threshold"] not in ("positive", 1, 20, 45, 70, 100):
                raise ValueError("constraint requires nonempty locations, nonnegative before month and supported threshold")
            checks.append(dict(name=row["name"], nodes=nodes,
                               before_month=before, threshold=row["threshold"]))
        result["constraints"] = checks
    if spec.get("initial"):
        initial = {}
        for row in spec["initial"]:
            value = float(row["value"])
            if not math.isfinite(value) or not 0 < value <= 100:
                raise ValueError("initial custom requires 0 < value <= 100")
            nodes = resolve_nodes(graph, row)
            if not nodes:
                raise ValueError("initial custom selector matched no locations")
            for v in nodes:
                initial[v] = value
        result["initial_values"] = sorted(initial.items())
    if spec.get("coefficients"):
        pp = [base_p] * graph.n
        rho = [base_rho] * graph.n
        for row in spec["coefficients"]:
            nodes = resolve_nodes(graph, row)
            if not nodes:
                raise ValueError(f"coefficient selector matched no nodes: {row}")
            scale = float(row.get("p_scale", 1))
            retention = float(row.get("rho", base_rho))
            if not math.isfinite(scale) or scale < 0 or not math.isfinite(retention) or not 0 <= retention <= 1:
                raise ValueError("coefficient requires finite p_scale >= 0 and 0 <= rho <= 1")
            for v in nodes:
                pp[v] *= scale
                if "rho" in row:
                    rho[v] = retention
        result.update(p_by_node=pp, rho_by_node=rho)
    if spec.get("routes"):
        inc = [dict(zip(graph.incoming[v], graph.in_weight[v] if graph.in_weight else [1] * len(graph.incoming[v])))
               for v in range(graph.n)]
        out = [list(a) for a in graph.outgoing]
        for row in spec["routes"]:
            a, b = index[row["from"]], index[row["to"]]
            weight = float(row["weight"])
            if a == b or not math.isfinite(weight) or weight < 0:
                raise ValueError("route needs distinct endpoints and finite weight >= 0")
            for u, v in ([(a, b)] if row.get("directed", False) else [(a, b), (b, a)]):
                inc[v][u] = weight
                if v not in out[u]:
                    out[u].append(v)
        graph.incoming = [tuple(a) for a in inc]
        graph.in_weight = [tuple(a.values()) for a in inc]
        graph.outgoing = [tuple(a) for a in out]
    graph.meta["scenario"] = spec
    if any(key in spec for key in ("transport", "sources", "waves", "wake", "coefficient_events", "land_corridors", "contacts")):
        from .transport import compile_inputs
        result.update(compile_inputs(graph, spec, base_p, base_rho, start_year))
    return result
