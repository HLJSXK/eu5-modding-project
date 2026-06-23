"""
sync_location_window.py — Rebuild src/stable/in_game/gui/location_window.gui.

Copies the current vanilla baseline from reference_game_files/ and re-injects
the mod's active location-window UI addition: the StandardofLiving_tooltip
navigational button in the demography shortcuts row, between AverageSatisfaction
and the expand spacer.

Run after syncing reference_game_files/ to a new EU5 version:
  conda run -n eu5 python scripts/sync_location_window.py
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
SRC  = ROOT / "src/stable/in_game/gui/location_window.gui"
REF  = ROOT / "reference_game_files/game/in_game/gui/location_window.gui"

# Unique anchor: the closing braces of the AverageSatisfaction navigational_button_alt
# (action_tooltip block + button close). Ends exactly where the SOL button is inserted.
ANCHOR = (
    "\t\t\t\t\t\t\t\taction_tooltip = {\n"
    "\t\t\t\t\t\t\t\t\tclick_type = left\n"
    "\t\t\t\t\t\t\t\t\tclick_mode = single\n"
    "\t\t\t\t\t\t\t\t\ttitle = \"OPEN_PEOPLE_VIEW\"\n"
    "\t\t\t\t\t\t\t\t\ton_action = \"[ShowCountryPeopleViewWithLocation(Location.GetId, '(bool)yes')]\"\n"
    "\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t}"
)

# SOL navigational button — shows StandardofLiving_tooltip on hover.
# Sits between AverageSatisfaction button and the expand spacer in the demography shortcuts row.
SOL_BUTTON = (
    "\t\t\t\t\t\t\tnavigational_button_alt = {\n"
    "\t\t\t\t\t\t\t\tsize = {38 38}\n"
    "\n"
    "\t\t\t\t\t\t\t\tblockoverride \"icon_texture\" {\n"
    "\t\t\t\t\t\t\t\t\tpiechart = {\n"
    "\t\t\t\t\t\t\t\t\t\tparentanchor = center\n"
    "\t\t\t\t\t\t\t\t\t\tsize = { 70% 70% }\n"
    "\t\t\t\t\t\t\t\t\t\talwaystransparent = yes\n"
    "\n"
    "\t\t\t\t\t\t\t\t\t\thbox = {\n"
    "\t\t\t\t\t\t\t\t\t\t\twidget = {\n"
    "\t\t\t\t\t\t\t\t\t\t\t\tusing = layoutpolicy_expanding\n"
    "\t\t\t\t\t\t\t\t\t\t\t\ticon = {\n"
    "\t\t\t\t\t\t\t\t\t\t\t\t\tsize = { 100% 100% }\n"
    "\t\t\t\t\t\t\t\t\t\t\t\t\tparentanchor = center\n"
    "\t\t\t\t\t\t\t\t\t\t\t\t\tname = \"stat_sol_living_standard\"\n"
    "\t\t\t\t\t\t\t\t\t\t\t\t\ttexture = \"gfx/interface/icons/sol/sol_living_standard.dds\"\n"
    "\t\t\t\t\t\t\t\t\t\t\t\t\ttexture_density = 2\n"
    "\t\t\t\t\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t\t\t\tusing = bg_circle_piechart\n"
    "\t\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t\t}\n"
    "\n"
    "\t\t\t\t\t\t\t\ttooltipwidget = {\n"
    "\t\t\t\t\t\t\t\t\tusing = StandardofLiving_tooltip\n"
    "\t\t\t\t\t\t\t\t}\n"
    "\t\t\t\t\t\t\t}"
)


def strip_trailing_whitespace(text: str) -> str:
    newline = "\n" if text.endswith("\n") else ""
    return "\n".join(line.rstrip(" \t") for line in text.splitlines()) + newline


def main() -> None:
    text = REF.read_text(encoding="utf-8")

    count = text.count(ANCHOR)
    if count != 1:
        raise SystemExit(
            f"ERROR: anchor found {count} time(s) in vanilla file — "
            "vanilla may have changed; update ANCHOR in this script."
        )

    text = text.replace(ANCHOR, ANCHOR + "\n" + SOL_BUTTON, 1)
    text = strip_trailing_whitespace(text)
    SRC.write_text(text, encoding="utf-8")
    print(f"Synced  {SRC.relative_to(ROOT)}")
    print("        SOL tooltip button injected after AverageSatisfaction shortcut.")


if __name__ == "__main__":
    main()
