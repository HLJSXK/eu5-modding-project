"""Check validation context and reporting without hiding genuine source errors."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import validate


@unittest.skipUnless(sys.platform == 'win32', 'Windows batch integration')
class BuildValidationTests(unittest.TestCase):
    def test_batch_uses_selected_interpreter_and_preserves_validation_status(self):
        build = (Path(__file__).resolve().parents[1] / 'build.bat').read_bytes()
        for validation_exit, selection in ((0, 'explicit'), (7, 'explicit'), (0, 'active_eu5')):
            with self.subTest(validation_exit=validation_exit, selection=selection), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / 'build.bat').write_bytes(build)
                scripts = root / 'scripts'
                scripts.mkdir()
                (scripts / 'gen_sol_chain.py').write_text(
                    'from pathlib import Path\nPath("generated").touch()\n', encoding='utf-8')
                (scripts / 'validate.py').write_text(
                    'import sys\nfrom pathlib import Path\n'
                    'assert Path("generated").exists()\n'
                    'print("validation fixture")\n'
                    f'sys.exit({validation_exit})\n', encoding='utf-8')
                env = dict(os.environ, EU5_PYTHON=sys.executable)
                if selection == 'active_eu5':
                    env.pop('EU5_PYTHON')
                    env['CONDA_PREFIX'] = str(Path(sys.executable).parent)
                result = subprocess.run(
                    ['cmd', '/d', '/c', 'build.bat', '--validate-only'], cwd=root,
                    env=env, capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, int(validation_exit != 0), result.stdout + result.stderr)
                self.assertIn(sys.executable, result.stdout)
                self.assertIn('validation fixture', result.stdout)
                self.assertNotIn('Ensuring UTF-8 BOM', result.stdout)
                self.assertNotIn('Mirroring', result.stdout)
                self.assertIn('validation fixture', (root / 'tmp/build_validate.log').read_text(encoding='utf-8'))


class ContextSensitivePatternTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = {entry['id']: entry for entry in validate.load_anti_patterns(validate.REPO_ROOT)}

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.base = self.root / 'base'
        for database, text in (
            ('goods', 'clay = { color = goods_clay }'),
            ('international_organizations', 'hre = { unique = yes }'),
        ):
            source = self.base / 'reference_game_files/game/in_game/common' / database / 'base.txt'
            source.parent.mkdir(parents=True)
            source.write_text(text, encoding='utf-8')
        for name, value in (('REPO_ROOT', self.root), ('BASE_ROOT', self.base)):
            patcher = patch.object(validate, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        validate.issues.clear()
        self.addCleanup(validate.issues.clear)
        self.addCleanup(validate.reference_objects.cache_clear)

    def check(self, rule, content, relative='in_game/common/scripted_effects/test.txt'):
        validate.issues.clear()
        path = self.root / 'src/stable' / relative
        validate.check_anti_patterns(path, content, [self.patterns[rule]])
        return list(validate.issues)

    def test_change_variable_checks_direct_fields_at_any_line(self):
        rule = 'change_variable_uses_value_key'
        for content in (
            'change_variable = { name = X value = 1 }',
            'effect = { change_variable = {\nname = X\nvalue = { value = 1 }\n} }',
            'change_variable = { add = { value = 2 } name = X value = 1 }',
        ):
            with self.subTest(content=content):
                self.assertEqual(len(self.check(rule, content)), 1)
        for operation in ('add', 'subtract', 'multiply', 'divide', 'min', 'max', 'modulo'):
            content = f'change_variable = {{ name = X {operation} = {{ value = var:Y multiply = 2 }} }}'
            with self.subTest(operation=operation):
                self.assertEqual(self.check(rule, content), [])

    def test_comments_and_quoted_script_examples_are_not_effects(self):
        content = '# change_variable = { name = X value = 1 }\ntext = "change_variable = { value = 2 }"'
        self.assertEqual(self.check('change_variable_uses_value_key', content), [])

    def test_comment_mask_preserves_hash_in_strings_and_source_lines(self):
        rule = 'gui_action_button_ui_action_enabled_out_of_context'
        relative = 'in_game/gui/test.gui'
        content = '# enabled = "[UIAction.IsEnabled]"\ntext = "#R Red#!" # "quoted comment"\nenabled = "[UIAction.IsEnabled]"'
        issues = self.check(rule, content, relative)
        self.assertEqual(len(issues), 1)
        self.assertIn(':3 --', issues[0])
        masked = validate.strip_script_comments(content)
        self.assertIn('"#R Red#!"', masked)
        self.assertEqual(len(masked), len(content))
        self.assertEqual(masked.count('\n'), content.count('\n'))

    def test_goods_overrides_keep_their_color_but_new_goods_cannot_reuse_it(self):
        rule = 'custom_goods_reuses_vanilla_goods_color'
        relative = 'in_game/common/goods/compat.txt'
        for prefix in ('', 'REPLACE:', 'INJECT:', 'TRY_INJECT:'):
            with self.subTest(prefix=prefix):
                self.assertEqual(self.check(rule, f'{prefix}clay = {{ color = goods_clay }}', relative), [])
                self.assertEqual(len(self.check(rule, f'{prefix}new_good = {{ color = goods_clay }}', relative)), 1)
        self.assertEqual(self.check(rule, 'new_good = { color = goods_new_good }', relative), [])

    def test_generic_io_getter_requires_evidence_of_a_missing_custom_asset(self):
        rule = 'mod_io_geticon_without_matching_texture'
        relative = 'in_game/gui/location_window.gui'
        content = 'icon = { texture = "[InternationalOrganization.GetIcon]" }'
        self.assertEqual(self.check(rule, content, relative), [])
        source = self.root / 'src/stable/in_game/common/international_organizations/types.txt'
        source.parent.mkdir(parents=True)
        source.write_text('REPLACE:hre = { unique = yes }', encoding='utf-8')
        self.assertEqual(self.check(rule, content, relative), [])
        source.write_text('new_league = { unique = yes }', encoding='utf-8')
        self.assertEqual(len(self.check(rule, content, relative)), 1)
        self.assertIn('new_league', validate.issues[0])
        # A declared local dependency can supply the icon asset.
        for target, data in (
            ('stable', {'id': 'main', 'relationships': [{'rel_type': 'dependency', 'id': 'icons'}]}),
            ('icon_pack', {'id': 'icons', 'relationships': []}),
        ):
            metadata = self.root / 'src' / target / '.metadata/metadata.json'
            metadata.parent.mkdir(parents=True)
            metadata.write_text(json.dumps(data), encoding='utf-8')
        icon = self.root / 'src/icon_pack/main_menu/gfx/interface/icons/international_organizations/new_league.dds'
        icon.parent.mkdir(parents=True)
        icon.write_bytes(b'fixture')
        self.assertEqual(self.check(rule, content, relative), [])


class ValidationExitTests(unittest.TestCase):
    def run_validator(self, content, *, staged=True, ai_report=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'src/stable/in_game/common/scripted_effects/generated.txt'
            source.parent.mkdir(parents=True)
            source.write_text(content, encoding='utf-8')
            patterns = [{'id': 'sample', 'pattern': 'invalid_instruction',
                         'category': 'syntax', 'bad': 'invalid instruction',
                         'correction': 'use the valid instruction'}]
            staged_name = str(source.relative_to(root)).replace('\\', '/') if staged else ''
            result = subprocess.CompletedProcess(['git'], 0, staged_name, '')
            arguments = ['validate.py', '--changed'] + (['--ai-report'] if ai_report else [])
            out = io.StringIO()
            validate.issues.clear()
            try:
                with patch.object(validate, 'REPO_ROOT', root), \
                     patch.object(validate, 'get_changed_files', return_value=[source]), \
                     patch.object(validate, 'load_anti_patterns', return_value=patterns), \
                     patch.object(validate, 'load_valid_enums', return_value={}), \
                     patch.object(validate, 'load_modifier_whitelist', return_value=set()), \
                     patch.object(validate.subprocess, 'run', return_value=result), \
                     patch.object(sys, 'argv', arguments), \
                     contextlib.redirect_stdout(out):
                    with self.assertRaises(SystemExit) as exited:
                        validate.main()
                return exited.exception.code, out.getvalue()
            finally:
                validate.issues.clear()

    def test_generated_output_warning_does_not_block_either_mode(self):
        content = '# @AUTOGENERATED by sample_generator.py\nvalid_effect = { value = 1 }\n'
        code, text = self.run_validator(content)
        self.assertEqual(code, 0)
        self.assertIn('[WARN] [AUTOGEN]', text)
        self.assertIn('[OK]', text)
        code, text = self.run_validator(content, ai_report=True)
        result = json.loads(text)
        self.assertEqual(code, 0)
        self.assertTrue(result['pass'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['warnings']), 1)

    def test_real_error_still_blocks_both_modes_with_warning_present(self):
        content = '# @AUTOGENERATED by sample_generator.py\ninvalid_instruction = yes\n'
        for ai_report in (False, True):
            with self.subTest(ai_report=ai_report):
                code, text = self.run_validator(content, ai_report=ai_report)
                self.assertEqual(code, 1)
                if ai_report:
                    result = json.loads(text)
                    self.assertFalse(result['pass'])
                    self.assertEqual(len(result['errors']), 1)
                    self.assertEqual(len(result['warnings']), 1)
                else:
                    self.assertIn('[FAIL] 1 error(s)', text)
                    self.assertIn('[SYNTAX]', text)

    def test_clean_unstaged_source_has_no_warning(self):
        code, text = self.run_validator('valid_effect = { value = 1 }\n', staged=False)
        self.assertEqual(code, 0)
        self.assertNotIn('[WARN]', text)

    def test_generic_action_slot_rule_preserves_native_resolution_vote(self):
        patterns = [entry for entry in validate.load_anti_patterns(validate.REPO_ROOT)
                    if entry['id'] == 'select_trigger_custom_target_flag']
        self.assertEqual(len(patterns), 1)
        cases = (
            ('resolutions/native.txt', 'recipient', False),
            ('resolutions/native.txt', 'vote', False),
            ('generic_actions/selection.txt', 'target_1', False),
            ('generic_actions/selection.txt', 'selected_artist', True),
        )
        try:
            for relative, flag, expected_error in cases:
                with self.subTest(relative=relative, flag=flag):
                    validate.issues.clear()
                    path = validate.REPO_ROOT / 'src/stable/in_game/common' / relative
                    validate.check_anti_patterns(path, f'target_flag = {flag}', patterns)
                    self.assertEqual(bool(validate.issues), expected_error)
        finally:
            validate.issues.clear()


if __name__ == '__main__':
    unittest.main()
