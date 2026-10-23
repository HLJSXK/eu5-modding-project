"""Generate the SOL four-section row, maps/tooltips, localization and ranking caches.

Pure source generation: renderer modules are used only by the separate UI checks.
The visual contract is ai_gui_assessment/prototypes/living_standard_4sections/DESIGN.md.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TARGET_ROOTS = {name: ROOT / "src" / name for name in ("stable", "sol_standalone")}
UTF8_BOM = b"\xef\xbb\xbf"
ESTATES = ["nobles", "clergy", "burghers", "commoners", "tribesmen"]
W = 440                 # tooltip body width
PANEL_W = 570
PENDING_BODY_W = PANEL_W - 20  # contextual tooltip's 10px content margins
ROW_Y = 130
ROW_H = 36
GLORP_ROOT = ROOT / ".eu5-base/reference_mods/3601047146/in_game/gui/glorp.gui"
FOUR_SECTION_SOURCE = ROOT / "ai_gui_assessment/prototypes/living_standard_4sections/build.py"
_four_section_module = None


def four_section_module():
    """Load the reviewed four-section source without running its renderer."""
    global _four_section_module
    if _four_section_module is None:
        spec = importlib.util.spec_from_file_location("sol_lshud4_source", FOUR_SECTION_SOURCE)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {FOUR_SECTION_SOURCE}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _four_section_module = module
    return _four_section_module


# ------------------------------------------------------------------ expressions
def V(name, scope="Player"):
    return f"{scope}.MakeScope.GetVariable('{name}').GetValue"


def IS(name, scope="Player"):
    return f"{scope}.MakeScope.GetVariable('{name}').IsSet"


def G(name):
    return f"GetGlobalVariable('{name}').GetValue"


def fp(x):
    return f"'(CFixedPoint){x}'"


READY = IS("sol_ls_pci")
YOY_READY = IS("sol_ls_pci_yoy")
TIER_READY = f"And({READY}, {IS('sol_ls_tier')})"
RANK_READY = f"And({READY}, And({IS('sol_ls_rank')}, GetGlobalVariable('sol_ls_rank_count').IsSet))"


def tier_select(prefix):
    v = V("sol_ls_tier")
    return (f"[SelectLocalization(GreaterThan_CFixedPoint({v}, {fp(1.5)}), '{prefix}_HIGH', "
            f"SelectLocalization(GreaterThan_CFixedPoint({v}, {fp(0.5)}), '{prefix}_MID', '{prefix}_LOW'))]")


def trend_select(prefix, var="sol_ls_pci_yoy_class"):
    v = V(var)
    return (f"[SelectLocalization(GreaterThan_CFixedPoint({v}, {fp(1.5)}), '{prefix}_BIG_UP', "
            f"SelectLocalization(GreaterThan_CFixedPoint({v}, {fp(0)}), '{prefix}_UP', "
            f"SelectLocalization(GreaterThan_CFixedPoint({v}, {fp(-1.5)}), '{prefix}_DOWN', '{prefix}_BIG_DOWN')))]")


def tier_visible(level):
    v = V("sol_ls_tier")
    if level == 2:
        return f"[GreaterThan_CFixedPoint({v}, {fp(1.5)})]"
    if level == 1:
        return f"[And(GreaterThan_CFixedPoint({v}, {fp(0.5)}), LessThan_CFixedPoint({v}, {fp(1.5)}))]"
    return f"[LessThan_CFixedPoint({v}, {fp(0.5)})]"


TIER_TEX = {0: "gfx/interface/sol_proto/tier_need.dds",
            1: "gfx/interface/sol_proto/tier_daily.dds",
            2: "gfx/interface/sol_proto/tier_lux.dds"}
PENDING_TEX = "gfx/interface/icons/sol/sol_living_standard.dds"


def tier_icons(size):
    """Three mutually exclusive tier icons, or the SOL emblem before the first snapshot."""
    icons = "\n".join(
        f'\t\t\ticon = {{ size = {{ 100% 100% }} texture = "{TIER_TEX[t]}" texture_density = 2 '
        f'visible = "{tier_visible(t)}" alwaystransparent = yes }}' for t in (0, 1, 2))
    return (f"widget = {{\n\t\tsize = {{ {size} {size} }}\n\t\tparentanchor = center\n"
            f"\t\twidget = {{ size = {{ 100% 100% }} visible = \"[{TIER_READY}]\"\n{icons}\n\t\t}}\n"
            f"\t\ticon = {{ size = {{ 100% 100% }} texture = \"{PENDING_TEX}\" texture_density = 2 alpha = 0.6 "
            f"visible = \"[Not({TIER_READY})]\" alwaystransparent = yes }}\n\t}}")


def medallion(size, inner):
    return f"""widget = {{
	size = {{ {size} {size} }}
	background = {{ texture = "gfx/interface/component_tiles/hud_corners/circle_background.dds" texture_density = 2 modify_texture = {{ using = color_intense_bg_blue_texture }} }}
	{tier_icons(inner)}
	icon = {{ size = {{ 100% 100% }} texture = "[GetGraphicalCultureTexture('circle_frame')]" texture_density = 2 alwaystransparent = yes }}
}}"""


def text(t, w=None, h=None, fs=None, align="left|nobaseline", fmt=None, raw=False, font=None, extra=""):
    parts = ["text_single = {"]
    if w is not None:
        parts.append(f"size = {{ {w} {h or 20} }} autoresize = no")
    if fs:
        parts.append(f"fontsize = {fs}")
    if font:
        parts.append(f"using = {font}")
    parts.append(f"align = {align}")
    if fmt:
        parts.append(f'default_format = "{fmt}"')
    parts.append(f'{"raw_text" if raw else "text"} = "{t}"')
    if extra:
        parts.append(extra)
    parts.append("}")
    return " ".join(parts)


def gold_rule(w):
    return f"widget = {{ size = {{ {w} 1 }} background = {{ using = color_gold_texture alpha = 0.45 }} }}"


def outline(w, h, alpha_fill=0.10):
    edges = "".join(
        f" widget = {{ size = {{ {sw} {sh} }} position = {{ {x} {y} }} background = {{ using = color_gold_texture alpha = 0.6 }} }}"
        for sw, sh, x, y in ((w, 1, 0, 0), (w, 1, 0, h - 1), (1, h, 0, 0), (1, h, w - 1, 0)))
    return f"widget = {{ ignore_layout = yes size = {{ {w} {h} }} background = {{ using = color_gold_texture alpha = {alpha_fill} }}{edges} }}"


BAR = ('progresstexture = "gfx/interface/sol_proto/bar_{c}.dds" noprogresstexture = "gfx/interface/sol_proto/bar_track.dds" '
       'texture_density = 2 spriteType = Corneredstretched spriteborder = {{ 12 0 }}')


# ------------------------------------------------------------------ GUI
def diverging(var, w=150):
    half = w // 2
    neg = f"[FixedPointToFloat(Min_CFixedPoint(Max_CFixedPoint(Multiply_CFixedPoint({V(var)}, {fp(-5)}), {fp(0)}), {fp(1)}))]"
    pos = f"[FixedPointToFloat(Min_CFixedPoint(Max_CFixedPoint(Multiply_CFixedPoint({V(var)}, {fp(5)}), {fp(0)}), {fp(1)}))]"
    return f"""widget = {{ size = {{ {w} 14 }}
						hbox = {{ size = {{ {w} 10 }} position = {{ 0 2 }} spacing = 0
							progressbar = {{ size = {{ {half} 10 }} min = 0 max = 1 invertprogress = yes value = "{neg}" {BAR.format(c='red')} }}
							progressbar = {{ size = {{ {half} 10 }} min = 0 max = 1 value = "{pos}" {BAR.format(c='green')} }}
						}}
						widget = {{ size = {{ 2 14 }} position = {{ {half - 1} 0 }} background = {{ texture = "gfx/interface/sol_proto/bar_tick.dds" texture_density = 2 }} }}
					}}"""


def estate_row(e):
    return f"""
				hbox = {{ name = "sol_lshud_estate_{e}" size = {{ {W} 26 }} visible = "[GreaterThan_CFixedPoint({V('sol_ls_pop_' + e)}, {fp(0)})]" spacing = 6
					{text('SOL_ESTATE_' + e.upper(), 84, 26)}
					{text(f'[{V("sol_ls_pci_" + e)}|2] @gold!', 82, 26, align='right|nobaseline', fmt='#high', raw=True)}
					widget = {{ size = {{ 8 1 }} }}
					widget = {{ size = {{ 248 26 }}
						hbox = {{ name = "sol_lshud_estate_yoy_{e}" size = {{ 248 26 }} spacing = 6 visible = "[{YOY_READY}]"
							{diverging('sol_ls_pci_yoy_' + e)}
							{text(f'[{V("sol_ls_pci_yoy_" + e)}|+=1%]', 58, 26, align='right|nobaseline', raw=True)}
							{text(trend_select('SOL_LSHUD_TREND_ICON', 'sol_ls_pci_yoy_class_' + e), 26, 26, align='right|nobaseline')}
						}}
						{text('SOL_LSHUD_YOY_PENDING', 248, 26, fs=12, fmt='#weak', align='right|nobaseline', extra=f'visible = "[Not({YOY_READY})]"')}
					}}
				}}"""


def ladder_row(name, ctx, visible, self_row=False):
    rel = (f"[FixedPointToFloat(Divide_CFixedPoint({V('sol_ls_pci', 'Country')}, "
           f"Max_CFixedPoint({G('sol_ls_top_pci')}, {fp(0.01)})))]")
    bar = BAR.format(c="gold" if self_row else "steel")
    hl = outline(W, 26) if self_row else ""
    return f"""
				hbox = {{ name = "{name}" size = {{ {W} 26 }} visible = "{visible}" spacing = 6
					datacontext = "[{ctx}]"
					{hl}
					{text(f"[{V('sol_ls_rank', 'Country')}|0]", 34, 26, align='right|nobaseline', fmt='#weak', raw=True)}
					{text('[Country.GetNameWithNoTooltip]', 150, 26, fmt='#high' if self_row else None, raw=True)}
					progressbar = {{ size = {{ 150 8 }} min = 0 max = 1 value = "{rel}" {bar} }}
					expand = {{}}
					{text(f"[{V('sol_ls_pci', 'Country')}|2]", 60, 26, align='right|nobaseline', raw=True)}
					widget = {{ size = {{ 4 1 }} }}
				}}"""


def neighbour(slot):
    return (f"Player.MakeScope.GetVariable('sol_ls_{slot}').GetCountry",
            f"[{IS('sol_ls_' + slot)}]")


def _row_divider() -> str:
    return f"widget = {{ size = {{ 1 {ROW_H - 14} }} background = {{ using = color_gold_texture alpha = 0.35 }} }}"


def leftrow_source() -> str:
    """Compact Living Standard readout beneath the nine left-panel tabs."""
    closed = f"[And3(IsPlayerValid, Not(Or(LeftView.IsShown, LeftView.IsSideAttached)), GreaterThan_CFixedPoint(Player.MakeScope.ScriptValue('sol_ls_hud_enabled'), {fp(0)}))]"
    return f"""# Generated by scripts/gen_sol_lshud.py - do not edit.
# Living Standard row below the left-panel tab buttons; detail hover reuses SOL_LSHUD_tooltip.

widget = {{
\tname = "sol_lshud_leftrow_root"
\tsize = {{ 100% 100% }}
\tlayer = bottom
\talwaystransparent = yes
\tvisible = "{closed}"

\twidget = {{
\t\tname = "sol_lshud_leftrow"
\t\tsize = {{ {PANEL_W} {ROW_H} }}
\t\tposition = {{ 0 {ROW_Y} }}
\t\talwaystransparent = no
\t\ttooltipwidget = {{ using = SOL_LSHUD_tooltip }}
\t\tusing = Animation_Show_Hide_UI
\t\tblockoverride "on_hide_ui" {{ position_x = -{PANEL_W} alpha = 0 }}
\t\tblockoverride "on_show_ui" {{ position_x = 0 alpha = 1 }}
\t\tusing = bg_panel_bar
\t\twidget = {{ size = {{ {PANEL_W} 1 }} position = {{ 0 {ROW_H - 1} }} background = {{ using = color_gold_texture alpha = 0.55 }} }}

\t\thbox = {{ name = "sol_lshud_leftrow_ready" size = {{ {PANEL_W} {ROW_H} }} margin = {{ 10 0 }} spacing = 8 visible = "[{READY}]"
\t\t\twidget = {{ size = {{ 30 30 }}
\t\t\t\tbackground = {{ texture = "gfx/interface/component_tiles/hud_corners/circle_background.dds" texture_density = 2 modify_texture = {{ using = color_intense_bg_blue_texture }} }}
{tier_icons(22)}
\t\t\t\ticon = {{ size = {{ 100% 100% }} texture = "[GetGraphicalCultureTexture('circle_frame')]" texture_density = 2 alwaystransparent = yes }}
\t\t\t}}
\t\t\t{text('SOL_LSHUD_ROW_LABEL', 66, 22, fs=15, font='Font_Type_Headers')}
\t\t\t{text(tier_select('SOL_LSHUD_ROW_TIER'), 30, 22, fs=15, extra=f'visible = "[{TIER_READY}]"')}
\t\t\t{text('SOL_LSHUD_ROW_TIER_PENDING', 30, 22, fs=13, fmt='#weak', extra=f'visible = "[Not({TIER_READY})]"')}
\t\t\t{_row_divider()}
\t\t\t{text('SOL_LSHUD_ROW_PCI_LABEL', 52, 22, fs=12, fmt='#weak')}
\t\t\t{text(f"[{V('sol_ls_pci')}|2] @gold!", 76, 24, fs=17, font='Font_Type_Headers', fmt='#high', raw=True)}
\t\t\t{_row_divider()}
\t\t\t{text('SOL_LSHUD_ROW_YOY_LABEL', 28, 22, fs=12, fmt='#weak')}
\t\t\twidget = {{ size = {{ 82 22 }}
\t\t\t\thbox = {{ name = "sol_lshud_row_yoy" size = {{ 82 22 }} spacing = 8 visible = "[{YOY_READY}]"
\t\t\t\t\t{text(trend_select('SOL_LSHUD_TREND_ICON'), 18, 22, fs=14, align='center|nobaseline')}
\t\t\t\t\t{text(f"[{V('sol_ls_pci_yoy')}|+=1%]", 56, 22, fs=15, raw=True)}
\t\t\t\t}}
\t\t\t\t{text('SOL_LSHUD_YOY_PENDING', 82, 22, fs=12, fmt='#weak', extra=f'name = "sol_lshud_row_yoy_pending" visible = "[Not({YOY_READY})]"')}
\t\t\t}}
\t\t\t{_row_divider()}
\t\t\t{text('SOL_LSHUD_ROW_RANK', 120, 22, fs=14, extra=f'visible = "[{RANK_READY}]"')}
\t\t\t{text('SOL_LSHUD_ROW_RANK_PENDING', 120, 22, fs=13, fmt='#weak', extra=f'visible = "[Not({RANK_READY})]"')}
\t\t\texpand = {{}}
\t\t}}

\t\thbox = {{ name = "sol_lshud_leftrow_pending" size = {{ {PANEL_W} {ROW_H} }} margin = {{ 10 0 }} spacing = 8 visible = "[Not({READY})]"
\t\t\twidget = {{ size = {{ 30 30 }}
\t\t\t\tbackground = {{ texture = "gfx/interface/component_tiles/hud_corners/circle_background.dds" texture_density = 2 modify_texture = {{ using = color_intense_bg_blue_texture }} }}
{tier_icons(22)}
\t\t\t\ticon = {{ size = {{ 100% 100% }} texture = "[GetGraphicalCultureTexture('circle_frame')]" texture_density = 2 alwaystransparent = yes }}
\t\t\t}}
\t\t\t{text('SOL_LSHUD_ROW_LABEL', 66, 22, fs=15, font='Font_Type_Headers')}
\t\t\t{_row_divider()}
\t\t\t{text('SOL_LSHUD_ROW_PENDING', None, None, fs=13, fmt='#weak')}
\t\t\texpand = {{}}
\t\t}}
\t}}
}}
"""


def glorp_compat_source() -> str:
    """Shift Glorp UI's own stats bar and toggle while preserving their source bodies."""
    try:
        source = GLORP_ROOT.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing vendored Glorp UI GUI reference: {GLORP_ROOT}") from exc
    lines = [
        "# Generated by scripts/gen_sol_lshud.py - do not edit.",
        "# Preserves the vendored Glorp UI bodies and moves its stats bar and toggle below the SOL row.",
        "# Requires SOL to load after Glorp UI; the two overrides are unused without Glorp UI.",
        "",
        "Types SOLLivingStandardGlorpCompat {",
    ]
    for name in ("left_panel_info_bar", "left_panel_info_toggle"):
        body = _extract_widget_type(source, name)
        lines.extend([
            f"\ttype {name} = widget {{",
            "\t\tallow_outside = yes",
            f"\t\tposition = {{ 0 {ROW_H} }}",
            "\t\twidget = {",
            body,
            "\t\t}",
            "\t}",
            "",
        ])
    lines.extend(["}", ""])
    return "\n".join(lines)


def _extract_widget_type(source: str, name: str) -> str:
    match = re.search(rf"\btype\s+{re.escape(name)}\s*=\s*widget\s*\{{", source)
    if not match:
        raise ValueError(f"Glorp UI type not found: {name}")
    depth, index = 1, match.end()
    quoted = escaped = False
    while index < len(source) and depth:
        char = source[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "#":
            newline = source.find("\n", index)
            index = len(source) if newline < 0 else newline
            continue
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        index += 1
    if depth:
        raise ValueError(f"Unbalanced braces in Glorp UI type {name}")
    return source[match.end():index - 1].strip("\r\n")


def _legacy_tooltip_source():
    rank = V("sol_ls_rank")
    up = f"[GreaterThan_CFixedPoint({V('sol_ls_pci_yoy_class')}, {fp(0)})]"
    down = f"[LessThan_CFixedPoint({V('sol_ls_pci_yoy_class')}, {fp(0)})]"
    top1_visible = f"[And(GetGlobalVariable('sol_ls_top_1').IsSet, GreaterThan_CFixedPoint({rank}, {fp(3)}))]"
    rows = [ladder_row("sol_lshud_top_1", "GetGlobalVariable('sol_ls_top_1').GetCountry", top1_visible)]
    rows.append(f"""
				hbox = {{ size = {{ {W} 14 }} visible = "[GreaterThan_CFixedPoint({rank}, {fp(4)})]"
					{text('SOL_LSHUD_ELLIPSIS', 34, 14, align='right|nobaseline', fmt='#weak')}
					expand = {{}}
				}}""")
    for slot in ("above_2", "above_1"):
        rows.append(ladder_row(f"sol_lshud_{slot}", *neighbour(slot)))
    rows.append(ladder_row("sol_lshud_self", "Player", "yes", self_row=True))
    for slot in ("below_1", "below_2"):
        rows.append(ladder_row(f"sol_lshud_{slot}", *neighbour(slot)))

    return f"""template SOL_LSHUD_tooltip {{
	ContextualTooltipType = {{
		blockoverride "tooltip_title" {{
			hbox = {{
				name = "sol_lshud_hero"
				size = {{ {W + 20} 104 }}
				layoutpolicy_horizontal = expanding
				margin = {{ 14 10 }}
				spacing = 14
				using = bg_contextual_tooltip_header
				{medallion(80, 58)}
				vbox = {{ layoutpolicy_vertical = expanding visible = "[{READY}]"
					{text(tier_select('SOL_LSHUD_TITLE'), 190, 24, fs=18, font='Font_Type_Headers', extra=f'visible = "[{TIER_READY}]"')}
					{text('SOL_LSHUD_LABEL', 190, 24, fs=18, font='Font_Type_Headers', extra=f'visible = "[Not({TIER_READY})]"')}
					{text(f"[{V('sol_ls_pci')}|2] @gold!", 190, 40, fs=32, font='Font_Type_Headers', fmt='#high', raw=True)}
					{text('SOL_LSHUD_UNIT', 190, 18, fs=12, fmt='#weak')}
				}}
				vbox = {{ layoutpolicy_vertical = expanding visible = "[Not({READY})]"
					expand = {{}}
					{text('SOL_LSHUD_LABEL', 190, 24, fs=18, font='Font_Type_Headers')}
					{text('SOL_LSHUD_PENDING_SHORT', 190, 24, fs=15, fmt='#weak')}
					expand = {{}}
				}}
				expand = {{}}
				widget = {{ name = "sol_lshud_pill" size = {{ 116 76 }} visible = "[{YOY_READY}]"
					widget = {{ size = {{ 116 76 }} visible = "{up}" background = {{ using = color_mid_green_texture alpha = 0.28 }} }}
					widget = {{ size = {{ 116 76 }} visible = "{down}" background = {{ using = color_mid_red_texture alpha = 0.28 }} }}
					vbox = {{ size = {{ 116 76 }} margin = {{ 6 6 }}
						{text(trend_select('SOL_LSHUD_TREND'), 104, 22, fs=15, align='center|nobaseline')}
						{text(f"[{V('sol_ls_pci_yoy')}|+=1%]", 104, 26, fs=22, align='center|nobaseline', font='Font_Type_Headers', raw=True)}
						{text('SOL_LSHUD_PREV_SHORT', 104, 18, fs=12, align='center|nobaseline', fmt='#weak')}
					}}
				}}
				vbox = {{ name = "sol_lshud_yoy_pending" visible = "[And({READY}, Not({YOY_READY}))]"
					{text('SOL_LSHUD_ROW_YOY_LABEL', 116, 24, fs=15, align='center|nobaseline')}
					{text('SOL_LSHUD_YOY_PENDING', 116, 24, fs=12, align='center|nobaseline', fmt='#weak')}
				}}
			}}
		}}
		blockoverride "tooltip_content" {{
			vbox = {{
				name = "sol_lshud_pending_body"
				visible = "[Not({READY})]"
				minimumsize = {{ {PENDING_BODY_W} -1 }}
				layoutpolicy_horizontal = expanding
				text_multi = {{ name = "sol_lshud_pending_text" layoutpolicy_horizontal = expanding max_width = {PENDING_BODY_W} autoresize = yes text = "SOL_LSHUD_PENDING_BODY" }}
			}}
			vbox = {{
				name = "sol_lshud_body"
				visible = "[{READY}]"
				spacing = 2
				hbox = {{ size = {{ {W} 22 }}
					{text('SOL_LSHUD_SECTION_ESTATES_YOY', 260, 22, fmt='#S', font='Font_Type_Headers')}
					expand = {{}}
					{text('SOL_LSHUD_SCALE_20', 160, 22, align='right|nobaseline', fs=12, fmt='#weak')}
				}}
				{gold_rule(W)}
{''.join(estate_row(e) for e in ESTATES)}
				widget = {{ size = {{ 1 8 }} }}
				hbox = {{ size = {{ {W} 22 }}
					{text('SOL_LSHUD_SECTION_WORLD', 140, 22, fmt='#S', font='Font_Type_Headers')}
					expand = {{}}
					{text('SOL_LSHUD_PERCENTILE', 290, 22, align='right|nobaseline', extra=f'visible = "[{RANK_READY}]"')}
				}}
				{gold_rule(W)}
				vbox = {{ name = "sol_lshud_ranking" visible = "[{RANK_READY}]" spacing = 2
{''.join(rows)}
				}}
				text_multi = {{ name = "sol_lshud_rank_pending" visible = "[Not({RANK_READY})]" max_width = {W} autoresize = yes text = "SOL_LSHUD_RANK_PENDING" }}
				widget = {{ size = {{ 1 6 }} }}
				text_multi = {{ visible = "[{RANK_READY}]" max_width = {W} autoresize = yes fontsize = 12 default_format = "#weak" text = "SOL_LSHUD_FOOTNOTE" }}
				text_multi = {{ visible = "[Not({RANK_READY})]" max_width = {W} autoresize = yes fontsize = 12 default_format = "#weak" text = "SOL_LSHUD_FOOTNOTE_PENDING" }}
			}}
		}}
	}}
}}
"""


def gui_source() -> str:
    """Ship the reviewed four-section row and its four contextual tooltips."""
    source = four_section_module()
    rendered = (source.row_source() + source.tooltip_income() + source.tooltip_power()
                + source.tooltip_goods() + source.tooltip_rank()).replace(
                    "- design prototype only.", "- generated by scripts/gen_sol_lshud.py; edit the four-section source.")
    return "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"


# ------------------------------------------------------------------ localization
P = "Player.MakeScope.GetVariable"
LOC = {
    "SOL_LSHUD_ROW_LABEL": "生活水平",
    "SOL_LSHUD_ROW_TIER_LOW": "#N 低#!",
    "SOL_LSHUD_ROW_TIER_MID": "#Y 中#!",
    "SOL_LSHUD_ROW_TIER_HIGH": "#P 高#!",
    "SOL_LSHUD_ROW_TIER_PENDING": "—",
    "SOL_LSHUD_ROW_PCI_LABEL": "人均收入",
    "SOL_LSHUD_ROW_YOY_LABEL": "同比",
    "SOL_LSHUD_ROW_RANK": f"世界 #high [{P}('sol_ls_rank').GetValue|0]#! / [GetGlobalVariable('sol_ls_rank_count').GetValue|0]",
    "SOL_LSHUD_ROW_RANK_PENDING": "排行待更新",
    "SOL_LSHUD_ROW_PENDING": "等待首次计算",
    "SOL_LSHUD_YOY_PENDING": "暂无去年数据",
    "SOL_LSHUD_LABEL": "生活水平",
    "SOL_LSHUD_TITLE_LOW": "生活水平：#N 低#! [Player.MakeScope.ScriptValue('sol_ls_sol_display')|1]",
    "SOL_LSHUD_TITLE_MID": "生活水平：#Y 中#! [Player.MakeScope.ScriptValue('sol_ls_sol_display')|1]",
    "SOL_LSHUD_TITLE_HIGH": "生活水平：#P 高#! [Player.MakeScope.ScriptValue('sol_ls_sol_display')|1]",
    "SOL_LSHUD_UNIT": "每千人每年净收入",
    "SOL_LSHUD_TREND_BIG_UP": "@arrow_bonus_tier_2! #P 大增长#!",
    "SOL_LSHUD_TREND_UP": "@arrow_bonus_tier_1! #P 增长#!",
    "SOL_LSHUD_TREND_DOWN": "@arrow_malus_tier_1! #N 降低#!",
    "SOL_LSHUD_TREND_BIG_DOWN": "@arrow_malus_tier_2! #N 大降低#!",
    "SOL_LSHUD_TREND_ICON_BIG_UP": "@arrow_bonus_tier_2!",
    "SOL_LSHUD_TREND_ICON_UP": "@arrow_bonus_tier_1!",
    "SOL_LSHUD_TREND_ICON_DOWN": "@arrow_malus_tier_1!",
    "SOL_LSHUD_TREND_ICON_BIG_DOWN": "@arrow_malus_tier_2!",
    "SOL_LSHUD_PREV_SHORT": f"一年前 [{P}('sol_ls_pci_prev').GetValue|2]",
    "SOL_LSHUD_SECTION_ESTATES_YOY": "各阶层人均收入与同比",
    "SOL_LSHUD_SCALE_20": "条形满格 = ±20%",
    "SOL_LSHUD_SECTION_WORLD": "全球位置",
    "SOL_LSHUD_PERCENTILE": f"第 #high [{P}('sol_ls_rank').GetValue|0]#! / [GetGlobalVariable('sol_ls_rank_count').GetValue|0] · 高于 [{P}('sol_ls_percentile').GetValue|0%] 的国家",
    "SOL_LSHUD_ELLIPSIS": "⋯",
    "SOL_LSHUD_PENDING_SHORT": "等待首次计算",
    "SOL_LSHUD_PENDING_BODY": "人均收入在首次计算后即可显示；同比需要去年同月数据。全球排行每年 1 月 1 日刷新，首次初始化或手动全局重算时也会更新。",
    "SOL_LSHUD_RANK_PENDING": "全球排行与等级将在下一次 1 月 1 日刷新后显示。",
    "SOL_LSHUD_FOOTNOTE": ("人均收入 = 各阶层月净收入之和 ÷ 人口（千人）× 12，已扣建筑维护费。生活水平 = 千人均年流动资金 + 生活水平修正。生活水平等级以世界人口加权平均生活水平 "
                           "[GetGlobalVariable('sol_ls_world_sol').GetValue|2] 为基准：低于其 75% 为低，高于其 133% 为高。"
                           "同比：≥ +5% 大增长，0 ~ +5% 增长，−5% ~ 0 降低，≤ −5% 大降低；暂无去年同月数据时不显示。玩家按月、AI 按计算频率设置刷新（默认周年）。排行每年 1 月 1 日更新。"),
    "SOL_LSHUD_FOOTNOTE_PENDING": "人均收入 = 各阶层月净收入之和 ÷ 人口（千人）× 12，已扣建筑维护费。玩家按月、AI 按计算频率设置刷新（默认周年）；同比需要去年同月数据。",
}

LOC_ENGLISH = {
    "SOL_LSHUD_ROW_LABEL": "Living Standard",
    "SOL_LSHUD_ROW_TIER_LOW": "#N Low#!",
    "SOL_LSHUD_ROW_TIER_MID": "#Y Medium#!",
    "SOL_LSHUD_ROW_TIER_HIGH": "#P High#!",
    "SOL_LSHUD_ROW_TIER_PENDING": "—",
    "SOL_LSHUD_ROW_PCI_LABEL": "Income / person",
    "SOL_LSHUD_ROW_YOY_LABEL": "YoY",
    "SOL_LSHUD_ROW_RANK": f"World #high [{P}('sol_ls_rank').GetValue|0]#! / [GetGlobalVariable('sol_ls_rank_count').GetValue|0]",
    "SOL_LSHUD_ROW_RANK_PENDING": "Ranking pending",
    "SOL_LSHUD_ROW_PENDING": "Awaiting first calculation",
    "SOL_LSHUD_YOY_PENDING": "No prior-year data",
    "SOL_LSHUD_LABEL": "Living Standard",
    "SOL_LSHUD_TITLE_LOW": "Living Standard: #N Low#! [Player.MakeScope.ScriptValue('sol_ls_sol_display')|1]",
    "SOL_LSHUD_TITLE_MID": "Living Standard: #Y Medium#! [Player.MakeScope.ScriptValue('sol_ls_sol_display')|1]",
    "SOL_LSHUD_TITLE_HIGH": "Living Standard: #P High#! [Player.MakeScope.ScriptValue('sol_ls_sol_display')|1]",
    "SOL_LSHUD_UNIT": "Annual net income per 1,000 people",
    "SOL_LSHUD_TREND_BIG_UP": "@arrow_bonus_tier_2! #P Strong rise#!",
    "SOL_LSHUD_TREND_UP": "@arrow_bonus_tier_1! #P Rise#!",
    "SOL_LSHUD_TREND_DOWN": "@arrow_malus_tier_1! #N Fall#!",
    "SOL_LSHUD_TREND_BIG_DOWN": "@arrow_malus_tier_2! #N Strong fall#!",
    **{key: value for key, value in LOC.items() if key.startswith("SOL_LSHUD_TREND_ICON_")},
    "SOL_LSHUD_PREV_SHORT": f"Year ago [{P}('sol_ls_pci_prev').GetValue|2]",
    "SOL_LSHUD_SECTION_ESTATES_YOY": "Estate income and annual change",
    "SOL_LSHUD_SCALE_20": "Full bar = ±20%",
    "SOL_LSHUD_SECTION_WORLD": "World position",
    "SOL_LSHUD_PERCENTILE": f"#high [{P}('sol_ls_rank').GetValue|0]#! / [GetGlobalVariable('sol_ls_rank_count').GetValue|0] · Above [{P}('sol_ls_percentile').GetValue|0%] of countries",
    "SOL_LSHUD_ELLIPSIS": "⋯",
    "SOL_LSHUD_PENDING_SHORT": "Awaiting first calculation",
    "SOL_LSHUD_PENDING_BODY": "Income appears after the first calculation. Annual change needs data from the same month last year. World rankings refresh on 1 January, at initialization and on manual global recalculation.",
    "SOL_LSHUD_RANK_PENDING": "World rankings and tiers will appear after the next 1 January refresh.",
    "SOL_LSHUD_FOOTNOTE": (
        "Income per person = monthly net estate income ÷ population (thousands) × 12, after building maintenance. "
        "Living standard = annual liquid funds per 1,000 people + SOL modifier. Living-standard tiers use the population-weighted world average of [GetGlobalVariable('sol_ls_world_sol').GetValue|2]: "
        "low below 75%, high above 133%. Annual change: ≥ +5% strong rise; 0 to +5% rise; −5% to 0 fall; ≤ −5% strong fall. "
        "Annual change is unavailable without data from the same month last year. Player figures refresh monthly; AI follows the calculation frequency setting (annual by default). Rankings refresh on 1 January."
    ),
    "SOL_LSHUD_FOOTNOTE_PENDING": (
        "Income per person = monthly net estate income ÷ population (thousands) × 12, after building maintenance. "
        "Player figures refresh monthly; AI follows the calculation frequency setting (annual by default). Annual change needs data from the same month last year."
    ),
}

# The design prototype owns the four-section key set. Keep its Chinese copy in
# the reviewed source and provide the production English counterpart here.
_FOUR_SECTION_EN = {
    "SOL_LSHUD4_S4_VALUE": f"#high [{P}('sol_ls_rank').GetValue|0]#! / [GetGlobalVariable('sol_ls_rank_count').GetValue|0]",
    "SOL_LSHUD4_S4_PENDING": "Pending",
    "SOL_LSHUD4_DASH": "—",
    "SOL_LSHUD4_NATION": "Nation",
    "SOL_LSHUD4_TIER_PENDING": "Living-standard tier pending the 1 January ranking",
    "SOL_LSHUD4_PREV_LINE": f"Year ago per-capita [{P}('sol_ls_pci_prev').GetValue|2]; national annual net income [{P}('sol_ls_income_all').GetValue|0] @gold!",
    "SOL_LSHUD4_T1_TITLE": "Income and annual change",
    "SOL_LSHUD4_T1_SUB": "Per capita = annual net income / population (thousands)",
    "SOL_LSHUD4_T1_TABLE": "Nation and estates",
    "SOL_LSHUD4_COL_ESTATE": "Estate",
    "SOL_LSHUD4_COL_POP": "Population (k)",
    "SOL_LSHUD4_COL_INCOME": "Annual income",
    "SOL_LSHUD4_COL_PCI": "Per capita",
    "SOL_LSHUD4_COL_SOL": "Living std.",
    "SOL_LSHUD4_COL_YOY": "Annual change",
    "SOL_LSHUD4_COL_RANK": "World rank",
    "SOL_LSHUD4_COL_PERCENTILE": "Percentile",
    "SOL_LSHUD4_COL_BEST": "World best",
    "SOL_LSHUD4_T1_NOTE": "Net income includes estate building maintenance. Annual change compares the same month last year: >= +5% strong rise, 0 to +5% rise, -5% to 0 fall, <= -5% strong fall.",
    "SOL_LSHUD4_T2_TITLE": "Purchasing power",
    "SOL_LSHUD4_T2_SUB": "Available funds / baseline consumption - 1",
    "SOL_LSHUD4_T2_NOTE": "0% means the baseline basket is exactly affordable; -100% means no available funds. The row shows the national total.",
    "SOL_LSHUD4_T3_TITLE": "Main spending and substitute groups",
    "SOL_LSHUD4_T3_SPEND": "Highest spending goods (by total price)",
    "SOL_LSHUD4_T3_SUB": "Monthly spending total; substitute-group supply is shown below",
    "SOL_LSHUD4_T3_SPEND_TOTAL": f"National spending [{P}('sol_ls_spend_total').GetValue|1] @gold! / month",
    "SOL_LSHUD4_T4_TITLE": "World ranking",
    "SOL_LSHUD4_T4_SUB": "Ranked by living standard; updated each 1 January",
    "SOL_LSHUD4_T4_NATION": "National rank",
    "SOL_LSHUD4_T4_ESTATES": "Estate ranks",
    "SOL_LSHUD4_T4_ESTATES_HINT": "Living standard compared with the same estate worldwide",
    "SOL_LSHUD4_T4_NOTE": "Estate ranks include only countries with that estate. The percentile bar is the share of countries surpassed.",
}
for _key, _value in four_section_module().LOC.items():
    if _key.startswith("SOL_LSHUD4_ESTATE_RANK_"):
        _FOUR_SECTION_EN[_key] = _value.replace("#high", "#high").replace("GetValue|0]#! / [GetGlobalVariable", "GetValue|0]#! / [GetGlobalVariable")
LOC.update(four_section_module().LOC)
LOC_ENGLISH.update(_FOUR_SECTION_EN)


def outputs(targets: tuple[str, ...] = tuple(TARGET_ROOTS)) -> dict[Path, bytes]:
    from sol_lshud_income_source import render_income_values
    from sol_lshud_ranking_source import render_values, render_world_ranking
    from gen_sol_ls_gui import UI_STRINGS
    import sol_map_modes_source as maps

    if LOC.keys() != LOC_ENGLISH.keys():
        raise ValueError("HUD localization keys must match between languages")
    # Localization bindings must follow the same country as the reused GUI.
    country_translations = {
        "simp_chinese": dict(UI_STRINGS["simp_chinese"], **LOC),
        "english": dict(UI_STRINGS["english"], **LOC_ENGLISH),
    }
    country_keys = {key for strings in country_translations.values()
                    for key, value in strings.items() if "Player." in value}
    result = {}
    for target in targets:
        root = TARGET_ROOTS[target]
        result[root / "in_game/gui/SOL_lshud.gui"] = gui_source().encode("utf-8")
        result[root / "in_game/gui/SOL_lshud_glorp_compat.gui"] = glorp_compat_source().encode("utf-8")
        result[root / "in_game/gui/scripted_widgets/SOL_lshud_scripted_widgets.txt"] = UTF8_BOM + (
            "# Generated by scripts/gen_sol_lshud.py - do not edit.\n"
            "gui/SOL_lshud.gui = sol_lshud4_root\n"
        ).encode("utf-8")
        result[root / "in_game/common/scripted_effects/D_SOL_lshud_ranking.txt"] = UTF8_BOM + render_world_ranking().encode("utf-8")
        result[root / "in_game/common/script_values/SOL_lshud_ranking_values.txt"] = UTF8_BOM + (render_values(standalone=target == "sol_standalone") + "\n" + render_income_values()).encode("utf-8")
        result[root / "in_game/gfx/map/map_modes/SOL_map_modes.txt"] = UTF8_BOM + maps.render_map_modes(standalone=target == "sol_standalone").encode("utf-8")
        result[root / "in_game/common/script_values/SOL_map_values.txt"] = UTF8_BOM + maps.render_map_values().encode("utf-8")
        result[root / "in_game/gui/SOL_map_tooltips.gui"] = maps.render_map_tooltips(four_section_module(), country_keys).encode("utf-8")
        # Reuse the existing complete-mip SOL emblem for the map menu's ID lookup.
        emblem = (root / "main_menu/gfx/interface/icons/map_modes/sol_living_standard.dds").read_bytes()
        for mode in maps.MAP_MODES[1:]:
            result[root / f"main_menu/gfx/interface/icons/map_modes/{mode}.dds"] = emblem
        for language, translations in (("simp_chinese", LOC), ("english", LOC_ENGLISH)):
            lines = [f"l_{language}:", " # Generated by scripts/gen_sol_lshud.py - do not edit."]
            lines += [f' {key}: "{value}"' for key, value in translations.items()]
            path = root / f"main_menu/localization/{language}/SOL_lshud_l_{language}.yml"
            result[path] = UTF8_BOM + ("\n".join(lines) + "\n").encode("utf-8")
            map_loc = dict(maps.LOC if language == "simp_chinese" else maps.LOC_ENGLISH)
            map_loc.update({key + "_MAP": country_translations[language][key].replace("Player.", "Scope.GetCountry.")
                            for key in sorted(country_keys)})
            lines = [f"l_{language}:", " # Generated by scripts/gen_sol_lshud.py; edit scripts/sol_map_modes_source.py."]
            lines += [f' {key}: "{value}"' for key, value in map_loc.items()]
            result[root / f"main_menu/localization/{language}/SOL_map_modes_l_{language}.yml"] = UTF8_BOM + ("\n".join(lines) + "\n").encode("utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=[*TARGET_ROOTS, "all"], default="all")
    parser.add_argument("--check", action="store_true", help="Check without writing files")
    args = parser.parse_args()
    targets = tuple(TARGET_ROOTS) if args.target == "all" else (args.target,)
    stale = []
    for path, payload in outputs(targets).items():
        label = path.relative_to(ROOT)
        if args.check:
            current = path.read_bytes() if path.exists() else None
            if current != payload:
                stale.append(label)
                print(f"[FAIL] Out of date: {label}")
            else:
                print(f"[OK] Up to date: {label}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            print(f"[OK] Written: {label}")
    if stale:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


