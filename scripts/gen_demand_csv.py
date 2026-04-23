#!/usr/bin/env python3
"""
Generate data/demand_price_table.csv from vanilla goods files + z_SOL_pop_goods.txt.

Also optionally rewrites the comment blocks above each INJECT entry in
z_SOL_pop_goods.txt so they reflect the actual computed net demand values.

Usage:
  python scripts/gen_demand_csv.py                    # generate CSV only
  python scripts/gen_demand_csv.py --update-comments  # also rewrite comments
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SIMULATOR_DIR = REPO_ROOT / "tools" / "sol_demand_simulator"
sys.path.insert(0, str(SIMULATOR_DIR))

from parser import (
    INJECT_FILE,
    VANILLA_GOODS_DIR,
    _collect_brace_block,
    _expand_demand_add,
    _expand_demand_multiply,
    _find_sub_block,
    _parse_kv_block,
    _read,
    load_demand_matrix,
)
from curve_designer import GROUP_GOODS

DATA_DIR = REPO_ROOT / "data"
OUTPUT_CSV = DATA_DIR / "demand_price_table.csv"

# Reverse map: good → group name
GOOD_TO_GROUP: Dict[str, str] = {
    good: group for group, goods in GROUP_GOODS.items() for good in goods
}

# Raw EU5 pop types — commoners are NOT pre-aggregated here
POP_TYPE_ORDER: List[str] = ["nobles", "clergy", "burghers", "laborers", "peasants", "soldiers", "tribesmen"]


# ---------------------------------------------------------------------------
# CSV generation
# ---------------------------------------------------------------------------

def compute_demand_table() -> List[Dict]:
    """Return rows ready for CSV output."""
    dm = load_demand_matrix()
    rows = []
    for good, entry in sorted(dm.items()):
        row: Dict = {
            "good":  good,
            "group": GOOD_TO_GROUP.get(good, ""),
            "price": entry.price,
        }
        for pt in POP_TYPE_ORDER:
            row[pt] = entry.demand_per_pop_type.get(pt, 0.0)
        rows.append(row)
    return rows


def write_demand_csv(rows: List[Dict], path: Path = OUTPUT_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["good", "group", "price"] + POP_TYPE_ORDER
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[gen_demand_csv] Wrote {len(rows)} rows → {path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Comment regeneration helpers
# ---------------------------------------------------------------------------

def _parse_inject_add_pop_types(good: str) -> Dict[str, float]:
    """Extract inject demand_add for *good* from z_SOL_pop_goods.txt, per pop type."""
    text = _read(INJECT_FILE)
    pattern = re.compile(r"\bINJECT\s*:\s*" + re.escape(good) + r"\s*=\s*\{")
    m = pattern.search(text)
    if not m:
        return {pt: 0.0 for pt in POP_TYPE_ORDER}
    brace_pos = text.index("{", m.start())
    inner, _ = _collect_brace_block(text, brace_pos)

    da_inner = _find_sub_block(inner, "demand_add")
    if da_inner is None:
        return {pt: 0.0 for pt in POP_TYPE_ORDER}

    per_pt = _expand_demand_add(_parse_kv_block(da_inner))
    return {pt: per_pt.get(pt, 0.0) for pt in POP_TYPE_ORDER}


def _parse_vanilla_pop_types(good: str) -> Dict[str, float]:
    """Compute vanilla net demand (add × multiply) per pop type for *good*."""
    pattern = re.compile(r"\b" + re.escape(good) + r"\s*=\s*\{")
    for fpath in sorted(VANILLA_GOODS_DIR.glob("*.txt")):
        text = _read(fpath)
        m = pattern.search(text)
        if not m:
            continue
        brace_pos = text.index("{", m.start())
        inner, _ = _collect_brace_block(text, brace_pos)

        add_inner = _find_sub_block(inner, "demand_add")
        mult_inner = _find_sub_block(inner, "demand_multiply")

        va = _expand_demand_add(_parse_kv_block(add_inner) if add_inner else {})
        vm = _expand_demand_multiply(_parse_kv_block(mult_inner) if mult_inner else {})

        per_pt = {pt: va.get(pt, 0.0) * vm.get(pt, 1.0) for pt in POP_TYPE_ORDER}
        return per_pt

    return {pt: 0.0 for pt in POP_TYPE_ORDER}


def _build_inject_comment(good: str, dm: Dict) -> str:
    """
    Build the replacement comment block for one INJECT entry.

    Format (lines with all-zero values are omitted):
      # vanilla net: nobles=X | laborers=X | peasants=X | ...
      # inject add:  laborers=+X | ...        (omitted if no inject changes)
      # net:         nobles=X | laborers=X | ...
    """
    vanilla_pts = _parse_vanilla_pop_types(good)
    inject_pts = _parse_inject_add_pop_types(good)

    entry = dm.get(good)
    net_pts: Dict[str, float] = (
        {pt: entry.demand_per_pop_type.get(pt, 0.0) for pt in POP_TYPE_ORDER}
        if entry else
        {pt: vanilla_pts.get(pt, 0.0) + inject_pts.get(pt, 0.0) for pt in POP_TYPE_ORDER}
    )

    def fmt_vals(vals: Dict[str, float], show_sign: bool = False) -> Optional[str]:
        parts = []
        for pt in POP_TYPE_ORDER:
            v = vals.get(pt, 0.0)
            if abs(v) < 1e-9:
                continue
            parts.append(f"{pt}={v:+.6g}" if show_sign else f"{pt}={v:.6g}")
        return " | ".join(parts) if parts else None

    lines: List[str] = []

    v_str = fmt_vals(vanilla_pts)
    if v_str:
        lines.append(f"# vanilla net: {v_str}")

    i_str = fmt_vals(inject_pts, show_sign=True)
    if i_str:
        lines.append(f"# inject add:  {i_str}")

    n_str = fmt_vals(net_pts)
    lines.append(f"# net:         {n_str}" if n_str else "# net:         (all zero)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rewrite z_SOL_pop_goods.txt comments
# ---------------------------------------------------------------------------

def update_pop_goods_comments(rows: List[Dict]) -> None:
    """
    Rewrite the comment block immediately above each INJECT:good = { entry
    in z_SOL_pop_goods.txt.  Non-comment / non-blank lines are untouched.
    """
    dm = load_demand_matrix()
    text = _read(INJECT_FILE)
    lines = text.splitlines(keepends=True)

    # Collect INJECT positions (line index, good name)
    inject_positions: List[Tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"INJECT\s*:\s*(\w+)\s*=", line.strip())
        if m:
            inject_positions.append((i, m.group(1)))

    if not inject_positions:
        print("[gen_demand_csv] No INJECT entries found; comments unchanged.")
        return

    # Work backwards so indices stay valid
    new_lines = list(lines)
    for inject_idx, good in reversed(inject_positions):
        # Walk backwards to find the start of the preceding comment block
        comment_start = inject_idx
        j = inject_idx - 1
        while j >= 0:
            stripped = new_lines[j].strip()
            if stripped == "":
                j -= 1
                continue
            if stripped.startswith("#") and not re.match(r"###", stripped):
                comment_start = j
                j -= 1
            else:
                break

        new_comment = _build_inject_comment(good, dm)
        new_comment_lines = [c + "\n" for c in new_comment.split("\n")]

        new_lines[comment_start:inject_idx] = new_comment_lines

    # Write back with UTF-8 BOM preserved
    result = "".join(new_lines)
    INJECT_FILE.write_bytes(b"\xef\xbb\xbf" + result.encode("utf-8"))
    print(f"[gen_demand_csv] Updated comments → {INJECT_FILE.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    update_comments = "--update-comments" in sys.argv
    rows = compute_demand_table()
    write_demand_csv(rows)
    if update_comments:
        update_pop_goods_comments(rows)


if __name__ == "__main__":
    main()
