#!/usr/bin/env python3
"""Render the SOL substitute-group goods block shared by every SOL economy surface.

The surfaces show goods grouped by demand group rather than as one flat lattice:
each group is a labelled row with its member goods beside it, so a player reads a
shortage straight off the row.

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

from sol_goods_order import GROUP_ORDER, group_rows, ordered  # noqa: E402
from sol_substitution import CORE  # noqa: E402

# Goods support @good! through engine registration. These standalone widgets need
# a fixed footprint and positioned substitution markers; use their standard DDS.
ICON_DIR = "gfx/interface/icons/trade_goods"

# Full and dim icons are mutually exclusive. A translucent copy drawn over an
# opaque original cannot dim it. Static alpha avoids an unverified numeric binding.
DIM_ALPHA = "0.3"

GROUPS_PER_LINE = 2
ICON_W = 20
# sol_group_row: 216px total, 80px label, 2px gaps, including the trailing expand.
# Six icons fit; larger compatibility groups need explicit continuation rows.
ICONS_PER_GROUP_ROW = 6

# Player-facing group names, [english, simp_chinese]. Kept short: the label column is
# 80px and a long name would shrink to fontsize_min and look broken.
GROUP_LABELS: dict[str, tuple[str, str]] = {
    "basic_clothing": ("Clothing", "基本衣物"),
    "standard_clothing": ("Fine cloth", "标准衣物"),
    "crude_goods": ("Crude", "粗制品"),
    "household": ("Household", "家用器具"),
    "heating": ("Heating", "取暖"),
    "staple": ("Staple", "主粮"),
    "luxury_food": ("Delicacy", "奢侈食物"),
    "condiments": ("Seasoning", "调味品"),
    "protein": ("Protein", "蛋白质"),
    "intoxicants": ("Drink", "烈性饮品"),
    "luxury_drinks": ("Fine drink", "奢侈饮品"),
    "luxury_goods": ("Luxury", "奢侈品"),
    "spices": ("Spice", "香料"),
    "precious": ("Precious", "贵金属"),
    "treasures": ("Treasure", "珍宝"),
    "medicine": ("Medicine", "药材"),
    "ritual": ("Ritual", "祭祀用品"),
    "knowledge": ("Knowledge", "书籍纸张"),
    "weapons": ("Weapons", "武器"),
    "mounts": ("Mounts", "牲畜坐骑"),
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
        f"{indent}\tsize = {{ {ICON_W} 24 }}",
        f'{indent}\ttooltip = "{tooltip}"',
        f'{indent}\ticon = {{ size = {{ 100% 100% }} parentanchor = center visible = "[{consumed}]" texture = "{texture}" }}',
        f'{indent}\ticon = {{ size = {{ 100% 100% }} parentanchor = center alpha = "{DIM_ALPHA}" '
        f'visible = "[Not({consumed})]" texture = "{texture}" }}',
    ]
    if good in CORE:
        value = f"{country}.ScriptValue('sol_substitute_{good}_display')"
        for op, marker in (("GreaterThan_CFixedPoint", "#G +#!"), ("LessThan_CFixedPoint", "#R -#!")):
            out.append(f'{indent}\ttext_single = {{ size = {{ 10 12 }} autoresize = no fontsize = 12 '
                       f'position = {{ 10 12 }} raw_text = "{marker}" '
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
    out = [
        f"{indent}sol_group_row = {{",
        f'{indent}\tblockoverride "sol_group_label" {{ text = "{label}" }}',
        f'{indent}\tblockoverride "sol_group_icons" {{',
    ]
    for good in goods:
        out.extend(_good_cell(f"{indent}\t\t", good, _consumed_expr(variable_map, good, scope), scope))
    out.append(f"{indent}\t}}")
    out.append(f"{indent}}}")
    return out


def render_group_columns(goods: list[str], variable_map: str, scope: str, indent: str) -> list[str]:
    """Labelled groups with bounded icon rows, GROUPS_PER_LINE columns per line."""
    rows = [
        (group, members[start : start + ICONS_PER_GROUP_ROW])
        for group, members in group_rows(ordered(goods))
        for start in range(0, len(members), ICONS_PER_GROUP_ROW)
    ]
    out: list[str] = []
    for start in range(0, len(rows), GROUPS_PER_LINE):
        out.append(f"{indent}hbox = {{")
        out.append(f"{indent}\tlayoutpolicy_horizontal = expanding")
        out.append(f"{indent}\tspacing = 6")
        for group, members in rows[start : start + GROUPS_PER_LINE]:
            out.extend(_group_row(f"{indent}\t", group, members, variable_map, scope))
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
        f"{indent}\tmargin = {{ 10 2 }}",
        f"{indent}\tspacing = 1",
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
