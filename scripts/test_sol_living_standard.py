"""Living standard (SOL) uses annual funds per thousand and never feeds demand.

Executes the generated SOL effects in the offline scope fixture and checks the
shipped scripts of every deploy target for the one-way data flow:
purchasing power -> demand, and flat + (1 + percent) * annual funds per thousand -> SOL.
"""
from pathlib import Path
import re
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sol_living_standard_source import (ESTATES, SOL_ONLY_TOKENS, FEEDBACK_MODIFIERS,
                                        FLAT_MODIFIER, PERCENT_MODIFIER, BUILDING_SOURCES,
                                        public_name, render_effects, render_values,
                                        render_feedback_modifiers, render_feedback_localization,
                                        render_modifier_types, render_modifier_icons,
                                        render_building_sources, render_modifier_type_localization)
from test_sol_substitution import Runtime, Scope, parse
from sol_lshud_income_source import render_yoy_effects, render_yoy_values

ROOT = Path(__file__).resolve().parent.parent
BASE_TARGETS = ("stable", "sol_standalone")
ALL_TARGETS = (*BASE_TARGETS, "sol_pp_compatibility_submod", "sol_mnt_compatibility_submod",
               "sol_jtg_compatibility_submod")
SOL_TOKEN = re.compile("|".join(re.escape(token) + (r"\b" if token == "sol_location_sol" else "")
                                for token in SOL_ONLY_TOKENS))

# Effects and values allowed to mention SOL-only names.
SOL_EFFECTS = {
    "sol_compute_location_living_standard",
    "sol_ls_reset_country_living_standard",
    "sol_ls_accumulate_country_living_standard",
    "sol_ls_finalize_country_living_standard",
    "sol_ls_finalize_country_living_standard_yoy",
    "sol_ls_compute_living_standard_yoy",
    "sol_ls_recalculate_world_ranking",
    "sol_apply_location_living_standard_modifiers",
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
    def __init__(self, modifier=None):
        self.quantities, self.prices, self.maps, self.saved = {}, {}, {}, {}
        self.enabled = True
        self.local_context = {}
        from collections import Counter
        self.operations = Counter()
        self.effects = {n.key: n.value for n in parse(render_effects() + render_yoy_effects())}
        self.script_values = {n.key: n.value for n in parse(render_values() + render_yoy_values())}
        for name, value in (modifier or {}).items():
            self.script_values[name] = parse(f"x = {{ value = {value} }}")[0].value

    def value(self, node, scope, initial=0.):
        if isinstance(node, str) and node in (f"modifier:{FLAT_MODIFIER}", f"modifier:{PERCENT_MODIFIER}"):
            return scope.external.get(node.removeprefix("modifier:"), 0.)
        if node == "local_commoner_population":
            return sum(scope.pops.get(key, 0) for key in ("laborers", "peasants", "soldiers"))
        if node == "local_sol_population_sum":
            return sum(scope.pops.values())
        return super().value(node, scope, initial)


def location(owner, liquid, base, pops=None):
    variables = {}
    for estate in ESTATES:
        variables[f"sol_location_{estate}_liquid_funds"] = liquid.get(estate, 0.)
        variables[f"sol_location_{estate}_net_income"] = liquid.get(estate, 0.)
        variables[f"sol_location_{estate}_base_spending"] = base.get(estate, 0.)
    variables["sol_location_liquid_funds"] = sum(liquid.values())
    variables["sol_location_total_income"] = sum(liquid.values())
    variables["sol_location_base_total_spending"] = sum(base.values())
    place = Scope("location", variables=variables, owner=owner, pops=pops or {})
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
    location(country, {"nobles": 6, "commoners": 3}, {"nobles": 4, "commoners": 6}, {"nobles": .5, "peasants": 2})
    location(country, {"burghers": 2, "commoners": 1}, {"burghers": 1, "commoners": 4}, {"burghers": .25, "laborers": 1})
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
    def test_native_flat_and_percent_formula_and_floors(self):
        # x, flat contributions, percent contributions, expected SOL.
        for x, flat, percent, expected in (
                (1, (.2,), (.05,), 1.25),
                (1, (.2,), (.05, .03), 1.28),
                (1, (.2,), (-1.5,), .2),
                (1, (.2,), (-1,), .2),
                (.05, (-.1,), (), 0),
                (1, (-2,), (.05,), 0),
                (0, (.2,), (.5,), .2),
                (300, (.05,), (.05,), 315.05)):
            with self.subTest(x=x, flat=flat, percent=percent):
                runtime, country = LivingStandardRuntime(), Scope("country")
                place = location(country, {"commoners": x / 12}, {"commoners": .5}, {"peasants": 1})
                before = dict(place.variables)
                place.external.update({FLAT_MODIFIER: sum(flat), PERCENT_MODIFIER: sum(percent)})
                solve(runtime, country)
                self.assertAlmostEqual(place.variables["sol_location_sol"], expected)
                self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], expected)
                for name, value in before.items():
                    self.assertEqual(place.variables[name], value, name)

    def test_building_sources_combine_with_population_weights_and_feedback(self):
        runtime, country = LivingStandardRuntime(), fixture()
        solve(runtime, country)
        before = [dict(p.variables) for p in country.locations]
        coefficients = {building: (modifier, float(value)) for building, modifier, value in BUILDING_SOURCES}
        # Model native modifier totals supplied by the engine; this fixture does
        # not claim to execute building-level or goods-access scaling in EU5.
        sources = (("hospital", "aqueduct_system", "tanning_workshop", "theater", "opera_house"),
                   ("pest_house", "iron_mill", "library"))
        expected_total = 0
        for place, snapshot, buildings in zip(country.locations, before, sources):
            for building in buildings:
                modifier, amount = coefficients[building]
                place.external[modifier] = place.external.get(modifier, 0) + amount
            flat, percent = place.external.get(FLAT_MODIFIER, 0), place.external.get(PERCENT_MODIFIER, 0)
            population = sum(place.pops.values())
            expected = flat + (1 + percent) * snapshot["sol_location_sol"]
            runtime.run("sol_compute_location_living_standard", place)
            runtime.run("sol_apply_location_living_standard_modifiers", place)
            self.assertAlmostEqual(place.variables["sol_location_sol"], expected)
            self.assertAlmostEqual(place.modifiers[FEEDBACK_MODIFIERS[0]], min(.5, .02 * expected))
            for name, value in snapshot.items():
                if "sol_total" not in name and name != "sol_location_sol":
                    self.assertEqual(place.variables[name], value, name)
            expected_total += expected * population
        solve(runtime, country)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], expected_total / country.variables["sol_ls_pop_all"])

    def test_percent_estate_override_only_affects_target_estate(self):
        runtime, country = LivingStandardRuntime(), fixture()
        solve(runtime, country)
        before = dict(country.variables)
        boosted = LivingStandardRuntime({"sol_location_nobles_local_sol_percent_value": .25})
        solve(boosted, country)
        self.assertAlmostEqual(country.variables["sol_ls_sol_nobles"], before["sol_ls_sol_nobles"] * 1.25)
        for estate in ("commoners", "burghers"):
            self.assertEqual(country.variables[public_name(estate)], before[public_name(estate)])

    def test_first_batch_native_definitions_and_inherited_compatibility(self):
        expected_flat = dict(hospital=.05, lazaretto=.03, pest_house=.03, aqueduct_system=.02,
                             darussifa=.08, charite_of_berlin=.06, magistrato_alla_sanita=.06,
                             tanning_workshop=-.01, tannery_manufactory=-.02, tannery_mill=-.03,
                             putrefaction_works=-.02, putrefaction_mill=-.03, iron_mill=-.02, steel_mill=-.02)
        expected_percent = dict(theater=.02, opera_house=.03, library=.01)
        sources = parse(render_building_sources())
        self.assertEqual({n.key for n in sources}, {f"TRY_INJECT:{key}" for key in expected_flat | expected_percent})
        for source in sources:
            building = source.key.removeprefix("TRY_INJECT:")
            self.assertEqual([n.key for n in source.value], ["modifier"])
            fields = source.value[0].value
            self.assertEqual(len(fields), 1)
            modifier = FLAT_MODIFIER if building in expected_flat else PERCENT_MODIFIER
            self.assertEqual(fields[0].key, modifier)
            self.assertEqual(float(fields[0].value), (expected_flat | expected_percent)[building])
        types = {n.key: {f.key: f.value for f in n.value} for n in parse(render_modifier_types())}
        self.assertEqual(set(types), {FLAT_MODIFIER, PERCENT_MODIFIER})
        self.assertEqual(types[FLAT_MODIFIER]["decimals"], "2")
        self.assertEqual(types[PERCENT_MODIFIER]["percent"], "yes")
        for definition in types.values():
            self.assertEqual(definition["game_data"][0].value, "location")
        for target in ALL_TARGETS:
            # Compatibility submods inherit stable's additive definitions.
            roots = [ROOT / "src/stable", ROOT / "src" / target] if target not in BASE_TARGETS else [ROOT / "src" / target]
            expected = {
                "in_game/common/building_types/SOL_living_standard_buildings.txt": render_building_sources(),
                "main_menu/common/modifier_type_definitions/SOL_living_standard_modifier_types.txt": render_modifier_types(),
                "main_menu/common/modifier_icons/SOL_living_standard_modifier_icons.txt": render_modifier_icons(),
            }
            for language in ("english", "simp_chinese"):
                expected[f"main_menu/localization/{language}/SOL_living_standard_modifier_types_l_{language}.yml"] = render_modifier_type_localization(language)
            for relative, content in expected.items():
                path = next(root / relative for root in reversed(roots) if (root / relative).is_file())
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertEqual(path.read_text(encoding="utf-8-sig"), content)
            for icon in parse(render_modifier_icons()):
                for field in icon.value:
                    self.assertTrue((roots[0] / "main_menu" / field.value).is_file())

    def test_feedback_boundaries_and_native_units(self):
        runtime = LivingStandardRuntime()
        modifiers = {n.key: {c.key: c.value for c in n.value}
                     for n in parse(render_feedback_modifiers())}
        migration, low, high = FEEDBACK_MODIFIERS
        place = Scope("location")
        for sol, attraction, growth in ((0, 0, -.001), (.09999, .0019998, -.001),
                                        (.1, .002, 0), (1, .02, 0), (5, .1, 0),
                                        (10, .2, 0), (10.00001, .2000002, .001),
                                        (24.99999, .4999998, .001), (25, .5, .001),
                                        (25.00001, .5, .001), (100, .5, .001)):
            with self.subTest(sol=sol):
                place.variables['sol_location_sol'] = sol
                # Reapply twice to verify replacement rather than accumulation.
                for _ in range(2):
                    runtime.run('sol_apply_location_living_standard_modifiers', place)
                self.assertAlmostEqual(place.modifiers[migration] * float(modifiers[migration]['local_migration_attraction']), attraction)
                actual_growth = sum(place.modifiers.get(name, 0) * float(modifiers[name]['local_population_growth'])
                                    for name in (low, high))
                self.assertAlmostEqual(actual_growth, growth)
                self.assertFalse(low in place.modifiers and high in place.modifiers)

    def test_missing_sol_clears_feedback_and_is_neutral(self):
        runtime, place = LivingStandardRuntime(), Scope('location')
        for sol in (0, 20):
            place.variables['sol_location_sol'] = sol
            runtime.run('sol_apply_location_living_standard_modifiers', place)
            del place.variables['sol_location_sol']
            runtime.run('sol_apply_location_living_standard_modifiers', place)
            self.assertFalse(place.modifiers)
        runtime.run('sol_clear_location_living_standard_modifiers', place)
        self.assertFalse(place.modifiers)

    def test_feedback_follows_local_sol_and_modifier_without_changing_demand(self):
        runtime, country = LivingStandardRuntime(), Scope('country')
        poor = location(country, {'commoners': .001}, {'commoners': 5}, {'peasants': 1})
        rich = location(country, {'commoners': 1}, {'commoners': 5}, {'peasants': 1})
        solve(runtime, country)
        snapshots = [dict(place.variables) for place in country.locations]
        for place in country.locations:
            runtime.run('sol_apply_location_living_standard_modifiers', place)
        self.assertIn(FEEDBACK_MODIFIERS[1], poor.modifiers)
        self.assertIn(FEEDBACK_MODIFIERS[2], rich.modifiers)
        for place, before in zip(country.locations, snapshots):
            self.assertEqual(place.variables, before)
        boosted = LivingStandardRuntime({'sol_location_local_sol_modifier_value': 11})
        solve(boosted, country)
        boosted.run('sol_apply_location_living_standard_modifiers', poor)
        self.assertIn(FEEDBACK_MODIFIERS[2], poor.modifiers)
        self.assertNotIn(FEEDBACK_MODIFIERS[1], poor.modifiers)
        for place, before in zip(country.locations, snapshots):
            for name, value in before.items():
                if 'sol_total' not in name and name != 'sol_location_sol':
                    self.assertEqual(place.variables[name], value, name)

    def test_feedback_uses_existing_apply_pass_and_cleanup_paths(self):
        for target in BASE_TARGETS:
            effects = {node.key: node.value for _, node in effects_of(target)}
            apply_nodes = list(walk(effects['sol_apply_local_pop_demand_modifiers']))
            self.assertEqual(sum(n.key == 'every_owned_location' for n in apply_nodes), 1)
            self.assertEqual(sum(n.key == 'sol_apply_location_living_standard_modifiers' for n in apply_nodes), 1)
            feedback = list(walk(effects['sol_apply_location_living_standard_modifiers']))
            self.assertFalse(any(n.key.startswith('every_') for n in feedback))
            for node in feedback:
                if node.key == 'add_location_modifier':
                    fields = {n.key: n.value for n in node.value}
                    self.assertEqual(fields['months'], '1')
                    self.assertEqual(fields['mode'], 'replace')
        for target in ('stable', 'sol_pp_compatibility_submod', 'sol_mnt_compatibility_submod'):
            folder = ROOT / 'src' / target / 'in_game/common/scripted_effects'
            path = next(folder.glob('*cmm_effects.txt'))
            effects = {n.key.removeprefix('REPLACE:'): n.value for n in parse(path.read_text(encoding='utf-8-sig'))}
            callbacks = list(walk(effects['sol_handle_cmf_callback']))
            setting = next(n for n in callbacks if n.key == 'flag:sol__sol_on')
            self.assertTrue(any(n.key == 'sol_clear_location_living_standard_modifiers' for n in walk([setting])))
        actions = parse((ROOT / 'src/stable/in_game/common/on_action/SOL_economy_on_actions.txt').read_text(encoding='utf-8-sig'))
        cleanup = next(n for n in actions if n.key == 'sol_substitution_cleanup_monthly_pulse')
        self.assertTrue(any(n.key == 'sol_clear_location_living_standard_modifiers' for n in walk([cleanup])))

    def test_generated_feedback_definitions_and_bilingual_names(self):
        for target in BASE_TARGETS:
            root = ROOT / 'src' / target / 'main_menu'
            paths = {root / 'common/static_modifiers/SOL_living_standard_modifiers.txt': render_feedback_modifiers()}
            for language in ('english', 'simp_chinese'):
                paths[root / f'localization/{language}/SOL_living_standard_modifiers_l_{language}.yml'] = render_feedback_localization(language)
            for path, expected in paths.items():
                self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
                self.assertEqual(path.read_text(encoding='utf-8-sig'), expected)
            definitions = parse(render_feedback_modifiers())
            for definition in definitions:
                self.assertEqual(next(n.value for n in definition.value if n.key == 'game_data')[0].value, 'location')

    def test_zero_modifier_is_annual_funds_per_thousand(self):
        runtime, country = LivingStandardRuntime(), fixture()
        solve(runtime, country)
        for place in country.locations:
            for estate in ESTATES:
                self.assertAlmostEqual(place.variables[f"sol_location_{estate}_sol_total"],
                                       place.variables[f"sol_location_{estate}_liquid_funds"] * 12)
            self.assertAlmostEqual(place.variables["sol_location_sol"],
                                   place.variables["sol_location_liquid_funds"] * 12 / sum(place.pops.values()))
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 12 * 12 / 3.75)
        self.assertAlmostEqual(country.variables["sol_ls_sol_nobles"], 6 * 12 / .5)
        self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], 4 * 12 / 3)
        self.assertAlmostEqual(country.variables["sol_ls_sol_burghers"], 2 * 12 / .25)
        self.assertEqual(runtime.value("sol_ls_sol_display", country), country.variables["sol_ls_sol"])

    def test_purchasing_power_is_sol_over_annual_baseline_when_modifier_is_zero(self):
        runtime, country = LivingStandardRuntime(), fixture()
        solve(runtime, country)
        for place in country.locations:
            annual_baseline = place.variables["sol_location_base_total_spending"] * 12 / sum(place.pops.values())
            purchasing_power = place.variables["sol_location_liquid_funds"] / place.variables["sol_location_base_total_spending"]
            self.assertAlmostEqual(place.variables["sol_location_sol"] / annual_baseline, purchasing_power)

    def test_hand_calculated_example_uses_population_weights(self):
        runtime, country = LivingStandardRuntime(), Scope("country")
        place = location(country, {"commoners": .3, "nobles": .4},
                         {"commoners": .2, "nobles": .2}, {"peasants": 2, "nobles": .05})
        solve(runtime, country)
        self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], 1.8)
        self.assertAlmostEqual(country.variables["sol_ls_sol_nobles"], 96)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 8.4 / 2.05)
        self.assertAlmostEqual(place.variables["sol_location_liquid_funds"] / place.variables["sol_location_base_total_spending"], 1.75)

    def test_modifier_adds_same_amount_without_touching_purchasing_power(self):
        country = fixture()
        solve(LivingStandardRuntime(), country)
        before_country = dict(country.variables)
        snapshots = [dict(place.variables) for place in country.locations]
        solve(LivingStandardRuntime({"sol_location_local_sol_modifier_value": 3}), country)
        for metric in ("all", "nobles", "burghers", "commoners"):
            name = public_name(metric)
            self.assertAlmostEqual(country.variables[name], before_country[name] + 3)
        for place, snapshot in zip(country.locations, snapshots):
            for name, value in snapshot.items():
                if "sol_total" not in name and name != "sol_location_sol":
                    self.assertEqual(place.variables[name], value, name)
            self.assertAlmostEqual(place.variables["sol_location_sol"], snapshot["sol_location_sol"] + 3)

    def test_negative_modifier_floors_each_estate_before_aggregation(self):
        country = fixture()
        solve(LivingStandardRuntime({"sol_location_nobles_local_sol_modifier_value": -200}), country)
        self.assertEqual(country.variables["sol_ls_sol_nobles"], 0)
        self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], 16)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 6 * 12 / 3.75)

    def test_zero_baseline_has_sol_but_zero_population_clears_stale_values(self):
        runtime, country = LivingStandardRuntime(), Scope("country")
        place = location(country, {"tribesmen": 2}, {}, {"tribesmen": 4})
        country.variables["sol_ls_sol_clergy"] = 5
        solve(runtime, country)
        self.assertAlmostEqual(country.variables["sol_ls_sol_tribesmen"], 6)
        self.assertNotIn(public_name("clergy"), country.variables)
        place.pops.clear()
        place.variables["sol_location_tribesmen_liquid_funds"] = 0
        solve(runtime, country)
        self.assertNotIn("sol_location_sol", place.variables)
        self.assertNotIn("sol_ls_sol", country.variables)
        self.assertEqual(runtime.value("sol_ls_sol_display", country), 0)

    def test_zero_baseline_tribesmen_rank_and_world_average_conserves_totals(self):
        from test_sol_lshud_ranking import RankingRuntime
        settled, tribal = fixture(), Scope("country")
        location(tribal, {"tribesmen": 2}, {}, {"tribesmen": 4})
        for item in (settled, tribal):
            solve(LivingStandardRuntime(), item)
            item.population = item.variables["sol_ls_pop_all"]
        # Single-location countries are unranked; give the tribal fixture a second (empty) location.
        tribal.locations.append(Scope("location"))
        ranking = RankingRuntime([settled, tribal])
        ranking.refresh()
        self.assertIn("sol_ls_rank", tribal.variables)
        self.assertEqual(tribal.variables["sol_ls_rank_tribesmen"], 1)
        self.assertEqual(ranking.globals["sol_ls_world_sol_tribesmen"], 6)
        self.assertAlmostEqual(ranking.globals["sol_ls_world_sol"], (12 * 12 + 2 * 12) / (3.75 + 4))

    def test_baseline_rescaling_changes_power_but_not_sol(self):
        runtime, country = LivingStandardRuntime(), fixture()
        solve(runtime, country)
        previous = dict(country.variables)
        powers = [p.variables["sol_location_liquid_funds"] / p.variables["sol_location_base_total_spending"] for p in country.locations]
        for place in country.locations:
            for name in place.variables:
                if "base_" in name:
                    place.variables[name] *= 2
        solve(runtime, country)
        for name, value in previous.items():
            self.assertEqual(country.variables[name], value, name)
        for place, old in zip(country.locations, powers):
            self.assertAlmostEqual(place.variables["sol_location_liquid_funds"] / place.variables["sol_location_base_total_spending"], old / 2)

    def test_sol_surfaces_never_format_amounts_as_percent_or_subtract_one(self):
        for target in ALL_TARGETS:
            for path in (ROOT / "src" / target).rglob("*"):
                if path.suffix not in (".gui", ".yml"):
                    continue
                text = path.read_text(encoding="utf-8-sig")
                for binding in re.findall(r"\[[^\]\n]*\]", text):
                    if re.search(r"sol_ls_(?:sol(?:_(?:nobles|clergy|burghers|commoners|tribesmen|display))?|(?:top|world)_sol(?:_\w+)?)['\"]|sol_map_living_standard_value", binding):
                        self.assertNotRegex(binding, r"\|[^\]]*%", str(path))
                        self.assertNotIn("Subtract_CFixedPoint", binding, str(path))

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
            wrapper = [n.key for n in effects["sol_solve_country_pop_demand"]]
            self.assertEqual(wrapper[0], "sol_ls_reset_country_living_standard")
            self.assertLess(wrapper.index("sol_ls_finalize_country_living_standard"),
                            wrapper.index("sol_ls_finalize_country_living_standard_yoy"))
            accumulator = effects["sol_ls_accumulate_country_living_standard"]
            names = {n.value[0].value for n in walk(accumulator) if n.key == "change_variable"}
            self.assertIn("sol_ls_pop_all", names)
            self.assertIn("sol_ls_sol_total_all", names)
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
