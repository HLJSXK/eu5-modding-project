"""Living standard (SOL) is derived from purchasing power and never feeds demand.

Executes the generated SOL effects in the offline scope fixture and checks the
shipped scripts of every deploy target for the one-way data flow:
purchasing power -> demand, and purchasing power + local bonus -> SOL.
"""
from pathlib import Path
import re
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sol_living_standard_source import (ESTATES, SOL_ONLY_TOKENS, public_name, render_effects,
                                        render_values)
from test_sol_substitution import Runtime, Scope, parse

ROOT = Path(__file__).resolve().parent.parent
BASE_TARGETS = ("stable", "sol_standalone")
ALL_TARGETS = (*BASE_TARGETS, "sol_pp_compatibility_submod", "sol_mnt_compatibility_submod",
               "sol_jtg_compatibility_submod")
SOL_TOKEN = re.compile("|".join(map(re.escape, SOL_ONLY_TOKENS)))

# Effects and values allowed to mention SOL-only names.
SOL_EFFECTS = {
    "sol_compute_location_living_standard",
    "sol_ls_reset_country_living_standard",
    "sol_ls_accumulate_country_living_standard",
    "sol_ls_finalize_country_living_standard",
    "sol_ls_recalculate_world_ranking",
    # Calls sol_compute_location_living_standard as its final statement only.
    "sol_compute_location_pop_demand",
}
SOL_VALUE_PREFIXES = ("sol_location_", "sol_ls_", "sol_map_living_standard_")
# Variables that make up demand: the raw/final location scales, the applied
# modifier size, and every country solver input or output.
DEMAND_VARIABLE = re.compile(
    r"^(sol_location_(raw|final)_demand_scale|sol_location_pop_demand_modifier_size|sol_location_baseline_total_spending"
    r"|sol_country_(demand|base_spending|baseline|class)_\w+|gls_country_final_demand_scale_avg)$")
PURCHASING_POWER_GUI = (
    "in_game/gui/SOL_economy_local.gui",
    "in_game/gui/panels/situation/global_living_standard.gui",
)


class LivingStandardRuntime(Runtime):
    def __init__(self, bonus=None):
        self.quantities, self.prices, self.maps, self.saved = {}, {}, {}, {}
        self.enabled = True
        self.local_context = {}
        from collections import Counter
        self.operations = Counter()
        self.effects = {n.key: n.value for n in parse(render_effects())}
        self.script_values = {n.key: n.value for n in parse(render_values())}
        for name, value in (bonus or {}).items():
            self.script_values[name] = parse(f"x = {{ value = {value} }}")[0].value


def location(owner, liquid, base):
    variables = {}
    for estate in ESTATES:
        variables[f"sol_location_{estate}_liquid_funds"] = liquid.get(estate, 0.)
        variables[f"sol_location_{estate}_base_spending"] = base.get(estate, 0.)
    variables["sol_location_liquid_funds"] = sum(liquid.values())
    variables["sol_location_base_total_spending"] = sum(base.values())
    place = Scope("location", variables=variables, owner=owner)
    owner.locations.append(place)
    return place


def solve(runtime, country):
    runtime.run("sol_ls_reset_country_living_standard", country)
    for place in country.locations:
        runtime.run("sol_compute_location_living_standard", place)
        runtime.run("sol_ls_accumulate_country_living_standard", place)
    runtime.run("sol_ls_finalize_country_living_standard", country)


def fixture():
    country = Scope("country")
    location(country, {"nobles": 6, "commoners": 3}, {"nobles": 4, "commoners": 6})
    location(country, {"burghers": 2, "commoners": 1}, {"burghers": 1, "commoners": 4})
    return country


def effects_of(target):
    folder = ROOT / "src" / target / "in_game/common/scripted_effects"
    for path in sorted(folder.glob("*.txt")):
        for node in parse(path.read_text(encoding="utf-8-sig")):
            yield path, node


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node.value, list):
            yield from walk(node.value)


def mentions_sol(node):
    return any(SOL_TOKEN.search(str(item.key)) or (isinstance(item.value, str) and SOL_TOKEN.search(item.value))
               for item in walk([node]))


class LivingStandardTests(unittest.TestCase):
    def test_zero_bonus_equals_purchasing_power(self):
        runtime, country = LivingStandardRuntime(), fixture()
        solve(runtime, country)
        for place in country.locations:
            for estate in ESTATES:
                self.assertAlmostEqual(place.variables[f"sol_location_{estate}_sol_equivalent"],
                                       place.variables[f"sol_location_{estate}_liquid_funds"])
            self.assertAlmostEqual(place.variables["sol_location_sol_equivalent"],
                                   place.variables["sol_location_liquid_funds"])
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 12 / 15)
        self.assertAlmostEqual(country.variables["sol_ls_sol_nobles"], 6 / 4)
        self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], 4 / 10)
        self.assertAlmostEqual(country.variables["sol_ls_sol_burghers"], 2)

    def test_bonus_raises_sol_without_touching_purchasing_power(self):
        runtime = LivingStandardRuntime({"sol_location_local_sol_bonus_value": 0.1,
                                         "sol_location_nobles_local_sol_bonus_value": -2})
        country = fixture()
        before = [dict(place.variables) for place in country.locations]
        solve(runtime, country)
        first = country.locations[0].variables
        # Commoners: 3 funds + 0.1 x 6 baseline; nobles: floored at zero.
        self.assertAlmostEqual(first["sol_location_commoners_sol_equivalent"], 3.6)
        self.assertEqual(first["sol_location_nobles_sol_equivalent"], 0)
        self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], (3.6 + 1.4) / 10)
        for place, snapshot in zip(country.locations, before):
            for name, value in snapshot.items():
                self.assertEqual(place.variables[name], value, name)
            self.assertTrue(all("sol_equivalent" in name for name in set(place.variables) - set(snapshot)))

    def test_estate_without_baseline_has_no_sol(self):
        runtime, country = LivingStandardRuntime(), fixture()
        country.variables["sol_ls_sol_tribesmen"] = 5
        solve(runtime, country)
        self.assertNotIn(public_name("tribesmen"), country.variables)
        self.assertNotIn(public_name("clergy"), country.variables)
        self.assertIn("sol_ls_sol_index_display", runtime.script_values)

    def test_demand_path_never_reads_living_standard(self):
        for target in ALL_TARGETS:
            for path, effect in effects_of(target):
                if not mentions_sol(effect):
                    continue
                with self.subTest(target=target, effect=effect.key):
                    self.assertIn(effect.key, SOL_EFFECTS, str(path))
                for node in walk([effect]):
                    if node.key in ("set_variable", "change_variable") and isinstance(node.value, list):
                        name = next(n.value for n in node.value if n.key == "name")
                        if DEMAND_VARIABLE.match(name):
                            with self.subTest(target=target, variable=name):
                                self.assertFalse(mentions_sol(node), f"{path}: {name} reads SOL")

    def test_location_sol_is_the_last_step_of_the_demand_pass(self):
        for target in BASE_TARGETS:
            effects = {node.key: node.value for _, node in effects_of(target)}
            body = effects["sol_compute_location_pop_demand"]
            self.assertEqual([n.key for n in body].count("sol_compute_location_living_standard"), 1)
            self.assertEqual(body[-1].key, "sol_compute_location_living_standard")
            self.assertFalse(any(mentions_sol(node) for node in body[:-1]))
            # The drivers only call the country hooks; they never read SOL values themselves.
            expected = {"sol_solve_country_pop_demand": ["sol_ls_reset_country_living_standard",
                                                         "sol_ls_finalize_country_living_standard"],
                        "sol_solve_country_pop_demand_raw_only": ["sol_ls_accumulate_country_living_standard"],
                        "sol_solve_country_pop_demand_solver": ["sol_ls_accumulate_country_living_standard"]}
            for name, calls in expected.items():
                found = [n.key for n in walk(effects[name]) if n.key.endswith("_country_living_standard")]
                self.assertEqual(found, calls, name)
                self.assertFalse(any(mentions_sol(n) for n in effects[name]), name)

    def test_script_values_keep_demand_and_sol_apart(self):
        for target in ALL_TARGETS:
            folder = ROOT / "src" / target / "in_game/common/script_values"
            for path in sorted(folder.glob("*.txt")):
                for node in parse(path.read_text(encoding="utf-8-sig")):
                    if mentions_sol(node):
                        with self.subTest(target=target, value=node.key):
                            self.assertTrue(node.key.startswith(SOL_VALUE_PREFIXES), str(path))
                            self.assertNotIn("demand", node.key)
                    if node.key == "local_sol_pop_demand_scale":
                        self.assertFalse(mentions_sol(node))

    def test_purchasing_power_surfaces_read_purchasing_power_only(self):
        for target in ALL_TARGETS:
            root = ROOT / "src" / target
            for relative in PURCHASING_POWER_GUI:
                for path in root.glob(relative.replace("SOL_economy_local", "*SOL_economy_local")):
                    with self.subTest(path=str(path)):
                        self.assertIsNone(SOL_TOKEN.search(path.read_text(encoding="utf-8-sig")))
        for target in BASE_TARGETS:
            modes = {n.key: n for n in parse((ROOT / "src" / target / "in_game/gfx/map/map_modes/SOL_map_modes.txt")
                                             .read_text(encoding="utf-8-sig"))}
            self.assertFalse(mentions_sol(modes["sol_purchasing_power"]))
            self.assertTrue(mentions_sol(modes["sol_living_standard"]))
            hud = (ROOT / "src" / target / "in_game/gui/SOL_lshud.gui").read_text(encoding="utf-8-sig")
            power = hud[hud.index("SOL_LSHUD4_tooltip_2"):hud.index("SOL_LSHUD4_tooltip_3")]
            self.assertIsNone(SOL_TOKEN.search(power))

    def test_generated_targets_match_source(self):
        for target in BASE_TARGETS:
            path = ROOT / "src" / target / "in_game/common/script_values/SOL_living_standard_values.txt"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual(path.read_text(encoding="utf-8-sig"), render_values())
            effects = (ROOT / "src" / target / "in_game/common/scripted_effects/A_SOL_economy_effects.txt")
            self.assertIn(render_effects().strip(), effects.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
