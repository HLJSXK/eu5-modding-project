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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
# Aligned with DEMAND_GROUPS (20 groups). Multi-group goods are assigned to their primary group.
# victuals: requires sol_pp_victuals_compat_is_on check throughout.
INDICATOR_GROUPS: List[Tuple[str, List[str]]] = [
    ("basic_clothing",    ["cloth", "leather"]),
    ("standard_clothing", ["fine_cloth"]),                 # cloth → basic_clothing
    ("luxury_goods",      ["fur", "porcelain", "lacquerware", "marble", "glass"]),
    ("crude_goods",       ["lumber", "masonry", "tools", "pottery"]),
    ("heating",           ["beeswax", "coal"]),            # lumber → crude_goods
    ("household",         ["furniture"]),                   # beeswax→heating, glass→luxury_goods
    ("staple",            ["wheat", "rice", "millet", "maize", "potato", "legumes"]),
    ("condiments",        ["sugar", "salt", "olives"]),    # olives←staple; sugar←stimulants; salt←military
    ("luxury_food",       ["wild_game", "victuals", "fruit"]),
    ("protein",           ["fish", "livestock"]),          # wild_game → luxury_food
    ("intoxicants",       ["wine", "beer", "liquor", "tobacco"]),  # tobacco←stimulants
    ("luxury_drinks",     ["tea", "coffee", "cocoa"]),     # wine → intoxicants; ←stimulants
    ("spices",            ["saffron", "pepper", "cloves", "chili"]),
    ("precious",          ["goods_gold", "silver", "jewelry"]),
    ("treasures",         ["amber", "gems", "ivory", "pearls"]),
    ("medicine",          ["medicaments", "mercury"]),     # mercury primary=medicine; ←ritual
    ("ritual",            ["incense"]),                    # mercury → medicine
    ("weapons",           ["weaponry", "firearms"]),       # ←military
    ("mounts",            ["horses", "elephants"]),        # ←military
    ("knowledge",         ["paper", "books"]),
]

# Goods requiring compat-flag checks (sol_pp_victuals_compat_is_on = yes)
COMPAT_GOODS = frozenset(["victuals"])

GOOD_TO_IND_GROUP = {g: grp for grp, goods in INDICATOR_GROUPS for g in goods}
IND_GROUP_SIZE    = {grp: len(goods) for grp, goods in INDICATOR_GROUPS}
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

DEMAND_GROUP_NAMES_ZH: dict = {
    "basic_clothing":    "基本衣物",
    "crude_goods":       "粗制品",
    "staple":            "主食",
    "condiments":        "调味品",
    "heating":           "取暖燃料",
    "household":         "家居用品",
    "standard_clothing": "标准衣物",
    "intoxicants":       "嗜好饮料",
    "luxury_drinks":     "奢侈饮品",
    "luxury_food":       "奢侈食物",
    "luxury_goods":      "奢侈商品",
    "protein":           "蛋白食物",
    "spices":            "香料",
    "precious":          "贵重品",
    "treasures":         "珍宝",
    "medicine":          "药品",
    "ritual":            "祭祀物品",
    "weapons":           "武器",
    "mounts":            "坐骑",
    "knowledge":         "知识用品",
}

DEMAND_GROUP_NAMES_EN: dict = {
    "basic_clothing":    "Basic Clothing",
    "crude_goods":       "Crude Goods",
    "staple":            "Staple Food",
    "condiments":        "Condiments",
    "heating":           "Heating Fuel",
    "household":         "Household Goods",
    "standard_clothing": "Standard Clothing",
    "intoxicants":       "Intoxicants",
    "luxury_drinks":     "Luxury Drinks",
    "luxury_food":       "Luxury Food",
    "luxury_goods":      "Luxury Goods",
    "protein":           "Protein Food",
    "spices":            "Spices",
    "precious":          "Precious Goods",
    "treasures":         "Treasures",
    "medicine":          "Medicine",
    "ritual":            "Ritual Goods",
    "weapons":           "Weapons",
    "mounts":            "Mounts",
    "knowledge":         "Knowledge Goods",
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
# Storage: 6 global variable lists per good (56 goods × 6 = 336 lists).
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
    n = IND_GROUP_SIZE[ind_grp]
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

    # — demand share offset (% deviation from equal normal share) —
    # Formula: weight_indicator × n / base_total_weight − 1
    # Normal state: 1 × n / n − 1 = 0  →  |+=0%] displays "0%"
    # Scarce: weight<1 → negative decimal  Surplus: weight>1 → positive decimal
    # |+=0%] in GUI multiplies by 100 for display; do NOT multiply by 100 here.
    if is_compat:
        # Helper flag = 1 when compat on, 0 when compat off.
        # Multiplied at end so compat-off evaluates to 0 instead of -1.
        lines += [
            f"sol_demand_share_offset_{good}_compat = {{",
            f"    value = 0",
            f"    if = {{ limit = {{ sol_pp_victuals_compat_is_on = yes }} value = 1 }}",
            f"}}",
            f"sol_demand_share_offset_{good} = {{",
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
            f"    multiply = {n}",
            f"    divide = {grp_weight}",
            f"    add = -1",
            f"    multiply = sol_demand_share_offset_{good}_compat",
            f"}}",
        ]
    else:
        lines += [
            f"sol_demand_share_offset_{good} = {{",
            f"    value = sol_weight_indicator_{good}",
            f"    multiply = {n}",
            f"    divide = {grp_weight}",
            f"    add = -1",
            f"}}",
        ]

    return lines


def _gen_group_base_total_weight(grp: str, goods: List[str], prices: dict) -> List[str]:
    """Emit sol_<grp>_base_total_weight with price-weighted tiered contributions.

    Normal state denominator = Σ(price_j / avg_price) = n, preserving equal shares.
    Scarce state: expensive goods reduce denominator more → price-aware redistribution.
    """
    avg_price = sum(prices.get(g, 1.0) for g in goods) / len(goods) if goods else 1.0
    lines: List[str] = [f"sol_{grp}_base_total_weight = {{", "    value = 0"]
    for good in goods:
        price = prices.get(good, 1.0)
        price_factor = round(price / avg_price, 5)
        is_compat = good in COMPAT_GOODS
        if is_compat:
            lines.append(f"    if = {{ limit = {{ sol_pp_victuals_compat_is_on = yes }}")
            first = True
            for suffix, _t, weight, _d in SHORTAGE_TIERS:
                kw = "if" if first else "else_if"
                first = False
                contrib = round(weight * price_factor, 5)
                lines.append(f"        {kw} = {{ limit = {{ {_list_check(good, suffix)} }} add = {contrib} }}")
            for suffix, _t, weight, _d in SURPLUS_TIERS:
                contrib = round(weight * price_factor, 5)
                lines.append(f"        else_if = {{ limit = {{ {_list_check(good, suffix)} }} add = {contrib} }}")
            normal_contrib = round(1.0 * price_factor, 5)
            lines.append(f"        else = {{ add = {normal_contrib} }}")
            lines.append(f"    }}")
        else:
            first = True
            for suffix, _t, weight, _d in SHORTAGE_TIERS:
                kw = "if" if first else "else_if"
                first = False
                contrib = round(weight * price_factor, 5)
                lines.append(f"    {kw} = {{ limit = {{ {_list_check(good, suffix)} }} add = {contrib} }}")
            for suffix, _t, weight, _d in SURPLUS_TIERS:
                contrib = round(weight * price_factor, 5)
                lines.append(f"    else_if = {{ limit = {{ {_list_check(good, suffix)} }} add = {contrib} }}")
            normal_contrib = round(1.0 * price_factor, 5)
            lines.append(f"    else = {{ add = {normal_contrib} }}")
    lines += ["    min = 0.001", "}"]
    return lines


def gen_indicators_file(prices: dict) -> str:
    out: List[str] = [INDICATORS_HEADER.rstrip()]
    for grp, goods in INDICATOR_GROUPS:
        out.append("")
        out.append(f"###############################################################")
        out.append(f"# {grp.upper()} group: {', '.join(goods)}")
        out.append(f"###############################################################")
        out.append("")
        # base total weight first
        out.extend(_gen_group_base_total_weight(grp, goods, prices))
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
    ("SOL_SUBST_SECTION_TITLE", "Substitute Group"),
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
    ("SOL_PANEL_SCARCITY_TITLE", "Substitute Groups — Capital Market"),
]

NEW_LOC_KEYS_ZH = [
    ("SOL_SUBST_SECTION_TITLE", "替代组"),
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
    ("SOL_PANEL_SCARCITY_TITLE", "替代商品组——首都市场"),
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


def gen_group_ratio_templates(prices: dict) -> str:
    """Generate one SOL_subst_ratios_{group} template per DEMAND_GROUPS entry.

    Each template is scope-agnostic (static text + icons only, no ScriptValue).
    Used in Good Tooltip via 'using = SOL_subst_ratios_{group}' per-good,
    and at the tail of each Substitute UI group tooltip.
    """
    lines: List[str] = [
        "# ============================================================",
        "#  Per-group static ratio templates (SOL_subst_ratios_{group})",
        "#  Scope-agnostic: static text + icons, no ScriptValue calls.",
        "#  Used in Good Tooltip (one call per group the good belongs to)",
        "#  and at the tail of each SOL_{group}_scarce_tooltip.",
        "#  AUTO-GENERATED by scripts/gen_scarcity.py — do not edit by hand.",
        "# ============================================================",
        "",
    ]
    for grp, members in DEMAND_GROUPS:
        grp_zh = DEMAND_GROUP_NAMES_ZH.get(grp, grp)
        lines += [
            f"template SOL_subst_ratios_{grp} {{",
            f"\tvbox = {{",
            f"\t\tlayoutpolicy_horizontal = expanding",
            f"\t\tspacing = 3",
            f"\t\tmargin = {{ 4 4 }}",
            f"\t\tusing = bg_listbase_template",
            f'\t\ttext_single = {{ layoutpolicy_horizontal = expanding raw_text = "{grp_zh}" }}',
        ]
        for a in members:
            pa = prices.get(a, 1.0)
            a_zh = GOOD_NAMES_ZH.get(a, a)
            a_icon = _good_icon(a)
            for b in members:
                if b == a:
                    continue
                pb = prices.get(b, 1.0)
                ratio_str = _fmt_ratio(pa / pb)
                b_zh = GOOD_NAMES_ZH.get(b, b)
                b_icon = _good_icon(b)
                lines += [
                    f"\t\thbox = {{",
                    f"\t\t\tlayoutpolicy_horizontal = expanding",
                    f"\t\t\tspacing = 6",
                    f"\t\t\thbox = {{",
                    f'\t\t\t\ttext_single = {{ raw_text = "1单位{a_zh}" }}',
                    f'\t\t\t\ticon = {{ size = {{ 20 20 }} texture = "{a_icon}" }}',
                    f"\t\t\t}}",
                    f"\t\t\thbox = {{",
                    f'\t\t\t\ttext_single = {{ raw_text = "可替代 {ratio_str}单位{b_zh}" }}',
                    f'\t\t\t\ticon = {{ size = {{ 20 20 }} texture = "{b_icon}" }}',
                    f"\t\t\t}}",
                    f"\t\t}}",
                ]
        lines += [
            f"\t}}",
            f"}}",
            f"",
        ]
    return "\n".join(lines) + "\n"


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
\t# Structure per good: vbox (visible=X, expanding) { title, group subtitle, k rows }
\t# Each hbox row is expanding so text_single(expanding) gets space (not compressed to 0).
\t# vbox (not widget) used as wrapper so sizing propagates to TooltipContentSection parent.
\t# Row format: hbox { "1单位NAME" [ICON] "可替代 N单位NAME" [ICON] }
\t# Icon paths: gfx/interface/icons/trade_goods/icon_goods_<key>.dds
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


def _good_icon(good: str) -> str:
    return f"gfx/interface/icons/trade_goods/icon_goods_{good}.dds"


def gen_goods_gui_override_file(prices: dict) -> str:
    """Generate the full content of z_SOL_goods_tooltip_override.gui."""
    # Build reverse map: good → [(grp_key, grp_members), ...] in DEMAND_GROUPS order
    good_to_groups: dict = {}
    for grp, members in DEMAND_GROUPS:
        for good in members:
            good_to_groups.setdefault(good, []).append((grp, members))

    # Emit one vbox per unique good, in ALL_GOODS order
    lines: List[str] = []
    for good in ALL_GOODS:
        if good not in good_to_groups:
            continue
        groups = good_to_groups[good]
        gn_zh = GOOD_NAMES_ZH.get(good, good)
        good_icon = _good_icon(good)
        pa = prices.get(good, 1.0)

        lines += [
            # Outer card: vbox with bg_listbase_template (dark-tinted frame, same as tooltip list sections)
            f"\tvbox = {{",
            f'\t\tvisible = "[EqualTo_string(Goods.GetKey, \'{good}\')]"',
            f"\t\tlayoutpolicy_horizontal = expanding",
            f"\t\tspacing = 6",
            f"\t\tmargin = {{ 4 4 }}",
            f"\t\tusing = bg_listbase_template",
            # Section title
            f'\t\ttext_single = {{ layoutpolicy_horizontal = expanding text = "SOL_SUBST_SECTION_TITLE" }}',
        ]

        for grp, members in groups:
            lines.append(f"\t\tusing = SOL_subst_ratios_{grp}")

        lines += [f"\t}}", ""]

    body = "\n".join(lines)
    return gen_group_ratio_templates(prices) + GUI_STATIC_HEADER + body + GUI_STATIC_FOOTER


# ── Main ───────────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without changing files")
    args = parser.parse_args()
    dry = args.dry_run

    # 0. Parse prices (needed for both indicators and GUI override)
    prices = _parse_goods_prices()

    # 1. Effects file (full regen)
    _write(EFFECTS_FILE, gen_effects_file(), dry)

    # 2. Weights file (Part 1 string-replace per good)
    weights_text = WEIGHTS_FILE.read_text(encoding="utf-8")
    patched = patch_weights_file(weights_text)
    _write(WEIGHTS_FILE, patched, dry)

    # 3. Indicators file (full regen — price-weighted group denominators)
    _write(INDICATORS_FILE, gen_indicators_file(prices), dry)

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

    # 6. GUI override file (full regen)
    _write(GUI_OVERRIDE_FILE, gen_goods_gui_override_file(prices), dry, encoding="utf-8")

    if not dry:
        print("\nDone. Run next:")
        print("  conda run -n eu5 python scripts/gen_sol_ui.py --target tooltips")
        print("  conda run -n eu5 python scripts/validate.py --changed")


if __name__ == "__main__":
    main()
