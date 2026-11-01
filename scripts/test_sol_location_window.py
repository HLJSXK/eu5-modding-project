#!/usr/bin/env python3
"""Regressions for the SOL location-window source owners."""

from __future__ import annotations

import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class LocationWindowGenerationTests(unittest.TestCase):
    def test_stable_and_standalone_use_glorp_14_while_pp_keeps_its_own_base(self) -> None:
        import generate_sol_location_window as standalone
        import gen_sol_pp_compat as pp
        import sync_location_window as stable

        expected_glorp_source = stable.REPO_ROOT / ".eu5-base/reference_mods/3601047146/in_game/gui/location_window.gui"
        self.assertEqual(stable.SOURCE_PATH, expected_glorp_source)
        self.assertEqual(standalone.SOURCE_PATH, expected_glorp_source)
        self.assertEqual(
            pp.PP_LOCATION_GUI,
            pp.PP_ROOT / "in_game" / "gui" / "location_window.gui",
        )

        stable_outputs = stable.generate_outputs()
        stable_window = stable_outputs[stable.TARGET_PATH]
        stable_types = stable_outputs[stable.TARGET_TYPES_PATH]
        standalone_window = standalone.generate()

        for window in (stable_window, standalone_window):
            self.assertIn("# GlorpUI:", window)
            self.assertEqual(window.count("sol_location_living_standard_button = {}"), 1)
            self.assertEqual(window.count("tv_location_wonders_button = {}"), 1)
            self.assertEqual(window.count("tv_location_wonders_panel = {}"), 1)
            for marker in stable.LEGACY_GUI_MARKERS:
                self.assertNotIn(marker, window)
        self.assertIn("local_sol_total_income", standalone_window)
        self.assertIn("type row_building_card", stable_types)
        self.assertIn("type location_card", stable_types)
        self.assertNotIn("vanilla types extracted", stable_types)

    def test_checked_in_location_windows_match_their_generators(self) -> None:
        import generate_sol_location_window as standalone
        import sync_location_window as stable

        for path, generated in (
            *stable.generate_outputs().items(),
            (standalone.TARGET_PATH, standalone.generate()),
        ):
            with self.subTest(path=path):
                self.assertEqual(path.read_text(encoding="utf-8-sig"), generated)


if __name__ == "__main__":
    unittest.main()
