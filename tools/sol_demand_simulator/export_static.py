"""
Static JSON export for the GitHub Pages viewer.

Reads existing data files (CSV / JSON) and writes a set of JSON snapshots
to docs/simulator/data/.  Run this script locally or in CI before deploying.

Output files:
  meta.json           — group/good metadata, strata list
  alpha_bracket.json  — per-strata bracket alphas, thresholds, offsets, base prices
  alpha_generator.json — alpha-generator settings + power-law preview curves
  engel_curves.json   — per-good and per-group Engel curve point sets
  savings_params.json — ScenarioParams defaults for the JS savings simulator
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Path setup — allow running from any directory
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

REPO_ROOT = _HERE.parent.parent
OUT_DIR   = REPO_ROOT / "docs" / "simulator" / "data"

from dataclasses import replace as _dc_replace

from curve_designer import (
    SUBSTITUTE_GROUPS, GROUP_GOODS, GROUP_COLORS, LUXURY_RANK,
    ALL_GOODS, CurveDesignerState,
)
from engel_export import (
    _STRATA_KEYS, _GROUPS,
    load_bracket_table, load_bracket_thresholds,
    compute_piecewise_offsets, compute_intersection_b, compute_reference_income,
    generate_power_alpha_bracket_table,
    DEFAULT_THRESHOLDS,
    BRACKET_TABLE,
)
from parser import load_demand_matrix


def _build_demand_matrix():
    dm = load_demand_matrix()
    # Replicate app.py default commoner re-weighting (500 laborers : 500 peasants : 0 soldiers)
    result = {}
    w = {"laborers": 0.5, "peasants": 0.5, "soldiers": 0.0}
    for good, entry in dm.items():
        weighted_comm = sum(entry.demand_per_pop_type[pt] * w[pt] for pt in w)
        result[good] = _dc_replace(
            entry,
            strata_demand={**entry.strata_demand, "commoners": weighted_comm},
        )
    return result


_demand_matrix = _build_demand_matrix()


def _round(v: float, n: int = 6) -> float:
    return round(float(v), n)


# ---------------------------------------------------------------------------
# Step 1 – initialise CurveDesignerState
# ---------------------------------------------------------------------------

def _init_state() -> CurveDesignerState:
    cd = CurveDesignerState()
    cd.init_from_demand_matrix(_demand_matrix)
    return cd


# ---------------------------------------------------------------------------
# Step 2 – load bracket table (alpha + thresholds)
# ---------------------------------------------------------------------------

def _load_bracket_data() -> tuple[
    dict[str, dict[int, dict[str, float]]],
    dict[str, list[float]],
]:
    if BRACKET_TABLE.exists():
        alphas     = load_bracket_table()
        thresholds = load_bracket_thresholds()
    else:
        # Fallback: replicate flat alpha table across all brackets
        alphas     = {}
        thresholds = dict(DEFAULT_THRESHOLDS)
    return alphas, thresholds


# ---------------------------------------------------------------------------
# Step 3 – compute piecewise offsets for every (strata, group)
# ---------------------------------------------------------------------------

def _compute_offsets(
    cd: CurveDesignerState,
    alphas: dict[str, dict[int, dict[str, float]]],
    thresholds: dict[str, list[float]],
) -> dict[str, dict[int, dict[str, float]]]:
    offsets: dict[str, dict[int, dict[str, float]]] = {}
    for strata in _STRATA_KEYS:
        offsets[strata] = {}
        s_alphas     = alphas.get(strata, {})
        s_thresholds = thresholds.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))
        if not s_alphas or not s_thresholds:
            continue

        P_vals = {
            g: cd.groups[g].base_price_sum_per_strata.get(strata, 0.0)
            for g in SUBSTITUTE_GROUPS
        }
        y_ref   = compute_reference_income(s_thresholds)
        b_ref   = compute_intersection_b(P_vals)
        d_ref   = b_ref * y_ref if b_ref > 0 else None

        n_brackets = len(s_thresholds)
        for group in SUBSTITUTE_GROUPS:
            P = P_vals.get(group, 0.0)
            if P <= 0:
                for k in range(n_brackets):
                    offsets[strata].setdefault(k, {})[group] = 0.0
                continue
            alpha_brackets = [
                s_alphas.get(k, {}).get(group, 0.0)
                for k in range(n_brackets)
            ]
            c_vals = compute_piecewise_offsets(alpha_brackets, s_thresholds, P, d_ref=d_ref)
            for k, c in enumerate(c_vals):
                offsets[strata].setdefault(k, {})[group] = _round(c)

    return offsets


# ---------------------------------------------------------------------------
# Step 4 – build per-good & per-group Engel curves
# ---------------------------------------------------------------------------

_INCOME_POINTS = 80

def _build_engel_curves(
    cd: CurveDesignerState,
    alphas: dict[str, dict[int, dict[str, float]]],
    thresholds: dict[str, list[float]],
) -> dict:
    # Compact schema: x shared per strata, only y stored per curve
    # { per_good: { strata: { x: [...], curves: { good: [...y] } } } }
    result: dict[str, dict] = {"per_good": {}, "per_group": {}}

    for strata in _STRATA_KEYS:
        s_thresholds = thresholds.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))
        s_alphas_list = [
            alphas.get(strata, {}).get(k, {})
            for k in range(len(s_thresholds))
        ]
        max_t = max(s_thresholds) if s_thresholds else 1.0
        x_range = np.linspace(0.0, max_t * 2.0, _INCOME_POINTS)
        x_list = [_round(v, 4) for v in x_range.tolist()]

        # --- per-good curves ---
        per_good_pts = cd.compute_per_good_curve_points(
            strata,
            x_range,
            alphas_per_bracket=s_alphas_list if any(s_alphas_list) else None,
            thresholds=s_thresholds if any(s_alphas_list) else None,
        )
        result["per_good"][strata] = {
            "x": x_list,
            "curves": {
                good: [_round(v, 4) for v in per_good_pts[good].tolist()]
                for good in ALL_GOODS
            },
        }

        # --- per-group curves: d_g_s(y) = (α/P)*y + c (piecewise) ---
        P_vals = {
            g: cd.groups[g].base_price_sum_per_strata.get(strata, 0.0)
            for g in SUBSTITUTE_GROUPS
        }
        y_ref = compute_reference_income(s_thresholds)
        b_ref = compute_intersection_b(P_vals)
        d_ref = b_ref * y_ref if b_ref > 0 else None
        n_brackets = len(s_thresholds)

        group_curves: dict[str, list[float]] = {}
        for group in SUBSTITUTE_GROUPS:
            P = P_vals.get(group, 0.0)
            group_y = np.zeros(_INCOME_POINTS)
            if P > 0 and n_brackets > 0:
                alpha_brackets = [s_alphas_list[k].get(group, 0.0) for k in range(n_brackets)]
                c_vals = compute_piecewise_offsets(alpha_brackets, s_thresholds, P, d_ref=d_ref)
                for i, y in enumerate(x_range):
                    k = int(sum(1 for t in s_thresholds if t <= y)) - 1
                    k = max(0, min(k, n_brackets - 1))
                    group_y[i] = (alpha_brackets[k] / P) * y + c_vals[k]
            group_curves[group] = [_round(v, 4) for v in group_y.tolist()]
        result["per_group"][strata] = {"x": x_list, "curves": group_curves}

    return result


# ---------------------------------------------------------------------------
# Step 5 – load alpha-generator settings & build power-law preview
# ---------------------------------------------------------------------------

_AG_FILE = REPO_ROOT / "data" / "alpha_generator_settings.json"


def _default_ag_section() -> dict:
    return {"low_rank_exp": -0.35, "high_rank_exp": 0.35, "group_order": {}}


def _load_ag_settings() -> dict:
    if not _AG_FILE.exists():
        return {"all": _default_ag_section()}
    try:
        raw = json.loads(_AG_FILE.read_text(encoding="utf-8"))
        if "low_rank_exp" in raw:
            return {"all": raw}
        return raw
    except Exception:
        return {"all": _default_ag_section()}


def _derive_exponents(order_map: dict[str, int], high_exp: float, low_exp: float) -> dict[str, float]:
    if not order_map:
        return {g: 0.0 for g in SUBSTITUTE_GROUPS}
    ordered = sorted(order_map.items(), key=lambda kv: kv[1])
    n = len(ordered)
    result: dict[str, float] = {}
    for pos, (group, _) in enumerate(ordered):
        t = pos / max(n - 1, 1)
        result[group] = float(high_exp) + (float(low_exp) - float(high_exp)) * t
    for g in SUBSTITUTE_GROUPS:
        result.setdefault(g, 0.0)
    return result


def _build_ag_json(
    cd: CurveDesignerState,
    thresholds: dict[str, list[float]],
) -> dict:
    settings_raw = _load_ag_settings()
    out_settings: dict[str, dict] = {}
    preview_curves: dict[str, dict] = {}

    for strata in _STRATA_KEYS:
        # resolve settings: strata-specific → "all" → default
        section = settings_raw.get(strata) or settings_raw.get("all") or _default_ag_section()
        out_settings[strata] = {
            "low_rank_exp":  float(section.get("low_rank_exp", -0.35)),
            "high_rank_exp": float(section.get("high_rank_exp", 0.35)),
            "group_order":   {k: int(v) for k, v in section.get("group_order", {}).items()},
        }

        exponents = _derive_exponents(
            out_settings[strata]["group_order"],
            out_settings[strata]["high_rank_exp"],
            out_settings[strata]["low_rank_exp"],
        )
        P_vals = {
            g: cd.groups[g].base_price_sum_per_strata.get(strata, 0.0)
            for g in SUBSTITUTE_GROUPS
        }
        s_thresholds = thresholds.get(strata, DEFAULT_THRESHOLDS.get(strata, [0.0]))

        power_table = generate_power_alpha_bracket_table(
            {strata: s_thresholds},
            {strata: P_vals},
            exponents,
        )
        preview_curves[strata] = {
            group: {
                "brackets":   [_round(power_table[strata].get(k, {}).get(group, 0.0))
                                for k in range(len(s_thresholds))],
                "thresholds": [_round(t, 4) for t in s_thresholds],
            }
            for group in SUBSTITUTE_GROUPS
        }

    return {"settings": out_settings, "preview_curves": preview_curves}


# ---------------------------------------------------------------------------
# Step 6 – assemble meta.json
# ---------------------------------------------------------------------------

def _build_meta() -> dict:
    return {
        "groups": [
            {
                "name":         g,
                "color":        GROUP_COLORS.get(g, "#888888"),
                "luxury_rank":  LUXURY_RANK.get(g, 0),
            }
            for g in SUBSTITUTE_GROUPS
        ],
        "goods":       ALL_GOODS,
        "group_goods": GROUP_GOODS,
        "strata":      _STRATA_KEYS,
        "brackets":    6,
    }


# ---------------------------------------------------------------------------
# Step 7 – savings_params.json
# ---------------------------------------------------------------------------

def _build_savings_params() -> dict:
    return {
        "modes": ["linear", "tanh", "quadratic", "deadband"],
        "strata_params": {
            # pmin/pmax from simulator.py STRATA_PARAMS (sensitivity, threshold, pmin, pmax)
            "nobles":    {"pmin": -0.50, "pmax": 3.0},
            "clergy":    {"pmin": -0.50, "pmax": 2.0},
            "burghers":  {"pmin": -0.50, "pmax": 2.0},
            "commoners": {"pmin": -0.50, "pmax": 1.5},
            "tribesmen": {"pmin": -0.50, "pmax": 1.5},
        },
        "defaults": {
            "monthly_income":           50.0,
            "pressure_mode":            "linear",
            "pressure_linear_slope":    0.50,
            "pressure_tanh_k":          1.0,
            "pressure_quadratic_norm":  2.0,
            "pressure_deadband_delta":  0.15,
            "pressure_deadband_slope":  0.50,
            "savings_ratio_range":      [-1.0, 3.0],
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("export_static: initialising state …")
    cd = _init_state()

    print("export_static: loading bracket table …")
    alphas, thresholds = _load_bracket_data()

    print("export_static: computing piecewise offsets …")
    offsets = _compute_offsets(cd, alphas, thresholds)

    print("export_static: building Engel curves …")
    engel = _build_engel_curves(cd, alphas, thresholds)

    print("export_static: building alpha-generator preview …")
    base_prices: dict[str, dict[str, float]] = {}
    for strata in _STRATA_KEYS:
        base_prices[strata] = {
            g: _round(cd.groups[g].base_price_sum_per_strata.get(strata, 0.0))
            for g in SUBSTITUTE_GROUPS
        }

    alpha_bracket: dict = {
        "thresholds": {
            s: [_round(t, 4) for t in thresholds.get(s, [])]
            for s in _STRATA_KEYS
        },
        "alphas": {
            s: {
                str(k): {g: _round(v) for g, v in bracket.items()}
                for k, bracket in alphas.get(s, {}).items()
            }
            for s in _STRATA_KEYS
        },
        "offsets": {
            s: {
                str(k): {g: _round(v) for g, v in bracket.items()}
                for k, bracket in offsets.get(s, {}).items()
            }
            for s in _STRATA_KEYS
        },
        "base_prices": base_prices,
    }

    ag = _build_ag_json(cd, thresholds)
    meta = _build_meta()
    savings = _build_savings_params()

    # Goods weights
    weights: dict = {}
    for group in SUBSTITUTE_GROUPS:
        weights[group] = {}
        for good in GROUP_GOODS.get(group, []):
            weights[group][good] = _round(
                cd.goods_weight_store.good_share_in_group(good, group), 4
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "meta.json":            meta,
        "alpha_bracket.json":   alpha_bracket,
        "alpha_generator.json": ag,
        "engel_curves.json":    engel,
        "savings_params.json":  savings,
        "goods_weights.json":   weights,
    }
    for fname, data in files.items():
        path = OUT_DIR / fname
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        size_kb = path.stat().st_size / 1024
        print(f"  wrote {fname} ({size_kb:.1f} KB)")

    print("export_static: done.")


if __name__ == "__main__":
    main()
