"""Exercise the shipped map values, living-standard provenance and map registration."""
from pathlib import Path
import struct
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from test_sol_lshud_ranking import RankingRuntime, country
from test_sol_substitution import Scope, parse
from sol_map_modes_source import MAP_MODES

ROOT = Path(__file__).resolve().parent.parent


class MapRuntime(RankingRuntime):
    def __init__(self, target="stable", countries=()):
        super().__init__(list(countries))
        root = ROOT / "src" / target / "in_game/common"
        for filename in ("SOL_map_values.txt", "SOL_economy_values.txt"):
            self.script_values.update({n.key: n.value for n in parse(
                (root / "script_values" / filename).read_text(encoding="utf-8-sig"))})

    def value(self, node, scope, initial=0.):
        if isinstance(node, str):
            if node.startswith("owner."):
                return self.value(node[6:], scope.owner)
            if node == "local_sol_total_population":
                return max(sum(scope.pops.values()), .001)
        return super().value(node, scope, initial)

    def test(self, node, scope):
        if node.key == "has_owner":
            return (scope.owner is not None) == (node.value == "yes")
        if node.key == "owner" and isinstance(node.value, list):
            return scope.owner is not None and self.condition(node.value, scope.owner)
        return super().test(node, scope)


class MapModeTests(unittest.TestCase):
    def test_sol_tooltip_tiers_include_zero_baseline_populations_at_exact_boundaries(self):
        for target in ("stable", "sol_standalone"):
            runtime = MapRuntime(target)
            runtime.globals["sol_ls_world_sol"] = 10
            location = Scope("location", owner=country(10), variables={"sol_location_base_total_spending": 0})
            path = ROOT / "src" / target / "in_game/gfx/map/map_modes/SOL_map_modes.txt"
            mode = parse(path.read_text(encoding="utf-8-sig"))[0]
            tooltip = next(n.value for n in mode.value if n.key == "tooltip_key")
            for amount, tier in ((0, "VERY_LOW"), (4.99999, "VERY_LOW"), (5, "LOW"),
                                 (9.99999, "LOW"), (10, "MID"), (19.99999, "MID"), (20, "HIGH")):
                location.variables["sol_location_sol"] = amount
                selected = None
                for branch in tooltip:
                    limit = next((n.value for n in branch.value if n.key == "limit"), [])
                    if runtime.condition(limit, location):
                        selected = next(n.value for n in branch.value if n.key == "value")
                        break
                self.assertEqual(selected, "MAPMODE_SOL_LIVING_STANDARD_TT_" + tier)

    def test_living_standard_map_reads_amount_and_uses_world_average(self):
        for target in ("stable", "sol_standalone"):
            runtime = MapRuntime(target)
            location = Scope("location")
            self.assertEqual(runtime.value("sol_map_living_standard_value", location), 0)
            # Missing/zero world average has the same positive fallback, with no zero division.
            for average in (None, 0, 10, 20):
                runtime.globals.clear()
                if average is not None:
                    runtime.globals["sol_ls_world_sol"] = average
                reference = average or 6
                for amount in (0, reference * .5, reference, reference * 2, reference * 3, reference * 9):
                    for final_scale in (.01, 100):
                        location.variables.update(sol_location_sol=amount, sol_location_liquid_funds=999,
                                                  sol_location_base_total_spending=0,
                                                  sol_location_final_demand_scale=final_scale)
                        self.assertAlmostEqual(runtime.value("sol_map_living_standard_value", location), amount)
                        self.assertAlmostEqual(runtime.value("sol_map_living_standard_relative_value", location), amount / reference)
                        self.assertAlmostEqual(runtime.value("sol_map_living_standard_below_factor", location),
                                               min(amount / reference, 1))
                        self.assertAlmostEqual(runtime.value("sol_map_living_standard_above_factor", location),
                                               min(max((amount / reference - 1) / 2, 0), 1))
            situation = (ROOT / "src" / target / "in_game/common/situations/SOL_economy_situation.txt").read_text(encoding="utf-8-sig")
            modes = (ROOT / "src" / target / "in_game/gfx/map/map_modes/SOL_map_modes.txt").read_text(encoding="utf-8-sig")
            for text in (situation, modes):
                self.assertIn("sol_map_living_standard_below_factor", text)
                self.assertIn("sol_map_living_standard_above_factor", text)
                self.assertIn("sol_map_living_standard_relative_value < 1", text)
                for threshold in (2, 1, .5):
                    self.assertIn(f"sol_map_living_standard_relative_value >= {threshold}", text)
            self.assertNotIn("per_capita", situation)
            self.assertNotIn("base_total_spending", situation)

    def test_power_raw_percentage_and_neutral_missing_baseline(self):
        for target in ("stable", "sol_standalone"):
            runtime = MapRuntime(target)
            location = Scope("location")
            self.assertEqual(runtime.value("sol_map_purchasing_power_value", location), 0)
            for funds, baseline, expected in ((0, 10, -1), (5, 10, -.5), (10, 10, 0),
                                               (20, 10, 1), (30, 10, 2), (100, 10, 9), (10, 0, 0)):
                for final_scale in (.01, 100):
                    location.variables.update(sol_location_liquid_funds=funds, sol_location_base_total_spending=baseline,
                                              sol_location_final_demand_scale=final_scale)
                    self.assertEqual(runtime.value("sol_map_purchasing_power_value", location), expected)

    def test_rank_colors_follow_overall_rank_including_single_country(self):
        countries = [country(sol) for sol in (10, 30, 20)]
        runtime = MapRuntime(countries=countries)
        runtime.refresh()
        self.assertEqual([runtime.value("sol_map_rank_color_factor", c) for c in countries], [0, 1, .5])
        for owner in countries:
            for local_sol in (0, 99999):
                location = Scope("location", owner=owner, variables={"sol_location_sol": local_sol})
                self.assertEqual(runtime.value("owner.sol_map_rank_color_factor", location), owner.variables["sol_ls_percentile"])
        runtime = MapRuntime(countries=[country(10)])
        runtime.refresh()
        self.assertEqual(runtime.value("sol_map_rank_color_factor", runtime.countries[0]), 1)
        self.assertEqual(runtime.value("sol_map_rank_color_factor", country(999)), 0)

    def test_both_targets_register_contexts_and_complete_mip_icons(self):
        for target in ("stable", "sol_standalone"):
            root = ROOT / "src" / target
            modes = parse((root / "in_game/gfx/map/map_modes/SOL_map_modes.txt").read_text(encoding="utf-8-sig"))
            self.assertEqual([n.key for n in modes], list(MAP_MODES))
            for idx, node in enumerate(modes):
                fields = {n.key: n.value for n in node.value}
                color_if = next(n for n in fields["map_color"] if n.key == "if")
                color_limit = next(n.value for n in color_if.value if n.key == "limit")
                self.assertEqual(any(n.key == "sol_map_is_on" for n in color_limit), target == "stable")
                self.assertEqual(fields["category"], "economy")
                self.assertEqual(fields["index"], str(idx))
                for zoom in ("small", "medium", "large"):
                    context = "location" if idx < 2 else "country"
                    self.assertEqual(fields[zoom + "_map_names"], context)
                    self.assertEqual(fields[zoom + "_tooltip_context"], context)
                icon = (root / f"main_menu/gfx/interface/icons/map_modes/{node.key}.dds").read_bytes()
                self.assertEqual(icon[:4], b"DDS ")
                height, width, _pitch, depth, mips = struct.unpack_from("<5I", icon, 12)
                self.assertEqual((height, width, depth, mips), (128, 128, 1, 8))


if __name__ == "__main__":
    unittest.main()
