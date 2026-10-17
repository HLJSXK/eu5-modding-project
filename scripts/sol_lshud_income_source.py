"""Income accumulation and same-month annual samples for the SOL HUD.

The two solver preparation paths call the location accumulator inside their
existing first territory pass. No HUD effect starts another location iterator.
Population is in thousands; the monthly net income is annualized by twelve.
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ESTATES = ("nobles", "clergy", "burghers", "commoners", "tribesmen")
METRICS = ("all", *ESTATES)


def render_income_values() -> str:
    """Named, shared unit and trend thresholds (the HUD generator owns output)."""
    return """# Monthly gold per thousand people -> annual gold per thousand people.
sol_ls_annualization_factor = { value = 12 }
sol_ls_yoy_big_increase_threshold = { value = 0.05 }
sol_ls_yoy_big_decrease_threshold = { value = -0.05 }
"""


def _public_names(metric: str) -> tuple[str, str, str, str]:
    suffix = "" if metric == "all" else f"_{metric}"
    return (
        f"sol_ls_pci{suffix}",
        f"sol_ls_pci_prev{suffix}",
        f"sol_ls_pci_yoy{suffix}",
        f"sol_ls_pci_yoy_class{suffix}",
    )


def render_income_effects() -> str:
    lines = [
        "# HUD income piggybacks on the existing country solver preparation pass.",
        "sol_ls_reset_country_income = {",
        "\tset_variable = { name = sol_ls_income_all value = 0 }",
        "\tset_variable = { name = sol_ls_pop_all value = 0 }",
    ]
    for estate in ESTATES:
        lines.extend([
            f"\tset_variable = {{ name = sol_ls_income_{estate} value = 0 }}",
            f"\tset_variable = {{ name = sol_ls_pop_{estate} value = 0 }}",
        ])
    lines.extend([
        "}", "",
        "sol_ls_accumulate_country_income = {",
        "\t# Location scope, called immediately after sol_compute_location_pop_demand.",
        "\tsave_scope_as = sol_ls_income_location",
        "\towner = {",
        "\t\t# The solver clamps net income per estate before summing. Reuse that exact total",
        "\t\t# so one estate's maintenance deficit cannot consume another estate's income.",
        "\t\tchange_variable = { name = sol_ls_income_all add = scope:sol_ls_income_location.var:sol_location_total_income }",
        "\t\tchange_variable = { name = sol_ls_pop_all add = scope:sol_ls_income_location.local_sol_population_sum }",
    ])
    for estate in ESTATES:
        population = "local_commoner_population" if estate == "commoners" else f"num_pop_type:{estate}"
        lines.extend([
            f"\t\tchange_variable = {{ name = sol_ls_pop_{estate} add = scope:sol_ls_income_location.{population} }}",
            # Preserve gls_income_* (gross diagnostics). The solver already
            # subtracts maintenance and clamps each estate's available income.
            f"\t\tchange_variable = {{ name = sol_ls_income_{estate} add = scope:sol_ls_income_location.var:sol_location_{estate}_net_income }}",
        ])
    lines.extend(["\t}", "}", "", "sol_ls_finalize_country_income = {"])
    for metric in METRICS:
        lines.extend([
            f"\tset_variable = {{ name = sol_ls_current_pci_{metric} value = 0 }}",
            "\tif = {",
            f"\t\tlimit = {{ var:sol_ls_pop_{metric} > 0 }}",
            f"\t\tset_variable = {{ name = sol_ls_current_pci_{metric} value = {{ value = var:sol_ls_income_{metric} divide = var:sol_ls_pop_{metric} multiply = sol_ls_annualization_factor }} }}",
            "\t}",
        ])
    lines.extend([
        "\tset_variable = { name = sol_ls_previous_year value = { value = current_year subtract = 1 } }",
        "\t# Save/load and repeated refreshes cannot turn a partial year into YoY.",
        "\t# Keep both this year's last sample and the previous year's sample for each month.",
    ])
    for month in range(1, 13):
        prefix = f"sol_ls_sample_{month}"
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
            f"\t\t\t\tlimit = {{ var:{prefix}_year = var:sol_ls_previous_year }}",
            f"\t\t\t\tset_variable = {{ name = {prefix}_previous_year value = var:{prefix}_year }}",
            f"\t\t\t\tset_variable = {{ name = {prefix}_previous_day value = var:{prefix}_day }}",
        ])
        for metric in METRICS:
            lines.append(f"\t\t\t\tset_variable = {{ name = {prefix}_previous_{metric} value = var:{prefix}_{metric} }}")
        lines.extend([
            "\t\t\t}",
            f"\t\t\tset_variable = {{ name = {prefix}_year value = current_year }}",
            "\t\t}",
            "\t\tif = {",
            "\t\t\tlimit = {",
            f"\t\t\t\thas_variable = {prefix}_previous_year",
            f"\t\t\t\tvar:{prefix}_previous_year = var:sol_ls_previous_year",
            f"\t\t\t\tcurrent_day >= var:{prefix}_previous_day",
            "\t\t\t}",
        ])
        for metric in METRICS:
            pci, previous, yoy, trend = _public_names(metric)
            lines.extend([
                f"\t\t\tset_variable = {{ name = {previous} value = var:{prefix}_previous_{metric} }}",
                f"\t\t\tset_variable = {{ name = {pci} value = var:sol_ls_current_pci_{metric} }}",
            ])
        lines.extend([
            "\t\t\tsol_ls_compute_income_yoy = yes",
            "\t\t}",
            "\t\t# An incomplete new month retains the last complete public annual sample.",
        ])
        for metric in METRICS:
            lines.append(f"\t\tset_variable = {{ name = {prefix}_{metric} value = var:sol_ls_current_pci_{metric} }}")
        lines.extend([
            f"\t\tset_variable = {{ name = {prefix}_day value = current_day }}",
            "\t}",
        ])
    lines.extend(["}", "", "sol_ls_compute_income_yoy = {"])
    for metric in METRICS:
        pci, previous, yoy, trend = _public_names(metric)
        lines.extend([
            f"\tset_variable = {{ name = {yoy} value = 0 }}",
            "\tif = {",
            f"\t\tlimit = {{ var:{previous} > 0 }}",
            f"\t\tset_variable = {{ name = {yoy} value = {{ value = var:{pci} divide = var:{previous} subtract = 1 }} }}",
            "\t}",
            # Four trend classes follow the handoff contract, including zero
            # in the nonpositive, smaller-than-five-percent class.
            f"\tset_variable = {{ name = {trend} value = -1 }}",
            f"\tif = {{ limit = {{ var:{yoy} >= sol_ls_yoy_big_increase_threshold }} set_variable = {{ name = {trend} value = 2 }} }}",
            f"\telse_if = {{ limit = {{ var:{yoy} > 0 }} set_variable = {{ name = {trend} value = 1 }} }}",
            f"\telse_if = {{ limit = {{ var:{yoy} <= sol_ls_yoy_big_decrease_threshold }} set_variable = {{ name = {trend} value = -2 }} }}",
        ])
    lines.extend(["}", ""])
    return "\n".join(lines)
