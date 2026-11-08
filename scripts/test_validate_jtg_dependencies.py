"""Dependency modifier declarations are target-scoped and fail closed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import validate
from sol_substitution_profile import load_jtg_profile


class DependencyModifierTests(unittest.TestCase):
    def setUp(self):
        validate.issues.clear()
        validate.dependency_modifier_whitelist.cache_clear()
        self.addCleanup(validate.issues.clear)
        self.addCleanup(validate.dependency_modifier_whitelist.cache_clear)

    def check(self, target, text):
        path = validate.MOD_SOURCE_DIR / target / "in_game/common/auto_modifiers/test.txt"
        names = validate.modifier_whitelist_for_path(path, validate.load_modifier_whitelist())
        validate.check_modifier_names(path, text, names)
        return list(validate.issues)

    def test_all_thirty_real_jtg_declarations_and_typo(self):
        from gen_whole_group_baskets import CORE
        goods = set(load_jtg_profile().goods) - set(CORE)
        self.assertEqual(len(goods), 30)
        text = "\n".join(f"global_{g}_pop_demand = 1" for g in sorted(goods))
        self.assertEqual(self.check("sol_jtg_compatibility_submod", text), [])
        errors = self.check("sol_jtg_compatibility_submod", "global_plastter_pop_demand = 1")
        self.assertEqual(len(errors), 1)
        self.assertIn("[MODIFIER]", errors[0])

    def test_non_jtg_does_not_receive_dependency_names(self):
        for target in ("stable", "sol_standalone", "sol_pp_compatibility_submod", "sol_mnt_compatibility_submod"):
            with self.subTest(target=target):
                validate.issues.clear()
                self.assertEqual(len(self.check(target, "global_plaster_pop_demand = 1")), 1)

    def test_reference_identity_and_top_level_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mod = root / "src/target"
            metadata = mod / ".metadata/metadata.json"
            metadata.parent.mkdir(parents=True)
            metadata.write_text(json.dumps({"relationships": [{"rel_type": "dependency", "id": "moveably.goods"}]}), encoding="utf-8")
            reference = root / "reference_mods/3785316314"
            identity = reference / ".metadata/metadata.json"
            identity.parent.mkdir(parents=True)
            definitions = reference / "main_menu/common/modifier_type_definitions/test.txt"
            definitions.parent.mkdir(parents=True)
            definitions.write_text("global_declared = { nested_typo = { } }", encoding="utf-8")
            with patch.object(validate, "BASE_ROOT", root):
                self.assertEqual(validate.dependency_modifier_whitelist(mod), frozenset())
                validate.dependency_modifier_whitelist.cache_clear()
                identity.write_text('{"id":"wrong.mod"}', encoding="utf-8")
                self.assertEqual(validate.dependency_modifier_whitelist(mod), frozenset())
                validate.dependency_modifier_whitelist.cache_clear()
                identity.write_text('{"id":"moveably.goods"}', encoding="utf-8")
                self.assertEqual(validate.dependency_modifier_whitelist(mod), {"global_declared"})
                validate.dependency_modifier_whitelist.cache_clear()
                metadata.write_text('{"relationships":[]}', encoding="utf-8")
                self.assertEqual(validate.dependency_modifier_whitelist(mod), frozenset())


if __name__ == "__main__":
    unittest.main()
