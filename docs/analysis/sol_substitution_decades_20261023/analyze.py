"""Summarise the extracted substitution snapshots into summary.json.

Reads data/save_analysis/substitution_decades/<series>/snapshots/*.json written
by extract.py and demand_check/*.json written by demand_check.py.
Run after both; then run build_report.py.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import extract as X  # noqa: E402
from sol_substitution import price_weight  # noqa: E402

YEARS = list(range(1340, 1841, 10))
TOL = 2e-5


def load(year):
    return json.loads((X.OUTPUT / "snapshots" / f"{year}.json").read_text(encoding="utf-8"))


def clean_external(e):
    # Vanilla/age modifiers are multiples of 0.05 or 0.01; a polluted read is 2-M.
    return e is None or abs(e * 20 - round(e * 20)) < 1e-6 or abs(e * 100 - round(e * 100)) < 1e-6


def orphan_goods(c):
    return [k for k in range(56) if c["M"][k] is not None and c["E"][k] is not None
            and abs((c["S"][k] or 0) - c["E"][k] * (c["M"][k] - 1)) > TOL]


def wquant(pairs, qs):
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    out, acc, i = [], 0.0, 0
    for q in qs:
        while i < len(pairs) and acc + pairs[i][1] < q * total:
            acc += pairs[i][1]
            i += 1
        out.append(pairs[min(i, len(pairs) - 1)][0])
    return out


def chinese_goods():
    names = {}
    base = X.BASE_ROOT / "reference_game_files/game/main_menu/localization/simp_chinese/goods_l_simp_chinese.yml"
    for line in base.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r'^\s*([a-z_]+):\d*\s*"([^"]*)"', line)
        if m and m.group(1) in X.GI:
            names[m.group(1)] = m.group(2)
    return names


def main():
    G = list(X.CORE)
    zh = chinese_goods()
    decades, prev = [], None
    oracle_bins = defaultdict(list)
    tier_total = tier_ok = 0
    zero_removed = zero_kept = 0
    orphan_cases, polluted_cases, revived_cases = [], [], []
    examples = {}
    for year in YEARS:
        d = load(year)
        cs = d["countries"]
        alive = [c for c in cs if c["nloc"] > 0]
        has = [c for c in alive if c["has"]]
        pop = sum(c["pop"] for c in alive)
        by_id = {c["id"]: c for c in cs}
        row = {"year": year, "alive": len(alive), "pop": round(pop, 1)}
        # Refresh freshness
        age = Counter()
        for c in alive:
            if not c["has"]:
                age["none"] += 1
            elif year - c["year"] <= 1:
                age["fresh"] += 1
            else:
                age["stale"] += 1
        row["fresh"], row["stale"], row["noinit"] = age["fresh"], age["stale"], age["none"]
        row["stale_pop_pct"] = round(100 * sum(c["pop"] for c in has if year - c["year"] > 1) / pop, 4)
        for c in has:
            if year - c["year"] > 1:
                revived_cases.append({"year": year, "tag": c["tag"], "nloc": c["nloc"], "since": int(c["year"]),
                                      "sizes": sum(s is not None for s in c["S"])})
        if prev:
            inc = sorted(c["refresh"] - prev[c["id"]]["refresh"] for c in has
                         if c["id"] in prev and prev[c["id"]]["has"] and prev[c["id"]]["nloc"] > 0)
            row["refresh_inc_p50"] = inc[len(inc) // 2]
            row["refresh_inc_p05"] = inc[int(.05 * len(inc))]
        # Direction, magnitude, oracle
        tab = Counter()
        mq, wb, wm, wp = [], defaultdict(float), defaultdict(float), defaultdict(float)
        tb = tm = 0.0
        ok_w = all_w = 0.0
        for c in has:
            if "base" not in c:
                continue
            polluted = not all(clean_external(e) for e in c["E"])
            for k in range(56):
                b = c["base"][k]
                if b <= 0:
                    continue
                M, w = c["M"][k], c["wavg"][k]
                cls = "exp" if w < .999 else ("cheap" if w > 1.001 else "neu")
                dirn = "down" if M < .9999 else ("up" if M > 1.0001 else "flat")
                tab[(cls, dirn)] += b
                mq.append((M, b))
                tb += b
                tm += b * M
                wb[k] += b
                wm[k] += b * M
                if c["pjan"][k] is not None:
                    wp[k] += b * c["pjan"][k]
                if c["year"] == year and not polluted and k not in orphan_goods(c):
                    err = abs(c["Mo"][k] - M)
                    all_w += b
                    ok_w += b * (err < .01)
                    key = 0 if b < 1e-3 else 1 if b < 1e-2 else 2 if b < 1e-1 else 3 if b < 1 else 4
                    oracle_bins[key].append(err)
        for cls in ("exp", "cheap", "neu"):
            t = sum(v for (a, _), v in tab.items() if a == cls)
            row[cls] = {dd: round(tab[(cls, dd)] / t, 4) for dd in ("down", "flat", "up")}
        gx = [math.log(wp[k] / wb[k]) for k in wb if wp[k] > 0]
        gy = [math.log(wm[k] / wb[k]) for k in wb if wp[k] > 0]
        mx, my = sum(gx) / len(gx), sum(gy) / len(gy)
        row["corr"] = round(sum((a - mx) * (b - my) for a, b in zip(gx, gy)) /
                            math.sqrt(sum((a - mx) ** 2 for a in gx) * sum((b - my) ** 2 for b in gy)), 4)
        row["goods_points"] = [{"g": G[k], "p": round(wp[k] / wb[k], 4), "m": round(wm[k] / wb[k], 4)}
                               for k in wb if wp[k] > 0]
        q = wquant(mq, (.05, .25, .5, .75, .95))
        row["mq"] = [round(x, 4) for x in q]
        row["big_share"] = round(sum(b for m, b in mq if abs(m - 1) > .1) / tb, 4)
        row["sum_ratio"] = round(tm / tb, 4)
        row["oracle_ok"] = round(ok_w / all_w, 4) if all_w else None
        # Price tier cache
        D = d["default_price"]
        ok = tot = 0
        best = None
        for off in range(1, 14):
            o = t = 0
            for m in d["markets"].values():
                for g, r in m["goods"].items():
                    if r["w"] is None or len(r["h"]) < 13:
                        continue
                    t += 1
                    o += price_weight(r["h"][-off] / D[g]) == r["w"]
            if t and (best is None or o / t > best[1]):
                best = (off, o / t, o, t)
        row["tier_match"] = round(best[1], 5)
        row["tier_offset"] = best[0]
        tier_ok += best[2]
        tier_total += best[3]
        row["stale_market_keys"] = d["stale_weight_keys"]
        # Pollution, orphans, dead caches
        pol = [c for c in has if not all(clean_external(e) for e in c["E"])]
        row["polluted"] = len(pol)
        row["polluted_pop_pct"] = round(100 * sum(c["pop"] for c in pol) / pop, 4)
        for c in pol:
            cells = [k for k in range(56) if not clean_external(c["E"][k])]
            match = sum(abs(c["E"][k] - (2 - c["M"][k])) < 2e-4 for k in cells)
            polluted_cases.append({"year": year, "tag": c["tag"], "nloc": c["nloc"], "refresh": int(c["refresh"]),
                                   "cells": len(cells), "two_minus_m": match})
        orph = [(c, orphan_goods(c)) for c in has]
        orph = [(c, ks) for c, ks in orph if ks]
        row["orphans"] = len(orph)
        row["orphan_pop_pct"] = round(100 * sum(c["pop"] for c, _ in orph) / pop, 4)
        for c, ks in orph:
            donors = []
            for o in cs:
                if o["id"] == c["id"] or o["nloc"] > 0:
                    continue
                n = sum(1 for k in ks if o["S"][k] is not None and abs(o["S"][k] - c["S"][k]) < 1e-9)
                if n == len(ks):
                    donors.append(o["tag"])
            orphan_cases.append({"year": year, "tag": c["tag"], "nloc": c["nloc"],
                                 "pop_pct": round(100 * c["pop"] / pop, 3),
                                 "goods": [{"g": G[k], "zh": zh.get(G[k], G[k]), "S": c["S"][k], "M": c["M"][k]} for k in ks],
                                 "donor": donors[:1]})
        dead = [c for c in cs if c["nloc"] == 0 and c["has"]]
        row["dead_caches"] = len(dead)
        row["dead_sizes"] = sum(1 for c in dead for s in c["S"] if s is not None)
        row["dead_mb"] = round(sum(c["bytes"] for c in dead) / 1e6, 2)
        row["alive_mb"] = round(sum(c["bytes"] for c in has) / 1e6, 2)
        row["save_mb"] = round(Path(d["source"]).stat().st_size / 1e6, 1) if Path(d["source"]).exists() else None
        # Zero-size removal
        row["zero_removed"] = row["zero_kept"] = 0
        if prev:
            for c in has:
                p = prev.get(c["id"])
                if not p or not p["has"] or p["nloc"] == 0:
                    continue
                for k in range(56):
                    if p["S"][k] not in (None, 0) and c["M"][k] == 1.0 and k not in orphan_goods(c):
                        if c["S"][k] is None:
                            zero_removed += 1
                            row["zero_removed"] += 1
                        else:
                            zero_kept += 1
                            row["zero_kept"] += 1
        if year in (1340, 1590, 1840):
            ex = {}
            for t in ("FRA", "HUN", "MAM", "CHI", "CAS", "ENG"):
                c = next((c for c in has if c["tag"] == t and "base" in c), None)
                if not c:
                    continue
                ks = sorted((k for k in range(56) if c["base"][k] > 0), key=lambda k: c["M"][k])
                pick = lambda k: {"g": G[k], "zh": zh.get(G[k], G[k]), "M": c["M"][k], "p": c["pjan"][k], "w": c["wavg"][k]}
                ex[t] = {"nloc": c["nloc"], "low": [pick(k) for k in ks[:3]], "high": [pick(k) for k in ks[-3:][::-1]]}
            examples[year] = ex
        decades.append(row)
        prev = by_id
    # Oracle bins
    labels = ["< 0.001", "0.001–0.01", "0.01–0.1", "0.1–1", "≥ 1"]
    obins = []
    for key in range(5):
        a = sorted(oracle_bins[key])
        n = len(a)
        obins.append({"label": labels[key], "n": n, "p50": a[n // 2], "p90": a[int(.9 * n)],
                      "over_001": round(sum(x > .01 for x in a) / n, 4)})
    # Engine pickup (demand_check)
    edges = [(-9, -.25), (-.25, -.1), (-.1, -.03), (-.03, .03), (.03, .1), (.1, .25), (.25, 9)]
    pickup, bins = [], defaultdict(lambda: [0, 0.0, 0.0])
    for path in sorted((X.OUTPUT / "demand_check").glob("*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        pickup.append({"year": r["year"], "slope": round(r["slope_F"], 3), "se": round(r["slope_F_se"], 3),
                       "price_slope": round(r["slope_price"], 3), "n": r["n"]})
        by = defaultdict(list)
        for c in r["cells"]:
            if c["base"] <= 0:
                continue
            y = math.log(c["actual"] / c["base"]) - r["slope_price"] * math.log(c["price_ratio"])
            by[c["g"]].append((y, math.log(c["F"])))
        for rows in by.values():
            ref = sorted(y for y, x in rows if abs(x) < .03)
            if len(ref) < 3:
                continue
            med = ref[len(ref) // 2]
            for y, x in rows:
                for i, (a, b) in enumerate(edges):
                    if a <= x < b:
                        bins[i][0] += 1
                        bins[i][1] += y - med
                        bins[i][2] += x
    pickup_bins = [{"lo": edges[i][0], "hi": edges[i][1], "n": n, "x": round(sx / n, 4), "y": round(sy / n, 4)}
                   for i, (n, sy, sx) in sorted(bins.items())]
    summary = {
        "series": X.SERIES, "goods_zh": zh, "decades": decades, "oracle_bins": obins,
        "tier_ok": tier_ok, "tier_total": tier_total, "zero_removed": zero_removed, "zero_kept": zero_kept,
        "orphan_cases": orphan_cases, "polluted_cases": polluted_cases, "revived_cases": revived_cases,
        "pickup": pickup, "pickup_bins": pickup_bins, "examples": examples,
    }
    (X.OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("decades", len(decades), "tier", tier_ok, tier_total, "zero", zero_removed, zero_kept,
          "orphans", len(orphan_cases), "polluted", len(polluted_cases), "revived", len(revived_cases))


if __name__ == "__main__":
    main()
