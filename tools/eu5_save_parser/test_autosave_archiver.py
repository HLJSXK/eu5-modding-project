"""Shared autosave regressions plus workspace compatibility checks."""
from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "tools/eu5_save_parser/autosave_archiver.py"
SHARED = ROOT / ".eu5-base/scripts"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.saves = self.folder / "save games"
        self.saves.mkdir()
        (self.saves / "autosave.eu5").write_text(
            'SAV0300abcdef\nmetadata={\n date=1340.1.1\n playthrough_id="test-game"\n}\n',
            encoding="utf-8")

    def run_tool(self, *args):
        result = subprocess.run(
            [sys.executable, "-B", str(LAUNCHER), "--save-dir", str(self.saves),
             "--once", "--min-free-gb", "0", *args],
            cwd=self.folder, capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_imported_api_comes_from_shared_implementation(self):
        from . import autosave_archiver as launcher
        for symbol in (launcher.Archiver, launcher.SaveInfo, launcher.read_save_info):
            self.assertEqual(Path(inspect.getfile(symbol)).resolve(),
                             (SHARED / "autosave_archiver.py").resolve())

    def test_project_default_is_independent_of_current_directory(self):
        result = self.run_tool("--dry-run")
        self.assertIn(str(ROOT / "data/saves/observer_archive"), result.stdout)
        self.assertFalse((self.folder / "data").exists())

    def test_explicit_output_is_forwarded_in_both_forms(self):
        for args in (("--out", "custom archive"), ("--out=custom archive",)):
            with self.subTest(args=args):
                self.run_tool(*args)
                state = json.loads((self.folder / "custom archive/archive_state.json").read_text(encoding="utf-8"))
                self.assertEqual(len(state["playthroughs"]["test-game"]["buckets"]), 1)

    def test_explicit_workspace_is_forwarded(self):
        workspace = self.folder / "another workspace"
        self.run_tool("--workspace", str(workspace))
        self.assertTrue((workspace / "data/saves/observer_archive/archive_state.json").is_file())

    def test_missing_base_has_repair_message(self):
        isolated = self.folder / "tools/eu5_save_parser/autosave_archiver.py"
        isolated.parent.mkdir(parents=True)
        isolated.write_bytes(LAUNCHER.read_bytes())
        result = subprocess.run([sys.executable, "-B", str(isolated), "--help"],
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scripts/bootstrap_base.py", result.stderr)


def load_tests(loader, tests, pattern):
    suite_path = SHARED / "test_autosave_archiver.py"
    spec = importlib.util.spec_from_file_location("_eu5_shared_autosave_tests", suite_path)
    shared_tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared_tests)
    tests.addTests(loader.loadTestsFromModule(shared_tests))
    return tests


if __name__ == "__main__":
    unittest.main()
