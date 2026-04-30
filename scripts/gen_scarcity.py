#!/usr/bin/env python3
"""
gen_scarcity.py — regenerate all scarcity-tier files (3 shortage + 3 surplus tiers).

6 tiers:
  -3 (Very Cheap): price < 0.40×, weight ×2.00
  -2 (Cheap):      price < 0.65×, weight ×1.50
  -1 (Affordable): price < 0.85×, weight ×1.25
   0 (Normal):     0.85×–1.30×, weight ×1.00  (no list)
  +1 (Mild):       price > 1.30×, weight ×0.75
  +2 (Moderate):   price > 1.70×, weight ×0.50
  +3 (Severe):     price > 2.30×, weight ×0.25

Generates / rewrites:
  effects    → SOL_substitute_effects.txt       (full regen, header preserved)
  indicators → SOL_substitute_good_indicators.txt (full regen, header preserved)
  weights    → SOL_goods_weight_values.txt       (Part 1 string-replace per good)
  loc        → SOL_substitute_goods_l_english.yml (key upsert)

Usage:
    conda run -n eu5 python scripts/gen_scarcity.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).parent.parent

# ── Tier data ────────────────────────────────────────────────────────────────────────────────

# Shortage tiers: (list_suffix, threshold_multiplier, weight_mult, desc_key)
# Ordered most extreme first (used for if/else_if chain, and for removal)
SHORTAGE_TIERS: List[Tuple[str, float, float, str]] = [
    ("severe",    2.30, 0.25, "SOL_WEIGHT_SCARCE_3"),
    ("moderate",  1.70, 0.50, "SOL_WEIGHT_SCARCE_2"),
    ("mild",      1.30, 0.75, "SOL_WEIGHT_SCARCE_1"),
]

# Surplus tiers: (list_suffix, threshold_multiplier, weight_mult, desc_key)
# Ordered most extreme first (used for if/else_if chain after shortage tiers, and for removal)
SURPLUS_TIERS: List[Tuple[str, float, float, str]] = [
    ("vcheap",    0.40, 2.00, "SOL_WEIGHT_CHEAP_3"),
    ("cheap",     0.65, 1.50, "SOL_WEIGHT_CHEAP_2"),
    ("affordable",0.85, 1.25, "SOL_WEIGHT_CHEAP_1"),
]

ALL_TIER_SUFFIXES = [t[0] for t in SHORTAGE_TIERS + SURPLUS_TIERS]

# ── Indicator groups ─────────────────────────────────────────────────────────────────────────

# Groups that define the demand_share denominator (sol_<grp>_base_total_weight).
# Multi-group demand goods are mapped to their primary indicator group.
# victuals: requires sol_pp_victuals_compat_is_on check throughout.
INDICATOR_GROUPS: List[Tuple[str, List[str]]] = [
    ("alcohol",     ["wine", "liquor", "beer"]),
    ("textiles",    ["fur", "cloth", "fine_cloth", "leather"]),
    ("knowledge",   ["beeswax", "paper", "books"]),
    ("precious",    ["goods_gold", "silver", "jewelry"]),
    ("treasures",   ["amber", "gems", "ivory", "pearls"]),
    ("ritual",      ["incense", "medicaments", "mercury"]),
    ("stimulants",  ["sugar", "tobacco", "tea", "cocoa", "coffee"]),
    ("spices",      ["saffron", "pepper", "cloves", "chili"]),
    ("staple",      ["wheat", "rice", "millet", "maize", "potato", "legumes", "olives", "fruit"]),
    ("protein",     ["fish", "wild_game", "livestock"]),
    ("military",    ["horses", "elephants", "weaponry", "firearms", "coal", "salt", "victuals"]),
    ("household",   ["lumber", "masonry", "tools", "pottery", "furniture",
                     "porcelain", "lacquerware", "marble", "glass"]),
]

# Goods requiring compat-flag checks (sol_pp_victuals_compat_is_on = yes)
COMPAT_GOODS = frozenset(["victuals"])

GOOD_TO_IND_GROUP = {g: grp for grp, goods in INDICATOR_GROUPS for g in goods}
ALL_GOODS = [g for _, goods in INDICATOR_GROUPS for g in goods]

# ── Good-group tooltip: display names and group names ──────────────────────────────────────────

GOOD_NAMES_ZH: dict = {
    "wine": "葡萄酒", "liquor": "烈酒", "beer": "啤酒",
    "fur": "毛皮", "cloth": "布匹", "fine_cloth": "精纺品", "leather": "皮革",
    "beeswax": "蜂蜡", "paper": "纸张", "books": "书籍",
    "goods_gold": "黄金", "silver": "白银", "jewelry": "珠宝",
    "amber": "琥珀", "gems": "宝石", "ivory": "象牙", "pearls": "珍珠",
    "incense": "熏香", "medicaments": "草药", "mercury": "汞",
    "sugar": "糖", "tobacco": "烟草", "tea": "茶叶", "cocoa": "可可", "coffee": "咖啡",
    "saffron": "藏红花", "pepper": "胡椒", "cloves": "丁香", "chili": "辣椒",
    "wheat": "小麦", "rice": "大米", "millet": "杂谷", "maize": "玉米",
    "potato": "土豆", "legumes": "豆类", "olives": "橄榄", "fruit": "水果",
    "fish": "鱼类", "wild_game": "野味", "livestock": "牲畜",
    "horses": "马匹", "elephants": "大象", "weaponry": "武器", "firearms": "火器",
    "coal": "煤炭", "salt": "盐", "victuals": "口粮",
    "lumber": "木材", "masonry": "砖石", "tools": "工具", "pottery": "陶器",
    "furniture": "家具", "porcelain": "瓷器", "lacquerware": "漆器",
    "marble": "大理石", "glass": "玻璃",
}

GOOD_NAMES_EN: dict = {
    "wine": "Wine", "liquor": "Liquor", "beer": "Beer",
    "fur": "Fur", "cloth": "Cloth", "fine_cloth": "Fine Cloth", "leather": "Leather",
    "beeswax": "Beeswax", "paper": "Paper", "books": "Books",
    "goods_gold": "Gold", "silver": "Silver", "jewelry": "Jewelry",
    "amber": "Amber", "gems": "Gems", "ivory": "Ivory", "pearls": "Pearls",
    "incense": "Incense", "medicaments": "Medicaments", "mercury": "Mercury",
    "sugar": "Sugar", "tobacco": "Tobacco", "tea": "Tea", "cocoa": "Cocoa", "coffee": "Coffee",
    "saffron": "Saffron", "pepper": "Pepper", "cloves": "Cloves", "chili": "Chili",
    "wheat": "Wheat", "rice": "Rice", "millet": "Millet", "maize": "Maize",
    "potato": "Potato", "legumes": "Legumes", "olives": "Olives", "fruit": "Fruit",
    "fish": "Fish", "wild_game": "Wild Game", "livestock": "Livestock",
    "horses": "Horses", "elephants": "Elephants", "weaponry": "Weaponry", "firearms": "Firearms",
    "coal": "Coal", "salt": "Salt", "victuals": "Victuals",
    "lumber": "Lumber", "masonry": "Masonry", "tools": "Tools", "pottery": "Pottery",
    "furniture": "Furniture", "porcelain": "Porcelain", "lacquerware": "Lacquerware",
    "marble": "Marble", "glass": "Glass",
}

GROUP_NAMES_ZH: dict = {
    "alcohol":    "酒类",
    "textiles":   "纺织品",
    "knowledge":  "知识用品",
    "precious":   "贵重品",
    "treasures":  "珍宝",
    "ritual":     "祭祀物品",
    "stimulants": "嗜好品",
    "spices":     "香料",
    "staple":     "主食",
    "protein":    "蛋白食物",
    "military":   "军需品",
    "household":  "家居用品",
}

GROUP_NAMES_EN: dict = {
    "alcohol":    "Alcoholic Drinks",
    "textiles":   "Textiles",
    "knowledge":  "Knowledge Goods",
    "precious":   "Precious Goods",
    "treasures":  "Treasures",
    "ritual":     "Ritual Goods",
    "stimulants": "Stimulants",
    "spices":     "Spices",
    "staple":     "Staple Food",
    "protein":    "Protein Food",
    "military":   "Military Goods",
    "household":  "Household Goods",
}

# ── File paths ──────────────────────────────────────────────────────────────────────────────

EFFECTS_FILE          = ROOT / "src/stable/in_game/common/scripted_effects/SOL_substitute_effects.txt"
WEIGHTS_FILE          = ROOT / "src/stable/in_game/common/script_values/SOL_goods_weight_values.txt"
INDICATORS_FILE       = ROOT / "src/stable/in_game/common/script_values/SOL_substitute_good_indicators.txt"
GROUP_INDICATORS_FILE = ROOT / "src/stable/in_game/common/script_values/SOL_substitute_group_indicators.txt"
LOCALIZATION_FILE     = ROOT / "src/stable/main_menu/localization/english/SOL_substitute_goods_l_english.yml"
LOCALIZATION_FILE_ZH  = ROOT / "src/stable/main_menu/localization/simp_chinese/SOL_substitute_goods_l_simp_chinese.yml"
GOODS_DIR             = ROOT / "reference_game_files/game/in_game/common/goods"
GUI_OVERRIDE_FILE     = ROOT / "src/stable/in_game/gui/z_SOL_goods_tooltip_override.gui"

# ── Effects file generator ─────────────────────────────────────────────────────────────────────────

EFFECTS_HEADER = """\
### ============================================================
### SECTION: Substitute Goods Scarcity Cache
### ============================================================
# Computes per-market scarcity tier for all pop-demand substitute goods.
#
# 6 tiers (3 shortage + 3 surplus):
#   Severe     (> 2.30× default): weight ×0.25   list: SOL_<good>_severe_markets
#   Moderate   (> 1.70× default): weight ×0.50   list: SOL_<good>_moderate_markets
#   Mild       (> 1.30× default): weight ×0.75   list: SOL_<good>_mild_markets
#   Normal     (0.85×–1.30×):      weight ×1.00   (no list)
#   Affordable (< 0.85× default): weight ×1.25   list: SOL_<good>_affordable_markets
#   Cheap      (< 0.65× default): weight ×1.50   list: SOL_<good>_cheap_markets
#   Very Cheap (< 0.40× default): weight ×2.00   list: SOL_<good>_vcheap_markets
#
# Each market belongs to at most one tier list per good.
# No hysteresis — yearly update rate damps oscillation adequately.
#
# Storage: 6 global variable lists per good (54 goods × 6 = 324 lists).
# Pop demand checks: location.market ?= { is_target_in_global_variable_list = { ... } }
#
# AUTO-GENERATED by scripts/gen_scarcity.py — do not edit by hand.
"""


def _good_list_name(good: str, tier_suffix: str) -> str:
    return f"SOL_{good}_{tier_suffix}_markets"


def _gen_good_effects(good: str) -> str:
    """Generate the per-market tier assignment block for one good."""
    lines: List[str] = []
    is_compat = good in COMPAT_GOODS
    indent = "        "  # 8 spaces (inside every_market_in_world)

    lines.append(f"{indent}# {good}")

    # Step 1: Remove from all tier lists
    for suffix in ALL_TIER_SUFFIXES:
        lst = _good_list_name(good, suffix)
        if is_compat:
            lines += [
                f"{indent}if = {{",
                f"{indent}    limit = {{",
                f"{indent}        sol_pp_victuals_compat_is_on = yes",
                f"{indent}        has_global_variable_list = {lst}",
                f"{indent}        is_target_in_global_variable_list = {{ name = {lst} target = this }}",
                f"{indent}    }}",
                f"{indent}    remove_list_global_variable = {{ name = {lst} target = this }}",
                f"{indent}}}",
            ]
        else:
            lines += [
                f"{indent}if = {{",
                f"{indent}    limit = {{",
                f"{indent}        has_global_variable_list = {lst}",
                f"{indent}        is_target_in_global_variable_list = {{ name = {lst} target = this }}",
                f"{indent}    }}",
                f"{indent}    remove_list_global_variable = {{ name = {lst} target = this }}",
                f"{indent}}}",
            ]

    # Step 2: Add to correct tier via if/else_if chain
    first = True
    for suffix, threshold, _weight, _desc in SHORTAGE_TIERS:
        lst = _good_list_name(good, suffix)
        kw = "if" if first else "else_if"
        first = False
        price_cmp = f'"market_price(goods:{good})"'
        def_price = f'"default_price(goods:{good})"'
        if is_compat:
            lines += [
                f"{indent}{kw} = {{",
                f"{indent}    limit = {{",
                f"{indent}        sol_pp_victuals_compat_is_on = yes",
                f"{indent}        {price_cmp} > {{",
                f"{indent}            value = {def_price}",
                f"{indent}            multiply = {threshold}",
                f"{indent}        }}",
                f"{indent}    }}",
                f"{indent}    add_to_global_variable_list = {{ name = {lst} target = this }}",
                f"{indent}}}",
            ]
        else:
            lines += [
                f"{indent}{kw} = {{",
                f"{indent}    limit = {{",
                f"{indent}        {price_cmp} > {{",
                f"{indent}            value = {def_price}",
                f"{indent}            multiply = {threshold}",
                f"{indent}        }}",
                f"{indent}    }}",
                f"{indent}    add_to_global_variable_list = {{ name = {lst} target = this }}",
                f"{indent}}}",
            ]

    for suffix, threshold, _weight, _desc in SURPLUS_TIERS:
        lst = _good_list_name(good, suffix)
        price_cmp = f'"market_price(goods:{good})"'
        def_price = f'"default_price(goods:{good})"'
        if is_compat:
            lines += [
                f"{indent}else_if = {{",
                f"{indent}    limit = {{",
                f"{indent}        sol_pp_victuals_compat_is_on = yes",
                f"{indent}        {price_cmp} < {{",
                f"{indent}            value = {def_price}",
                f"{indent}            multiply = {threshold}",
                f"{indent}        }}",
                f"{indent}    }}",
                f"{indent}    add_to_global_variable_list = {{ name = {lst} target = this }}",
                f"{indent}}}",
            ]
        else:
            lines += [
                f"{indent}else_if = {{",
                f"{indent}    limit = {{",
                f"{indent}        {price_cmp} < {{",
                f"{indent}            value = {def_price}",
                f"{indent}            multiply = {threshold}",
                f"{indent}        }}",
                f"{indent}    }}",
                f"{indent}    add_to_global_variable_list = {{ name = {lst} target = this }}",
                f"{indent}}}",
            ]

    return "\n".join(lines)


def gen_effects_file() -> str:
    body_lines: List[str] = []
    prev_grp = None
    for grp, goods in INDICATOR_GROUPS:
        if grp != prev_grp:
            body_lines.append(f"        # === Group: {grp} ===")
            prev_grp = grp
        for good in goods:
            body_lines.append(_gen_good_effects(good))
            body_lines.append("")

    body = "\n".join(body_lines)
    return (
        EFFECTS_HEADER
        + "\nSOL_update_substitute_scarcity = {\n"
        + "    every_market_in_world = {\n"
        + body
        + "    }\n"
        + "}\n"
    )


# ── Weights file patcher ─────────────────────────────────────────────────────────────────────────

def _new_weight_part1(good: str) -> str:
    """Return the replacement Part 1 substitution block (tab-indented, no trailing newline)."""
    lines: List[str] = ["\t# Part 1 — Substitution"]
    first = True
    # Shortage tiers (reduce weight)
    for suffix, _threshold, weight, desc in SHORTAGE_TIERS:
        lst = _good_list_name(good, suffix)
        kw = "if" if first else "else_if"
        first = False
        lines += [
            f"\t{kw} = {{",
            f"\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }} }}",
            f'\t\tmultiply = {{ value = {weight} desc = "{desc}" }}',
            f"\t}}",
        ]
    # Surplus tiers (increase weight)
    for suffix, _threshold, weight, desc in SURPLUS_TIERS:
        lst = _good_list_name(good, suffix)
        lines += [
            f"\telse_if = {{",
            f"\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }} }}",
            f'\t\tmultiply = {{ value = {weight} desc = "{desc}" }}',
            f"\t}}",
        ]
    return "\n".join(lines)


def _new_weight_part1_compat(good: str) -> str:
    """Return the replacement Part 1 block for compat goods (double-tab indented)."""
    lines: List[str] = [f"\t\t# Part 1 — Substitution (only meaningful when compat is on)"]
    first = True
    for suffix, _threshold, weight, desc in SHORTAGE_TIERS:
        lst = _good_list_name(good, suffix)
        kw = "if" if first else "else_if"
        first = False
        lines += [
            f"\t\t{kw} = {{",
            f"\t\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }} }}",
            f'\t\t\tmultiply = {{ value = {weight} desc = "{desc}" }}',
            f"\t\t}}",
        ]
    for suffix, _threshold, weight, desc in SURPLUS_TIERS:
        lst = _good_list_name(good, suffix)
        lines += [
            f"\t\telse_if = {{",
            f"\t\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }} }}",
            f'\t\t\tmultiply = {{ value = {weight} desc = "{desc}" }}',
            f"\t\t}}",
        ]
    return "\n".join(lines)


def patch_weights_file(text: str) -> str:
    """String-replace the Part 1 block for every good in the weights file."""
    for good in ALL_GOODS:
        if good in COMPAT_GOODS:
            # victuals: Part 1 sits at double-tab depth inside the compat if block
            old = (
                f"\t\t# Part 1 — Substitution (only meaningful when compat is on)\n"
                f"\t\tif = {{\n"
                f"\t\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = SOL_{good}_scarce_markets target = this }} }} }}\n"
                f'\t\t\tmultiply = {{ value = 0.5 desc = "SOL_WEIGHT_SCARCE" }}\n'
                f"\t\t}}\n"
            )
            new = _new_weight_part1_compat(good) + "\n"
        else:
            old = (
                f"\t# Part 1 — Substitution\n"
                f"\tif = {{\n"
                f"\t\tlimit = {{ location.market ?= {{ is_target_in_global_variable_list = {{ name = SOL_{good}_scarce_markets target = this }} }} }}\n"
                f'\t\tmultiply = {{ value = 0.5 desc = "SOL_WEIGHT_SCARCE" }}\n'
                f"\t}}\n"
            )
            new = _new_weight_part1(good) + "\n"
        if old not in text:
            # Expected on re-runs: file already has the 6-tier pattern
            already_updated = f"SOL_{good}_severe_markets" in text
            if not already_updated:
                print(f"WARNING: Part 1 block not found for good '{good}' in weights file", file=sys.stderr)
            continue
        text = text.replace(old, new)
    return text


# ── Indicators file generator ────────────────────────────────────────────────────────────────────

INDICATORS_HEADER = """\
### ============================================================
### SECTION: Per-Good Scarcity Tier Indicators (GUI tooltip helpers)
### ============================================================
# Per good, this file emits five script values (all evaluated at location scope
# via Location.MakeScope.ScriptValue):
#
#   sol_good_<good>_scarcity_tier  — int 0–3: 0=normal, 1=mild, 2=moderate, 3=severe
#   sol_good_<good>_surplus_tier   — int 0–3: 0=normal, 1=affordable, 2=cheap, 3=very cheap
#   sol_good_<good>_scarce         — binary 1 if any scarcity tier (backward compat)
#   sol_weight_indicator_<good>    — float 0.25–2.00 (effective weight for display)
#   sol_demand_share_<good>        — float 0–100 (% share within indicator group)
#
# Per indicator group, one sol_<grp>_base_total_weight value is emitted.
#
# AUTO-GENERATED by scripts/gen_scarcity.py — do not edit by hand.
"""


def _list_check(good: str, suffix: str, scope_prefix: str = "market") -> str:
    """Return inline EU5 trigger: <scope> ?= { is_target_in_global_variable_list ... }"""
    lst = _good_list_name(good, suffix)
    return f"{scope_prefix} ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }}"


def _gen_good_indicators(good: str) -> List[str]:
    is_compat = good in COMPAT_GOODS
    ind_grp = GOOD_TO_IND_GROUP[good]
    lines: List[str] = []

    # — scarcity_tier (0-3) —
    lines.append(f"sol_good_{good}_scarcity_tier = {{")
    lines.append(f"    value = 0")
    for i, (suffix, _t, _w, _d) in enumerate(SHORTAGE_TIERS):
        kw = "if" if i == 0 else "else_if"
        if is_compat:
            lines += [
                f"    {kw} = {{ limit = {{ sol_pp_victuals_compat_is_on = yes {_list_check(good, suffix)} }} value = {3 - i} }}",
            ]
        else:
            lines.append(f"    {kw} = {{ limit = {{ {_list_check(good, suffix)} }} value = {3 - i} }}")
    lines.append("}")

    # — surplus_tier (0-3) —
    lines.append(f"sol_good_{good}_surplus_tier = {{")
    lines.append(f"    value = 0")
    for i, (suffix, _t, _w, _d) in enumerate(SURPLUS_TIERS):
        kw = "if" if i == 0 else "else_if"
        if is_compat:
            lines += [
                f"    {kw} = {{ limit = {{ sol_pp_victuals_compat_is_on = yes {_list_check(good, suffix)} }} value = {3 - i} }}",
            ]
        else:
            lines.append(f"    {kw} = {{ limit = {{ {_list_check(good, suffix)} }} value = {3 - i} }}")
    lines.append("}")

    # — backward-compat binary scarce flag —
    lines.append(f"sol_good_{good}_scarce = {{")
    lines.append(f"    value = 0")
    for i, (suffix, _t, _w, _d) in enumerate(SHORTAGE_TIERS):
        kw = "if" if i == 0 else "else_if"
        if is_compat:
            lines.append(f"    {kw} = {{ limit = {{ sol_pp_victuals_compat_is_on = yes {_list_check(good, suffix)} }} value = 1 }}")
        else:
            lines.append(f"    {kw} = {{ limit = {{ {_list_check(good, suffix)} }} value = 1 }}")
    lines.append("}")

    # — weight indicator (0.25–2.00) —
    if is_compat:
        lines += [
            f"sol_weight_indicator_{good} = {{",
            f"    value = 0",
            f"    if = {{",
            f"        limit = {{ sol_pp_victuals_compat_is_on = yes }}",
            f"        add = 1",
        ]
        first_adj = True
        for suffix, _t, weight, _d in SHORTAGE_TIERS + SURPLUS_TIERS:
            kw = "if" if first_adj else "else_if"
            first_adj = False
            delta = weight - 1.0
            lines.append(f"        {kw} = {{ limit = {{ {_list_check(good, suffix)} }} add = {delta} }}")
        lines += ["    }", "}"]
    else:
        lines.append(f"sol_weight_indicator_{good} = {{")
        lines.append(f"    value = 1")
        first_adj = True
        for suffix, _t, weight, _d in SHORTAGE_TIERS + SURPLUS_TIERS:
            kw = "if" if first_adj else "else_if"
            first_adj = False
            delta = weight - 1.0
            lines.append(f"    {kw} = {{ limit = {{ {_list_check(good, suffix)} }} add = {delta} }}")
        lines.append("}")

    # — demand share (0–100) —
    grp_weight = f"sol_{ind_grp}_base_total_weight"
    if is_compat:
        lines += [
            f"sol_demand_share_{good} = {{",
            f"    value = 0",
            f"    if = {{",
            f"        limit = {{ sol_pp_victuals_compat_is_on = yes }}",
            f"        add = 1",
        ]
        first_adj = True
        for suffix, _t, weight, _d in SHORTAGE_TIERS + SURPLUS_TIERS:
            kw = "if" if first_adj else "else_if"
            first_adj = False
            delta = weight - 1.0
            lines.append(f"        {kw} = {{ limit = {{ {_list_check(good, suffix)} }} add = {delta} }}")
        lines += [
            f"    }}",
            f"    divide = {grp_weight}",
            f"    multiply = 100",
            f"}}",
        ]
    else:
        lines.append(f"sol_demand_share_{good} = {{")
        lines.append(f"    value = sol_weight_indicator_{good}")
        lines.append(f"    divide = {grp_weight}")
        lines.append(f"    multiply = 100")
        lines.append("}")

    return lines


def _gen_group_base_total_weight(grp: str, goods: List[str]) -> List[str]:
    """Emit sol_<grp>_base_total_weight with tiered per-good contributions."""
    lines: List[str] = [f"sol_{grp}_base_total_weight = {{", "    value = 0"]
    for good in goods:
        is_compat = good in COMPAT_GOODS
        if is_compat:
            # Wrap entirely in compat check
            lines.append(f"    if = {{ limit = {{ sol_pp_victuals_compat_is_on = yes }}")
            for suffix, _t, weight, _d in SHORTAGE_TIERS:
                lines.append(f"        if = {{ limit = {{ {_list_check(good, suffix)} }} add = {weight} }}")
            # surplus tiers (else_if chain continues from shortage)
            for suffix, _t, weight, _d in SURPLUS_TIERS:
                lines.append(f"        else_if = {{ limit = {{ {_list_check(good, suffix)} }} add = {weight} }}")
            lines.append(f"        else = {{ add = 1 }}")
            lines.append(f"    }}")
        else:
            first = True
            for suffix, _t, weight, _d in SHORTAGE_TIERS:
                kw = "if" if first else "else_if"
                first = False
                lines.append(f"    {kw} = {{ limit = {{ {_list_check(good, suffix)} }} add = {weight} }}")
            for suffix, _t, weight, _d in SURPLUS_TIERS:
                lines.append(f"    else_if = {{ limit = {{ {_list_check(good, suffix)} }} add = {weight} }}")
            lines.append(f"    else = {{ add = 1 }}")
    lines += ["    min = 0.001", "}"]
    return lines


def gen_indicators_file() -> str:
    out: List[str] = [INDICATORS_HEADER.rstrip()]
    for grp, goods in INDICATOR_GROUPS:
        out.append("")
        out.append(f"###############################################################")
        out.append(f"# {grp.upper()} group: {', '.join(goods)}")
        out.append(f"###############################################################")
        out.append("")
        # base total weight first
        out.extend(_gen_group_base_total_weight(grp, goods))
        out.append("")
        # per-good indicators
        for good in goods:
            out.extend(_gen_good_indicators(good))
            out.append("")
    return "\n".join(out) + "\n"


# ── Group indicators file generator ─────────────────────────────────────────────────────────────
# These are the *demand* groups (used by GUI icon dots), distinct from INDICATOR_GROUPS above.
# Each sol_grp_<group>_scarce returns 1 if any good in that group is in any shortage tier.

DEMAND_GROUPS: List[Tuple[str, List[str]]] = [
    ("basic_clothing",    ["cloth", "leather"]),
    ("crude_goods",       ["lumber", "masonry", "tools", "pottery"]),
    ("staple",            ["wheat", "rice", "millet", "maize", "potato", "legumes", "fish"]),
    ("condiments",        ["sugar", "salt", "olives"]),
    ("heating",           ["lumber", "coal", "beeswax"]),
    ("household",         ["furniture", "pottery", "glass", "paper", "beeswax"]),
    ("standard_clothing", ["cloth", "fine_cloth"]),
    ("intoxicants",       ["wine", "beer", "liquor", "tobacco"]),
    ("luxury_drinks",     ["tea", "coffee", "wine", "cocoa"]),
    ("luxury_food",       ["wild_game", "victuals", "fruit"]),
    ("luxury_goods",      ["fine_cloth", "fur", "porcelain", "lacquerware", "marble", "glass"]),
    ("protein",           ["fish", "wild_game", "livestock"]),
    ("spices",            ["saffron", "pepper", "cloves", "chili"]),
    ("precious",          ["goods_gold", "silver", "jewelry"]),
    ("treasures",         ["amber", "gems", "ivory", "pearls"]),
    ("medicine",          ["medicaments", "mercury"]),
    ("ritual",            ["incense", "mercury"]),
    ("weapons",           ["weaponry", "firearms"]),
    ("mounts",            ["horses", "elephants"]),
    ("knowledge",         ["paper", "books"]),
]

GROUP_INDICATORS_HEADER = """\
### ============================================================
### SECTION: Substitute Group Scarcity Indicators (GUI helpers)
### ============================================================
# Each value returns 1 if any good in the demand group is currently
# scarce (any shortage tier) at the evaluated location's market.
#
# Used by location_window.gui demography_item blockoverride to drive
# visibility of per-stratum substitute-goods icons in the Population tab.
#
# Scope when evaluated: location (via Location.MakeScope.ScriptValue)
#
# AUTO-GENERATED by scripts/gen_scarcity.py — do not edit by hand.
"""


def gen_group_indicators_file() -> str:
    out: List[str] = [GROUP_INDICATORS_HEADER.rstrip()]
    for grp, goods in DEMAND_GROUPS:
        out.append("")
        out.append(f"sol_grp_{grp}_scarce = {{")
        out.append(f"    value = 0")
        out.append(f"    if = {{")
        out.append(f"        limit = {{")
        out.append(f"            OR = {{")
        for good in goods:
            for suffix, _t, _w, _d in SHORTAGE_TIERS:
                lst = _good_list_name(good, suffix)
                out.append(f"                market ?= {{ is_target_in_global_variable_list = {{ name = {lst} target = this }} }}")
        out.append(f"            }}")
        out.append(f"        }}")
        out.append(f"        value = 1")
        out.append(f"    }}")
        out.append(f"}}")
    out.append("")
    return "\n".join(out)


# ── Localization upsert ───────────────────────────────────────────────────────────────────────────

NEW_LOC_KEYS_EN = [
    ("SOL_WEIGHT_SCARCE_1", "Mild shortage — weight ×0.75"),
    ("SOL_WEIGHT_SCARCE_2", "Moderate shortage — weight ×0.50"),
    ("SOL_WEIGHT_SCARCE_3", "Severe shortage — weight ×0.25"),
    ("SOL_WEIGHT_CHEAP_1",  "Affordable — weight ×1.25"),
    ("SOL_WEIGHT_CHEAP_2",  "Cheap — weight ×1.50"),
    ("SOL_WEIGHT_CHEAP_3",  "Very cheap — weight ×2.00"),
    ("SOL_TT_STATUS_OK",          'OK'),
    ("SOL_TT_STATUS_MILD",       '#R Mild#!'),
    ("SOL_TT_STATUS_MODERATE",   '#R Moderate#!'),
    ("SOL_TT_STATUS_SEVERE",     '#R Severe#!'),
    ("SOL_TT_STATUS_AFFORDABLE", '#G Affordable#!'),
    ("SOL_TT_STATUS_CHEAP",      '#G Cheap#!'),
    ("SOL_TT_STATUS_VCHEAP",     '#G Very Cheap#!'),
]

NEW_LOC_KEYS_ZH = [
    ("SOL_WEIGHT_SCARCE_1", "轻微短缺——权重 ×0.75"),
    ("SOL_WEIGHT_SCARCE_2", "中度短缺——权重 ×0.50"),
    ("SOL_WEIGHT_SCARCE_3", "严重短缺——权重 ×0.25"),
    ("SOL_WEIGHT_CHEAP_1",  "价格低廉——权重 ×1.25"),
    ("SOL_WEIGHT_CHEAP_2",  "价格便宜——权重 ×1.50"),
    ("SOL_WEIGHT_CHEAP_3",  "极度便宜——权重 ×2.00"),
    ("SOL_TT_STATUS_OK",          '正常'),
    ("SOL_TT_STATUS_MILD",       '#R 轻微短缺#!'),
    ("SOL_TT_STATUS_MODERATE",   '#R 中度短缺#!'),
    ("SOL_TT_STATUS_SEVERE",     '#R 严重短缺#!'),
    ("SOL_TT_STATUS_AFFORDABLE", '#G 低廉#!'),
    ("SOL_TT_STATUS_CHEAP",      '#G 便宜#!'),
    ("SOL_TT_STATUS_VCHEAP",     '#G 极度便宜#!'),
]


def upsert_localization(text: str, keys: List[Tuple[str, str]]) -> str:
    for key, val in keys:
        line = f' {key}:0 "{val}"'
        # Match both `:0` and legacy (no version number) formats
        existing = re.compile(rf'^ {re.escape(key)}(?::0)? ".*"$', re.MULTILINE)
        if existing.search(text):
            text = existing.sub(line, text)
        else:
            text = text.rstrip("\n") + "\n" + line + "\n"
    return text


# ── Write helpers ─────────────────────────────────────────────────────────────────────────────

def _write(path: Path, content: str, dry_run: bool, encoding: str = "utf-8") -> None:
    if dry_run:
        print(f"[dry-run] Would write {path.name} ({len(content.splitlines())} lines)")
    else:
        path.write_text(content, encoding=encoding)
        print(f"Written  {path.name}")


# ── Good-group GUI info generators ───────────────────────────────────────────────────────────────

def _parse_goods_prices() -> dict:
    """Parse default_market_price from goods definition files."""
    prices: dict = {}
    for fname in sorted(GOODS_DIR.glob("*.txt")):
        if fname.name == "readme.txt":
            continue
        text = fname.read_text(encoding="utf-8")
        current_good = None
        depth = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            opens = line.count("{")
            closes = line.count("}")
            if depth == 0 and opens > 0:
                m = re.match(r'^(\w+)\s*=\s*\{', stripped)
                if m:
                    current_good = m.group(1)
                    prices.setdefault(current_good, 1.0)
            elif current_good and depth == 1:
                m = re.match(r'default_market_price\s*=\s*([\d.]+)', stripped)
                if m:
                    prices[current_good] = float(m.group(1))
            depth += opens - closes
            if depth <= 0:
                depth = 0
                current_good = None
    return prices


def _fmt_ratio(r: float) -> str:
    rounded = round(r, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    s = f"{rounded:.2f}".rstrip("0")
    return s


def _fmt_price(p: float) -> str:
    return str(int(p)) if p == int(p) else f"{p:.1f}"


def gen_goods_group_loca_keys(prices: dict) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Return (en_pairs, zh_pairs) of (loca_key, loca_value) for per-good group tooltip."""
    en_pairs: List[Tuple[str, str]] = []
    zh_pairs: List[Tuple[str, str]] = []
    for grp, members in INDICATOR_GROUPS:
        grp_zh = GROUP_NAMES_ZH.get(grp, grp)
        grp_en = GROUP_NAMES_EN.get(grp, grp)
        for good in members:
            pa = prices.get(good, 1.0)
            gn_zh = GOOD_NAMES_ZH.get(good, good)
            gn_en = GOOD_NAMES_EN.get(good, good)
            pa_s = _fmt_price(pa)

            subs_zh = []
            subs_en = []
            for other in members:
                if other == good:
                    continue
                pb = prices.get(other, 1.0)
                ratio = pa / pb
                on_zh = GOOD_NAMES_ZH.get(other, other)
                on_en = GOOD_NAMES_EN.get(other, other)
                subs_zh.append(f"1份{gn_zh}可替代{_fmt_ratio(ratio)}份{on_zh}")
                subs_en.append(f"1 {gn_en} ≈ {_fmt_ratio(ratio)} {on_en}")

            if subs_zh:
                val_zh = f"该商品属于 #B{grp_zh}#! 替代组：{'；'.join(subs_zh)}。"
                val_en = f"Belongs to #B{grp_en}#! substitute group: {'; '.join(subs_en)}."
            else:
                val_zh = f"该商品属于 #B{grp_zh}#! 替代组（组内唯一商品）。"
                val_en = f"Belongs to #B{grp_en}#! substitute group (sole member)."

            key = f"SOL_good_subst_group_{good}"
            zh_pairs.append((key, val_zh))
            en_pairs.append((key, val_en))

    return en_pairs, zh_pairs


def _replace_gen_section(text: str, tag: str, new_body: str) -> str:
    """Replace content between # @GEN_BEGIN:<tag> and # @GEN_END:<tag>."""
    begin = f"# @GEN_BEGIN:{tag}"
    end = f"# @GEN_END:{tag}"
    if begin in text and end in text:
        pre = text[:text.index(begin)]
        post = text[text.index(end) + len(end):]
        return pre + begin + "\n" + new_body + end + post
    return text + "\n" + begin + "\n" + new_body + end + "\n"


GUI_STATIC_HEADER = """\
# ============================================================
# z_SOL_goods_tooltip_override.gui
# Overrides 4 vanilla goods tooltip templates to inject substitute group info.
#
# Templates overridden:
#   Goods_tooltip                — generic goods tooltip (Goods scope)
#   SpecificGoodsMarket_tooltip  — market-context goods tooltip (Goods scope)
#   goods_market_price_tooltip   — market price chart tooltip (GoodsMarketEntry scope)
#   GoodsPriceOnMarket_tooltip   — price-on-market tooltip (GoodsPriceOnMarketWrap scope)
#
# All vanilla blockoverrides are replicated unchanged.
# Adds blockoverride "extra_tooltip_content" → SOL_goods_substitute_group_block
# Non-Goods scopes use widget { datacontext = "[X.GetGoods]" } to switch to Goods scope.
#
# AUTO-GENERATED (scaffold + body) by scripts/gen_scarcity.py — do not edit by hand.
# ============================================================

template Goods_tooltip {
\tContextualTooltipType = {
\t\tblockoverride "title_icon" {
\t\t\tbutton = {
\t\t\t\tusing = tooltip_title_icon_size
\t\t\t\ttexture = "[GetGoodsIcon(Goods.Self)]"
\t\t\t\tonclick = "[ShowGoods(Goods.Self)]"
\t\t\t\ttooltipwidget = {
\t\t\t\t\tLeftClickButtonTooltip = {
\t\t\t\t\t\tblockoverride "onclick_text" { text = "OPEN_GOOD_PANEL" }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}

\t\tblockoverride "title_text" {
\t\t\ttext = "[Goods.GetNameWithNoTooltip]"
\t\t}

\t\tblockoverride "concept_link" {
\t\t\ttext = [goods|e]
\t\t}

\t\tblockoverride "title_button" {
\t\t\tcustom_map_mode_button = {
\t\t\t\tdatacontext = "[GetMapMode('reactive_trade_good')]"

\t\t\t\tblockoverride "on_action" {
\t\t\t\t\ton_action = "[ShowGoodsReactive(Goods.Self)]"
\t\t\t\t}

\t\t\t\tblockoverride "icon" {
\t\t\t\t\ttexture = "[GetGoodsIcon(Goods.Self)]"
\t\t\t\t}
\t\t\t}
\t\t}

\t\tblockoverride "tooltip_content" {
\t\t\tusing = goods_details

\t\t\tTooltipFlavorTextBlock = {
\t\t\t\tblockoverride "text" {
\t\t\t\t\ttext = "[Goods.GetFlavorText]"
\t\t\t\t}
\t\t\t}
\t\t}

\t\t# ── Substitute group info ─────────────────────────────────────
\t\tblockoverride "extra_tooltip_content" {
\t\t\tusing = SOL_goods_substitute_group_block
\t\t}
\t}
}

template SOL_goods_substitute_group_block {
\t# One widget per good — exactly one visible at a time.
\t# Visibility check: EqualTo_string(Goods.GetKey, 'X')
\t# Pattern confirmed from battle_lateralview.gui:609 (EqualTo_string(CombatModifier.GetKey, 'dice'))
\t# AUTO-GENERATED — do not edit by hand.
"""

GUI_STATIC_FOOTER = """\
}

template SpecificGoodsMarket_tooltip {
\tContextualTooltipType = {

\t\tblockoverride "title_icon" {
\t\t\tbutton = {
\t\t\t\tusing = tooltip_title_icon_size
\t\t\t\ttexture = "[GetGoodsIcon(Goods.Self)]"
\t\t\t\ttooltipwidget = {
\t\t\t\t\tusing = Goods_tooltip
\t\t\t\t}
\t\t\t\taction_tooltip = {
\t\t\t\t\tclick_type = left
\t\t\t\t\tclick_mode = single
\t\t\t\t\ttitle = "OPEN_GOOD_PANEL"
\t\t\t\t\ton_action = "[ShowGoods(Goods.Self)]"
\t\t\t\t}
\t\t\t}
\t\t}

\t\tblockoverride "title_text" {
\t\t\ttext = "[Goods.GetNameWithNoTooltip]"
\t\t}

\t\tblockoverride "concept_link" {
\t\t\ttext = [goods|E]
\t\t}

\t\tblockoverride "title_button" {
\t\t\tcustom_map_mode_button = {
\t\t\t\tdatacontext = "[GetMapMode('reactive_trade_good')]"

\t\t\t\tblockoverride "on_action" {
\t\t\t\t\ton_action = "[ShowGoodsReactive(Goods.Self)]"
\t\t\t\t}

\t\t\t\tblockoverride "icon" {
\t\t\t\t\ttexture = "[GetGoodsIcon(Goods.Self)]"
\t\t\t\t}
\t\t\t}
\t\t}

\t\tblockoverride "tooltip_content" {
\t\t\tusing = goods_details
\t\t\tdatacontext = "[Market.GetMarketEntry(Goods.Self)]"

\t\t\tusing = SpecificGoodsFromMarketContent
\t\t\tblockoverride "data_from" {
\t\t\t\tdatacontext = "[Market]"
\t\t\t}

\t\t\tblock "good_details_extra_info" {}

\t\t\tTooltipFlavorTextBlock = {
\t\t\t\ttextcontext = "[Goods.GetFlavorText]"
\t\t\t}
\t\t}

\t\t# ── Substitute group info ─────────────────────────────────────
\t\tblockoverride "extra_tooltip_content" {
\t\t\tusing = SOL_goods_substitute_group_block
\t\t}
\t}
}

template goods_market_price_tooltip {
\tContextualTooltipType = {
\t\tblockoverride "title_icon" {
\t\t\tbutton = {
\t\t\t\tdatacontext = "[GoodsMarketEntry.GetGoods]"
\t\t\t\tusing = tooltip_title_icon_size
\t\t\t\ttexture = "[GetGoodsIcon(GoodsMarketEntry.GetGoods)]"
\t\t\t\ttooltipwidget = {
\t\t\t\t\tusing = Goods_tooltip
\t\t\t\t}
\t\t\t\taction_tooltip = {
\t\t\t\t\tclick_type = left
\t\t\t\t\tclick_mode = single
\t\t\t\t\ttitle = "OPEN_GOOD_PANEL"
\t\t\t\t\ton_action = "[ShowGoods(GoodsMarketEntry.GetGoods)]"
\t\t\t\t}
\t\t\t}
\t\t}

\t\tblockoverride "title_text" {
\t\t\ttext = "GOODS_MARKET_ENTRY_TITLE"
\t\t}

\t\tblockoverride "concept_link" {
\t\t\ttext = "[market_price|e]"
\t\t}

\t\tblockoverride "tooltip_content" {
\t\t\tusing = goods_market_details
\t\t}

\t\t# ── Substitute group info (GoodsMarketEntry scope → Goods via datacontext) ────
\t\tblockoverride "extra_tooltip_content" {
\t\t\twidget = {
\t\t\t\tdatacontext = "[GoodsMarketEntry.GetGoods]"
\t\t\t\tusing = SOL_goods_substitute_group_block
\t\t\t}
\t\t}
\t}
}

template GoodsPriceOnMarket_tooltip {
\tContextualTooltipType = {
\t\tblockoverride "title_icon_texture" {
\t\t\ttexture = "[GetGoodsIcon(GoodsPriceOnMarketWrap.GetGoods)]"
\t\t}

\t\tblockoverride "title_text" {
\t\t\ttext = "[GoodsPriceOnMarketWrap.GetName]"
\t\t}

\t\tblockoverride "concept_link" {
\t\t\ttext = "[market_price|e]"
\t\t}

\t\tblockoverride "tooltip_content" {
\t\t\tdatacontext = "[GoodsPriceOnMarketWrap.GetGoodsMarketEntry]"
\t\t\tdatacontext = "[GoodsPriceOnMarketWrap.GetMarket]"
\t\t\tusing = goods_market_details
\t\t}

\t\t# ── Substitute group info (GoodsPriceOnMarketWrap scope → Goods via datacontext) ────
\t\tblockoverride "extra_tooltip_content" {
\t\t\twidget = {
\t\t\t\tdatacontext = "[GoodsPriceOnMarketWrap.GetGoods]"
\t\t\t\tusing = SOL_goods_substitute_group_block
\t\t\t}
\t\t}
\t}
}
"""


def gen_goods_gui_override_file(prices: dict) -> str:
    """Generate the full content of z_SOL_goods_tooltip_override.gui."""
    lines: List[str] = []
    for grp, members in INDICATOR_GROUPS:
        lines.append(f"\t# --- {GROUP_NAMES_EN.get(grp, grp)} ---")
        for good in members:
            key = f"SOL_good_subst_group_{good}"
            lines.append(f"\tTooltipTextBlock = {{")
            lines.append(f"\t\tvisible = \"[EqualTo_string(Goods.GetKey, '{good}')]\"")
            lines.append(f"\t\tblockoverride \"text\" {{ text = \"{key}\" }}")
            lines.append(f"\t}}")
        lines.append("")
    body = "\n".join(lines)
    return GUI_STATIC_HEADER + body + GUI_STATIC_FOOTER


# ── Main ───────────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without changing files")
    args = parser.parse_args()
    dry = args.dry_run

    # 1. Effects file (full regen)
    _write(EFFECTS_FILE, gen_effects_file(), dry)

    # 2. Weights file (Part 1 string-replace per good)
    weights_text = WEIGHTS_FILE.read_text(encoding="utf-8")
    patched = patch_weights_file(weights_text)
    _write(WEIGHTS_FILE, patched, dry)

    # 3. Indicators file (full regen)
    _write(INDICATORS_FILE, gen_indicators_file(), dry)

    # 4. Group indicators file (full regen — fixes "variable never set" engine errors)
    _write(GROUP_INDICATORS_FILE, gen_group_indicators_file(), dry)

    # 5. Localization (upsert new keys; EU5 YAML requires UTF-8 BOM)
    for loc_file, keys in [
        (LOCALIZATION_FILE,    NEW_LOC_KEYS_EN),
        (LOCALIZATION_FILE_ZH, NEW_LOC_KEYS_ZH),
    ]:
        loc_text = loc_file.read_text(encoding="utf-8-sig")
        loc_new  = upsert_localization(loc_text, keys)
        _write(loc_file, loc_new, dry, encoding="utf-8-sig")

    # 6. Per-good group tooltip localization keys (upsert)
    prices = _parse_goods_prices()
    en_pairs, zh_pairs = gen_goods_group_loca_keys(prices)
    for loc_file, pairs in [
        (LOCALIZATION_FILE,    en_pairs),
        (LOCALIZATION_FILE_ZH, zh_pairs),
    ]:
        loc_text = loc_file.read_text(encoding="utf-8-sig")
        loc_new  = upsert_localization(loc_text, pairs)
        _write(loc_file, loc_new, dry, encoding="utf-8-sig")

    # 7. GUI override file (full regen)
    _write(GUI_OVERRIDE_FILE, gen_goods_gui_override_file(prices), dry, encoding="utf-8")

    if not dry:
        print("\nDone. Run next:")
        print("  conda run -n eu5 python scripts/gen_sol_ui.py --target tooltips")
        print("  conda run -n eu5 python scripts/validate.py --changed")


if __name__ == "__main__":
    main()
