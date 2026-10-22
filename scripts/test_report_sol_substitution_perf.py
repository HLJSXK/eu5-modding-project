"""Verify country-only save parsing and defensible counter comparisons."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from report_sol_substitution_perf import (
    CONTROL, PREFIX, STRATEGY, SaveFormatError, Snapshot, compare, core_goods,
    make_report, read_snapshot, summarize,
)


def save_text(countries: dict[int, tuple[str, dict[str, float]]], date="1400.1.1", *, crlf=False) -> str:
    lines = ["SAV02000000000000000000000000000", "metadata={", f"\tdate={date}",
             "\tplaythrough_id=sample", "}", "countries={", "\ttags={"]
    lines.extend(f"\t\t{cid}={tag}" for cid, (tag, _) in countries.items())
    lines.extend(["\t}", "\tdatabase={"])
    for cid, (tag, values) in countries.items():
        lines.extend([f"{cid}={{", f'\tcountry_name="{tag}"', "\tvariables={", "\t\tdata={ {"])
        for name, value in values.items():
            lines.extend([f"\t\t\t\tflag={name}", "\t\t\t\tdata={", "\t\t\t\t\ttype=value"])
            identity = round(value * 100_000) % (1 << 64)
            if identity:  # Engine omits the identity for zero values.
                lines.append(f"\t\t\t\t\tidentity={identity}")
            lines.extend(["\t\t\t\t}", "\t\t\t} {"])
        lines.extend(["\t\t} }", "\t}", "}"])
    lines.extend(["\t}", "}", "population={", "\tdatabase={", "999={", "\tinvalid=record", "}", "\t}", "}"])
    return ("\r\n" if crlf else "\n").join(lines) + ("\r\n" if crlf else "\n")


def variables(refresh=None, dirty=None, **extra):
    result = {PREFIX + key: value for key, value in extra.items()}
    if refresh is not None:
        result[PREFIX + "refresh_count"] = refresh
    if dirty is not None:
        result[PREFIX + "dirty_count"] = dirty
    return result


class PerfSaveReportTests(unittest.TestCase):
    def test_country_only_parse_signed_and_omitted_identity_with_crlf(self):
        values = variables(2, 0, dirty_reason=7, cached_own=-0.03125, actual_own=-0.03124)
        values[STRATEGY] = 8
        values[CONTROL] = 1
        values["unrelated_private_variable"] = 123
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "snapshot.eu5"
            path.write_bytes(save_text({1: ("AAA", values), 2: ("BBB", {})}, crlf=True).encode())
            parsed = read_snapshot(path)
        self.assertEqual(parsed.variables[1][PREFIX + "cached_own"], -0.03125)
        self.assertEqual(parsed.variables[1][PREFIX + "dirty_count"], 0)
        self.assertEqual(parsed.variables[1][STRATEGY], 8)
        self.assertEqual(parsed.variables[1][CONTROL], 1)
        self.assertNotIn("unrelated_private_variable", parsed.variables[1])
        self.assertEqual(parsed.variables[2], {})
        self.assertEqual(parsed.label, "snapshot.eu5")

    def test_old_save_has_unknown_totals_not_zero(self):
        old = Snapshot("old.eu5", "1400.1.1", None, {1: "AAA"}, {1: {STRATEGY: 8}})
        result = summarize(old)
        self.assertIsNone(result["refresh_count_total"])
        self.assertIsNone(result["dirty_count_total"])
        self.assertEqual(result["counter_covered_countries"], 0)
        self.assertIn("没有本轮诊断变量", result["warning"])

    def test_diff_excludes_reset_new_removed_and_cleared_countries(self):
        tags = {cid: f"T{cid}" for cid in range(1, 8)}
        before = Snapshot("before", "1400.1.1", None, tags, {
            1: variables(4), 2: variables(8, 5), 3: variables(4, 1),
            4: variables(1), 5: {}, 7: variables(2),
        })
        good_index = core_goods().index("cloth") + 1
        after = Snapshot("after", "1400.2.1", None, tags, {
            1: variables(6, 2, dirty_reason=7, dirty_good=good_index, cached_own=-.03125, actual_own=-.03124),
            2: variables(1), 3: {}, 5: variables(1), 6: variables(3), 7: variables(2),
        })
        diff = compare(before, after, core_goods())
        self.assertEqual(diff["refresh_delta_total"], 2)
        self.assertEqual(diff["dirty_delta_total"], 2)
        self.assertEqual(diff["comparable_countries"], 2)
        self.assertEqual(diff["status_countries"]["counter_reset"], 1)
        self.assertEqual(diff["status_countries"]["diagnostics_cleared"], 1)
        self.assertEqual(diff["status_countries"]["new_diagnostics"], 1)
        self.assertEqual(diff["status_countries"]["new_country"], 1)
        self.assertEqual(diff["status_countries"]["removed_country"], 1)
        self.assertEqual(diff["top20_refresh_countries"][0]["good"], "cloth")
        self.assertEqual(diff["top20_refresh_countries"][0]["dirty_reason"], 7)
        self.assertTrue(all(row["refresh_delta"] is None for row in diff["noncomparable_countries"]))

    def test_current_strategy_share_includes_uninstrumented_country(self):
        snapshot = Snapshot("one", None, None, {}, {
            1: {STRATEGY: 8}, 2: {STRATEGY: 7}, 3: {},
        })
        strategy = summarize(snapshot)["strategy_cache"]
        self.assertEqual(strategy["strategy8_share_of_known"], .5)
        self.assertEqual(strategy["missing_countries"], 1)

    def test_controller_parse_and_separate_player_ai_unknown_deltas(self):
        tags = {1: "AAA", 2: "BBB", 3: "CCC"}
        before_values = {cid: variables(2) for cid in tags}
        after_values = {
            1: {**variables(3), CONTROL: 1},
            2: {**variables(4, 2), CONTROL: 0},
            3: variables(5, 1),
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "controlled.eu5"
            path.write_bytes(save_text({cid: (tags[cid], values) for cid, values in after_values.items()}).encode())
            parsed = read_snapshot(path)
        # An omitted zero identity is still a recorded AI controller, whereas
        # a missing field must stay unknown instead of silently becoming AI.
        self.assertEqual(parsed.variables[2][CONTROL], 0)
        before = Snapshot("before", None, None, tags, before_values)
        diff = compare(before, parsed, core_goods())
        self.assertEqual(diff["delta_by_control"]["human"],
                         {"comparable_countries": 1, "refresh_delta_total": 1, "dirty_delta_total": 0})
        self.assertEqual(diff["delta_by_control"]["AI"],
                         {"comparable_countries": 1, "refresh_delta_total": 2, "dirty_delta_total": 2})
        self.assertEqual(diff["delta_by_control"]["unknown"],
                         {"comparable_countries": 1, "refresh_delta_total": 3, "dirty_delta_total": 1})
        self.assertEqual({row["id"]: row["control"] for row in diff["top20_refresh_countries"]},
                         {1: "human", 2: "AI", 3: "unknown"})

    def test_no_comparable_counters_cannot_claim_zero_refresh(self):
        old = Snapshot("old", None, None, {1: "AAA"}, {1: {}})
        new = Snapshot("new", None, None, {1: "AAA"}, {1: variables(2)})
        result = make_report([old, new])["comparison"]
        self.assertIsNone(result["refresh_delta_total"])
        self.assertIsNotNone(result["warning"])

    def test_order_and_playthrough_validation(self):
        before = Snapshot("before", "1400.3.1", "sample", {}, {})
        after = Snapshot("after", "1400.2.1", "sample", {}, {})
        with self.assertRaisesRegex(ValueError, "顺序倒置"):
            make_report([before, after])
        after.playthrough_id = "different"
        with self.assertRaisesRegex(ValueError, "不同 playthrough"):
            make_report([before, after])

    def test_binary_save_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "binary.eu5"
            path.write_bytes(b"PK\x03\x04compressed")
            with self.assertRaises(SaveFormatError):
                read_snapshot(path)


if __name__ == "__main__":
    unittest.main()
