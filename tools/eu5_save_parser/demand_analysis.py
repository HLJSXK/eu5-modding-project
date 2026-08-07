"""Analyze SOL class compensation results by country and stratum.

The optimizer still needs a scalar objective to select one constrained
candidate, but this module deliberately does not use that scalar as its
headline result.  Every exported diagnostic compares nobles, clergy,
burghers, and lower strata separately.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


STRATA = ("nobles", "clergy", "burghers", "lower")
CLASS_LABELS = STRATA
DEFAULT_CAPACITY_FLOOR = 0.01
DEFAULT_NEGATIVE_POOL = 0.96
DEFAULT_BALANCE_WEIGHT = 0.05
DEFAULT_EPSILON = 0.00001
APPROXIMATION_STRATEGIES = (
    "balanced_l2",
    "improvement_l2",
    "target_l2",
    "absolute_l2",
    "minimax_ratio",
)
RELAXED_TOTAL_STRATEGIES = (
    "improvement_free_total",
    "improvement_soft_total_0.01",
    "improvement_soft_total_0.1",
    "improvement_soft_total_1",
)
RELAXED_TOTAL_PENALTIES = {
    "improvement_free_total": 0.0,
    "improvement_soft_total_0.01": 0.01,
    "improvement_soft_total_0.1": 0.1,
    "improvement_soft_total_1": 1.0,
}

_COUNTRY_BASELINE_COLUMNS = (
    "sol_country_baseline_spending_nobles",
    "sol_country_baseline_spending_clergy",
    "sol_country_baseline_spending_burghers",
    "sol_country_baseline_lower",
)
_COUNTRY_TARGET_COLUMNS = (
    "sol_country_demand_target_nobles",
    "sol_country_demand_target_clergy",
    "sol_country_demand_target_burghers",
    "sol_country_demand_target_lower",
)
_LOCATION_SCORE_COLUMNS = (
    "sol_location_demand_score_nobles",
    "sol_location_demand_score_clergy",
    "sol_location_demand_score_burghers",
    "sol_location_demand_score_lower",
)
_LOCATION_BASE_COLUMNS = (
    "sol_location_nobles_base_spending",
    "sol_location_clergy_base_spending",
    "sol_location_burghers_base_spending",
    "sol_location_lower_base_spending",
)


@dataclass(frozen=True, slots=True)
class ClassificationParameters:
    """Parameters mirrored from the active SOL classification strategy."""

    capacity_floor: float = DEFAULT_CAPACITY_FLOOR
    negative_pool: float = DEFAULT_NEGATIVE_POOL
    balance_weight: float = DEFAULT_BALANCE_WEIGHT

    def validate(self) -> None:
        if self.capacity_floor < 0:
            raise ValueError("capacity_floor must be nonnegative")
        if self.negative_pool < 0:
            raise ValueError("negative_pool must be nonnegative")
        if self.balance_weight < 0:
            raise ValueError("balance_weight must be nonnegative")
        allocated = 4 * self.capacity_floor + self.negative_pool
        if not math.isclose(allocated, 1.0, abs_tol=1e-9):
            raise ValueError(
                "4 * capacity_floor + negative_pool must equal 1"
            )


@dataclass(frozen=True, slots=True)
class LocationInput:
    id: int
    capacity: float
    confidence: float
    scores: tuple[float, float, float, float]
    spending: tuple[float, float, float, float]
    saved_class: int | None


@dataclass(frozen=True, slots=True)
class CountryInput:
    owner_id: str
    owner_tag: str
    location_count: int
    baseline: tuple[float, float, float, float]
    target: tuple[float, float, float, float]
    pressure: tuple[float, float, float, float]
    baseline_total: float


@dataclass(frozen=True, slots=True)
class Solution:
    status: str
    factors: tuple[float, float, float, float] | None = None
    prediction: tuple[float, float, float, float] | None = None
    active_classes: tuple[int, ...] = ()
    exact: bool = False
    total_error: float | None = None
    selection_objective: float | None = None
    strategy: str = ""
    gate_passed: bool = False
    average_improvement_ratio: float | None = None
    average_abs_improvement: float | None = None


def _number(row: Mapping[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value else 0.0


def _error_scale(raw: float, target: float, epsilon: float) -> float:
    """Use the current raw row scale, with a target fallback for zero rows."""

    if abs(raw) > epsilon:
        return abs(raw)
    if abs(target) > epsilon:
        return abs(target)
    return epsilon


def _residual_tolerance(target: float) -> float:
    """Mirror the current runtime residual tolerance."""

    return abs(target) * 0.001 + 0.01


def _solve_linear_system(
    matrix: Sequence[Sequence[float]],
    rhs: Sequence[float],
    *,
    epsilon: float = 1e-11,
) -> list[float] | None:
    """Solve a small dense system with partial pivoting."""

    size = len(rhs)
    work = [list(matrix[index]) + [rhs[index]] for index in range(size)]
    for pivot in range(size):
        swap = max(
            range(pivot, size),
            key=lambda index: abs(work[index][pivot]),
        )
        if abs(work[swap][pivot]) <= epsilon:
            return None
        work[pivot], work[swap] = work[swap], work[pivot]
        divisor = work[pivot][pivot]
        work[pivot] = [value / divisor for value in work[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = work[row][pivot]
            if factor == 0:
                continue
            work[row] = [
                work[row][column] - factor * work[pivot][column]
                for column in range(size + 1)
            ]
    return [work[index][-1] for index in range(size)]


def _solve_fixed_order_system(
    matrix: Sequence[Sequence[float]],
    rhs: Sequence[float],
    *,
    pivot_epsilon: float = 0.0001,
) -> list[float] | None:
    """Mirror the runtime solver's fixed row order and pivot threshold."""

    size = len(rhs)
    work = [list(matrix[index]) + [rhs[index]] for index in range(size)]
    for pivot in range(size):
        divisor = work[pivot][pivot]
        if abs(divisor) <= pivot_epsilon:
            return None
        for row in range(pivot + 1, size):
            factor = work[row][pivot] / divisor
            for column in range(pivot, size + 1):
                work[row][column] -= factor * work[pivot][column]
    solved = [0.0] * size
    for row in range(size - 1, -1, -1):
        divisor = work[row][row]
        if abs(divisor) <= pivot_epsilon:
            return None
        solved[row] = (
            work[row][-1]
            - sum(
                work[row][column] * solved[column]
                for column in range(row + 1, size)
            )
        ) / divisor
    return solved


def classify_locations(
    country: CountryInput,
    locations: Sequence[LocationInput],
    parameters: ClassificationParameters,
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> tuple[dict[int, int], tuple[float, ...], tuple[float, ...]]:
    """Reproduce the active confidence-ordered greedy classification."""

    parameters.validate()
    pressure_total = sum(country.pressure)
    if pressure_total > epsilon:
        targets = tuple(
            country.baseline_total * parameters.capacity_floor
            + country.baseline_total
            * parameters.negative_pool
            * pressure
            / pressure_total
            for pressure in country.pressure
        )
    else:
        targets = (country.baseline_total / 4,) * 4

    current = [0.0] * 4
    assignments: dict[int, int] = {}
    ordered = sorted(
        locations,
        key=lambda location: (location.confidence, location.id),
        reverse=True,
    )
    for location in ordered:
        candidates: list[float] = []
        for class_index in range(4):
            penalty = 0.0
            if targets[class_index] > epsilon:
                penalty = (
                    parameters.balance_weight
                    * current[class_index]
                    / targets[class_index]
                )
            candidates.append(location.scores[class_index] - penalty)
        selected = max(
            range(4), key=lambda index: (candidates[index], -index)
        )
        assignments[location.id] = selected
        current[selected] += location.capacity
    return assignments, targets, tuple(current)


def saved_assignments(
    locations: Sequence[LocationInput],
) -> dict[int, int]:
    """Read class assignments persisted in the save instead of replaying."""

    return {
        location.id: location.saved_class
        for location in locations
        if location.saved_class is not None
    }


def build_class_matrix(
    locations: Sequence[LocationInput],
    assignments: Mapping[int, int],
) -> tuple[list[list[float]], tuple[int, ...], tuple[float, ...]]:
    """Sum each location's raw-weighted four-stratum spending by class."""

    matrix = [[0.0] * 4 for _ in range(4)]
    counts = [0] * 4
    capacities = [0.0] * 4
    for location in locations:
        class_index = assignments.get(location.id)
        if class_index is None or not 0 <= class_index < 4:
            continue
        counts[class_index] += 1
        capacities[class_index] += location.capacity
        for stratum_index in range(4):
            matrix[stratum_index][class_index] += location.spending[
                stratum_index
            ]
    return matrix, tuple(counts), tuple(capacities)


def solve_direct_exact(
    matrix: Sequence[Sequence[float]],
    target: Sequence[float],
    raw: Sequence[float],
    counts: Sequence[int],
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> Solution:
    """Test the current four-class exact solve without hiding its failure."""

    if any(count <= 0 for count in counts):
        return Solution(status="missing_class")
    scales = [
        _error_scale(raw[index], target[index], epsilon)
        for index in range(4)
    ]
    normalized_matrix = [
        [matrix[row][column] / scales[row] for column in range(4)]
        for row in range(4)
    ]
    normalized_target = [target[row] / scales[row] for row in range(4)]
    factors = _solve_fixed_order_system(
        normalized_matrix, normalized_target
    )
    if factors is None:
        return Solution(status="singular")
    if any(factor < -epsilon for factor in factors):
        return Solution(
            status="negative_factor",
            factors=tuple(factors),
            active_classes=(0, 1, 2, 3),
        )
    factors = [max(0.0, factor) for factor in factors]
    prediction = tuple(
        sum(matrix[row][column] * factors[column] for column in range(4))
        for row in range(4)
    )
    exact = all(
        abs(prediction[index] - target[index])
        <= _residual_tolerance(target[index])
        for index in range(4)
    )
    return Solution(
        status="feasible" if exact else "residual_failure",
        factors=tuple(factors),
        prediction=prediction,
        active_classes=(0, 1, 2, 3),
        exact=exact,
        total_error=sum(prediction) - sum(target),
    )


def _approximation_scales(
    strategy: str,
    target: Sequence[float],
    raw: Sequence[float],
    epsilon: float,
) -> list[float]:
    """Return row scales for one approximation objective."""

    if strategy == "balanced_l2":
        return [
            _error_scale(raw[index], target[index], epsilon)
            for index in range(4)
        ]
    if strategy == "improvement_l2" or strategy == "minimax_ratio":
        return [
            max(abs(raw[index] - target[index]), epsilon)
            for index in range(4)
        ]
    if strategy == "target_l2":
        return [max(abs(target[index]), epsilon) for index in range(4)]
    if strategy == "absolute_l2":
        return [1.0] * 4
    raise ValueError(f"unknown approximation strategy: {strategy}")


def _solve_weighted_total_constrained_nonnegative(
    matrix: Sequence[Sequence[float]],
    target: Sequence[float],
    raw: Sequence[float],
    *,
    scales: Sequence[float],
    strategy: str,
    epsilon: float = DEFAULT_EPSILON,
) -> Solution:
    """Enumerate all active sets for a weighted L2 fit."""

    target_total = sum(target)
    if abs(target_total) <= epsilon:
        zero = (0.0, 0.0, 0.0, 0.0)
        return Solution(
            status="feasible",
            factors=zero,
            prediction=zero,
            exact=True,
            total_error=0.0,
            selection_objective=0.0,
        )

    columns = tuple(
        column
        for column in range(4)
        if sum(abs(matrix[row][column]) for row in range(4)) > epsilon
    )
    if not columns:
        return Solution(status="no_nonempty_class")

    normalized_matrix = [
        [matrix[row][column] / scales[row] for column in range(4)]
        for row in range(4)
    ]
    normalized_target = [target[row] / scales[row] for row in range(4)]
    best: tuple[float, float, Solution] | None = None

    for size in range(1, len(columns) + 1):
        for active in itertools.combinations(columns, size):
            gram = [
                [
                    sum(
                        normalized_matrix[row][left]
                        * normalized_matrix[row][right]
                        for row in range(4)
                    )
                    for right in active
                ]
                for left in active
            ]
            projection = [
                sum(
                    normalized_matrix[row][column]
                    * normalized_target[row]
                    for row in range(4)
                )
                for column in active
            ]
            total_coefficients = [
                sum(matrix[row][column] for row in range(4))
                / target_total
                for column in active
            ]
            kkt = [
                gram[index] + [total_coefficients[index]]
                for index in range(size)
            ]
            kkt.append(total_coefficients + [0.0])
            solved = _solve_linear_system(kkt, projection + [1.0])
            if solved is None:
                continue
            active_factors = solved[:size]
            if any(factor < -epsilon for factor in active_factors):
                continue

            factors = [0.0] * 4
            for column, factor in zip(active, active_factors):
                factors[column] = max(0.0, factor)
            prediction = tuple(
                sum(
                    matrix[row][column] * factors[column]
                    for column in range(4)
                )
                for row in range(4)
            )
            relative_errors = [
                (prediction[row] - target[row]) / scales[row]
                for row in range(4)
            ]
            objective = sum(error * error for error in relative_errors)
            exact = all(
                abs(prediction[index] - target[index])
                <= _residual_tolerance(target[index])
                for index in range(4)
            )
            solution = Solution(
                status="feasible",
                factors=tuple(factors),
                prediction=prediction,
                active_classes=active,
                exact=exact,
                total_error=sum(prediction) - target_total,
                selection_objective=objective,
                strategy=strategy,
            )
            ranking = (objective, max(factors), solution)
            if best is None or ranking[:2] < best[:2]:
                best = ranking

    return best[2] if best is not None else Solution(status="no_candidate")


def _solve_soft_total_nonnegative_l2(
    matrix: Sequence[Sequence[float]],
    target: Sequence[float],
    raw: Sequence[float],
    *,
    total_penalty: float,
    strategy: str,
    epsilon: float = DEFAULT_EPSILON,
) -> Solution:
    """Fit nonnegative factors while penalizing, rather than enforcing, total drift."""

    columns = tuple(
        column
        for column in range(4)
        if sum(abs(matrix[row][column]) for row in range(4)) > epsilon
    )
    if not columns:
        return Solution(status="no_nonempty_class", strategy=strategy)
    scales = _approximation_scales(
        "improvement_l2", target, raw, epsilon
    )
    total_target = sum(target)
    total_scale = max(abs(total_target), epsilon)
    normalized_target = [target[row] / scales[row] for row in range(4)]
    normalized_matrix = [
        [matrix[row][column] / scales[row] for column in range(4)]
        for row in range(4)
    ]
    normalized_total_columns = [
        sum(matrix[row][column] for row in range(4)) / total_scale
        for column in columns
    ]
    normalized_total_target = total_target / total_scale
    best: tuple[float, float, Solution] | None = None

    for size in range(1, len(columns) + 1):
        for active in itertools.combinations(columns, size):
            gram = [
                [
                    sum(
                        normalized_matrix[row][left]
                        * normalized_matrix[row][right]
                        for row in range(4)
                    )
                    for right in active
                ]
                for left in active
            ]
            projection = [
                sum(
                    normalized_matrix[row][column]
                    * normalized_target[row]
                    for row in range(4)
                )
                for column in active
            ]
            if total_penalty > 0:
                total_values = [
                    normalized_total_columns[columns.index(column)]
                    for column in active
                ]
                for left in range(size):
                    for right in range(size):
                        gram[left][right] += (
                            total_penalty
                            * total_values[left]
                            * total_values[right]
                        )
                    projection[left] += (
                        total_penalty
                        * total_values[left]
                        * normalized_total_target
                    )
            active_factors = _solve_linear_system(gram, projection)
            if active_factors is None or any(
                factor < -epsilon for factor in active_factors
            ):
                continue
            factors = [0.0] * 4
            for column, factor in zip(active, active_factors):
                factors[column] = max(0.0, factor)
            prediction = tuple(
                sum(
                    matrix[row][column] * factors[column]
                    for column in range(4)
                )
                for row in range(4)
            )
            relative_errors = [
                (prediction[row] - target[row]) / scales[row]
                for row in range(4)
            ]
            normalized_total_error = (
                sum(prediction) - total_target
            ) / total_scale
            objective = sum(error * error for error in relative_errors)
            objective += total_penalty * normalized_total_error**2
            exact = all(
                abs(prediction[index] - target[index])
                <= _residual_tolerance(target[index])
                for index in range(4)
            )
            solution = Solution(
                status="feasible",
                factors=tuple(factors),
                prediction=prediction,
                active_classes=active,
                exact=exact,
                total_error=sum(prediction) - total_target,
                selection_objective=objective,
                strategy=strategy,
            )
            ranking = (objective, max(factors), solution)
            if best is None or ranking[:2] < best[:2]:
                best = ranking
    return best[2] if best is not None else Solution(
        status="no_candidate", strategy=strategy
    )


def _solve_minimax_total_constrained_nonnegative(
    matrix: Sequence[Sequence[float]],
    target: Sequence[float],
    raw: Sequence[float],
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> Solution:
    """Minimize the worst normalized residual over nonnegative factors.

    The four-row problem is small enough to solve by enumerating LP vertices.
    For each active class set, the variables are its factors plus the maximum
    residual ``t``.  One total-preservation equation and every combination of
    ``k`` active residual/nonnegative boundaries are checked.
    """

    target_total = sum(target)
    if abs(target_total) <= epsilon:
        zero = (0.0, 0.0, 0.0, 0.0)
        return Solution(
            status="feasible",
            factors=zero,
            prediction=zero,
            exact=True,
            total_error=0.0,
            selection_objective=0.0,
            strategy="minimax_ratio",
        )

    columns = tuple(
        column
        for column in range(4)
        if sum(abs(matrix[row][column]) for row in range(4)) > epsilon
    )
    if not columns:
        return Solution(status="no_nonempty_class", strategy="minimax_ratio")
    scales = _approximation_scales(
        "minimax_ratio", target, raw, epsilon
    )
    best: tuple[float, float, Solution] | None = None

    for size in range(1, len(columns) + 1):
        for active in itertools.combinations(columns, size):
            class_totals = [
                sum(matrix[row][column] for row in range(4))
                for column in active
            ]
            boundaries: list[tuple[list[float], float]] = []
            for row in range(4):
                coefficients = [matrix[row][column] for column in active]
                boundaries.append(
                    (coefficients + [-scales[row]], target[row])
                )
                boundaries.append(
                    (coefficients + [scales[row]], target[row])
                )
            for factor_index in range(size):
                coefficients = [0.0] * (size + 1)
                coefficients[factor_index] = 1.0
                boundaries.append((coefficients, 0.0))

            for selected in itertools.combinations(boundaries, size):
                system = [[*class_totals, 0.0]]
                rhs = [target_total]
                for coefficients, boundary_rhs in selected:
                    system.append(coefficients)
                    rhs.append(boundary_rhs)
                solved = _solve_linear_system(system, rhs)
                if solved is None:
                    continue
                active_factors = solved[:size]
                residual_limit = solved[-1]
                if residual_limit < -epsilon:
                    continue
                if any(factor < -epsilon for factor in active_factors):
                    continue
                factors = [0.0] * 4
                for column, factor in zip(active, active_factors):
                    factors[column] = max(0.0, factor)
                prediction = tuple(
                    sum(
                        matrix[row][column] * factors[column]
                        for column in range(4)
                    )
                    for row in range(4)
                )
                normalized_errors = [
                    abs(prediction[row] - target[row]) / scales[row]
                    for row in range(4)
                ]
                if any(
                    error > residual_limit + 1e-8
                    for error in normalized_errors
                ):
                    continue
                exact = all(
                    abs(prediction[index] - target[index])
                    <= _residual_tolerance(target[index])
                    for index in range(4)
                )
                solution = Solution(
                    status="feasible",
                    factors=tuple(factors),
                    prediction=prediction,
                    active_classes=active,
                    exact=exact,
                    total_error=sum(prediction) - target_total,
                    selection_objective=max(normalized_errors),
                    strategy="minimax_ratio",
                )
                ranking = (
                    (
                        solution.selection_objective
                        if solution.selection_objective is not None
                        else math.inf
                    ),
                    sum(normalized_errors),
                    solution,
                )
                if best is None or ranking[:2] < best[:2]:
                    best = ranking
    return (
        best[2]
        if best is not None
        else Solution(status="no_candidate", strategy="minimax_ratio")
    )


def solve_total_constrained_nonnegative(
    matrix: Sequence[Sequence[float]],
    target: Sequence[float],
    raw: Sequence[float],
    *,
    strategy: str = "balanced_l2",
    epsilon: float = DEFAULT_EPSILON,
) -> Solution:
    """Solve one named nonnegative approximation strategy."""

    if strategy in RELAXED_TOTAL_PENALTIES:
        return _solve_soft_total_nonnegative_l2(
            matrix,
            target,
            raw,
            total_penalty=RELAXED_TOTAL_PENALTIES[strategy],
            strategy=strategy,
            epsilon=epsilon,
        )
    if strategy == "minimax_ratio":
        return _solve_minimax_total_constrained_nonnegative(
            matrix, target, raw, epsilon=epsilon
        )
    scales = _approximation_scales(strategy, target, raw, epsilon)
    return _solve_weighted_total_constrained_nonnegative(
        matrix,
        target,
        raw,
        scales=scales,
        strategy=strategy,
        epsilon=epsilon,
    )


def _assess_candidate(
    solution: Solution,
    target: Sequence[float],
    raw: Sequence[float],
    *,
    epsilon: float,
) -> Solution:
    """Apply the hard four-stratum improvement gate to a candidate."""

    if solution.prediction is None:
        return solution
    improvements = [
        abs(raw[index] - target[index])
        - abs(solution.prediction[index] - target[index])
        for index in range(4)
    ]
    tolerances = [
        max(epsilon, abs(raw[index] - target[index]) * 1e-9)
        for index in range(4)
    ]
    gate_passed = all(
        improvement > tolerance
        for improvement, tolerance in zip(improvements, tolerances)
    )
    ratios = []
    for index in range(4):
        raw_error = abs(raw[index] - target[index])
        scale = (
            raw_error
            if raw_error > epsilon
            else _error_scale(raw[index], target[index], epsilon)
        )
        ratios.append(improvements[index] / scale)
    return replace(
        solution,
        gate_passed=gate_passed
        and all(abs(raw[index] - target[index]) > epsilon for index in range(4)),
        average_improvement_ratio=sum(ratios) / 4,
        average_abs_improvement=sum(improvements) / 4,
    )


def choose_accepted_approximation(
    matrix: Sequence[Sequence[float]],
    target: Sequence[float],
    raw: Sequence[float],
    *,
    enforce_gate: bool = True,
    epsilon: float = DEFAULT_EPSILON,
) -> tuple[Solution, dict[str, Solution]]:
    """Try all strategies and optionally enforce the four-stratum gate."""

    candidates = {
        strategy: _assess_candidate(
            solve_total_constrained_nonnegative(
                matrix,
                target,
                raw,
                strategy=strategy,
                epsilon=epsilon,
            ),
            target,
            raw,
            epsilon=epsilon,
        )
        for strategy in APPROXIMATION_STRATEGIES
    }
    accepted = [
        solution
        for solution in candidates.values()
        if solution.gate_passed or not enforce_gate
    ]
    if accepted:
        selected = max(
            accepted,
            key=lambda solution: (
                round(
                    solution.average_improvement_ratio
                    if solution.average_improvement_ratio is not None
                    else -math.inf,
                    12,
                ),
                round(
                    solution.average_abs_improvement
                    if solution.average_abs_improvement is not None
                    else -math.inf,
                    12,
                ),
                -round(
                    solution.selection_objective
                    if solution.selection_objective is not None
                    else math.inf,
                    12,
                ),
                -APPROXIMATION_STRATEGIES.index(solution.strategy),
            ),
        )
        return selected, candidates
    fallback = Solution(
        status="gate_rejected" if enforce_gate else "no_candidate",
        factors=(1.0, 1.0, 1.0, 1.0),
        prediction=tuple(raw),
        total_error=sum(raw) - sum(target),
        strategy="raw_fallback",
    )
    return fallback, candidates


def _metric_fields(
    prefix: str,
    spending: float | None,
    target: float,
    raw_abs_error: float,
    scale: float,
    *,
    epsilon: float,
) -> dict[str, object]:
    if spending is None:
        return {
            f"{prefix}_spending": None,
            f"{prefix}_error": None,
            f"{prefix}_abs_error": None,
            f"{prefix}_relative_error": None,
            f"{prefix}_abs_improvement": None,
            f"{prefix}_improvement_ratio": None,
            f"{prefix}_worsening_ratio": None,
            f"{prefix}_worsening_percentage": None,
            f"{prefix}_direction": "unavailable",
        }
    error = spending - target
    absolute = abs(error)
    improvement = raw_abs_error - absolute
    if raw_abs_error > epsilon:
        improvement_ratio: float | None = improvement / raw_abs_error
    else:
        improvement_ratio = None
    if raw_abs_error > epsilon:
        worsening_ratio = max(0.0, -improvement / raw_abs_error)
        worsening_percentage: float = worsening_ratio * 100.0
    else:
        worsening_percentage = math.inf if absolute > epsilon else 0.0
        worsening_ratio = math.inf if absolute > epsilon else 0.0
    comparison_tolerance = max(epsilon, raw_abs_error * 1e-9)
    if improvement > comparison_tolerance:
        direction = "improved"
    elif improvement < -comparison_tolerance:
        direction = "worsened"
    else:
        direction = "unchanged"
    return {
        f"{prefix}_spending": spending,
        f"{prefix}_error": error,
        f"{prefix}_abs_error": absolute,
        f"{prefix}_relative_error": error / scale,
        f"{prefix}_abs_improvement": improvement,
        f"{prefix}_improvement_ratio": improvement_ratio,
        f"{prefix}_worsening_ratio": worsening_ratio,
        f"{prefix}_worsening_percentage": worsening_percentage,
        f"{prefix}_direction": direction,
    }


def analyze_country(
    country: CountryInput,
    locations: Sequence[LocationInput],
    parameters: ClassificationParameters,
    *,
    use_saved_classes: bool = False,
    enforce_approximation_gate: bool = True,
    epsilon: float = DEFAULT_EPSILON,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Return one country row and four independently evaluated rows."""

    if not locations:
        country_row = {
            "owner_id": country.owner_id,
            "owner_tag": country.owner_tag,
            "location_count": country.location_count,
            "valid_location_count": 0,
            "analysis_status": "no_valid_locations",
            "classification_source": (
                "saved" if use_saved_classes else "simulated"
            ),
        }
        return country_row, []

    if use_saved_classes:
        assignments = saved_assignments(locations)
        targets = (None, None, None, None)
        assigned_capacities = (None, None, None, None)
    else:
        assignments, targets, assigned_capacities = classify_locations(
            country, locations, parameters, epsilon=epsilon
        )

    matrix, counts, capacities = build_class_matrix(locations, assignments)
    direct = solve_direct_exact(
        matrix,
        country.target,
        country.baseline,
        counts,
        epsilon=epsilon,
    )
    approximate, approximation_candidates = choose_accepted_approximation(
        matrix,
        country.target,
        country.baseline,
        enforce_gate=enforce_approximation_gate,
        epsilon=epsilon,
    )

    target_total = sum(country.target)
    total_error_scale = max(abs(target_total), epsilon)
    country_row: dict[str, object] = {
        "owner_id": country.owner_id,
        "owner_tag": country.owner_tag,
        "location_count": country.location_count,
        "valid_location_count": len(locations),
        "analysis_status": "analyzed",
        "classification_source": "saved" if use_saved_classes else "simulated",
        "raw_total": sum(country.baseline),
        "target_total": target_total,
        "raw_total_error": sum(country.baseline) - sum(country.target),
        "raw_total_error_percentage": (
            abs(sum(country.baseline) - target_total)
            / total_error_scale
            * 100.0
        ),
        "exact_status": direct.status,
        "exact_feasible": direct.exact,
        "approx_status": approximate.status,
        "approx_exact": approximate.exact,
        "approx_accepted": approximate.strategy != "raw_fallback",
        "approx_gate_passed": approximate.gate_passed,
        "approx_gate_enforced": enforce_approximation_gate,
        "approx_strategy": approximate.strategy,
        "approx_average_improvement_ratio": (
            approximate.average_improvement_ratio
        ),
        "approx_average_abs_improvement": approximate.average_abs_improvement,
        "approx_active_classes": "/".join(
            str(index + 1) for index in approximate.active_classes
        ),
        "approx_total_error": approximate.total_error,
        "approx_total_error_percentage": (
            abs(approximate.total_error or 0.0)
            / total_error_scale
            * 100.0
        ),
    }

    for strategy in APPROXIMATION_STRATEGIES:
        candidate = approximation_candidates[strategy]
        prefix = f"candidate_{strategy}_"
        country_row[f"{prefix}status"] = candidate.status
        country_row[f"{prefix}gate_passed"] = candidate.gate_passed
        country_row[f"{prefix}average_improvement_ratio"] = (
            candidate.average_improvement_ratio
        )
        country_row[f"{prefix}average_abs_improvement"] = (
            candidate.average_abs_improvement
        )
    for index in range(4):
        country_row[f"class_{index + 1}_count"] = counts[index]
        country_row[f"class_{index + 1}_capacity"] = capacities[index]
        country_row[f"class_{index + 1}_target_capacity"] = targets[index]
        country_row[f"exact_factor_{index + 1}"] = (
            direct.factors[index] if direct.factors is not None else None
        )
        country_row[f"approx_factor_{index + 1}"] = (
            approximate.factors[index]
            if approximate.factors is not None
            else None
        )

    stratum_rows: list[dict[str, object]] = []
    approximate_directions: list[str] = []
    for index, stratum in enumerate(STRATA):
        raw_spending = country.baseline[index]
        target_spending = country.target[index]
        scale = _error_scale(raw_spending, target_spending, epsilon)
        raw_error = raw_spending - target_spending
        raw_abs_error = abs(raw_error)
        row: dict[str, object] = {
            "owner_id": country.owner_id,
            "owner_tag": country.owner_tag,
            "stratum": stratum,
            "target_spending": target_spending,
            "raw_spending": raw_spending,
            "error_scale": scale,
            "raw_error": raw_error,
            "raw_abs_error": raw_abs_error,
            "raw_relative_error": raw_error / scale,
            "exact_feasible": direct.exact,
            "approx_exact": approximate.exact,
            "approx_accepted": approximate.strategy != "raw_fallback",
            "approx_gate_passed": approximate.gate_passed,
            "approx_gate_enforced": enforce_approximation_gate,
            "approx_strategy": approximate.strategy,
        }
        exact_spending = (
            direct.prediction[index]
            if direct.exact and direct.prediction is not None
            else None
        )
        approximate_spending = (
            approximate.prediction[index]
            if approximate.prediction is not None
            else None
        )
        row.update(
            _metric_fields(
                "exact",
                exact_spending,
                target_spending,
                raw_abs_error,
                scale,
                epsilon=epsilon,
            )
        )
        row.update(
            _metric_fields(
                "approx",
                approximate_spending,
                target_spending,
                raw_abs_error,
                scale,
                epsilon=epsilon,
            )
        )
        approximate_directions.append(str(row["approx_direction"]))
        stratum_rows.append(row)

    country_row["approx_improved_strata"] = approximate_directions.count(
        "improved"
    )
    country_row["approx_worsened_strata"] = approximate_directions.count(
        "worsened"
    )
    country_row["approx_unchanged_strata"] = approximate_directions.count(
        "unchanged"
    )
    country_row["approx_all_strata_improved"] = (
        country_row["approx_gate_passed"]
    )
    country_row["approx_pareto_improves_raw"] = country_row[
        "approx_all_strata_improved"
    ]
    worsening = [
        float(row["approx_worsening_percentage"])
        for row in stratum_rows
        if row["approx_worsening_percentage"] is not None
    ]
    country_row["approx_max_worsening_percentage"] = (
        max(worsening) if worsening else None
    )
    country_row["approx_worsening_strata"] = sum(
        value > 0 for value in worsening
    )
    return country_row, stratum_rows


def _percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_strata(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Build four summary rows without combining strata into one score."""

    result: list[dict[str, object]] = []
    for stratum in STRATA:
        selected = [row for row in rows if row["stratum"] == stratum]
        raw_abs = [float(row["raw_abs_error"]) for row in selected]
        raw_relative = [
            abs(float(row["raw_relative_error"])) for row in selected
        ]
        approx_abs = [
            float(row["approx_abs_error"])
            for row in selected
            if row["approx_abs_error"] is not None
        ]
        approx_improvement = [
            float(row["approx_abs_improvement"])
            for row in selected
            if row["approx_abs_improvement"] is not None
        ]
        positive_improvement = [
            value for value in approx_improvement if value > 0
        ]
        worsening = [-value for value in approx_improvement if value < 0]
        approx_ratios = [
            float(row["approx_improvement_ratio"])
            for row in selected
            if row["approx_improvement_ratio"] is not None
        ]
        exact_selected = [row for row in selected if row["exact_feasible"]]
        exact_improvement = [
            float(row["exact_abs_improvement"])
            for row in exact_selected
            if row["exact_abs_improvement"] is not None
        ]
        result.append(
            {
                "stratum": stratum,
                "country_count": len(selected),
                "raw_abs_error_total": sum(raw_abs),
                "raw_abs_error_median": _percentile(raw_abs, 0.5),
                "raw_abs_error_p90": _percentile(raw_abs, 0.9),
                "raw_abs_relative_error_median": _percentile(
                    raw_relative, 0.5
                ),
                "raw_abs_relative_error_p90": _percentile(
                    raw_relative, 0.9
                ),
                "approx_evaluated_count": len(selected),
                "approx_candidate_count": sum(
                    bool(row["approx_accepted"]) for row in selected
                ),
                "approx_improved_count": sum(
                    row["approx_direction"] == "improved" for row in selected
                ),
                "approx_worsened_count": sum(
                    row["approx_direction"] == "worsened" for row in selected
                ),
                "approx_unchanged_count": sum(
                    row["approx_direction"] == "unchanged" for row in selected
                ),
                "approx_abs_error_median": _percentile(approx_abs, 0.5),
                "approx_abs_improvement_total": sum(approx_improvement),
                "approx_positive_improvement_total": sum(
                    positive_improvement
                ),
                "approx_worsening_total": sum(worsening),
                "approx_positive_improvement_median": _percentile(
                    positive_improvement, 0.5
                ),
                "approx_worsening_median": _percentile(worsening, 0.5),
                "approx_abs_improvement_median": _percentile(
                    approx_improvement, 0.5
                ),
                "approx_abs_improvement_p10": _percentile(
                    approx_improvement, 0.1
                ),
                "approx_abs_improvement_p90": _percentile(
                    approx_improvement, 0.9
                ),
                "approx_improvement_ratio_median": _percentile(
                    approx_ratios, 0.5
                ),
                "exact_feasible_count": len(exact_selected),
                "exact_abs_improvement_total": sum(exact_improvement),
                "exact_abs_improvement_median": _percentile(
                    exact_improvement, 0.5
                ),
            }
        )
    return result


def summarize_approximation_strategies(
    country_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Compare candidate strategies after the four-stratum hard gate."""

    analyzed = [
        row for row in country_rows if row.get("analysis_status") == "analyzed"
    ]
    result: list[dict[str, object]] = []
    for strategy in APPROXIMATION_STRATEGIES:
        prefix = f"candidate_{strategy}_"
        candidate_rows = [
            row
            for row in analyzed
            if row.get(f"{prefix}status") not in (None, "no_candidate")
        ]
        accepted = [
            row for row in candidate_rows if row.get(f"{prefix}gate_passed")
        ]
        ratios = [
            float(row[f"{prefix}average_improvement_ratio"])
            for row in accepted
            if row.get(f"{prefix}average_improvement_ratio") is not None
        ]
        absolute = [
            float(row[f"{prefix}average_abs_improvement"])
            for row in accepted
            if row.get(f"{prefix}average_abs_improvement") is not None
        ]
        selected = [
            row
            for row in analyzed
            if row.get("approx_strategy") == strategy
            and row.get("approx_accepted")
        ]
        selected_worsening = [
            float(row["approx_max_worsening_percentage"])
            for row in selected
            if row.get("approx_max_worsening_percentage") is not None
        ]
        result.append(
            {
                "strategy": strategy,
                "country_count": len(analyzed),
                "candidate_count": len(candidate_rows),
                "gate_passed_count": len(accepted),
                "gate_passed_rate": (
                    len(accepted) / len(analyzed) if analyzed else None
                ),
                "selected_count": len(selected),
                "mean_average_improvement_ratio": (
                    sum(ratios) / len(ratios) if ratios else None
                ),
                "median_average_improvement_ratio": _percentile(ratios, 0.5),
                "mean_average_abs_improvement": (
                    sum(absolute) / len(absolute) if absolute else None
                ),
                "median_average_abs_improvement": _percentile(absolute, 0.5),
                "selected_worsening_country_count": sum(
                    value > 0 for value in selected_worsening
                ),
                "selected_max_worsening_percentage": (
                    max(selected_worsening) if selected_worsening else None
                ),
                "selected_p90_worsening_percentage": _percentile(
                    selected_worsening, 0.9
                ),
            }
        )
    return result


def _read_inputs(
    analysis_directory: Path,
    *,
    country_tags: set[str] | None = None,
    epsilon: float = DEFAULT_EPSILON,
) -> tuple[list[CountryInput], dict[str, list[LocationInput]]]:
    country_path = analysis_directory / "countries.csv"
    location_path = analysis_directory / "locations.csv"
    if not country_path.is_file() or not location_path.is_file():
        raise ValueError(
            f"{analysis_directory} must contain countries.csv and locations.csv"
        )

    countries: list[CountryInput] = []
    with country_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            tag = row.get("owner_tag", "")
            if country_tags and tag.upper() not in country_tags:
                continue
            countries.append(
                CountryInput(
                    owner_id=row.get("owner_id", ""),
                    owner_tag=tag,
                    location_count=int(float(row.get("location_count") or 0)),
                    baseline=tuple(
                        _number(row, key) for key in _COUNTRY_BASELINE_COLUMNS
                    ),
                    target=tuple(
                        _number(row, key) for key in _COUNTRY_TARGET_COLUMNS
                    ),
                    pressure=tuple(
                        _number(
                            row,
                            f"sol_country_class_negative_pressure_{index}",
                        )
                        for index in range(1, 5)
                    ),
                    baseline_total=_number(
                        row, "sol_country_baseline_spending_total"
                    ),
                )
            )

    selected_ids = {country.owner_id for country in countries}
    locations: dict[str, list[LocationInput]] = defaultdict(list)
    with location_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            owner_id = row.get("owner_id", "")
            if owner_id not in selected_ids:
                continue
            capacity = _number(row, "sol_location_baseline_total_spending")
            base_total = _number(row, "sol_location_base_total_spending")
            if capacity <= epsilon or base_total <= epsilon:
                continue
            raw_factor = _number(row, "sol_location_raw_demand_scale")
            saved = round(_number(row, "sol_location_demand_class")) - 1
            locations[owner_id].append(
                LocationInput(
                    id=int(row["location_id"]),
                    capacity=capacity,
                    confidence=_number(
                        row, "sol_location_demand_class_confidence"
                    ),
                    scores=tuple(
                        _number(row, key) for key in _LOCATION_SCORE_COLUMNS
                    ),
                    spending=tuple(
                        _number(row, key) * raw_factor
                        for key in _LOCATION_BASE_COLUMNS
                    ),
                    saved_class=saved if 0 <= saved < 4 else None,
                )
            )
    return countries, locations


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty report: {path}")
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_analysis(
    analysis_directory: Path,
    output_directory: Path,
    parameters: ClassificationParameters,
    *,
    country_tags: set[str] | None = None,
    use_saved_classes: bool = False,
    enforce_approximation_gate: bool = True,
    epsilon: float = DEFAULT_EPSILON,
) -> tuple[Path, Path, Path, Path, Path]:
    """Analyze one parser export and write detailed strategy comparisons."""

    countries, locations = _read_inputs(
        analysis_directory, country_tags=country_tags, epsilon=epsilon
    )
    country_rows: list[dict[str, object]] = []
    stratum_rows: list[dict[str, object]] = []
    for country in sorted(
        countries, key=lambda item: (item.owner_tag, item.owner_id)
    ):
        country_row, rows = analyze_country(
            country,
            locations.get(country.owner_id, ()),
            parameters,
            use_saved_classes=use_saved_classes,
            enforce_approximation_gate=enforce_approximation_gate,
            epsilon=epsilon,
        )
        country_rows.append(country_row)
        stratum_rows.extend(rows)

    analyzed_country_rows = [
        row for row in country_rows if row["analysis_status"] == "analyzed"
    ]
    if not analyzed_country_rows:
        raise ValueError("no countries with valid SOL location data were found")
    summary_rows = summarize_strata(stratum_rows)
    strategy_summary_rows = summarize_approximation_strategies(
        country_rows
    )
    country_output = output_directory / "demand_country_results.csv"
    stratum_output = output_directory / "demand_stratum_results.csv"
    summary_output = output_directory / "demand_stratum_summary.csv"
    strategy_output = output_directory / "demand_strategy_summary.csv"
    metadata_output = output_directory / "demand_analysis_metadata.json"
    _write_csv(country_output, country_rows)
    _write_csv(stratum_output, stratum_rows)
    _write_csv(summary_output, summary_rows)
    _write_csv(strategy_output, strategy_summary_rows)
    metadata = {
        "source": str(analysis_directory.resolve()),
        "classification_source": (
            "saved" if use_saved_classes else "simulated"
        ),
        "classification_parameters": asdict(parameters),
        "epsilon": epsilon,
        "country_filter": sorted(country_tags or ()),
        "countries_exported": len(country_rows),
        "countries_analyzed": len(analyzed_country_rows),
        "stratum_rows": len(stratum_rows),
        "approximation": (
            f"{len(APPROXIMATION_STRATEGIES)} nonnegative candidates; "
            "candidates are ranked by mean improvement ratio"
        ),
        "approximation_strategies": list(APPROXIMATION_STRATEGIES),
        "total_constraint": (
            "hard equality for total-constrained strategies; relaxed-total "
            "strategies use a soft penalty"
            if any(
                strategy in RELAXED_TOTAL_PENALTIES
                for strategy in APPROXIMATION_STRATEGIES
            )
            else "hard equality"
        ),
        "approximation_gate_enforced": enforce_approximation_gate,
        "approximation_gate": (
            "every stratum must reduce absolute target error by more than "
            "the numeric comparison tolerance"
            if enforce_approximation_gate
            else "disabled for this diagnostic run"
        ),
        "reporting": (
            "raw, approximate, and exact errors are reported separately "
            "for nobles, clergy, burghers, and lower"
        ),
    }
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("strategy          candidates  gate_passed  selected  mean_gain  median_gain")
    for row in strategy_summary_rows:
        print(
            f"{row['strategy']:<17}"
            f"{row['candidate_count']:>10}  "
            f"{row['gate_passed_count']:>11}  "
            f"{row['selected_count']:>8}  "
            f"{(row['mean_average_improvement_ratio'] or 0):>9.3f}  "
            f"{(row['median_average_improvement_ratio'] or 0):>11.3f}"
        )
    print(
        "stratum  countries  raw_abs_med  raw_rel_med  "
        "approx(+/-/=)  approx_gain_med  exact"
    )
    for row in summary_rows:
        print(
            f"{row['stratum']:<9}"
            f"{row['country_count']:>9}  "
            f"{row['raw_abs_error_median']:>11.5f}  "
            f"{row['raw_abs_relative_error_median']:>11.3f}  "
            f"{row['approx_improved_count']:>5}/"
            f"{row['approx_worsened_count']}/"
            f"{row['approx_unchanged_count']:<5}  "
            f"{row['approx_abs_improvement_median']:>15.5f}  "
            f"{row['exact_feasible_count']:>5}"
        )
    return (
        country_output,
        stratum_output,
        summary_output,
        strategy_output,
        metadata_output,
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze SOL raw, exact, and total-preserving nonnegative "
            "approximate results separately for all four strata."
        )
    )
    parser.add_argument(
        "analysis",
        type=Path,
        help="parser export directory containing countries.csv and locations.csv",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="output directory (default: <analysis>/demand_strategy_analysis)",
    )
    parser.add_argument(
        "--country",
        action="append",
        default=[],
        metavar="TAG",
        help="analyze only this country tag; may be repeated",
    )
    parser.add_argument(
        "--use-saved-classes",
        action="store_true",
        help="use class ids persisted in the save instead of replaying current parameters",
    )
    parser.add_argument(
        "--disable-four-stratum-gate",
        action="store_true",
        help=(
            "diagnostic mode: rank candidates even when one or more strata "
            "worsen; the default keeps the hard four-stratum gate"
        ),
    )
    parser.add_argument(
        "--relax-total-constraint",
        action="store_true",
        help=(
            "diagnostic mode: add nonnegative L2 candidates with free or "
            "soft total-spending preservation"
        ),
    )
    parser.add_argument(
        "--capacity-floor",
        type=float,
        default=DEFAULT_CAPACITY_FLOOR,
    )
    parser.add_argument(
        "--negative-pool",
        type=float,
        default=DEFAULT_NEGATIVE_POOL,
    )
    parser.add_argument(
        "--balance-weight",
        type=float,
        default=DEFAULT_BALANCE_WEIGHT,
    )
    return parser.parse_args()


def main() -> int:
    global APPROXIMATION_STRATEGIES
    args = _arguments()
    if args.relax_total_constraint:
        APPROXIMATION_STRATEGIES = (
            APPROXIMATION_STRATEGIES + RELAXED_TOTAL_STRATEGIES
        )
    parameters = ClassificationParameters(
        capacity_floor=args.capacity_floor,
        negative_pool=args.negative_pool,
        balance_weight=args.balance_weight,
    )
    output = args.output or args.analysis / (
        "demand_strategy_analysis_relaxed_total"
        if args.relax_total_constraint
        else "demand_strategy_analysis"
    )
    try:
        paths = run_analysis(
            args.analysis,
            output,
            parameters,
            country_tags={tag.upper() for tag in args.country} or None,
            use_saved_classes=args.use_saved_classes,
            enforce_approximation_gate=not args.disable_four_stratum_gate,
        )
    except (OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print("Wrote:")
    for path in paths:
        print(f"  {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
