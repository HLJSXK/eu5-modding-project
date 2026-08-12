#!/usr/bin/env python3
"""Compare unified vs per-stratum savings pressure multipliers across saves.

Reconstructs the current (unified) liquid funds and an alternative (per-stratum)
variant, then re-runs the country-level solve for each country to measure:
- Feasibility rate change
- Gate pass rate change
- Class coefficient magnitude shift
- Per-stratum residual change

Usage:
    python -m tools.eu5_save_parser.stratified_multiplier_impact <analysis_dir> ...
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np


STRATA = ["nobles", "clergy", "burghers", "commoners", "tribesmen"]
CLASSES = [1, 2, 3, 4]


def load_country_data(analysis_dir: Path) -> Dict[str, Dict]:
    """Load country-level estate gold, targets, and aggregated variables."""
    countries = {}
    with open(analysis_dir / "countries.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tag = row["owner_tag"]
            countries[tag] = {
                "nobles_gold": float(row["gls_nobles_gold"] or 0),
                "nobles_target": float(row["gls_nobles_target"] or 0),
                "clergy_gold": float(row["gls_clergy_gold"] or 0),
                "clergy_target": float(row["gls_clergy_target"] or 0),
                "burghers_gold": float(row["gls_burghers_gold"] or 0),
                "burghers_target": float(row["gls_burghers_target"] or 0),
                "commoner_gold": float(row["gls_commoner_gold"] or 0),
                "commoner_target": float(row["gls_commoner_target"] or 0),
                "tribesmen_gold": float(row["gls_tribesmen_gold"] or 0),
                "tribesmen_target": float(row["gls_tribesmen_target"] or 0),
                "unified_adjustment": float(row["gls_savings_pressure_adjustment"] or 0),
            }
    return countries


def load_location_data(analysis_dir: Path) -> List[Dict]:
    """Load per-location net income, base spending, class assignment, and owner."""
    locations = []
    with open(analysis_dir / "locations.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            owner_tag = row.get("owner_tag", "")
            if not owner_tag:
                continue
            locations.append({
                "owner_tag": owner_tag,
                "demand_class": int(float(row.get("sol_location_demand_class") or 0)),
                "nobles_net_income": float(row.get("sol_location_nobles_net_income") or 0),
                "clergy_net_income": float(row.get("sol_location_clergy_net_income") or 0),
                "burghers_net_income": float(row.get("sol_location_burghers_net_income") or 0),
                "commoners_net_income": float(row.get("sol_location_commoners_net_income") or 0),
                "tribesmen_net_income": float(row.get("sol_location_tribesmen_net_income") or 0),
                "nobles_base_spending": float(row.get("sol_location_nobles_base_spending") or 0),
                "clergy_base_spending": float(row.get("sol_location_clergy_base_spending") or 0),
                "burghers_base_spending": float(row.get("sol_location_burghers_base_spending") or 0),
                "commoners_base_spending": float(row.get("sol_location_commoners_base_spending") or 0),
                "laborers_base_spending": float(row.get("sol_location_laborers_base_spending") or 0),
                "peasants_base_spending": float(row.get("sol_location_peasants_base_spending") or 0),
                "soldiers_base_spending": float(row.get("sol_location_soldiers_base_spending") or 0),
                "tribesmen_base_spending": float(row.get("sol_location_tribesmen_base_spending") or 0),
            })
    return locations


def compute_per_stratum_adjustments(country: Dict) -> Dict[str, float]:
    """Compute per-stratum savings pressure adjustments: (gold / target - 1) * 0.25, capped at +0.5."""
    # Map internal stratum names to CSV column keys (commoner vs commoners)
    key_map = {
        "nobles": "nobles",
        "clergy": "clergy",
        "burghers": "burghers",
        "commoners": "commoner",  # CSV uses singular
        "tribesmen": "tribesmen",
    }
    adjustments = {}
    for stratum in STRATA:
        key = key_map[stratum]
        gold = country[f"{key}_gold"]
        target = country[f"{key}_target"]
        if target > 0:
            adj = (gold / target - 1) * 0.25
            adjustments[stratum] = min(adj, 0.5)
        else:
            adjustments[stratum] = 0.0
    return adjustments


def build_matrix_and_target(
    locations: List[Dict],
    owner_tag: str,
    multipliers: Dict[str, float]
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Build 4x4 matrix M and 4-vector target t for the given country under the specified multipliers.

    Returns (M, t) or (None, None) if country has no valid locations.
    """
    owned = [loc for loc in locations if loc["owner_tag"] == owner_tag and loc["demand_class"] in CLASSES]
    if not owned:
        return None, None

    M = np.zeros((4, 4))
    t = np.zeros(4)

    for loc in owned:
        cls = loc["demand_class"]
        col = cls - 1

        # Raw scale for this location under the specified multipliers
        total_liquid = sum(
            max(0, loc[f"{s}_net_income"]) * max(0, 1 + multipliers[s])
            for s in STRATA
        )
        total_base = sum(
            loc[f"{s}_base_spending"]
            for s in ["nobles", "clergy", "burghers", "laborers", "peasants", "soldiers", "tribesmen"]
        )
        raw_scale = total_liquid / total_base if total_base > 0 else 0

        # Matrix: M[row, col] += raw_weighted_base_spending for each stratum
        M[0, col] += raw_scale * loc["nobles_base_spending"]
        M[1, col] += raw_scale * loc["clergy_base_spending"]
        M[2, col] += raw_scale * loc["burghers_base_spending"]
        # Row 3 = commoners + tribesmen (lower)
        M[3, col] += raw_scale * (
            loc["commoners_base_spending"] + loc["tribesmen_base_spending"]
        )

    # Target vector: sum of liquid funds per stratum
    for loc in owned:
        t[0] += max(0, loc["nobles_net_income"]) * max(0, 1 + multipliers["nobles"])
        t[1] += max(0, loc["clergy_net_income"]) * max(0, 1 + multipliers["clergy"])
        t[2] += max(0, loc["burghers_net_income"]) * max(0, 1 + multipliers["burghers"])
        t[3] += (
            max(0, loc["commoners_net_income"]) * max(0, 1 + multipliers["commoners"])
            + max(0, loc["tribesmen_net_income"]) * max(0, 1 + multipliers["tribesmen"])
        )

    return M, t


def check_feasibility(M: np.ndarray, t: np.ndarray, tol: float = 0.01) -> Tuple[bool, float]:
    """Check if target t is in cone(M columns) by solving min ||M x - t||_2 s.t. x >= 0.

    Returns (is_feasible, residual_norm).
    """
    from scipy.optimize import nnls
    x, residual = nnls(M, t)
    residual_norm = np.linalg.norm(M @ x - t)
    return residual_norm < tol, residual_norm


def check_gate_pass(M: np.ndarray, t: np.ndarray) -> Tuple[bool, List[float]]:
    """Check if the raw baseline (all x=1) passes the gate: at least one row has error > 1e-5.

    Returns (passes_gate, raw_errors_per_row).
    """
    raw_pred = M.sum(axis=1)
    raw_errors = np.abs(raw_pred - t)
    passes = np.any(raw_errors > 1e-5)
    return passes, raw_errors.tolist()


def solve_exact_4x4(M: np.ndarray, t: np.ndarray) -> Optional[np.ndarray]:
    """Solve M x = t exactly if det(M) is non-zero and solution is nonnegative."""
    try:
        x = np.linalg.solve(M, t)
        if np.all(x >= -1e-9):
            return np.maximum(x, 0)
    except np.linalg.LinAlgError:
        pass
    return None


def analyze_country(
    country: Dict,
    locations: List[Dict],
    owner_tag: str,
    per_stratum_adjustments: Dict[str, float]
) -> Dict:
    """Compare unified vs per-stratum multipliers for one country."""
    unified_mults = {s: country["unified_adjustment"] for s in STRATA}

    M_uni, t_uni = build_matrix_and_target(locations, owner_tag, unified_mults)
    M_strat, t_strat = build_matrix_and_target(locations, owner_tag, per_stratum_adjustments)

    result = {
        "tag": owner_tag,
        "unified_adjustment": country["unified_adjustment"],
        "nobles_adjustment": per_stratum_adjustments["nobles"],
        "clergy_adjustment": per_stratum_adjustments["clergy"],
        "burghers_adjustment": per_stratum_adjustments["burghers"],
        "commoners_adjustment": per_stratum_adjustments["commoners"],
        "tribesmen_adjustment": per_stratum_adjustments["tribesmen"],
    }

    if M_uni is None or M_strat is None:
        result.update({
            "status": "no_locations",
            "unified_feasible": None,
            "stratified_feasible": None,
        })
        return result

    # Feasibility
    uni_feasible, uni_residual = check_feasibility(M_uni, t_uni)
    strat_feasible, strat_residual = check_feasibility(M_strat, t_strat)

    # Gate pass
    uni_gate, uni_raw_errors = check_gate_pass(M_uni, t_uni)
    strat_gate, strat_raw_errors = check_gate_pass(M_strat, t_strat)

    # Exact solve
    x_uni = solve_exact_4x4(M_uni, t_uni)
    x_strat = solve_exact_4x4(M_strat, t_strat)

    result.update({
        "status": "ok",
        "unified_feasible": uni_feasible,
        "unified_residual": uni_residual,
        "unified_gate_pass": uni_gate,
        "unified_raw_error_max": max(uni_raw_errors),
        "stratified_feasible": strat_feasible,
        "stratified_residual": strat_residual,
        "stratified_gate_pass": strat_gate,
        "stratified_raw_error_max": max(strat_raw_errors),
        "unified_exact_success": x_uni is not None,
        "stratified_exact_success": x_strat is not None,
    })

    if x_uni is not None:
        result["unified_coef_max"] = float(np.max(x_uni))
        result["unified_coef_mean"] = float(np.mean(x_uni))
    if x_strat is not None:
        result["stratified_coef_max"] = float(np.max(x_strat))
        result["stratified_coef_mean"] = float(np.mean(x_strat))

    return result


def process_save(analysis_dir: Path) -> List[Dict]:
    """Process one save and return per-country comparison results."""
    countries = load_country_data(analysis_dir)
    locations = load_location_data(analysis_dir)

    results = []
    for tag, country_data in countries.items():
        per_stratum_adj = compute_per_stratum_adjustments(country_data)
        res = analyze_country(country_data, locations, tag, per_stratum_adj)
        results.append(res)

    return results


def summarize_results(results: List[Dict], save_name: str):
    """Print summary statistics for one save."""
    valid = [r for r in results if r["status"] == "ok"]
    if not valid:
        print(f"\n{save_name}: No valid countries")
        return

    uni_feasible = sum(1 for r in valid if r["unified_feasible"])
    strat_feasible = sum(1 for r in valid if r["stratified_feasible"])

    uni_gate = sum(1 for r in valid if r["unified_gate_pass"])
    strat_gate = sum(1 for r in valid if r["stratified_gate_pass"])

    uni_exact = sum(1 for r in valid if r["unified_exact_success"])
    strat_exact = sum(1 for r in valid if r["stratified_exact_success"])

    total = len(valid)

    print(f"\n{'='*60}")
    print(f"{save_name}")
    print(f"{'='*60}")
    print(f"Countries analyzed: {total}")
    print(f"\nFeasibility (cone containment, tol=0.01):")
    print(f"  Unified:     {uni_feasible:4d} / {total} ({100*uni_feasible/total:5.1f}%)")
    print(f"  Stratified:  {strat_feasible:4d} / {total} ({100*strat_feasible/total:5.1f}%)")
    print(f"  Delta:       {strat_feasible - uni_feasible:+4d} ({100*(strat_feasible - uni_feasible)/total:+5.1f}%)")

    print(f"\nGate pass (at least one raw error > 1e-5):")
    print(f"  Unified:     {uni_gate:4d} / {total} ({100*uni_gate/total:5.1f}%)")
    print(f"  Stratified:  {strat_gate:4d} / {total} ({100*strat_gate/total:5.1f}%)")
    print(f"  Delta:       {strat_gate - uni_gate:+4d} ({100*(strat_gate - uni_gate)/total:+5.1f}%)")

    print(f"\nExact solve success (nonnegative solution exists):")
    print(f"  Unified:     {uni_exact:4d} / {total} ({100*uni_exact/total:5.1f}%)")
    print(f"  Stratified:  {strat_exact:4d} / {total} ({100*strat_exact/total:5.1f}%)")
    print(f"  Delta:       {strat_exact - uni_exact:+4d} ({100*(strat_exact - uni_exact)/total:+5.1f}%)")

    # Coefficient magnitude comparison for countries where both succeeded
    both_exact = [r for r in valid if r["unified_exact_success"] and r["stratified_exact_success"]]
    if both_exact:
        uni_coef_means = [r["unified_coef_mean"] for r in both_exact]
        strat_coef_means = [r["stratified_coef_mean"] for r in both_exact]
        mean_change = np.mean(np.array(strat_coef_means) - np.array(uni_coef_means))
        print(f"\nClass coefficient mean change (where both exact succeeded, N={len(both_exact)}):")
        print(f"  Average delta: {mean_change:+.4f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("analysis_dirs", nargs="+", type=Path, help="One or more _all_* analysis directories")
    parser.add_argument("--output", type=Path, help="Optional CSV output path for detailed results")
    args = parser.parse_args()

    all_results = []

    for analysis_dir in args.analysis_dirs:
        if not analysis_dir.exists():
            print(f"Warning: {analysis_dir} does not exist, skipping", file=sys.stderr)
            continue

        save_name = analysis_dir.name.replace("_all_", "")
        print(f"\nProcessing {save_name}...", file=sys.stderr)

        results = process_save(analysis_dir)
        for r in results:
            r["save"] = save_name
        all_results.extend(results)

        summarize_results(results, save_name)

    if args.output:
        fieldnames = [
            "save", "tag", "status",
            "unified_adjustment", "nobles_adjustment", "clergy_adjustment",
            "burghers_adjustment", "commoners_adjustment", "tribesmen_adjustment",
            "unified_feasible", "unified_residual", "unified_gate_pass", "unified_raw_error_max",
            "unified_exact_success", "unified_coef_max", "unified_coef_mean",
            "stratified_feasible", "stratified_residual", "stratified_gate_pass", "stratified_raw_error_max",
            "stratified_exact_success", "stratified_coef_max", "stratified_coef_mean",
        ]
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\nDetailed results written to {args.output}")


if __name__ == "__main__":
    main()
