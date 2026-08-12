#!/usr/bin/env python3
"""Add price suppression indicators to all goods in SOL GUI files."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# All 55 SOL demand goods
GOODS = [
    "amber", "beer", "beeswax", "books", "chili", "cloth", "cloves", "coal", "cocoa",
    "coffee", "elephants", "fine_cloth", "firearms", "fish", "fruit", "fur", "furniture",
    "gems", "glass", "goods_gold", "hemp", "horses", "incense", "ivory", "jewelry",
    "lacquerware", "leather", "legumes", "liquor", "livestock", "maize", "millet",
    "mirrors", "musical_instruments", "nutmeg", "oil", "paper", "pearls", "pepper",
    "porcelain", "pottery", "precious_metals", "rice", "salt", "silk", "silver",
    "slaves", "spices", "sugar", "tea", "timber", "tobacco", "tools", "wheat", "wine"
]


def process_gui_file(file_path: Path) -> None:
    """Add price suppression indicators for all goods in the GUI file."""
    text = file_path.read_text(encoding="utf-8")
    original_text = text

    for good in GOODS:
        # Old pattern: widget with good icon + trigger_no
        old_pattern = (
            f'widget = {{ size = {{ 34 30 }} tooltip = "{good}" '
            f'text_single = {{ size = {{ 100% 100% }} align = center raw_text = "@{good}!" }} '
            f'text_single = {{ size = {{ 100% 100% }} align = center raw_text = "@trigger_no!" fontsize = 23 '
            f'visible = "[Not(GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap(\'sol_market_consumes_{good}\', Location.GetMarket.MakeScope).GetValue,\'(CFixedPoint)0\'))]" }} }}'
        )

        # New pattern: add arrow_down indicator between good icon and trigger_no
        new_pattern = (
            f'widget = {{ size = {{ 34 30 }} tooltip = "{good}" '
            f'text_single = {{ size = {{ 100% 100% }} align = center raw_text = "@{good}!" }} '
            f'text_single = {{ size = {{ 100% 100% }} align = center raw_text = "#R @arrow_down!#!" '
            f'visible = "[And(GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap(\'sol_market_consumes_{good}\', Location.GetMarket.MakeScope).GetValue,\'(CFixedPoint)0\'), '
            f'GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap(\'sol_market_price_suppressed_{good}\', Location.GetMarket.MakeScope).GetValue,\'(CFixedPoint)0\'))]" }} '
            f'text_single = {{ size = {{ 100% 100% }} align = center raw_text = "@trigger_no!" fontsize = 23 '
            f'visible = "[Not(GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap(\'sol_market_consumes_{good}\', Location.GetMarket.MakeScope).GetValue,\'(CFixedPoint)0\'))]" }} }}'
        )

        # Replace the pattern (only if it exists and hasn't been modified already)
        if old_pattern in text:
            text = text.replace(old_pattern, new_pattern)

    if text != original_text:
        file_path.write_text(text, encoding="utf-8")
        changes = sum(1 for g in GOODS if old_pattern.replace('{good}', g) in original_text)
        print(f"[add_all_price_suppression] Updated {file_path} ({changes} goods modified)")
    else:
        print(f"[add_all_price_suppression] {file_path} already up to date")


def main():
    gui_files = [
        Path("src/stable/in_game/gui/SOL_economy_local.gui"),
        Path("src/sol_standalone/in_game/gui/SOL_economy_local.gui"),
    ]

    for gui_file in gui_files:
        if gui_file.exists():
            process_gui_file(gui_file)
        else:
            print(f"[add_all_price_suppression] Warning: {gui_file} not found")


if __name__ == "__main__":
    main()
