#!/usr/bin/env python3
"""Add price suppression indicator (red down arrow) to goods icons in location GUI.

For each good that has consumption but is expensive (market_price > default_price),
display a red down arrow overlay to indicate demand suppression.
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def process_gui_file(file_path: Path) -> None:
    """Add price suppression indicators to all goods widgets in the GUI file."""
    text = file_path.read_text(encoding="utf-8")

    # Pattern matches: widget = { size = { 34 30 } tooltip = "GOOD" text_single = { ... } text_single = { ... "@trigger_no!" ... } }
    # We need to add a third text_single for the suppression indicator
    pattern = re.compile(
        r'(widget = \{ size = \{ 34 30 \} tooltip = "([a-z_]+)" text_single = \{ [^}]+ \} )(text_single = \{ [^}]+ raw_text = "@trigger_no!" [^}]+ \} \})',
        re.MULTILINE
    )

    def replacer(match: re.Match) -> str:
        prefix = match.group(1)
        good_name = match.group(2)
        trigger_no_part = match.group(3)

        # Add the suppression indicator before the closing }
        suppression_indicator = (
            f'text_single = {{ size = {{ 100% 100% }} align = center raw_text = "#R @arrow_down!#!" '
            f'visible = "[And(GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap(\'sol_market_consumes_{good_name}\', Location.GetMarket.MakeScope).GetValue,\'(CFixedPoint)0\'), '
            f'GreaterThan_CFixedPoint(GetVariableFromGlobalVariableMap(\'sol_market_price_suppressed_{good_name}\', Location.GetMarket.MakeScope).GetValue,\'(CFixedPoint)0\'))]" }} '
        )

        return f"{prefix}{suppression_indicator}{trigger_no_part}"

    new_text = pattern.sub(replacer, text)

    if new_text != text:
        file_path.write_text(new_text, encoding="utf-8")
        print(f"[add_price_suppression] Updated {file_path}")
        # Count how many goods were updated
        count = len(pattern.findall(text))
        print(f"[add_price_suppression] Added suppression indicators to {count} goods")
    else:
        print(f"[add_price_suppression] No changes needed in {file_path}")


def main():
    # Process all relevant GUI files
    gui_files = [
        Path("src/stable/in_game/gui/SOL_economy_local.gui"),
        Path("src/sol_standalone/in_game/gui/SOL_economy_local.gui"),
    ]

    for gui_file in gui_files:
        if gui_file.exists():
            process_gui_file(gui_file)
        else:
            print(f"[add_price_suppression] Warning: {gui_file} not found, skipping")


if __name__ == "__main__":
    main()
