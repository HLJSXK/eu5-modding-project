#!/usr/bin/env python3
"""
Convert data/alpha_table.csv to z_SOL_group_budget_shares.txt.

Usage:
  python scripts/gen_budget_shares.py          # validate + write
  python scripts/gen_budget_shares.py --check  # validate only, exit non-zero if invalid
"""

import csv
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
SIMULATOR_DIR = REPO_ROOT / "tools" / "sol_demand_simulator"
sys.path.insert(0, str(SIMULATOR_DIR))

from parser import (
    BUDGET_SHARES_FILE,
    _GROUPS,
    _STRATA_KEYS,
    export_budget_shares_jomini,
)

DATA_DIR   = REPO_ROOT / "data"
ALPHA_CSV  = DATA_DIR / "alpha_table.csv"
UTF8_BOM   = b"\xef\xbb\xbf"


def load_alpha_table(path: Path = ALPHA_CSV) -> Dict[str, Dict[str, float]]:
    """Return {strata: {group: alpha}} from alpha_table.csv."""
    if not path.exists():
        raise FileNotFoundError(f"alpha_table.csv not found at {path}")
    result: Dict[str, Dict[str, float]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            strata = row["strata"]
            result[strata] = {g: float(row[g]) for g in _GROUPS if g in row}
    return result


def validate_alpha_sums(alpha: Dict[str, Dict[str, float]], tol: float = 1e-3) -> List[str]:
    """Return a list of error strings for strata whose alpha sum deviates from 1.0."""
    errors = []
    for strata in _STRATA_KEYS:
        if strata not in alpha:
            errors.append(f"[ALPHA] alpha_table.csv — strata '{strata}' missing")
            continue
        total = sum(alpha[strata].values())
        if abs(total - 1.0) > tol:
            errors.append(
                f"[ALPHA] alpha_table.csv — strata '{strata}' sums to {total:.6f}, expected 1.0"
            )
    return errors


def write_budget_shares(alpha: Dict[str, Dict[str, float]], path: Path = BUDGET_SHARES_FILE) -> None:
    """Render alpha values as Jomini and write to z_SOL_group_budget_shares.txt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # export_budget_shares_jomini expects prices (unused when shares provided) + shares
    text = export_budget_shares_jomini(prices={}, shares=alpha)
    path.write_bytes(UTF8_BOM + text.encode("utf-8") + b"\n")
    print(f"[gen_budget_shares] Written → {path.relative_to(REPO_ROOT)}")


def main() -> None:
    check_only = "--check" in sys.argv
    alpha = load_alpha_table()
    errors = validate_alpha_sums(alpha)

    if errors:
        for e in errors:
            print(e)
        sys.exit(1)

    if check_only:
        print("[gen_budget_shares] Alpha sums valid.")
        sys.exit(0)

    write_budget_shares(alpha)


if __name__ == "__main__":
    main()
