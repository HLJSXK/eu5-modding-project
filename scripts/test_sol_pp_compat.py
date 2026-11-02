#!/usr/bin/env python3
"""Regression tests for the PP 0.10 compatibility boundary."""

from __future__ import annotations

import sys
import re
import unittest
from decimal import Decimal
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_pp_compat as pp


ROOT = Path(__file__).resolve().parents[1]
RENDERER_ROOT = ROOT / ".eu5-base" / "ai_gui_assessment" / "renderer"
if str(RENDERER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDERER_ROOT))
from eu5_gui_renderer.pdx import parse_file


DATABASE_OPERATIONS = (
    "TRY_INJECT:", "TRY_REPLACE:", "INJECT:", "REPLACE:",
    "REPLACE_OR_CREATE:", "INJECT_OR_CREATE:",
)


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
            target_budget = old_budget * pp.PP_BASKET_MULTIPLIERS[pop_type]
            if target_budget > 0:
                self.assertLessEqual(abs(new_budget / target_budget - 1), 0.05)

    def test_pp_baskets_use_save_medians_and_two_significant_digits(self) -> None:
        base = {good: quantities for good, _price, quantities in pp._load_good_rows()}
        calibrated = {good: quantities for good, _price, quantities in pp._compat_good_rows()}
        self.assertEqual(pp.PP_BASKET_MULTIPLIERS["nobles"], 2.0)
        self.assertEqual(pp.PP_BASKET_MULTIPLIERS["clergy"], 2.0)
        self.assertAlmostEqual(pp.PP_BASKET_MULTIPLIERS["burghers"], 1.5373831775700935)
        self.assertAlmostEqual(pp.PP_BASKET_MULTIPLIERS["laborers"], 1.706803704957381)
        self.assertAlmostEqual(pp.PP_BASKET_MULTIPLIERS["peasants"], 1.706803704957381)
        self.assertAlmostEqual(pp.PP_BASKET_MULTIPLIERS["soldiers"], 1.706803704957381)
        self.assertEqual(pp.PP_BASKET_MULTIPLIERS["tribesmen"], 1.0)
        for good, quantities in calibrated.items():
            for pop_type, quantity in quantities.items():
                if good != "lumber" and base.get(good, {}).get(pop_type, 0.0) > 0:
                    self.assertGreater(quantity, 0, (good, pop_type))
                if quantity > 0:
                    self.assertLessEqual(
                        pp._significant_digits(Decimal(str(quantity))),
                        2,
                        (good, pop_type, quantity),
                    )

    def test_compatch_emits_target_scoped_basket_deltas(self) -> None:
        outputs = pp._render_outputs()
        output = outputs[pp.LUMBER_OUTPUT]
        self.assertIn("# PP compatch basket calibration: coal.", output)
        self.assertIn("INJECT:coal = {", output)
        self.assertIn("INJECT:cloves = {", output)
        self.assertIn("INJECT:silk = {", output)
        self.assertIn("sol_unit_consumption_nobles_fine_cloth", outputs[pp.VALUES_OUTPUT])

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
        button_at = window.index("sol_location_living_standard_button = {}")
        average_at = window.rfind("using = AverageSatisfaction_tooltip", 0, button_at)
        migration_at = window.find("using = MigrationAttraction_tooltip", button_at)
        self.assertGreaterEqual(average_at, 0)
        self.assertGreater(migration_at, button_at)

    def test_economic_balance_is_cmf_opt_in_and_default_off(self) -> None:
        outputs = pp._render_outputs()
        cmm = outputs[pp.CMM_EFFECTS_OUTPUT]
        disabled = outputs[pp.CMM_TRIGGERS_OUTPUT]
        auto = outputs[pp.AUTO_MODIFIERS_OUTPUT]
        scripted_gui = outputs[pp.CMM_SCRIPTED_GUI_OUTPUT]
        self.assertIn("setting_id = pp_as_on", cmm)
        self.assertIn("default_value = 0", cmm)
        for setting_id in ("bte", "ae", "cts", "ds", "difficulty", "gdp_dev", "ai_pr"):
            self.assertIn(f"setting_id = {setting_id}", cmm)
            self.assertIn(f"flag:sol__{setting_id}", cmm)
        self.assertNotIn("setting_id = as_on", cmm)
        self.assertNotIn("flag:sol__as_on", cmm)
        self.assertIn("has_global_variable_map = cmm", disabled)
        self.assertIn("has_global_variable = sol_as_enabled", disabled)
        for trigger in ("sol_as_is_on", "sol_ae_is_on", "sol_difficulty_is_on", "sol_gdp_dev_is_on"):
            self.assertIn(f"REPLACE:{trigger} = {{", disabled)
        self.assertNotIn("potential_trigger = { always = no }", auto)
        self.assertIn("sol_substitute_silk", auto)
        for setting_id in (
            "sol_map", "ai_reduced_freq", "bte", "ae", "cts", "ds",
            "difficulty", "gdp_dev", "ai_pr", "iwe", "hwe", "rwe",
        ):
            self.assertNotIn(f"sol__{setting_id}_on_changed =", scripted_gui)

    def test_pp_silk_localization_uses_unique_keys(self) -> None:
        outputs = pp._render_outputs()
        for path in (pp.LOCATION_GUI_OUTPUT, pp.SITUATION_GUI_OUTPUT):
            text = outputs[path]
            self.assertIn("SOL_PP_GOOD_SUB_silk", text)
            self.assertNotIn("SOL_GOOD_SUB_silk", text)
            self.assertNotIn("SOL_SUB_PRICE_silk", text)
        self.assertIn("SOL_PP_SUB_PRICE_silk", outputs[pp.LOCATION_GUI_OUTPUT])
        for language in ("english", "simp_chinese"):
            text = outputs[pp.ENGLISH_SUB_LOC_OUTPUT if language == "english" else pp.CHINESE_SUB_LOC_OUTPUT]
            self.assertIn(f"SOL_PP_GOOD_SUB_silk:", text)
            self.assertIn(f"SOL_PP_SUB_PRICE_silk:", text)
            pp_keys = set(re.findall(r"(?m)^\s+([A-Za-z0-9_.-]+):", text))
            upstream_keys = set()
            upstream_roots = (
                ROOT / "src/stable/main_menu/localization" / language,
                ROOT.parent / "prosper-or-perish-upstream" / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "main_menu/localization" / language,
            )
            for loc_root in upstream_roots:
                if not loc_root.exists():
                    continue
                for loc_file in loc_root.glob("*.yml"):
                    upstream_keys.update(re.findall(
                        r"(?m)^\s+([A-Za-z0-9_.-]+):",
                        loc_file.read_text(encoding="utf-8-sig"),
                    ))
            self.assertFalse(pp_keys & upstream_keys, sorted(pp_keys & upstream_keys))

    def test_loaded_sol_pp_stack_has_no_plain_key_collisions(self) -> None:
        roots = {
            "SOL": ROOT / "src/stable",
            "PP": ROOT.parent / "prosper-or-perish-upstream" / "mod" / "Prosper or Perish (Population Growth & Food Rework)",
            "COMPATCH": ROOT / "src/sol_pp_compatibility_submod",
        }
        objects = {}
        for owner, root in roots.items():
            for path in root.rglob("*.txt"):
                relative = path.relative_to(root)
                database = (relative.parts[0], *relative.parts[1:-1])
                for node in parse_file(path):
                    if not node.is_block():
                        continue
                    operation = "="
                    key = node.key
                    for prefix in DATABASE_OPERATIONS:
                        if key.startswith(prefix):
                            operation = prefix[:-1]
                            key = key[len(prefix):]
                            break
                    objects.setdefault((database, key), []).append((owner, operation, path))

        collisions = []
        for (database, key), entries in objects.items():
            compatch = [entry for entry in entries if entry[0] == "COMPATCH" and entry[1] == "="]
            upstream = [entry for entry in entries if entry[0] in {"SOL", "PP"}]
            if database[-1] == "on_action":
                continue
            if compatch and upstream:
                collisions.append((database, key, compatch, upstream))
            if len(compatch) > 1:
                collisions.append((database, key, compatch, []))
        self.assertEqual([], collisions)


if __name__ == "__main__":
    unittest.main()
