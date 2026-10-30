"""Verify aggregation against the independent oracle and cached auto-modifier evaluation costs."""
import random
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gen_market_unit_consumption import _load_good_rows
from sol_substitution import CORE, POPS, aggregate, response
from test_sol_substitution import Runtime, Scope, parse


class PerformanceTests(unittest.TestCase):
    def test_value_block_floor_is_not_local_effect_minimum(self):
        rt = Runtime(_load_good_rows())
        country = Scope('country')
        rt.execute(parse('''
            set_local_variable = { name = floor value = { value = 1 min = 0 } }
            set_local_variable = { name = effect_min value = 1 }
            change_local_variable = { name = effect_min min = 0 }
        '''), country)
        self.assertEqual(rt.local_context['floor'], 1)
        self.assertEqual(rt.local_context['effect_min'], 0)

    def fixture(self, count=20):
        rows = _load_good_rows()
        rt = Runtime(rows)
        country = Scope('country', human=False, external={'cloth': -.75})
        market = rt.market(dict.fromkeys(CORE, 1.) | {'cloth': .5, 'leather': 2.})
        country.locations = [Scope('location', owner=country, market=market,
                                   pops=dict.fromkeys(POPS, i + .00001)) for i in range(1, count + 1)]
        return rows, rt, country, market

    def test_multimarket_mixed_strata_matches_location_oracle(self):
        from gen_sol_pp_compat import _compat_good_rows
        rng = random.Random(20261015)
        for rows, removed in ((_load_good_rows(), ()), (_compat_good_rows(), {'lumber'})):
            rt = Runtime(rows, removed_goods=removed)
            country = Scope('country', external={g: rng.choice((-1.5, -.75, 0., .125)) for g in CORE})
            weights = [{g: rng.choice((.25, .5, .75, 1., 1.25, 1.5, 2.)) for g in CORE} for _ in range(3)]
            supplied = [{g for g in CORE if rng.random() > .2} for _ in weights]
            markets = [rt.market(w, s) for w, s in zip(weights, supplied)]
            q = {g: {p: round(v[p], 5) for p in POPS} for g, _, v in rows}
            prices = {g: price for g, price, _ in rows}
            bases, responses = [], []
            for index in range(24):
                m = index % len(markets)
                pops = {p: rng.choice((0., .00001, .125, 13.12345, 120.)) for p in POPS}
                country.locations.append(Scope('location', owner=country, market=markets[m], pops=pops))
                for pop in POPS:
                    eligible = {g for g in CORE if q[g][pop] > 0 and g in supplied[m]
                                and 1 + country.external[g] > 0}
                    bases.append({g: pops[pop] * q[g][pop] * prices[g] for g in eligible})
                    responses.append(response(weights[m], eligible, pop=pop, removed_goods=removed))
            # An owned location without a market contributes no basket weight.
            country.locations.append(Scope('location', owner=country, pops=dict.fromkeys(POPS, 999.)))
            expected = aggregate(bases, responses)
            rt.run('sol_refresh_country_substitution', country)
            for good in CORE:
                self.assertAlmostEqual(country.variables['sol_sub_multiplier_' + good], expected.get(good, 1.))
                self.assertAlmostEqual(country.variables['sol_good_effective_' + good],
                                       max(1 + country.external[good], 0.) * expected.get(good, 1.))
            for market in markets:
                self.assertFalse(market.local)
                self.assertFalse(market.variables)

    def test_high_frequency_auto_evaluation_only_reads_caches(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        expected = {good: rt.auto_strength(good, country) for good in CORE}
        self.assertTrue(any(expected.values()))
        before = country.variables.copy(), rt.maps.copy()
        rt.operations.clear()
        original_value = rt.value

        def cached_value(node, scope, initial=0.):
            if isinstance(node, str):
                self.assertFalse(node.startswith(('modifier:', 'country_modifier_strength(',
                                                  'global_variable_map(', 'default_price(',
                                                  'num_pop_type:', 'sol_unit_consumption_')),
                                 'auto modifier must not enter economic calculations')
            return original_value(node, scope, initial)

        rt.value = cached_value
        for _ in range(100):
            for good in CORE:
                self.assertEqual(rt.auto_strength(good, country), expected[good])
        self.assertFalse(rt.operations)
        self.assertEqual((country.variables, rt.maps), before)
        self.assertFalse(country.modifiers)

    def test_repeated_solve_never_grants_static_modifiers_or_accumulates(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        before = {good: rt.auto_strength(good, country) for good in CORE}
        for _ in range(3):
            rt.run('sol_refresh_country_substitution', country)
            for good in CORE:
                self.assertAlmostEqual(rt.auto_strength(good, country), before[good])
        self.assertEqual(rt.operations['add_country_modifier'], 0)
        self.assertEqual(rt.operations['remove_country_modifier'], 0)

    def test_external_changes_update_only_at_next_solve(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        before = rt.auto_strength('cloth', country)
        country.external['cloth'] += .00001
        self.assertEqual(rt.auto_strength('cloth', country), before)
        rt.run('sol_refresh_country_substitution', country)
        self.assertAlmostEqual(country.variables['sol_sub_external_cloth'], .25001)
        self.assertAlmostEqual(country.variables['sol_good_effective_cloth'],
                               .25001 + rt.auto_strength('cloth', country))

    def test_toggle_and_missing_cache_are_immediately_neutral(self):
        _, rt, country, _ = self.fixture()
        self.assertEqual(rt.auto_strength('cloth', country), 0)
        rt.run('sol_refresh_country_substitution', country)
        self.assertNotEqual(rt.auto_strength('cloth', country), 0)
        rt.enabled = False
        self.assertEqual(rt.auto_strength('cloth', country), 0)
        rt.run('sol_refresh_country_substitution', country)
        self.assertAlmostEqual(country.variables['sol_good_effective_cloth'], .25)
        self.assertNotIn('sol_sub_size_cloth', country.variables)
        rt.enabled = True
        self.assertEqual(rt.auto_strength('cloth', country), 0)
        rt.run('sol_refresh_country_substitution', country)
        self.assertNotEqual(rt.auto_strength('cloth', country), 0)
        country.variables.pop('sol_sub_size_cloth')
        self.assertEqual(rt.auto_strength('cloth', country), 0)

    def test_zero_cache_removal_preserves_spending_and_next_solve(self):
        for weight in (.5, 2.):
            with self.subTest(cloth_weight=weight):
                _, rt, country, _ = self.fixture()
                changed_market = rt.market({'cloth': weight, 'leather': 1.})
                for loc in country.locations:
                    loc.market = changed_market
                rt.run('sol_refresh_country_substitution', country)
                previous = rt.auto_strength('cloth', country)
                self.assertNotEqual(previous, 0)
                neutral_market = rt.market(dict.fromkeys(CORE, 1.))
                for loc in country.locations:
                    loc.market = neutral_market
                for _ in range(2):
                    rt.run('sol_refresh_country_substitution', country)
                    self.assertFalse(any('sol_sub_size_' + good in country.variables for good in CORE))
                    self.assertEqual(country.variables['sol_substitute_max_size'], 0)
                    self.assertAlmostEqual(country.variables['sol_good_effective_cloth'], .25)
                    self.assertAlmostEqual(country.variables['sol_sub_external_cloth'], .25)
                    self.assertEqual(rt.auto_strength('cloth', country), 0)
                for loc in country.locations:
                    loc.market = changed_market
                rt.run('sol_refresh_country_substitution', country)
                self.assertAlmostEqual(rt.auto_strength('cloth', country), previous)
                self.assertAlmostEqual(country.variables['sol_sub_external_cloth'], .25)

    def test_inactive_country_cleanup_is_a_noop_after_first_clear(self):
        _, rt, country, market = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        rt.run('sol_clear_country_substitution', country)
        self.assertFalse(country.variables)
        self.assertFalse(country.modifiers)
        self.assertFalse(market.local)
        rt.operations.clear()
        rt.run('sol_clear_country_substitution', country)
        self.assertEqual(rt.operations['remove_variable'], 0)
        self.assertEqual(rt.operations['every_owned_location'], 0)


if __name__ == '__main__':
    unittest.main()
