"""Execute the generated SOL world ranking with offline country scopes."""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from test_sol_substitution import Runtime, Scope, parse
from sol_lshud_ranking_source import NEIGHBOURS, render_values, render_world_ranking


ROOT = Path(__file__).resolve().parent.parent
EFFECT = "sol_ls_recalculate_world_ranking"
CACHE_KEYS = tuple("sol_ls_" + name for name in ("rank", "percentile", "tier", *NEIGHBOURS))


class LocationCount:
    """Allow country.num_locations without allowing a hidden location scan."""

    def __init__(self, count=1):
        self.count = count

    def __len__(self):
        return self.count

    def __iter__(self):
        raise AssertionError("World ranking must not traverse locations")


@dataclass(eq=False)
class Country(Scope):
    population: float = 100


def country(pci, population=100, locations=1):
    return Country("country", variables={"sol_ls_pci": pci, "sol_ls_pop_all": population},
                   locations=LocationCount(locations), population=population)


def effect_calls(nodes, effect=EFFECT, ancestors=()):
    for node in nodes:
        if node.key == effect:
            yield node, ancestors
        if isinstance(node.value, list):
            yield from effect_calls(node.value, effect, ancestors + (node,))


class RankingRuntime(Runtime):
    """Extend the shared effect interpreter, leaving its original tests intact.

    Iterators consume the emitted order key, limit and max expressions. Ordinary
    variable writes, value arithmetic and saved scope links use the shared
    interpreter, so assertions exercise generated effects rather than a Python
    implementation of the ranking algorithm.
    """

    def __init__(self, countries, source=None):
        # This fixture only needs country ranking values; avoid generating the
        # unrelated substitution goods database in Runtime.__init__.
        self.quantities = {}
        self.prices = {}
        self.maps = {}
        self.saved = {}
        self.enabled = True
        self.operations = Counter()
        self.local_context = {}
        self.effects = {n.key: n.value for n in parse(source or render_world_ranking())}
        self.script_values = {n.key: n.value for n in parse(render_values())}
        self.countries = countries
        self.globals = {}
        self.visits = Counter()

    def value(self, node, scope, initial=0.):
        if isinstance(node, str):
            if node.startswith("global_var:"):
                name, sep, tail = node[len("global_var:"):].partition(".")
                target = self.globals[name]
                return self.value(tail, target) if sep else target
            if node == "total_population":
                return scope.population
        return super().value(node, scope, initial)

    def test(self, node, scope):
        if node.key == "has_global_variable":
            return node.value in self.globals
        if node.key.startswith("global_var:") and isinstance(node.value, list):
            return self.condition(node.value, self.value(node.key, scope))
        return super().test(node, scope)

    def execute(self, nodes, scope):
        taken = False
        for node in nodes:
            key, val = node.key, node.value
            if key == "limit":
                continue
            if key in ("if", "else_if", "else"):
                if key != "if" and taken:
                    continue
                limits = next((n.value for n in val if n.key == "limit"), [])
                allowed = key == "else" or self.condition(limits, scope)
                if key == "if":
                    taken = False
                if allowed and not taken:
                    self.execute([n for n in val if n.key != "limit"], scope)
                    taken = True
                continue
            taken = False
            if key in ("set_global_variable", "change_global_variable"):
                self.operations[key] += 1
                fields = {n.key: n.value for n in val}
                name = fields.pop("name")
                if key == "set_global_variable":
                    self.globals[name] = self.value(fields["value"], scope)
                else:
                    # Reuse the value-block arithmetic parser for add/subtract.
                    self.globals[name] = self.value([n for n in val if n.key != "name"],
                                                    scope, self.globals[name])
            elif key == "remove_global_variable":
                self.operations[key] += 1
                self.globals.pop(val, None)
            elif key in ("every_country", "ordered_country"):
                self.operations[key] += 1
                fields = {n.key: n.value for n in val}
                candidates = [c for c in self.countries if self.condition(fields.get("limit", []), c)]
                metadata = {"limit", "order_by", "max", "min", "check_range_bounds", "position"}
                if key == "ordered_country":
                    candidates.sort(key=lambda c: self.value(fields["order_by"], c), reverse=True)
                    candidates = candidates[:int(self.value(fields.get("max", str(len(candidates))), scope))]
                body = [n for n in val if n.key not in metadata]
                for target in candidates:
                    self.visits[key] += 1
                    self.execute(body, target)
            elif key.startswith("global_var:"):
                self.operations[key] += 1
                self.execute(val, self.value(key, scope))
            elif "location" in key and key.startswith(("every_", "ordered_", "random_")):
                raise AssertionError("World ranking must not traverse locations: " + key)
            else:
                super().execute([node], scope)

    def refresh(self):
        self.run(EFFECT, Scope("global"))


class RankingTests(unittest.TestCase):
    def assert_clean_scratch(self, runtime):
        for name in ("rank_population", "rank_income", "rank_cursor", "rank_previous_1", "rank_previous_2"):
            self.assertNotIn("sol_ls_" + name, runtime.globals)

    def assert_ladder(self, runtime, expected):
        self.assertEqual(runtime.globals["sol_ls_rank_count"], len(expected))
        for index, target in enumerate(expected):
            self.assertEqual(target.variables["sol_ls_rank"], index + 1)
            self.assertAlmostEqual(target.variables["sol_ls_percentile"],
                                   (len(expected) - index - 1) / (len(expected) - 1) if len(expected) > 1 else 0)
            for offset, prefix in ((-1, "above_1"), (-2, "above_2"), (1, "below_1"), (2, "below_2")):
                key = "sol_ls_" + prefix
                neighbour_index = index + offset
                if 0 <= neighbour_index < len(expected):
                    self.assertIs(target.variables[key], expected[neighbour_index])
                else:
                    self.assertNotIn(key, target.variables)
        for index in range(1, 11):
            key = "sol_ls_top_" + str(index)
            if index <= len(expected):
                self.assertIs(runtime.globals[key], expected[index - 1])
            else:
                self.assertNotIn(key, runtime.globals)
        self.assertEqual(sum(runtime.globals["sol_ls_tier_count_" + str(i)] for i in range(3)), len(expected))
        self.assert_clean_scratch(runtime)

    def test_empty_world_clears_previous_global_leaders(self):
        rt = RankingRuntime([])
        rt.globals.update({"sol_ls_top_" + str(i): country(i) for i in range(1, 11)})
        rt.globals.update(sol_ls_rank_count=99, sol_ls_top_pci=99, sol_ls_world_pci=99,
                          sol_ls_tier_count_0=4, sol_ls_tier_count_1=5, sol_ls_tier_count_2=6)
        rt.refresh()
        self.assert_ladder(rt, [])
        self.assertEqual(rt.globals["sol_ls_top_pci"], 0)
        self.assertEqual(rt.globals["sol_ls_world_pci"], 0)
        self.assertEqual(rt.operations["ordered_country"], 0)

    def test_single_country_has_zero_percentile_and_no_neighbours(self):
        target = country(25)
        rt = RankingRuntime([target])
        rt.refresh()
        self.assert_ladder(rt, [target])
        self.assertEqual(target.variables["sol_ls_tier"], 1)
        self.assertEqual(rt.globals["sol_ls_top_pci"], 25)
        self.assertEqual(rt.globals["sol_ls_world_pci"], 25)

    def test_first_january_ranks_current_income_without_prior_year_samples(self):
        from test_sol_lshud_income import IncomeRuntime, country_fixture, scale_income

        for target in ("stable", "sol_standalone"):
            with self.subTest(target=target):
                income = IncomeRuntime()
                player, ai = country_fixture(), country_fixture()
                scale_income(ai, 2)
                # Startup samples exist, but no country has a full-year baseline.
                for item in (player, ai):
                    income.sample(item, year=1337, month=4, day=1)
                    item.population = 10
                # Player keeps sampling monthly; reduced-frequency AI can still
                # rank using its last solve. January has no prior-year baseline.
                scale_income(player, 3)
                income.sample(player, year=1338, month=1)
                for item in (player, ai):
                    self.assertNotIn("sol_ls_pci_yoy", item.variables)
                    self.assertNotIn("sol_ls_pci_prev", item.variables)
                rt = RankingRuntime([player, ai])
                original_value = rt.value
                rt.value = lambda node, scope, initial=0.: 1 if node == "current_month" else original_value(node, scope, initial)
                path = ROOT / "src" / target / "in_game/common/situations/SOL_economy_situation.txt"
                _, ancestors = next(effect_calls(parse(path.read_text(encoding="utf-8-sig"))))
                # Execute the shipped January gate rather than bypassing it.
                rt.execute([ancestors[-1]], Scope("global"))
                self.assert_ladder(rt, [player, ai])
                self.assertAlmostEqual(rt.globals["sol_ls_world_pci"], 48)
                self.assertEqual(player.variables["sol_ls_rank"], 1)
                self.assertEqual(ai.variables["sol_ls_rank"], 2)

    def test_full_ranking_past_top_ten_and_two_neighbours_each_side(self):
        countries = [country(i, population=i * 10) for i in (4, 12, 2, 7, 1, 11, 6, 9, 3, 13, 5, 10, 8)]
        rt = RankingRuntime(countries)
        rt.refresh()
        expected = sorted(countries, key=lambda c: c.variables["sol_ls_pci"], reverse=True)
        self.assert_ladder(rt, expected)
        self.assertEqual(rt.visits["every_country"], 13)
        self.assertEqual(rt.visits["ordered_country"], 13)
        self.assertEqual(rt.operations["every_country"], 1)
        self.assertEqual(rt.operations["ordered_country"], 1)
        self.assertEqual(expected[-1].variables["sol_ls_rank"], 13)

    def test_world_pci_is_cached_population_weighted(self):
        rich, poor = country(20, 10), country(2, 90)
        # Live population gates participation; cached populations weight the census.
        rich.population, poor.population = 1000, 1
        rt = RankingRuntime([poor, rich])
        rt.refresh()
        self.assert_ladder(rt, [rich, poor])
        self.assertAlmostEqual(rt.globals["sol_ls_world_pci"], 3.8)

    def test_exact_low_and_high_thresholds_belong_to_middle_tier(self):
        values = (7.499, 7.5, 13.3, 13.301, 8.4)
        countries = [country(value, 1) for value in values]
        rt = RankingRuntime(countries)
        rt.refresh()
        self.assertEqual(rt.globals["sol_ls_world_pci"], 10)
        self.assertEqual([c.variables["sol_ls_tier"] for c in countries], [0, 1, 1, 2, 1])
        self.assertEqual([rt.globals["sol_ls_tier_count_" + str(i)] for i in range(3)], [1, 3, 1])

    def test_all_zero_world_uses_middle_tier_without_division_by_zero(self):
        countries = [country(0, n) for n in (10, 20, 30)]
        rt = RankingRuntime(countries)
        rt.refresh()
        actual = sorted(countries, key=lambda c: c.variables["sol_ls_rank"])
        self.assert_ladder(rt, actual)
        self.assertEqual(rt.globals["sol_ls_world_pci"], 0)
        self.assertEqual(rt.globals["sol_ls_top_pci"], 0)
        self.assertEqual([c.variables["sol_ls_tier"] for c in countries], [1, 1, 1])

    def test_lost_territory_population_or_income_clears_stale_country_links(self):
        for loss in ("territory", "population", "income", "cached_population", "missing_cached_population"):
            with self.subTest(loss=loss):
                countries = [country(value) for value in (40, 30, 20, 10)]
                rt = RankingRuntime(countries)
                rt.refresh()
                removed = countries[0]
                if loss == "territory":
                    removed.locations.count = 0
                elif loss == "population":
                    removed.population = 0
                elif loss == "income":
                    del removed.variables["sol_ls_pci"]
                elif loss == "cached_population":
                    removed.variables["sol_ls_pop_all"] = 0
                else:
                    del removed.variables["sol_ls_pop_all"]
                rt.refresh()
                self.assert_ladder(rt, countries[1:])
                for key in CACHE_KEYS:
                    self.assertNotIn(key, removed.variables)
                self.assertNotIn(removed, [v for k, v in rt.globals.items() if k.startswith("sol_ls_top_")])
                self.assertEqual(rt.globals["sol_ls_world_pci"], 20)

    def test_equal_income_visits_every_country_without_repeating_ties(self):
        countries = [country(10, index + 1) for index in range(16)]
        rt = RankingRuntime(countries)
        rt.refresh()
        self.assertEqual({c.variables["sol_ls_rank"] for c in countries}, set(range(1, 17)))
        self.assertEqual(rt.visits["ordered_country"], 16)
        actual = sorted(countries, key=lambda c: c.variables["sol_ls_rank"])
        self.assert_ladder(rt, actual)
        self.assertEqual(len({id(rt.globals["sol_ls_top_" + str(i)]) for i in range(1, 11)}), 10)

    def test_existing_ranking_recomputes_after_income_changes_and_shrink(self):
        countries = [country(value) for value in range(1, 13)]
        rt = RankingRuntime(countries)
        rt.refresh()
        for index, target in enumerate(countries):
            target.variables["sol_ls_pci"] = 12 - index
        rt.refresh()
        self.assert_ladder(rt, countries)
        rt.countries = countries[:2]
        rt.refresh()
        self.assert_ladder(rt, countries[:2])
        self.assertEqual(rt.globals["sol_ls_world_pci"], 11.5)

    def test_annual_situation_hook_runs_once_outside_country_iterators(self):
        for target in ("stable", "sol_standalone"):
            with self.subTest(target=target):
                path = ROOT / "src" / target / "in_game/common/situations/SOL_economy_situation.txt"
                found = list(effect_calls(parse(path.read_text(encoding="utf-8-sig"))))
                self.assertEqual(len(found), 1)
                call, ancestors = found[0]
                self.assertEqual(call.value, "yes")
                self.assertIn("on_monthly", [node.key for node in ancestors])
                self.assertFalse(any(node.key.startswith(("every_", "ordered_", "random_")) for node in ancestors))
                annual = ancestors[-1]
                self.assertEqual(annual.key, "if")
                limits = next(node.value for node in annual.value if node.key == "limit")
                self.assertEqual([(node.key, node.op, node.value) for node in limits], [("current_month", "=", "1")])

    def test_manual_resolution_ranks_once_after_all_country_refreshes_in_hidden_effect(self):
        for target in ("stable", "sol_standalone"):
            with self.subTest(target=target):
                path = ROOT / "src" / target / "in_game/common/resolutions/SOL_economy_resolution.txt"
                resolution = next(node for node in parse(path.read_text(encoding="utf-8-sig"))
                                  if node.key == "global_living_standard_recalculate")
                found = list(effect_calls(resolution.value))
                self.assertEqual(len(found), 1)
                call, ancestors = found[0]
                self.assertEqual(call.value, "yes")
                self.assertIn("effect", [node.key for node in ancestors])
                self.assertIn("hidden_effect", [node.key for node in ancestors])
                self.assertFalse(any(node.key.startswith(("every_", "ordered_", "random_")) for node in ancestors))
                recipient_index = next(index for index, node in enumerate(ancestors) if node.key == "scope:recipient")
                recipient = ancestors[recipient_index]
                rank_block = ancestors[recipient_index + 1]
                country_indices = [index for index, node in enumerate(recipient.value) if node.key == "every_country"]
                self.assertEqual(len(country_indices), 1)
                self.assertLess(country_indices[0], recipient.value.index(rank_block))
                self.assertTrue(list(effect_calls(recipient.value[country_indices[0]].value, "gls_full_refresh_country")))

    def test_startup_load_global_helper_ranks_once_after_country_refreshes(self):
        for target in ("stable", "sol_standalone"):
            with self.subTest(target=target):
                path = ROOT / "src" / target / "in_game/common/scripted_effects/A_SOL_economy_effects.txt"
                helper = next(node for node in parse(path.read_text(encoding="utf-8-sig"))
                              if node.key == "gls_recalculate_global_living_standard")
                found = list(effect_calls(helper.value))
                self.assertEqual(len(found), 1)
                call, ancestors = found[0]
                self.assertEqual(call.value, "yes")
                self.assertFalse(ancestors)
                country_indices = [index for index, node in enumerate(helper.value) if node.key == "every_country"]
                self.assertEqual(len(country_indices), 1)
                self.assertLess(country_indices[0], helper.value.index(call))
                self.assertTrue(list(effect_calls(helper.value[country_indices[0]].value, "gls_full_refresh_country")))

    def test_generated_targets_match_source_and_execute_identically(self):
        paths = [ROOT / "src" / target / "in_game/common/scripted_effects/D_SOL_lshud_ranking.txt"
                 for target in ("stable", "sol_standalone")]
        if not any(path.exists() for path in paths):
            self.skipTest("Run gen_sol_lshud.py to emit the ranking targets")
        sources = []
        for path in paths:
            self.assertTrue(path.exists(), str(path))
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), str(path))
            source = path.read_text(encoding="utf-8-sig")
            self.assertEqual(source, render_world_ranking(), str(path))
            for estate in ("nobles", "clergy", "burghers", "commoners", "tribesmen"):
                self.assertIn(f"sol_ls_rank_{estate}", source)
                self.assertIn(f"sol_ls_percentile_{estate}", source)
                self.assertIn(f"sol_ls_top_1_{estate}", source)
            sources.append(source)
            rt = RankingRuntime([country(3), country(7), country(1)], source)
            rt.refresh()
            self.assert_ladder(rt, [rt.countries[1], rt.countries[0], rt.countries[2]])
            value_path = path.parents[1] / "script_values/SOL_lshud_ranking_values.txt"
            values = {n.key: n.value for n in parse(value_path.read_text(encoding="utf-8-sig"))}
            for expected in parse(render_values(standalone="sol_standalone" in path.parts)):
                self.assertEqual(values[expected.key], expected.value, str(value_path))
        self.assertEqual(*sources)


if __name__ == "__main__":
    unittest.main()
