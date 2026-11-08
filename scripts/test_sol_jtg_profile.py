"""Independent approved mapping and baseline-isolation audit."""
import json
import re
import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gen_sol_jtg_compat as jtg
from sol_substitution_profile import load_jtg_profile
from sol_substitution import CONFIG, GROUPS

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tmp/jtg-substitution-baseline"
APPROVED = {
    "protein": "meat cheese", "household": "soap pewterware candles tallow palmoil whaleoil",
    "heating": "candles tallow palmoil whaleoil", "spices": "cardamom cinnamon nutmeg star_anise vanilla ginger turmeric",
    "condiments": "ginger turmeric", "luxury_goods": "brassware clocks cosmetics mirrors ornaments perfume silverware aromatics bells",
    "ritual": "aromatics bells", "knowledge": "optics precision_instruments", "treasures": "jade diamonds obsidian",
    "crude_goods": "plaster",
}
OVERRIDES = {("plaster", "laborers"): .00063, ("plaster", "peasants"): .00014, ("plaster", "soldiers"): .00014,
             ("cosmetics", "clergy"): .00630, ("perfume", "clergy"): .00630, ("precision_instruments", "clergy"): .00867,
             ("ginger", "laborers"): .00011, ("ginger", "soldiers"): .00011,
             ("turmeric", "laborers"): .00011, ("turmeric", "soldiers"): .00011, ("candles", "soldiers"): .00018}


class ProfileAudit(unittest.TestCase):
    def test_ui_cells_and_group_memberships_cover_every_profile_good(self):
        from sol_goods_ui import _good_cell
        from gen_sol_goods_tooltip import _memberships
        p = load_jtg_profile()
        by_good, by_group = _memberships(p)
        for good in p.goods:
            cell = "\n".join(_good_cell("", good, "yes", "Location.GetMarket.MakeScope", p))
            self.assertEqual(cell.count("raw_text = \"@"), 7, good)
            self.assertIn("SOL_GOOD_SUB_" + good, cell)
            self.assertIn("sol_substitute_" + good + "_display", cell)
            self.assertEqual({entry[0] for entry in by_good[good]}, {g for g, members in p.groups.items() if good in members})
        self.assertEqual(set(by_group), set(p.groups))
        self.assertEqual(len(p.groups["luxury_goods"]), 15)
        self.assertEqual(len(p.groups["household"]), 11)
        self.assertEqual(len(p.groups["spices"]), 11)
        target = ROOT / "src/sol_jtg_compatibility_submod"
        local = (target / "in_game/gui/zz_SOL_economy_local.gui").read_text(encoding="utf-8-sig")
        situation = (target / "in_game/gui/panels/situation/global_living_standard.gui").read_text(encoding="utf-8-sig")
        market = (target / "in_game/gui/shared/market_tooltips.gui").read_text(encoding="utf-8-sig")
        for good in p.goods:
            for surface in (local, situation):
                self.assertIn("sol_substitute_" + good + "_display", surface)
            self.assertIn(good, market)
        hud = (target / "in_game/gui/SOL_lshud.gui").read_text(encoding="utf-8-sig")
        self.assertEqual(set(re.findall(r"sol_sub_hud_good_(\d+)", hud)), set("123456"))
        for language in ("english", "simp_chinese"):
            path = target / f"main_menu/localization/{language}/zz_SOL_JTG_substitution_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            labels = path.read_text(encoding="utf-8-sig")
            for good in p.goods:
                for prefix in ("SOL_LSHUD_GOOD_ICON_", "AUTO_MODIFIER_NAME_sol_substitute_", "AUTO_MODIFIER_DESC_sol_substitute_"):
                    self.assertIn(prefix + good + ":", labels)

    def test_exact_mapping_and_unchanged_default_groups(self):
        p = load_jtg_profile()
        added = set(jtg.EXPECTED_DEMAND_GOODS)
        self.assertEqual(dict(p.historical_sizes), CONFIG["historical_sizes"])
        from sol_substitution import SUBSCRIBED
        self.assertEqual({pop: set(groups) for pop, groups in p.subscriptions.items()},
                         {pop: set(groups) for pop, groups in SUBSCRIBED.items()})
        self.assertEqual(len(added), 30)
        self.assertEqual(set(p.goods) - set(added), set(g for members in GROUPS.values() for g in members))
        for group, members in p.groups.items():
            self.assertEqual(set(members) & added, set(APPROVED.get(group, "").split()), group)
            self.assertEqual(set(members) - added, set(GROUPS[group]), group)
        self.assertEqual({(g, pop): v for g, qs in p.quantity_overrides.items() for pop, v in qs.items()}, OVERRIDES)

    def test_only_eleven_quantity_cells_change_and_emit_budget_report(self):
        fixture = json.loads((ROOT / "scripts/fixtures/jtg_quantities_before_grouping_20261109.json").read_text())
        before = {g: (price, q) for g, price, q in fixture["rows"]}
        after = {g: (price, q) for g, price, q in jtg._jtg_good_rows(jtg._load_rows())}
        profile = load_jtg_profile()
        combined = {g: qs for g, _, qs in jtg._combined_good_rows(jtg._load_rows())}
        for pop, groups in profile.subscriptions.items():
            for group in groups:
                for good in profile.groups[group]:
                    self.assertGreater(combined[good][pop], 0, (pop, group, good))
        changes = {(g, pop): value for g, (_, qs) in after.items() for pop, value in qs.items() if value != before[g][1][pop]}
        self.assertEqual(changes, OVERRIDES)
        pops = next(iter(after.values()))[1]
        report = {pop: {"before": sum(price * qs[pop] for price, qs in before.values()),
                        "after": sum(price * qs[pop] for price, qs in after.values())} for pop in pops}
        from gen_market_unit_consumption import _load_good_rows
        base = _load_good_rows()
        report = {"external": report, "combined": {pop: {
            side: values[side] + sum(price * qs[pop] for _, price, qs in base)
            for side in ("before", "after")} for pop, values in report.items()}}
        BASELINE.mkdir(parents=True, exist_ok=True)
        (BASELINE / "budget_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")



if __name__ == "__main__":
    unittest.main()
