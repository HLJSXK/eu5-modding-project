"""Execute generated substitution effects against an offline EU5 scope fixture."""
import math
import re
import sys
import unittest
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'ai_gui_assessment/renderer'))
from pdx import parse
from gen_market_unit_consumption import _load_good_rows
from sol_substitution import CORE, GROUPS, CONFIG, POPS, price_weight, response, aggregate, render_country_runtime, render_location_spending, render_modifiers, render_values, market_details
from gen_whole_group_baskets import validate_baskets, read_quantities, load_subscriptions, round_component


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
    def __init__(self, rows, enabled=True, *, removed_goods=()):
        self.effects = {n.key: n.value for n in parse(render_country_runtime(rows, removed_goods=removed_goods) + render_location_spending(rows))}
        self.quantities = {f'sol_unit_consumption_{pop}_{good}': round(q[pop], 5)
                           for good, _, q in rows for pop in POPS}
        self.prices = {good: price for good, price, _ in rows}
        self.maps = {}
        self.saved = {}
        self.enabled = enabled
        self.script_values = {n.key: n.value for n in parse(render_values())}
        self.auto_modifiers = {n.key: n.value for n in parse(render_modifiers())}
        self.operations = Counter()
        self.local_context = {}

    def auto_strength(self, good, scope):
        fields = {n.key: n.value for n in self.auto_modifiers.get('sol_substitute_' + good, [])}
        if not fields or not self.condition(fields['potential_trigger'], scope):
            return 0.
        return self.value(fields['scales_with'], scope) * self.value(fields['global_' + good + '_pop_demand'], scope)

    def value(self, node, scope, initial=0.):
        if isinstance(node, list):
            value = initial
            for op in node:
                if op.key == 'if':
                    limits = next((n.value for n in op.value if n.key == 'limit'), [])
                    if self.condition(limits, scope):
                        value = self.value([n for n in op.value if n.key != 'limit'], scope, value)
                    continue
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
        if node.startswith('local_var:'): return self.local_context[node[10:]]
        if node.startswith('var:'): return scope.variables[node[4:]]
        if node.startswith('num_pop_type:'): return scope.pops.get(node[13:], 0.)
        if node.startswith('modifier:global_'):
            good = node[len('modifier:global_'):-len('_pop_demand')]
            return scope.external.get(good, 0.) + scope.modifiers.get('sol_substitute_' + good, 0.) + self.auto_strength(good, scope)
        if node.startswith('country_modifier_strength('):
            return scope.modifiers[node[len('country_modifier_strength('):-1]]
        if node.startswith('global_variable_map('):
            name, key = node[len('global_variable_map('):-1].split('|')
            return self.maps[(name, id(self.value(key, scope)))]
        if node.startswith('default_price(goods:'): return self.prices[node[len('default_price(goods:'):-1]]
        if node == 'num_locations': return len(scope.locations)
        if node == 'current_year': return 1337
        if node == 'market': return scope.market
        if node == 'owner': return scope.owner
        if node in self.quantities: return self.quantities[node]
        if node in self.script_values: return self.value(self.script_values[node], scope)
        return float(node)

    def condition(self, nodes, scope):
        return all(self.test(n, scope) for n in nodes)

    def test(self, node, scope):
        key, val = node.key, node.value
        if key == 'OR': return any(self.test(n, scope) for n in val)
        if key == 'AND': return self.condition(val, scope)
        if key == 'NOT': return not self.condition(val, scope)
        if key == 'has_variable': return val in scope.variables
        if key == 'has_local_variable': return val in self.local_context
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
        # Jomini local_var is a global event-target link in the script context,
        # and remains visible after scope switches (vanilla transfer_pop).
        scope.local = self.local_context
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
            self.operations[key] += 1
            if key in ('set_variable', 'set_local_variable', 'save_scope_value_as'):
                fields = {n.key: n.value for n in val}
                target = self.saved if key == 'save_scope_value_as' else self.local_context if key == 'set_local_variable' else scope.variables
                target[fields['name']] = self.value(fields['value'], scope)
            elif key in ('change_variable', 'change_local_variable'):
                name = next(n.value for n in val if n.key == 'name')
                target = self.local_context if key == 'change_local_variable' else scope.variables
                ops = [n for n in val if n.key != 'name']
                result = target[name]
                for op in ops:
                    rhs = self.value(op.value, scope)
                    if op.key == 'add': result += rhs
                    elif op.key == 'subtract': result -= rhs
                    elif op.key == 'multiply': result *= rhs
                    elif op.key == 'min' and key == 'change_local_variable':
                        # Runtime save evidence: local effect min=0 turns a
                        # positive external baseline into zero. Do not reuse
                        # value-block min's lower-bound semantics here.
                        result = min(result, rhs)
                    else: raise AssertionError(op.key)
                target[name] = result
            elif key in ('remove_variable', 'remove_local_variable'):
                (self.local_context if key == 'remove_local_variable' else scope.variables).pop(val, None)
            elif key == 'remove_country_modifier': scope.modifiers.pop(val, None)
            elif key == 'add_country_modifier':
                fields = {n.key: n.value for n in val}
                # Match the current 1.4 source schema; the engine rejects name=.
                scope.modifiers[fields['modifier']] = self.value(fields['size'], scope)
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
            elif key == 'every_market_present_in_country':
                limits = next((n.value for n in val if n.key == 'limit'), [])
                markets = dict.fromkeys(loc.market for loc in scope.locations if loc.market is not None)
                for market in markets:
                    if self.condition(limits, market): self.execute(val, market)
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
        for good in CORE:
            self.assertEqual(country.variables['sol_sub_multiplier_' + good], 1)
            self.assertNotIn('sol_sub_size_' + good, country.variables)
            potential = next(n.value for n in rt.auto_modifiers['sol_substitute_' + good]
                             if n.key == 'potential_trigger')
            self.assertFalse(rt.condition(potential, country))
            self.assertEqual(rt.auto_strength(good, country), 0)
            self.assertEqual(country.variables['sol_good_effective_' + good], 1)
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
        expected = response(weights, active, pop='nobles')
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
        self.assertAlmostEqual(rt.auto_strength('cloth', country), size)
        rt.run('sol_refresh_country_substitution', country)
        self.assertAlmostEqual(rt.auto_strength('cloth', country), size)
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
            rt.local_context.update(sol_market_actual_price_cloth=ratio * rt.prices['cloth'], sol_market_effective_price_cloth=min(ratio, 1) * rt.prices['cloth'], sol_market_consumes_cloth_count=1)
            rt.run('tier', loc.market)
            self.assertEqual(rt.maps[('sol_market_substitute_weight_cloth', id(loc.market))], price_weight(ratio))
        rt.local_context['sol_market_consumes_cloth_count'] = 0
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

    def test_periodic_refresh_rebuilds_market_population_and_external_inputs(self):
        rt, country, loc = self.fixture({'cloth': .5, 'leather': 1})
        rt.run('sol_refresh_country_substitution', country)
        before = rt.auto_strength('cloth', country)
        loc.market = rt.market({'cloth': 2, 'leather': 1})
        loc.pops = {'burghers': 20}
        country.external['cloth'] = -.75
        rt.run('sol_refresh_country_substitution', country)
        self.assertNotAlmostEqual(rt.auto_strength('cloth', country), before)
        self.assertAlmostEqual(country.variables['sol_sub_external_cloth'], .25)
        self.assertAlmostEqual(country.variables['sol_good_effective_cloth'],
                               .25 + rt.auto_strength('cloth', country))
        rt.run('sol_clear_country_substitution', country)
        self.assertFalse(country.variables)
        self.assertEqual(rt.auto_strength('cloth', country), 0)

    def test_missing_supply_and_pp_frozen_goods(self):
        rt, country, loc = self.fixture({'cloth': .5, 'leather': 1})
        rt.maps[('sol_market_consumes_leather', id(loc.market))] = 0
        rt.run('sol_refresh_country_substitution', country)
        self.assertEqual(country.variables['sol_sub_multiplier_cloth'], 1)
        from gen_sol_pp_compat import _compat_good_rows
        pp = Runtime(_compat_good_rows(), removed_goods={'lumber'})
        pp.maps[('sol_market_good_spending_nobles_victuals', id(loc.market))] = 3
        pp.maps[('sol_market_good_spending_nobles_lumber', id(loc.market))] = 999
        pp.run('sol_compute_substitute_unit_spending', loc)
        self.assertEqual(loc.variables['sol_unit_spending_nobles'], 3)

    def test_commoner_condiments_substitute_with_no_sugar(self):
        for pops in ({'peasants': 100}, {'laborers': 100}, {'soldiers': 100},
                     {'nobles': 1, 'laborers': 30, 'peasants': 60, 'soldiers': 9}):
            with self.subTest(pops=pops):
                rt, country, loc = self.fixture({'olives': 2, 'salt': 1, 'sugar': 1})
                loc.pops = pops
                rt.maps['sol_market_consumes_sugar', id(loc.market)] = 0
                rt.run('sol_refresh_country_substitution', country)
                self.assertAlmostEqual(country.variables['sol_sub_multiplier_olives'], 4 / 3)
                self.assertAlmostEqual(country.variables['sol_sub_multiplier_salt'], 2 / 3)
                self.assertAlmostEqual(country.variables['sol_sub_multiplier_sugar'], 1)

    def test_unsubscribed_groups_do_not_change_overlap_response(self):
        rt, country, loc = self.fixture(dict.fromkeys(CORE, 1) | {'wine': 2})
        loc.pops = {'laborers': 100}
        rt.run('sol_refresh_country_substitution', country)
        # Laborers' wine belongs only to intoxicants; supplied luxury drinks
        # must not dilute it. Mercury belongs only to medicine for laborers.
        self.assertAlmostEqual(country.variables['sol_sub_multiplier_wine'], 1.6)
        runtime = render_country_runtime(self.rows)
        laborers = runtime.split('if = { limit = { local_var:sol_sub_population_laborers > 0 }', 1)[1].split(
            'if = { limit = { local_var:sol_sub_population_peasants > 0 }', 1)[0]
        for good in ('tea', 'coffee', 'cocoa', 'fine_cloth', 'incense'):
            self.assertNotIn('sol_sub_neutral_' + good, laborers)
        self.assertEqual(laborers.count('name = sol_sub_neutral_mercury add ='), 1)

    def test_whole_group_invariants_for_generated_targets(self):
        target, _ = read_quantities(ROOT / 'data/target_demand.csv')
        table, _ = read_quantities(ROOT / 'data/demand_price_table.csv')
        validate_baskets(target)
        self.assertEqual(target, table)
        for name in ('stable', 'sol_standalone', 'sol_pp_compatibility_submod', 'sol_mnt_compatibility_submod'):
            if name == 'sol_pp_compatibility_submod':
                from gen_sol_pp_compat import _compat_good_rows
                validate_baskets({good: q for good, _, q in _compat_good_rows()}, removed_goods={'lumber'}, label=name)
                pp_runtime = render_country_runtime(_compat_good_rows(), removed_goods={'lumber'})
                self.assertNotIn('name = sol_sub_neutral_lumber', pp_runtime)
                self.assertNotIn('multiply = sol_unit_consumption_peasants_lumber', pp_runtime)
                continue
            values = next((ROOT / 'src' / name / 'in_game/common/script_values').glob('*market_unit_consumption_values.txt'))
            # Zero-consumption constants are intentionally omitted by codegen.
            q = {good: dict.fromkeys(POPS, 0.) for good in CORE}
            for node in parse(values.read_text(encoding='utf-8-sig')):
                key = node.key.removeprefix('REPLACE:')
                for pop in POPS:
                    prefix = f'sol_unit_consumption_{pop}_'
                    if key.startswith(prefix) and key[len(prefix):] in q:
                        q[key[len(prefix):]][pop] = float(next(n.value for n in node.value if n.key == 'value'))
            validate_baskets(q, removed_goods={'lumber'} if name == 'sol_pp_compatibility_submod' else (), label=name)

    def test_generator_rejects_partial_and_unsubscribed_demand(self):
        q = {good: dict(values) for good, _, values in self.rows}
        q['salt']['peasants'] = 0
        with self.assertRaisesRegex(ValueError, 'salt/peasants'):
            render_country_runtime([(good, price, q[good]) for good, price, _ in self.rows])
        q['salt']['peasants'] = .00002
        q['incense']['peasants'] = .00001
        with self.assertRaisesRegex(ValueError, 'outside subscribed groups'):
            validate_baskets(q)
        q['incense']['peasants'] = 0
        q['lumber']['peasants'] = 0
        with self.assertRaisesRegex(ValueError, 'lumber/peasants'):
            validate_baskets(q)
        q['lumber'] = dict.fromkeys(POPS, 0)
        validate_baskets(q, removed_goods={'lumber'})

    def test_subscription_table_rejects_invalid_cells(self):
        source = (ROOT / 'data/pop_group_baskets.csv').read_text(encoding='utf-8')
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'baskets.csv'
            for invalid in (source.replace('basic_clothing,1', 'basic_clothing,2'),
                            source + source.splitlines()[1] + '\n',
                            '\n'.join(source.splitlines()[:-1]) + '\n'):
                path.write_text(invalid, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_subscriptions(path)

    def test_mnt_tiny_members_survive_price_scaling(self):
        from gen_sol_mnt_compat import _compat_quantities, _load_sol_targets, _validate_demand_invariants, Block
        targets = _load_sol_targets()
        prices = {good: Decimal(1) for good in targets}
        blocks = {good: Block(good, 'default_market_price = 1000000', '', Path('fixture')) for good in targets}
        blocks['tools'] = Block('tools', 'default_market_price = 0.5', '', Path('fixture'))
        q = _compat_quantities(targets, prices, blocks)
        _validate_demand_invariants(targets, q, prices, blocks)
        validate_baskets(q)
        self.assertEqual(q['salt']['peasants'], Decimal('.00001'))
        self.assertEqual(q['tools']['laborers'], Decimal('.0005'))

    def test_migration_rounding_preserves_small_budget_and_net_lattice(self):
        ideal = {'sugar': Decimal('.00025') / 9, 'salt': Decimal('.00025') / 12,
                 'olives': Decimal('.00025') / 3}
        prices = {'sugar': Decimal(3), 'salt': Decimal(4), 'olives': Decimal(1)}
        q, error = round_component(ideal, prices, Decimal('.00025'), dict.fromkeys(ideal, Decimal(0)))
        self.assertEqual(error, 0)
        self.assertEqual(q, {'sugar': Decimal('.00003'), 'salt': Decimal('.00002'), 'olives': Decimal('.00008')})
        q, _ = round_component({'masonry': Decimal('.00001')}, {'masonry': Decimal(1)},
                               Decimal('.00001'), {'masonry': Decimal('.000015')})
        self.assertEqual(q['masonry'], Decimal('.000015'))

    def test_contextual_goods_tooltips(self):
        from sol_goods_ui import render_goods_vbox
        location = render_goods_vbox(['cloth'], 'sol_market_consumes', 'Location.GetMarket.MakeScope', '')
        country = render_goods_vbox(['cloth'], 'gls_country_consumes', 'Player.MakeScope', '')
        self.assertIn("Location.GetOwner.MakeScope.ScriptValue('sol_substitute_cloth_display')", location)
        self.assertIn('sol_market_substitute_weight_cloth', location)
        self.assertIn("Player.MakeScope.ScriptValue('sol_substitute_cloth_display')", country)
        self.assertNotIn('sol_market_substitute_weight', country)
        self.assertNotIn('blockoverride \"sol_good_tooltip\"', location)

    def test_substitution_display_lifecycle(self):
        rt, country, loc = self.fixture({'cloth': .5, 'leather': 1})
        self.assertEqual(rt.value('sol_substitute_status_display', country), 1)
        self.assertEqual(rt.value('sol_substitute_cloth_display', country), 1)
        rt.run('sol_refresh_country_substitution', country)
        self.assertEqual(rt.value('sol_substitute_status_display', country), 2)
        self.assertEqual(rt.value('sol_substitute_cloth_display', country), country.variables['sol_sub_multiplier_cloth'])
        rt.enabled = False
        rt.run('sol_refresh_country_substitution', country)
        self.assertEqual(rt.value('sol_substitute_status_display', country), 0)
        self.assertEqual(rt.value('sol_substitute_cloth_display', country), 1)
        rt.enabled = True
        self.assertEqual(rt.value('sol_substitute_status_display', country), 1)

    def test_algorithm_a_90_10(self):
        d = response({'a': .5, 'b': 1}, {'a', 'b'}, {'g': ['a', 'b']}, {'g': 2})
        self.assertAlmostEqual(90*d['a'], 60)
        self.assertAlmostEqual(10*d['b'], 40/3)

    def test_interface_coverage_and_packaging(self):
        types = (ROOT / '.eu5-base/reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt').read_text(encoding='utf-8-sig')
        for good in CORE: self.assertRegex(types, rf'(?m)^global_{good}_pop_demand\s*=')
        self.assertEqual(len(GROUPS), 20)
        self.assertEqual(sum(len(m) for m in GROUPS.values()), 67)
        for target in ('stable', 'sol_standalone'):
            path = ROOT / 'src' / target / 'in_game/common/scripted_effects/C_SOL_substitution.txt'
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            source = path.read_text(encoding='utf-8-sig')
            effects = {n.key for n in parse(source)}
            self.assertIn('sol_compute_substitute_unit_spending', effects)
            self.assertIn('sol_clear_country_substitution', effects)
            for obsolete in ('add_country_modifier', 'remove_country_modifier',
                             'country_modifier_strength', 'sol_apply_country_substitution',
                             'sol_check_substitution_snapshot'):
                self.assertNotIn(obsolete, source)
            self.assertFalse((ROOT / 'src' / target / 'main_menu/common/static_modifiers/SOL_substitute_global_modifiers.txt').exists())
            auto_path = ROOT / 'src' / target / 'in_game/common/auto_modifiers/SOL_substitute_global_modifiers.txt'
            self.assertEqual(auto_path.read_text(encoding='utf-8-sig'), render_modifiers())
            self.assertEqual(len(parse(render_modifiers())), len(CORE))
            for language in ('english', 'simp_chinese'):
                loc_path = ROOT / 'src' / target / 'main_menu/localization' / language / f'SOL_substitution_modifiers_l_{language}.yml'
                self.assertTrue(loc_path.read_bytes().startswith(b'\xef\xbb\xbf'))
                localization = loc_path.read_text(encoding='utf-8-sig')
                keys = re.findall(r'^ ([A-Za-z0-9_]+):', localization, re.MULTILINE)
                expected = {f'AUTO_MODIFIER_{kind}_sol_substitute_{good}'
                            for kind in ('NAME', 'DESC') for good in CORE}
                self.assertEqual(set(keys), expected)
                self.assertEqual(len(keys), len(expected))
                for line in localization.splitlines()[1:]:
                    self.assertRegex(line, r'^ [A-Za-z0-9_]+: "[^"\r\n]+"$')
        pp = (ROOT / 'src/sol_pp_compatibility_submod/in_game/common/scripted_effects/zz_A_SOL_economy_effects.txt').read_text(encoding='utf-8-sig')
        refresh = next(n for n in parse(pp) if n.key == 'REPLACE:sol_refresh_country_substitution')
        body = repr(refresh.value)
        self.assertNotIn('sol_sub_neutral_lumber', body)
        self.assertNotIn('sol_sub_multiplier_victuals', pp)
        # Compatibility targets can embed a complete generated country runtime.
        # Reject stale copies even when the base targets already use auto caches.
        for path in (ROOT / 'src').glob('*/in_game/common/scripted_effects/*.txt'):
            source = path.read_text(encoding='utf-8-sig')
            self.assertNotRegex(source, r'(?:add|remove)_country_modifier[^\n]*\bsol_substitute_', str(path))
            self.assertNotIn('sol_apply_country_substitution', source, str(path))
            self.assertNotIn('sol_check_substitution_snapshot', source, str(path))


if __name__ == '__main__':
    unittest.main()
