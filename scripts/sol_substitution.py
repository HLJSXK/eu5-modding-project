"""Price-only substitute response and generated EU5 country demand runtime.

Algorithm A compares historical weighted group averages to the same eligible
neutral basket. No Engel/development/era/scarcity scale is restored.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "data/substitute_groups.json").read_text(encoding="utf-8"))
POPS = ("nobles", "clergy", "burghers", "laborers", "peasants", "soldiers", "tribesmen")
GROUPS: dict[str, list[str]] = {}
with (ROOT / "data/goods_weights.csv").open(encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle):
        GROUPS.setdefault(row["group"], []).append(row["good"])
CORE = sorted({good for members in GROUPS.values() for good in members})
assert len(CORE) == 56 and len(GROUPS) == 20
assert set(GROUPS) == set(CONFIG["historical_sizes"])
assert CONFIG["algorithm"] == "A" and CONFIG["preference"] == 1 and CONFIG["epsilon"] == 0


def price_weight(ratio: float) -> float:
    for threshold, weight in ((2.30, .25), (1.70, .50), (1.30, .75)):
        if ratio > threshold:
            return weight
    for threshold, weight in ((.40, 2.), (.65, 1.50), (.85, 1.25)):
        if ratio < threshold:
            return weight
    return 1.


def response(weights: dict[str, float], eligible: set[str],
             groups: dict[str, list[str]] | None = None,
             sizes: dict[str, int] | None = None) -> dict[str, float]:
    groups = GROUPS if groups is None else groups
    sizes = CONFIG["historical_sizes"] if sizes is None else sizes
    current = {good: 0. for good in weights}
    neutral = current.copy()
    for group, members in groups.items():
        active = [good for good in members if good in eligible]
        total = sum(weights[good] for good in active)
        if not active or total <= 0:
            continue
        for good in active:
            current[good] += sizes[group] * weights[good] / total
            neutral[good] += sizes[group] / len(active)
    # Membership-count division cancels in H_T / H_1, including overlaps.
    return {good: current[good] / neutral[good] if neutral[good] > 0 else 1.
            for good in weights}


def aggregate(baselines: list[dict[str, float]],
              responses: list[dict[str, float]]) -> dict[str, float]:
    goods = set().union(*baselines)
    result = {}
    for good in goods:
        base = sum(row.get(good, 0.) for row in baselines)
        target = sum(row.get(good, 0.) * d.get(good, 1.)
                     for row, d in zip(baselines, responses, strict=True))
        result[good] = target / base if base > 0 else 1.
    return result


def map_write(name: str, value: str, indent: str = "\t\t") -> list[str]:
    return [f"{indent}remove_from_global_variable_map = {{ name = {name} key = scope:sol_market_cache }}",
            f"{indent}add_to_global_variable_map = {{ name = {name} key = scope:sol_market_cache value = {value} }}"]


def market_details(good: str, pops: list[str]) -> list[str]:
    lines = [f"\t\tset_local_variable = {{ name = sol_sub_price_weight value = 1 }}"]
    for index, (op, threshold, weight) in enumerate(((">", 2.30, .25), (">", 1.70, .5), (">", 1.30, .75), ("<", .4, 2), ("<", .65, 1.5), ("<", .85, 1.25))):
        kind = "if" if index == 0 else "else_if"
        lines.append(f'\t\t{kind} = {{ limit = {{ local_var:sol_market_actual_price_{good} {op} {{ value = "default_price(goods:{good})" multiply = {threshold} }} }} set_local_variable = {{ name = sol_sub_price_weight value = {weight} }} }}')
    lines += map_write(f"sol_market_substitute_weight_{good}", "local_var:sol_sub_price_weight")
    for pop in pops:
        lines += ["\t\tset_local_variable = { name = sol_sub_unit_cost value = 0 }",
                  f"\t\tif = {{ limit = {{ local_var:sol_market_consumes_{good}_count > 0 }} set_local_variable = {{ name = sol_sub_unit_cost value = {{ value = sol_unit_consumption_{pop}_{good} multiply = local_var:sol_market_effective_price_{good} }} }} }}"]
        lines += map_write(f"sol_market_good_spending_{pop}_{good}", "local_var:sol_sub_unit_cost")
    lines += ["\t\tremove_local_variable = sol_sub_unit_cost", "\t\tremove_local_variable = sol_sub_price_weight"]
    return lines


def render_location_spending(rows, replace: bool = False) -> str:
    lines = [f"{'REPLACE:' if replace else ''}sol_compute_substitute_unit_spending = {{",
             "\t# Location scope; market details are raw, country effective factors applied once."]
    for pop in POPS:
        lines.append(f"\tset_variable = {{ name = sol_unit_spending_{pop} value = 0 }}")
    lines += ["\towner ?= { save_scope_as = sol_spending_country }",
              "\tif = { limit = { exists = market exists = owner }",
              "\t\tmarket = { save_scope_as = sol_location_market }"]
    for good, _, quantities in rows:
        lines.append("\t\tset_local_variable = { name = sol_sub_effective value = 1 }")
        if good in CORE:
            lines.append(f"\t\tif = {{ limit = {{ scope:sol_spending_country = {{ has_variable = sol_good_effective_{good} }} }} set_local_variable = {{ name = sol_sub_effective value = scope:sol_spending_country.var:sol_good_effective_{good} }} }}")
        for pop in POPS:
            if round(quantities[pop], 5) <= 0:
                continue
            name = f"sol_market_good_spending_{pop}_{good}"
            lines += [f"\t\tif = {{ limit = {{ has_global_variable_map = {name} is_key_in_global_variable_map = {{ name = {name} target = scope:sol_location_market }} }}",
                      f'\t\t\tchange_variable = {{ name = sol_unit_spending_{pop} add = {{ value = "global_variable_map({name}|scope:sol_location_market)" multiply = local_var:sol_sub_effective }} }}',
                      "\t\t}"]
    lines += ["\t}", "\tremove_local_variable = sol_sub_effective", "}"]
    return "\n".join(lines) + "\n"


def render_modifiers() -> str:
    return "# Generated by gen_sol_substitution.py\n" + "\n".join(
        f"sol_substitute_{good} = {{\n\tgame_data = {{ category = country }}\n\tglobal_{good}_pop_demand = 1\n}}\n" for good in CORE)


def render_values() -> str:
    lines = ["# Generated by gen_sol_substitution.py"]
    for name in ("year", "goods_count", "max_size"):
        lines += [f"sol_substitute_{name}_display = {{", "\tvalue = 0",
                  f"\tif = {{ limit = {{ has_variable = sol_substitute_{name} }} add = var:sol_substitute_{name} }}", "}"]
    for good in CORE:
        lines += [f"sol_substitute_{good}_display = {{", "\tvalue = 1",
                  f"\tif = {{ limit = {{ has_variable = sol_sub_multiplier_{good} }} value = var:sol_sub_multiplier_{good} }}", "}"]
    return "\n".join(lines) + "\n"


def render_country_runtime(rows) -> str:
    quantities = {good: q for good, _, q in rows if good in CORE}
    lines = ["# Generated by gen_sol_substitution.py; algorithm A, V=1.",
             "sol_clear_country_substitution = {"]
    for good in CORE:
        lines += [f"\tif = {{ limit = {{ has_country_modifier = sol_substitute_{good} }} remove_country_modifier = sol_substitute_{good} }}"]
        for field in ("multiplier", "size", "effective", "external", "base", "target"):
            lines.append(f"\tremove_variable = sol_sub_{field}_{good}")
        lines.append(f"\tremove_variable = sol_good_effective_{good}")
    for name in ("initialized", "year", "goods_count", "max_size", "locations", "enabled", "human"):
        lines.append(f"\tremove_variable = sol_substitute_{name}")
    lines += ["\tremove_variable = sol_substitute_dirty",
              "\tremove_variable = sol_demand_snapshot_initialized",
              "\tremove_variable = sol_demand_snapshot_locations",
              "\tremove_variable = sol_demand_snapshot_human",
              "\tevery_owned_location = { remove_variable = sol_sub_snapshot_country remove_variable = sol_sub_snapshot_market remove_variable = sol_demand_snapshot_country remove_variable = sol_demand_snapshot_market }",
              "}", "", "sol_refresh_country_substitution = {",
              "\t# Remove own old values before reading external additive offsets.",
              "\tsave_scope_as = sol_sub_country",
              "\tif = { limit = { NOT = { has_global_variable = sol_market_substitution_initialized } } sol_refresh_market_pop_demand_maps = yes }",
              "\tset_local_variable = { name = sol_sub_market_missing value = 0 }",
              "\tevery_owned_location = { limit = { is_land = yes exists = market } market = { save_scope_as = sol_sub_market_probe } if = { limit = { OR = { NOT = { has_global_variable_map = sol_market_substitute_cache } NOT = { is_key_in_global_variable_map = { name = sol_market_substitute_cache target = scope:sol_sub_market_probe } } } } scope:sol_sub_country = { set_local_variable = { name = sol_sub_market_missing value = 1 } } } }",
              "\tif = { limit = { local_var:sol_sub_market_missing = 1 } sol_refresh_market_pop_demand_maps = yes }",
              "\tremove_local_variable = sol_sub_market_missing",
              "\tset_variable = { name = sol_substitute_goods_count value = 0 }",
              "\tset_variable = { name = sol_substitute_max_size value = 0 }",
              "\tset_variable = { name = sol_substitute_enabled value = 0 }",
              "\tset_variable = { name = sol_substitute_human value = 0 }",
              "\tif = { limit = { is_human = yes } set_variable = { name = sol_substitute_human value = 1 } }",
              "\tif = { limit = { sol_substitution_is_on = yes } set_variable = { name = sol_substitute_enabled value = 1 } }"]
    for good in CORE:
        lines += [f"\tif = {{ limit = {{ has_country_modifier = sol_substitute_{good} }} remove_country_modifier = sol_substitute_{good} }}",
                  f"\tset_variable = {{ name = sol_sub_external_{good} value = {{ value = 1 add = modifier:global_{good}_pop_demand min = 0 }} }}",
                  f"\tset_variable = {{ name = sol_sub_multiplier_{good} value = 1 }}",
                  f"\tset_variable = {{ name = sol_sub_size_{good} value = 0 }}",
                  f"\tset_variable = {{ name = sol_sub_base_{good} value = 0 }}",
                  f"\tset_variable = {{ name = sol_sub_target_{good} value = 0 }}"]
    lines += ["\tif = { limit = { sol_substitution_is_on = yes num_locations > 0 }",
              "\t\tevery_owned_location = {", "\t\t\tlimit = { is_land = yes exists = market }",
              "\t\t\tmarket = { save_scope_as = sol_sub_market }"]
    for good in CORE:
        name = f"sol_market_substitute_weight_{good}"
        supply = f"sol_market_consumes_{good}"
        lines += [f"\t\t\tset_local_variable = {{ name = sol_sub_weight_{good} value = 0 }}",
                  f"\t\t\tif = {{ limit = {{ has_global_variable_map = {name} is_key_in_global_variable_map = {{ name = {name} target = scope:sol_sub_market }} has_global_variable_map = {supply} is_key_in_global_variable_map = {{ name = {supply} target = scope:sol_sub_market }}",
                  f'\t\t\t\t"global_variable_map({supply}|scope:sol_sub_market)" > 0 scope:sol_sub_country.var:sol_sub_external_{good} > 0 }}',
                  f'\t\t\t\tset_local_variable = {{ name = sol_sub_weight_{good} value = "global_variable_map({name}|scope:sol_sub_market)" }}', "\t\t\t}"]
    for pop in POPS:
        used = [good for good in CORE if round(quantities[good][pop], 5) > 0]
        lines.append(f"\t\t\tif = {{ limit = {{ num_pop_type:{pop} > 0 }}")
        for good in used:
            lines += [f"\t\t\t\tset_local_variable = {{ name = sol_sub_current_{good} value = 0 }}",
                      f"\t\t\t\tset_local_variable = {{ name = sol_sub_neutral_{good} value = 0 }}"]
        for group, members in GROUPS.items():
            active = [good for good in members if good in used]
            if not active:
                continue
            size = CONFIG["historical_sizes"][group]
            lines += ["\t\t\t\tset_local_variable = { name = sol_sub_group_count value = 0 }",
                      "\t\t\t\tset_local_variable = { name = sol_sub_group_weight value = 0 }"]
            for good in active:
                lines.append(f"\t\t\t\tif = {{ limit = {{ local_var:sol_sub_weight_{good} > 0 }} change_local_variable = {{ name = sol_sub_group_count add = 1 }} change_local_variable = {{ name = sol_sub_group_weight add = local_var:sol_sub_weight_{good} }} }}")
            lines.append("\t\t\t\tif = { limit = { local_var:sol_sub_group_weight > 0 local_var:sol_sub_group_count > 0 }")
            for good in active:
                lines += [f"\t\t\t\t\tif = {{ limit = {{ local_var:sol_sub_weight_{good} > 0 }}",
                          f"\t\t\t\t\t\tchange_local_variable = {{ name = sol_sub_current_{good} add = {{ value = {size} multiply = local_var:sol_sub_weight_{good} divide = local_var:sol_sub_group_weight }} }}",
                          f"\t\t\t\t\t\tchange_local_variable = {{ name = sol_sub_neutral_{good} add = {{ value = {size} divide = local_var:sol_sub_group_count }} }}", "\t\t\t\t\t}"]
            lines.append("\t\t\t\t}")
        for good in used:
            lines += [f"\t\t\t\tif = {{ limit = {{ local_var:sol_sub_neutral_{good} > 0 }}",
                      f'\t\t\t\t\tset_local_variable = {{ name = sol_sub_amount value = {{ value = num_pop_type:{pop} multiply = sol_unit_consumption_{pop}_{good} multiply = "default_price(goods:{good})" }} }}',
                      f"\t\t\t\t\tset_local_variable = {{ name = sol_sub_response value = {{ value = local_var:sol_sub_current_{good} divide = local_var:sol_sub_neutral_{good} }} }}",
                      "\t\t\t\t\tsave_scope_value_as = { name = sol_sub_base_amount value = local_var:sol_sub_amount }",
                      "\t\t\t\t\tsave_scope_value_as = { name = sol_sub_target_amount value = { value = local_var:sol_sub_amount multiply = local_var:sol_sub_response } }",
                      f"\t\t\t\t\tscope:sol_sub_country = {{ change_variable = {{ name = sol_sub_base_{good} add = scope:sol_sub_base_amount }} change_variable = {{ name = sol_sub_target_{good} add = scope:sol_sub_target_amount }} }}",
                      "\t\t\t\t}",
                      f"\t\t\t\tremove_local_variable = sol_sub_current_{good}",
                      f"\t\t\t\tremove_local_variable = sol_sub_neutral_{good}"]
        lines.append("\t\t\t}")
    for good in CORE:
        lines.append(f"\t\t\tremove_local_variable = sol_sub_weight_{good}")
    for name in ("group_count", "group_weight", "amount", "response"):
        lines.append(f"\t\t\tremove_local_variable = sol_sub_{name}")
    lines += ["\t\t}", "\t}"]
    for good in CORE:
        lines += [f"\tif = {{ limit = {{ var:sol_sub_base_{good} > 0 }}",
                  f"\t\tset_variable = {{ name = sol_sub_multiplier_{good} value = {{ value = var:sol_sub_target_{good} divide = var:sol_sub_base_{good} min = 0 }} }}",
                  "\t\tchange_variable = { name = sol_substitute_goods_count add = 1 }", "\t}",
                  f"\tset_variable = {{ name = sol_sub_size_{good} value = {{ value = var:sol_sub_multiplier_{good} subtract = 1 multiply = var:sol_sub_external_{good} }} }}",
                  f"\tset_variable = {{ name = sol_good_effective_{good} value = {{ value = var:sol_sub_external_{good} add = var:sol_sub_size_{good} min = 0 }} }}",
                  f"\tset_local_variable = {{ name = sol_sub_abs value = var:sol_sub_size_{good} }}",
                  "\tif = { limit = { local_var:sol_sub_abs < 0 } change_local_variable = { name = sol_sub_abs multiply = -1 } }",
                  "\tif = { limit = { local_var:sol_sub_abs > var:sol_substitute_max_size } set_variable = { name = sol_substitute_max_size value = local_var:sol_sub_abs } }",
                  f"\tremove_variable = sol_sub_base_{good}", f"\tremove_variable = sol_sub_target_{good}"]
    lines += ["\tremove_local_variable = sol_sub_abs",
              "\tset_variable = { name = sol_substitute_year value = current_year }",
              "\tset_variable = { name = sol_substitute_initialized value = 1 }",
              "\tsol_apply_country_substitution = yes",
              "\t# Disabled substitution retains only the solver's external-demand baseline.",
              "\tif = { limit = { sol_substitution_is_on = no }",
              "\t\tsol_clear_country_substitution = yes"]
    for good in CORE:
        lines.append(f"\t\tset_variable = {{ name = sol_good_effective_{good} value = {{ value = 1 add = modifier:global_{good}_pop_demand min = 0 }} }}")
    lines += ["\t}",
              "\tevery_owned_location = { limit = { is_land = yes } set_variable = { name = sol_demand_snapshot_country value = scope:sol_sub_country } if = { limit = { exists = market } market = { save_scope_as = sol_demand_snapshot_market } set_variable = { name = sol_demand_snapshot_market value = scope:sol_demand_snapshot_market } } else = { remove_variable = sol_demand_snapshot_market } }",
              "\tset_variable = { name = sol_demand_snapshot_locations value = num_locations }",
              "\tset_variable = { name = sol_demand_snapshot_human value = 0 }",
              "\tif = { limit = { is_human = yes } set_variable = { name = sol_demand_snapshot_human value = 1 } }",
              "\tset_variable = { name = sol_demand_snapshot_initialized value = 1 }",
              "}", "",
              "sol_apply_country_substitution = {"]
    for good in CORE:
        lines += [f"\tif = {{ limit = {{ has_variable = sol_sub_size_{good} NOT = {{ var:sol_sub_size_{good} = 0 }} sol_substitution_is_on = yes }}",
                  f"\t\tadd_country_modifier = {{ name = sol_substitute_{good} months = 2 mode = replace size = var:sol_sub_size_{good} }}",
                  f"\t}} else = {{ if = {{ limit = {{ has_country_modifier = sol_substitute_{good} }} remove_country_modifier = sol_substitute_{good} }} }}"]
    lines += ["}", "", "sol_check_substitution_snapshot = {",
              "\tset_variable = { name = sol_substitute_dirty value = 0 }",
              "\tsave_scope_as = sol_sub_check_country",
              "\tif = { limit = { NOT = { has_variable = sol_demand_snapshot_initialized } } set_variable = { name = sol_substitute_dirty value = 1 } }",
              "\telse = {",
              "\t\tif = { limit = { OR = { NOT = { var:sol_demand_snapshot_locations = num_locations } AND = { is_human = yes NOT = { var:sol_demand_snapshot_human = 1 } } AND = { is_ai = yes NOT = { var:sol_demand_snapshot_human = 0 } } } } set_variable = { name = sol_substitute_dirty value = 1 } }",
              "\t\tevery_owned_location = { limit = { is_land = yes }",
              "\t\t\tif = { limit = { NOT = { has_variable = sol_demand_snapshot_country } } scope:sol_sub_check_country = { set_variable = { name = sol_substitute_dirty value = 1 } } }",
              "\t\t\telse_if = { limit = { NOT = { var:sol_demand_snapshot_country = scope:sol_sub_check_country } } scope:sol_sub_check_country = { set_variable = { name = sol_substitute_dirty value = 1 } } }",
              "\t\t\tif = { limit = { exists = market }",
              "\t\t\t\tmarket = { save_scope_as = sol_sub_check_market }",
              "\t\t\t\tif = { limit = { OR = { NOT = { has_global_variable_map = sol_market_substitute_cache } NOT = { is_key_in_global_variable_map = { name = sol_market_substitute_cache target = scope:sol_sub_check_market } } } } scope:sol_sub_check_country = { set_variable = { name = sol_substitute_dirty value = 1 } } }",
              "\t\t\t\tif = { limit = { NOT = { has_variable = sol_demand_snapshot_market } } scope:sol_sub_check_country = { set_variable = { name = sol_substitute_dirty value = 1 } } }",
              "\t\t\t\telse_if = { limit = { NOT = { var:sol_demand_snapshot_market = scope:sol_sub_check_market } } scope:sol_sub_check_country = { set_variable = { name = sol_substitute_dirty value = 1 } } }",
              "\t\t\t} else_if = { limit = { has_variable = sol_demand_snapshot_market } scope:sol_sub_check_country = { set_variable = { name = sol_substitute_dirty value = 1 } } }",
              "\t\t}", "\t}"]
    for good in CORE:
        lines += [f"\tif = {{ limit = {{ has_variable = sol_good_effective_{good} }}",
                  f"\t\tset_local_variable = {{ name = sol_sub_check_external value = {{ value = 1 add = modifier:global_{good}_pop_demand }} }}",
                  f"\t\tif = {{ limit = {{ has_country_modifier = sol_substitute_{good} has_variable = sol_sub_size_{good} }} change_local_variable = {{ name = sol_sub_check_external subtract = var:sol_sub_size_{good} }} }}",
                  "\t\tchange_local_variable = { name = sol_sub_check_external min = 0 }",
                  f"\t\tif = {{ limit = {{ sol_substitution_is_on = yes has_variable = sol_sub_external_{good} }}",
                  f"\t\t\tif = {{ limit = {{ NOT = {{ local_var:sol_sub_check_external = var:sol_sub_external_{good} }} }} set_variable = {{ name = sol_substitute_dirty value = 1 }} }}",
                  f"\t\t}} else = {{ if = {{ limit = {{ NOT = {{ local_var:sol_sub_check_external = var:sol_good_effective_{good} }} }} set_variable = {{ name = sol_substitute_dirty value = 1 }} }} }}", "\t}",
                  "\telse = { set_variable = { name = sol_substitute_dirty value = 1 } }"]
    lines += ["\tremove_local_variable = sol_sub_check_external", "}"]
    return "\n".join(lines) + "\n"
