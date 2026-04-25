"""
EU5 SOL Demand Simulator — Piecewise Engel Curve Exporter

Reads data/alpha_bracket_table.csv and generates
z_SOL_group_budget_shares.txt with per-bracket if blocks.

EU5 script_values support if/else_if/else (confirmed in _script_values.info).
We use the cumulative-jump encoding:

    local_{strata}_{group}_budget_share = {
        value = α₀
        if = { limit = { <income_var> >= y₁ } add = +Δα₁ }
        if = { limit = { <income_var> >= y₂ } add = +Δα₂ }
        ...
    }

Budget constraint: Σ_g Δα_g,k = 0 for all k (jumps are zero-sum across groups),
which holds automatically when each bracket row sums to 1.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALPHA_TABLE = REPO_ROOT / "data" / "alpha_table.csv"
BRACKET_TABLE = REPO_ROOT / "data" / "alpha_bracket_table.csv"
BUDGET_SHARES_FILE = (
    REPO_ROOT
    / "src/stable/in_game/common/script_values/z_SOL_group_budget_shares.txt"
)

_STRATA_KEYS = ["nobles", "clergy", "burghers", "commoners", "tribesmen"]
_GROUPS = [
    "alcohol", "textiles", "knowledge", "precious", "ritual",
    "stimulants", "spices", "staple", "protein", "military", "household",
]

# Maps strata → EU5 script_value name for GDP per capita in location scope.
# tribesmen: None means keep constant α (uniform placeholder, no Engel curve).
_INCOME_VAR: Dict[str, str | None] = {
    "nobles":    "local_noble_gdp_per_capita_display",
    "clergy":    "local_clergy_gdp_per_capita_display",
    "burghers":  "local_burghers_gdp_per_capita_display",
    "commoners": "local_commoner_gdp_per_capita_display",
    "tribesmen": None,
}

# Default bracket thresholds per strata (income in gold/month/pop-unit).
# Bracket 0 always starts at 0 (threshold not emitted as if-block).
DEFAULT_THRESHOLDS: Dict[str, List[float]] = {
    "nobles":    [0.0, 5.0, 15.0, 40.0],
    "clergy":    [0.0, 3.0, 10.0, 30.0],
    "burghers":  [0.0, 3.0, 10.0, 30.0],
    "commoners": [0.0, 0.5,  1.5,  4.0],
    "tribesmen": [0.0, 0.5,  1.5,  4.0],
}


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def load_bracket_table(path: Path = BRACKET_TABLE) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Load alpha_bracket_table.csv.

    Returns {strata: {bracket_index: {group: alpha}}}.
    """
    result: Dict[str, Dict[int, Dict[str, float]]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            strata = row["strata"]
            bracket = int(row["bracket"])
            if strata not in result:
                result[strata] = {}
            result[strata][bracket] = {g: float(row[g]) for g in _GROUPS if g in row}
    return result


def load_bracket_thresholds(path: Path = BRACKET_TABLE) -> Dict[str, List[float]]:
    """Load per-strata bracket threshold values from alpha_bracket_table.csv."""
    thresholds: Dict[str, List[float]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            strata = row["strata"]
            bracket = int(row["bracket"])
            thresh = float(row["threshold"])
            if strata not in thresholds:
                thresholds[strata] = []
            # Expand list to fit bracket index
            while len(thresholds[strata]) <= bracket:
                thresholds[strata].append(0.0)
            thresholds[strata][bracket] = thresh
    return thresholds


def save_bracket_table(
    alphas: Dict[str, Dict[int, Dict[str, float]]],
    thresholds: Dict[str, List[float]],
    path: Path = BRACKET_TABLE,
) -> None:
    """Write alpha_bracket_table.csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["strata", "bracket", "threshold"] + _GROUPS
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for strata in _STRATA_KEYS:
            strata_alphas = alphas.get(strata, {})
            strata_thresholds = thresholds.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))
            for k in range(len(strata_thresholds)):
                bracket_alphas = strata_alphas.get(k, {})
                row: dict = {
                    "strata": strata,
                    "bracket": k,
                    "threshold": strata_thresholds[k],
                }
                row.update({g: round(bracket_alphas.get(g, 0.0), 6) for g in _GROUPS})
                writer.writerow(row)


def init_bracket_table_from_alpha_table(
    alpha_path: Path = ALPHA_TABLE,
    bracket_path: Path = BRACKET_TABLE,
) -> None:
    """
    Bootstrap alpha_bracket_table.csv from alpha_table.csv.

    All brackets start with identical α values (degenerate = fully linear).
    Users then adjust per-bracket α in the Tab 4 UI to introduce non-linearity.
    """
    single: Dict[str, Dict[str, float]] = {}
    with alpha_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            strata = row["strata"]
            single[strata] = {g: float(row[g]) for g in _GROUPS if g in row}

    # Replicate across all brackets per strata
    all_alphas: Dict[str, Dict[int, Dict[str, float]]] = {}
    for strata in _STRATA_KEYS:
        base = single.get(strata, {g: 1.0 / len(_GROUPS) for g in _GROUPS})
        thresholds = DEFAULT_THRESHOLDS.get(strata, [0.0])
        all_alphas[strata] = {k: base.copy() for k in range(len(thresholds))}

    save_bracket_table(all_alphas, DEFAULT_THRESHOLDS, bracket_path)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_all_bracket_constraints(
    alphas: Dict[str, Dict[int, Dict[str, float]]],
    tolerance: float = 1e-5,
) -> List[str]:
    """
    Check Σ_g α_g,s,k = 1 for every (strata, bracket).

    Returns a list of error strings (empty = all OK).
    """
    errors = []
    for strata, brackets in alphas.items():
        for k, group_alphas in brackets.items():
            total = sum(group_alphas.values())
            if abs(total - 1.0) > tolerance:
                errors.append(
                    f"[{strata} bracket {k}] Σα = {total:.6f} (expected 1.0, "
                    f"gap = {total - 1.0:+.6f})"
                )
    return errors


# ---------------------------------------------------------------------------
# EU5 Script Value Export
# ---------------------------------------------------------------------------

def export_bracket_budget_shares(
    alphas: Dict[str, Dict[int, Dict[str, float]]],
    thresholds: Dict[str, List[float]],
    output_path: Path = BUDGET_SHARES_FILE,
    tolerance: float = 1e-9,
) -> List[str]:
    """
    Generate z_SOL_group_budget_shares.txt with piecewise if blocks.

    Each script_value uses the cumulative-jump encoding so that
    Σ_g α_g_s(y) = 1 holds at every income level.

    Args:
        alphas:      {strata: {bracket: {group: alpha}}}
        thresholds:  {strata: [threshold_0, threshold_1, ...]} — threshold_0 must be 0
        output_path: destination file (overwrites)
        tolerance:   minimum |jump| to emit an if block

    Returns list of warning strings (non-fatal; empty = clean export).
    """
    warnings: List[str] = []
    lines: List[str] = []
    lines.append("# Budget shares — piecewise Engel curves\n")
    lines.append("# Generated by engel_export.py — DO NOT EDIT MANUALLY\n")
    lines.append("# Source: data/alpha_bracket_table.csv\n\n")

    for strata in _STRATA_KEYS:
        lines.append(f"# {strata}\n")
        income_var = _INCOME_VAR.get(strata)
        strata_thresholds = thresholds.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))
        strata_alphas = alphas.get(strata, {})
        n_brackets = len(strata_thresholds)

        for group in _GROUPS:
            bracket_values = [
                strata_alphas.get(k, {}).get(group, 0.0)
                for k in range(n_brackets)
            ]
            alpha_0 = bracket_values[0]

            if income_var is None:
                # tribesmen: constant — no piecewise needed
                lines.append(
                    f"local_{strata}_{group}_budget_share = {{ value = {alpha_0:.6f} }}\n"
                )
                continue

            # Build cumulative-jump form
            jumps = [bracket_values[k] - bracket_values[k - 1] for k in range(1, n_brackets)]
            has_any_jump = any(abs(j) > tolerance for j in jumps)

            if not has_any_jump:
                # No non-linearity for this (strata, group) — emit compact form
                lines.append(
                    f"local_{strata}_{group}_budget_share = {{ value = {alpha_0:.6f} }}\n"
                )
                continue

            lines.append(f"local_{strata}_{group}_budget_share = {{\n")
            lines.append(f"\tvalue = {alpha_0:.6f}\n")
            for k, jump in enumerate(jumps, start=1):
                if abs(jump) <= tolerance:
                    continue
                thresh = strata_thresholds[k]
                lines.append(
                    f"\tif = {{ limit = {{ {income_var} >= {thresh} }} add = {jump:+.6f} }}\n"
                )
            lines.append("}\n")

        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return warnings


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Export piecewise budget shares from alpha_bracket_table.csv"
    )
    parser.add_argument(
        "--init", action="store_true",
        help="Bootstrap alpha_bracket_table.csv from alpha_table.csv (run once)",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate bracket constraints without exporting",
    )
    args = parser.parse_args()

    if args.init:
        if BRACKET_TABLE.exists():
            print(f"WARNING: {BRACKET_TABLE} already exists. Overwriting.")
        init_bracket_table_from_alpha_table()
        print(f"Initialized {BRACKET_TABLE}")
        return

    if not BRACKET_TABLE.exists():
        print(f"ERROR: {BRACKET_TABLE} not found. Run with --init first.")
        return

    bracket_alphas = load_bracket_table(BRACKET_TABLE)
    bracket_thresholds = load_bracket_thresholds(BRACKET_TABLE)

    errors = validate_all_bracket_constraints(bracket_alphas)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        if not args.validate:
            print("Aborting export due to constraint violations.")
            return
        return

    if args.validate:
        print("All bracket constraints satisfied.")
        return

    warnings = export_bracket_budget_shares(bracket_alphas, bracket_thresholds)
    for w in warnings:
        print(f"WARNING: {w}")
    print(f"Exported → {BUDGET_SHARES_FILE}")


if __name__ == "__main__":
    main()
