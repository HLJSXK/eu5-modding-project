"""Tests for the per-stratum SOL demand analysis."""

from __future__ import annotations

import unittest

from .demand_analysis import (
    ClassificationParameters,
    CountryInput,
    LocationInput,
    analyze_country,
    solve_direct_exact,
    solve_total_constrained_nonnegative,
)


class DemandAnalysisTests(unittest.TestCase):
    def test_exact_diagonal_system(self) -> None:
        matrix = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        target = (2.0, 3.0, 4.0, 5.0)
        raw = (1.0, 1.0, 1.0, 1.0)

        direct = solve_direct_exact(matrix, target, raw, (1, 1, 1, 1))
        approximate = solve_total_constrained_nonnegative(
            matrix, target, raw
        )

        self.assertTrue(direct.exact)
        self.assertEqual(direct.status, "feasible")
        self.assertEqual(direct.factors, target)
        self.assertTrue(approximate.exact)
        assert approximate.factors is not None
        for actual, expected in zip(approximate.factors, target):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(approximate.total_error or 0.0, 0.0)

        minimax = solve_total_constrained_nonnegative(
            matrix,
            target,
            raw,
            strategy="minimax_ratio",
        )
        self.assertTrue(minimax.exact)
        self.assertEqual(minimax.factors, target)

    def test_strata_report_improvement_and_worsening_separately(self) -> None:
        country = CountryInput(
            owner_id="1",
            owner_tag="TST",
            location_count=1,
            baseline=(1.0, 1.0, 0.0, 0.0),
            target=(2.0, 1.0, 0.0, 0.0),
            pressure=(0.0, 0.0, 0.0, 0.0),
            baseline_total=2.0,
        )
        location = LocationInput(
            id=1,
            capacity=2.0,
            confidence=1.0,
            scores=(1.0, 0.0, 0.0, 0.0),
            spending=(1.0, 1.0, 0.0, 0.0),
            saved_class=0,
        )

        country_row, rows = analyze_country(
            country,
            [location],
            ClassificationParameters(),
            use_saved_classes=True,
        )

        self.assertEqual(country_row["exact_status"], "missing_class")
        self.assertEqual(country_row["approx_status"], "gate_rejected")
        self.assertFalse(country_row["approx_accepted"])
        self.assertEqual(country_row["approx_improved_strata"], 0)
        self.assertEqual(country_row["approx_worsened_strata"], 0)
        self.assertEqual(country_row["approx_unchanged_strata"], 4)
        self.assertFalse(country_row["approx_pareto_improves_raw"])
        by_stratum = {row["stratum"]: row for row in rows}
        self.assertEqual(
            by_stratum["nobles"]["approx_direction"], "unchanged"
        )
        self.assertEqual(
            by_stratum["clergy"]["approx_direction"], "unchanged"
        )
        self.assertAlmostEqual(
            float(by_stratum["nobles"]["approx_spending"]), 1.0
        )
        self.assertAlmostEqual(
            float(by_stratum["clergy"]["approx_spending"]), 1.0
        )
        self.assertAlmostEqual(float(country_row["approx_total_error"]), -1.0)

        diagnostic_row, diagnostic_rows = analyze_country(
            country,
            [location],
            ClassificationParameters(),
            use_saved_classes=True,
            enforce_approximation_gate=False,
        )
        self.assertTrue(diagnostic_row["approx_accepted"])
        self.assertFalse(diagnostic_row["approx_gate_passed"])
        self.assertEqual(diagnostic_row["approx_worsening_strata"], 1)
        self.assertEqual(
            diagnostic_row["approx_max_worsening_percentage"], float("inf")
        )
        diagnostic_by_stratum = {
            row["stratum"]: row for row in diagnostic_rows
        }
        self.assertEqual(
            diagnostic_by_stratum["clergy"]["approx_direction"],
            "worsened",
        )

    def test_only_all_strata_improvement_is_accepted(self) -> None:
        country = CountryInput(
            owner_id="2",
            owner_tag="ALL",
            location_count=4,
            baseline=(1.0, 1.0, 1.0, 1.0),
            target=(2.0, 2.0, 2.0, 2.0),
            pressure=(0.0, 0.0, 0.0, 0.0),
            baseline_total=4.0,
        )
        locations = [
            LocationInput(
                id=index,
                capacity=1.0,
                confidence=1.0,
                scores=(1.0, 0.0, 0.0, 0.0),
                spending=tuple(
                    1.0 if row == index else 0.0 for row in range(4)
                ),
                saved_class=index,
            )
            for index in range(4)
        ]

        country_row, rows = analyze_country(
            country,
            locations,
            ClassificationParameters(),
            use_saved_classes=True,
        )

        self.assertTrue(country_row["approx_accepted"])
        self.assertEqual(country_row["approx_improved_strata"], 4)
        self.assertEqual(country_row["approx_worsened_strata"], 0)
        self.assertEqual(country_row["approx_strategy"], "balanced_l2")
        self.assertAlmostEqual(
            float(country_row["approx_average_improvement_ratio"]), 1.0
        )
        self.assertTrue(
            all(row["approx_direction"] == "improved" for row in rows)
        )


if __name__ == "__main__":
    unittest.main()
