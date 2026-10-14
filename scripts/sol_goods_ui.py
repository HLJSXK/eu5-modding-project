#!/usr/bin/env python3
"""Render the SOL substitute-group goods block shared by every SOL economy surface.

The surfaces show goods grouped by demand tier and demand group rather than as one
flat lattice: each F-route tier contains labelled group cards with member goods,
so a player reads a shortage straight off the row.

Three consumers rely on this module:

  scripts/gen_sol_ls_gui.py       builds both SOL economy surfaces
  scripts/gen_sol_pp_compat.py    rebuilds the block with its victuals good added
  scripts/gen_sol_jtg_compat.py   rebuilds the block with the 26 JTG goods added

Keeping one renderer means all three agree on cell markup. That matters because the
compat submods re-render this exact block: a shape change here silently breaks them
otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sol_goods_order import GROUP_ORDER, GROUP_MEMBERS, GROUP_TIERS, PRIMARY_GROUP  # noqa: E402
from sol_substitution import CORE  # noqa: E402

# Goods support @good! through engine registration. These standalone widgets need
# a fixed footprint and positioned substitution markers; use their standard DDS.
ICON_DIR = "gfx/interface/icons/trade_goods"

# Full and dim icons are mutually exclusive. A translucent copy drawn over an
# opaque original cannot dim it. Static alpha avoids an unverified numeric binding.
DIM_ALPHA = "0.3"

# Six 18px icons + five 1px gaps + two 4px margins fit a 122px card.
# Four cards + three 4px gaps give a 500px content column on both surfaces.
ICON_W = 18
LOCATION_CARD_W = 122
COUNTRY_CARD_W = 122
LOCATION_ICONS_PER_ROW = 6
COUNTRY_ICONS_PER_ROW = 6
GOODS_CONTENT_W = 500

# Player-facing group names, [english, simp_chinese]. Kept short: the label column is
# 80px and a long name would shrink to fontsize_min and look broken.
GROUP_LABELS: dict[str, tuple[str, str]] = {
    "basic_clothing": ("Clothing", "基本衣物"),
    "standard_clothing": ("Fine cloth", "体面衣物"),
    "crude_goods": ("Crude", "粗制品"),
    "household": ("Household", "家用"),
    "heating": ("Heating", "取暖"),
    "staple": ("Staple", "主粮"),
    "luxury_food": ("Delicacy", "珍馐"),
    "condiments": ("Seasoning", "调味"),
    "protein": ("Protein", "蛋白质"),
    "intoxicants": ("Drink", "酒与烟草"),
    "luxury_drinks": ("Fine drink", "奢侈饮品"),
    "luxury_goods": ("Luxury", "奢侈品"),
    "spices": ("Spice", "香料"),
    "precious": ("Precious", "贵金属"),
    "treasures": ("Treasure", "珍宝"),
    "medicine": ("Medicine", "药材"),
    "ritual": ("Ritual", "祭祀"),
    "knowledge": ("Knowledge", "书写"),
    "weapons": ("Weapons", "武器"),
    "mounts": ("Mounts", "坐骑"),
}

TIER_LABELS: dict[str, tuple[str, str]] = {
    "required": ("Required", "必需"),
    "daily": ("Daily", "日用"),
    "luxury": ("Luxury", "奢侈"),
}

TIER_TEXTURES = {
    "required": "tier_need.dds",
    "daily": "tier_daily.dds",
    "luxury": "tier_lux.dds",
}


def _consumed_expr(variable_map: str, good: str, scope: str) -> str:
    entry = f"GetVariableFromGlobalVariableMap('{variable_map}_{good}', {scope})"
    return (
        f"GreaterThan_CFixedPoint(Select_CFixedPoint({entry}.IsSet, "
        f"{entry}.GetValue, '(CFixedPoint)0'), '(CFixedPoint)0')"
    )


def _good_cell(indent: str, good: str, consumed: str, scope: str) -> list[str]:
    """Supply state, country substitution direction and context-specific hover data."""
    texture = f"{ICON_DIR}/icon_goods_{good}.dds"
    country = "Location.GetOwner.MakeScope" if scope.startswith("Location.") else scope
    multiplier = f"[{country}.ScriptValue('sol_substitute_{good}_display')|2]" if good in CORE else "1.00"
    tooltip = f"@{good}! [Localize('{good}')]\\n[Localize('SOL_GOOD_SUB_{good}')]\\n[Localize('SOL_SUB_MULTIPLIER')]: {multiplier}"
    tooltip += "\\n" + substitution_status(country)
    if scope.startswith("Location."):
        weight = f"GetVariableFromGlobalVariableMap('sol_market_substitute_weight_{good}', {scope})"
        tooltip += f"\\n[SelectLocalization({weight}.IsSet, 'SOL_SUB_PRICE_{good}', 'SOL_SUB_PRICE_PENDING')]"
    tooltip += "\\n[Localize('SOL_SUB_SCOPE_NOTE')]\\n[Localize('SOL_SUB_LEGEND_TOOLTIP')]"
    out = [
        f"{indent}widget = {{",
        f"{indent}\tsize = {{ {ICON_W} 18 }}",
        f'{indent}\ttooltip = "{tooltip}"',
        f'{indent}\ticon = {{ size = {{ 100% 100% }} parentanchor = center visible = "[{consumed}]" texture = "{texture}" }}',
        f'{indent}\ticon = {{ size = {{ 100% 100% }} parentanchor = center alpha = "{DIM_ALPHA}" '
        f'visible = "[Not({consumed})]" texture = "{texture}" }}',
    ]
    if good in CORE:
        value = f"{country}.ScriptValue('sol_substitute_{good}_display')"
        for op, marker in (("GreaterThan_CFixedPoint", "#G +#!"), ("LessThan_CFixedPoint", "#R -#!")):
            out.append(f'{indent}\ttext_single = {{ size = {{ 9 10 }} autoresize = no fontsize = 11 '
                       f'position = {{ 8 7 }} raw_text = "{marker}" '
                       f'visible = "[And({consumed}, {op}({value}, \'(CFixedPoint)1\'))]" }}')
    out.append(f"{indent}}}")
    return out


def substitution_status(country: str) -> str:
    value = f"{country}.ScriptValue('sol_substitute_status_display')"
    return (f"[SelectLocalization(GreaterThan_CFixedPoint({value}, '(CFixedPoint)1'), "
            f"'SOL_SUB_ACTIVE', SelectLocalization(GreaterThan_CFixedPoint({value}, "
            "'(CFixedPoint)0'), 'SOL_SUB_PENDING', 'SOL_SUB_DISABLED'))]")


def _group_row(indent: str, group: str | None, goods: list[str], variable_map: str, scope: str) -> list[str]:
    label = f"SOL_SUBGROUP_{group.upper()}" if group else "SOL_SUBGROUP_UNGROUPED"
    location = scope.startswith("Location.")
    card_w = LOCATION_CARD_W if location else COUNTRY_CARD_W
    icons_per_row = LOCATION_ICONS_PER_ROW if location else COUNTRY_ICONS_PER_ROW
    card_h = 48 + 19 * ((len(goods) - 1) // icons_per_row)
    count = "'(int32)0'"
    for good in goods:
        count = f"Add_int32({count}, Select_int32({_consumed_expr(variable_map, good, scope)}, '(int32)1', '(int32)0'))"
    out = [
        f"{indent}sol_group_row = {{",
        f"{indent}\tsize = {{ {card_w} {card_h} }}",
        f"{indent}\tlayoutpolicy_horizontal = fixed",
        f'{indent}\tblockoverride "sol_group_header" {{ size = {{ {card_w - 8} 17 }} layoutpolicy_horizontal = fixed }}',
        f'{indent}\tblockoverride "sol_group_label" {{ size = {{ {card_w - 38} 17 }} text = "{label}" tooltip = "{label}" }}',
        f'{indent}\tblockoverride "sol_group_count" {{ raw_text = "[{count}]/{len(goods)}" }}',
        f'{indent}\tblockoverride "sol_group_progress" {{ size = {{ {card_w - 8} 3 }} max = {len(goods)} value = "[{count}]" }}',
        f'{indent}\tblockoverride "sol_group_icons" {{',
    ]
    for start in range(0, len(goods), icons_per_row):
        row = goods[start : start + icons_per_row]
        out.append(f"{indent}\t\thbox = {{ size = {{ {len(row) * 19 - 1} 18 }} layoutpolicy_horizontal = fixed spacing = 1")
        for good in goods[start : start + icons_per_row]:
            out.extend(_good_cell(f"{indent}\t\t\t", good, _consumed_expr(variable_map, good, scope), scope))
        out.append(f"{indent}\t\t}}")
    out.append(f"{indent}\t}}")
    out.append(f"{indent}}}")
    return out


def _tier_header(indent: str, tier: str) -> list[str]:
    label = f"SOL_SUBTIER_{tier.upper()}"
    texture = TIER_TEXTURES[tier]
    return [
        f"{indent}hbox = {{ size = {{ -1 16 }} layoutpolicy_horizontal = expanding spacing = 5 margin = {{ 0 1 }}",
        f'{indent}\ticon = {{ size = {{ 16 16 }} texture = "gfx/interface/sol_proto/{texture}" texture_density = 2 }}',
        f'{indent}\ttext_single = {{ autoresize = yes fontsize = 11 align = left|nobaseline text = "{label}" }}',
        f"{indent}\texpand = {{}}",
        f"{indent}}}",
    ]


def render_group_columns(goods: list[str], variable_map: str, scope: str, indent: str) -> list[str]:
    """Render F-route groups in required, daily, and luxury tiers."""
    available = set(goods)
    out: list[str] = []
    for tier, tier_groups in GROUP_TIERS:
        rows = [(group, [good for good in GROUP_MEMBERS[group] if good in available])
                for group in tier_groups]
        rows = [(group, members) for group, members in rows if members]
        if not rows:
            continue
        out.extend(_tier_header(indent, tier))
        for start in range(0, len(rows), 4):
            out.append(f"{indent}hbox = {{")
            out.append(f"{indent}\tlayoutpolicy_horizontal = expanding")
            out.append(f"{indent}\tspacing = 4")
            for group, members in rows[start : start + 4]:
                out.extend(_group_row(f"{indent}\t", group, members, variable_map, scope))
            if len(rows[start : start + 4]) < 4:
                out.append(f"{indent}\texpand = {{}}")
            out.append(f"{indent}}}")
    # Compatibility-only goods have no F group; keep them in a final card row.
    ungrouped = list(dict.fromkeys(good for good in goods if good not in PRIMARY_GROUP))
    if ungrouped:
        cards = [ungrouped[start:start + 6] for start in range(0, len(ungrouped), 6)]
        for start in range(0, len(cards), 4):
            out.append(f"{indent}hbox = {{")
            out.append(f"{indent}\tlayoutpolicy_horizontal = expanding")
            out.append(f"{indent}\tspacing = 4")
            for members in cards[start:start + 4]:
                out.extend(_group_row(f"{indent}\t", None, members, variable_map, scope))
            if len(cards[start:start + 4]) < 4:
                out.append(f"{indent}\texpand = {{}}")
            out.append(f"{indent}}}")
    return out


def group_label_keys() -> list[str]:
    """Every group label key the block can emit, for loc generation."""
    return [f"SOL_SUBGROUP_{group.upper()}" for group in GROUP_ORDER] + ["SOL_SUBGROUP_UNGROUPED"]


def render_goods_vbox(goods: list[str], variable_map: str, scope: str, indent: str) -> str:
    """The whole goods vbox, so the compat generators rebuild it instead of patching it.

    The compat submods each add goods (PP adds victuals, JTG adds 26), and goods are now
    grouped, so a good cannot be inserted by line any more - the group it belongs to has
    to be recomputed. Both generators therefore replace the whole vbox with this
    rendering, which keeps all three surfaces identical in structure.
    """
    lines = [
        f"{indent}vbox = {{",
        f"{indent}\tlayoutpolicy_horizontal = expanding",
        f"{indent}\tmargin = {{ 0 2 }}",
        f"{indent}\tspacing = 4",
    ]
    if not scope.startswith("Location."):
        status = f"{scope}.ScriptValue('sol_substitute_status_display')"
        summary = (f"[SelectLocalization(GreaterThan_CFixedPoint({status}, '(CFixedPoint)1'), "
                   f"'SOL_SUB_SUMMARY', SelectLocalization(GreaterThan_CFixedPoint({status}, "
                   "'(CFixedPoint)0'), 'SOL_SUB_PENDING', 'SOL_SUB_DISABLED'))]")
        lines.append(f'{indent}\ttext_single = {{ layoutpolicy_horizontal = expanding fontsize = 12 '
                     f'raw_text = "{summary}" tooltip = "SOL_SUB_SUMMARY_TOOLTIP" }}')
        lines.append(f'{indent}\ttext_single = {{ layoutpolicy_horizontal = expanding fontsize = 11 '
                     f'text = "SOL_SUB_LEGEND" tooltip = "SOL_SUB_LEGEND_TOOLTIP" }}')
    lines.extend(render_group_columns(goods, variable_map, scope, f"{indent}\t"))
    lines.append(f'{indent}\ttextbox = {{ using = tooltip_text_block_template max_width = {GOODS_CONTENT_W} fontsize = 11 text = "SOL_F_GOODS_SUPPLY_NOTE" }}')
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def replace_goods_vbox(
    text: str, section_marker: str, goods: list[str], variable_map: str, scope: str
) -> str:
    """Replace the vbox following `section_marker` with the grouped goods block."""
    marker_index = text.find(section_marker)
    if marker_index < 0:
        raise ValueError(f"Section marker not found: {section_marker}")
    line_end = text.find("\n", marker_index)
    match = re.search(r"(?m)^(?P<indent>[\t ]*)vbox\s*=\s*\{", text[line_end + 1 :])
    if not match:
        raise ValueError(f"Goods vbox not found after {section_marker}")
    vbox_start = line_end + 1 + match.start()
    brace_start = text.index("{", vbox_start)
    depth = 0
    vbox_end = -1
    for index in range(brace_start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                vbox_end = index
                break
    if vbox_end < 0:
        raise ValueError(f"Unbalanced braces in the goods vbox after {section_marker}")
    rendered = render_goods_vbox(goods, variable_map, scope, match.group("indent"))
    return text[:vbox_start] + rendered + text[vbox_end + 1 :]
