#!/usr/bin/env python3
"""Regression checks for the MnT 0.2.12 compatibility source contract."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_mnt_compat as mnt


class MntCompatibilityTests(unittest.TestCase):
    def test_authority_renderer_keeps_closing_brace_out_of_terminal_comment(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sol_root = root / "sol"
            vanilla_root = root / "vanilla"
            mnt_root = root / "mnt"
            for path in (sol_root, vanilla_root, mnt_root):
                path.mkdir()
            (sol_root / "authority.txt").write_text(
                "TRY_REPLACE:sample_price = { gold = 1 }\n", encoding="utf-8"
            )
            (vanilla_root / "authority.txt").write_text(
                "sample_price = {\n\tgold = 1\n\t# terminal comment\n}\n",
                encoding="utf-8",
            )

            with patch.object(mnt, "REPO_ROOT", root):
                rendered = mnt._render_authority_objects(
                    sol_root / "authority.txt", vanilla_root, mnt_root, "test authority"
                )

        self.assertIn("\t# terminal comment\n}\n", rendered)
        blocks = mnt._parse_top_level_blocks(rendered, Path("generated.txt"))
        self.assertEqual([(block.operation, block.key) for block in blocks], [("REPLACE", "sample_price")])

    def test_reference_version_is_pinned_to_mnt_012(self):
        mnt._validate_mnt_version()

        with TemporaryDirectory() as temp_dir:
            metadata = Path(temp_dir) / "metadata.json"
            metadata.write_text(
                json.dumps({"version": "0.2.11", "supported_game_version": "1.4.*"}),
                encoding="utf-8",
            )
            with patch.object(mnt, "MNT_METADATA", metadata):
                with self.assertRaisesRegex(ValueError, "targets MnT 0.2.12"):
                    mnt._validate_mnt_version()

    def test_epbm_keeps_all_three_mnt_building_loops_and_charge_body(self):
        source = mnt._unique_block(
            mnt._blocks_in_file(mnt.MNT_EPBM), "epbm_calculate_maintenance", "M&T EPBM"
        ).body
        rendered = mnt._render_epbm_body()

        for iterator in ("every_estate", "every_owned_building", "every_owned_foreign_building"):
            with self.subTest(iterator=iterator):
                self.assertEqual(source.count(f"{iterator} = {{"), 1)
                self.assertIn(f"{iterator} = {{", rendered)
        self.assertEqual(mnt._strip_epbm_instrumentation(rendered).rstrip(), source.rstrip())
        self.assertIn("epbm_split_by_estate_power = yes", rendered)
        self.assertIn("epbm_add_estate_building_costs = yes", rendered)
        self.assertIn("name = epbm_crown_pool_cost", rendered)
        self.assertIn("name = epbm_crown_bldg_cost", rendered)

        foreign_start = rendered.index("every_owned_foreign_building = {")
        foreign_body_start = rendered.index("{", foreign_start)
        foreign_body, _ = mnt._collect_brace_block(rendered, foreign_body_start)
        self.assertNotIn("SOL_MNT_BEGIN shared_building_cache", foreign_body)

    def test_estate_location_cache_only_tracks_country_owned_locations(self):
        body = mnt._render_estate_route_body()
        self.assertIn("SOL_MNT_BEGIN assigned_location_cache", body)
        self.assertIn("location = { owner = scope:sol_mnt_maintenance_country }", body)
        self.assertIn("sol_mnt_raw_assigned_$estate$", body)

    def test_generated_goods_and_location_gui_match_mnt_contract(self):
        outputs = mnt._render_outputs()
        goods = mnt._parse_top_level_blocks(outputs[mnt.GOODS_OUTPUT], mnt.GOODS_OUTPUT)
        tools = next(block for block in goods if block.key == "tools")
        self.assertEqual(mnt._final_pop_demand(tools.body)["laborers"], mnt.Decimal("0.002"))
        self.assertEqual(len(mnt._load_sol_targets()), 56)

        gui = outputs[mnt.LOCATION_GUI_OUTPUT]
        self.assertEqual(gui.count("using = tv_location_wonders_close_on_queue"), 6)
        self.assertEqual(gui.count("OpenConstructionQueue("), 6)
        self.assertEqual(gui.count("sol_location_living_standard_button = {}"), 1)
        button_at = gui.index("sol_location_living_standard_button = {}")
        average_at = gui.rfind("using = AverageSatisfaction_tooltip", 0, button_at)
        migration_at = gui.find("using = MigrationAttraction_tooltip", button_at)
        self.assertGreaterEqual(average_at, 0)
        self.assertGreater(migration_at, button_at)
        self.assertIn("[Location.MakeScope.ScriptValue('local_sol_total_income')|g2]", gui)

    def test_generated_authority_blocks_remain_top_level_after_terminal_comments(self):
        outputs = mnt._render_outputs()
        for path in (mnt.PRICES_OUTPUT, mnt.STATIC_OUTPUT):
            with self.subTest(path=path.name):
                blocks = mnt._parse_top_level_blocks(outputs[path], path)
                self.assertGreater(len(blocks), 0)
                self.assertTrue(all(block.operation == "REPLACE" for block in blocks))


if __name__ == "__main__":
    unittest.main()
