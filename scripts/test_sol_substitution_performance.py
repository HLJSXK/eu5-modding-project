"""Verify aggregation against the independent oracle and monthly write costs."""
import random
import sys
import unittest
from decimal import Decimal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gen_market_unit_consumption import _load_good_rows
from sol_substitution import CORE, POPS, aggregate, response
from test_sol_substitution import Runtime, Scope, parse


class SavedValueRuntime(Runtime):
    """Exact decimal guard replay; not a general engine fixed-point emulator."""
    def value(self, node, scope, initial=0.):
        if isinstance(node, str) and node.startswith('modifier:global_'):
            good = node[len('modifier:global_'):-len('_pop_demand')]
            return (Decimal(str(scope.external.get(good, 0))) +
                    Decimal(str(scope.modifiers.get('sol_substitute_' + good, 0))))
        result = super().value(node, scope, Decimal(str(initial)))
        return Decimal(str(result)) if isinstance(result, (int, float)) else result


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

    def test_clean_months_do_not_rewrite_country_modifiers(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        self.assertTrue(country.modifiers)
        before = country.modifiers.copy()
        rt.operations.clear()
        for _ in range(24):
            rt.run('sol_check_substitution_snapshot', country)
            self.assertEqual(country.variables['sol_substitute_dirty'], 0)
            rt.run('sol_apply_country_substitution', country)
        self.assertEqual(rt.operations['add_country_modifier'], 0)
        self.assertEqual(rt.operations['remove_country_modifier'], 0)
        self.assertEqual(before, country.modifiers)
        self.assertEqual(rt.operations['change_local_variable'], 0)

    def test_repeated_solve_preserves_modifiers_without_write(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        rt.operations.clear()
        rt.run('sol_refresh_country_substitution', country)
        self.assertEqual(rt.operations['add_country_modifier'], 0)
        self.assertEqual(rt.operations['remove_country_modifier'], 0)

    def test_tiny_external_change_and_missing_modifier_force_refresh(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        country.external['cloth'] += .00001
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        country.modifiers.pop('sol_substitute_cloth')
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        self.assertIn('sol_substitute_cloth', country.modifiers)

    def test_request_cache_difference_is_not_external_change(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        # Corrupt only the request cache. The actual modifier stays correct.
        country.variables['sol_sub_applied_cloth'] = 999
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 0)
        self.assertNotIn('sol_sub_perf_dirty_count', country.variables)
        rt.run('sol_refresh_country_substitution', country)
        self.assertEqual(country.variables['sol_sub_external_cloth'], .25)
        self.assertEqual(country.variables['sol_sub_perf_refresh_count'], 2)

    def test_actual_own_drift_is_repaired_without_external_contamination(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        country.modifiers['sol_substitute_cloth'] = -.03125
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        self.assertEqual(country.variables['sol_sub_perf_dirty_reason'], 7)
        rt.run('sol_refresh_country_substitution', country)
        self.assertEqual(country.variables['sol_sub_external_cloth'], .25)
        self.assertAlmostEqual(country.modifiers['sol_substitute_cloth'], country.variables['sol_sub_size_cloth'])
        self.assertAlmostEqual(country.variables['sol_good_effective_cloth'],
                               .25 + country.modifiers['sol_substitute_cloth'])

    def test_stable_live_strength_different_from_request_does_not_force_solve(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        # Model a confirmed live strength differing from the requested value,
        # followed by aggregate readback catching up. No real engine rounding
        # behavior is assumed; both native-visible quantities are explicit.
        country.modifiers['sol_substitute_cloth'] = -.03125
        country.variables['sol_sub_live_cloth'] = -.03125
        country.variables['sol_good_effective_cloth'] = .25 - .03125
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 0)
        self.assertNotIn('sol_sub_perf_dirty_count', country.variables)
        rt.operations.clear()
        rt.run('sol_apply_country_substitution', country)
        self.assertEqual(rt.operations['add_country_modifier'], 0)

    def test_delayed_aggregate_readback_keeps_ai_clean_across_goods(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        # Reproduce saved traces in fixed binary-exact form for float fixtures:
        # native own already updated, observed aggregate still from before it.
        # Covers positive/negative own sizes and positive/zero external floors.
        cases = (('amber', .25, 0.), ('beeswax', -.125, .5),
                 ('beer', -.25, -1.25), ('cloth', .125, -.75))
        for good, own, external in cases:
            country.external[good] = external
            country.modifiers['sol_substitute_' + good] = own
            country.variables['sol_sub_applied_' + good] = own
            country.variables['sol_sub_live_' + good] = own
            country.variables['sol_sub_external_' + good] = max(1 + external, 0.)
            country.variables['sol_demand_observed_total_' + good] = external
        for _ in range(12):
            rt.run('sol_check_substitution_snapshot', country)
            self.assertEqual(country.variables['sol_substitute_dirty'], 0)
        self.assertNotIn('sol_sub_perf_dirty_count', country.variables)

    def test_old_local_effect_clamp_reproduces_mass_dirty_trigger(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        country.modifiers['sol_substitute_amber'] = .25
        country.variables.update(sol_sub_applied_amber=.25, sol_sub_live_amber=.25,
                                 sol_sub_external_amber=1., sol_demand_observed_total_amber=0.)
        original = '''
            set_local_variable = { name = sol_sub_check_external value = { value = 1 add = modifier:global_amber_pop_demand } }
            change_local_variable = { name = sol_sub_check_external subtract = local_var:sol_sub_check_actual_own }
            change_local_variable = { name = sol_sub_check_external min = 0 }
        '''
        rt.local_context['sol_sub_check_actual_own'] = .25
        rt.execute(parse(original), country)
        self.assertEqual(rt.local_context['sol_sub_check_external'], 0.)
        self.assertNotEqual(rt.local_context['sol_sub_check_external'], country.variables['sol_sub_external_amber'])
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 0)

    def test_saved_dan_tur_nor_readback_values_do_not_force_solve(self):
        traces = (('DAN', 'amber', '-0.13527', '-0.13511'),
                  ('TUR', 'beeswax', '0.26545', '0.26557'),
                  ('NOR', 'amber', '0.19859', '0.19885'))
        for tag, good, old_total, actual in traces:
            with self.subTest(country=tag):
                rt = SavedValueRuntime(_load_good_rows())
                country = Scope('country', human=False)
                market = rt.market({})
                loc = Scope('location', owner=country, market=market)
                country.locations = [loc]
                country.variables.update(sol_demand_snapshot_initialized=1,
                                         sol_demand_snapshot_locations=1,
                                         sol_demand_snapshot_human=0,
                                         sol_demand_snapshot_enabled=1,
                                         sol_demand_snapshot_version=2)
                loc.variables.update(sol_demand_snapshot_country=country,
                                     sol_demand_snapshot_market=market)
                for member in CORE:
                    country.variables['sol_sub_external_' + member] = Decimal(1)
                    country.variables['sol_good_effective_' + member] = Decimal(1)
                    country.variables['sol_demand_observed_total_' + member] = Decimal(0)
                country.modifiers['sol_substitute_' + good] = Decimal(actual)
                country.variables['sol_sub_live_' + good] = Decimal(actual)
                country.variables['sol_sub_applied_' + good] = Decimal(actual)
                country.variables['sol_demand_observed_total_' + good] = Decimal(old_total)
                rt.run('sol_check_substitution_snapshot', country)
                self.assertEqual(country.variables['sol_substitute_dirty'], 0)
                self.assertNotIn('sol_sub_perf_dirty_count', country.variables)
                self.assertEqual(country.variables['sol_demand_observed_total_' + good], Decimal(actual))

    def test_real_external_change_records_reason_and_actual_strength(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        requested = country.variables['sol_sub_applied_cloth']
        country.modifiers['sol_substitute_cloth'] = -.03125
        country.variables['sol_sub_live_cloth'] = -.03125
        country.external['cloth'] += .00001
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        self.assertEqual(country.variables['sol_sub_perf_dirty_count'], 1)
        self.assertEqual(country.variables['sol_sub_perf_dirty_reason'], 6)
        self.assertEqual(CORE[int(country.variables['sol_sub_perf_dirty_good']) - 1], 'cloth')
        self.assertEqual(country.variables['sol_sub_perf_cached_own'], requested)
        self.assertEqual(country.variables['sol_sub_perf_actual_own'], -.03125)
        self.assertAlmostEqual(country.variables['sol_sub_perf_external_now'], .25001)
        rt.run('sol_refresh_country_substitution', country)
        self.assertAlmostEqual(country.variables['sol_sub_external_cloth'], .25001)

    def test_missing_modifier_reason_and_first_dirty_cause(self):
        _, rt, country, market = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        country.modifiers.pop('sol_substitute_cloth')
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_sub_perf_dirty_reason'], 5)
        rt.run('sol_refresh_country_substitution', country)
        rt.maps.pop(('sol_market_substitute_cache', id(market)))
        country.external['cloth'] += .00001
        # Market-cache failure precedes external checks and remains the cause.
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_sub_perf_dirty_reason'], 4)
        self.assertEqual(country.variables['sol_sub_perf_dirty_count'], 2)

    def test_structural_dirty_does_not_retain_previous_goods_payload(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        country.external['cloth'] += .00001
        rt.run('sol_check_substitution_snapshot', country)
        self.assertIn('sol_sub_perf_external_now', country.variables)
        rt.run('sol_refresh_country_substitution', country)
        country.locations.pop()
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_sub_perf_dirty_reason'], 2)
        self.assertEqual(country.variables['sol_sub_perf_dirty_good'], 0)
        for field in ('old_total', 'new_total', 'cached_own', 'actual_own', 'external_now'):
            self.assertNotIn('sol_sub_perf_' + field, country.variables)

    def test_old_snapshot_and_enable_toggle_invalidate(self):
        _, rt, country, _ = self.fixture()
        rt.run('sol_refresh_country_substitution', country)
        country.variables.pop('sol_demand_snapshot_enabled')
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        rt.enabled = False
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        self.assertFalse(country.modifiers)
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 0)
        rt.enabled = True
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)

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
