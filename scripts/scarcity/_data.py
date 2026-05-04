"""Shared data constants and helper utilities for the scarcity package."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).parent.parent.parent

# ── Tier data ─────────────────────────────────────────────────────────────────

SHORTAGE_TIERS: List[Tuple[str, float, float, str]] = [
    ("severe",    2.30, 0.25, "SOL_WEIGHT_SCARCE_3"),
    ("moderate",  1.70, 0.50, "SOL_WEIGHT_SCARCE_2"),
    ("mild",      1.30, 0.75, "SOL_WEIGHT_SCARCE_1"),
]

SURPLUS_TIERS: List[Tuple[str, float, float, str]] = [
    ("vcheap",    0.40, 2.00, "SOL_WEIGHT_CHEAP_3"),
    ("cheap",     0.65, 1.50, "SOL_WEIGHT_CHEAP_2"),
    ("affordable",0.85, 1.25, "SOL_WEIGHT_CHEAP_1"),
]

ALL_TIER_SUFFIXES = [t[0] for t in SHORTAGE_TIERS + SURPLUS_TIERS]

# ── Indicator groups (PRIMARY GROUP) ─────────────────────────────────────────
# Each good appears in exactly one indicator group — its PRIMARY GROUP.
# This is the canonical authority for:
#   - substitute weight redistribution  (SOL_update_substitute_scarcity)
#   - all-goods scarcity score          (SOL_compute_scarcity_score)
#   - ALL_GOODS / GOOD_TO_IND_GROUP lookups
# Never add a good to more than one indicator group.

INDICATOR_GROUPS: List[Tuple[str, List[str]]] = [
    ("basic_clothing",    ["cloth", "leather"]),
    ("standard_clothing", ["fine_cloth"]),
    ("luxury_goods",      ["fur", "porcelain", "lacquerware", "marble", "glass"]),
    ("crude_goods",       ["lumber", "masonry", "tools", "pottery"]),
    ("heating",           ["beeswax", "coal"]),
    ("household",         ["furniture"]),
    ("staple",            ["wheat", "rice", "millet", "maize", "potato", "legumes"]),
    ("condiments",        ["sugar", "salt", "olives"]),
    ("luxury_food",       ["wild_game", "victuals", "fruit"]),  # wild_game primary here; secondary in DEMAND_GROUPS protein
    ("protein",           ["fish", "livestock"]),               # fish primary here; secondary in DEMAND_GROUPS luxury_food
    ("intoxicants",       ["wine", "beer", "liquor", "tobacco"]),
    ("luxury_drinks",     ["tea", "coffee", "cocoa"]),
    ("spices",            ["saffron", "pepper", "cloves", "chili"]),
    ("precious",          ["goods_gold", "silver", "jewelry"]),
    ("treasures",         ["amber", "gems", "ivory", "pearls"]),
    ("medicine",          ["medicaments", "mercury"]),          # mercury primary here; secondary in DEMAND_GROUPS ritual
    ("ritual",            ["incense"]),
    ("weapons",           ["weaponry", "firearms"]),
    ("mounts",            ["horses", "elephants"]),
    ("knowledge",         ["paper", "books"]),                  # paper primary here; secondary in DEMAND_GROUPS household
]

COMPAT_GOODS = frozenset(["victuals"])

GOOD_TO_IND_GROUP = {g: grp for grp, goods in INDICATOR_GROUPS for g in goods}
IND_GROUP_SIZE    = {grp: len(goods) for grp, goods in INDICATOR_GROUPS}
ALL_GOODS = [g for _, goods in INDICATOR_GROUPS for g in goods]

# ── Demand groups (DISPLAY GROUPING — goods may appear in multiple groups) ────
# Used for GUI icon dots only. A good may appear as a secondary member in groups
# other than its primary group (see INDICATOR_GROUPS above).
# Secondary members are annotated with "# secondary (primary: <group>)".
# This list does NOT drive substitution weights or the scarcity score.

DEMAND_GROUPS: List[Tuple[str, List[str]]] = [
    ("basic_clothing",    ["cloth", "leather"]),
    ("crude_goods",       ["lumber", "masonry", "tools", "pottery"]),
    ("staple",            ["wheat", "rice", "millet", "maize", "potato", "legumes"]),
    ("condiments",        ["sugar", "salt", "olives"]),
    ("heating",           ["lumber",   # secondary (primary: crude_goods)
                           "coal", "beeswax"]),
    ("household",         ["furniture",
                           "pottery",  # secondary (primary: crude_goods)
                           "glass",    # secondary (primary: luxury_goods)
                           "paper",    # secondary (primary: knowledge)
                           "beeswax"   # secondary (primary: heating)
                           ]),
    ("standard_clothing", ["cloth",    # secondary (primary: basic_clothing)
                           "fine_cloth"]),
    ("intoxicants",       ["wine", "beer", "liquor", "tobacco"]),
    ("luxury_drinks",     ["tea", "coffee",
                           "wine",     # secondary (primary: intoxicants)
                           "cocoa"]),
    ("luxury_food",       ["wild_game", "victuals", "fruit",
                           "fish"      # secondary (primary: protein)
                           ]),
    ("luxury_goods",      ["fine_cloth",  # secondary (primary: standard_clothing)
                           "fur", "porcelain", "lacquerware", "marble", "glass"]),
    ("protein",           ["fish", "livestock",
                           "wild_game"  # secondary (primary: luxury_food)
                           ]),
    ("spices",            ["saffron", "pepper", "cloves", "chili"]),
    ("precious",          ["goods_gold", "silver", "jewelry"]),
    ("treasures",         ["amber", "gems", "ivory", "pearls"]),
    ("medicine",          ["medicaments", "mercury"]),
    ("ritual",            ["incense",
                           "mercury"   # secondary (primary: medicine)
                           ]),
    ("weapons",           ["weaponry", "firearms"]),
    ("mounts",            ["horses", "elephants"]),
    ("knowledge",         ["paper", "books"]),
]

DEMAND_GROUP_SIZE = {grp: len(members) for grp, members in DEMAND_GROUPS}

# ── Display names ─────────────────────────────────────────────────────────────

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

# ── File paths ────────────────────────────────────────────────────────────────

EFFECTS_FILE          = ROOT / "src/stable/in_game/common/scripted_effects/SOL_substitute_effects.txt"
SCARCITY_SCORE_FILE   = ROOT / "src/stable/in_game/common/scripted_effects/z_SOL_scarcity_score.txt"
WEIGHTS_FILE          = ROOT / "src/stable/in_game/common/script_values/SOL_goods_weight_values.txt"
INDICATORS_FILE       = ROOT / "src/stable/in_game/common/script_values/SOL_substitute_good_indicators.txt"
GROUP_INDICATORS_FILE = ROOT / "src/stable/in_game/common/script_values/SOL_substitute_group_indicators.txt"
LOCALIZATION_FILE     = ROOT / "src/stable/main_menu/localization/english/SOL_substitute_goods_l_english.yml"
LOCALIZATION_FILE_ZH  = ROOT / "src/stable/main_menu/localization/simp_chinese/SOL_substitute_goods_l_simp_chinese.yml"
GOODS_DIR             = ROOT / "reference_game_files/game/in_game/common/goods"
GUI_OVERRIDE_FILE     = ROOT / "src/stable/in_game/gui/z_SOL_goods_tooltip_override.gui"

# ── Scarcity score ────────────────────────────────────────────────────────────

# Price threshold for each tier (× default price).
# Used to derive exact correction factors: -(1 - 1/P_tier), matching the
# "spending = income" target.  Natural bounds: severe all-goods → −0.565;
# vcheap all-goods → +1.50.  No hard cap needed; demand scales have min = 0.
TIER_PRICE_THRESHOLDS: dict[str, float] = {
    "severe":      2.30,
    "moderate":    1.70,
    "mild":        1.30,
    "affordable":  0.85,
    "cheap":       0.65,
    "vcheap":      0.40,
}

# Exact correction factor per unit of budget share for each tier.
# Formula: -(1 - 1/P_tier)  →  positive for surplus tiers (P < 1), negative for shortage.
TIER_EXACT_FACTORS: dict[str, float] = {
    k: -(1.0 - 1.0 / v) for k, v in TIER_PRICE_THRESHOLDS.items()
}

# ── Shared helpers ────────────────────────────────────────────────────────────

def _good_list_name(good: str, tier_suffix: str) -> str:
    return f"SOL_{good}_{tier_suffix}_markets"


def _fmt_ratio(r: float) -> str:
    rounded = round(r, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    s = f"{rounded:.2f}".rstrip("0")
    return s


def _fmt_price(p: float) -> str:
    return str(int(p)) if p == int(p) else f"{p:.1f}"


def _write(path: Path, content: str, dry_run: bool, encoding: str = "utf-8") -> None:
    if dry_run:
        print(f"[dry-run] Would write {path.name} ({len(content.splitlines())} lines)")
    else:
        path.write_text(content, encoding=encoding)
        print(f"Written  {path.name}")
