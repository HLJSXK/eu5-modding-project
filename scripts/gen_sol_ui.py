#!/usr/bin/env python3
"""
gen_sol_ui.py — legacy generator for UI sections that reference substitute groups.

Usage:
    $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_ui.py [--target all|location|tooltips|gls|effects] [--dry-run]

Each target rewrites the content between @GEN_BEGIN/@GEN_END anchors in its file:
  location  -> disabled legacy target; use sync_location_window.py instead
  tooltips  → SOL_substitute_tooltip.gui     20 template blocks (full regen after header)
  gls       → global_living_standard.gui     20 demand rows
  effects   → A_SOL_economy_effects.txt      Phase D / Phase B / Phase G anchors
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools" / "sol_demand_simulator"))
from curve_designer import GROUP_GOODS  # noqa: E402  # type: ignore[import]

# ── Canonical group data ──────────────────────────────────────────────────────

POP_GROUPS: Dict[str, List[str]] = {
    "nobles":   ["precious", "treasures", "luxury_goods", "mounts"],
    "clergy":   ["ritual", "medicine", "knowledge", "luxury_drinks"],
    "burghers": ["standard_clothing", "spices", "household", "luxury_food"],
    "laborers": ["intoxicants", "basic_clothing", "crude_goods", "heating"],
    "peasants": ["staple", "protein", "condiments", "weapons"],
}

GROUP_ICONS: Dict[str, str] = {
    "basic_clothing":    "icon_goods_leather.dds",
    "crude_goods":       "icon_goods_tools.dds",
    "staple":            "icon_goods_wheat.dds",
    "condiments":        "icon_goods_sugar.dds",
    "heating":           "icon_goods_coal.dds",
    "household":         "icon_goods_furniture.dds",
    "standard_clothing": "icon_goods_cloth.dds",
    "intoxicants":       "icon_goods_wine.dds",
    "luxury_drinks":     "icon_goods_tea.dds",
    "luxury_food":       "icon_goods_wild_game.dds",
    "luxury_goods":      "icon_goods_porcelain.dds",
    "protein":           "icon_goods_fish.dds",
    "spices":            "icon_goods_pepper.dds",
    "precious":          "icon_goods_goods_gold.dds",
    "treasures":         "icon_goods_gems.dds",
    "medicine":          "icon_goods_medicaments.dds",
    "ritual":            "icon_goods_incense.dds",
    "weapons":           "icon_goods_weaponry.dds",
    "mounts":            "icon_goods_horses.dds",
    "knowledge":         "icon_goods_books.dds",
}

GROUP_DISPLAY: Dict[str, str] = {
    "basic_clothing":    "Basic Clothing",
    "crude_goods":       "Crude Goods",
    "staple":            "Staple Food",
    "condiments":        "Condiments",
    "heating":           "Heating",
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
    "knowledge":         "Knowledge",
}

# Primary indicator group for each good — must mirror INDICATOR_GROUPS in gen_scarcity.py.
# Used to detect guest goods (goods whose primary group differs from the display group).
GOOD_TO_PRIMARY_GROUP: Dict[str, str] = {
    g: grp
    for grp, members in [
        ("basic_clothing",    ["cloth", "leather"]),
        ("standard_clothing", ["fine_cloth"]),
        ("luxury_goods",      ["fur", "porcelain", "lacquerware", "marble", "glass"]),
        ("crude_goods",       ["lumber", "masonry", "tools", "pottery"]),
        ("heating",           ["beeswax", "coal"]),
        ("household",         ["furniture"]),
        ("staple",            ["wheat", "rice", "millet", "maize", "potato", "legumes"]),
        ("condiments",        ["sugar", "salt", "olives"]),
        ("luxury_food",       ["wild_game", "fruit"]),
        ("protein",           ["fish", "livestock"]),
        ("intoxicants",       ["wine", "beer", "liquor", "tobacco"]),
        ("luxury_drinks",     ["tea", "coffee", "cocoa"]),
        ("spices",            ["saffron", "pepper", "cloves", "chili"]),
        ("precious",          ["goods_gold", "silver", "jewelry"]),
        ("treasures",         ["amber", "gems", "ivory", "pearls"]),
        ("medicine",          ["medicaments", "mercury"]),
        ("ritual",            ["incense"]),
        ("weapons",           ["weaponry", "firearms"]),
        ("mounts",            ["horses", "elephants"]),
        ("knowledge",         ["paper", "books"]),
    ]
    for g in members
}

# Which GLS estates participate in each group.
# commoners = laborers + peasants + soldiers (combined in demand scale calculation).
GLS_PART: Dict[str, Dict[str, bool]] = {
    "basic_clothing":    {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "crude_goods":       {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "staple":            {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "condiments":        {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "heating":           {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "household":         {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "standard_clothing": {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "intoxicants":       {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "luxury_drinks":     {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "luxury_food":       {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "luxury_goods":      {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": False},
    "protein":           {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "spices":            {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": False},
    "precious":          {"nobles": True,  "clergy": False, "burghers": True,  "commoners": False},
    "treasures":         {"nobles": True,  "clergy": False, "burghers": True,  "commoners": False},
    "medicine":          {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "ritual":            {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": True},
    "weapons":           {"nobles": True,  "clergy": False, "burghers": False, "commoners": True},
    "mounts":            {"nobles": True,  "clergy": False, "burghers": False, "commoners": False},
    "knowledge":         {"nobles": True,  "clergy": True,  "burghers": True,  "commoners": False},
}

LUXURY_RANK: Dict[str, int] = {
    "staple": 1, "crude_goods": 2, "condiments": 3, "heating": 4, "basic_clothing": 5,
    "protein": 6, "household": 7, "intoxicants": 8, "standard_clothing": 9, "weapons": 10,
    "mounts": 11, "spices": 12, "medicine": 13, "luxury_drinks": 14, "luxury_food": 15,
    "luxury_goods": 16, "precious": 17, "knowledge": 18, "ritual": 19, "treasures": 20,
}

# Canonical display order: expensive → cheap (descending luxury rank).
DISPLAY_ORDER: List[str] = sorted(GLS_PART.keys(), key=lambda g: LUXURY_RANK[g], reverse=True)

# Three visual tiers: top 7, mid 7, bottom 6 by luxury rank.
TIERS: List[tuple] = [
    ("SOL_TIER_PRECIOUS", DISPLAY_ORDER[0:7]),
    ("SOL_TIER_COMMON",   DISPLAY_ORDER[7:14]),
    ("SOL_TIER_CRUDE",    DISPLAY_ORDER[14:20]),
]

SUBSTITUTE_GROUPS: List[str] = DISPLAY_ORDER

# Groups each estate participates in (derived from GLS_PART)
ESTATE_GROUPS: Dict[str, List[str]] = {
    estate: [g for g, p in GLS_PART.items() if p.get(estate, False)]
    for estate in ("nobles", "clergy", "burghers", "commoners")
}

# ── File paths ────────────────────────────────────────────────────────────────

LOCATION_WINDOW    = ROOT / "src/stable/in_game/gui/location_window.gui"
TOOLTIP_FILE       = ROOT / "src/stable/in_game/gui/SOL_substitute_tooltip.gui"
GLS_FILE           = ROOT / "src/stable/in_game/gui/panels/situation/global_living_standard.gui"
EFFECTS_FILE       = ROOT / "src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt"
ECONOMY_LOCAL_FILE = ROOT / "src/stable/in_game/gui/SOL_economy_local.gui"

# ── Replacement helper ────────────────────────────────────────────────────────

def replace_section(path: Path, tag: str, new_content: str, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    begin_marker = f"# @GEN_BEGIN:{tag}"
    end_marker = f"# @GEN_END:{tag}"
    pattern = re.compile(
        re.escape(begin_marker) + r"\n.*?" + re.escape(end_marker),
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        print(f"ERROR: anchor '{tag}' not found in {path.name}", file=sys.stderr)
        sys.exit(1)
    replacement = begin_marker + "\n" + new_content + end_marker
    new_text = pattern.sub(replacement, text)
    if dry_run:
        print(f"[dry-run] Would update {path.name}:{tag} ({len(new_content.splitlines())} lines)")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"Updated {path.name}:{tag}")

# ── Generator: location_window.gui substitute icon block ─────────────────────

def gen_substitute_icons() -> str:
    T = "\t" * 9  # match surrounding indentation in the hbox inside the pop row
    lines: List[str] = []
    for poptype, groups in POP_GROUPS.items():
        for group in groups:
            texture = GROUP_ICONS[group]
            display = GROUP_DISPLAY[group]
            lines += [
                f"{T}# {poptype}: {display}",
                f"{T}widget = {{",
                f"{T}\tsize = {{ 24 24 }}",
                f"{T}\tvisible = \"[ObjectsEqual(GetPopTypeByName('{poptype}'), PopType.Self)]\"",
                f"{T}\ticon = {{",
                f"{T}\t\tsize = {{ 24 24 }}",
                f"{T}\t\ttexture = \"gfx/interface/icons/trade_goods/{texture}\"",
                f"{T}\t\ttooltipwidget = {{ using = SOL_{group}_scarce_tooltip }}",
                f"{T}\t}}",
                f"{T}\ticon = {{",
                f"{T}\t\tsize = {{ 10 10 }}",
                f"{T}\t\tparentanchor = bottom|right",
                f"{T}\t\tposition = {{ 2 2 }}",
                f"{T}\t\ttexture = \"gfx/interface/component_tiles/bookmark_white.dds\"",
                f"{T}\t\ttintcolor = {{ 1.0 0.2 0.2 1.0 }}",
                f"{T}\t\tvisible = \"[GreaterThan_CFixedPoint(Location.MakeScope.ScriptValue('sol_grp_{group}_scarce'), '(CFixedPoint)0')]\"",
                f"{T}\t}}",
                f"{T}}}",
                f"",
            ]
    return "\n".join(lines)

# ── Generator: SOL_substitute_tooltip.gui templates ──────────────────────────

# Per-poptype GDP/savings script value names
_GDP_SV: Dict[str, str] = {
    "nobles":   "local_noble_gdp_per_capita_display",
    "clergy":   "local_clergy_gdp_per_capita_display",
    "burghers": "local_burghers_gdp_per_capita_display",
    "laborers": "local_commoner_gdp_per_capita_display",
    "peasants": "local_commoner_gdp_per_capita_display",
}
_SAV_SV: Dict[str, str] = {
    "nobles":   "local_nobles_savings_pressure",
    "clergy":   "local_clergy_savings_pressure",
    "burghers": "local_burghers_savings_pressure",
    "laborers": "local_commoner_savings_pressure",
    "peasants": "local_commoner_savings_pressure",
}

def _demand_sv(poptype: str, group: str) -> str:
    if poptype in ("laborers", "peasants"):
        return f"local_commoners_{group}_demand_scale_offset"
    return f"local_{poptype}_{group}_demand_scale_offset"

# goods_gold's localization key is SOL_TT_GOODS_GOLD (not SOL_TT_GOODS_GOODS_GOLD)
_GOOD_LOC_SUFFIX: Dict[str, str] = {
    "goods_gold": "GOLD",
}

def _good_row(good: str, group: str = None) -> List[str]:
    sc = f"sol_good_{good}_scarcity_tier"   # 0-3
    su = f"sol_good_{good}_surplus_tier"    # 0-3
    ab = f"sol_good_{good}_absent"          # 0 or 1
    wt = f"sol_weight_indicator_{good}"
    primary = GOOD_TO_PRIMARY_GROUP.get(good)
    if group is not None and primary != group:
        ds = f"sol_demand_share_offset_{good}_in_{group}"
    else:
        ds = f"sol_demand_share_offset_{good}"
    loc_suffix = _GOOD_LOC_SUFFIX.get(good, good.upper())

    def _gt(sv: str, n: int) -> str:
        return f"GreaterThan_CFixedPoint(Location.MakeScope.ScriptValue('{sv}'), '(CFixedPoint){n}')"

    def _not(expr: str) -> str:
        return f"Not({expr})"

    def _and(a: str, b: str) -> str:
        return f"And({a}, {b})"

    sc_any    = _gt(sc, 0)                          # any scarcity
    sc_gt1    = _gt(sc, 1)                          # moderate or severe
    sc_gt2    = _gt(sc, 2)                          # severe only
    su_any    = _gt(su, 0)                          # any surplus
    su_gt1    = _gt(su, 1)                          # cheap or vcheap
    su_gt2    = _gt(su, 2)                          # vcheap only
    ab_1      = _gt(ab, 0)                          # good absent from market
    v_severe   = sc_gt2
    v_moderate = _and(sc_gt1, _not(sc_gt2))
    v_mild     = _and(sc_any, _not(sc_gt1))
    # v_normal excludes absent; v_no_tier covers normal+absent for weight/share display
    v_normal   = _and(_not(sc_any), _and(_not(su_any), _not(ab_1)))
    v_no_tier  = _and(_not(sc_any), _not(su_any))  # normal OR absent (weight stays 1.0)
    v_afford   = _and(su_any, _not(su_gt1))
    v_cheap    = _and(su_gt1, _not(su_gt2))
    v_vcheap   = su_gt2
    v_absent   = ab_1

    return [
        f"                    # Row: {good}",
        f"                    hbox = {{",
        f"                        layoutpolicy_horizontal = expanding",
        f"                        spacing = 4",
        f"                        icon = {{ size = {{ 20 20 }} texture = \"gfx/interface/icons/trade_goods/icon_goods_{good}.dds\" }}",
        f"                        text_single = {{ layoutpolicy_horizontal = expanding text = \"SOL_TT_GOODS_{loc_suffix}\" }}",
        # Status column (8 states: 7 price tiers + absent)
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_severe}]\"   text = \"SOL_TT_STATUS_SEVERE\" }}",
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_moderate}]\" text = \"SOL_TT_STATUS_MODERATE\" }}",
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_mild}]\"     text = \"SOL_TT_STATUS_MILD\" }}",
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_normal}]\"   text = \"SOL_TT_STATUS_OK\" }}",
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_afford}]\"   text = \"SOL_TT_STATUS_AFFORDABLE\" }}",
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_cheap}]\"    text = \"SOL_TT_STATUS_CHEAP\" }}",
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_vcheap}]\"   text = \"SOL_TT_STATUS_VCHEAP\" }}",
        f"                        text_single = {{ min_width = 55 align = hcenter visible = \"[{v_absent}]\"   text = \"SOL_TT_STATUS_ABSENT\" }}",
        # Weight column (3 color states: scarce=red, no-tier=plain, surplus=green)
        # Absent goods keep weight 1.0 and display as plain (v_no_tier covers normal+absent)
        f"                        text_single = {{ min_width = 50 align = hcenter",
        f"                            visible = \"[{sc_any}]\"",
        f"                            raw_text = \"#R [Location.MakeScope.ScriptValue('{wt}')|2]#!\" }}",
        f"                        text_single = {{ min_width = 50 align = hcenter",
        f"                            visible = \"[{v_no_tier}]\"",
        f"                            raw_text = \"[Location.MakeScope.ScriptValue('{wt}')|2]\" }}",
        f"                        text_single = {{ min_width = 50 align = hcenter",
        f"                            visible = \"[{su_any}]\"",
        f"                            raw_text = \"#G [Location.MakeScope.ScriptValue('{wt}')|2]#!\" }}",
        # Demand share offset column (signed %, scarce=red, no-tier=plain, surplus=green)
        f"                        text_single = {{ min_width = 50 align = hcenter",
        f"                            visible = \"[{sc_any}]\"",
        f"                            raw_text = \"#R [Location.MakeScope.ScriptValue('{ds}')|+=0%]#!\" }}",
        f"                        text_single = {{ min_width = 50 align = hcenter",
        f"                            visible = \"[{v_no_tier}]\"",
        f"                            raw_text = \"[Location.MakeScope.ScriptValue('{ds}')|+=0%]\" }}",
        f"                        text_single = {{ min_width = 50 align = hcenter",
        f"                            visible = \"[{su_any}]\"",
        f"                            raw_text = \"#G [Location.MakeScope.ScriptValue('{ds}')|+=0%]#!\" }}",
        f"                    }}",
    ]

def _correction_row(poptype: str, group: str) -> List[str]:
    part = GLS_PART[group]
    key = "commoners" if poptype in ("laborers", "peasants") else poptype
    if not part.get(key, False):
        return []
    return [
        f"                    hbox = {{",
        f"                        visible = \"[ObjectsEqual(GetPopTypeByName('{poptype}'), PopType.Self)]\"",
        f"                        layoutpolicy_horizontal = expanding",
        f"                        text_single = {{ layoutpolicy_horizontal = expanding text = \"SOL_TT_CURRENT_CLASS\" }}",
        f"                        text_single = {{ min_width = 68 align = hcenter raw_text = \"[Location.MakeScope.ScriptValue('{_GDP_SV[poptype]}')|+2]\" }}",
        f"                        text_single = {{ min_width = 68 align = hcenter raw_text = \"[Location.MakeScope.ScriptValue('{_SAV_SV[poptype]}')|+=0%]\" }}",
        f"                        text_single = {{ min_width = 68 align = hcenter raw_text = \"[Location.MakeScope.ScriptValue('{_demand_sv(poptype, group)}')|+=0%]\" }}",
        f"                    }}",
    ]

def gen_substitute_tooltips() -> str:
    lines: List[str] = []
    for group in SUBSTITUTE_GROUPS:
        display  = GROUP_DISPLAY[group]
        goods    = GROUP_GOODS[group]
        icon_tex = GROUP_ICONS[group]
        loc_key  = group.upper()

        lines += [
            f"# {'=' * 60}",
            f"#  GROUP: {display}  ({', '.join(goods)})",
            f"# {'=' * 60}",
            f"template SOL_{group}_scarce_tooltip {{",
            f"    ContextualTooltipType = {{",
            f"        blockoverride \"title_icon\" {{",
            f"            icon = {{ using = tooltip_title_icon_size",
            f"                     texture = \"gfx/interface/icons/trade_goods/{icon_tex}\" }}",
            f"        }}",
            f"        blockoverride \"title_text\" {{ text = \"SOL_TT_{loc_key}_TITLE\" }}",
            f"        blockoverride \"tooltip_content\" {{",
            f"            vbox = {{",
            f"                layoutpolicy_horizontal = expanding",
            f"                TooltipTextBlock = {{",
            f"                    blockoverride \"text\" {{ text = \"SOL_TT_{loc_key}_DESC\" }}",
            f"                }}",
            f"                vbox = {{",
            f"                    layoutpolicy_horizontal = expanding",
            f"                    margin = {{ 10 4 }}",
            f"                    spacing = 2",
            f"                    # Header",
            f"                    hbox = {{",
            f"                        layoutpolicy_horizontal = expanding",
            f"                        text_single = {{ layoutpolicy_horizontal = expanding text = \"SOL_TT_GOODS_LIST_HEADER\" }}",
            f"                        text_single = {{ min_width = 55 align = hcenter text = \"SOL_TT_STATUS_HEADER\" }}",
            f"                        text_single = {{ min_width = 50 align = hcenter text = \"SOL_TT_WEIGHT_HEADER\" }}",
            f"                        text_single = {{ min_width = 50 align = hcenter text = \"SOL_TT_DEMAND_HEADER\" }}",
            f"                    }}",
        ]
        for good in goods:
            lines.extend(_good_row(good, group=group))
        lines += [
            f"                }}",
            f"            }}",
            f"        }}",
            f"    }}",
            f"}}",
            f"",
            f"",
        ]
    return "\n".join(lines)

# ── Generator: global_living_standard.gui demand rows ────────────────────────

# Estate columns in GLS: (gls_estate_key, estate_form_key)
GLS_ESTATES = [
    ("nobles",    "nobles_estate"),
    ("clergy",    "clergy_estate"),
    ("burghers",  "burghers_estate"),
    ("commoners", "peasants_estate"),
    ("tribesmen", "tribes_estate"),
]

def gen_gls_demand_rows() -> str:
    T = "\t\t\t\t\t\t"  # indentation matching the existing hbox rows
    lines: List[str] = []
    for tier_key, tier_groups in TIERS:
        lines.append(f"{T}hbox = {{")
        lines.append(f"{T}\tlayoutpolicy_horizontal = expanding")
        lines.append(f"{T}\ttext_single = {{ layoutpolicy_horizontal = expanding align = hcenter text = \"{tier_key}\" }}")
        lines.append(f"{T}}}")
        lines.append(f"")
        for group in tier_groups:
            part = GLS_PART[group]
            lines.append(f"{T}# {group}")
            lines.append(f"{T}hbox = {{")
            lines.append(f"{T}\tlayoutpolicy_horizontal = expanding")
            lines.append(f"{T}\ttext_single = {{ layoutpolicy_horizontal = expanding text = \"SOL_TT_{group.upper()}_TITLE\" }}")
            for estate_key, estate_form in GLS_ESTATES:
                vis = f"[Player.GetGovernment.GetEstateFromKey('{estate_form}').ExistsForCountry]"
                if estate_key == "tribesmen" or not part.get(estate_key, False):
                    lines.append(f"{T}\ttext_single = {{ min_width = 72 align = hcenter visible = \"{vis}\"   raw_text = \"-\" }}")
                else:
                    var = f"gls_{estate_key}_{group}_offset"
                    lines.append(f"{T}\ttext_single = {{ min_width = 72 align = hcenter visible = \"{vis}\"   text = \"[Player.MakeScope.GetVariable('{var}').GetValue|+=0%]\" }}")
            lines.append(f"{T}}}")
            lines.append(f"")
    return "\n".join(lines)

# ── Generator: SOL_economy_local.gui demand rows ─────────────────────────────

# Estate columns for local tooltip: nobles/clergy/burghers/commoners then tribesmen placeholder.
_LOCAL_ESTATES = ["nobles", "clergy", "burghers", "commoners"]

def gen_economy_local_demand_rows() -> str:
    T = "\t\t\t\t\t"  # indentation matching the existing hbox rows in SOL_economy_local.gui
    lines: List[str] = []
    for tier_key, tier_groups in TIERS:
        lines.append(f"{T}hbox = {{")
        lines.append(f"{T}\tlayoutpolicy_horizontal = expanding")
        lines.append(f"{T}\ttext_single = {{ layoutpolicy_horizontal = expanding align = hcenter text = \"{tier_key}\" }}")
        lines.append(f"{T}}}")
        lines.append(f"")
        for group in tier_groups:
            part = GLS_PART[group]
            lines.append(f"{T}# {group}")
            lines.append(f"{T}hbox = {{")
            lines.append(f"{T}\tlayoutpolicy_horizontal = expanding")
            lines.append(f"{T}\ttext_single = {{ layoutpolicy_horizontal = expanding text = \"SOL_TT_{group.upper()}_TITLE\" }}")
            for estate in _LOCAL_ESTATES:
                if part.get(estate, False):
                    sv = f"local_{estate}_{group}_demand_scale_offset"
                    lines.append(f"{T}\ttext_single = {{ min_width = 68 align = hcenter raw_text = \"[Location.MakeScope.ScriptValue('{sv}')|+=0%]\" }}")
                else:
                    lines.append(f"{T}\ttext_single = {{ min_width = 68 align = hcenter raw_text = \"-\" }}")
            lines.append(f"{T}\ttext_single = {{ min_width = 68 align = hcenter raw_text = \"-\" }}")  # tribesmen
            lines.append(f"{T}}}")
            lines.append(f"")
    return "\n".join(lines)

# ── Generator: global_living_standard.gui scarcity icon row ─────────────────

def gen_gls_scarcity_icons() -> str:
    T = "\t\t\t\t\t"  # indentation inside the card vbox
    lines: List[str] = []
    # vbox carries the datacontext to establish Location scope for child expressions;
    # using vbox (not widget) so it auto-sizes to content and the card frame fills correctly.
    lines.append(f"{T}vbox = {{")
    lines.append(f"{T}\tdatacontext = \"[Player.GetCapital]\"")
    lines.append(f"{T}\tlayoutpolicy_horizontal = expanding")
    lines.append(f"{T}\tspacing = 4")
    for tier_key, tier_groups in TIERS:
        lines.append(f"{T}\thbox = {{")
        lines.append(f"{T}\t\tlayoutpolicy_horizontal = expanding")
        lines.append(f"{T}\t\ttext_single = {{ layoutpolicy_horizontal = expanding text = \"{tier_key}\" }}")
        for group in tier_groups:
            icon_tex = GROUP_ICONS[group]
            lines += [
                f"{T}\t\twidget = {{",
                f"{T}\t\t\tsize = {{ 32 32 }}",
                f"{T}\t\t\ticon = {{",
                f"{T}\t\t\t\tsize = {{ 32 32 }}",
                f"{T}\t\t\t\ttexture = \"gfx/interface/icons/trade_goods/{icon_tex}\"",
                f"{T}\t\t\t\ttooltipwidget = {{ using = SOL_{group}_scarce_tooltip }}",
                f"{T}\t\t\t}}",
                f"{T}\t\t\ticon = {{",
                f"{T}\t\t\t\tparentanchor = bottom|right",
                f"{T}\t\t\t\tposition = {{ 2 2 }}",
                f"{T}\t\t\t\tsize = {{ 10 10 }}",
                f"{T}\t\t\t\ttexture = \"gfx/interface/component_tiles/bookmark_white.dds\"",
                f"{T}\t\t\t\ttintcolor = {{ 1.0 0.2 0.2 1.0 }}",
                f"{T}\t\t\t\tvisible = \"[GreaterThan_CFixedPoint(Location.MakeScope.ScriptValue('sol_grp_{group}_scarce'), '(CFixedPoint)0')]\"",
                f"{T}\t\t\t}}",
                f"{T}\t\t}}",
            ]
        lines.append(f"{T}\t}}")
    lines.append(f"{T}}}")
    return "\n".join(lines) + "\n"

# ── Generator: A_SOL_economy_effects.txt phases ──────────────────────────────

def gen_effects_phase_g_guard() -> str:
    lines: List[str] = []
    for estate, groups in ESTATE_GROUPS.items():
        for group in groups:
            lines.append(f"\t\t\t\thas_variable = gls_{estate}_{group}_offset")
    return "\n".join(lines)

def gen_effects_phase_d() -> str:
    lines: List[str] = []
    for estate, groups in ESTATE_GROUPS.items():
        for group in groups:
            lines.append(f"\tset_variable = {{ name = gls_sum_{estate}_{group}_scale value = 0 }}")
        lines.append("")
    return "\n".join(lines)

def gen_effects_phase_b(estate: str) -> str:
    groups = ESTATE_GROUPS[estate]
    lines: List[str] = []
    if estate == "commoners":
        for group in groups:
            lines.append(
                f"\t\t\t\t\tchange_variable = {{ name = gls_sum_commoners_{group}_scale"
                f"   add = {{ value = scope:gls_cached_location.local_commoners_{group}_demand_scale"
                f"   multiply = scope:gls_cached_location.local_commoner_population }} }}"
            )
    else:
        for group in groups:
            lines.append(
                f"\t\t\t\t\tchange_variable = {{ name = gls_sum_{estate}_{group}_scale"
                f"   add = {{ value = scope:gls_cached_location.local_{estate}_{group}_demand_scale"
                f"   multiply = scope:gls_cached_location.num_pop_type:{estate} }} }}"
            )
    return "\n".join(lines)

def gen_effects_phase_g(estate: str) -> str:
    groups = ESTATE_GROUPS[estate]
    pop_var = f"gls_pop_{estate}"
    lines: List[str] = []
    for group in groups:
        lines.append(f"\tset_variable = {{ name = gls_{estate}_{group}_offset    value = 0 }}")
    lines.append(f"\tif = {{")
    lines.append(f"\t\tlimit = {{ var:{pop_var} > 0 }}")
    for group in groups:
        lines.append(
            f"\t\tset_variable = {{ name = gls_{estate}_{group}_offset"
            f"    value = {{ add = var:gls_sum_{estate}_{group}_scale"
            f"    divide = var:{pop_var}  subtract = 1 }} }}"
        )
    lines.append(f"\t}}")
    return "\n".join(lines)

# ── Target runners ────────────────────────────────────────────────────────────

# DISABLED for the EU5 1.3 active SOL flow.
# Legacy substitute-group icons are no longer part of the location window. Rebuild
# location_window.gui from the current vanilla baseline with sync_location_window.py.
def run_location(dry_run: bool) -> None:
    raise SystemExit(
        "ERROR: --target location is legacy-disabled for EU5 1.3.\n"
        "Run  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/sync_location_window.py  to sync location_window.gui."
    )

def run_tooltips(dry_run: bool) -> None:
    replace_section(TOOLTIP_FILE, "templates", gen_substitute_tooltips(), dry_run)

def run_gls(dry_run: bool) -> None:
    replace_section(GLS_FILE, "demand_rows", gen_gls_demand_rows(), dry_run)

def run_scarcity_icons(dry_run: bool) -> None:
    replace_section(GLS_FILE, "scarcity_icons", gen_gls_scarcity_icons(), dry_run)

def run_effects(dry_run: bool) -> None:
    replace_section(EFFECTS_FILE, "phase_g_guard",      gen_effects_phase_g_guard(),     dry_run)
    replace_section(EFFECTS_FILE, "phase_d_scales",     gen_effects_phase_d(),          dry_run)
    replace_section(EFFECTS_FILE, "phase_b_nobles",     gen_effects_phase_b("nobles"),   dry_run)
    replace_section(EFFECTS_FILE, "phase_b_clergy",     gen_effects_phase_b("clergy"),   dry_run)
    replace_section(EFFECTS_FILE, "phase_b_burghers",   gen_effects_phase_b("burghers"), dry_run)
    replace_section(EFFECTS_FILE, "phase_b_commoners",  gen_effects_phase_b("commoners"),dry_run)
    replace_section(EFFECTS_FILE, "phase_g_nobles",     gen_effects_phase_g("nobles"),   dry_run)
    replace_section(EFFECTS_FILE, "phase_g_clergy",     gen_effects_phase_g("clergy"),   dry_run)
    replace_section(EFFECTS_FILE, "phase_g_burghers",   gen_effects_phase_g("burghers"), dry_run)
    replace_section(EFFECTS_FILE, "phase_g_commoners",  gen_effects_phase_g("commoners"),dry_run)

def run_economy_local(dry_run: bool) -> None:
    replace_section(ECONOMY_LOCAL_FILE, "demand_rows", gen_economy_local_demand_rows(), dry_run)

TARGETS = {
    "location":        run_location,
    "tooltips":        run_tooltips,
    "gls":             run_gls,
    "scarcity_icons":  run_scarcity_icons,
    "effects":         run_effects,
    "economy_local":   run_economy_local,
}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default="all", choices=["all"] + list(TARGETS.keys()))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runners = (
        [fn for name, fn in TARGETS.items() if name != "location"]
        if args.target == "all"
        else [TARGETS[args.target]]
    )
    for runner in runners:
        runner(args.dry_run)

if __name__ == "__main__":
    main()
