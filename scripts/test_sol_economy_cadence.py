"""Execute real pulse/apply control flow with the expensive solve boundary stubbed."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gen_market_unit_consumption import _load_good_rows
from test_sol_substitution import Runtime, Scope, parse

ROOT = Path(__file__).resolve().parent.parent
SIZE = 'sol_location_pop_demand_modifier_size'
STATUS = 'sol_country_demand_solve_status'
TARGETS = ('stable', 'sol_standalone')


def block(nodes, key):
    return next(n.value for n in nodes if n.key == key)


def read_nodes(path):
    return parse(path.read_text(encoding='utf-8-sig'))


class CadenceRuntime(Runtime):
    def __init__(self, target, reduced=True, enabled=True):
        super().__init__(_load_good_rows(), enabled=enabled)
        # File-only tracing is disabled in normal builds and does not participate
        # in this economy fixture; its generated bodies are checked in test_sol_oos.
        self.effects['sol_oos_trace_country'] = []
        self.effects['sol_oos_trace_global'] = []
        self.reduced = reduced
        self.master = True
        self.calls = Counter()
        self.native_writes = []
        self.actions = {n.key:n.value for n in read_nodes(
            ROOT/'src'/target/'in_game/common/on_action/SOL_economy_on_actions.txt')}
        economy = {n.key:n.value for n in read_nodes(
            ROOT/'src'/target/'in_game/common/scripted_effects/A_SOL_economy_effects.txt')}
        for name in ('sol_apply_local_pop_demand_modifiers','sol_update_local_pop_demand_modifiers',
                     'sol_apply_location_living_standard_modifiers', 'sol_clear_location_living_standard_modifiers'):
            self.effects[name] = deepcopy(economy[name])
        # Keep the generated size expression and metadata; adapt only the native
        # modifier write, which the shared offline fixture does not implement.
        def adapt(nodes):
            for node in nodes:
                if node.key == 'add_location_modifier':
                    self.native_definition = {n.key:n.value for n in node.value}
                    node.key = 'fixture_native_location_write'
                    node.value = 'yes'
                elif isinstance(node.value,list):
                    adapt(node.value)
        adapt(self.effects['sol_apply_local_pop_demand_modifiers'])
        self.effects['fixture_native_location_write'] = []
        self.effects['sol_update_estate_building_maintenance'] = []
        # The actual numerical solver is covered separately. This boundary stub
        # makes every recomputation visible and supplies a fresh location result.
        self.effects['sol_solve_country_pop_demand'] = parse('''
            set_variable = { name = sol_country_demand_solve_status value = 1 }
            every_owned_location = {
                set_variable = { name = sol_location_pop_demand_modifier_size value = 0.25 }
                set_variable = { name = sol_location_sol value = 12 }
            }
        ''')

    def value(self,node,scope,initial=0.):
        if node == 'current_date' or node == '1337.5.1':
            return 1
        if node == 'total_population':
            return 1 if scope.locations else 0
        return super().value(node,scope,initial)

    def test(self,node,scope):
        if node.key == 'sol_ai_reduced_freq_is_on':
            return self.reduced == (node.value == 'yes')
        if node.key == 'sol_sol_is_on':
            return self.master == (node.value == 'yes')
        return super().test(node,scope)

    def run(self,name,scope):
        self.calls[name] += 1
        if name == 'sol_check_substitution_snapshot':
            raise AssertionError('Monthly cadence must never poll the snapshot')
        if name == 'fixture_native_location_write':
            definition=self.native_definition
            assert definition['months']=='1' and definition['mode']=='replace'
            size=self.value(definition['size'],scope)
            scope.modifiers[definition['modifier']]=size
            self.native_writes.append((scope,size))
            return
        return super().run(name,scope)

    def pulse(self,name,country):
        action=self.actions[name]
        conditions=next((n.value for n in action if n.key=='trigger'),[])
        if self.condition(conditions,country):
            self.execute(block(action,'effect'),country)


def country(human=False,cached=True):
    c=Scope('country',human=human)
    if cached:
        c.variables[STATUS]=1
    c.locations=[Scope('location',owner=c,variables={SIZE:0.6})]
    return c


class LifecycleRuntime(Runtime):
    """Execute real lifecycle dispatch; economic pulse bodies have separate tests."""
    def __init__(self, target):
        self.actions = {}
        folder = ROOT/'src'/target/'in_game/common/on_action'
        for filename in ('SOL_economy_on_actions.txt', 'SOL_migration_on_actions.txt'):
            if (folder/filename).exists():
                for node in read_nodes(folder/filename):
                    self.actions.setdefault(node.key, []).extend(node.value)
        self.migration_marker = None
        if 'sol_migration_stamp_new_game' in self.actions:
            stamp = block(self.actions['sol_migration_stamp_new_game'], 'effect')
            self.migration_marker = next(n.value for n in stamp if n.key == 'set_global_variable')
        self.effects = {'gls_recalculate_global_living_standard': []}
        self.flags = set()
        self.countries = [country(human=True), country(), country(human=True)]
        self.notifications = []
        self.calls = Counter()
        self.operations = Counter()
        self.local_context = {}
        self.master = True

    def test(self, node, scope):
        if node.key == 'has_global_variable':
            return node.value in self.flags
        if node.key == 'sol_sol_is_on':
            return self.master == (node.value == 'yes')
        return super().test(node, scope)

    def dispatch(self, name, scope):
        # These unrelated boundaries are exercised by CadenceTests or their
        # own feature tests, not by this migration/startup fixture.
        if name in {'sol_initialize_cmm_alias_defaults_game_start', 'sol_ae_game_start',
                    'sol_substitution_cleanup_monthly_pulse', 'sol_local_pop_demand_monthly_pulse'}:
            return
        nodes = self.actions.get(name, [])
        conditions = [n for section in nodes if section.key == 'trigger' for n in section.value]
        if not self.condition(conditions, scope):
            return
        for section in nodes:
            if section.key == 'effect':
                self.execute(section.value, scope)
            elif section.key == 'on_actions':
                for child in section.value:
                    self.dispatch(child.key, scope)

    def execute(self, nodes, scope):
        for node in nodes:
            if node.key == 'set_global_variable':
                self.flags.add(node.value if isinstance(node.value, str) else
                               next(n.value for n in node.value if n.key == 'name'))
            elif node.key == 'trigger_event_silently':
                self.dispatch(next(n.value for n in node.value if n.key == 'on_action'), scope)
            elif node.key == 'trigger_event_non_silently':
                # All recipients must observe the global stamp before any event.
                assert self.migration_marker in self.flags
                self.notifications.append((node.value, scope))
            elif node.key == 'every_country':
                conditions = next((n.value for n in node.value if n.key == 'limit'), [])
                for recipient in self.countries:
                    if self.condition(conditions, recipient):
                        self.execute(node.value, recipient)
            else:
                super().execute([node], scope)

    def run(self, name, scope):
        self.calls[name] += 1
        super().run(name, scope)


class CadenceTests(unittest.TestCase):
    def test_feedback_reapplies_ai_cache_monthly_and_refreshes_on_anniversary(self):
        for target in TARGETS:
            rt, c = CadenceRuntime(target), country()
            place = c.locations[0]
            place.variables['sol_location_sol'] = 2
            for _ in range(12):
                rt.pulse('sol_local_pop_demand_monthly_pulse', c)
                self.assertAlmostEqual(place.modifiers['sol_living_standard_migration_modifier'], .04)
                self.assertNotIn('sol_living_standard_high_growth_modifier', place.modifiers)
            self.assertEqual(rt.calls['sol_solve_country_pop_demand'], 0)
            rt.pulse('sol_ai_yearly_pop_demand_pulse', c)
            self.assertEqual(rt.calls['sol_solve_country_pop_demand'], 1)
            self.assertAlmostEqual(place.modifiers['sol_living_standard_migration_modifier'], .24)
            self.assertEqual(place.modifiers['sol_living_standard_high_growth_modifier'], 1)

    def test_feedback_and_demand_clear_on_disabled_monthly_pulse(self):
        rt, c = CadenceRuntime('stable'), country()
        place = c.locations[0]
        place.variables['sol_location_sol'] = 0
        rt.pulse('sol_local_pop_demand_monthly_pulse', c)
        self.assertIn('sol_living_standard_low_growth_modifier', place.modifiers)
        rt.master = False
        rt.pulse('sol_substitution_cleanup_monthly_pulse', c)
        self.assertFalse(place.modifiers)
        self.assertEqual(rt.calls['sol_solve_country_pop_demand'], 0)

    def test_ai_cached_months_ignore_all_snapshot_changes_and_substitution_modes(self):
        for target in TARGETS:
            for enabled in (False,True):
                with self.subTest(target=target,enabled=enabled):
                    rt=CadenceRuntime(target,enabled=enabled);c=country()
                    c.variables.update(sol_demand_snapshot_locations=999,sol_substitute_dirty=1)
                    c.external['cloth']=0.3
                    c.locations[0].market=Scope('market')
                    c.locations.append(Scope('location',owner=c,variables={SIZE:-0.4}))
                    for _ in range(12):
                        rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                    self.assertEqual(rt.calls['sol_solve_country_pop_demand'],0)
                    self.assertEqual(rt.calls['sol_check_substitution_snapshot'],0)
                    self.assertEqual(len(rt.native_writes),24)
                    self.assertEqual([l.variables[SIZE] for l in c.locations],[0.6,-0.4])

    def test_humans_recompute_each_month(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt=CadenceRuntime(target);c=country(human=True)
                for _ in range(3):rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                self.assertEqual(rt.calls['sol_solve_country_pop_demand'],3)
                self.assertEqual(c.locations[0].variables[SIZE],0.25)

    def test_ai_annual_pulse_recomputes_and_applies_immediately(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt=CadenceRuntime(target);c=country()
                rt.pulse('sol_ai_yearly_pop_demand_pulse',c)
                self.assertEqual(rt.calls['sol_solve_country_pop_demand'],1)
                self.assertEqual(rt.native_writes[-1][1],0.25)
                rt.pulse('sol_ai_yearly_pop_demand_pulse',country(human=True))
                self.assertEqual(rt.calls['sol_solve_country_pop_demand'],1)

    def test_new_country_initializes_once(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt=CadenceRuntime(target);c=country(cached=False)
                c.locations[0].variables.clear()
                for _ in range(2):rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                self.assertEqual(rt.calls['sol_solve_country_pop_demand'],1)
                self.assertEqual([v for _,v in rt.native_writes],[0.25,0.25])

    def test_missing_location_is_neutral_until_annual_update(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt=CadenceRuntime(target);c=country()
                acquired=Scope('location',owner=c)
                c.locations.append(acquired)
                rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                self.assertEqual(rt.calls['sol_solve_country_pop_demand'],0)
                self.assertEqual(acquired.variables[SIZE],0)
                self.assertEqual(c.locations[0].variables[SIZE],0.6)
                rt.pulse('sol_ai_yearly_pop_demand_pulse',c)
                self.assertEqual(acquired.variables[SIZE],0.25)

    def test_existing_zero_and_negative_coefficients_are_preserved(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt=CadenceRuntime(target);c=country()
                c.locations=[Scope('location',owner=c,variables={SIZE:v}) for v in (0,-1,-0.4,2)]
                rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                self.assertEqual([v for _,v in rt.native_writes],[0,-1,-0.4,2])

    def test_control_changes_follow_current_controller_without_polling(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt=CadenceRuntime(target);c=country()
                rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                c.human=True
                rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                c.human=False
                rt.pulse('sol_local_pop_demand_monthly_pulse',c)
                self.assertEqual(rt.calls['sol_solve_country_pop_demand'],1)

    def test_explicit_full_mod_monthly_ai_option_is_preserved(self):
        rt=CadenceRuntime('stable',reduced=False);c=country()
        for _ in range(2):rt.pulse('sol_local_pop_demand_monthly_pulse',c)
        rt.pulse('sol_ai_yearly_pop_demand_pulse',c)
        self.assertEqual(rt.calls['sol_solve_country_pop_demand'],2)

    def test_master_off_and_empty_countries_do_not_enter_monthly_solve(self):
        rt=CadenceRuntime('stable');rt.master=False
        rt.pulse('sol_local_pop_demand_monthly_pulse',country())
        self.assertEqual(rt.calls['sol_solve_country_pop_demand'],0)
        for target in TARGETS:
            rt=CadenceRuntime(target);c=Scope('country',human=False)
            rt.pulse('sol_local_pop_demand_monthly_pulse',c)
            self.assertEqual(rt.calls['sol_solve_country_pop_demand'],0)

    def test_yearly_registration_and_native_post_lobby_refresh_are_present(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt=CadenceRuntime(target)
                entries=block(rt.actions['yearly_country_pulse'],'on_actions')
                self.assertTrue(any(n.key=='sol_ai_yearly_pop_demand_pulse' for n in entries))
                startup=block(rt.actions['on_game_started_after_lobby'],'on_actions')
                self.assertEqual(sum(n.key=='gls_init_on_game_started_after_lobby' for n in startup),1)
                rt.effects['gls_recalculate_global_living_standard']=[]
                rt.pulse('gls_init_on_game_started_after_lobby',Scope('global'))
                self.assertEqual(rt.calls['gls_recalculate_global_living_standard'],1)
                if target=='stable':
                    rt.master=False
                    rt.pulse('gls_init_on_game_started_after_lobby',Scope('global'))
                    self.assertEqual(rt.calls['gls_recalculate_global_living_standard'],1)


class LifecycleTests(unittest.TestCase):
    def test_economics_waits_for_country_selection_and_respects_master(self):
        for target in TARGETS:
            with self.subTest(target=target):
                rt = LifecycleRuntime(target)
                rt.dispatch('on_game_start', Scope('global'))
                self.assertEqual(rt.calls['gls_recalculate_global_living_standard'], 0)
                rt.dispatch('on_game_started_after_lobby', Scope('global'))
                self.assertEqual(rt.calls['gls_recalculate_global_living_standard'], 1)
                if target == 'stable':
                    rt.master = False
                    rt.dispatch('on_game_started_after_lobby', Scope('global'))
                    self.assertEqual(rt.calls['gls_recalculate_global_living_standard'], 1)

    def test_native_new_game_stamp_prevents_migration_notice(self):
        rt = LifecycleRuntime('stable')
        metadata = json.loads((ROOT/'src/stable/.metadata/metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(rt.migration_marker, f"SOL_migration_{metadata['version']}_seen")
        rt.dispatch('on_game_start', Scope('global'))
        self.assertIn(rt.migration_marker, rt.flags)
        for _ in range(2):
            for c in rt.countries:
                rt.dispatch('monthly_country_pulse', c)
        self.assertFalse(rt.notifications)

    def test_old_save_notifies_all_humans_once_even_with_legacy_flags(self):
        rt = LifecycleRuntime('stable')
        rt.flags.update({'sol_game_started_after_lobby', 'sol_is_new_game',
                         'SOL_migration_v3_seen', 'SOL_migration_260101_seen'})
        # Loading while paused dispatches no native monthly tick.
        self.assertFalse(rt.notifications)
        rt.dispatch('monthly_country_pulse', rt.countries[1])
        self.assertNotIn(rt.migration_marker, rt.flags)
        for _ in range(2):
            for c in rt.countries:
                rt.dispatch('monthly_country_pulse', c)
        self.assertEqual(rt.notifications, [('sol_migration.1', rt.countries[0]),
                                            ('sol_migration.1', rt.countries[2])])
        rt.dispatch('SOL_migration_fire_event', Scope('global'))
        self.assertEqual(len(rt.notifications), 2)
        self.assertEqual(rt.calls['gls_recalculate_global_living_standard'], 0)
        loaded = LifecycleRuntime('stable')
        loaded.flags = rt.flags.copy()
        for c in loaded.countries:
            loaded.dispatch('monthly_country_pulse', c)
        self.assertFalse(loaded.notifications)

    def test_already_migrated_save_skips_notice_with_sol_disabled(self):
        rt = LifecycleRuntime('stable')
        rt.master = False
        rt.flags.add(rt.migration_marker)
        for c in rt.countries:
            rt.dispatch('monthly_country_pulse', c)
        self.assertFalse(rt.notifications)
        rt.flags.clear()
        rt.dispatch('monthly_country_pulse', rt.countries[0])
        self.assertEqual(len(rt.notifications), 2)

    def test_legacy_gui_entrypoints_and_registrations_are_absent(self):
        names = ('sol_after_lobby_caller', 'sol_load_after_lobby_caller', 'sol_gls_init_caller')
        for target in TARGETS:
            root = ROOT/'src'/target
            for folder in ('in_game/gui', 'in_game/common/scripted_guis'):
                for path in (root/folder).rglob('*'):
                    if path.suffix in {'.txt', '.gui'}:
                        content = path.read_text(encoding='utf-8-sig')
                        for name in names:
                            self.assertNotIn(name, content, str(path))


if __name__ == '__main__':
    unittest.main()
