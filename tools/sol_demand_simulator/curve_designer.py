"""
EU5 SOL Demand Simulator — Substitute Group Curve Designer

Designs linear Engel curves per substitute group such that:
    Σ(demand × price) = income  (恒等于收入)

Core formula:
    d_g(y) = (α_g / P_g) × y       demand at income y
    spend_g(y) = α_g × y            spending at income y

    P_g = Σ_i∈g (base_demand_i × price_i)   base price sum for group g
    Σ_g α_g = 1                                 budget shares sum to 1
    Σ_g spend_g(y) = y                          satisfied by construction
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


# 10 substitute groups (from SOL_substitute_good_indicators.txt)
SUBSTITUTE_GROUPS: List[str] = [
    "alcohol", "textiles", "knowledge", "precious", "ritual",
    "stimulants", "spices", "staple", "protein", "military",
]

# Group -> goods mapping (from SOL_substitute_good_indicators.txt)
GROUP_GOODS: Dict[str, List[str]] = {
    "alcohol":    ["wine", "liquor", "beer"],
    "textiles":   ["fur", "cloth", "fine_cloth", "jewelry"],
    "knowledge":  ["beeswax", "paper", "books"],
    "precious":   ["goods_gold", "silver", "pearls", "amber", "gems", "ivory"],
    "ritual":     ["incense", "medicaments", "mercury"],
    "stimulants": ["sugar", "tobacco", "tea", "cocoa", "coffee"],
    "spices":     ["saffron", "pepper", "cloves", "chili"],
    "staple":     ["wheat", "rice", "millet", "maize", "potato", "legumes", "olives", "fruit"],
    "protein":    ["fish", "wild_game", "livestock"],
    "military":   ["horses", "elephants", "weaponry", "firearms", "coal", "salt", "victuals"],
}

GROUP_COLORS: Dict[str, str] = {
    "alcohol":    "#e74c3c",
    "textiles":   "#9b59b6",
    "knowledge":  "#3498db",
    "precious":   "#f39c12",
    "ritual":     "#e67e22",
    "stimulants": "#1abc9c",
    "spices":     "#c0392b",
    "staple":     "#27ae60",
    "protein":    "#2980b9",
    "military":   "#7f8c8d",
}

# Groups ranked by "luxury" level (higher = more elastic should be)
LUXURY_RANK: Dict[str, int] = {
    "staple":     1,   #必需品，弹性低
    "protein":    2,
    "alcohol":    3,
    "military":   4,
    "spices":     5,
    "stimulants": 6,
    "textiles":   7,
    "knowledge":  8,
    "ritual":     9,
    "precious":   10,  # 奢侈品，弹性高
}


@dataclass
class SubstituteGroup:
    """Demand curve model for one substitute group."""
    name: str
    goods: List[str]
    # Computed from demand_matrix at demand_scale=1
    base_price_sum: float = 0.0   # P_g = Σ(base_demand_i × price_i), average across strata
    # Engel curve parameter (designer input)
    budget_share: float = 0.0     # α_g, fraction of income (0.0–1.0)
    # Per-strata base price sums: P_g[s] = Σ_i∈g (base_demand_i_strata × price_i)
    base_price_sum_per_strata: Dict[str, float] = field(default_factory=dict)

    @property
    def slope(self) -> float:
        """Engel curve slope: b_g = α_g / P_g (average across strata)"""
        if self.base_price_sum <= 0:
            return 0.0
        return self.budget_share / self.base_price_sum

    def slope_for_strata(self, strata: str) -> float:
        """Engel curve slope for a specific strata."""
        P = self.base_price_sum_per_strata.get(strata, 0.0)
        if P <= 0:
            return 0.0
        return self.budget_share / P

    @property
    def intercept(self) -> float:
        """Linear curve intercept (always 0 for Engel curve — demand = 0 when income = 0)."""
        return 0.0

    def demand_at(self, income: float) -> float:
        """Compute group demand at given income level (average across strata)."""
        return self.slope * income

    def demand_at_strata(self, strata: str, income: float) -> float:
        """Compute group demand at given income level for a specific strata."""
        return self.slope_for_strata(strata) * income

    def spend_at(self, income: float) -> float:
        """Compute group spending at given income level."""
        return self.budget_share * income


@dataclass
class CurveDesignerState:
    """Complete state for the curve designer tab."""
    groups: Dict[str, SubstituteGroup] = field(default_factory=dict)
    # Designer budget shares (sum should = 1.0)
    budget_shares: Dict[str, float] = field(default_factory=dict)

    def compute_base_price_sums(self, demand_matrix: dict) -> None:
        """Compute P_g for each group from demand_matrix.

        P_g = Σ_i∈g (avg_demand_i × price_i)
        where avg_demand_i = mean across all strata of the strata_demand.

        Also computes P_g[s] = Σ_i∈g (demand_i_strata × price_i) per strata.
        """
        from parser import STRATA
        for g_name, group in self.groups.items():
            total = 0.0
            per_strata: Dict[str, float] = {}
            for good_name in group.goods:
                if good_name in demand_matrix:
                    entry = demand_matrix[good_name]
                    # Average across strata for aggregate P_g
                    avg_demand = sum(entry.strata_demand.values()) / len(entry.strata_demand)
                    total += avg_demand * entry.price
                    # Per-strata P_g[s]
                    for s in STRATA:
                        strata_demand = entry.strata_demand.get(s, 0.0)
                        per_strata[s] = per_strata.get(s, 0.0) + strata_demand * entry.price
            group.base_price_sum = total
            group.base_price_sum_per_strata = per_strata

    def set_budget_shares(self, shares: Dict[str, float]) -> None:
        """Set budget shares and propagate to groups."""
        self.budget_shares = shares.copy()
        for g_name, share in shares.items():
            if g_name in self.groups:
                self.groups[g_name].budget_share = share

    def validate_constraint(self, income: float, strata: str | None = None) -> Dict[str, float]:
        """
        Validate that Σ(demand × price) = income.

        If strata is None, uses aggregate P_g (average across strata).
        If strata is specified, uses per-strata P_g.
        """
        if strata is None:
            group_spends = {g: g_obj.spend_at(income) for g, g_obj in self.groups.items()}
            total_spend = sum(group_spends.values())
        else:
            group_spends = {g: g_obj.budget_share * income for g, g_obj in self.groups.items()}
            total_spend = sum(group_spends.values())
        return {
            "total_spend": total_spend,
            "total_income": income,
            "gap": total_spend - income,
            "group_spends": group_spends,
        }

    def auto_calibrate_budget_shares(self) -> Dict[str, float]:
        """
        Auto-calibrate budget shares proportional to base_price_sum.
        α_g = P_g / Σ_h P_h
        """
        total_P = sum(g.base_price_sum for g in self.groups.values())
        if total_P <= 0:
            return {g: 1.0 / len(self.groups) for g in self.groups}
        return {g.name: g.base_price_sum / total_P for g in self.groups.values()}

    def init_from_demand_matrix(self, demand_matrix: dict) -> None:
        """Initialize groups from demand_matrix."""
        for g_name in SUBSTITUTE_GROUPS:
            self.groups[g_name] = SubstituteGroup(
                name=g_name,
                goods=GROUP_GOODS[g_name],
            )
        self.compute_base_price_sums(demand_matrix)
        auto_shares = self.auto_calibrate_budget_shares()
        self.set_budget_shares(auto_shares)


# ---------------------------------------------------------------------------
# Key Functions
# ---------------------------------------------------------------------------

def compute_demand_curve(
    income: float,
    budget_shares: Dict[str, float],
    base_price_sums: Dict[str, float],
) -> Dict[str, float]:
    """
    Compute per-group demand given income and budget shares (aggregate).

    d_g(income) = (budget_share_g / base_price_sum_g) × income

    Returns dict {group_name: demand}.
    """
    result = {}
    for g, share in budget_shares.items():
        P_g = base_price_sums.get(g, 0.0)
        if P_g > 0:
            result[g] = (share / P_g) * income
        else:
            result[g] = 0.0
    return result


def compute_demand_curve_per_strata(
    strata: str,
    income: float,
    budget_shares: Dict[str, float],
    base_price_sums_per_strata: Dict[str, Dict[str, float]],
) -> Dict[str, float]:
    """
    Compute per-group demand for a specific strata.

    d_g_s(income) = (budget_share_g / P_g_s) × income

    Args:
        strata: the strata name (nobles, clergy, etc.)
        income: income level
        budget_shares: {group_name: share}
        base_price_sums_per_strata: {group_name: {strata: P_g_s}}

    Returns dict {group_name: demand}.
    """
    result = {}
    for g, share in budget_shares.items():
        P_g_s = base_price_sums_per_strata.get(g, {}).get(strata, 0.0)
        if P_g_s > 0:
            result[g] = (share / P_g_s) * income
        else:
            result[g] = 0.0
    return result


def compute_equilibrium_spend(
    income: float,
    budget_shares: Dict[str, float],
) -> Dict[str, float]:
    """
    Compute equilibrium spending per group.
    spend_g = budget_share_g × income
    """
    return {g: share * income for g, share in budget_shares.items()}


def validate_budget_constraint(
    budget_shares: Dict[str, float],
) -> tuple[bool, float, float]:
    """
    Validate that Σ(budget_shares) = 1.

    Returns (is_valid, sum_shares, gap).
    """
    total = sum(budget_shares.values())
    is_valid = abs(total - 1.0) < 1e-9
    gap = total - 1.0
    return is_valid, total, gap


def suggest_budget_correction(
    current_shares: Dict[str, float],
) -> Dict[str, float]:
    """
    Suggest corrections to budget shares so they sum to 1.
    Proportional adjustment: new_share = share / Σshares × 1.0
    """
    total = sum(current_shares.values())
    if total <= 0:
        return {g: 1.0 / len(current_shares) for g in current_shares}
    return {g: share / total for g, share in current_shares.items()}


def compute_engel_curve_points(
    income_range: np.ndarray,
    budget_shares: Dict[str, float],
    base_price_sums: Dict[str, float],
) -> Dict[str, np.ndarray]:
    """
    Compute Engel curve (demand vs income) for each group over income_range (aggregate).

    Returns dict {group_name: demand_array}.
    """
    results = {}
    for g, share in budget_shares.items():
        P_g = base_price_sums.get(g, 0.0)
        if P_g > 0:
            results[g] = (share / P_g) * income_range
        else:
            results[g] = np.zeros_like(income_range)
    return results


def compute_engel_curve_points_per_strata(
    strata: str,
    income_range: np.ndarray,
    budget_shares: Dict[str, float],
    base_price_sums_per_strata: Dict[str, Dict[str, float]],
) -> Dict[str, np.ndarray]:
    """
    Compute Engel curve (demand vs income) for each group for a specific strata.

    Returns dict {group_name: demand_array}.
    """
    results = {}
    for g, share in budget_shares.items():
        P_g_s = base_price_sums_per_strata.get(g, {}).get(strata, 0.0)
        if P_g_s > 0:
            results[g] = (share / P_g_s) * income_range
        else:
            results[g] = np.zeros_like(income_range)
    return results


def compute_spend_curve_points(
    income_range: np.ndarray,
    budget_shares: Dict[str, float],
) -> Dict[str, np.ndarray]:
    """
    Compute spend curve (spending vs income) for each group over income_range.

    Returns dict {group_name: spend_array}.
    """
    return {g: share * income_range for g, share in budget_shares.items()}


def compute_total_spend_curve(
    income_range: np.ndarray,
    budget_shares: Dict[str, float],
) -> np.ndarray:
    """
    Compute total spending across all groups for each income level.
    Σ_g (α_g × income) = (Σ_g α_g) × income = income (when Σα_g = 1)
    """
    return sum(share * income_range for share in budget_shares.values())


def luxury_sorted_groups() -> List[str]:
    """Return substitute groups sorted by luxury rank (low to high)."""
    return sorted(SUBSTITUTE_GROUPS, key=lambda g: LUXURY_RANK.get(g, 5))


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick sanity check
    shares = {g: 0.1 for g in SUBSTITUTE_GROUPS}
    is_valid, total, gap = validate_budget_constraint(shares)
    print(f"Budget shares sum to {total:.4f}, valid={is_valid}, gap={gap:.6f}")

    # Test Engel curve computation
    income_range = np.linspace(0, 20, 100)
    P_g = 1.0  # placeholder
    engel = compute_engel_curve_points(income_range, shares, {g: 1.0 for g in SUBSTITUTE_GROUPS})
    total_demand = sum(engel.values())
    print(f"Total demand at income=10: {np.interp(10, income_range, total_demand):.4f}")
    print("Expected total demand ≈ income / avg_P = 10 / 1.0 = 10 (since all P_g=1)")