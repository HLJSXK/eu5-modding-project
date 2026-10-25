"""Same-month living-standard annual samples for the SOL HUD.

The historical module path is retained for the generation workflow. Country
population and SOL accumulation belong to sol_living_standard_source instead.
The SOL-specific sample namespace deliberately ignores legacy income samples.
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ESTATES = ("nobles", "clergy", "burghers", "commoners", "tribesmen")
METRICS = ("all", *ESTATES)


def render_yoy_values() -> str:
    """Named trend thresholds (the HUD generator owns output)."""
    return """# Living-standard annual trend thresholds.
sol_ls_yoy_big_increase_threshold = { value = 0.05 }
sol_ls_yoy_big_decrease_threshold = { value = -0.05 }
"""


def _public_names(metric: str) -> tuple[str, str, str, str]:
    suffix = "" if metric == "all" else f"_{metric}"
    return (
        f"sol_ls_sol{suffix}",
        f"sol_ls_sol_prev{suffix}",
        f"sol_ls_sol_yoy{suffix}",
        f"sol_ls_sol_yoy_class{suffix}",
    )


def render_yoy_effects() -> str:
    lines = [
        "# Called after current country SOL has been finalized, without a location pass.",
        "sol_ls_finalize_country_living_standard_yoy = {",
    ]
    for metric in METRICS:
        current, previous, yoy, trend = _public_names(metric)
        lines.extend([
            # Availability is per sample: never reuse a stale month's comparison.
            f"\tremove_variable = {previous}",
            f"\tremove_variable = {yoy}",
            f"\tremove_variable = {trend}",
        ])
    lines.extend([
        "\tset_variable = { name = sol_ls_sol_previous_year value = { value = current_year subtract = 1 } }",
        "\t# Save/load and repeated refreshes cannot turn a partial year into YoY.",
        "\t# Keep both this year's last sample and the previous year's sample for each month.",
    ])
    for month in range(1, 13):
        prefix = f"sol_ls_sol_sample_{month}"
        lines.extend([
            "\tif = {",
            f"\t\tlimit = {{ current_month = {month} }}",
            "\t\tif = {",
            f"\t\t\tlimit = {{ NOT = {{ has_variable = {prefix}_year }} }}",
            f"\t\t\tset_variable = {{ name = {prefix}_year value = current_year }}",
            "\t\t}",
            "\t\telse_if = {",
            f"\t\t\tlimit = {{ var:{prefix}_year < current_year }}",
            f"\t\t\tremove_variable = {prefix}_previous_year",
            "\t\t\tif = {",
            f"\t\t\t\tlimit = {{ var:{prefix}_year = var:sol_ls_sol_previous_year }}",
            f"\t\t\t\tset_variable = {{ name = {prefix}_previous_year value = var:{prefix}_year }}",
            f"\t\t\t\tset_variable = {{ name = {prefix}_previous_day value = var:{prefix}_day }}",
        ])
        for metric in METRICS:
            lines.extend([
                f"\t\t\t\tremove_variable = {prefix}_previous_{metric}",
                "\t\t\t\tif = {",
                f"\t\t\t\t\tlimit = {{ has_variable = {prefix}_{metric} }}",
                f"\t\t\t\t\tset_variable = {{ name = {prefix}_previous_{metric} value = var:{prefix}_{metric} }}",
                "\t\t\t\t}",
            ])
        lines.extend([
            "\t\t\t}",
            f"\t\t\tset_variable = {{ name = {prefix}_year value = current_year }}",
            "\t\t}",
            "\t\tif = {",
            "\t\t\tlimit = {",
            f"\t\t\t\thas_variable = {prefix}_previous_year",
            f"\t\t\t\tvar:{prefix}_previous_year = var:sol_ls_sol_previous_year",
            f"\t\t\t\tcurrent_day >= var:{prefix}_previous_day",
            "\t\t\t}",
        ])
        for metric in METRICS:
            current, previous, yoy, trend = _public_names(metric)
            lines.extend([
                "\t\t\tif = {",
                f"\t\t\t\tlimit = {{ has_variable = {current} has_variable = {prefix}_previous_{metric} }}",
                f"\t\t\t\tset_variable = {{ name = {previous} value = var:{prefix}_previous_{metric} }}",
                "\t\t\t}",
            ])
        lines.extend([
            "\t\t\tsol_ls_compute_living_standard_yoy = yes",
            "\t\t}",
            "\t\t# No matching baseline leaves current SOL available and only YoY unset.",
        ])
        for metric in METRICS:
            current = _public_names(metric)[0]
            lines.extend([
                f"\t\tremove_variable = {prefix}_{metric}",
                "\t\tif = {",
                f"\t\t\tlimit = {{ has_variable = {current} }}",
                f"\t\t\tset_variable = {{ name = {prefix}_{metric} value = var:{current} }}",
                "\t\t}",
            ])
        lines.extend([
            f"\t\tset_variable = {{ name = {prefix}_day value = current_day }}",
            "\t}",
        ])
    lines.extend(["}", "", "sol_ls_compute_living_standard_yoy = {"])
    for metric in METRICS:
        current, previous, yoy, trend = _public_names(metric)
        lines.extend([
            "\tif = {",
            f"\t\tlimit = {{ has_variable = {current} has_variable = {previous} }}",
            f"\t\tset_variable = {{ name = {yoy} value = 0 }}",
            "\t\tif = {",
            f"\t\t\tlimit = {{ var:{previous} > 0 }}",
            f"\t\t\tset_variable = {{ name = {yoy} value = {{ value = var:{current} divide = var:{previous} subtract = 1 }} }}",
            "\t\t}",
            # Four trend classes follow the handoff contract, including zero
            # in the nonpositive, smaller-than-five-percent class.
            f"\t\tset_variable = {{ name = {trend} value = -1 }}",
            f"\t\tif = {{ limit = {{ var:{yoy} >= sol_ls_yoy_big_increase_threshold }} set_variable = {{ name = {trend} value = 2 }} }}",
            f"\t\telse_if = {{ limit = {{ var:{yoy} > 0 }} set_variable = {{ name = {trend} value = 1 }} }}",
            f"\t\telse_if = {{ limit = {{ var:{yoy} <= sol_ls_yoy_big_decrease_threshold }} set_variable = {{ name = {trend} value = -2 }} }}",
            "\t}",
        ])
    lines.extend(["}", ""])
    return "\n".join(lines)
