"""
EU5 SOL Demand Simulator — Piecewise Engel Curve Exporter

Generates three EU5 script_value files from data/alpha_bracket_table.csv:

  z_SOL_group_budget_shares.txt  — piecewise α(y) (slope parameter)
  z_SOL_group_demand_offsets.txt — piecewise c(y) (continuity offset)
  z_SOL_group_demand_scales_location.txt — combined demand formula

## Piecewise-linear demand with continuity

Demand for group g at strata s:
    d_g_s(y) = b_g_s(y) * y + c_g_s(y)
    where b_g_s(y) = α_g_s(y) / P_g_s

Continuity conditions:
    c_0 = 0                      (segment 0 always passes through origin)
    c_k = c_{k-1} + (b_{k-1} - b_k) * y_k   (d continuous at threshold y_k)

Budget constraint (Σ spending = income at savings equilibrium):
    Σ_g (b_g * y + c_g) * P_g = y
    Satisfied automatically when Σ_g α_g,k = 1 at each bracket k,
    because Σ_g c_g * P_g = 0 follows from the continuity recurrence.

## EU5 encoding

α(y) is exported as cumulative-jump script_value:
    local_{s}_{g}_budget_share = { value=α₀  if>=y₁ add=Δα₁  ... }

c(y) is exported similarly:
    local_{s}_{g}_demand_offset = { value=0  if>=y₁ add=Δc₁  ... }

demand_scale uses an inline sub-expression:
    demand_scale = (sp+1) * { y * α/P + c }
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
    "nobles":    [0.0,  3.0,  8.0, 25.0],
    "clergy":    [0.0,  1.0,  3.0, 10.0],
    "burghers":  [0.0,  1.0,  3.0, 10.0],
    "commoners": [0.0, 0.05, 0.20,  0.80],
    "tribesmen": [0.0, 0.05, 0.20,  0.80],
}

DEMAND_OFFSETS_FILE = (
    REPO_ROOT
    / "src/stable/in_game/common/script_values/z_SOL_group_demand_offsets.txt"
)
DEMAND_BASE_FILE = (
    REPO_ROOT
    / "src/stable/in_game/common/script_values/z_SOL_group_demand_base_location.txt"
)
DEMAND_SCALES_FILE = (
    REPO_ROOT
    / "src/stable/in_game/common/script_values/z_SOL_group_demand_scales_location.txt"
)

# EU5 variable name mappings for demand scale generation.
# savings_pressure and gdp_per_capita follow inconsistent naming conventions in the base mod.
_SP_VAR: Dict[str, str] = {
    "nobles":    "local_nobles_savings_pressure",
    "clergy":    "local_clergy_savings_pressure",
    "burghers":  "local_burghers_savings_pressure",
    "commoners": "local_commoner_savings_pressure",
    "tribesmen": "local_tribesmen_savings_pressure",
}
_GDP_VAR: Dict[str, str | None] = {
    "nobles":    "local_noble_gdp_per_capita_display",
    "clergy":    "local_clergy_gdp_per_capita_display",
    "burghers":  "local_burghers_gdp_per_capita_display",
    "commoners": "local_commoner_gdp_per_capita_display",
    "tribesmen": None,
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
                    f"[{strata} bracket {k}] Σα = {total:.5f} (expected 1.0, "
                    f"gap = {total - 1.0:+.5f})"
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
                    f"local_{strata}_{group}_budget_share = {{ value = {alpha_0:.5f} }}\n"
                )
                continue

            # Build cumulative-jump form
            jumps = [bracket_values[k] - bracket_values[k - 1] for k in range(1, n_brackets)]
            has_any_jump = any(abs(j) > tolerance for j in jumps)

            if not has_any_jump:
                # No non-linearity for this (strata, group) — emit compact form
                lines.append(
                    f"local_{strata}_{group}_budget_share = {{ value = {alpha_0:.5f} }}\n"
                )
                continue

            lines.append(f"local_{strata}_{group}_budget_share = {{\n")
            lines.append(f"\tvalue = {alpha_0:.5f}\n")
            for k, jump in enumerate(jumps, start=1):
                if abs(jump) <= tolerance:
                    continue
                thresh = strata_thresholds[k]
                lines.append(
                    f"\tif = {{ limit = {{ {income_var} >= {thresh} }} add = {jump:.5f} }}\n"
                )
            lines.append("}\n")

        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return warnings


# ---------------------------------------------------------------------------
# Offset computation
# ---------------------------------------------------------------------------

def compute_piecewise_offsets(
    alpha_brackets: List[float],
    thresholds: List[float],
    P: float,
) -> List[float]:
    """
    Compute per-bracket demand offset c_k for continuity.

    d(y) = b(y)*y + c(y),   b(y) = alpha(y)/P

    c_0 = 0  (segment 0 passes through origin)
    c_k = c_{k-1} + (alpha_{k-1} - alpha_k) / P * y_k   for k >= 1

    Ensures d_k(y_k) = d_{k-1}(y_k) at every threshold y_k.
    """
    n = len(thresholds)
    if P <= 0 or n <= 1:
        return [0.0] * n
    c = [0.0]
    for k in range(1, n):
        delta = (alpha_brackets[k - 1] - alpha_brackets[k]) / P * thresholds[k]
        c.append(c[-1] + delta)
    return c


def export_demand_offsets(
    alphas: Dict[str, Dict[int, Dict[str, float]]],
    thresholds: Dict[str, List[float]],
    P_values: Dict[str, Dict[str, float]],
    output_path: Path = DEMAND_OFFSETS_FILE,
    tolerance: float = 1e-9,
) -> List[str]:
    """
    Generate z_SOL_group_demand_offsets.txt.

    Each c(y) is a piecewise script_value derived from the alpha brackets and P_g_s.
    Tribesmen and degenerate (all-same-alpha) cases emit { value = 0 }.

    Args:
        alphas:      {strata: {bracket: {group: alpha}}}
        thresholds:  {strata: [y_0, y_1, ...]}  (y_0 must be 0)
        P_values:    {strata: {group: P_g_s}}
        output_path: destination file
        tolerance:   minimum |Δc| to emit an if block

    Returns list of warning strings (empty = clean).
    """
    warnings: List[str] = []
    lines: List[str] = []
    lines.append("# Demand continuity offsets c(y) — piecewise values\n")
    lines.append("# Generated by engel_export.py — DO NOT EDIT MANUALLY\n")
    lines.append("# d(y) = b(y)*y + c(y),  b = alpha/P_g_s\n")
    lines.append("# c_0=0; c_k = c_{k-1} + (alpha_{k-1}-alpha_k)/P * y_k\n\n")

    for strata in _STRATA_KEYS:
        lines.append(f"# {strata}\n")
        income_var = _INCOME_VAR.get(strata)
        s_thresholds = thresholds.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))
        s_alphas = alphas.get(strata, {})
        s_P = P_values.get(strata, {})
        n = len(s_thresholds)

        for group in _GROUPS:
            P = s_P.get(group, 0.0)
            a_vals = [s_alphas.get(k, {}).get(group, 0.0) for k in range(n)]
            c_vals = compute_piecewise_offsets(a_vals, s_thresholds, P)

            if income_var is None or all(abs(cv) <= tolerance for cv in c_vals):
                lines.append(f"local_{strata}_{group}_demand_offset = {{ value = 0 }}\n")
                continue

            lines.append(f"local_{strata}_{group}_demand_offset = {{\n")
            lines.append(f"\tvalue = 0\n")
            for k in range(1, n):
                delta = c_vals[k] - c_vals[k - 1]
                if abs(delta) <= tolerance:
                    continue
                lines.append(
                    f"\tif = {{ limit = {{ {income_var} >= {s_thresholds[k]} }}"
                    f" add = {delta:.5f} }}\n"
                )
            lines.append("}\n")

        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return warnings


def export_demand_base(
    output_path: Path = DEMAND_BASE_FILE,
) -> None:
    """
    Generate z_SOL_group_demand_base_location.txt.

    Defines local_{strata}_{group}_demand_base = gdp * alpha/P + offset
    as a named intermediate so that demand_scale can reference it via a
    top-level multiply = named_sv (confirmed valid), avoiding nested
    sub-expressions with variable refs (unconfirmed in engine docs).
    """
    lines: List[str] = [
        "# Intermediate demand base values — one entry per (strata, group) pair.\n",
        "# Formula: demand_base = gdp * alpha/P + demand_offset\n",
        "#   = piecewise linear demand at unit savings_pressure\n",
        "# Referenced by z_SOL_group_demand_scales_location.txt via multiply = demand_base.\n",
        "#\n",
        "# Generated by engel_export.py — DO NOT EDIT MANUALLY\n",
        "\n",
    ]

    for group in _GROUPS:
        lines.append(f"# {'─' * 62}\n")
        lines.append(f"#  GROUP: {group}\n")
        lines.append(f"# {'─' * 62}\n")

        for strata in _STRATA_KEYS:
            gdp_var = _GDP_VAR[strata]
            var     = f"local_{strata}_{group}_demand_base"

            if gdp_var is None:
                # tribesmen — no income term; base = 1 (multiplied by sp+1 in scale)
                lines.append(f"{var} = {{ value = 1 }}\n")
            else:
                lines += [
                    f"{var} = {{\n",
                    f"\tvalue = {gdp_var}\n",
                    f"\tmultiply = local_{strata}_{group}_budget_share\n",
                    f"\tdivide = local_{strata}_{group}_P\n",
                    f"\tadd = local_{strata}_{group}_demand_offset\n",
                    f"}}\n",
                ]
        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")


def export_demand_scales_with_offset(
    output_path: Path = DEMAND_SCALES_FILE,
) -> None:
    """
    (Re)generate z_SOL_group_demand_scales_location.txt.

    Precise formula: demand_scale = (sp + 1) * demand_base
    where demand_base = gdp * alpha/P + offset (defined in z_SOL_group_demand_base_location.txt).
    top-level multiply = named_sv is confirmed valid; avoids nested sub-expressions.

    Tribesmen formula is unchanged: sp + 1 (demand_base = 1 for tribesmen).
    """
    lines: List[str] = [
        "# Location-scope demand scale values — one entry per (strata, group) pair.\n",
        "# Precise formula (non-tribesmen):\n",
        "#   demand_scale = (sp + 1) * demand_base\n",
        "#   demand_base  = gdp * alpha/P + demand_offset  (z_SOL_group_demand_base_location.txt)\n",
        "# Using named intermediate avoids nested multiply={} sub-expressions with variable refs.\n",
        "# Tribesmen use a simplified form: sp + 1 (no income term).\n",
        "#\n",
        "# Generated by engel_export.py — DO NOT EDIT MANUALLY\n",
        "#   nobles   : local_nobles_savings_pressure / local_noble_gdp_per_capita_display\n",
        "#   clergy   : local_clergy_savings_pressure / local_clergy_gdp_per_capita_display\n",
        "#   burghers : local_burghers_savings_pressure / local_burghers_gdp_per_capita_display\n",
        "#   commoners: local_commoner_savings_pressure / local_commoner_gdp_per_capita_display\n",
        "#   tribesmen: local_tribesmen_savings_pressure\n",
        "\n",
    ]

    for group in _GROUPS:
        lines.append(f"# {'─' * 62}\n")
        lines.append(f"#  GROUP: {group}\n")
        lines.append(f"# {'─' * 62}\n")

        for strata in _STRATA_KEYS:
            sp_var = _SP_VAR[strata]
            gdp_var = _GDP_VAR[strata]
            var    = f"local_{strata}_{group}_demand_scale"

            if gdp_var is None:
                # tribesmen: sp + 1 (demand_base = 1, so result = sp + 1)
                lines += [
                    f"{var} = {{\n",
                    f"\tvalue = {sp_var}\n",
                    f"\tadd = 1\n",
                    f"\tmin = 0\n",
                    f"}}\n",
                ]
            else:
                # (sp + 1) * demand_base — multiply = named_sv at top level is confirmed valid
                lines += [
                    f"{var} = {{\n",
                    f"\tvalue = {sp_var}\n",
                    f"\tadd = 1\n",
                    f"\tmultiply = local_{strata}_{group}_demand_base\n",
                    f"\tmin = 0\n",
                    f"}}\n",
                ]
        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Group prices export (wraps parser._auto_group_prices)
# ---------------------------------------------------------------------------

_UTF8_BOM = b"\xef\xbb\xbf"


def export_group_prices(output_path: Path | None = None) -> Path:
    """Compute P_g_s from the current demand matrix and write z_SOL_group_prices.txt.

    Returns the path written.
    """
    from parser import (  # type: ignore
        _auto_group_prices,
        GROUP_PRICES_FILE,
        export_group_prices_jomini,
    )
    path = output_path or GROUP_PRICES_FILE
    prices = _auto_group_prices()
    text = export_group_prices_jomini(prices)
    path.write_bytes(_UTF8_BOM + text.encode("utf-8") + b"\n")
    return path


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Export all SOL mod files from alpha_bracket_table.csv"
    )
    ap.add_argument(
        "--init", action="store_true",
        help="Bootstrap alpha_bracket_table.csv from alpha_table.csv (run once)",
    )
    ap.add_argument(
        "--validate", action="store_true",
        help="Validate bracket constraints without exporting",
    )
    args = ap.parse_args()

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

    if args.validate:
        print("All bracket constraints satisfied.")
        return

    from parser import _auto_group_prices  # type: ignore
    P_values = _auto_group_prices()

    out = export_group_prices()
    print(f"Exported → {out.relative_to(REPO_ROOT)}")

    warnings = export_bracket_budget_shares(bracket_alphas, bracket_thresholds)
    for w in warnings:
        print(f"WARNING: {w}")
    print(f"Exported → {BUDGET_SHARES_FILE.relative_to(REPO_ROOT)}")

    warnings2 = export_demand_offsets(bracket_alphas, bracket_thresholds, P_values)
    for w in warnings2:
        print(f"WARNING: {w}")
    print(f"Exported → {DEMAND_OFFSETS_FILE.relative_to(REPO_ROOT)}")

    export_demand_base()
    print(f"Exported → {DEMAND_BASE_FILE.relative_to(REPO_ROOT)}")

    export_demand_scales_with_offset()
    print(f"Exported → {DEMAND_SCALES_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
