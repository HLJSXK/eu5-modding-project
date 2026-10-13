"""Execute generated substitution effects against an offline EU5 scope fixture."""
import math
import re
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'ai_gui_assessment/renderer'))
from pdx import parse
from gen_market_unit_consumption import _load_good_rows
from sol_substitution import CORE, GROUPS, CONFIG, POPS, price_weight, response, aggregate, render_country_runtime, render_location_spending, market_details


@dataclass(eq=False)
class Scope:
    kind: str
    variables: dict = field(default_factory=dict)
    local: dict = field(default_factory=dict)
    modifiers: dict = field(default_factory=dict)
    external: dict = field(default_factory=dict)
    pops: dict = field(default_factory=dict)
    locations: list = field(default_factory=list)
    market: object = None
    owner: object = None
    human: bool = True


class Runtime:
    def __init__(self, rows, enabled=True):
        self.effects = {n.key: n.value for n in parse(render_country_runtime(rows) + render_location_spending(rows))}
        self.quantities = {f'sol_unit_consumption_{pop}_{good}': round(q[pop], 5)
                           for good, _, q in rows for pop in POPS}
        self.prices = {good: price for good, price, _ in rows}
        self.maps = {}
        self.saved = {}
        self.enabled = enabled

    def value(self, node, scope):
        if isinstance(node, list):
            value = 0.
            for op in node:
                rhs = self.value(op.value, scope)
                if op.key == 'value': value = rhs
                elif op.key == 'add': value += rhs
                elif op.key == 'subtract': value -= rhs
                elif op.key == 'multiply': value *= rhs
                elif op.key == 'divide': value /= rhs
                elif op.key == 'min': value = max(value, rhs)
                elif op.key == 'max': value = min(value, rhs)
                else: raise AssertionError(op.key)
            return value
        if node.startswith('scope:'):
            name, sep, tail = node[6:].partition('.')
            value = self.saved[name]
            return self.value(tail, value) if sep else value
        if node.startswith('local_var:'): return scope.local[node[10:]]
        if node.startswith('var:'): return scope.variables[node[4:]]
        if node.startswith('num_pop_type:'): return scope.pops.get(node[13:], 0.)
        if node.startswith('modifier:global_'):
            good = node[len('modifier:global_'):-len('_pop_demand')]
            return scope.external.get(good, 0.) + scope.modifiers.get('sol_substitute_' + good, 0.)
        if node.startswith('global_variable_map('):
            name, key = node[len('global_variable_map('):-1].split('|')
            return self.maps[(name, id(self.value(key, scope)))]
        if node.startswith('default_price(goods:'): return self.prices[node[len('default_price(goods:'):-1]]
        if node == 'num_locations': return len(scope.locations)
        if node == 'current_year': return 1337
        if node == 'market': return scope.market
        if node == 'owner': return scope.owner
        if node in self.quantities: return self.quantities[node]
        return float(node)

    def condition(self, nodes, scope):
        return all(self.test(n, scope) for n in nodes)

    def test(self, node, scope):
        key, val = node.key, node.value
        if key == 'OR': return any(self.test(n, scope) for n in val)
        if key == 'AND': return self.condition(val, scope)
        if key == 'NOT': return not self.condition(val, scope)
        if key == 'has_variable': return val in scope.variables
        if key == 'has_country_modifier': return val in scope.modifiers
        if key == 'has_global_variable': return True
        if key == 'has_global_variable_map': return any(k[0] == val for k in self.maps)
        if key == 'is_key_in_global_variable_map':
            fields = {n.key: n.value for n in val}
            return (fields['name'], id(self.value(fields['target'], scope))) in self.maps
        if key == 'sol_substitution_is_on': return self.enabled == (val == 'yes')
        if key == 'is_land': return scope.kind == 'location'
        if key == 'is_human': return scope.human == (val == 'yes')
        if key == 'is_ai': return scope.human == (val == 'no')
        if key == 'exists':
            try: return self.value(val, scope) is not None
            except KeyError: return False
        if key.startswith('scope:') and isinstance(val, list): return self.condition(val, self.value(key, scope))
        a, b = self.value(key, scope), self.value(val, scope)
        return {'=': lambda: a == b, '>': lambda: a > b, '<': lambda: a < b, '>=': lambda: a >= b, '<=': lambda: a <= b}[node.op]()

    def run(self, effect, scope):
        self.execute(self.effects[effect], scope)

    def execute(self, nodes, scope):
        taken = False
        for node in nodes:
            key, val = node.key, node.value
            if key == 'limit': continue
            if key in ('if', 'else_if', 'else'):
                if key != 'if' and taken:
                    continue
                limits = next((n.value for n in val if n.key == 'limit'), [])
                allowed = self.condition(limits, scope) if key != 'else' else True
                if key == 'if': taken = False
                if allowed and not taken:
                    self.execute([n for n in val if n.key != 'limit'], scope)
                    taken = True
                continue
            taken = False
            if key in ('set_variable', 'set_local_variable', 'save_scope_value_as'):
                fields = {n.key: n.value for n in val}
                target = self.saved if key == 'save_scope_value_as' else scope.local if key == 'set_local_variable' else scope.variables
                target[fields['name']] = self.value(fields['value'], scope)
            elif key in ('change_variable', 'change_local_variable'):
                name = next(n.value for n in val if n.key == 'name')
                target = scope.local if key == 'change_local_variable' else scope.variables
                ops = [n for n in val if n.key != 'name']
                result = target[name]
                for op in ops:
                    rhs = self.value(op.value, scope)
                    if op.key == 'add': result += rhs
                    elif op.key == 'subtract': result -= rhs
                    elif op.key == 'multiply': result *= rhs
                    elif op.key == 'min': result = max(result, rhs)
                    else: raise AssertionError(op.key)
                target[name] = result
            elif key in ('remove_variable', 'remove_local_variable'):
                (scope.local if key == 'remove_local_variable' else scope.variables).pop(val, None)
            elif key == 'remove_country_modifier': scope.modifiers.pop(val, None)
            elif key == 'add_country_modifier':
                fields = {n.key: n.value for n in val}
                scope.modifiers[fields['name']] = self.value(fields['size'], scope)
            elif key == 'save_scope_as': self.saved[val] = scope
            elif key in ('remove_from_global_variable_map', 'add_to_global_variable_map'):
                fields = {n.key: n.value for n in val}
                index = (fields['name'], id(self.value(fields['key'], scope)))
                if key.startswith('remove'): self.maps.pop(index, None)
                else: self.maps[index] = self.value(fields['value'], scope)
            elif key == 'every_owned_location':
                limits = next((n.value for n in val if n.key == 'limit'), [])
                for loc in scope.locations:
                    if self.condition(limits, loc): self.execute(val, loc)
            elif key == 'market': self.execute(val, scope.market)
            elif key == 'owner':
                if scope.owner is not None: self.execute(val, scope.owner)
            elif key.startswith('scope:'): self.execute(val, self.value(key, scope))
            elif key in self.effects: self.run(key, scope)
            else: raise AssertionError(key)

    def market(self, weights, supplied=None):
        market = Scope('market')
        self.maps[('sol_market_substitute_cache', id(market))] = 1
        supplied = set(weights) if supplied is None else supplied
        for good, weight in weights.items():
            self.maps[(f'sol_market_substitute_weight_{good}', id(market))] = weight
            self.maps[(f'sol_market_consumes_{good}', id(market))] = int(good in supplied)
        return market


class SubstitutionTests(unittest.TestCase):
    def setUp(self):
        self.rows = _load_good_rows()

    def fixture(self, weights, external=None, enabled=True):
        rt = Runtime(self.rows, enabled)
        country = Scope('country', external=external or {})
        market = rt.market(weights)
        location = Scope('location', market=market, owner=country, pops={'nobles': 90})
        country.locations = [location]
        return rt, country, location

    def test_strict_boundaries(self):
        for boundary, expected, below, above in ((2.3,.5,.5,.25),(1.7,.75,.75,.5),(1.3,1,1,.75),(.85,1,1.25,1),(.65,1.25,1.5,1.25),(.4,1.5,2,1.5)):
            self.assertEqual(price_weight(boundary), expected)
            self.assertEqual(price_weight(boundary-.00001), below)
            self.assertEqual(price_weight(boundary+.00001), above)

    def test_generated_neutral_overlap_and_cleanup(self):
        rt, country, loc = self.fixture(dict.fromkeys(CORE, 1))
        rt.run('sol_refresh_country_substitution', country)
        self.assertFalse(country.modifiers)
        for good in CORE: self.assertEqual(country.variables['sol_sub_multiplier_' + good], 1)
        self.assertFalse(country.local)
        self.assertFalse(loc.local)
        rt.run('sol_clear_country_substitution', country)
        self.assertFalse(country.variables)

    def test_generated_overlap_matches_independent_response(self):
        weights = dict.fromkeys(CORE, 1)
        weights.update(cloth=.5, lumber=.25, wine=2, fish=1.5)
        rt, country, loc = self.fixture(weights)
        rt.run('sol_refresh_country_substitution', country)
        q = {g: row for g, _, row in self.rows}
        active = {g for g in CORE if q[g]['nobles'] > 0}
        expected = response(weights, active)
        for good in CORE: self.assertAlmostEqual(country.variables['sol_sub_multiplier_' + good], expected[good])

    def test_generated_two_markets_and_no_self_accumulation(self):
        rt, country, loc = self.fixture({'cloth': .5, 'leather': 1}, {'cloth': -.75})
        loc2 = Scope('location', market=rt.market({'cloth': 2, 'leather': 1}), owner=country, pops={'nobles': 30})
        country.locations.append(loc2)
        rt.run('sol_refresh_country_substitution', country)
        # Cloth overlaps basic_clothing and standard_clothing; the lone cloth
        # in the latter contributes 2 to both current and neutral sums.
        expected = (90 * 8/9 + 30 * 10/9) / 120
        self.assertAlmostEqual(country.variables['sol_sub_multiplier_cloth'], expected)
        size = .25 * (expected - 1)
        self.assertAlmostEqual(country.modifiers['sol_substitute_cloth'], size)
        rt.run('sol_refresh_country_substitution', country)
        self.assertAlmostEqual(country.modifiers['sol_substitute_cloth'], size)
        rt.enabled = False
        rt.run('sol_refresh_country_substitution', country)
        self.assertFalse(country.modifiers)
        self.assertFalse(any(k.startswith('sol_sub_') or k.startswith('sol_substitute_') for k in country.variables))
        self.assertEqual(country.variables['sol_good_effective_cloth'], .25)

    def test_no_supply_single_member_zero_external_and_empty_country(self):
        rt, country, loc = self.fixture({'cloth': .5}, {'cloth': -1.5})
        rt.run('sol_refresh_country_substitution', country)
        self.assertFalse(country.modifiers)
        self.assertEqual(country.variables['sol_good_effective_cloth'], 0)
        country.external.clear()
        rt.run('sol_refresh_country_substitution', country)
        self.assertFalse(country.modifiers)
        country.locations.clear()
        rt.run('sol_refresh_country_substitution', country)
        self.assertFalse(country.modifiers)

    def test_small_positive_baseline_and_reference_price_aggregation(self):
        self.assertEqual(aggregate([{'a': .00001}], [{'a': 1}])['a'], 1)
        self.assertEqual(aggregate([{'a': 1}, {'a': 1}], [{'a': .5}, {'a': 1.5}])['a'], 1)
        self.assertEqual(aggregate([{'a': 0}], [{'a': 2}])['a'], 1)

    def test_generated_tier_boundaries_and_map_overwrite(self):
        rt, country, loc = self.fixture({'cloth': 1})
        rt.effects['tier'] = parse('\n'.join(market_details('cloth', ['nobles'])))
        rt.saved['sol_market_cache'] = loc.market
        for ratio in (2.3, 1.7, 1.3, .85, .65, .4, 2.30001, 1.70001, 1.30001, .84999, .64999, .39999):
            loc.market.local.update(sol_market_actual_price_cloth=ratio * rt.prices['cloth'], sol_market_effective_price_cloth=min(ratio, 1) * rt.prices['cloth'], sol_market_consumes_cloth_count=1)
            rt.run('tier', loc.market)
            self.assertEqual(rt.maps[('sol_market_substitute_weight_cloth', id(loc.market))], price_weight(ratio))
        loc.market.local['sol_market_consumes_cloth_count'] = 0
        rt.run('tier', loc.market)
        self.assertEqual(rt.maps[('sol_market_good_spending_nobles_cloth', id(loc.market))], 0)

    def test_generated_location_effective_factor_once_and_shared_market(self):
        rt, country, loc = self.fixture({'cloth': .5, 'leather': 1}, {'cloth': -.75})
        other = Scope('country', external={'cloth': .5}, locations=[])
        otherloc = Scope('location', market=loc.market, owner=other, pops={'nobles': 30})
        other.locations = [otherloc]
        rt.maps[('sol_market_good_spending_nobles_cloth', id(loc.market))] = 10
        rt.maps[('sol_market_good_spending_nobles_leather', id(loc.market))] = 20
        for owner, location in ((country, loc), (other, otherloc)):
            rt.run('sol_refresh_country_substitution', owner)
            rt.run('sol_compute_substitute_unit_spending', location)
            expected = 10 * owner.variables['sol_good_effective_cloth'] + 20 * owner.variables['sol_good_effective_leather']
            self.assertAlmostEqual(location.variables['sol_unit_spending_nobles'], expected)
            self.assertFalse(location.local)
        self.assertNotEqual(loc.variables['sol_unit_spending_nobles'], otherloc.variables['sol_unit_spending_nobles'])
        loc.market = None
        rt.run('sol_compute_substitute_unit_spending', loc)
        self.assertEqual(loc.variables['sol_unit_spending_nobles'], 0)

    def test_generated_snapshot_lifecycle(self):
        rt, country, loc = self.fixture({'cloth': .5, 'leather': 1})
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 0)
        country.external['cloth'] = -.75
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        country.human = False
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        loc.market = rt.market({'cloth': 2, 'leather': 1})
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        loc.market = None
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        replacement = Scope('location', market=rt.market({'cloth': 1}), owner=country, pops={'nobles': 90})
        country.locations = [replacement]
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_refresh_country_substitution', country)
        rt.enabled = False
        rt.run('sol_refresh_country_substitution', country)
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 0)
        country.external['cloth'] = 0
        rt.run('sol_check_substitution_snapshot', country)
        self.assertEqual(country.variables['sol_substitute_dirty'], 1)
        rt.run('sol_clear_country_substitution', country)
        self.assertFalse(country.variables)
        self.assertFalse(replacement.variables)

    def test_missing_supply_and_pp_frozen_goods(self):
        rt, country, loc = self.fixture({'cloth': .5, 'leather': 1})
        rt.maps[('sol_market_consumes_leather', id(loc.market))] = 0
        rt.run('sol_refresh_country_substitution', country)
        self.assertEqual(country.variables['sol_sub_multiplier_cloth'], 1)
        from gen_sol_pp_compat import _compat_good_rows
        pp = Runtime(_compat_good_rows())
        pp.maps[('sol_market_good_spending_nobles_victuals', id(loc.market))] = 3
        pp.maps[('sol_market_good_spending_nobles_lumber', id(loc.market))] = 999
        pp.run('sol_compute_substitute_unit_spending', loc)
        self.assertEqual(loc.variables['sol_unit_spending_nobles'], 3)

    def test_contextual_goods_tooltips(self):
        from sol_goods_ui import render_goods_vbox
        location = render_goods_vbox(['cloth'], 'sol_market_consumes', 'Location.GetMarket.MakeScope', '')
        country = render_goods_vbox(['cloth'], 'gls_country_consumes', 'Player.MakeScope', '')
        self.assertIn("Location.GetOwner.MakeScope.ScriptValue('sol_substitute_cloth_display')", location)
        self.assertIn('sol_market_substitute_weight_cloth', location)
        self.assertIn("Player.MakeScope.ScriptValue('sol_substitute_cloth_display')", country)
        self.assertNotIn('sol_market_substitute_weight', country)
        self.assertNotIn('blockoverride \"sol_good_tooltip\"', location)

    def test_algorithm_a_90_10(self):
        d = response({'a': .5, 'b': 1}, {'a', 'b'}, {'g': ['a', 'b']}, {'g': 2})
        self.assertAlmostEqual(90*d['a'], 60)
        self.assertAlmostEqual(10*d['b'], 40/3)

    def test_interface_coverage_and_packaging(self):
        types = (ROOT / 'reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt').read_text(encoding='utf-8-sig')
        for good in CORE: self.assertRegex(types, rf'(?m)^global_{good}_pop_demand\s*=')
        self.assertEqual(len(GROUPS), 20)
        self.assertEqual(sum(len(m) for m in GROUPS.values()), 67)
        for target in ('stable', 'sol_standalone'):
            path = ROOT / 'src' / target / 'in_game/common/scripted_effects/C_SOL_substitution.txt'
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            effects = {n.key for n in parse(path.read_text(encoding='utf-8-sig'))}
            self.assertIn('sol_compute_substitute_unit_spending', effects)
            self.assertIn('sol_clear_country_substitution', effects)
        pp = (ROOT / 'src/sol_pp_compatibility_submod/in_game/common/scripted_effects/zz_A_SOL_economy_effects.txt').read_text(encoding='utf-8-sig')
        refresh = next(n for n in parse(pp) if n.key == 'REPLACE:sol_refresh_country_substitution')
        body = repr(refresh.value)
        self.assertNotIn('sol_sub_neutral_lumber', body)
        self.assertNotIn('sol_sub_multiplier_victuals', pp)


if __name__ == '__main__':
    unittest.main()
