"""Generate and render the adopted HUD living-standard badge (design B, left-hung).

Writes sol_lshud.gui and sol_lshud_l_simp_chinese.yml next to this file,
adds the badge root to the offline vanilla HUD, and renders the badge, its
tooltip, and a hover composite for several data states.  All values are
invented mock data; the backend contract is in HANDOFF.md.

usage: python build.py [output_dir]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
sys.path.insert(0, str(WORKSPACE / ".eu5-base" / "ai_gui_assessment" / "renderer"))
os.environ.setdefault("EU5_RENDER_WORKSPACE", str(WORKSPACE))
os.environ.setdefault("EU5_RENDER_MOD_ROOT", str(WORKSPACE / "src" / "stable"))
sys.setrecursionlimit(20000)

GUI_FILE = HERE / "sol_lshud.gui"
LOC_FILE = HERE / "sol_lshud_l_simp_chinese.yml"
ESTATES = ["nobles", "clergy", "burghers", "commoners", "tribesmen"]
BADGE_POS = (636, 34)   # just right of the left country-banner flourish, hanging from the topbar
W = 440                 # tooltip body width


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
            f"\t\twidget = {{ size = {{ 100% 100% }} visible = \"[{READY}]\"\n{icons}\n\t\t}}\n"
            f"\t\ticon = {{ size = {{ 100% 100% }} texture = \"{PENDING_TEX}\" texture_density = 2 alpha = 0.6 "
            f"visible = \"[Not({READY})]\" alwaystransparent = yes }}\n\t}}")


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
    neg = f"[FixedPointToFloat(Min_CFixedPoint(Max_CFixedPoint(Multiply_CFixedPoint({V(var)}, {fp(-10)}), {fp(0)}), {fp(1)}))]"
    pos = f"[FixedPointToFloat(Min_CFixedPoint(Max_CFixedPoint(Multiply_CFixedPoint({V(var)}, {fp(10)}), {fp(0)}), {fp(1)}))]"
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
					{text('SOL_ESTATE_' + e.upper(), 104, 26)}
					{text(f'[{V("sol_ls_pci_" + e)}|2]', 62, 26, align='right|nobaseline', fmt='#high', raw=True)}
					widget = {{ size = {{ 8 1 }} }}
					{diverging('sol_ls_pci_yoy_' + e)}
					expand = {{}}
					{text(f'[{V("sol_ls_pci_yoy_" + e)}|+=1%]', 58, 26, align='right|nobaseline', raw=True)}
					{text(trend_select('SOL_LSHUD_TREND_ICON', 'sol_ls_pci_yoy_class_' + e), 26, 26, align='right|nobaseline')}
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


def gui_source():
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

    return f"""# Generated by ai_gui_assessment/prototypes/living_standard_hud/build.py - prototype only.
# Integration target: a scripted widget (in_game/gui/scripted_widgets/*.txt -> gui/<file>.gui = sol_lshud_root).

widget = {{
	name = "sol_lshud_root"
	size = {{ 100% 100% }}
	layer = topbar
	alwaystransparent = yes
	visible = "[And(IsPlayerValid, Not(And(IsLateralViewBlockingMapRendering, IsLateralViewFullScreen)))]"

	widget = {{
		name = "sol_lshud_badge"
		size = {{ 132 100 }}
		position = {{ {BADGE_POS[0]} {BADGE_POS[1]} }}
		alwaystransparent = yes
		allow_outside = yes

		widget = {{
			name = "sol_lshud_plate"
			size = {{ 132 30 }}
			position = {{ 0 60 }}
			alwaystransparent = no
			tooltipwidget = {{ using = SOL_LSHUD_tooltip }}
			background = {{ using = color_intense_bg_blue_texture alpha = 0.92 margin = {{ -3 -3 }} }}
			background = {{ texture = "gfx/interface/graphical_cultures/european_gfx/pause_label_frame.dds" texture_density = 2 spriteType = Corneredstretched spriteborder = {{ 26 0 }} }}
			hbox = {{ size = {{ 132 30 }} margin = {{ 16 0 }} spacing = 4 visible = "[{READY}]"
				expand = {{}}
				{text(f"[{V('sol_ls_pci')}|2]", None, None, fs=17, font='Font_Type_Headers', fmt='#high', raw=True)}
				{text(trend_select('SOL_LSHUD_TREND_ICON'), None, None, fs=14)}
				{text(f"[{V('sol_ls_pci_yoy')}|+=1%]", None, None, fs=12, raw=True)}
				expand = {{}}
			}}
			hbox = {{ size = {{ 132 30 }} visible = "[Not({READY})]"
				expand = {{}}
				{text('SOL_LSHUD_PENDING_SHORT', None, None, fs=14, fmt='#weak')}
				expand = {{}}
			}}
		}}

		widget = {{
			name = "sol_lshud_medallion"
			size = {{ 66 66 }}
			parentanchor = top|hcenter
			alwaystransparent = no
			tooltipwidget = {{ using = SOL_LSHUD_tooltip }}
			{medallion(66, 46)}
		}}
	}}
}}

template SOL_LSHUD_tooltip {{
	ContextualTooltipType = {{
		blockoverride "tooltip_title" {{
			hbox = {{
				name = "sol_lshud_hero"
				size = {{ {W + 20} 104 }}
				margin = {{ 14 10 }}
				spacing = 14
				using = bg_contextual_tooltip_header
				{medallion(80, 58)}
				vbox = {{ layoutpolicy_vertical = expanding visible = "[{READY}]"
					{text(tier_select('SOL_LSHUD_TITLE'), 190, 24, fs=18, font='Font_Type_Headers')}
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
				widget = {{ name = "sol_lshud_pill" size = {{ 116 76 }} visible = "[{READY}]"
					widget = {{ size = {{ 116 76 }} visible = "{up}" background = {{ using = color_mid_green_texture alpha = 0.28 }} }}
					widget = {{ size = {{ 116 76 }} visible = "{down}" background = {{ using = color_mid_red_texture alpha = 0.28 }} }}
					vbox = {{ size = {{ 116 76 }} margin = {{ 6 6 }}
						{text(trend_select('SOL_LSHUD_TREND'), 104, 22, fs=15, align='center|nobaseline')}
						{text(f"[{V('sol_ls_pci_yoy')}|+=1%]", 104, 26, fs=22, align='center|nobaseline', font='Font_Type_Headers', raw=True)}
						{text('SOL_LSHUD_PREV_SHORT', 104, 18, fs=12, align='center|nobaseline', fmt='#weak')}
					}}
				}}
			}}
		}}
		blockoverride "tooltip_content" {{
			vbox = {{
				name = "sol_lshud_pending_body"
				visible = "[Not({READY})]"
				text_multi = {{ max_width = {W} autoresize = yes text = "SOL_LSHUD_PENDING_BODY" }}
			}}
			vbox = {{
				name = "sol_lshud_body"
				visible = "[{READY}]"
				spacing = 2
				hbox = {{ size = {{ {W} 22 }}
					{text('SOL_LSHUD_SECTION_ESTATES_YOY', 260, 22, fmt='#S', font='Font_Type_Headers')}
					expand = {{}}
					{text('SOL_LSHUD_SCALE_10', 160, 22, align='right|nobaseline', fs=12, fmt='#weak')}
				}}
				{gold_rule(W)}
{''.join(estate_row(e) for e in ESTATES)}
				widget = {{ size = {{ 1 8 }} }}
				hbox = {{ size = {{ {W} 22 }}
					{text('SOL_LSHUD_SECTION_WORLD', 140, 22, fmt='#S', font='Font_Type_Headers')}
					expand = {{}}
					{text('SOL_LSHUD_PERCENTILE', 290, 22, align='right|nobaseline')}
				}}
				{gold_rule(W)}
{''.join(rows)}
				widget = {{ size = {{ 1 6 }} }}
				text_multi = {{ max_width = {W} autoresize = yes fontsize = 12 default_format = "#weak" text = "SOL_LSHUD_FOOTNOTE" }}
			}}
		}}
	}}
}}
"""


# ------------------------------------------------------------------ localization
P = "Player.MakeScope.GetVariable"
LOC = {
    "SOL_LSHUD_LABEL": "生活水平",
    "SOL_LSHUD_TITLE_LOW": "生活水平：#N 低#!",
    "SOL_LSHUD_TITLE_MID": "生活水平：#Y 中#!",
    "SOL_LSHUD_TITLE_HIGH": "生活水平：#P 高#!",
    "SOL_LSHUD_UNIT": "每千人每年收入",
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
    "SOL_LSHUD_SCALE_10": "条形满格 = ±10%",
    "SOL_LSHUD_SECTION_WORLD": "全球位置",
    "SOL_LSHUD_PERCENTILE": f"第 #high [{P}('sol_ls_rank').GetValue|0]#! / [GetGlobalVariable('sol_ls_rank_count').GetValue|0] · 高于 [{P}('sol_ls_percentile').GetValue|0%] 的国家",
    "SOL_LSHUD_ELLIPSIS": "⋯",
    "SOL_LSHUD_PENDING_SHORT": "待年度结算",
    "SOL_LSHUD_PENDING_BODY": "本国的生活水平将在下一次年度结算（本国周年日）后显示，全球排行在每年 1 月 1 日更新。",
    "SOL_LSHUD_FOOTNOTE": ("人均收入 = 各阶层净收入之和 ÷ 人口（千人），按年计。等级以世界人口加权平均 "
                           "[GetGlobalVariable('sol_ls_world_pci').GetValue|2] 为基准：低于其 75% 为低，高于其 133% 为高。"
                           "同比：≥ +5% 大增长，0 ~ +5% 增长，−5% ~ 0 降低，≤ −5% 大降低。本国数值在周年日更新，排行每年 1 月 1 日更新。"),
}


def write_sources():
    GUI_FILE.write_text(gui_source(), encoding="utf-8-sig")
    lines = ["l_simp_chinese:"] + [f' {k}: "{v}"' for k, v in LOC.items()]
    LOC_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


# ------------------------------------------------------------------ mock data
BOARD = [
    ("VEN", "威尼斯", 4.92, .031, 2), ("GEN", "热那亚", 4.37, -.012, 2), ("FLO", "佛罗伦萨", 3.95, .058, 2),
    ("MLO", "米兰", 3.41, .004, 2), ("BUR", "勃艮第", 2.88, .022, 2), ("FLA", "佛兰德斯", 2.74, -.067, 2),
    ("MAM", "马穆鲁克", 2.51, .009, 2), ("ENG", "英格兰", 2.33, .041, 2), ("ARA", "阿拉贡", 2.12, -.018, 1),
    ("BOH", "波希米亚", 1.98, .027, 1), ("CAS", "卡斯蒂利亚", 1.91, .013, 1), ("HUN", "匈牙利", 1.86, .045, 1),
    ("FRA", "法兰西", 1.84, -.031, 1), ("POL", "波兰", 1.80, .062, 1),
]


def country(tag, name, rank, pci, yoy, tier):
    return {"__type__": "Country", "Self": tag, "GetNameWithNoTooltip": name, "GetName": name,
            "MakeScope.GetVariable('sol_ls_rank').GetValue": rank,
            "MakeScope.GetVariable('sol_ls_pci').GetValue": pci,
            "MakeScope.GetVariable('sol_ls_pci_yoy').GetValue": yoy,
            "MakeScope.GetVariable('sol_ls_tier').GetValue": tier}


PLAYER_VARS = {
    "sol_ls_pci": 1.86, "sol_ls_pci_prev": 1.78, "sol_ls_pci_yoy": .045,
    "sol_ls_pci_yoy_class": 1, "sol_ls_tier": 1, "sol_ls_rank": 12, "sol_ls_percentile": .87,
    "sol_ls_pop_nobles": 41, "sol_ls_pop_clergy": 88, "sol_ls_pop_burghers": 520, "sol_ls_pop_commoners": 7770,
    "sol_ls_pop_tribesmen": 0,
    "sol_ls_pci_nobles": 38.40, "sol_ls_pci_clergy": 14.20, "sol_ls_pci_burghers": 6.85, "sol_ls_pci_commoners": 1.12,
    "sol_ls_pci_tribesmen": 0,
    "sol_ls_pci_yoy_nobles": .061, "sol_ls_pci_yoy_clergy": .018, "sol_ls_pci_yoy_burghers": -.023,
    "sol_ls_pci_yoy_commoners": .041, "sol_ls_pci_yoy_tribesmen": 0,
    "sol_ls_pci_yoy_class_nobles": 2, "sol_ls_pci_yoy_class_clergy": 1, "sol_ls_pci_yoy_class_burghers": -1,
    "sol_ls_pci_yoy_class_commoners": 1, "sol_ls_pci_yoy_class_tribesmen": 1,
}
GLOBAL_VARS = {"sol_ls_rank_count": 87, "sol_ls_world_pci": 1.62, "sol_ls_top_pci": 4.92}

STATES = {
    # suffix: (player variable overrides, player rank, data ready)
    "": ({}, 12, True),
    "_high_bigup": ({"sol_ls_tier": 2, "sol_ls_pci_yoy_class": 2, "sol_ls_pci_yoy": .081, "sol_ls_pci_prev": 1.72}, 12, True),
    "_low_bigdown": ({"sol_ls_tier": 0, "sol_ls_pci_yoy_class": -2, "sol_ls_pci_yoy": -.070, "sol_ls_pci_prev": 2.00}, 12, True),
    "_rank2": ({"sol_ls_tier": 2, "sol_ls_rank": 2, "sol_ls_percentile": .99, "sol_ls_pci": 4.50}, 2, True),
    "_pending": ({}, 12, False),
}


def state_mocks(overrides, rank, ready):
    pv = dict(PLAYER_VARS, **overrides)
    board = [b for b in BOARD if b[0] != "HUN"]
    board.insert(rank - 1, ("HUN", "匈牙利", pv["sol_ls_pci"], pv["sol_ls_pci_yoy"], pv["sol_ls_tier"]))
    countries = [country(tag, n, i + 1, p, y, t) for i, (tag, n, p, y, t) in enumerate(board)]
    me = rank - 1
    slots = {"above_1": me - 1, "above_2": me - 2, "below_1": me + 1, "below_2": me + 2}
    slots = {k: countries[i] for k, i in slots.items() if 0 <= i < len(countries)}
    return [
        (r"Player\.Self", "HUN"),
        (r"Player\.MakeScope\.GetVariable\('sol_ls_pci'\)\.IsSet", ready),
        (r"Player\.MakeScope\.GetVariable\('sol_ls_(\w+)'\)\.IsSet", lambda m: ready and m[1] in slots),
        # The renderer evaluates a hidden row's datacontext too; the game does not.
        (r"Player\.MakeScope\.GetVariable\('sol_ls_(\w+)'\)\.GetCountry", lambda m: slots.get(m[1], countries[0])),
        (r"Player\.MakeScope\.GetVariable\('(\w+)'\)\.GetValue", lambda m: pv[m[1]] if ready else 0),
        (r"GetGlobalVariable\('sol_ls_top_(\d+)'\)\.IsSet", lambda m: int(m[1]) <= len(countries)),
        (r"GetGlobalVariable\('sol_ls_top_(\d+)'\)\.GetCountry", lambda m: countries[int(m[1]) - 1]),
        (r"GetGlobalVariable\('(\w+)'\)\.GetValue", lambda m: GLOBAL_VARS[m[1]]),
        (r"Player", countries[me]),
    ]


# ------------------------------------------------------------------ rendering
def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else WORKSPACE / "ai_gui_assessment/images/living_standard_hud_20261016"
    out.mkdir(parents=True, exist_ok=True)
    write_sources()

    from PIL import Image
    from eu5_gui_renderer import hud
    from eu5_gui_renderer.data import Evaluator, Formats, Loc, TextIcons
    from eu5_gui_renderer.engine import Engine
    from eu5_gui_renderer.gui import Expander, GuiDB, collect_files, dump
    from eu5_gui_renderer.textures import TEXTURES

    db = GuiDB(collect_files() + [GUI_FILE])
    loc = Loc()
    for line in LOC_FILE.read_text(encoding="utf-8-sig").splitlines()[1:]:
        m = Loc.LINE_RE.match(line)
        if m:
            loc.d[m.group(1)] = m.group(2)
    node = next(n for n in db.roots[str(GUI_FILE)]
                if n.is_block() and any(c.key == "name" and c.value == "sol_lshud_root" for c in n.value))

    bar_crops = []
    for suffix, (overrides, rank, ready) in STATES.items():
        log = []
        ex = Expander(db, log)
        root = hud.build(db, ex, 1920, 1080)
        widget = ex.build(node.key, node.value, {}, str(GUI_FILE), node.line)
        root.children.append(widget)
        ev = Evaluator(state_mocks(overrides, rank, ready) + hud.mocks(), loc, log)
        eng = Engine(ex, ev, loc, Formats(), TextIcons(), 1.0)
        eng.place(root, 0, 0, 1920, 1080)
        img = Image.new("RGBA", (1920, 1080), (29, 35, 42, 255))
        eng.render(root, img)

        badge = next(e for e in hud.walk(widget) if e.props.get("name") == "sol_lshud_badge")
        owner = next(e for e in hud.walk(badge) if e.tooltipwidget is not None)
        tip = ex.build_lazy(owner.tooltipwidget)
        tw, th = eng.measure(tip, None)["hint"]
        tx = max(4, min(round(badge.x), 1920 - round(tw) - 4))
        ty = round(badge.y + badge.h + 6)
        eng.place(tip, tx, ty, tw, th)
        hover = img.copy()
        eng.render(tip, hover)

        pad = 16
        alone = Image.new("RGBA", (round(tw) + 2 * pad, round(th) + 2 * pad), (40, 52, 46, 255))
        eng.place(tip, pad, pad, tw, th)
        eng.render(tip, alone)

        tag = f"B{suffix}"
        if not suffix:
            img.save(out / f"{tag}_hud.png")
            img.crop((0, 0, 1920, 300)).save(out / f"{tag}_hud_top.png")
            (out / f"{tag}_tree.txt").write_text("\n".join(dump(root)) + "\n", encoding="utf-8")
        hover.crop((0, 0, 1920, min(1080, ty + round(th) + 20))).save(out / f"{tag}_hover.png")
        alone.save(out / f"{tag}_tooltip.png")
        bx, by, bw, bh = round(badge.x), round(badge.y), round(badge.w), round(badge.h)
        crop = img.crop((max(0, bx - 70), 0, bx + bw + 70, by + bh + 6))
        crop.save(out / f"{tag}_bar.png")
        bar_crops.append(crop)
        issues = sorted({x for x in log if "sol_ls" in x or "SOL_LSHUD" in x or "TYPE ERROR" in x or "INVALID" in x})
        print(f"{tag}: badge {bx},{by} {bw}x{bh}; tooltip {round(tw)}x{round(th)}; prototype issues: {len(issues)}")
        for issue in issues:
            print("   ", issue)

    sheet = Image.new("RGBA", (sum(c.width for c in bar_crops) + 12 * len(bar_crops), max(c.height for c in bar_crops)),
                      (20, 24, 30, 255))
    x = 0
    for crop in bar_crops:
        sheet.paste(crop, (x, 0))
        x += crop.width + 12
    sheet.save(out / "B_states.png")
    print("missing textures:", sorted(TEXTURES.missing))
    print("output:", out)


if __name__ == "__main__":
    main()
