"""
EU5 SOL Demand Simulator — Simulation Engine

Exactly replicates the three demand-scaling functions from SOL_pop_values.txt:

  1. GDP per capita  →  local_*_gdp_per_capita_display
  2. Nonlinear GDP component  →  local_*_gdp_nonlinear_component
  3. Savings pressure  →  local_*_savings_pressure

Combined into: sol_gdp_per_capita_scale  (the multiplier applied to every good's demand)

The simulation loop models the demand-update interval (the SOL situation pulse):
  - Monthly tick : income earned, spending deducted, savings updated (frozen scale)
  - Every N years: demand scale recalculated from current savings and GDP
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd

from parser import STRATA

# ---------------------------------------------------------------------------
# Per-strata constants (directly from SOL_pop_values.txt)
# ---------------------------------------------------------------------------

PRESSURE_MODES = {
    "linear":    "Linear (vanilla) — slope 0.5",
    "tanh":      "Tanh (smooth sigmoid) — fast saturation",
    "quadratic": "Quadratic — zero slope near target",
    "deadband":  "Deadband ±15% — stable buffer zone",
}

STRATA_PARAMS = {
    # (sensitivity, threshold, pressure_min, pressure_max)
    "nobles":    (0.05, 0.3, -0.50, 3.0),
    "clergy":    (0.15, 0.2, -0.50, 2.0),
    "burghers":  (0.15, 0.2, -0.50, 2.0),
    "commoners": (1.50, 0.1, -0.50, 1.5),
    "tribesmen": (1.50, 0.1, -0.50, 1.5),
}

# Tax-share weights (from SOL_pop_values.txt local_*_tax_share)
TAX_WEIGHTS = {
    "nobles":    150,
    "clergy":    25,
    "burghers":  20,
    "commoners": 1,     # laborers + peasants + soldiers
    "tribesmen": 0.01,
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Scenario input
# ---------------------------------------------------------------------------

@dataclass
class StrataState:
    pop_count: float   # EU5 pop-unit count (1 unit = 1000 people)
    tax_rate:  float   # 0.0 – 1.0  (fraction taxed away from estate)
    savings:   float   # estate gold (current)


@dataclass
class ScenarioParams:
    # Country-level
    monthly_income: float           # owner.monthly_income_trade_and_tax  [gold/month]
    num_institutions: int           # number of embraced institutions (0–10)

    # Location-level
    tax_base: float                 # location_tax_base  [gold/month]
    effective_control: float        # 0.01 – 1.0

    # Social mechanics
    peasant_enfranchisement: float  # 0.1 – 1.0

    # Per-strata initial state
    strata: Dict[str, StrataState]

    # Simulation settings
    update_interval_years: int      # 1, 2, or 3
    sim_years: int                  # total simulation duration in years

    # --- fields with defaults below this line ---

    # Commoner sub-type pop counts (stored for UI round-trip; not used in formulas here).
    # app.py uses these to build a population-weighted demand matrix before simulation.
    # If all zero, app.py falls back to equal three-way split.
    pop_laborers: float = 0.0
    pop_peasants: float = 0.0
    pop_soldiers: float = 0.0

    # Demand scale smoothing (EMA)
    # d_new = ema_alpha × d_computed + (1 - ema_alpha) × d_old
    # 1.0 = no smoothing (vanilla behaviour); lower values damp oscillation
    ema_alpha: float = 1.0

    # Savings pressure function shape (see PRESSURE_MODES)
    pressure_mode: str = "linear"

    # Per-mode tunable parameters
    pressure_linear_slope:   float = 0.50   # linear: ramp slope
    pressure_tanh_k:         float = 1.0    # tanh:  steepness factor k in tanh(k·d)
    pressure_quadratic_norm: float = 2.0    # quadratic: |d|=norm → pressure reaches pmax
    pressure_deadband_delta: float = 0.15   # deadband: dead-zone half-width
    pressure_deadband_slope: float = 0.50   # deadband: ramp slope outside dead zone


# ---------------------------------------------------------------------------
# Three scaling functions (exact replicas from SOL_pop_values.txt)
# ---------------------------------------------------------------------------

def fn1_gdp_per_capita(p: ScenarioParams) -> Dict[str, float]:
    """
    Function 1: GDP per capita for each strata.

    Replicates (per SOL_pop_values.txt):
        local_nobles_effective_tax_share, local_commoner_effective_tax_share,
        local_*_income_pool, local_*_gdp_display, local_*_gdp_per_capita_display
    """
    enf = _clamp(p.peasant_enfranchisement, 0.1, 1.0)
    oppression = 1.0 - enf

    commoner_pop  = max(0.001, p.strata["commoners"].pop_count)
    nobles_pop    = max(0.001, p.strata["nobles"].pop_count)
    clergy_pop    = max(0.001, p.strata["clergy"].pop_count)
    burghers_pop  = max(0.001, p.strata["burghers"].pop_count)
    tribesmen_pop = max(0.001, p.strata["tribesmen"].pop_count)

    raw_noble_share    = nobles_pop    * TAX_WEIGHTS["nobles"]
    clergy_share       = clergy_pop    * TAX_WEIGHTS["clergy"]
    burgher_share      = burghers_pop  * TAX_WEIGHTS["burghers"]
    raw_commoner_share = commoner_pop  * TAX_WEIGHTS["commoners"]
    tribesman_share    = tribesmen_pop * TAX_WEIGHTS["tribesmen"]

    commoner_to_nobles  = raw_commoner_share * oppression
    nobles_eff_share    = raw_noble_share + commoner_to_nobles
    commoner_eff_share  = raw_commoner_share - commoner_to_nobles

    total_share = max(0.01, nobles_eff_share + clergy_share + burgher_share
                            + commoner_eff_share + tribesman_share)

    ctrl = max(0.01, p.effective_control)
    control_loss = (1.0 / ctrl - 1.0) * p.tax_base  # lost to low control

    eff_shares = {
        "nobles":    nobles_eff_share,
        "clergy":    clergy_share,
        "burghers":  burgher_share,
        "commoners": commoner_eff_share,
        "tribesmen": tribesman_share,
    }
    pop_counts = {
        "nobles":    nobles_pop,
        "clergy":    clergy_pop,
        "burghers":  burghers_pop,
        "commoners": commoner_pop,
        "tribesmen": tribesmen_pop,
    }

    result: Dict[str, float] = {}
    for s in STRATA:
        strata_taxed = (1.0 - p.strata[s].tax_rate) * p.tax_base
        income_pool  = control_loss + strata_taxed
        gdp          = income_pool * eff_shares[s] / total_share
        result[s]    = gdp / pop_counts[s]   # GDP per pop-unit

    return result


def fn2_gdp_nonlinear(gdp_per_cap: Dict[str, float]) -> Dict[str, float]:
    """
    Function 2: Nonlinear (sigmoid-like) GDP component.

    Replicates:
        local_*_sol_pressure
        local_*_gdp_nonlinear_component
    """
    result: Dict[str, float] = {}
    for s in STRATA:
        sens, thresh, _, _ = STRATA_PARAMS[s]
        sol_pressure = gdp_per_cap[s] * sens - thresh
        denom        = max(0.05, 1.0 + sol_pressure * 0.45)
        result[s]    = sol_pressure / denom
    return result


def fn3_savings_pressure(p: ScenarioParams, savings: Dict[str, float]) -> Dict[str, float]:
    """
    Function 3: Savings pressure = f(savings / savings_target).

    Replicates (base):
        local_*_savings_target
        local_*_savings_pressure

    Extended with configurable function shape via p.pressure_mode:
        "linear"    — vanilla clamp(0.5*(r-1), pmin, pmax)
        "tanh"      — pmax * tanh(r-1), smooth saturation
        "quadratic" — sign(d) * pmax * (d/2)^2, zero slope at equilibrium
        "deadband"  — dead zone ±15% around target, then linear outside
    """
    income = max(0.0, p.monthly_income)
    targets = {
        "nobles":    max(80.0,  200.0 + 8.0 * income),
        "clergy":    max(60.0,  100.0 + 3.0 * income),
        "burghers":  max(60.0,  100.0 + 3.0 * income),
        "commoners": max(45.0,    0.0 + 2.0 * income),
        "tribesmen": max(35.0,    0.0 + 1.0 * income),
    }
    mode = getattr(p, "pressure_mode", "linear")
    result: Dict[str, float] = {}
    for s in STRATA:
        target           = targets[s]
        d                = savings[s] / max(1e-9, target) - 1.0   # savings ratio − 1
        _, _, pmin, pmax = STRATA_PARAMS[s]

        if mode == "tanh":
            k   = getattr(p, "pressure_tanh_k", 1.0)
            raw = pmax * math.tanh(k * d)
        elif mode == "quadratic":
            norm = getattr(p, "pressure_quadratic_norm", 2.0)
            raw  = math.copysign(pmax * (d / norm) ** 2, d)
        elif mode == "deadband":
            δ     = getattr(p, "pressure_deadband_delta", 0.15)
            slope = getattr(p, "pressure_deadband_slope", 0.50)
            raw   = 0.0 if abs(d) < δ else slope * (d - math.copysign(δ, d))
        else:  # "linear" / default
            slope = getattr(p, "pressure_linear_slope", 0.50)
            raw   = d * slope

        result[s] = _clamp(raw, pmin, pmax)
    return result


def savings_pressure_curve_np(
    x_ratio: np.ndarray,
    pmin: float,
    pmax: float,
    mode: str,
    slope: float = 0.50,
    k: float = 1.0,
    norm: float = 2.0,
    delta: float = 0.15,
) -> np.ndarray:
    """
    Compute savings_pressure for an array of savings/target ratios.
    Used by Tab 2 chart — not part of the simulation engine.

    Args:
        slope: linear / deadband ramp slope
        k:     tanh steepness factor
        norm:  quadratic normalization (|d|=norm → pmax)
        delta: deadband half-width
    """
    d = x_ratio - 1.0
    if mode == "tanh":
        raw = pmax * np.tanh(k * d)
    elif mode == "quadratic":
        raw = np.sign(d) * pmax * (d / norm) ** 2
    elif mode == "deadband":
        raw = np.where(np.abs(d) < delta, 0.0, slope * (d - np.sign(d) * delta))
    else:  # linear
        raw = d * slope
    return np.clip(raw, pmin, pmax)


def compute_savings_targets(p: ScenarioParams) -> Dict[str, float]:
    income = max(0.0, p.monthly_income)
    return {
        "nobles":    max(80.0,  200.0 + 8.0 * income),
        "clergy":    max(60.0,  100.0 + 3.0 * income),
        "burghers":  max(60.0,  100.0 + 3.0 * income),
        "commoners": max(45.0,    0.0 + 2.0 * income),
        "tribesmen": max(35.0,    0.0 + 1.0 * income),
    }


def compute_demand_scale(
    p: ScenarioParams,
    savings: Dict[str, float] | None = None,
    gdp_per_cap: Dict[str, float] | None = None,
) -> Dict[str, float]:
    """
    Compute sol_gdp_per_capita_scale for each strata.

    Replicates:
        local_*_demand_scale_offset
        gdp_per_capita_scale  (→ sol_gdp_per_capita_scale)
    """
    if savings is None:
        savings = {s: p.strata[s].savings for s in STRATA}
    if gdp_per_cap is None:
        gdp_per_cap = fn1_gdp_per_capita(p)

    nl       = fn2_gdp_nonlinear(gdp_per_cap)
    sp       = fn3_savings_pressure(p, savings)
    inst_bon = p.num_institutions * 0.05

    result: Dict[str, float] = {}
    for s in STRATA:
        offset    = nl[s] + sp[s]
        result[s] = 1.0 + inst_bon + offset
    return result


# ---------------------------------------------------------------------------
# Spending / income helpers
# ---------------------------------------------------------------------------

def compute_base_demand_index(demand_matrix: dict) -> Dict[str, float]:
    """
    Compute Σ_goods(strata_demand × price) for each strata at scale=1.

    strata_demand already encodes the combined vanilla + inject base per 1000 pops.
    This is the unscaled spending index (price-weighted demand units per 1000 pops/year).
    """
    idx: Dict[str, float] = {s: 0.0 for s in STRATA}
    for entry in demand_matrix.values():
        for s in STRATA:
            idx[s] += entry.strata_demand[s] * entry.price
    return idx


def compute_monthly_income_from_gdp(p: ScenarioParams) -> Dict[str, float]:
    """
    Monthly income per strata derived from the GDP formula.
    = local_*_gdp_display  (gold/month)
    """
    gdp_pc = fn1_gdp_per_capita(p)
    pop_counts = {
        "nobles":    max(0.001, p.strata["nobles"].pop_count),
        "clergy":    max(0.001, p.strata["clergy"].pop_count),
        "burghers":  max(0.001, p.strata["burghers"].pop_count),
        "commoners": max(0.001, p.strata["commoners"].pop_count),
        "tribesmen": max(0.001, p.strata["tribesmen"].pop_count),
    }
    return {s: gdp_pc[s] * pop_counts[s] for s in STRATA}


# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------

def simulate(
    p: ScenarioParams,
    demand_matrix: dict,
    income_override: Dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Run a month-by-month simulation.

    Income model:
      - If income_override is given, use those fixed gold/month values.
      - Otherwise derive from the GDP formula.

    Spending model (direct):
      - base_index[s] = Σ(demand × price) at scale=1, per pop-unit, per month
      - monthly_spending[s] = base_index[s] × pop_count[s] × demand_scale[s]
      - spending/income ratio is a balance measurement, not a parameter

    Returns a DataFrame with columns:
        month, year, strata, savings, savings_ratio, savings_target,
        demand_scale, gdp_nonlinear, savings_pressure, monthly_income,
        monthly_spending, net_flow, update_tick
    """
    # Compute income (fixed for duration of sim unless GDP params change)
    if income_override:
        income = income_override
    else:
        income = compute_monthly_income_from_gdp(p)

    # Pop counts per strata (for direct spending formula)
    pop_counts = {s: max(0.001, p.strata[s].pop_count) for s in STRATA}

    # base_idx[s] = Σ(strata_demand × price) per pop-unit per year at demand_scale=1
    base_idx = compute_base_demand_index(demand_matrix)

    # GDP per capita is static for this scenario (pop counts and tax don't change)
    gdp_per_cap = fn1_gdp_per_capita(p)

    # Initial state
    savings: Dict[str, float] = {s: p.strata[s].savings for s in STRATA}
    demand_scale = compute_demand_scale(p, savings=savings, gdp_per_cap=gdp_per_cap)
    savings_targets = compute_savings_targets(p)

    records = []
    total_months = p.sim_years * 12
    update_interval_months = p.update_interval_years * 12
    months_since_update = 0

    for month in range(total_months + 1):
        sp_pressure = fn3_savings_pressure(p, savings)
        nl          = fn2_gdp_nonlinear(gdp_per_cap)
        is_tick     = (months_since_update == 0 and month > 0)

        for s in STRATA:
            m_spend  = base_idx[s] * pop_counts[s] * demand_scale[s]
            net_flow = income[s] - m_spend
            records.append({
                "month":            month,
                "year":             month / 12.0,
                "strata":           s,
                "savings":          savings[s],
                "savings_target":   savings_targets[s],
                "savings_ratio":    savings[s] / max(1e-9, savings_targets[s]),
                "demand_scale":     demand_scale[s],
                "gdp_nonlinear":    nl[s],
                "savings_pressure": sp_pressure[s],
                "monthly_income":   income[s],
                "monthly_spending": m_spend,
                "net_flow":         net_flow,
                "update_tick":      is_tick,
            })

        if month == total_months:
            break

        # Apply monthly delta
        for s in STRATA:
            m_spend    = base_idx[s] * pop_counts[s] * demand_scale[s]
            savings[s] = max(0.0, savings[s] + income[s] - m_spend)

        # Update demand scale on pulse tick (with optional EMA smoothing)
        months_since_update += 1
        if months_since_update >= update_interval_months:
            months_since_update = 0
            computed = compute_demand_scale(p, savings=savings, gdp_per_cap=gdp_per_cap)
            α = p.ema_alpha
            demand_scale = {s: α * computed[s] + (1 - α) * demand_scale[s] for s in STRATA}

    return pd.DataFrame(records)


