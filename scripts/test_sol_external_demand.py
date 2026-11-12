"""Execute neutral JTG external-demand accounting and cache lifecycle."""
import sys
import unittest
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from gen_market_unit_consumption import _load_good_rows
import gen_sol_jtg_compat as jtg
from sol_substitution import CORE, POPS, render_location_spending
from test_sol_substitution import Runtime, Scope, parse

class ExternalDemandTests(unittest.TestCase):
    def test_actual_jtg_render_and_all_modifier_declarations(self):
        text = jtg._render_effects(jtg._load_rows())
        runtime = jtg._render_substitution_runtime(jtg._load_rows())
        root = Path(__file__).resolve().parent.parent
        declarations = "\n".join(p.read_text(encoding="utf-8-sig") for p in (root / ".eu5-base/reference_mods/3785316314/main_menu/common/modifier_type_definitions").glob("*.txt"))
        self.assertEqual(len(jtg.EXPECTED_DEMAND_GOODS), 30)
        for good in jtg.EXPECTED_DEMAND_GOODS:
            self.assertIn(f"modifier:global_{good}_pop_demand", runtime)
            self.assertIn(f"global_{good}_pop_demand", declarations)
            self.assertIn(f"has_variable = sol_good_effective_{good}", text)

    def test_generated_external_multipliers_cache_refresh_and_disabled_lifecycle(self):
        rows = _load_good_rows()
        rt = Runtime(rows)
        effect = parse(render_location_spending([("soap", 1, {p: 1 for p in POPS})], external_goods=("soap",)))[0]
        rt.effects[effect.key] = effect.value
        country = Scope("country", external={"soap": .25})
        market = rt.market(dict.fromkeys(CORE, 1))
        loc = Scope("location", owner=country, market=market)
        country.locations = [loc]
        rt.maps[("sol_market_good_spending_nobles_soap", id(market))] = 10
        country.variables["sol_good_effective_soap"] = 99
        rt.run("sol_compute_substitute_unit_spending", loc)
        self.assertEqual(loc.variables["sol_unit_spending_nobles"], 12.5)
        country.external["soap"] = -.25
        rt.run("sol_compute_substitute_unit_spending", loc)
        self.assertEqual(loc.variables["sol_unit_spending_nobles"], 12.5)
        for enabled, offset, expected in ((True, -.25, 7.5), (False, .5, 15), (False, -2, 0)):
            rt.enabled = enabled
            country.external["soap"] = offset
            rt.run("sol_refresh_country_substitution", country)
            self.assertNotIn(("sol_country_market_spending_owner", id(market)), rt.maps)
            rt.run("sol_compute_substitute_unit_spending", loc)
            self.assertEqual(loc.variables["sol_unit_spending_nobles"], expected)
        self.assertNotIn("sol_sub_size_soap", country.variables)
        self.assertFalse(any(v == "SOL_LSHUD_GOOD_ICON_soap" for v in country.variables.values()))

if __name__ == "__main__":
    unittest.main()
