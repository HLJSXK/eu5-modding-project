"""Run the shared offline suite plus SOL launcher integration checks."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / ".eu5-base/scripts"
LAUNCHER = ROOT / "scripts/update_workshop_tags.py"


class LauncherTests(unittest.TestCase):
    def run_tool(self, cwd, *args):
        return subprocess.run(
            [sys.executable, "-B", str(LAUNCHER), "--item-id", "1234567890", *args],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=20)

    def test_default_metadata_does_not_depend_on_current_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_tool(folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(ROOT / "src/stable/.metadata/metadata.json"), result.stdout)
        self.assertIn("Offline preview only", result.stdout)

    def test_explicit_metadata_is_forwarded_in_both_forms(self):
        with tempfile.TemporaryDirectory() as folder:
            metadata = Path(folder) / "custom.json"
            metadata.write_text(json.dumps({"game_id": "eu5", "tags": ["Gameplay"]}), encoding="utf-8")
            for arguments in (("--metadata", "custom.json"), ("--metadata=custom.json",)):
                with self.subTest(arguments=arguments):
                    result = self.run_tool(folder, *arguments)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(str(metadata), result.stdout)
                    self.assertIn("Desired tags: Gameplay", result.stdout)


if __name__ == "__main__":
    suite = SHARED / "test_update_workshop_tags.py"
    if not suite.is_file():
        raise SystemExit("Shared Workshop tag tests missing; bootstrap/update .eu5-base first.")
    result = subprocess.run([sys.executable, "-B", str(suite)], check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    unittest.main()
