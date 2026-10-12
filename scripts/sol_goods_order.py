#!/usr/bin/env python3
"""Single source of truth for SOL substitute-group ordering of goods in the UI.

Both SOL economy surfaces show every demand good as an icon cell. Ordering those
cells by substitute group (instead of alphabetically) is what makes the grouping
legible without any extra widgets: a cell is adjacent to its substitutes.

The membership table is read from data/goods_weights.csv, which is the existing
substitute-group data file (one row per membership, a good may appear in several
groups). Every good's PRIMARY group is the first group it appears in, following
GROUPS in the order the groups first appear in that file. Overlapping goods
therefore appear once, under their primary group.

JTG-only goods have no membership in that file and sort after every grouped good,
keeping their existing relative order.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
GOODS_WEIGHTS = REPO_ROOT / "data" / "goods_weights.csv"


def _load() -> tuple[list[str], dict[str, str]]:
    groups: list[str] = []
    primary: dict[str, str] = {}
    with GOODS_WEIGHTS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            good = (row["good"] or "").strip()
            group = (row["group"] or "").strip()
            if not good or not group:
                continue
            if group not in groups:
                groups.append(group)
            primary.setdefault(good, group)
    if len(primary) != 56:
        raise ValueError(
            f"Expected 56 grouped SOL goods in {GOODS_WEIGHTS}, found {len(primary)}"
        )
    return groups, primary


GROUP_ORDER, PRIMARY_GROUP = _load()


def group_of(good: str) -> str | None:
    return PRIMARY_GROUP.get(good)


def sort_key(good: str) -> tuple[int, str]:
    """Sort goods into substitute-group order.

    Grouped goods come first (in group order, then by table order inside the
    group); ungrouped goods follow in their original relative order.
    """
    group = PRIMARY_GROUP.get(good)
    if group is None:
        return (len(GROUP_ORDER), good)
    index = GROUP_ORDER.index(group)
    return (index, f"{index:03d}")


def ordered(goods: list[str]) -> list[str]:
    """Return `goods` in substitute-group order, keeping ungrouped goods stable."""
    ungrouped = [good for good in goods if good not in PRIMARY_GROUP]
    grouped = [good for good in goods if good in PRIMARY_GROUP]
    # Stable pass first so two goods in the same group keep their original order.
    return sorted(grouped, key=lambda g: GROUP_ORDER.index(PRIMARY_GROUP[g])) + ungrouped


def main() -> None:
    goods = list(PRIMARY_GROUP)
    lines = ["# Substitute groups (order = first appearance in data/goods_weights.csv)"]
    for group in GROUP_ORDER:
        members = ordered([good for good in goods if PRIMARY_GROUP[good] == group])
        lines.append(f"\n{group} ({len(members)}): " + ", ".join(members))
    lines.append("\n# UI cell order (10 per row)")
    cells = ordered(goods)
    for start in range(0, len(cells), 10):
        lines.append("  " + " ".join(cells[start : start + 10]))
    print("\n".join(lines))


if __name__ == "__main__":
    main()


def group_rows(goods: list[str]) -> list[tuple[str | None, list[str]]]:
    """Split `goods` into (group, members) rows in GROUP_ORDER, ungrouped goods last.

    This is what lets the UI show substitute groups as labelled rows instead of one
    flat lattice of icons: the group is the unit the player reasons about, and an
    ungrouped good (the compat submods' extras) gets its own trailing row rather
    than being silently mixed in.
    """
    buckets: dict[str | None, list[str]] = {}
    for good in goods:
        buckets.setdefault(PRIMARY_GROUP.get(good), []).append(good)
    rows = [(group, buckets[group]) for group in GROUP_ORDER if group in buckets]
    if None in buckets:
        rows.append((None, buckets[None]))
    return rows
