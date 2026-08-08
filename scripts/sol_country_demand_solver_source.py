"""Render the country-level linear demand solver as a separate game file.

The country matrix is assembled by the regular SOL economy emitter, while
the fixed-dimensional linear algebra is emitted into
``B_SOL_country_demand_solver.txt``.  Jomini scripted effects are global, so
the split is a load/ownership boundary only; effect names and call sites stay
unchanged.
"""

from __future__ import annotations

import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sol_economy_effects_source import (  # noqa: E402
    ScriptWriter,
    emit_section_30_country_demand_math,
)


_TOP_LEVEL_EFFECT = re.compile(r"^([A-Za-z0-9_]+) = \{$")

# These effects implement the country linear space itself: the old exact
# diagnostic, KKT/reduced Gaussian primitives, active-set candidates, and selection.
# Matrix aggregation and location application deliberately remain in A_....
_SOLVER_EFFECTS = frozenset(
    {
        "sol_country_demand_abs",
        "sol_country_demand_eliminate_cell",
        "sol_country_demand_eliminate_rhs",
        "sol_country_demand_eliminate_row",
        "sol_country_demand_check_pivot",
        "sol_country_demand_backsolve_cell",
        "sol_country_demand_backsolve_row",
        "sol_country_demand_backsolve_class_cell",
        "sol_country_demand_backsolve_classes",
        "sol_country_demand_select_anchor",
        "sol_country_demand_fill_anchor_column",
        "sol_country_demand_clear_matrix",
        "sol_country_demand_cache_original_matrix",
        "sol_country_demand_solve_4",
        "sol_country_demand_solve_5",
        "sol_country_demand_solve_classes",
        "sol_country_demand_validate_anchor",
        "sol_country_demand_apply_anchor",
        "sol_country_demand_normalize_working_class_row",
        "sol_country_demand_normalize_working_class_matrix",
        "sol_country_demand_validate_class",
        "sol_country_demand_validate_class_residual",
        "sol_country_demand_check_kkt_pivot",
        "sol_country_demand_solve_kkt_5",
        "sol_country_demand_solve_reduced_3",
        "sol_country_demand_solve_reduced_4",
        "sol_country_demand_approx_reset_kkt",
        "sol_country_demand_approx_reset_diagnostics",
        "sol_country_demand_approx_prepare_country",
        "sol_country_demand_approx_prepare_strategy",
        "sol_country_demand_approx_assess",
        "sol_country_demand_select_approx_strategy",
        "sol_country_demand_solve_approximation",
        "sol_country_demand_minimax_vertex_enumeration",
    }
)


def _is_solver_effect(name: str) -> bool:
    return name in _SOLVER_EFFECTS or name.startswith(
        (
            "sol_country_demand_approx_candidate_",
            "sol_country_demand_minimax_vertex_",
            "sol_country_demand_run_strategy_",
        )
    )


def _section_30_lines() -> list[str]:
    writer = ScriptWriter()
    emit_section_30_country_demand_math(writer)
    return writer.lines


def _split_section_30() -> tuple[list[str], list[str]]:
    """Split top-level Jomini effect blocks without changing their bodies."""

    aggregation: list[str] = []
    solver: list[str] = []
    pending: list[str] = []
    lines = _section_30_lines()
    index = 0
    while index < len(lines):
        match = _TOP_LEVEL_EFFECT.match(lines[index])
        if not match:
            pending.append(lines[index])
            index += 1
            continue

        name = match.group(1)
        block = [lines[index]]
        depth = lines[index].count("{") - lines[index].count("}")
        index += 1
        while index < len(lines) and depth > 0:
            block.append(lines[index])
            depth += lines[index].count("{") - lines[index].count("}")
            index += 1

        destination = solver if _is_solver_effect(name) else aggregation
        destination.extend(pending)
        destination.extend(block)
        pending = []

    # Keep trailing whitespace with the regular file.  The solver file gets
    # its own concise header and does not need section-30 comments.
    aggregation.extend(pending)
    return aggregation, solver


def _render(lines: list[str]) -> str:
    return "\n".join(lines).strip() + "\n"


def render_country_demand_aggregation() -> str:
    """Return section 30 with all solver-owned effects removed."""

    aggregation, _ = _split_section_30()
    return _render(aggregation)


def render_country_demand_solver() -> str:
    """Return only the fixed-dimensional country solver effects."""

    _, solver = _split_section_30()
    return _render(solver)
