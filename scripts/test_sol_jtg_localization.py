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
            self.assertFalse(keys & set(jtg.EXPECTED_ALL_NEW_GOODS), (path, keys & set(jtg.EXPECTED_ALL_NEW_GOODS)))


if __name__ == "__main__":
    unittest.main()
