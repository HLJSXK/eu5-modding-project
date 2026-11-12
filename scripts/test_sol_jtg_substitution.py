"""Execute emitted JTG effects with an independently configured arithmetic oracle."""
import sys
import unittest
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_jtg_compat as jtg
from sol_substitution import render_country_runtime, render_location_spending, render_values, render_modifiers, POPS
from sol_substitution_profile import load_jtg_profile
from test_sol_substitution import Runtime, Scope, parse
from test_sol_jtg_profile import APPROVED


class JtgRuntime(Runtime):
    def __init__(self):
        rows = jtg._combined_good_rows(jtg._load_rows())
        p = load_jtg_profile()
        self.effects = {n.key.removeprefix("REPLACE:"): n.value for n in parse(render_country_runtime(rows, profile=p) + render_location_spending(rows, profile=p))}
        # Override with the real compatibility entry points, including REPLACE operation wrappers.
        for n in parse(jtg._render_substitution_runtime(jtg._load_rows()) + jtg._render_effects(jtg._load_rows())):
            self.effects[n.key.removeprefix("REPLACE:")] = n.value
        self.quantities = {f"sol_unit_consumption_{pop}_{g}": q[pop] for g, _, q in rows for pop in POPS}
        self.prices = {g: price for g, price, _ in rows}
        self.maps, self.saved = {}, {}
        self.enabled = True
        self.script_values = {n.key: n.value for n in parse(render_values(profile=p))}
        self.auto_modifiers = {n.key: n.value for n in parse(render_modifiers(profile=p))}
        root = Path(__file__).resolve().parents[1]
        actual_values = (root / "src/stable/in_game/common/script_values/SOL_country_substitute_values.txt").read_text(encoding="utf-8-sig") + jtg.SUBSTITUTION_VALUES_OUTPUT.read_text(encoding="utf-8-sig")
        actual_modifiers = (root / "src/stable/in_game/common/auto_modifiers/SOL_substitute_global_modifiers.txt").read_text(encoding="utf-8-sig") + jtg.SUBSTITUTION_MODIFIERS_OUTPUT.read_text(encoding="utf-8-sig")
        nodes = parse(actual_modifiers)
        assert len(nodes) == len({n.key for n in nodes}) == 86
        self.auto_modifiers = {n.key: n.value for n in nodes}
        self.script_values = {n.key: n.value for n in parse(actual_values)}
        self.operations, self.local_context = Counter(), {}
        self.rows = rows


class JtgExecution(unittest.TestCase):
    def test_legacy_market_cache_requires_profile_schema(self):
        class LegacyRuntime(JtgRuntime):
            migrated = False

            def test(self, node, scope):
                if node.key == "has_global_variable" and node.value == load_jtg_profile().cache_schema:
                    return self.migrated
                return super().test(node, scope)

            def run(self, effect, scope):
                if effect == "sol_refresh_market_pop_demand_maps":
                    self.migrated = True
                    self.operations["profile_world_refresh"] += 1
                    return
                return super().run(effect, scope)

        rt = LegacyRuntime()
        country = Scope("country")
        market = rt.market({g: 1 for g in rt.prices if g not in jtg.EXPECTED_DEMAND_GOODS})
        country.locations = [Scope("location", owner=country, market=market, pops={"nobles": 100})]
        rt.run("sol_refresh_country_substitution", country)
        self.assertTrue(rt.migrated)
        self.assertEqual(rt.operations["profile_world_refresh"], 1)
        rt.run("sol_refresh_country_substitution", country)
        self.assertEqual(rt.operations["profile_world_refresh"], 1)

    def fixture(self, weights=None, supplied=None, external=None):
        rt = JtgRuntime()
        country = Scope("country", external=external or {})
        market = rt.market(weights or dict.fromkeys(rt.prices, 1), supplied)
        loc = Scope("location", owner=country, market=market, pops={"nobles": 100})
        country.locations = [loc]
        return rt, country, loc

    def test_neutral_all_eighty_six_and_no_drift(self):
        rt, country, loc = self.fixture()
        for _ in range(3):
            rt.run("sol_refresh_country_substitution", country)
            for good in rt.prices:
                self.assertAlmostEqual(country.variables["sol_good_effective_" + good], 1)
                self.assertEqual(rt.auto_strength(good, country), 0)
        self.assertEqual(len(rt.auto_modifiers), 86)

    def test_overlap_price_supply_external_and_country_isolation(self):
        rt, country, loc = self.fixture(external={"candles": .5})
        weights = dict.fromkeys(rt.prices, 1)
        weights.update(candles=2, soap=.5, aromatics=1.5)
        for g, w in weights.items():
            rt.maps[("sol_market_substitute_weight_" + g, id(loc.market))] = w
        # Missing whale oil supply excludes it from both historical and current averages.
        rt.maps[("sol_market_consumes_whaleoil", id(loc.market))] = 0
        rt.run("sol_refresh_country_substitution", country)
        p = load_jtg_profile()
        q = {g: qs["nobles"] for g, _, qs in rt.rows}
        for good in jtg.EXPECTED_DEMAND_GOODS:
            current, neutral = 0., 0.
            for group in p.subscriptions["nobles"]:
                members = [g for g in p.groups[group] if q[g] > 0 and g != "whaleoil"]
                if good in members:
                    current += p.historical_sizes[group] * weights[good] / sum(weights[g] for g in members)
                    neutral += p.historical_sizes[group] / len(members)
            expected = current / neutral if neutral else 1
            self.assertAlmostEqual(country.variables["sol_sub_multiplier_" + good], expected, msg=good)
        economic = lambda c: {k: v for k, v in c.variables.items() if not k.startswith("sol_sub_perf_")}
        saved = economic(country)
        rt.run("sol_refresh_country_substitution", country)
        self.assertEqual(economic(country), saved)

        other = Scope("country", locations=[])
        rt.run("sol_refresh_country_substitution", other)
        self.assertEqual(economic(country), saved)
        rt.enabled = False
        rt.run("sol_refresh_country_substitution", country)
        self.assertAlmostEqual(country.variables["sol_good_effective_candles"], 1.5)
        self.assertEqual(rt.auto_strength("candles", country), 0)
        rt.enabled = True
        rt.run("sol_refresh_country_substitution", country)
        self.assertEqual(economic(country), saved)

    def test_shared_market_spending_counts_each_good_once(self):
        rt, country, loc = self.fixture(external={"candles": .5})
        other = Scope("country", external={"candles": -.5})
        otherloc = Scope("location", owner=other, market=loc.market, pops={"nobles": 100})
        other.locations = [otherloc]
        for good in rt.prices:
            rt.maps[("sol_market_good_spending_nobles_" + good, id(loc.market))] = 1
        for owner, location in ((country, loc), (other, otherloc), (country, loc)):
            rt.run("sol_refresh_country_substitution", owner)
            rt.run("sol_compute_substitute_unit_spending", location)
            expected = sum(owner.variables["sol_good_effective_" + g] for g, _, qs in rt.rows if qs["nobles"] > 0)
            self.assertAlmostEqual(location.variables["sol_unit_spending_nobles"], expected)
        self.assertAlmostEqual(loc.variables["sol_unit_spending_nobles"] - otherloc.variables["sol_unit_spending_nobles"], 1)

    def test_two_markets_weight_by_population(self):
        rt, country, loc = self.fixture()
        second_weights = dict.fromkeys(rt.prices, 1)
        second_weights["candles"] = 2
        second = Scope("location", owner=country, market=rt.market(second_weights), pops={"nobles": 300})
        country.locations.append(second)
        rt.run("sol_refresh_country_substitution", country)
        p = load_jtg_profile()
        numerator, denominator = 0., 0.
        for group in p.subscriptions["nobles"]:
            members = [g for g in p.groups[group] if rt.quantities["sol_unit_consumption_nobles_" + g] > 0]
            if "candles" in members:
                numerator += p.historical_sizes[group] * 2 / sum(second_weights[g] for g in members)
                denominator += p.historical_sizes[group] / len(members)
        expected = (100 + 300 * numerator / denominator) / 400
        self.assertAlmostEqual(country.variables["sol_sub_multiplier_candles"], expected)

    def test_missing_effective_cache_uses_external_demand_once(self):
        for external, expected in ((.5, 1.5), (-.5, .5), (-2, 0)):
            rt, country, loc = self.fixture(external={"candles": external})
            rt.maps[("sol_market_good_spending_nobles_candles", id(loc.market))] = 10
            rt.run("sol_compute_substitute_unit_spending", loc)
            self.assertAlmostEqual(loc.variables["sol_unit_spending_nobles"], 10 * expected)



if __name__ == "__main__":
    unittest.main()
