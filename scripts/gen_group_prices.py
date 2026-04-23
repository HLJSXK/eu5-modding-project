#!/usr/bin/env python3
"""
Compute P_g_s (base price sums per strata per group) and write z_SOL_group_prices.txt.

P_g_s = Σ_{i ∈ group g} (demand_i_strata × price_i)

Usage:
  python scripts/gen_group_prices.py             # compute and write z_SOL_group_prices.txt
  python scripts/gen_group_prices.py --dry-run   # print what would change, don't write
"""

import re
import sys
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
SIMULATOR_DIR = REPO_ROOT / "tools" / "sol_demand_simulator"
sys.path.insert(0, str(SIMULATOR_DIR))

from parser import (
    GROUP_PRICES_FILE,
    _GROUPS,
    _STRATA_KEYS,
    _auto_group_prices,
    _read,
    export_group_prices_jomini,
)

UTF8_BOM = b"\xef\xbb\xbf"


def compute_group_prices() -> Dict[str, Dict[str, float]]:
    """Return {strata: {group: P_g_s}} computed from current demand matrix."""
    return _auto_group_prices()


def parse_current_prices(path: Path = GROUP_PRICES_FILE) -> Dict[str, Dict[str, float]]:
    """Parse existing z_SOL_group_prices.txt into the same format."""
    if not path.exists():
        return {}
    text = _read(path)
    result: Dict[str, Dict[str, float]] = {s: {} for s in _STRATA_KEYS}
    for m in re.finditer(r"local_(\w+?)_(\w+?)_P\s*=\s*\{[^}]*value\s*=\s*([\d.]+)", text):
        strata, group, val = m.group(1), m.group(2), float(m.group(3))
        if strata in result and group in _GROUPS:
            result[strata][group] = val
    return result


def write_group_prices(prices: Dict[str, Dict[str, float]], path: Path = GROUP_PRICES_FILE) -> None:
    """Write P_g_s values to z_SOL_group_prices.txt with UTF-8 BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = export_group_prices_jomini(prices)
    path.write_bytes(UTF8_BOM + text.encode("utf-8") + b"\n")
    print(f"[gen_group_prices] Written → {path.relative_to(REPO_ROOT)}")


def _diff_prices(
    expected: Dict[str, Dict[str, float]],
    actual: Dict[str, Dict[str, float]],
    tol: float = 1e-4,
) -> list[str]:
    diffs = []
    for s in _STRATA_KEYS:
        for g in _GROUPS:
            exp = expected.get(s, {}).get(g, 0.0)
            act = actual.get(s, {}).get(g, 0.0)
            if abs(exp - act) > tol:
                diffs.append(f"  {s}_{g}_P: {act:.6f} → {exp:.6f} (Δ={exp - act:+.6f})")
    return diffs


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    prices = compute_group_prices()
    current = parse_current_prices()

    diffs = _diff_prices(prices, current)
    if diffs:
        print(f"[gen_group_prices] {len(diffs)} value(s) would change:")
        for d in diffs:
            print(d)
    else:
        print("[gen_group_prices] No changes — z_SOL_group_prices.txt already up to date.")

    if not dry_run:
        write_group_prices(prices)


if __name__ == "__main__":
    main()
