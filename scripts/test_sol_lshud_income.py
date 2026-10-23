"""Execute living-standard annual sampling effects in the offline scope fixture."""

from pathlib import Path
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gen_market_unit_consumption import _load_good_rows
from sol_lshud_income_source import ESTATES, METRICS, _public_names, render_yoy_effects, render_yoy_values
from test_sol_substitution import Runtime, Scope, parse
from sol_living_standard_source import render_effects, render_values

ROOT = Path(__file__).resolve().parent.parent


class SolYoyRuntime(Runtime):
    def __init__(self):
        super().__init__(_load_good_rows())
        self.year, self.month, self.day = 1337, 5, 17
        self.effects.update({node.key: node.value for node in parse(render_effects() + render_yoy_effects())})
        self.script_values.update({node.key: node.value for node in parse(render_values() + render_yoy_values())})

    def value(self, node, scope, initial=0.):
        if node == "current_year":
            return self.year
        if node == "current_month":
            return self.month
        if node == "current_day":
            return self.day
        if node == "local_commoner_population":
            return sum(scope.pops.get(key, 0) for key in ("laborers", "peasants", "soldiers"))
        if node == "local_sol_population_sum":
            return sum(scope.pops.values())
        if isinstance(node, str) and node.startswith("modifier:"):
            return scope.external.get(node.removeprefix("modifier:"), 0)
        return super().value(node, scope, initial)

    def sample(self, country, year=None, month=None, day=None):
        if year is not None:
            self.year = year
        if month is not None:
            self.month = month
        if day is not None:
            self.day = day
        self.run("sol_ls_reset_country_living_standard", country)
        for location in country.locations:
            self.run("sol_compute_location_living_standard", location)
            self.run("sol_ls_accumulate_country_living_standard", location)
        self.run("sol_ls_finalize_country_living_standard", country)
        self.run("sol_ls_finalize_country_living_standard_yoy", country)


def country_fixture():
    country = Scope("country")
    # Independent input: monthly liquid funds and thousands of people, unequal
    # population weights. SOL reads liquid funds from the solver.
    for people, income in ((3, 9), (7, 7)):
        variables = {f"sol_location_{estate}_liquid_funds": 0 for estate in ESTATES}
        variables["sol_location_commoners_liquid_funds"] = income
        variables["sol_location_total_income"] = income
        country.locations.append(Scope("location", owner=country,
                                       pops={"peasants": people}, variables=variables,
                                       external={"net_total": income}))
    return country


def scale_funds(country, factor):
    for location in country.locations:
        location.external["net_total"] *= factor
        for estate in ESTATES:
            location.variables[f"sol_location_{estate}_liquid_funds"] *= factor
        location.variables["sol_location_total_income"] *= factor


class SolYoyTests(unittest.TestCase):
    def assert_yoy_unavailable(self, country):
        for metric in METRICS:
            for name in _public_names(metric)[1:]:
                self.assertNotIn(name, country.variables)

    def test_weighted_sol_published_immediately_with_yoy_pending(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        self.assertEqual(country.variables["sol_ls_pop_all"], 10)
        self.assertEqual(country.variables["sol_ls_pop_commoners"], 10)
        self.assertEqual(country.variables["sol_ls_pop_nobles"], 0)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 19.2)
        self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], 19.2)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, year=1338)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 19.2)
        self.assertAlmostEqual(country.variables["sol_ls_sol_commoners"], 19.2)
        self.assertEqual(country.variables["sol_ls_sol_yoy"], 0)
        self.assertNotIn("sol_ls_sol_nobles", country.variables)

    def test_calendar_year_change_and_short_anniversary_do_not_fake_year(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        runtime.sample(country, year=1338, month=1)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, month=5, day=16)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, day=17)
        self.assertIn("sol_ls_sol_yoy", country.variables)

    def test_repeated_refresh_preserves_prior_year_and_rotates_next_year(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        scale_funds(country, 1.1)
        runtime.sample(country, year=1338)
        self.assertAlmostEqual(country.variables["sol_ls_sol_prev"], 19.2)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], .1)
        self.assertEqual(country.variables["sol_ls_sol_yoy_class"], 2)
        scale_funds(country, 2)
        runtime.sample(country)
        self.assertAlmostEqual(country.variables["sol_ls_sol_prev"], 19.2)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], 1.2)
        runtime.sample(country, year=1339)
        self.assertAlmostEqual(country.variables["sol_ls_sol_prev"], 42.24)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], 0)

    def test_monthly_country_compares_same_month_not_latest_month(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        scale_funds(country, 2)
        runtime.sample(country, month=6)
        scale_funds(country, 1.05)
        runtime.sample(country, year=1338, month=5)
        self.assertAlmostEqual(country.variables["sol_ls_sol_prev"], 19.2)
        runtime.sample(country, month=6)
        self.assertAlmostEqual(country.variables["sol_ls_sol_prev"], 38.4)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], .05)

    def test_missed_year_and_month_require_new_full_baseline(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        runtime.sample(country, year=1340)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, year=1341, month=6)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, year=1342)
        self.assertIn("sol_ls_sol_yoy", country.variables)

    def test_zero_prior_sol_is_defined_without_division(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        scale_funds(country, 0)
        runtime.sample(country)
        country.locations[0].external["net_total"] = 1
        country.locations[0].variables["sol_location_commoners_liquid_funds"] = 1
        country.locations[0].variables["sol_location_total_income"] = 1
        runtime.sample(country, year=1338)
        self.assertEqual(country.variables["sol_ls_sol_prev"], 0)
        self.assertEqual(country.variables["sol_ls_sol_yoy"], 0)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 1.2)

    def test_thresholds_and_estate_trends(self):
        runtime, country = SolYoyRuntime(), Scope("country")
        for ratio, expected in ((1.06, 2), (1.05, 2), (1.01, 1), (1, -1), (.99, -1), (.95, -2), (.94, -2)):
            for estate in ("", *(f"_{item}" for item in ESTATES)):
                country.variables[f"sol_ls_sol{estate}"] = 100 * ratio
                country.variables[f"sol_ls_sol_prev{estate}"] = 100
            runtime.run("sol_ls_compute_living_standard_yoy", country)
            for estate in ("", *(f"_{item}" for item in ESTATES)):
                self.assertEqual(country.variables[f"sol_ls_sol_yoy_class{estate}"], expected)

    def test_current_sol_updates_and_stale_yoy_clears_without_matching_baseline(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        runtime.sample(country, year=1338)
        self.assertEqual(country.variables["sol_ls_sol_yoy"], 0)
        scale_funds(country, 2)
        runtime.sample(country, month=6)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 38.4)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, year=1339, month=5, day=16)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 38.4)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, day=17)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], 1)

    def test_first_year_sol_keeps_updating_without_fabricating_yoy(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country, year=1337, month=4, day=1)
        scale_funds(country, 2)
        runtime.sample(country, month=5)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 38.4)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, year=1338, month=1)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 38.4)
        self.assert_yoy_unavailable(country)
        runtime.sample(country, month=4)
        self.assertAlmostEqual(country.variables["sol_ls_sol_prev"], 19.2)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], 1)
        runtime.sample(country, month=5)
        self.assertAlmostEqual(country.variables["sol_ls_sol_prev"], 38.4)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], 0)

    def test_countries_keep_separate_samples(self):
        runtime = SolYoyRuntime()
        first, second = country_fixture(), country_fixture()
        runtime.sample(first)
        scale_funds(second, 2)
        runtime.sample(second)
        runtime.sample(first, year=1338)
        runtime.sample(second)
        self.assertAlmostEqual(first.variables["sol_ls_sol"], 19.2)
        self.assertAlmostEqual(second.variables["sol_ls_sol"], 38.4)

    def test_legacy_income_samples_cannot_supply_sol_baseline(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        country.variables.update(sol_ls_pci=1.86, sol_ls_sample_5_year=1337,
                                 sol_ls_sample_5_day=17, sol_ls_sample_5_all=1.86)
        runtime.sample(country, year=1338)
        self.assert_yoy_unavailable(country)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 19.2)
        self.assertEqual(country.variables["sol_ls_sample_5_all"], 1.86)
        runtime.sample(country, year=1339)
        self.assertEqual(country.variables["sol_ls_sol_yoy"], 0)

    def test_sol_modifier_changes_yoy_without_changing_funds(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        for place in country.locations:
            place.external["local_sol_living_standard"] = 3
        runtime.sample(country, year=1338)
        self.assertAlmostEqual(country.variables["sol_ls_sol"], 22.2)
        self.assertAlmostEqual(country.variables["sol_ls_sol_yoy"], 3 / 19.2)

    def test_absent_population_has_no_current_or_annual_sol(self):
        runtime, country = SolYoyRuntime(), country_fixture()
        runtime.sample(country)
        runtime.sample(country, year=1338)
        country.locations.clear()
        runtime.sample(country)
        self.assertNotIn("sol_ls_sol", country.variables)
        self.assert_yoy_unavailable(country)
        country.locations = country_fixture().locations
        for place in country.locations:
            place.owner = country
        runtime.sample(country, year=1339)
        self.assert_yoy_unavailable(country)

    def test_both_solver_paths_accumulate_inside_existing_preparation_pass(self):
        for target in ("stable", "sol_standalone"):
            nodes = parse((ROOT / "src" / target / "in_game/common/scripted_effects/A_SOL_economy_effects.txt").read_text(encoding="utf-8-sig"))
            effects = {node.key: node.value for node in nodes}
            wrapper = [node.key for node in effects["sol_solve_country_pop_demand"]]
            self.assertEqual(wrapper[0], "sol_ls_reset_country_living_standard")
            self.assertEqual(wrapper[-1], "sol_ls_finalize_country_living_standard_yoy")
            for effect in ("sol_solve_country_pop_demand_raw_only", "sol_solve_country_pop_demand_solver"):
                def paths(items, parents=()):
                    for node in items:
                        yield node.key, parents
                        if isinstance(node.value, list):
                            yield from paths(node.value, (*parents, node.key))
                calls = [parents for key, parents in paths(effects[effect]) if key == "sol_ls_accumulate_country_living_standard"]
                self.assertEqual(len(calls), 1)
                self.assertIn("every_owned_location", calls[0])
            self.assertNotIn("every_owned_location", render_yoy_effects())


if __name__ == "__main__":
    unittest.main()
