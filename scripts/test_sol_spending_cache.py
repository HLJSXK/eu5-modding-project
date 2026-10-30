"""Check market spending reuse, ownership isolation and refresh invalidation."""
import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gen_market_unit_consumption import _load_good_rows
from sol_substitution import CORE, POPS
from test_sol_substitution import Runtime, Scope, parse

ROOT = Path(__file__).resolve().parent.parent


class CountingRuntime(Runtime):
    def __init__(self, rows, *, removed_goods=()):
        super().__init__(rows, removed_goods=removed_goods)
        self.spending_reads = 0
        self.cached_spending_reads = 0

    def value(self, node, scope, initial=0.):
        if isinstance(node, str) and node.startswith('global_variable_map(sol_market_good_spending_'):
            self.spending_reads += 1
        if isinstance(node, str) and node.startswith('global_variable_map(sol_country_market_spending_') and not node.startswith('global_variable_map(sol_country_market_spending_owner|'):
            self.cached_spending_reads += 1
        return super().value(node, scope, initial)


class SpendingCacheTests(unittest.TestCase):
    def fixture(self, rows=None, markets=1, locations=1, *, removed_goods=()):
        rows = _load_good_rows() if rows is None else rows
        rt = CountingRuntime(rows, removed_goods=removed_goods)
        country = Scope('country')
        market_scopes = [rt.market(dict.fromkeys(CORE, 1)) for _ in range(markets)]
        for index, market in enumerate(market_scopes):
            for good, price, quantities in rows:
                for pop in POPS:
                    if round(quantities[pop], 5) > 0:
                        rt.maps[(f'sol_market_good_spending_{pop}_{good}', id(market))] = round(quantities[pop], 5) * price * (index + 1)
        country.locations = [Scope('location', owner=country, market=market_scopes[i % markets], pops={'nobles': i + 1}) for i in range(locations)]
        return rows, rt, country, market_scopes

    def expected(self, rows, rt, country, market, pop):
        return sum(rt.maps.get((f'sol_market_good_spending_{pop}_{good}', id(market)), 0.)
                   * (country.variables.get('sol_good_effective_' + good, 1.) if good in CORE else 1.)
                   for good, _, quantities in rows if round(quantities[pop], 5) > 0)

    def assert_spending(self, rows, rt, location):
        for pop in POPS:
            self.assertAlmostEqual(location.variables['sol_unit_spending_' + pop],
                                   self.expected(rows, rt, location.owner, location.market, pop))
        self.assertFalse(location.local)

    def test_large_country_reads_each_market_basket_once(self):
        rows, rt, country, markets = self.fixture(markets=3, locations=180)
        for index, good in enumerate(CORE):
            country.variables['sol_good_effective_' + good] = (index + 1) / len(CORE)
        for location in country.locations:
            rt.run('sol_compute_substitute_unit_spending', location)
            self.assert_spending(rows, rt, location)
        pairs = sum(round(q[pop], 5) > 0 for _, _, q in rows for pop in POPS)
        self.assertEqual(rt.spending_reads, len(markets) * pairs)
        self.assertEqual(pairs, 246)
        # A location-level basket loop would perform 180 * 246 reads here.
        self.assertEqual(rt.spending_reads, 738)
        self.assertEqual(rt.cached_spending_reads, len(country.locations) * len(POPS))
        for market in markets:
            self.assertFalse(market.local)
            self.assertFalse(market.variables)
            self.assertIs(rt.maps[('sol_country_market_spending_owner', id(market))], country)

    def test_shared_market_rebuilds_when_country_changes(self):
        rows, rt, country, markets = self.fixture()
        location = country.locations[0]
        country.variables['sol_good_effective_cloth'] = .25
        other = Scope('country', variables={'sol_good_effective_cloth': 1.5})
        other_location = Scope('location', owner=other, market=markets[0])
        other.locations = [other_location]
        pairs = sum(round(q[pop], 5) > 0 for _, _, q in rows for pop in POPS)
        for expected_reads, current in ((pairs, location), (pairs, location),
                                        (2 * pairs, other_location), (3 * pairs, location)):
            rt.run('sol_compute_substitute_unit_spending', current)
            self.assert_spending(rows, rt, current)
            self.assertEqual(rt.spending_reads, expected_reads)
        self.assertNotEqual(location.variables['sol_unit_spending_nobles'],
                            other_location.variables['sol_unit_spending_nobles'])

    def test_country_refresh_invalidates_same_owner_cache(self):
        rows, rt, country, markets = self.fixture()
        location = country.locations[0]
        rt.run('sol_refresh_country_substitution', country)
        rt.run('sol_compute_substitute_unit_spending', location)
        before = location.variables['sol_unit_spending_nobles']
        country.external['cloth'] = -.75
        # The country's new factors and changed market cost must both be used.
        rt.maps[('sol_market_good_spending_nobles_cloth', id(markets[0]))] *= 2
        rt.run('sol_refresh_country_substitution', country)
        self.assertNotIn(('sol_country_market_spending_owner', id(markets[0])), rt.maps)
        rt.spending_reads = 0
        rt.run('sol_compute_substitute_unit_spending', location)
        self.assert_spending(rows, rt, location)
        self.assertNotEqual(before, location.variables['sol_unit_spending_nobles'])
        self.assertEqual(rt.spending_reads, 246)
        rt.run('sol_clear_country_substitution', country)
        self.assertFalse(any(name.startswith('sol_country_market_spending_') and target == id(markets[0]) for name, target in rt.maps))

    def test_world_market_refresh_invalidates_after_price_or_supply_change(self):
        from gen_market_unit_consumption import _generate_refresh_block
        rows, rt, country, markets = self.fixture()
        location, market = country.locations[0], markets[0]
        country.variables['sol_good_effective_cloth'] = .4
        rt.run('sol_compute_substitute_unit_spending', location)
        # Execute the actual generated refresh prefix, before its price/supply
        # calculations. The fixture supplies their resulting raw spending map.
        refresh = parse(_generate_refresh_block(rows))[0]
        world_loop = next(node for node in refresh.value if node.key == 'every_market_in_world')
        prefix = world_loop.value[:next(index for index, node in enumerate(world_loop.value)
                                        if node.key == 'set_local_variable')]
        spending_key = ('sol_market_good_spending_nobles_cloth', id(market))
        for change, new_cost in (('price', rt.maps[spending_key] / 2), ('supply', 0.)):
            with self.subTest(change=change):
                before = location.variables['sol_unit_spending_nobles']
                rt.execute(prefix, market)
                self.assertNotIn(('sol_country_market_spending_owner', id(market)), rt.maps)
                rt.maps[spending_key] = new_cost
                rt.spending_reads = 0
                rt.run('sol_compute_substitute_unit_spending', location)
                self.assert_spending(rows, rt, location)
                self.assertNotEqual(before, location.variables['sol_unit_spending_nobles'])
                self.assertEqual(rt.spending_reads, 246)
                # Reuse resumes after rebuilding; no country refresh is needed.
                rt.run('sol_compute_substitute_unit_spending', location)
                self.assertEqual(rt.spending_reads, 246)

    def test_missing_market_or_owner_resets_all_location_totals(self):
        _, rt, country, _ = self.fixture()
        location = country.locations[0]
        rt.run('sol_compute_substitute_unit_spending', location)
        reads = rt.spending_reads
        market = location.market
        for missing in ('market', 'owner'):
            location.market, location.owner = market, country
            setattr(location, missing, None)
            rt.run('sol_compute_substitute_unit_spending', location)
            self.assertEqual([location.variables['sol_unit_spending_' + pop] for pop in POPS], [0.] * len(POPS))
            self.assertEqual(rt.spending_reads, reads)

    def test_absent_map_and_absent_market_key_contribute_zero(self):
        rows, rt, country, markets = self.fixture()
        for key in list(rt.maps):
            if key[0].startswith('sol_market_good_spending_'):
                rt.maps.pop(key)
        # A map can exist globally without an entry for this market.
        rt.maps[('sol_market_good_spending_nobles_cloth', id(Scope('market')))] = 999
        location = country.locations[0]
        rt.run('sol_compute_substitute_unit_spending', location)
        self.assert_spending(rows, rt, location)
        self.assertEqual(rt.spending_reads, 0)

    def test_pp_zero_lumber_and_neutral_extra_good(self):
        from gen_sol_pp_compat import _compat_good_rows
        rows, rt, country, markets = self.fixture(_compat_good_rows(), locations=3, removed_goods={'lumber'})
        country.variables.update(sol_good_effective_cloth=.25, sol_good_effective_victuals=20)
        rt.maps[('sol_market_good_spending_nobles_lumber', id(markets[0]))] = 999
        for location in country.locations:
            rt.run('sol_compute_substitute_unit_spending', location)
            self.assert_spending(rows, rt, location)
        pairs = sum(round(q[pop], 5) > 0 for _, _, q in rows for pop in POPS)
        self.assertEqual(rt.spending_reads, pairs)

    def test_jtg_extra_quantities_and_mnt_calibrated_quantities(self):
        from gen_sol_jtg_compat import _combined_good_rows, _load_rows
        base = _load_good_rows()
        values_file = ROOT / 'src/sol_mnt_compatibility_submod/in_game/common/script_values/zz_SOL_MnT_market_unit_consumption_values.txt'
        values = {node.key.removeprefix('REPLACE:'): float(node.value[0].value)
                  for node in parse(values_file.read_text(encoding='utf-8-sig'))
                  if node.key.removeprefix('REPLACE:').startswith('sol_unit_consumption_')}
        mnt = [(good, price, {pop: values.get(f'sol_unit_consumption_{pop}_{good}', 0.) for pop in POPS})
               for good, price, _ in base]
        for label, compatible in (('JTG', _combined_good_rows(_load_rows())), ('M&T', mnt)):
            with self.subTest(target=label):
                rows, rt, country, _ = self.fixture(compatible, locations=8)
                country.variables.update({'sol_good_effective_' + good: .4 for good in CORE})
                for location in country.locations:
                    rt.run('sol_compute_substitute_unit_spending', location)
                    self.assert_spending(rows, rt, location)
                pairs = sum(round(q[pop], 5) > 0 for _, _, q in rows for pop in POPS)
                self.assertEqual(rt.spending_reads, pairs)


if __name__ == '__main__':
    unittest.main()
