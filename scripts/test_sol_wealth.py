"""Execute SOL wealth/tax values against independent economic fixtures."""
from pathlib import Path
import ast
import json
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from test_sol_substitution import Runtime, Scope, parse
from gen_market_unit_consumption import _load_good_rows

ROOT = Path(__file__).resolve().parents[1]
ESTATES = ("nobles", "clergy", "burghers", "commoner", "tribesmen")
DISPLAYS = ("noble", "clergy", "burghers", "commoner", "tribesmen")
TAX_KEYS = ("nobles_estate", "clergy_estate", "burghers_estate", "peasants_estate", "tribes_estate")


class WealthRuntime(Runtime):
    def __init__(self, target):
        super().__init__(_load_good_rows())
        self.script_values.update({n.key: n.value for n in parse(
            (ROOT / "src" / target / "in_game/common/script_values/SOL_pop_values.txt").read_text(encoding="utf-8-sig"))})

    def value(self, node, scope, initial=0.):
        if isinstance(node, str):
            if node in ("local_control", "location_tax_base", "location_potential_tax_base"):
                return scope.external[node]
            if node.startswith("owner.estate_tax_percentage:"):
                return scope.owner.external[node.split(":", 1)[1]]
            if node.startswith("modifier:"):
                return scope.modifiers.get(node[9:], 0.)
        return super().value(node, scope, initial)

    def test(self, node, scope):
        if node.key == "owner" and isinstance(node.value, list):
            return self.condition(node.value, scope.owner)
        return super().test(node, scope)


class WealthTests(unittest.TestCase):
    def test_zero_wealth_and_distinct_estate_tax_rates(self):
        for target in ("stable", "sol_standalone"):
            runtime = WealthRuntime(target)
            rates = (.1, .2, .3, .4, .5)
            loc = Scope("location", owner=Scope("country", external=dict(zip(TAX_KEYS, rates))),
                        external=dict(local_control=0., location_tax_base=0., location_potential_tax_base=0.))
            self.assertEqual(runtime.value("local_wealth_display", loc), 0.)
            for estate in ESTATES:
                self.assertEqual(runtime.value(f"local_{estate}_income_pool", loc), 0.)
            loc.external.update(location_potential_tax_base=100., location_tax_base=30.)
            for estate, rate in zip(ESTATES, rates):
                self.assertAlmostEqual(runtime.value(f"local_{estate}_income_pool", loc), 100. - 30. * rate)

    def test_direct_wealth_all_estates_tax_and_maintenance(self):
        for target in ("stable", "sol_standalone"):
            runtime = WealthRuntime(target)
            for control, tax in ((1., 100.), (.75, 75.), (.005, .5), (0., 0.), (.5, 0.)):
                for rate in (0., .23, 1.):
                    with self.subTest(target=target, control=control, tax=tax, rate=rate):
                        owner = Scope("country", external=dict.fromkeys(TAX_KEYS, rate))
                        loc = Scope("location", owner=owner,
                            external=dict(local_control=control, location_tax_base=tax, location_potential_tax_base=100.))
                        self.assertEqual(runtime.value("local_wealth_display", loc), 100.)
                        self.assertEqual(runtime.value("local_gdp_from_taxbase_control_display", loc), 100.)
                        self.assertEqual(runtime.value("local_tax_base_display", loc), tax)
                        self.assertEqual(runtime.value("local_effective_control", loc), control)
                        self.assertEqual(runtime.value("local_control_loss_component", loc), 100. - tax)
                        for estate, display in zip(ESTATES, DISPLAYS):
                            # Shares are independent of wealth. Isolate the income pipeline.
                            share = "local_" + estate + ("_effective_tax_share" if estate in ("nobles", "commoner") else "_tax_share")
                            runtime.script_values[share] = parse("value = 2")
                            runtime.script_values["local_total_tax_share"] = parse("value = 10")
                            maintenance_estate = "commoners" if estate == "commoner" else estate
                            loc.variables[f"sol_location_estate_building_maintenance_{maintenance_estate}"] = 3.
                            expected = 100. - tax * rate
                            self.assertAlmostEqual(runtime.value(f"local_{estate}_income_pool", loc), expected)
                            self.assertAlmostEqual(runtime.value(f"local_{estate}_taxed_component", loc), tax * (1. - rate))
                            self.assertAlmostEqual(runtime.value(f"local_{display}_gdp_display", loc), max(0., expected * .2 - 3.))
                            if control >= .01 and tax:
                                self.assertAlmostEqual(expected, tax / control - tax * rate)

    def test_no_control_division_and_compat_targets_inherit_base_values(self):
        for target in ("stable", "sol_standalone"):
            text = (ROOT / "src" / target / "in_game/common/script_values/SOL_pop_values.txt").read_text()
            self.assertNotIn("divide = local_effective_control", text)
        for target in ("sol_pp_compatibility_submod", "sol_mnt_compatibility_submod", "sol_jtg_compatibility_submod"):
            for path in (ROOT / "src" / target / "in_game/common/script_values").glob("*.txt"):
                keys = {n.key for n in parse(path.read_text(encoding="utf-8-sig"))}
                self.assertFalse(keys & {"local_wealth_display", "local_control_loss_component", *[f"local_{e}_income_pool" for e in ESTATES]}, path)

    def test_simulator_explicit_wealth_and_presets(self):
        names = ("nobles", "clergy", "burghers", "commoners", "tribesmen")
        # Execute the real pure income code without requiring Streamlit's pandas
        # dependency for the unrelated plotting/simulation functions.
        source = ast.parse((ROOT / "tools/sol_demand_simulator/simulator.py").read_text(encoding="utf-8"))
        keep = {"TAX_WEIGHTS", "_clamp", "ScenarioParams", "StrataState", "fn1_gdp_per_capita"}
        selected = [n for n in source.body if getattr(n, "name", None) in keep or
                    isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in keep for t in n.targets)]
        from dataclasses import dataclass
        namespace = dict(dataclass=dataclass, Dict=dict, STRATA=names)
        exec(compile(ast.Module(body=selected, type_ignores=[]), "simulator_income", "exec"), namespace)
        ScenarioParams, StrataState, fn1_gdp_per_capita = (namespace[n] for n in ("ScenarioParams", "StrataState", "fn1_gdp_per_capita"))
        for tax in (75., .5, 0.):
            p = ScenarioParams(10., 0, tax, 100., 1., {s: StrataState(1., .2, 0.) for s in names}, 1, 1)
            self.assertAlmostEqual(sum(fn1_gdp_per_capita(p).values()), 100. - tax * .2)
        data = json.loads((ROOT / "tools/sol_demand_simulator/user_presets.json").read_text(encoding="utf-8"))
        for preset in data.values():
            self.assertIn("wealth", preset)
            self.assertNotIn("effective_control", preset)


if __name__ == "__main__":
    unittest.main()
