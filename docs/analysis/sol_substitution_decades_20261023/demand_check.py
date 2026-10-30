"""Indirect check that country substitution factors reach engine pop demand.

For every live market and core good, compare the engine's saved market
`demanded.Pops` with SOL's own expectation built from owned-location pops,
calibrated unit quantities and each location's local_pop_demand size:

    base(m,g)  = sum_l sum_pop size(l,pop) * q(pop,g) * (1 + local_size(l))
    subst(m,g) = same, also multiplied by the owner's sol_good_effective_<g>

The engine applies further multipliers (price, religion, food, slaves, other
pops) that SOL does not book, so absolute ratios are not expected to be 1.
Instead, within each good the residual log(actual/base) is regressed on
log(F) with a log price-ratio control. A slope near 1 means market demand
moves with the country factor; near 0 means the factor is not visible.

Usage: python demand_check.py 1500 1700 1840
"""
from __future__ import annotations

import json
import math
import mmap
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

LOCAL_SIZE = re.compile(
    rb"(?m)^\t{6}flag=sol_location_pop_demand_modifier_size\r?\n\t{6}data=\{\r?\n\t{7}type=value\r?\n(?:\t{7}identity=(\d+)\r?\n)?")
OUT = X.OUTPUT / "demand_check"


def location_rows(view, pops):
    a, b = X._top_level_bounds(view, "locations")
    db = view.find(b"\n\tlocations={", a, b)
    entries = list(X.LOCATION.finditer(view, db, b))
    rows = []
    for i, match in enumerate(entries):
        end = entries[i + 1].start() if i + 1 < len(entries) else b
        owner = X.OWNER.search(view, match.start(), end)
        market = X.LMARKET.search(view, match.start(), end)
        plist = X.LPOPS.search(view, match.start(), end)
        if owner is None or market is None or plist is None:
            continue
        local = LOCAL_SIZE.search(view, match.start(), end)
        size = X.signed(local.group(1)) if local else 0.0
        mix = defaultdict(float)
        for pid in plist.group(1).split():
            ptype, amount = pops.get(int(pid), (None, 0.0))
            if ptype in X.POPS:
                mix[ptype] += amount
        rows.append((int(owner.group(1)), int(market.group(1)), size, mix))
    return rows


def regress(points):
    """OLS of y on [x, z] after demeaning within each good; returns slope_x, slope_z, n."""
    by_good = defaultdict(list)
    for good, y, x, z, w in points:
        by_good[good].append((y, x, z, w))
    data = []
    for rows in by_good.values():
        if len(rows) < 3:
            continue
        sw = sum(r[3] for r in rows)
        my, mx, mz = (sum(r[i] * r[3] for r in rows) / sw for i in range(3))
        data += [(y - my, x - mx, z - mz, w) for y, x, z, w in rows]
    sxx = sum(w * x * x for _, x, _, w in data)
    szz = sum(w * z * z for _, _, z, w in data)
    sxz = sum(w * x * z for _, x, z, w in data)
    sxy = sum(w * x * y for y, x, _, w in data)
    szy = sum(w * z * y for y, _, z, w in data)
    det = sxx * szz - sxz * sxz
    bx = (sxy * szz - szy * sxz) / det
    bz = (szy * sxx - sxy * sxz) / det
    res = [(y - bx * x - bz * z, w) for y, x, z, w in data]
    sw = sum(w for _, w in res)
    s2 = sum(w * r * r for r, w in res) / sw
    se = math.sqrt(s2 * szz / det * sw / max(len(data) - 2, 1)) if det > 0 else float("nan")
    return bx, bz, len(data), se


def check(year):
    path = next(X.ARCHIVE.glob(f"{year}.*.eu5"))
    snapshot = json.loads((X.OUTPUT / "snapshots" / f"{year}.json").read_text(encoding="utf-8"))
    factor = {c["id"]: c["F"] for c in snapshot["countries"] if c["has"]}
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
        pops = X.population(view)
        rows = location_rows(view, pops)
        del pops
        markets = X.markets(view)
    base = defaultdict(float)
    subst = defaultdict(float)
    for owner, market, size, mix in rows:
        scale = max(1 + size, 0)
        effective = factor.get(owner)
        for good in X.CORE:
            amount = sum(mix[p] * X.UNIT[p].get(good, 0.0) for p in X.POPS) * scale
            if amount <= 0:
                continue
            f = effective[X.GI[good]] if effective and effective[X.GI[good]] is not None else 1.0
            base[(market, good)] += amount
            subst[(market, good)] += amount * f
    points, cells = [], []
    for (market, good), b in base.items():
        info = markets.get(market, {}).get("goods", {}).get(good)
        if not info or b <= 0 or info["pop"] <= 0 or info["p"] is None:
            continue
        f_avg = subst[(market, good)] / b
        if f_avg <= 0:
            continue
        y = math.log(info["pop"] / b)
        x = math.log(f_avg)
        z = math.log(info["p"] / X.DEFAULT[good])
        points.append((good, y, x, z, b))
        cells.append({"m": market, "g": good, "actual": info["pop"], "base": round(b, 6), "F": round(f_avg, 5),
                      "price_ratio": round(info["p"] / X.DEFAULT[good], 5)})
    bx, bz, n, se = regress(points)
    moved = [p for p in points if abs(p[2]) > math.log(1.05)]
    bx2, bz2, n2, se2 = regress(moved) if len(moved) > 20 else (None, None, len(moved), None)
    result = {"year": year, "slope_F": bx, "slope_F_se": se, "slope_price": bz, "n": n,
              "slope_F_moved": bx2, "slope_F_moved_se": se2, "n_moved": n2, "cells": cells}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{year}.json").write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    return year, bx, se, bz, n, bx2, n2


if __name__ == "__main__":
    for value in sys.argv[1:]:
        print(check(int(value)), flush=True)
