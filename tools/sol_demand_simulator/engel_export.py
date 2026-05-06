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

Continuity conditions (anchor at origin, y=0):
    c[0] = 0   (all groups through (0, 0))
    c[k] = c[k-1] + (b[k-1] - b[k]) * y_k   (forward propagation only)

Budget constraint (Σ spending = income at savings equilibrium):
    Σ_g (b_g * y + c_g) * P_g = y
    Satisfied automatically when Σ_g α_g,k = 1 at each bracket k,
    because Σ_g c_g * P_g = 0 follows from the recurrence and Σ α = 1.

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
import sys
from pathlib import Path
from typing import Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALPHA_TABLE = REPO_ROOT / "data" / "alpha_table.csv"
BRACKET_TABLE = REPO_ROOT / "data" / "alpha_bracket_table.csv"
BUDGET_SHARES_FILE = (
    REPO_ROOT
    / "src/stable/in_game/common/script_values/z_SOL_group_budget_shares.txt"
)

# EXPORT_ALPHA_MULTIPLIER — scaling applied to all emitted budget-share (alpha) values.
#
# The simulator calibrates alpha so that Σ_g alpha_g = 1 (pops spend exactly their income).
# Two structural gaps cause actual in-game spending to fall below this baseline:
#
#   GAP 1 — Progressive goods unlock (→ sol_era_coeff in-game):
#     Some goods require technology or institutions that are unavailable in early game.
#     The simulator assumes the full goods catalogue exists at all times; missing slots
#     reduce effective demand.  As eras advance, more goods unlock and the gap narrows.
#     In-game correction: global_var:sol_era_coeff, initialised to 2.0, decays ×0.95/era.
#
#   GAP 2 — Market price fluctuations (→ sol_market_scarcity_adj in-game):
#     Substitute groups force pops to buy the cheapest available good rather than the
#     group average the simulator assumes.  When goods are scarce (high prices), actual
#     spending falls; when cheap, it rises.
#     In-game correction: var:sol_market_scarcity_adj_<strata>, cached yearly per location,
#     range [0.80, 1.20] based on a 5-good market basket.
#
# Both in-game corrections are injected as multiply lines in the demand-scale blocks
# (z_SOL_group_demand_scales_location.txt).  This keeps the Python source at Σα = 1
# and makes both corrections visible and tunable without re-running the exporter.
#
# EXPORT_ALPHA_MULTIPLIER itself stays at 1.0 — do not restore the old 2.0 here.
# To adjust the base multiplier: edit sol_init_export_adj in A_SOL_economy_effects.txt.
EXPORT_ALPHA_MULTIPLIER: float = 1.0

_STRATA_KEYS = ["nobles", "clergy", "burghers", "commoners", "tribesmen"]
_GROUPS = [
    "basic_clothing", "crude_goods", "staple", "condiments", "heating",
    "household", "standard_clothing", "intoxicants", "luxury_drinks",
    "luxury_food", "luxury_goods", "protein", "spices", "precious",
    "treasures", "medicine", "ritual", "weapons", "mounts", "knowledge",
]

# Maps strata -> EU5 script_value name for GDP per capita in location scope.
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
# Power-based alpha generation
# ---------------------------------------------------------------------------


def compute_reference_income(thresholds: List[float]) -> float:
    """Pick the bracket1~2 boundary as the default power-curve anchor."""
    if len(thresholds) >= 3:
        return float(thresholds[2])
    if len(thresholds) >= 2:
        return float(thresholds[-1])
    return 1.0


def pick_bracket_sample_incomes(thresholds: List[float], y_ref: float) -> List[float]:
    """Pick one representative income sample per bracket."""
    n = len(thresholds)
    if n == 0:
        return []
    if n == 1:
        return [max(float(y_ref), 1e-6)]

    incomes: List[float] = []
    for k in range(n):
        lo = float(thresholds[k])
        if k + 1 < n:
            hi = float(thresholds[k + 1])
            incomes.append(max((lo + hi) * 0.5, 1e-6))
        else:
            prev = float(thresholds[k - 1]) if k > 0 else 0.0
            width = max(lo - prev, max(float(y_ref), 1.0) * 0.5, 1e-6)
            incomes.append(max(lo + 0.5 * width, 1e-6))
    return incomes


def compute_intersection_b(P_gs: Dict[str, float]) -> float:
    """Compute the shared b-value implied by Σ alpha = 1 at the reference income."""
    total_P = sum(max(float(P_gs.get(group, 0.0)), 0.0) for group in _GROUPS)
    if total_P <= 0:
        return 0.0
    return 1.0 / total_P


def generate_power_b_profile(
    intersection_b: float,
    exponent: float,
    incomes: List[float],
    y_ref: float,
) -> List[float]:
    """Generate a power-law b(y) profile from the shared intersection anchor."""
    if intersection_b <= 0:
        return [0.0 for _ in incomes]
    ref = max(float(y_ref), 1e-6)
    return [
        float(intersection_b) * (max(float(y), 1e-6) / ref) ** float(exponent)
        for y in incomes
    ]


def generate_power_d_boundary_slopes(
    intersection_b: float,
    exponent: float,
    thresholds: List[float],
    y_ref: float,
) -> List[float]:
    """
    Compute per-bracket average slope of d_g(y) = d_ref*(y/y_ref)^(1+exponent).

    d_ref = intersection_b * y_ref (= y_ref / ΣP_g).

    Bracket k (thresholds[k] to thresholds[k+1]):
        slope = (d_g(y_{k+1}) - d_g(y_k)) / (y_{k+1} - y_k)
    Last bracket: instantaneous derivative at thresholds[-1].

    Before normalization this enforces d_g(0)=0 (c_0=0) and d_g(y_ref)=d_ref
    simultaneously, so the (1,1) anchor holds and slopes near 0 depend only on
    the exponent, not on P_g.
    """
    if intersection_b <= 0:
        return [0.0] * len(thresholds)
    d_ref = float(intersection_b) * max(float(y_ref), 1e-6)
    ref = max(float(y_ref), 1e-6)
    exp = float(exponent)

    def _d(y: float) -> float:
        if y <= 0:
            return 0.0
        return d_ref * (y / ref) ** (1.0 + exp)

    slopes: List[float] = []
    n = len(thresholds)
    for k in range(n):
        y_lo = float(thresholds[k])
        if k + 1 < n:
            y_hi = float(thresholds[k + 1])
            width = y_hi - y_lo
            slope = (_d(y_hi) - _d(y_lo)) / width if width > 1e-12 else 0.0
        else:
            # Last bracket: derivative d'(y_lo) = d_ref*(1+exp)/y_ref*(y_lo/y_ref)^exp
            slope = d_ref * (1.0 + exp) / ref * (y_lo / ref) ** exp if y_lo > 0 else 0.0
        slopes.append(max(slope, 0.0))
    return slopes


def generate_power_alpha_brackets_for_strata(
    P_gs: Dict[str, float],
    thresholds: List[float],
    exponents: Dict[str, float],
) -> Dict[int, Dict[str, float]]:
    """Generate per-bracket alpha values for one strata from shared-intersection power-law d(y) curves."""
    y_ref = compute_reference_income(thresholds)
    n = len(thresholds)
    raw_by_bracket: Dict[int, Dict[str, float]] = {k: {} for k in range(n)}
    intersection_b = compute_intersection_b(P_gs)

    for group in _GROUPS:
        P = float(P_gs.get(group, 0.0))
        if P <= 0:
            for k in range(n):
                raw_by_bracket[k][group] = 0.0
            continue
        d_slopes = generate_power_d_boundary_slopes(intersection_b, exponents.get(group, 0.0), thresholds, y_ref)
        for k, slope in enumerate(d_slopes):
            raw_by_bracket[k][group] = max(slope * P, 0.0)

    normalized: Dict[int, Dict[str, float]] = {}
    fallback_total_P = sum(max(float(P_gs.get(g, 0.0)), 0.0) for g in _GROUPS)
    if fallback_total_P > 0:
        fallback = {g: max(float(P_gs.get(g, 0.0)), 0.0) / fallback_total_P for g in _GROUPS}
    else:
        fallback = {g: 1.0 / len(_GROUPS) for g in _GROUPS}

    for k in range(n):
        raw = raw_by_bracket[k]
        total = sum(raw.values())
        if total <= 0:
            normalized[k] = fallback.copy()
        else:
            normalized[k] = {g: raw.get(g, 0.0) / total for g in _GROUPS}
    return normalized


def generate_power_alpha_bracket_table(
    thresholds_by_strata: Dict[str, List[float]],
    P_values_by_strata: Dict[str, Dict[str, float]],
    exponents_by_group: Dict[str, float],
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Generate a full alpha_bracket_table structure from shared group exponents."""
    result: Dict[str, Dict[int, Dict[str, float]]] = {}
    for strata in _STRATA_KEYS:
        thresholds = thresholds_by_strata.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))
        P_values = P_values_by_strata.get(strata, {})
        result[strata] = generate_power_alpha_brackets_for_strata(
            P_values,
            thresholds,
            exponents_by_group,
        )
    return result


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
                strata_alphas.get(k, {}).get(group, 0.0) * EXPORT_ALPHA_MULTIPLIER
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
    d_ref: float | None = None,
) -> List[float]:
    """
    Compute per-bracket demand offset c_k for continuity.

    d(y) = b(y)*y + c(y),   b(y) = alpha(y)/P

    When d_ref is None (default): c_0 = 0 (all curves through origin).
    When d_ref is given: anchors at (y_ref, d_ref) where y_ref = thresholds[2].
      - c[k_ref] = d_ref - alpha[k_ref]/P * y_ref
      - Forward (k > k_ref): c[k] = c[k-1] + (alpha[k-1] - alpha[k])/P * thresholds[k]
      - Backward (k < k_ref): c[k] = c[k+1] + (alpha[k+1] - alpha[k])/P * thresholds[k+1]
    Both modes ensure d is continuous at every bracket boundary.
    """
    n = len(thresholds)
    if P <= 0 or n <= 1:
        return [0.0] * n

    if d_ref is None:
        c = [0.0]
        for k in range(1, n):
            delta = (alpha_brackets[k - 1] - alpha_brackets[k]) / P * thresholds[k]
            c.append(c[-1] + delta)
        return c

    y_ref = float(thresholds[2]) if n >= 3 else float(thresholds[-1])
    k_ref = 2 if n >= 3 else n - 1

    c = [0.0] * n
    c[k_ref] = d_ref - alpha_brackets[k_ref] / P * y_ref

    for k in range(k_ref + 1, n):
        c[k] = c[k - 1] + (alpha_brackets[k - 1] - alpha_brackets[k]) / P * thresholds[k]

    for k in range(k_ref - 1, -1, -1):
        c[k] = c[k + 1] + (alpha_brackets[k + 1] - alpha_brackets[k]) / P * thresholds[k + 1]

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
    lines.append("# anchor at (y_ref, d_ref); propagate forward/backward for continuity\n\n")

    for strata in _STRATA_KEYS:
        lines.append(f"# {strata}\n")
        income_var = _INCOME_VAR.get(strata)
        s_thresholds = thresholds.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))
        s_alphas = alphas.get(strata, {})
        s_P = P_values.get(strata, {})
        n = len(s_thresholds)

        for group in _GROUPS:
            P = s_P.get(group, 0.0)
            a_vals = [s_alphas.get(k, {}).get(group, 0.0) * EXPORT_ALPHA_MULTIPLIER for k in range(n)]
            c_vals = compute_piecewise_offsets(a_vals, s_thresholds, P, d_ref=None)

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
    P_values: Dict[str, Dict[str, float]],
    output_path: Path = DEMAND_BASE_FILE,
    zero_threshold: float = 1e-9,
) -> None:
    """
    Generate z_SOL_group_demand_base_location.txt.

    Defines local_{strata}_{group}_demand_base = gdp * alpha/P + offset.
    If P_g_s == 0 (group has no goods priced for this strata), emits
    value = 1 (neutral — no demand increase or decrease) to avoid divide-by-zero.

    Args:
        P_values:       {strata: {group: P_g_s}}
        output_path:    destination file
        zero_threshold: P values below this are treated as zero
    """
    lines: List[str] = [
        "# Intermediate demand base values — one entry per (strata, group) pair.\n",
        "# Formula (normal):  demand_base = gdp * alpha/P + demand_offset\n",
        "# Formula (P==0):    demand_base = 1  (neutral; group not priced for this strata)\n",
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
            P       = P_values.get(strata, {}).get(group, 0.0)

            if gdp_var is None or P <= zero_threshold:
                # tribesmen (no income term) or zero-price group:
                # base = 1 -> demand_scale = sp+1, neutral demand, no Engel curve
                reason = "tribesmen: no income term" if gdp_var is None else f"P_g_s = {P:.6g} ≈ 0"
                lines.append(f"# {reason} — hardcoded neutral\n")
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

    Full formula (non-tribesmen):
        demand_scale = (sp + 1) * demand_base * sol_era_coeff * sol_market_scarcity_adj

    where:
        demand_base            = gdp * alpha/P + offset  (z_SOL_group_demand_base_location.txt)
        sol_era_coeff          = global_var; corrects for progressive goods unlock across eras
        sol_market_scarcity_adj = location variable; corrects for market price fluctuations

    Tribesmen formula: (sp + 1) * sol_era_coeff * sol_market_scarcity_adj  (no income term).
    top-level multiply = named_sv is confirmed valid; avoids nested sub-expressions.
    """
    lines: List[str] = [
        "# Location-scope demand scale values — one entry per (strata, group) pair.\n",
        "# Full formula (non-tribesmen):\n",
        "#   demand_scale = (sp + 1) * demand_base * sol_era_coeff * sol_market_scarcity_adj\n",
        "#\n",
        "#   demand_base             = gdp * alpha/P + offset  (z_SOL_group_demand_base_location.txt)\n",
        "#   sol_era_coeff           = global_var:sol_era_coeff\n",
        "#                             Corrects for progressive goods unlock: simulator assumes the\n",
        "#                             full goods catalogue; early-game missing slots reduce spending.\n",
        "#                             Starts at 2.0, decays ×0.95 per era as more goods unlock.\n",
        "#   sol_market_scarcity_adj_<strata> = var:sol_market_scarcity_adj_<strata> on each location\n",
        "#                             Per-stratum market price correction weighted by budget shares.\n",
        "#                             Cached yearly per location by SOL_compute_scarcity_score_<strata>.\n",
        "#                             Natural range varies by stratum spending pattern (no hard cap).\n",
        "# Tribesmen use: (sp + 1) * sol_era_coeff * sol_market_scarcity_adj_tribesmen  (no income term).\n",
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

            scarcity_var = f"local_sol_scarcity_adj_{strata}"
            if gdp_var is None:
                # tribesmen: (sp + 1) * era_coeff * scarcity_adj
                lines += [
                    f"{var} = {{\n",
                    f"\tvalue = {sp_var}\n",
                    f"\tadd = 1\n",
                    f"\tmultiply = global_var:sol_era_coeff\n",
                    f"\tmultiply = {scarcity_var}\n",
                    f"\tmin = 0\n",
                    f"}}\n",
                ]
            else:
                # (sp + 1) * demand_base * era_coeff * scarcity_adj
                lines += [
                    f"{var} = {{\n",
                    f"\tvalue = {sp_var}\n",
                    f"\tadd = 1\n",
                    f"\tmultiply = local_{strata}_{group}_demand_base\n",
                    f"\tmultiply = global_var:sol_era_coeff\n",
                    f"\tmultiply = {scarcity_var}\n",
                    f"\tmin = 0\n",
                    f"}}\n",
                ]
        lines.append("\n")

    # demand_scale_offset = demand_scale - 1 (GUI per-group ±% row, |+=0% format)
    for group in _GROUPS:
        lines.append(f"# ── {group} ──\n")
        for strata in _STRATA_KEYS:
            var = f"local_{strata}_{group}_demand_scale"
            lines += [
                f"{var}_offset = {{\n",
                f"\tvalue = {var}\n",
                f"\tadd = -1\n",
                f"}}\n",
            ]
        lines.append("\n")

    # Consumption rate = sp + 1 (GUI "Liquid Funds" row, |+=0% format -> shows as %)
    # Variable name derived from _SP_VAR to match the inconsistent commoner/commoners naming.
    lines.append("# ── Consumption rate = 1 + savings_pressure (GUI Liquid Funds row) ──\n")
    for strata in _STRATA_KEYS:
        sp_var = _SP_VAR[strata]
        var    = sp_var.replace("_savings_pressure", "_consumption_rate")
        lines += [
            f"{var} = {{\n",
            f"\tvalue = {sp_var}\n",
            f"\tadd = 1\n",
            f"\tmin = 0\n",
            f"}}\n",
        ]

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
    print(f"Exported -> {out.relative_to(REPO_ROOT)}")

    warnings = export_bracket_budget_shares(bracket_alphas, bracket_thresholds)
    for w in warnings:
        print(f"WARNING: {w}")
    print(f"Exported -> {BUDGET_SHARES_FILE.relative_to(REPO_ROOT)}")

    warnings2 = export_demand_offsets(bracket_alphas, bracket_thresholds, P_values)
    for w in warnings2:
        print(f"WARNING: {w}")
    print(f"Exported -> {DEMAND_OFFSETS_FILE.relative_to(REPO_ROOT)}")

    export_demand_base(P_values)
    print(f"Exported -> {DEMAND_BASE_FILE.relative_to(REPO_ROOT)}")

    export_demand_scales_with_offset()
    print(f"Exported -> {DEMAND_SCALES_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
