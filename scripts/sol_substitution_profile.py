"""Explicit target-local substitution configuration; never mutates default tables."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class SubstitutionProfile:
    name: str
    cache_schema: str
    goods: tuple[str, ...]
    groups: Mapping[str, tuple[str, ...]]
    subscriptions: Mapping[str, tuple[str, ...]]
    group_order: tuple[str, ...]
    historical_sizes: Mapping[str, int]
    hud_goods: tuple[str, ...]
    quantity_overrides: Mapping[str, Mapping[str, float]]

    def groups_for_pop(self, pop, removed_goods=()):
        removed = set(removed_goods)
        if removed - set(self.goods):
            raise ValueError(f"Unknown target-level removals: {sorted(removed - set(self.goods))}")
        return {group: [good for good in self.groups[group] if good not in removed]
                for group in self.subscriptions[pop]}


def load_jtg_profile() -> SubstitutionProfile:
    raw = json.loads((Path(__file__).resolve().parent.parent / "data/jtg_substitution.json").read_text(encoding="utf-8"))
    groups = {g: tuple(members) for g, members in raw["groups"].items()}
    goods = tuple(raw["goods"])
    if len(goods) != 86 or len(set(goods)) != 86 or set(goods) != {g for members in groups.values() for g in members}:
        raise ValueError("JTG profile must contain exactly 86 unique grouped goods")
    if len(groups) != 20 or set(raw["group_order"]) != set(groups) or set(raw["historical_sizes"]) != set(groups):
        raise ValueError("JTG profile requires the existing twenty groups, sizes and ordering")
    if set(raw["hud_goods"]) != set(goods) or len(raw["hud_goods"]) != len(goods):
        raise ValueError("JTG HUD order must contain each active good once")
    from gen_whole_group_baskets import GROUPS, SUBSCRIBED, CORE
    from sol_goods_order import GROUP_ORDER, PRIMARY_GROUP
    base_sizes = json.loads((Path(__file__).resolve().parent.parent / "data/substitute_groups.json").read_text(encoding="utf-8"))["historical_sizes"]
    if set(groups) != set(GROUPS) or any([g for g in members if g in CORE] != GROUPS[name] for name, members in groups.items()):
        raise ValueError("JTG profile base memberships drifted from goods_weights.csv")
    if raw["subscriptions"] != SUBSCRIBED or raw["historical_sizes"] != base_sizes or raw["group_order"] != GROUP_ORDER:
        raise ValueError("JTG profile must preserve base subscriptions, historical N and group order")
    if [g for g in raw["hud_goods"] if g in CORE] != list(PRIMARY_GROUP):
        raise ValueError("JTG HUD must preserve base priority order")
    return SubstitutionProfile(raw["name"], raw["cache_schema"], goods, MappingProxyType(groups),
        MappingProxyType({p: tuple(gs) for p, gs in raw["subscriptions"].items()}),
        tuple(raw["group_order"]), MappingProxyType(raw["historical_sizes"]),
        tuple(raw["hud_goods"]), MappingProxyType({g: MappingProxyType(q) for g, q in raw["quantity_overrides"].items()}))
