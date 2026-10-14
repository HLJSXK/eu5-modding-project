#!/usr/bin/env python3
"""Generate sheet C goods tooltips for stable and standalone.

The shared goods_details keeps vanilla statistics and adds tier/group labels,
icon-and-name chips (including the current good), and the seven price preferences.
Only SpecificGoodsMarket_tooltip overrides the price section with a live market
ratio. Its vanilla file is preserved apart from that single insertion; generic
and card tooltips never acquire a fabricated market or consuming country.

LOCALIZATION
------------
Every good that can exist gets a key `SOL_GOOD_SUB_<good>`, generated from
data/goods_weights.csv plus the vanilla goods and the goods the compat submods add.
A good that belongs to no group keeps the explicit "no substitute group" string
for basket-cell hover. Graphical goods tooltips hide the entire substitution
section, including its heading, dividers and price preferences, for ungrouped goods.
This also handles unrelated third-party goods without a generated key.

Usage:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_goods_tooltip.py
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_goods_tooltip.py --check
"""

import argparse
import csv
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
STABLE = REPO_ROOT / "src" / "stable"
STANDALONE = REPO_ROOT / "src" / "sol_standalone"
TARGET_ROOTS = {"stable": STABLE, "sol_standalone": STANDALONE}
ALL_TARGETS = (STABLE, STANDALONE)
TARGETS = ALL_TARGETS

VANILLA_GOODS_DIR = REPO_ROOT / "reference_game_files" / "game" / "in_game" / "common" / "goods"
GOODS_WEIGHTS = REPO_ROOT / "data" / "goods_weights.csv"
VANILLA_GUI = (
    REPO_ROOT / "reference_game_files" / "game" / "main_menu" / "gui" / "shared" / "goods_details.gui"
)
VANILLA_MARKET_GUI = (
    REPO_ROOT / "reference_game_files/game/in_game/gui/shared/market_tooltips.gui"
)
GAME_GUI = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V"
    r"\game\main_menu\gui\shared\goods_details.gui"
)

UTF8_BOM = b"\xef\xbb\xbf"

from sol_goods_order import GROUP_TIERS
from sol_goods_ui import GROUP_LABELS as SHORT_GROUP_LABELS, TIER_LABELS

CONTENT_W = 420
PRICE_TIERS = (
    ("2", "<0.40", "r < 0.40", "G"),
    ("1.5", "<0.65", "0.40 <= r < 0.65", "G"),
    ("1.25", "<0.85", "0.65 <= r < 0.85", "G"),
    ("1", "0.85–1.30", "0.85 <= r <= 1.30", "E"),
    ("0.75", ">1.30", "1.30 < r <= 1.70", "R"),
    ("0.5", ">1.70", "1.70 < r <= 2.30", "R"),
    ("0.25", ">2.30", "r > 2.30", "R"),
)

# The compat submods add goods through INJECT blocks in their generated goods files.
MOD_GOODS_DIRS = [
    STABLE / "in_game" / "common" / "goods",
    REPO_ROOT / "src" / "sol_pp_compatibility_submod" / "in_game" / "common" / "goods",
    REPO_ROOT / "src" / "sol_jtg_compatibility_submod" / "in_game" / "common" / "goods",
    REPO_ROOT / "src" / "sol_mnt_compatibility_submod" / "in_game" / "common" / "goods",
]

# Group labels. The internal names come from data/goods_weights.csv; these are the
# player-facing strings, kept short so a good in three groups still fits the tooltip.
GROUP_LABELS = {
    "basic_clothing": ("Basic clothing", "基本衣物"),
    "standard_clothing": ("Standard clothing", "标准衣物"),
    "crude_goods": ("Crude goods", "粗制品"),
    "household": ("Household goods", "家用器具"),
    "heating": ("Heating", "取暖"),
    "staple": ("Staple food", "主粮"),
    "luxury_food": ("Luxury food", "奢侈食物"),
    "condiments": ("Condiments", "调味品"),
    "protein": ("Protein", "蛋白质"),
    "intoxicants": ("Intoxicants", "烈性饮品"),
    "luxury_drinks": ("Luxury drinks", "奢侈饮品"),
    "luxury_goods": ("Luxury goods", "奢侈品"),
    "spices": ("Spices", "香料"),
    "precious": ("Precious metals", "贵金属"),
    "treasures": ("Treasures", "珍宝"),
    "medicine": ("Medicine", "药材"),
    "ritual": ("Ritual", "祭祀用品"),
    "knowledge": ("Knowledge", "书籍纸张"),
    "weapons": ("Weapons", "武器"),
    "mounts": ("Mounts", "牲畜坐骑"),
}

HEADER = {
    "english": ("SOL_GOOD_SUBSTITUTES_HEADER", "#T Substitute groups#!"),
    "simp_chinese": ("SOL_GOOD_SUBSTITUTES_HEADER", "#T 替代组#!"),
}
NONE_LABEL = {
    "english": ("SOL_GOOD_SUB_NONE", "#E Not part of a substitute group#!"),
    "simp_chinese": ("SOL_GOOD_SUB_NONE", "#E 独立商品——不参与任何替代组#!"),
}


# --------------------------------------------------------------------------- data
def _memberships() -> tuple[dict[str, list[tuple[str, float]]], dict[str, list[str]]]:
    """good -> [(group, k_factor)], group -> [goods], in table order."""
    by_good: dict[str, list[tuple[str, float]]] = {}
    by_group: dict[str, list[str]] = {}
    with GOODS_WEIGHTS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            good = (row["good"] or "").strip()
            group = (row["group"] or "").strip()
            if not good or not group:
                continue
            by_good.setdefault(good, []).append((group, float(row["k_factor"] or 1.0)))
            by_group.setdefault(group, []).append(good)
    missing = sorted(set(by_group) - set(GROUP_LABELS))
    if missing:
        raise ValueError(f"Group has no player-facing label: {missing}")
    return by_good, by_group


def _vanilla_goods() -> set[str]:
    """Every top-level good defined by vanilla. INJECT blocks do not match."""
    goods: set[str] = set()
    if not VANILLA_GOODS_DIR.exists():
        return goods
    # Only top-level objects are goods, not demand_add/custom_tags children.
    pattern = re.compile(r"^([a-z][a-z_0-9]*)\s*=\s*\{")
    for path in sorted(VANILLA_GOODS_DIR.glob("*.txt")):
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.split("#", 1)[0]
            match = pattern.match(line)
            if match:
                goods.add(match.group(1))
    return goods


def _compat_goods() -> set[str]:
    """Goods the compat submods add, read from their generated INJECT blocks."""
    goods: set[str] = set()
    pattern = re.compile(r"^\s*INJECT:([a-z][a-z_0-9]*)\s*=\s*\{")
    for directory in MOD_GOODS_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.txt")):
            for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                match = pattern.match(line)
                if match:
                    goods.add(match.group(1))
    return goods


def _all_goods() -> list[str]:
    by_good, _ = _memberships()
    return sorted(set(by_good) | _vanilla_goods() | _compat_goods())


# ------------------------------------------------------------------------ gui text
def goods_block() -> str:
    """Static memberships and price legend; safe with only Goods in context."""
    by_good, by_group = _memberships()
    lines = [
        "\t# ---- SOL sheet C goods ---------------------------------------------------",
        f'\tvbox = {{ visible = "[{_member_condition(sorted(by_good))}]" layoutpolicy_horizontal = expanding spacing = 4',
        '\t\ttext_single = { size = { 420 23 } autoresize = no text = "SOL_GOOD_SUBSTITUTES_HEADER" fontsize = 15 align = left|nobaseline }',
        "\t\tdivider_center_gold = {}",
    ]
    for _, groups in GROUP_TIERS:
        for group in groups:
            members = by_group[group]
            lines += [
                f'\t\thbox = {{ visible = "[{_member_condition(members)}]" layoutpolicy_horizontal = expanding spacing = 4',
                f'\t\t\ttext_single = {{ size = {{ 108 27 }} autoresize = no fontsize = 13 fontsize_min = 11 align = left|nobaseline text = "SOL_GOOD_GROUP_{group}" tooltip = "SOL_GOOD_GROUP_{group}" }}',
                "\t\t\tvbox = { layoutpolicy_horizontal = expanding spacing = 2",
            ]
            # Explicit wrapping; a layout box does not wrap at its available width.
            for start in range(0, len(members), 4):
                lines.append("\t\t\t\thbox = { layoutpolicy_horizontal = expanding spacing = 2")
                for good in members[start:start + 4]:
                    lines.append(
                        '\t\t\t\t\ttext_single = { size = { 75 27 } autoresize = no fontsize = 13 fontsize_min = 11 align = left|nobaseline '
                        f'using = bg_number_container_bckg raw_text = "@{good}! [Localize(\'{good}\')]" tooltip = "{good}" }}'
                    )
                lines += ["\t\t\t\t\texpand = {}", "\t\t\t\t}"]
            lines += ["\t\t\t}", "\t\t}"]
    lines += [
        "\t}",
        '\tblock "sol_goods_price_context" { using = SOL_goods_price_tiers }',
    ]
    return "\n".join(lines) + "\n"


def _member_condition(goods: list[str]) -> str:
    """Explicit member allowlist; unknown, default and empty keys do not match."""
    condition = f"EqualTo_string(Goods.GetKey, '{goods[0]}')"
    for good in goods[1:]:
        condition = f"Or({condition}, EqualTo_string(Goods.GetKey, '{good}'))"
    return condition


def market_price_ratio() -> str:
    positive = "GreaterThan_CFixedPoint(Goods.GetDefaultMarketPrice, '(CFixedPoint)0')"
    return f"Divide_CFixedPoint(Market.GetPrice(Goods.Self), Select_CFixedPoint({positive}, Goods.GetDefaultMarketPrice, '(CFixedPoint)1'))"


def price_tier_condition(interval: str) -> str:
    """Compare actual prices to scaled base prices, as the runtime does.

    Dividing or formatting the ratio first can round a price across a boundary.
    The intervals also supply column tooltips, so the two stay consistent.
    """
    tokens = interval.split()
    operands = ["Market.GetPrice(Goods.Self)" if token == "r" else
                f"Multiply_CFixedPoint(Goods.GetDefaultMarketPrice, '(CFixedPoint){token}')"
                for token in tokens[::2]]
    comparisons = {"<": "LessThan_CFixedPoint", "<=": "LessThanOrEqualTo_CFixedPoint",
                   ">": "GreaterThan_CFixedPoint"}
    parts = [f"{comparisons[op]}({left}, {right})"
             for op, left, right in zip(tokens[1::2], operands, operands[1:])]
    inside = parts[0] if len(parts) == 1 else f"And({parts[0]}, {parts[1]})"
    return f"And(And(Market.IsValid, GreaterThan_CFixedPoint(Goods.GetDefaultMarketPrice, '(CFixedPoint)0')), {inside})"


def price_template(market: bool = False) -> str:
    grouped = sorted(_memberships()[0])
    lines = [
        f"\ntemplate {'SOL_goods_market_price_tiers' if market else 'SOL_goods_price_tiers'} {{",
        f'\tvbox = {{ visible = "[{_member_condition(grouped)}]" layoutpolicy_horizontal = expanding spacing = 4',
        '\t\ttext_single = { size = { 420 23 } autoresize = no text = "SOL_GOOD_PRICE_TIERS" fontsize = 15 align = left|nobaseline }',
        "\t\tdivider_center_gold = {}",
        "\t\thbox = { layoutpolicy_horizontal = expanding spacing = 2",
    ]
    for index, (weight, label, interval, color) in enumerate(PRICE_TIERS):
        lines.append(f'\t\t\tvbox = {{ size = {{ 58 40 }} layoutpolicy_horizontal = fixed spacing = 2 using = bg_number_container_bckg tooltip = "SOL_GOOD_PRICE_TIER_{index}"')
        if market:
            lines.append(
                f'\t\t\t\twidget = {{ name = "sol_price_tier_active_{index}" size = {{ 58 40 }} ignore_layout = yes '
                f'visible = "[{price_tier_condition(interval)}]" using = bg_square_gold_tile }}'
            )
        lines += [
            f'\t\t\t\ttext_single = {{ size = {{ 58 19 }} autoresize = no align = center fontsize = 13 raw_text = "#{color} ×{weight}#!" }}',
            f'\t\t\t\ttext_single = {{ size = {{ 58 17 }} autoresize = no align = center fontsize = 11 raw_text = "{label}" }}',
            "\t\t\t}",
        ]
    lines += ["\t\t}", "\t}", "}"]
    return "\n".join(lines) + "\n"


def market_price_block() -> str:
    grouped = _member_condition(sorted(_memberships()[0]))
    ratio = market_price_ratio()
    return (
        '\n\t\t\t# SOL: only this use site owns Market; generic goods stay static.\n'
        '\t\t\tblockoverride "sol_goods_price_context" {\n'
        '\t\t\t\tvbox = {\n'
        f'\t\t\t\t\tvisible = "[And(Market.IsValid, {grouped})]"\n'
        '\t\t\t\t\tlayoutpolicy_horizontal = expanding\n'
        '\t\t\t\t\tspacing = 4\n'
        '\t\t\t\t\tusing = SOL_goods_market_price_tiers\n'
        '\t\t\t\t\ttext_multi = {\n'
        '\t\t\t\t\t\tlayoutpolicy_horizontal = expanding\n'
        '\t\t\t\t\t\tautoresize = yes\n'
        '\t\t\t\t\t\talign = left|nobaseline\n'
        '\t\t\t\t\t\tvisible = "[GreaterThan_CFixedPoint(Goods.GetDefaultMarketPrice, \'(CFixedPoint)0\')]"\n'
        f'\t\t\t\t\t\tmax_width = {CONTENT_W}\n'
        '\t\t\t\t\t\tfontsize = 13\n'
        f'\t\t\t\t\t\traw_text = "[Localize(\'SOL_GOOD_MARKET_RATIO_PREFIX\')] #high [{ratio}|2]#! [Localize(\'SOL_GOOD_MARKET_RATIO_SUFFIX\')]"\n'
        '\t\t\t\t\t}\n'
        '\t\t\t\t}\n'
        '\t\t\t}\n'
    )


def inject_market(source: str) -> str:
    """Change only SpecificGoodsMarket_tooltip, preserving every vanilla block."""
    start = source.index("template SpecificGoodsMarket_tooltip {")
    # Put the override on the actual instance, alongside title/tooltip_content
    # overrides. An override nested in another override's raw contents is not
    # an instance override and is discarded by the renderer's expansion stage.
    needle = "\tContextualTooltipType = {\n"
    position = source.index(needle, start) + len(needle)
    block = "\n".join(line[1:] if line.startswith("\t") else line
                      for line in market_price_block().split("\n"))
    return source[:position] + block + source[position:]


def inject(source: str) -> str:
    """Insert the section at the end of the `goods_details` template body."""
    marker = "template goods_details {"
    if marker not in source:
        raise ValueError("Could not find `template goods_details` in the vanilla file")
    open_brace = source.index("{", source.index(marker))
    depth = 0
    close = -1
    for index in range(open_brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                close = index
                break
    if close < 0:
        raise ValueError("Unbalanced braces in `template goods_details`")
    return source[:close] + goods_block() + source[close:]


def gui_files(roots: tuple[Path, ...] = TARGETS) -> dict[Path, str]:
    source_path = VANILLA_GUI if VANILLA_GUI.exists() else GAME_GUI
    source = source_path.read_text(encoding="utf-8-sig", errors="replace")
    if "\ufeff" in source:
        source = source.replace("\ufeff", "")
    patched = inject(source) + price_template()
    relative = Path("main_menu") / "gui" / "shared" / "goods_details.gui"
    market_source = VANILLA_MARKET_GUI.read_text(encoding="utf-8-sig")
    market_relative = Path("in_game/gui/shared/market_tooltips.gui")
    return {**{root / relative: patched for root in roots},
            **{root / market_relative: inject_market(market_source) + price_template(market=True) for root in roots}}


# ------------------------------------------------------------------ localization
def _good_line(good: str, by_good: dict, by_group: dict, language: str) -> str:
    memberships = by_good.get(good)
    if not memberships:
        return NONE_LABEL[language][1]
    index = 0 if language == "english" else 1
    parts: list[str] = []
    for group, factor in memberships:
        peers = [other for other in by_group[group] if other != good]
        if not peers:
            continue
        label = GROUP_LABELS[group][index]
        icons = " ".join(f"@{peer}!" for peer in peers)
        suffix = "" if abs(factor - 1.0) < 1e-9 else f" #E x{factor:g}#!"
        parts.append(f"{label}: {icons}{suffix}")
    return "\\n".join(parts) if parts else NONE_LABEL[language][1]


def localization_files(roots: tuple[Path, ...] = TARGETS) -> dict[Path, str]:
    by_good, by_group = _memberships()
    result: dict[Path, str] = {}
    for language in ("english", "simp_chinese"):
        lines = [
            f"l_{language}:",
            " # === SOL substitute groups (goods tooltip) ===",
            f" {HEADER[language][0]}: \"{HEADER[language][1]}\"",
            f" {NONE_LABEL[language][0]}: \"{NONE_LABEL[language][1]}\"",
        ]
        index = 0 if language == "english" else 1
        strings = {
            "SOL_GOOD_PRICE_TIERS": ("Price preference tiers", "价格偏好档位"),
            "SOL_GOOD_MARKET_RATIO_PREFIX": ("This market's price is", "本市场价格为基础价的"),
            "SOL_GOOD_MARKET_RATIO_SUFFIX": ("times the base price.", "倍。"),
        }
        for tier, groups in GROUP_TIERS:
            for group in groups:
                strings[f"SOL_GOOD_GROUP_{group}"] = tuple(
                    f"#E {TIER_LABELS[tier][i]}#! {SHORT_GROUP_LABELS[group][i]}" for i in (0, 1)
                )
        for number, (weight, _, interval, _) in enumerate(PRICE_TIERS):
            strings[f"SOL_GOOD_PRICE_TIER_{number}"] = (
                f"Price / base price: {interval}. Preference weight: ×{weight}.",
                f"价格/基础价：{interval}。价格偏好权重：×{weight}。",
            )
        lines += [f' {key}: "{value[index]}"' for key, value in strings.items()]
        for good in _all_goods():
            lines.append(f' SOL_GOOD_SUB_{good}: "{_good_line(good, by_good, by_group, language)}"')
            # Selected only by the location hover when the market entry exists.
            weight = f"GetVariableFromGlobalVariableMap('sol_market_substitute_weight_{good}', Location.GetMarket.MakeScope)"
            lines.append(f' SOL_SUB_PRICE_{good}: "$SOL_SUB_PRICE_WEIGHT$: [{weight}.GetValue|2]"')
        lines.append("")
        text = "\n".join(lines)
        for root in roots:
            result[
                root / "main_menu" / "localization" / language / f"SOL_substitutes_l_{language}.yml"
            ] = text
    return result


# -------------------------------------------------------------------------- output
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the SOL goods tooltip override.")
    parser.add_argument(
        "--target",
        choices=["stable", "sol_standalone", "all"],
        default="all",
        help="Deploy target to write (default: all).",
    )
    parser.add_argument("--check", action="store_true", help="Check without writing files.")
    args = parser.parse_args()

    roots = ALL_TARGETS if args.target == "all" else (TARGET_ROOTS[args.target],)
    outputs = {**gui_files(roots), **localization_files(roots)}
    ok = True
    for path, content in outputs.items():
        relative = path.relative_to(REPO_ROOT)
        # .gui matches its vanilla source (no BOM); .yml must carry one.
        payload = content.encode("utf-8")
        if path.suffix == ".yml":
            payload = UTF8_BOM + payload
        if args.check:
            current = path.read_bytes() if path.exists() else None
            if current != payload:
                print(f"[FAIL] Out of date: {relative}")
                ok = False
            else:
                print(f"[OK] Up to date: {relative}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        print(f"[OK] Written: {relative}")
    if args.check and not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
