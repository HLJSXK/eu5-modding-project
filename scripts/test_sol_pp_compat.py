#!/usr/bin/env python3
"""Regression tests for the PP 0.10 compatibility boundary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_pp_compat as pp


ROOT = Path(__file__).resolve().parents[1]


class PPCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pp._validate_pp_version()

    def test_silk_is_compat_only_luxury_member(self) -> None:
        outputs = pp._render_outputs()
        self.assertIn("sol_substitute_silk", outputs[pp.EFFECTS_OUTPUT])
        self.assertNotIn("silk", (ROOT / "data/goods_weights.csv").read_text(encoding="utf-8"))
        for target in ("stable", "sol_standalone"):
            for path in (ROOT / "src" / target).rglob("*.txt"):
                self.assertNotIn("sol_substitute_silk", path.read_text(encoding="utf-8-sig"))

    def test_luxury_budget_is_preserved_when_silk_is_added(self) -> None:
        base_rows = {good: (price, quantities) for good, price, quantities in pp._load_good_rows()}
        compat_rows = {good: (price, quantities) for good, price, quantities in pp._compat_good_rows()}
        for pop_type in pp.POP_TYPES:
            old_budget = sum(
                base_rows[good][0] * base_rows[good][1][pop_type]
                for good in pp.LUXURY_BASELINE_MEMBERS
            )
            new_budget = sum(
                compat_rows[good][0] * compat_rows[good][1][pop_type]
                for good in (*pp.LUXURY_BASELINE_MEMBERS, "silk")
            )
            self.assertAlmostEqual(old_budget, new_budget, places=4)

    def test_victuals_and_lumber_final_demand_are_zero(self) -> None:
        fur_output = pp._render_outputs()[pp.LUMBER_OUTPUT]
        self.assertIn("TRY_INJECT:fur = {", fur_output)
        for expected in pp.PP_FUR_EXPECTED_LINES:
            self.assertIn(expected, fur_output)
        victuals = pp._parse_vanilla_goods_file(pp.PP_VICTUALS_FILE)["victuals"]
        correction = pp._parse_injected_demand_add(pp.LUMBER_OUTPUT, "victuals")
        for pop_type in pp.POP_TYPES:
            self.assertAlmostEqual(
                correction[pop_type],
                -(victuals["add"][pop_type] * victuals["mult"][pop_type]),
                places=5,
            )
        vanilla = pp.load_vanilla_goods()["lumber"]
        stable = pp._parse_inject_file(pp.STABLE_POP_GOODS)["lumber"]["inject_add"]
        upstream = pp._parse_injected_demand_add(pp.PP_LUMBER_FILE, "lumber")
        compat = pp._parse_injected_demand_add(pp.LUMBER_OUTPUT, "lumber")
        for pop_type in pp.POP_TYPES:
            self.assertAlmostEqual(
                vanilla["add"][pop_type] * vanilla["mult"][pop_type]
                + stable[pop_type]
                + upstream[pop_type]
                + compat[pop_type],
                0.0,
                places=5,
            )

    def test_victuals_never_enters_sol_accounting(self) -> None:
        outputs = pp._render_outputs()
        accounting = outputs[pp.EFFECTS_OUTPUT]
        values = outputs[pp.VALUES_OUTPUT]
        for text in (accounting, values):
            self.assertNotIn("sol_market_consumes_victuals", text)
            self.assertNotIn("sol_unit_consumption_nobles_victuals", text)
            self.assertNotIn("sol_substitute_victuals", text)

    def test_lumber_never_enters_compat_solver_or_ui(self) -> None:
        outputs = pp._render_outputs()
        for path in (pp.EFFECTS_OUTPUT, pp.LOCATION_GUI_OUTPUT, pp.SITUATION_GUI_OUTPUT):
            text = outputs[path]
            self.assertNotIn("sol_substitute_lumber", text)
            self.assertNotIn("sol_good_effective_lumber", text)
        self.assertNotIn("@lumber!", outputs[pp.LOCATION_GUI_OUTPUT])
        self.assertNotIn("@lumber!", outputs[pp.SITUATION_GUI_OUTPUT])

    def test_location_window_is_based_on_pp_and_injects_sol_button(self) -> None:
        outputs = pp._render_outputs()
        window = outputs[pp.LOCATION_WINDOW_OUTPUT]
        self.assertIn("size = { 600 100% } # PP: wider than the vanilla left panel", window)
        self.assertEqual(window.count("sol_location_living_standard_button = {}"), 1)
        self.assertIn("# SOL-PP compatibility insertion: shared location living-standard button.", window)

    def test_economic_balance_is_not_registered_or_active(self) -> None:
        outputs = pp._render_outputs()
        cmm = outputs[pp.CMM_EFFECTS_OUTPUT]
        disabled = outputs[pp.CMM_TRIGGERS_OUTPUT]
        auto = outputs[pp.AUTO_MODIFIERS_OUTPUT]
        for setting_id in ("as_on", "bte", "ae", "cts", "ds", "difficulty", "gdp_dev", "ai_pr"):
            self.assertNotIn(f"setting_id = {setting_id}", cmm)
            self.assertNotIn(f"flag:sol__{setting_id}", cmm)
        for trigger in ("sol_as_is_on", "sol_ae_is_on", "sol_difficulty_is_on", "sol_gdp_dev_is_on"):
            self.assertIn(f"REPLACE:{trigger} = {{ always = no }}", disabled)
        for modifier in pp.DISABLED_AUTO_MODIFIER_KEYS:
            self.assertIn(f"REPLACE:{modifier} = {{", auto)
            self.assertIn("potential_trigger = { always = no }", auto)


if __name__ == "__main__":
    unittest.main()
