"""Resolve emitted SOL localization chains against replaceable JTG names."""
import re
import sys
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sol_substitution_profile import load_jtg_profile
import gen_sol_jtg_compat as jtg

ROOT = Path(__file__).resolve().parents[1]
ENTRY = re.compile(r'^\s*([\w.]+):(?:\d+)?\s*"(.*)"\s*$', re.M)


def labels(language):
    merged = {}
    for target in ("stable", "sol_jtg_compatibility_submod"):
        for path in sorted((ROOT / "src" / target / "main_menu/localization" / language).glob("*.yml")):
            merged.update(ENTRY.findall(path.read_text(encoding="utf-8-sig")))
    return merged


def resolve(key, table, stack=()):
    if key in stack:
        raise AssertionError(f"Localization cycle: {stack + (key,)}")
    if key not in table:
        raise AssertionError(f"Missing localization: {key}")
    return re.sub(r"\$([\w.]+)\$", lambda m: resolve(m[1], table, stack + (key,)), table[key])


class LocalizationAudit(unittest.TestCase):
    def test_four_column_chip_short_names_are_local_to_details(self):
        from test_sol_substitution import parse
        expected = {"lacquerware": "Lacquer", "medicaments": "Medic.", "millet": "St. grains",
                    "pewterware": "Pewterw.", "precision_instruments": "Prec. Instr."}
        target = ROOT / "src/sol_jtg_compatibility_submod"
        chip_counts = []

        def visit(nodes):
            for node in nodes:
                if not isinstance(node.value, list):
                    continue
                if node.key == "hbox":
                    widgets = [n for n in node.value if n.key == "widget" and isinstance(n.value, list)
                               and any(c.key == "text_single" and isinstance(c.value, list)
                                       and any(t.key == "raw_text" and str(t.value).startswith("@") for t in c.value)
                                       for c in n.value)]
                    if widgets:
                        chip_counts.append(len(widgets))
                        self.assertLessEqual(len(widgets), 4)
                        for widget in widgets:
                            size = next(n.value for n in widget.value if n.key == "size")
                            self.assertEqual([str(n.key) for n in size], ["72", "27"])
                            text = next(n.value for n in widget.value if n.key == "text_single")
                            fields = {n.key: n.value for n in text}
                            shortened = "SOL_GOOD_SHORT_" in fields["raw_text"]
                            if shortened:
                                self.assertEqual(fields["elide"], "right")
                                self.assertEqual(str(fields["fontsize_min"]), "11")
                            else:
                                self.assertNotIn("elide", fields)
                visit(node.value)

        # Market tooltips inherit goods_details; they do not duplicate its chip definition.
        market = (target / "in_game/gui/shared/market_tooltips.gui").read_text(encoding="utf-8-sig")
        def uses_details(nodes):
            return any((n.key == "using" and n.value == "goods_details") or
                       (isinstance(n.value, list) and uses_details(n.value)) for n in nodes)
        self.assertTrue(uses_details(parse(market)))
        for relative in ("main_menu/gui/shared/goods_details.gui",):
            gui = (target / relative).read_text(encoding="utf-8-sig")
            visit(parse(gui))
            for good in expected:
                self.assertTrue(re.search(rf"raw_text = \"@{good}! \[Localize\('SOL_GOOD_SHORT_{good}'\)\]\" tooltip = \"{good}\"", gui), (relative, good))
        self.assertIn(4, chip_counts)
        for relative in ("in_game/gui/zz_SOL_economy_local.gui", "in_game/gui/panels/situation/global_living_standard.gui", "in_game/gui/SOL_lshud.gui"):
            self.assertNotIn("SOL_GOOD_SHORT_", (target / relative).read_text(encoding="utf-8-sig"))
        for language in ("english", "simp_chinese"):
            table = labels(language)
            for good, short in expected.items():
                table[good] = "third_party_full_" + good
                wanted = short if language == "english" else table[good]
                self.assertEqual(resolve("SOL_GOOD_SHORT_" + good, table), wanted)
                self.assertIn(table[good], resolve("AUTO_MODIFIER_NAME_sol_substitute_" + good, table))
                self.assertIn(table[good], resolve("AUTO_MODIFIER_DESC_sol_substitute_" + good, table))

    def test_generated_sol_key_sets_match_between_languages(self):
        target = ROOT / "src/sol_jtg_compatibility_submod/main_menu/localization"
        sets = {}
        for language in ("english", "simp_chinese"):
            keys = set()
            for path in (target / language).glob("*.yml"):
                keys.update(key for key, _ in ENTRY.findall(path.read_text(encoding="utf-8-sig")))
            sets[language] = keys
        self.assertEqual(sets["english"], sets["simp_chinese"])

    def test_profile_group_names_resolve_consistently_on_three_surfaces(self):
        for language in ("english", "simp_chinese"):
            table = labels(language)
            for group, members in load_jtg_profile().groups.items():
                card = resolve("SOL_SUBGROUP_" + group.upper(), table)
                detail = resolve("SOL_GOOD_GROUP_" + group, table)
                self.assertEqual(resolve("SOL_GOOD_GROUP_NAME_" + group.upper(), table), card)
                self.assertIn(card, detail)
                for good in members:
                    self.assertIn(card, resolve("SOL_GOOD_SUB_" + good, table), (language, group, good))
            expected = "知识" if language == "simp_chinese" else "Knowledge"
            self.assertEqual(resolve("SOL_SUBGROUP_KNOWLEDGE", table), expected)

    def test_third_party_good_names_follow_in_auto_names_and_gui_localize(self):
        target = ROOT / "src/sol_jtg_compatibility_submod"
        gui = "\n".join(p.read_text(encoding="utf-8-sig") for p in (target / "in_game/gui").rglob("*.gui"))
        for language in ("english", "simp_chinese"):
            table = labels(language)
            for good in load_jtg_profile().goods:
                table[good] = "external_name_" + good
                self.assertIn(table[good], resolve("AUTO_MODIFIER_NAME_sol_substitute_" + good, table))
                self.assertIn(table[good], resolve("AUTO_MODIFIER_DESC_sol_substitute_" + good, table))
            for good, first, second in (("plaster", "汉化灰泥甲", "汉化灰泥乙"),
                                        ("precision_instruments", "汉化精密仪器甲", "汉化精密仪器乙")):
                self.assertRegex(gui, rf"Localize\('{good}'\)")
                for external_name in (first, second):
                    table[good] = external_name
                    # Evaluate the emitted GUI Localize operand with the same merged dictionary.
                    operand = re.search(rf"Localize\('({good})'\)", gui)[1]
                    self.assertEqual(resolve(operand, table), external_name)
                    self.assertIn(external_name, resolve("AUTO_MODIFIER_NAME_sol_substitute_" + good, table))

    def test_no_original_jtg_name_overrides_and_bom(self):
        root = ROOT / "src/sol_jtg_compatibility_submod/main_menu/localization"
        for path in root.rglob("*.yml"):
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), str(path))
            keys = {key for key, _ in ENTRY.findall(path.read_text(encoding="utf-8-sig"))}
            original_names = set(jtg.EXPECTED_ALL_NEW_GOODS) | set(load_jtg_profile().goods)
            self.assertFalse(keys & original_names, (path, keys & original_names))


if __name__ == "__main__":
    unittest.main()
