"""Tests for the per-stratum SOL demand analysis."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from . import demand_analysis as demand
from .demand_analysis import (
    APPROXIMATION_STRATEGIES,
    ClassificationParameters,
    CountryInput,
    LocationInput,
    Solution,
    analyze_country,
    choose_accepted_approximation,
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

    def test_negative_exact_factors_have_nonnegative_approximation(self) -> None:
        matrix = [
            [1.0, 1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        target = (1.0, 2.0, 1.0, 2.0)
        raw = (1.0, 1.0, 1.0, 1.0)

        exact = solve_direct_exact(matrix, target, raw, (1, 1, 1, 1))
        self.assertEqual(exact.status, "negative_factor")
        approximate = solve_total_constrained_nonnegative(
            matrix, target, raw, strategy="balanced_l2"
        )
        self.assertEqual(approximate.status, "feasible")
        assert approximate.factors is not None
        self.assertTrue(all(factor >= -1e-5 for factor in approximate.factors))
        self.assertAlmostEqual(approximate.total_error or 0.0, 0.0, places=7)

    def test_each_hard_total_strategy_preserves_total(self) -> None:
        matrix = [
            [1.0, 0.2, 0.0, 0.0],
            [0.0, 0.8, 0.2, 0.0],
            [0.0, 0.0, 0.8, 0.2],
            [0.0, 0.0, 0.0, 0.8],
        ]
        target = (2.0, 1.5, 1.0, 0.5)
        raw = (1.0, 1.0, 1.0, 1.0)
        target_total = sum(target)

        for strategy in APPROXIMATION_STRATEGIES:
            with self.subTest(strategy=strategy):
                solution = solve_total_constrained_nonnegative(
                    matrix, target, raw, strategy=strategy
                )
                self.assertEqual(solution.status, "feasible")
                self.assertAlmostEqual(
                    sum(solution.prediction or ()), target_total, places=6
                )
                self.assertAlmostEqual(
                    solution.total_error or 0.0, 0.0, places=6
                )

    def test_missing_class_attempts_approximation_before_gate_fallback(self) -> None:
        country = CountryInput(
            owner_id="MISS",
            owner_tag="MIS",
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

        row, _ = analyze_country(
            country,
            [location],
            ClassificationParameters(),
            use_saved_classes=True,
        )

        self.assertEqual(row["exact_status"], "missing_class")
        self.assertEqual(row["approx_strategy"], "raw_fallback")
        self.assertFalse(row["approx_accepted"])
        self.assertGreater(
            sum(
                row[f"candidate_{strategy}_status"] == "feasible"
                for strategy in APPROXIMATION_STRATEGIES
            ),
            0,
        )

    def test_any_worsened_stratum_rejects_the_whole_gate(self) -> None:
        matrix = [
            [1.0, 0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
        ]
        target = (3.0, 1.0, 3.0, 1.0)
        raw = (2.4, 3.0, 2.4, 3.0)

        selected, candidates = choose_accepted_approximation(
            matrix, target, raw
        )

        self.assertEqual(selected.strategy, "raw_fallback")
        self.assertTrue(any(candidate.average_abs_improvement > 0 for candidate in candidates.values()))
        self.assertTrue(any(not candidate.gate_passed for candidate in candidates.values()))
        self.assertTrue(
            any(
                candidate.prediction
                and abs(candidate.prediction[0] - target[0])
                > abs(raw[0] - target[0])
                for candidate in candidates.values()
            )
        )

    def test_strategy_selection_uses_ratio_absolute_objective_then_order(self) -> None:
        def run_case(metrics: dict[str, tuple[float, float, float]]) -> str:
            solutions = {
                strategy: Solution(status="feasible", strategy=strategy)
                for strategy in APPROXIMATION_STRATEGIES
            }

            def assess(solution: Solution, *_args: object, **_kwargs: object) -> Solution:
                ratio, absolute, objective = metrics[solution.strategy]
                return Solution(
                    status="feasible",
                    strategy=solution.strategy,
                    gate_passed=True,
                    average_improvement_ratio=ratio,
                    average_abs_improvement=absolute,
                    selection_objective=objective,
                )

            with patch.object(
                demand,
                "solve_total_constrained_nonnegative",
                side_effect=solutions.values(),
            ), patch.object(demand, "_assess_candidate", side_effect=assess):
                selected, _ = choose_accepted_approximation(
                    [[1.0, 0.0, 0.0, 0.0]] * 4,
                    (1.0, 1.0, 1.0, 1.0),
                    (2.0, 2.0, 2.0, 2.0),
                )
            return selected.strategy

        self.assertEqual(
            run_case({
                "balanced_l2": (0.5, 0.5, 0.1),
                "improvement_l2": (0.8, 0.1, 1.0),
                "target_l2": (0.7, 0.9, 0.1),
                "absolute_l2": (0.6, 0.9, 0.1),
                "minimax_ratio": (0.7, 0.8, 0.1),
            }),
            "improvement_l2",
        )
        self.assertEqual(
            run_case({
                "balanced_l2": (0.5, 0.5, 0.1),
                "improvement_l2": (0.7, 0.5, 1.0),
                "target_l2": (0.7, 0.8, 2.0),
                "absolute_l2": (0.7, 0.6, 0.1),
                "minimax_ratio": (0.7, 0.8, 0.2),
            }),
            "minimax_ratio",
        )
        self.assertEqual(
            run_case({
                "balanced_l2": (0.7, 0.8, 0.4),
                "improvement_l2": (0.7, 0.8, 0.3),
                "target_l2": (0.7, 0.8, 0.2),
                "absolute_l2": (0.7, 0.8, 0.1),
                "minimax_ratio": (0.7, 0.8, 0.5),
            }),
            "absolute_l2",
        )
        self.assertEqual(
            run_case({strategy: (0.7, 0.8, 0.1) for strategy in APPROXIMATION_STRATEGIES}),
            "balanced_l2",
        )

    def test_minimax_candidate_respects_max_normalized_residual(self) -> None:
        matrix = [
            [1.0, 1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        target = (1.0, 2.0, 1.0, 2.0)
        raw = (1.0, 1.0, 1.0, 1.0)
        solution = solve_total_constrained_nonnegative(
            matrix, target, raw, strategy="minimax_ratio"
        )

        self.assertEqual(solution.status, "feasible")
        assert solution.prediction is not None
        scales = [max(abs(raw[i] - target[i]), 0.00001) for i in range(4)]
        max_error = max(
            abs(solution.prediction[i] - target[i]) / scales[i]
            for i in range(4)
        )
        self.assertLessEqual(max_error, (solution.selection_objective or 0.0) + 1e-7)

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
