#!/usr/bin/env python3
"""Measure within-country population heterogeneity across saves.

This needs only engine-native population data, so it also works on saves
exported without SOL runtime caches (no per-stratum income or base spending).
Those saves cannot support feasibility or improvement analysis -- the target
vector t is a SOL quantity -- but they can still answer the question section 2
rests on: do stratum shares actually differ enough between a country's own
locations for classification to have anything to work with?

Reported per country and aggregated per save:
  spread   - max minus min noble share across the country's locations
  ratio    - max over min, i.e. how many times denser the noble-heaviest
             location is than the sparsest
  distinct - how many of the four strata have a location where they are the
             single most over-represented stratum relative to the country mean

Usage:
    python tools/eu5_save_parser/heterogeneity_survey.py
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ANALYSIS_DIR = Path("data/save_analysis")
MIN_LOCATIONS = 5
SHARE_COLS = ("population_share_nobles", "population_share_clergy",
              "population_share_burghers", "population_share_lower")

DEFAULT_PICKS = ("1337_10_02_d95e1b3a", "1386_03_07", "1743_04_01")


def label_of(name: str) -> str:
    """Turn a directory name into a short date label."""
    import re
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", name)
    return f"{m.group(1)}.{m.group(2)}" if m else name


def find_saves(picks: tuple[str, ...]) -> list[tuple[str, Path]]:
    out = []
    for p in picks:
        hits = [d for d in ANALYSIS_DIR.iterdir()
                if d.is_dir() and d.name.startswith("_all_") and p in d.name]
        if hits:
            d = sorted(hits)[0]
            out.append((label_of(d.name), d))
    return out


def has_sol_data(save_dir: Path) -> bool:
    meta = save_dir / "metadata.json"
    if not meta.exists():
        return False
    import json
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get(
            "countries_with_sol_variables", 0) > 0
    except Exception:
        return False


def survey(save_dir: Path) -> list[dict]:
    path = save_dir / "locations.csv"
    if not path.exists():
        return []

    by_owner: dict[str, list[np.ndarray]] = defaultdict(list)
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            tag = (row.get("owner_tag") or "").strip()
            if not tag:
                continue
            try:
                v = np.array([float(row.get(c) or 0.0) for c in SHARE_COLS])
            except ValueError:
                continue
            if v.sum() <= 0:
                continue
            by_owner[tag].append(v)

    out = []
    for tag, vs in by_owner.items():
        if len(vs) < MIN_LOCATIONS:
            continue
        S = np.array(vs)
        mean = S.mean(axis=0)
        nob = S[:, 0]
        lo, hi = nob.min(), nob.max()
        # Which strata are somewhere the most over-represented, relative to the
        # country's own mean? That is what the classifier keys on.
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(mean > 0, S / mean, 0.0)
        distinct = len(set(int(i) for i in rel.argmax(axis=1)))
        out.append({
            "tag": tag, "n": len(vs),
            "spread": float(hi - lo),
            "ratio": float(hi / lo) if lo > 1e-9 else float("inf"),
            "distinct": distinct,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saves", nargs="*", default=list(DEFAULT_PICKS))
    args = ap.parse_args()

    saves = find_saves(tuple(args.saves))
    if not saves:
        print("no matching saves", file=sys.stderr)
        return 1

    results = {}
    for label, d in saves:
        recs = survey(d)
        if recs:
            results[label] = (recs, has_sol_data(d))
            tag = "" if has_sol_data(d) else "   (no SOL caches)"
            print(f"[survey] {label}: {len(recs)} countries with >={MIN_LOCATIONS} "
                  f"locations{tag}", file=sys.stderr)

    print()
    print("=== 国家内部人口结构异质性（仅需引擎原生数据）===")
    print(f"  {'存档':<10}{'国家数':>8}{'贵族份额跨度':>16}{'最大/最小倍数':>16}"
          f"{'4 类齐全':>12}")
    for label, (recs, _) in results.items():
        n = len(recs)
        spread = np.median([r["spread"] for r in recs])
        finite = [r["ratio"] for r in recs if np.isfinite(r["ratio"])]
        ratio = np.median(finite) if finite else float("nan")
        four = sum(1 for r in recs if r["distinct"] == 4)
        print(f"  {label:<10}{n:>8,}{spread:>16.4f}{ratio:>16.1f}"
              f"{f'{four:,}（{100*four/n:.1f}%）':>12}")

    print()
    print("=== 按国家规模分档（各档中位倍数）===")
    buckets = [(5, 9), (10, 49), (50, 199), (200, 10**9)]
    print(f"  {'地点数':<10}", end="")
    for label in results:
        print(f"{label:>12}", end="")
    print()
    for lo, hi in buckets:
        name = f"{lo}-{hi}" if hi < 10**9 else f"{lo}+"
        print(f"  {name:<10}", end="")
        for label, (recs, _) in results.items():
            sel = [r["ratio"] for r in recs
                   if lo <= r["n"] <= hi and np.isfinite(r["ratio"])]
            print(f"{(f'{np.median(sel):.1f}' if sel else '-'):>12}", end="")
        print()

    print()
    print("注：贵族份额跨度 = 国家内部最高与最低之差；倍数 = 最高 / 最低。")
    print("    4 类齐全 = 四个阶层各自都有某个地点是它相对超额表示最多的地方。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
