"""OOS evidence integrity, trace comparison and non-mutating generation checks."""
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sol_oos import ROOT, build, compare, file_manifest, parse_trace, read_report
from sol_oos_trace_source import BOUNDARIES, instrument, render_effects
from gen_sol_economy_effects import (_render_target, GENERATED_HEADER, _load_good_rows,
                                   _generate_refresh_block, render_country_demand_aggregation,
                                   render_static_sections)
from test_sol_substitution import parse


def manifest():
    return {"session": "test", "game_version": "1.4", "game_checksum": "abcd", "language": "en",
            "build_verified": True, "warnings": [], "mod_files": [{"path": "x.txt", "sha256": "a"}]}


def report(records):
    return {"manifest": manifest(), "streams": {"logs/debug.log": records}}


class TraceTests(unittest.TestCase):
    def test_generated_trace_preserves_original_statement_order_and_bodies(self):
        for target in ("stable", "sol_standalone"):
            generated, _ = _render_target(target)
            original = re.sub(r"^\tsol_oos_trace_(?:global|country) = \{ stage = \w+ \}\n", "", generated, flags=re.M)
            self.assertEqual(instrument(original), generated)
            # Independent uninstrumented rendering remains valid after commits;
            # never assume HEAD is permanently the pre-diagnostics revision.
            before = GENERATED_HEADER + render_static_sections(
                target, _generate_refresh_block(_load_good_rows()), render_country_demand_aggregation())
            self.assertEqual(original, before)
        effects = render_effects()
        for forbidden in ("set_variable", "set_global_variable", "change_variable", "random_", "cmf_log"):
            self.assertNotIn(forbidden, effects)
        self.assertEqual(effects.count("debug_log_scopes = no"), 1)
        self.assertIn("SOL_OOS;2;$stage$;GLOBAL;[GetDateString];event", effects)
        self.assertNotIn("SOL_OOS|", effects)
        self.assertNotIn(".GetTag]", effects)
        self.assertIn(".GetTagAndName]", effects)
        self.assertIn(".MakeScope.GetVariable(", effects)
        allowed = {"sol_oos_trace_country", "sol_oos_trace_global", "if", "else", "limit",
                   "sol_oos_trace_is_enabled", "is_human", "has_variable", "save_scope_as",
                   "debug_log", "debug_log_date", "debug_log_scopes"}
        def check(nodes):
            for node in nodes:
                self.assertIn(node.key, allowed)
                if isinstance(node.value, list):
                    check(node.value)
        check(parse(effects))

    def test_missing_boundary_fails_closed(self):
        with self.assertRaises(ValueError):
            instrument("not_a_known_effect = {\n}\n")

    def test_trace_default_disabled_in_both_targets(self):
        for target in ("stable", "sol_standalone"):
            text = (ROOT / "src" / target / "in_game/common/scripted_triggers/SOL_oos_trace_triggers.txt").read_text(encoding="utf-8-sig")
            self.assertIn("always = no", text)

    def test_order_and_per_subject_comparison(self):
        a = ("solve_end", "FRA", "1 January 1338", "event")
        b = ("solve_end", "ENG", "1 January 1338", "event")
        result = compare(report([a, b]), report([b, a]))
        self.assertEqual(result["streams"][0]["first_observed_difference"]["index"], 0)
        self.assertEqual(result["streams"][0]["per_subject_differences"], [])
        result = compare(report([a]), report([a, a]))
        self.assertTrue(result["streams"][0]["per_subject_differences"])

    def test_missing_trace_and_modified_files_are_not_success(self):
        a, b = report([]), report([])
        a["streams"], b["streams"] = {}, {}
        b["manifest"]["mod_files"][0]["sha256"] = "different"
        result = compare(a, b)
        self.assertTrue(result["mod_file_differences"])
        self.assertTrue(any("No trace" in f for f in result["findings"]))

    def test_unexpanded_expressions_are_reported(self):
        records = [("solve_end", "[SCOPE.sCountry('x').GetTag]", "1337", "event")]
        result = compare(report(records), report(records))
        self.assertTrue(any("Unexpanded" in f for f in result["findings"]))
        self.assertFalse(result["streams"][0]["trace_valid"])

    def test_v2_country_metrics_and_missing_values(self):
        text = "\n".join([
            "SOL_OOS;2;solve_begin;FRA France;1337年8月1日;event",
            "SOL_OOS;2;solve_begin;FRA France;1337年8月1日;sol_ls_sol=1.23456",
            "SOL_OOS;2;solve_begin;FRA France;1337年8月1日;other=MISSING",
        ])
        records, warnings = parse_trace(text)
        self.assertEqual(warnings, [])
        self.assertEqual(len(records), 3)
        self.assertEqual(records[1], ("solve_begin", "FRA France", "1337年8月1日", "sol_ls_sol=1.23456"))
        self.assertTrue(compare(report(records), report(records))["streams"][0]["trace_valid"])

    def test_runtime_broken_v1_is_recovered_without_counting_error_echoes(self):
        # Exact failure shape from the 2026-11-01 multiplayer report.
        lines = [
            "[20:36:24][jomini_effect_impl.cpp:479]: common/scripted_effects/SOL_oos_trace_effects.txt:16: SOL_OOS|1solve_begin$||1337年8月1日|event",
            "[20:36:24][jomini_effect_impl.cpp:2666]: 国家“法兰西”（FRA）",
            "[20:36:24][pdx_data_localize.cpp:192]: Data error in loc string 'SOL_OOS|1solve_begin$|[SCOPE.sCountry('sol_oos_trace_subject').GetTag]|[GetDateString]|sol_ls_sol=[bad]'",
            "[20:36:24][jomini_effect_impl.cpp:479]: common/scripted_effects/SOL_oos_trace_effects.txt:35: SOL_OOS|1solve_begin$||1337年8月1日|sol_ls_sol=ERROR:[bad|",
            "[20:36:24][jomini_effect_impl.cpp:479]: x.txt:7: SOL_OOS|1world_refresh_begin$|GLOBAL|1337年8月1日|event",
        ]
        records, warnings = parse_trace("\n".join(lines))
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0], ("solve_begin", "FRA", "1337年8月1日", "event"))
        self.assertEqual(records[1][1], "FRA")
        self.assertEqual(records[2][1], "GLOBAL")
        self.assertTrue(any("Malformed v1" in warning for warning in warnings))
        left = report(records)
        left["trace_warnings"] = {"logs/debug.log": warnings}
        result = compare(left, left)
        self.assertFalse(result["streams"][0]["trace_valid"])
        self.assertEqual(result["streams"][0]["left_stage_counts"]["solve_begin"], 1)
        self.assertFalse(any("No trace" in finding for finding in result["findings"]))

    def test_missing_country_is_not_inherited_from_a_previous_event(self):
        records, warnings = parse_trace("\n".join([
            "SOL_OOS;2;solve_begin;FRA France;1337;event",
            "SOL_OOS;2;solve_begin;;1337;event",
            "SOL_OOS;2;solve_begin;;1337;metric=0",
        ]))
        self.assertEqual([r[1] for r in records], ["FRA France", "UNKNOWN", "UNKNOWN"])
        self.assertIn("Missing country identity", warnings)

    def test_unrecognized_trace_is_reported(self):
        records, warnings = parse_trace("SOL_OOS broken record")
        self.assertEqual(records, [])
        self.assertIn("Unrecognized SOL_OOS record format", warnings)

    def test_zip_does_not_duplicate_logs_from_oos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.zip"
            line = "[12:00:00][jomini_effect_impl.cpp:479]: x.txt:7: SOL_OOS|1|gui_init_begin|GLOBAL|1337|event\n"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("collection.json", json.dumps(manifest()))
                archive.writestr("logs/debug.log", line)
                archive.writestr("oos/old/debug.log", line * 4)
                archive.writestr("../../untrusted.txt", "never extracted")
            result = read_report(path)
            self.assertEqual(len(result["streams"]["logs/debug.log"]), 1)

    def test_builder_refuses_existing_or_source_paths(self):
        for path in (ROOT, ROOT / "src" / "new-path", ROOT.parent):
            with self.assertRaises(ValueError):
                build("stable", path, True)

    def test_powershell_collects_hidden_metadata_and_oos_without_source_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mod, game, out = root / "mod", root / "game", root / "reports"
            (mod / ".metadata").mkdir(parents=True)
            (mod / ".metadata/metadata.json").write_text('{"id":"test"}')
            files = file_manifest(mod)
            (mod / "sol_oos_build.json").write_text(json.dumps({"files": files}))
            (game / "logs").mkdir(parents=True)
            log = game / "logs/debug.log"
            text = "SOL_OOS|1|gui_init_begin|GLOBAL|1337|event\n"
            log.write_text(text)
            (game / "oos/incident").mkdir(parents=True)
            (game / "oos/incident/state.txt").write_text("preserve OOS")
            command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(ROOT / "scripts/collect_sol_oos.ps1"), "-Role", "host", "-Session", "fixture",
                       "-ModPath", str(mod), "-UserDataPath", str(game), "-OutputRoot", str(out)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            archive = next(out.glob("*.zip"))
            loaded = read_report(archive)
            self.assertTrue(loaded["manifest"]["build_verified"])
            self.assertEqual(loaded["manifest"]["mod_files"][0]["path"], ".metadata/metadata.json")
            with zipfile.ZipFile(archive) as evidence:
                self.assertIn("oos/incident/state.txt", evidence.namelist())
            self.assertEqual(log.read_text(), text)
            # Hash checking detects a stale manifest on the next collection.
            (mod / "extra.txt").write_text("changed")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            newest = max(out.glob("*.zip"), key=lambda p: p.name)
            self.assertFalse(read_report(newest)["manifest"]["build_verified"])


if __name__ == "__main__":
    unittest.main()
