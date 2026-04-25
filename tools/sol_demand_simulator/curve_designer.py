"""
EU5 SOL Demand Simulator — Substitute Group Curve Designer

Designs linear Engel curves per substitute group such that:
    Σ(demand × price) = income  (恒等于收入)

Core formula:
    d_g_s(y) = (α_g_s / P_g_s) × y   demand at income y for strata s
    spend_g_s(y) = α_g_s × y           spending at income y for strata s

    P_g_s = Σ_i∈g (base_demand_i_strata × price_i)   base price sum for (group, strata)
    Σ_g α_g_s = 1  for each strata s                   budget shares sum to 1 per strata
    Σ_g spend_g_s(y) = y                                satisfied by construction
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

REPO_ROOT    = Path(__file__).resolve().parent.parent.parent
ALPHA_TABLE  = REPO_ROOT / "data" / "alpha_table.csv"


# 11 substitute groups (10 from SOL_substitute_good_indicators.txt + household from SOL_substitute_effects.txt)
SUBSTITUTE_GROUPS: List[str] = [
    "alcohol", "textiles", "knowledge", "precious", "ritual",
    "stimulants", "spices", "staple", "protein", "military", "household",
]

# Group -> goods mapping
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
    "household":  ["lumber", "masonry", "tools", "pottery", "furniture", "porcelain", "lacquerware", "marble"],
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
    "household":  "#795548",
}

# Groups ranked by "luxury" level (higher = more elastic should be)
LUXURY_RANK: Dict[str, int] = {
    "staple":     1,   #必需品，弹性低
    "protein":    2,
    "household":  3,
    "alcohol":    4,
    "military":   5,
    "spices":     6,
    "stimulants": 7,
    "textiles":   8,
    "knowledge":  9,
    "ritual":     10,
    "precious":   11,  # 奢侈品，弹性高
}


@dataclass
class SubstituteGroup:
    """Demand curve model for one substitute group."""
    name: str
    goods: List[str]
    # Computed from demand_matrix at demand_scale=1
    base_price_sum: float = 0.0   # P_g = Σ(base_demand_i × price_i), average across strata
    # Engel curve parameter — kept for backward compat; represents nobles strata or global average
    budget_share: float = 0.0     # α_g (global / nobles fallback)
    # Per-strata price sums: P_g_s = Σ_i∈g (base_demand_i_strata × price_i)
    base_price_sum_per_strata: Dict[str, float] = field(default_factory=dict)
    # Per-strata budget shares: α_g_s — primary store (set by CurveDesignerState)
    budget_share_per_strata: Dict[str, float] = field(default_factory=dict)

    def _alpha_for(self, strata: str) -> float:
        """Return alpha for given strata, fallback to global budget_share."""
        return self.budget_share_per_strata.get(strata, self.budget_share)

    @property
    def slope(self) -> float:
        """Engel curve slope using global budget_share and average P_g."""
        if self.base_price_sum <= 0:
            return 0.0
        return self.budget_share / self.base_price_sum

    def slope_for_strata(self, strata: str) -> float:
        """Engel curve slope b_g_s = α_g_s / P_g_s."""
        P = self.base_price_sum_per_strata.get(strata, self.base_price_sum)
        if P <= 0:
            return 0.0
        return self._alpha_for(strata) / P

    @property
    def intercept(self) -> float:
        return 0.0

    def demand_at(self, income: float) -> float:
        return self.slope * income

    def demand_at_strata(self, strata: str, income: float) -> float:
        return self.slope_for_strata(strata) * income

    def spend_at(self, income: float) -> float:
        return self.budget_share * income

    def spend_at_strata(self, strata: str, income: float) -> float:
        return self._alpha_for(strata) * income


_STRATA_KEYS = ["nobles", "clergy", "burghers", "commoners", "tribesmen"]


@dataclass
class CurveDesignerState:
    """Complete state for the curve designer tab."""
    groups: Dict[str, SubstituteGroup] = field(default_factory=dict)
    # Per-strata alpha store: {strata: {group: alpha_g_s}} — primary source of truth
    budget_shares_per_strata: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def budget_shares(self) -> Dict[str, float]:
        """Backward-compat: return nobles strata shares (or global if no strata data)."""
        return self.budget_shares_per_strata.get("nobles", {g: g_obj.budget_share for g, g_obj in self.groups.items()})

    def get_strata_shares(self, strata: str) -> Dict[str, float]:
        """Return alpha values for a single strata."""
        return self.budget_shares_per_strata.get(strata, {g: self.groups[g].budget_share for g in self.groups})

    def set_strata_shares(self, strata: str, shares: Dict[str, float]) -> None:
        """Set alpha values for one strata and propagate to SubstituteGroup."""
        self.budget_shares_per_strata[strata] = shares.copy()
        for g_name, alpha in shares.items():
            if g_name in self.groups:
                self.groups[g_name].budget_share_per_strata[strata] = alpha
                # Keep global budget_share synced to nobles strata
                if strata == "nobles":
                    self.groups[g_name].budget_share = alpha

    def set_budget_shares_per_strata(self, all_shares: Dict[str, Dict[str, float]]) -> None:
        """Set alpha values for all strata at once."""
        for strata, shares in all_shares.items():
            self.set_strata_shares(strata, shares)

    def set_budget_shares(self, shares: Dict[str, float]) -> None:
        """Backward-compat: apply same shares to all strata."""
        for strata in _STRATA_KEYS:
            self.set_strata_shares(strata, shares)

    def apply_delta_with_locks(
        self,
        strata: str,
        changed_group: str,
        new_alpha: float,
        locked: Dict[str, bool],
        P_gs: Dict[str, float] | None = None,
    ) -> Dict[str, float]:
        """
        Apply a change to changed_group's alpha and redistribute the delta uniformly
        across all unlocked groups in b-space (b = alpha / P_g_s), so groups with
        higher price-sums absorb proportionally more of the compensating adjustment.

        P_gs: optional {group: P_g_s} override; falls back to self.groups if available,
              then to 1.0 (degenerates to equal-alpha redistribution).
        Locked groups keep their values exactly.
        Returns the updated shares dict for this strata.
        """
        def _p(g: str) -> float:
            if P_gs and g in P_gs:
                v = P_gs[g]
            elif self.groups.get(g):
                v = self.groups[g].base_price_sum_per_strata.get(strata, 1.0)
            else:
                v = 1.0
            return v if v > 0 else 1.0

        current = self.get_strata_shares(strata).copy()
        old_alpha = current.get(changed_group, 0.0)
        delta = new_alpha - old_alpha

        unlocked = [
            g for g in SUBSTITUTE_GROUPS
            if g != changed_group and not locked.get(g, False)
        ]
        locked_other = [
            g for g in SUBSTITUTE_GROUPS
            if g != changed_group and locked.get(g, False)
        ]

        current[changed_group] = new_alpha

        if unlocked and abs(delta) > 1e-9:
            P_sum = sum(_p(g) for g in unlocked)
            per_b = -delta / P_sum   # equal Δb per unlocked group; Σ Δalpha = -delta exactly
            for g in unlocked:
                current[g] = max(0.0, current.get(g, 0.0) + per_b * _p(g))

        # Renormalize only among changed+unlocked groups to fix float drift.
        # Locked groups are never touched.
        locked_sum = sum(current.get(g, 0.0) for g in locked_other)
        adjustable = [changed_group] + unlocked
        adj_total = sum(current.get(g, 0.0) for g in adjustable)
        target = max(0.0, 1.0 - locked_sum)
        if adj_total > 0 and abs(adj_total - target) > 1e-9:
            scale = target / adj_total
            for g in adjustable:
                current[g] = max(0.0, current[g] * scale)

        self.set_strata_shares(strata, current)
        return current

    def validate_constraint(self, income: float, strata: str | None = None) -> Dict[str, float]:
        shares = self.get_strata_shares(strata) if strata else self.budget_shares
        group_spends = {g: shares.get(g, 0.0) * income for g in self.groups}
        total_spend = sum(group_spends.values())
        return {
            "total_spend": total_spend,
            "total_income": income,
            "gap": total_spend - income,
            "group_spends": group_spends,
        }

    def auto_calibrate_budget_shares(self) -> Dict[str, Dict[str, float]]:
        """
        Per-strata auto-calibrate: α_g_s = P_g_s / Σ_h P_h_s.
        Returns {strata: {group: alpha}}.
        """
        result: Dict[str, Dict[str, float]] = {}
        for s in _STRATA_KEYS:
            total_P = sum(
                g_obj.base_price_sum_per_strata.get(s, g_obj.base_price_sum)
                for g_obj in self.groups.values()
            )
            if total_P <= 0:
                result[s] = {g: 1.0 / len(self.groups) for g in self.groups}
            else:
                result[s] = {
                    g: g_obj.base_price_sum_per_strata.get(s, g_obj.base_price_sum) / total_P
                    for g, g_obj in self.groups.items()
                }
        return result

    def compute_base_price_sums(self, demand_matrix: dict) -> None:
        """Compute P_g and P_g_s for each group from demand_matrix."""
        from parser import STRATA
        for g_name, group in self.groups.items():
            total = 0.0
            per_strata: Dict[str, float] = {}
            for good_name in group.goods:
                if good_name in demand_matrix:
                    entry = demand_matrix[good_name]
                    avg_demand = sum(entry.strata_demand.values()) / len(entry.strata_demand)
                    total += avg_demand * entry.price
                    for s in STRATA:
                        strata_demand = entry.strata_demand.get(s, 0.0)
                        per_strata[s] = per_strata.get(s, 0.0) + strata_demand * entry.price
            group.base_price_sum = total
            group.base_price_sum_per_strata = per_strata

    def load_from_alpha_table(self, path: Path = ALPHA_TABLE) -> bool:
        """Load per-strata alpha values from alpha_table.csv. Returns True on success."""
        if not path.exists():
            return False
        try:
            all_shares: Dict[str, Dict[str, float]] = {}
            with path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    strata = row["strata"]
                    all_shares[strata] = {
                        g: float(row[g]) for g in SUBSTITUTE_GROUPS if g in row
                    }
            self.set_budget_shares_per_strata(all_shares)
            return True
        except Exception:
            return False

    def save_to_alpha_table(self, path: Path = ALPHA_TABLE) -> None:
        """Write current per-strata alpha values to alpha_table.csv."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["strata"] + SUBSTITUTE_GROUPS
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for strata in _STRATA_KEYS:
                shares = self.get_strata_shares(strata)
                row: Dict = {"strata": strata}
                row.update({g: round(shares.get(g, 0.0), 6) for g in SUBSTITUTE_GROUPS})
                writer.writerow(row)

    def init_from_demand_matrix(self, demand_matrix: dict) -> None:
        """Initialize groups from demand_matrix, then load alpha from alpha_table.csv."""
        for g_name in SUBSTITUTE_GROUPS:
            self.groups[g_name] = SubstituteGroup(
                name=g_name,
                goods=GROUP_GOODS[g_name],
            )
        self.compute_base_price_sums(demand_matrix)
        # Try loading per-strata alpha from file; fall back to auto-calibration
        if not self.load_from_alpha_table():
            auto_shares = self.auto_calibrate_budget_shares()
            self.set_budget_shares_per_strata(auto_shares)


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