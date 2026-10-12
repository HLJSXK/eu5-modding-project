#!/usr/bin/env python3
"""Generate the SOL goods tooltip override (substitute-group section).

Overrides main_menu/gui/shared/goods_details.gui for the stable and standalone
targets. That one file is the right seam: its `goods_details` template is spliced
with `using = goods_details` by every goods tooltip in the game - Goods_tooltip
(production_tooltips.gui:406), Goods_Cards_tooltip and SpecificGoodsMarket_tooltip
(market_tooltips.gui:1473) - so one override reaches all of them, and it is small
(210 lines) rather than the 1440- or 4598-line files that also use it.

WHAT IS SHOWN
-------------
Only substitute-group membership, which is a static property of the good: which
demand groups it belongs to and which goods substitute for it inside each. That is
true in every context, so it needs no scope.

Two things are deliberately NOT shown here:

  * the country-level SOL substitute multiplier - the generic goods tooltip has no
    single consuming country (a good is demanded by every country that trades it),
    and showing one country's multiplier would be a fiction. It belongs on a surface
    that owns a country: add a block at the SpecificGoodsMarket_tooltip use site
    (market_tooltips.gui:1523 `block "good_details_extra_info" {}`) or read it from
    a country-scoped panel.
  * the market price tier - needs a market in scope, so it likewise belongs on the
    market-context section, not on the generic tooltip.

Both are static-free extension points; this generator does not fabricate them.

LOCALIZATION
------------
Every good that can exist gets a key `SOL_GOOD_SUB_<good>`, generated from
data/goods_weights.csv plus the vanilla goods and the goods the compat submods add.
A good that belongs to no group gets the explicit "no substitute group" text rather
than a blank block. A good from an unrelated third-party mod has no key and would
print its raw key text - the one documented gap.

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
GAME_GUI = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V"
    r"\game\main_menu\gui\shared\goods_details.gui"
)

UTF8_BOM = b"\xef\xbb\xbf"

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
    pattern = re.compile(r"^\s*([a-z][a-z_0-9]*)\s*=\s*\{")
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
    """The section injected into `template goods_details`.

    Both children are vanilla TooltipTextBlock. `text` is the property that resolves
    an embedded expression here - the same shape the template already uses for
    `text = "[Goods.GetDemandsInfo]"`.
    """
    return (
        "\t# ---- SOL substitute groups -------------------------------------------------\n"
        "\t# Data: data/goods_weights.csv. Membership is static per good, so this reads\n"
        "\t# nothing scoped and is correct in every goods tooltip.\n"
        "\t# The country multiplier and the market price tier are NOT shown here: the\n"
        "\t# generic tooltip owns neither a country nor a market. Add them at a use site\n"
        "\t# that does (market_tooltips.gui:1523 `block \"good_details_extra_info\" {}`).\n"
        "\tTooltipTextBlock = {\n"
        '\t\tblockoverride "text" { text = "SOL_GOOD_SUBSTITUTES_HEADER" }\n'
        "\t}\n"
        "\n"
        "\tTooltipTextBlock = {\n"
        '\t\tblockoverride "text" {\n'
        '\t\t\ttext = "[Localize(Concatenate(\'SOL_GOOD_SUB_\', Goods.GetKey))]"\n'
        "\t\t}\n"
        "\t}\n"
    )


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
    patched = inject(source)
    relative = Path("main_menu") / "gui" / "shared" / "goods_details.gui"
    return {root / relative: patched for root in roots}


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
        for good in _all_goods():
            lines.append(f' SOL_GOOD_SUB_{good}: "{_good_line(good, by_good, by_group, language)}"')
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
