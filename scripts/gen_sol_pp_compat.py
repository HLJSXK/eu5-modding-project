#!/usr/bin/env python3
"""Generate SOL-PP compatibility overrides from stable SOL and PP sources."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT))

from gen_market_unit_consumption import (  # noqa: E402
    EPSILON,
    POP_TYPES,
    _find_effect_block,
    _format_float,
    _generate_refresh_block,
    _generate_values,
    _load_good_rows,
)
from tools.sol_demand_simulator.parser import (  # noqa: E402
    _collect_brace_block,
    _expand_demand_add,
    _slave_demand,
    _find_sub_block,
    _parse_kv_block,
    _parse_inject_file,
    _parse_vanilla_goods_file,
    load_vanilla_goods,
)
from sol_goods_ui import replace_goods_vbox  # noqa: E402
from sol_goods_order import GROUP_MEMBERS, PRIMARY_GROUP  # noqa: E402
from location_window_integrations import add_great_projects  # noqa: E402
import sol_substitution as _sol_substitution  # noqa: E402

TARGET_ROOT = REPO_ROOT / "src" / "sol_pp_compatibility_submod"
STABLE_ROOT = REPO_ROOT / "src" / "stable"
PP_ROOT = REPO_ROOT.parent / "prosper-or-perish-upstream" / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
PP_METADATA = PP_ROOT / ".metadata" / "metadata.json"
PP_EXPECTED_VERSION = "0.10.0"
PP_EXPECTED_COMMIT = "967cadbe"

PP_VICTUALS_FILE = PP_ROOT / "in_game" / "common" / "goods" / "pp_goods_victuals.txt"
PP_LUMBER_FILE = PP_ROOT / "in_game" / "common" / "goods" / "pp_goods_adjustments.txt"
PP_ROAD_PRICES = PP_ROOT / "in_game" / "common" / "prices" / "pp_road_gold_adjustments.txt"
STABLE_POP_GOODS = STABLE_ROOT / "in_game" / "common" / "goods" / "z_SOL_pop_goods.txt"
STABLE_EFFECTS = STABLE_ROOT / "in_game" / "common" / "scripted_effects" / "A_SOL_economy_effects.txt"
STABLE_CMM_EFFECTS = STABLE_ROOT / "in_game" / "common" / "scripted_effects" / "SOL_cmm_effects.txt"
STABLE_AUTO_MODIFIERS = STABLE_ROOT / "in_game" / "common" / "auto_modifiers" / "SOL_economy_auto_modifiers.txt"
STABLE_STATIC_MODIFIERS = STABLE_ROOT / "main_menu" / "common" / "static_modifiers" / "A_SOL_economy_modifiers.txt"
STABLE_WAR_STATIC_MODIFIERS = STABLE_ROOT / "main_menu" / "common" / "static_modifiers" / "A_SOL_war_modifiers.txt"
STABLE_PRICES = STABLE_ROOT / "in_game" / "common" / "prices" / "A_SOL_economy_prices.txt"
STABLE_LOCATION_GUI = STABLE_ROOT / "in_game" / "gui" / "SOL_economy_local.gui"
STABLE_SITUATION_GUI = STABLE_ROOT / "in_game" / "gui" / "panels" / "situation" / "global_living_standard.gui"
PP_LOCATION_GUI = PP_ROOT / "in_game" / "gui" / "location_window.gui"

VALUES_OUTPUT = TARGET_ROOT / "in_game" / "common" / "script_values" / "zz_SOL_market_unit_consumption_values.txt"
EFFECTS_OUTPUT = TARGET_ROOT / "in_game" / "common" / "scripted_effects" / "zz_A_SOL_economy_effects.txt"
LUMBER_OUTPUT = TARGET_ROOT / "in_game" / "common" / "goods" / "zz_SOL_PP_lumber_demand.txt"
LOCATION_GUI_OUTPUT = TARGET_ROOT / "in_game" / "gui" / "zz_SOL_economy_local.gui"
LOCATION_WINDOW_OUTPUT = TARGET_ROOT / "in_game" / "gui" / "location_window.gui"
SITUATION_GUI_OUTPUT = TARGET_ROOT / "in_game" / "gui" / "panels" / "situation" / "global_living_standard.gui"
AUTO_MODIFIERS_OUTPUT = TARGET_ROOT / "in_game" / "common" / "auto_modifiers" / "zz_SOL_PP_compact_economy_auto_modifiers.txt"
CMM_EFFECTS_OUTPUT = TARGET_ROOT / "in_game" / "common" / "scripted_effects" / "zz_SOL_PP_compact_cmm_effects.txt"
CMM_TRIGGERS_OUTPUT = TARGET_ROOT / "in_game" / "common" / "scripted_triggers" / "zz_SOL_PP_compact_disabled_triggers.txt"
CMM_SCRIPTED_GUI_OUTPUT = (
    TARGET_ROOT
    / "in_game"
    / "common"
    / "scripted_guis"
    / "zz_SOL_PP_compact_cmm_scripted_gui.txt"
)
ENGLISH_CMM_LOC_OUTPUT = (
    TARGET_ROOT / "main_menu" / "localization" / "english" / "SOL_PP_cmm_l_english.yml"
)
CHINESE_CMM_LOC_OUTPUT = (
    TARGET_ROOT
    / "main_menu"
    / "localization"
    / "simp_chinese"
    / "SOL_PP_cmm_l_simp_chinese.yml"
)
ENGLISH_SUB_LOC_OUTPUT = TARGET_ROOT / "main_menu" / "localization" / "english" / "SOL_PP_substitution_l_english.yml"
CHINESE_SUB_LOC_OUTPUT = TARGET_ROOT / "main_menu" / "localization" / "simp_chinese" / "SOL_PP_substitution_l_simp_chinese.yml"
STATIC_CLEANUP_OUTPUT = TARGET_ROOT / "main_menu" / "common" / "static_modifiers" / "zz_SOL_PP_compact_static_cleanup.txt"
WAR_OVERLAP_CLEANUP_OUTPUT = TARGET_ROOT / "main_menu" / "common" / "static_modifiers" / "zz_SOL_PP_compact_war_overlap_cleanup.txt"
WEATHER_OUTPUT = TARGET_ROOT / "in_game" / "common" / "static_modifiers" / "zz_SOL_PP_weather_modifiers.txt"
LIA_OUTPUT = TARGET_ROOT / "main_menu" / "common" / "static_modifiers" / "zz_SOL_PP_lia_modifiers.txt"
ON_ACTION_OUTPUT = TARGET_ROOT / "in_game" / "common" / "on_action" / "zz_SOL_PP_compatibility_on_actions.txt"

UTF8_BOM = b"\xef\xbb\xbf"
GENERATED_HEADER = "# @AUTOGENERATED by scripts/gen_sol_pp_compat.py - do not edit; run script to regenerate.\n"
EXPECTED_BASE_GOODS_COUNT = 56
COMPAT_EXTRA_GOODS = ("silk",)
SILK_DEFAULT_PRICE = 4.0
# Initial PP-only silk basket: one seventh of the existing SOL luxury budget,
# priced at silk's default price.  Existing members are scaled to six sevenths
# so adding silk does not enlarge the historical luxury basket.
SILK_BASELINE_QUANTITIES = {
    "nobles": 0.0583928571,
    "clergy": 0.0062200000,
    "burghers": 0.0101464286,
    "laborers": 0.0,
    "peasants": 0.0,
    "soldiers": 0.0,
    "tribesmen": 0.0,
}
# Calibrated from the 1340-04-06 PP + SOL + compatch save. Multipliers move
# each country-weighted median funds/base-spending ratio to 1 before rounding.
PP_BASKET_MULTIPLIERS = {
    "nobles": 2.0,
    "clergy": 2.0,
    "burghers": 1.5373831775700935,
    "laborers": 1.706803704957381,
    "peasants": 1.706803704957381,
    "soldiers": 1.706803704957381,
    "tribesmen": 1.0,
}
DEMAND_STEP = Decimal("0.00001")
SOURCE_STEP = Decimal("0.000005")
LUXURY_BASELINE_MEMBERS = (
    "fine_cloth", "fur", "porcelain", "lacquerware", "marble", "glass"
)
LUXURY_BASELINE_SCALE = 6.0 / 7.0
PP_SILK_DIRECT_DEMAND = {"nobles": 0.08, "clergy": 0.006, "burghers": 0.004}
PP_FUR_EXPECTED_LINES = (
    "none = 0.5", "mild = 0.75", "normal = 1", "severe = 1.25",
    "tropical = 0", "ha1300_climate_tropical_monsoon = 0",
    "ha1300_climate_savanna = 0", "arid = 0.5", "hot_semi_arid = 0.5",
    "market_unavailability_demand_modifier = 1.5",
)

AGE_FIELDS = (
    "global_build_buildings_efficiency",
    "city_upgrade_cost_modifier",
    "town_upgrade_cost_modifier",
)
AGE_NAMES = (
    (1, "age_1_traditions"),
    (2, "age_2_renaissance"),
    (3, "age_3_discovery"),
    (4, "age_4_reformation"),
    (5, "age_5_absolutism"),
    (6, "age_6_revolutions"),
)
ROAD_PRICE_KEYS = (
    "build_gravel_road",
    "build_paved_road",
    "build_modern_road",
    "build_railroad",
)
LIA_KEYS = (
    "harsh_winters_modifier",
    "reduced_wool_production_modifier",
    "fewer_fisheries_modifier",
    "livestock_suffers_modifier",
    "wineries_suffering_modifier",
    "great_frost_modifier",
    "short_harvest_modifier",
    "recent_white_storm_modifier",
)
PP_OWNED_WAR_LOCATION_KEYS = (
    "is_blockaded_by_enemies",
    "under_siege",
    "is_occupied",
    "looted",
)
VISIBLE_CMM_SETTINGS = (
    "sol_on",
    "sol_map",
    "substitution",
    "pp_as_on",
    "bte",
    "ae",
    "cts",
    "ds",
    "difficulty",
    "gdp_dev",
    "ai_pr",
    "hw_on",
    "iwe",
    "hwe",
    "rwe",
    "ai_reduced_freq",
    "solver_human_exact",
    "solver_human_approx",
    "solver_ai_exact",
    "solver_ai_approx",
)
HIDDEN_CMM_SETTINGS = ("as_on", "pp_gdp_dev")
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _validate_pp_version() -> None:
    if not PP_METADATA.is_file():
        raise ValueError(f"PP 0.10 metadata missing: {PP_METADATA}")
    metadata = json.loads(PP_METADATA.read_text(encoding="utf-8"))
    if metadata.get("version") != PP_EXPECTED_VERSION:
        raise ValueError(f"Expected PP {PP_EXPECTED_VERSION}, found {metadata.get('version')}")
    upstream_root = REPO_ROOT.parent / "prosper-or-perish-upstream"
    result = subprocess.run(
        ["git", "-C", str(upstream_root), "-c", f"safe.directory={upstream_root}", "rev-parse", "--short=8", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"Unable to verify PP source revision: {result.stderr.strip()}")
    head = result.stdout.strip()
    if head != PP_EXPECTED_COMMIT:
        raise ValueError(f"Expected PP commit {PP_EXPECTED_COMMIT}, found {head}")


def _validate_pp_fixed_inputs() -> None:
    silk_source = _parse_vanilla_goods_file(
        PP_ROOT / "in_game" / "common" / "goods" / "00_raw_materials.txt"
    ).get("silk")
    if silk_source is None or abs(silk_source["price"] - SILK_DEFAULT_PRICE) > EPSILON:
        raise ValueError("PP silk default price no longer matches the locked 0.10 value")
    silk_demand = _parse_injected_demand_add(PP_LUMBER_FILE, "silk")
    for pop_type, expected in PP_SILK_DIRECT_DEMAND.items():
        if abs(silk_demand[pop_type] - expected) > EPSILON:
            raise ValueError(f"PP silk direct demand changed for {pop_type}: {silk_demand[pop_type]}")
    fur_block = _find_named_block(PP_LUMBER_FILE, "fur")
    for expected in PP_FUR_EXPECTED_LINES:
        if expected not in fur_block:
            raise ValueError(f"PP fur condition changed; missing `{expected}`")


def _find_named_block_in_text(text: str, key: str, source: str) -> str:
    match = re.search(
        rf"(?m)^(?:(?:TRY_)?(?:INJECT|REPLACE):)?{re.escape(key)}\s*=\s*\{{",
        text,
    )
    if not match:
        raise ValueError(f"{key} block not found in {source}")
    brace_start = text.index("{", match.start())
    block, _end = _collect_brace_block(text, brace_start)
    return block


def _find_named_block(path: Path, key: str) -> str:
    return _find_named_block_in_text(_read(path), key, str(path))


def _numeric_fields(path: Path, key: str) -> List[Tuple[str, float]]:
    block = _find_named_block(path, key)
    fields: List[Tuple[str, float]] = []
    for match in re.finditer(
        r"(?m)^\s*([A-Za-z0-9_]+)\s*=\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:#.*)?$",
        block,
    ):
        fields.append((match.group(1), float(match.group(2))))
    if not fields:
        raise ValueError(f"No numeric fields found in {key} block from {path}")
    return fields


def _field_value(path: Path, key: str, field: str) -> Optional[float]:
    values = dict(_numeric_fields(path, key))
    return values.get(field)


def _validate_pp_road_price_ownership() -> None:
    if STABLE_PRICES.name >= PP_ROAD_PRICES.name:
        raise ValueError(
            "SOL road prices must load before PP road prices within TRY_INJECT: "
            f"{STABLE_PRICES.name} >= {PP_ROAD_PRICES.name}"
        )

    for path in (STABLE_PRICES, PP_ROAD_PRICES):
        text = _read(path)
        for key in ROAD_PRICE_KEYS:
            if not re.search(rf"(?m)^TRY_INJECT:{re.escape(key)}\s*=\s*\{{", text):
                raise ValueError(f"Expected TRY_INJECT:{key} in {path}")


def _render_inverse_injections(path: Path, keys: Tuple[str, ...], purpose: str) -> str:
    lines = [GENERATED_HEADER.rstrip(), purpose]
    for key in keys:
        lines.extend(["", f"TRY_INJECT:{key} = {{"])
        for field, value in _numeric_fields(path, key):
            lines.append(f"\t{field} = {_format_float(-value)}")
        lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _silk_row() -> Tuple[str, float, Dict[str, float]]:
    if set(SILK_BASELINE_QUANTITIES) != set(POP_TYPES):
        raise ValueError("Silk baseline must define every SOL pop type")
    if any(value < 0 for value in SILK_BASELINE_QUANTITIES.values()):
        raise ValueError("Silk baseline quantities must be non-negative")
    return "silk", SILK_DEFAULT_PRICE, dict(SILK_BASELINE_QUANTITIES)


def _significant_digits(value: Decimal) -> int:
    normalized = value.normalize()
    return len(normalized.as_tuple().digits) if normalized else 1


def _calibrated_quantity(quantity: float, pop_type: str) -> float:
    """Scale and round to the nearest emittable net quantity with <=2 sig figs."""
    original = Decimal(str(quantity)).quantize(SOURCE_STEP, rounding=ROUND_HALF_UP)
    if original <= 0:
        return 0.0
    ideal = original * Decimal(str(PP_BASKET_MULTIPLIERS[pop_type]))
    # Round to two significant digits first, then to the engine's five-decimal
    # fixed-point lattice. This keeps ordinary values such as 0.17142 at 0.17
    # while retaining tiny two-significant-digit values such as 0.000035.
    quantum = Decimal(1).scaleb(ideal.adjusted() - 1)
    rounded = ideal.quantize(quantum, rounding=ROUND_HALF_UP)
    rounded = rounded.quantize(DEMAND_STEP, rounding=ROUND_HALF_UP)
    return float(rounded if rounded > 0 else DEMAND_STEP)


def _calibrate_rows(
    rows: List[Tuple[str, float, Dict[str, float]]],
) -> List[Tuple[str, float, Dict[str, float]]]:
    return [
        (good, price, {pop_type: _calibrated_quantity(quantity, pop_type)
                       for pop_type, quantity in quantities.items()})
        for good, price, quantities in rows
    ]


def _activate_pp_substitution_goods() -> Dict[str, object]:
    """Extend only this generator process with PP's silk substitute member."""
    state: Dict[str, object] = {
        "core": list(_sol_substitution.CORE),
        "groups": {name: list(members) for name, members in _sol_substitution.GROUPS.items()},
        "group_members": {name: list(members) for name, members in GROUP_MEMBERS.items()},
        "primary": dict(PRIMARY_GROUP),
        "hud_goods": tuple(_sol_substitution.HUD_GOODS),
    }
    # PP lumber has zero final population demand and must not enter SOL's
    # substitution solver or its goods panels in this compatibility target.
    for group, members in GROUP_MEMBERS.items():
        GROUP_MEMBERS[group] = [good for good in members if good != "lumber"]
    PRIMARY_GROUP.pop("lumber", None)
    for group, members in _sol_substitution.GROUPS.items():
        _sol_substitution.GROUPS[group] = [good for good in members if good != "lumber"]
    if "silk" not in _sol_substitution.CORE:
        _sol_substitution.CORE.append("silk")
    GROUP_MEMBERS.setdefault("luxury_goods", [])
    if "silk" not in GROUP_MEMBERS["luxury_goods"]:
        GROUP_MEMBERS["luxury_goods"].append("silk")
    _sol_substitution.GROUPS.setdefault("luxury_goods", GROUP_MEMBERS["luxury_goods"])
    if "silk" not in _sol_substitution.GROUPS["luxury_goods"]:
        _sol_substitution.GROUPS["luxury_goods"].append("silk")
    PRIMARY_GROUP["silk"] = "luxury_goods"
    _sol_substitution.HUD_GOODS = tuple(
        good for good in _sol_substitution.HUD_GOODS if good != "lumber"
    )
    if "silk" not in _sol_substitution.HUD_GOODS:
        _sol_substitution.HUD_GOODS = (*_sol_substitution.HUD_GOODS, "silk")
    return state


def _restore_pp_substitution_goods(state: Dict[str, object]) -> None:
    _sol_substitution.CORE[:] = state["core"]
    _sol_substitution.GROUPS.clear()
    _sol_substitution.GROUPS.update({name: list(members) for name, members in state["groups"].items()})
    GROUP_MEMBERS.clear()
    GROUP_MEMBERS.update({name: list(members) for name, members in state["group_members"].items()})
    PRIMARY_GROUP.clear()
    PRIMARY_GROUP.update(state["primary"])
    _sol_substitution.HUD_GOODS = state["hud_goods"]


def _compat_good_rows() -> List[Tuple[str, float, Dict[str, float]]]:
    rows: List[Tuple[str, float, Dict[str, float]]] = []
    found_lumber = False
    base_rows = _load_good_rows()
    for good, price, quantities in base_rows:
        if good == "lumber":
            found_lumber = True
            quantities = {pop_type: 0.0 for pop_type in POP_TYPES}
        rows.append((good, price, quantities))

    if not found_lumber:
        raise ValueError("Base SOL demand table does not contain lumber")
    by_good = {good: (price, quantities) for good, price, quantities in rows}
    missing_luxury = [good for good in LUXURY_BASELINE_MEMBERS if good not in by_good]
    if missing_luxury:
        raise ValueError(f"Stable SOL luxury basket is missing {missing_luxury}")
    for good, price, quantities in rows:
        if good in LUXURY_BASELINE_MEMBERS:
            quantities = {
                pop_type: (
                    quantity * LUXURY_BASELINE_SCALE
                    if SILK_BASELINE_QUANTITIES[pop_type] > EPSILON
                    else quantity
                )
                for pop_type, quantity in quantities.items()
            }
        else:
            continue
        rows[rows.index((good, price, by_good[good][1]))] = (good, price, quantities)
    rows.append(_silk_row())
    rows = _calibrate_rows(rows)
    for pop_type in POP_TYPES:
        old_budget = sum(
            by_good[good][0] * by_good[good][1][pop_type]
            for good in LUXURY_BASELINE_MEMBERS
        ) * PP_BASKET_MULTIPLIERS[pop_type]
        new_budget = sum(
            price * quantities[pop_type]
            for good, price, quantities in rows
            if good in LUXURY_BASELINE_MEMBERS or good == "silk"
        )
        if old_budget <= EPSILON:
            continue
        if abs(new_budget / old_budget - 1) > 0.15:
            raise ValueError(
                f"Calibrated luxury budget rounding exceeds 15% for {pop_type}: "
                f"{old_budget} -> {new_budget}"
            )
    return sorted(rows, key=lambda row: row[0])


def _render_values(rows: List[Tuple[str, float, Dict[str, float]]]) -> str:
    silk_rows = [row for row in rows if row[0] == "silk"]
    if len(silk_rows) != 1:
        raise ValueError(f"Expected one silk row, found {len(silk_rows)}")
    text = _generate_values(rows)
    text = text.replace(
        "# @AUTOGENERATED by scripts/gen_market_unit_consumption.py - do not edit; run script to regenerate.\n",
        GENERATED_HEADER,
        1,
    )
    text = text.replace(
        "# Generated from data/demand_price_table.csv. Each value is net\n"
        "# demand_add quantity for one pop type and one good, with duplicate\n"
        "# legacy demand-group rows counted once. Yearly market spending\n"
        "# multiplies these quantities by min(market_price, default_price).\n",
        "# Replaces SOL unit-consumption values with PP-calibrated quantities,\n"
        "# and adds silk. Victuals is omitted because PP compatibility sets it to zero.\n"
        "# Existing luxury members are rebased to six sevenths of their SOL budget;\n"
        "# silk receives the remaining seventh before the PP basket calibration.\n"
        "# Yearly market spending multiplies these quantities by\n"
        "# min(market_price, default_price).\n",
        1,
    )
    # Existing SOL script values are database keys, so the compat target must
    # use an explicit replacement operation rather than a duplicate bare key.
    for good, _price, _quantities in rows:
        if good == "silk":
            continue
        text = re.sub(
            rf"(?m)^(sol_unit_consumption_[A-Za-z0-9_]*{re.escape('_' + good)}\s*=)",
            r"REPLACE:\1",
            text,
        )
    text += "\n# Silk participates in the PP-only luxury_goods substitution group.\n"
    text += "sol_substitute_silk_scale = {\n\tvalue = 0\n\tif = { limit = { sol_substitution_is_on = yes has_variable = sol_sub_size_silk } value = var:sol_sub_size_silk }\n}\n"
    text += "sol_substitute_silk_display = {\n\tvalue = 1\n\tif = { limit = { has_variable = sol_sub_multiplier_silk } value = var:sol_sub_multiplier_silk }\n}\n"
    return text


def _parse_injected_demand_add(path: Path, good: str) -> Dict[str, float]:
    text = _read(path)
    match = re.search(rf"\b(?:TRY_)?INJECT:{re.escape(good)}\s*=\s*\{{", text)
    if not match:
        raise ValueError(f"{good} injection not found in {path}")
    brace_start = text.index("{", match.start())
    block, _end = _collect_brace_block(text, brace_start)
    demand_add = _find_sub_block(block, "demand_add")
    if demand_add is None:
        raise ValueError(f"{good} demand_add not found in {path}")
    return _expand_demand_add(_parse_kv_block(demand_add))


def _parse_development_threshold(path: Path, good: str) -> Optional[float]:
    text = _read(path)
    match = re.search(rf"(?m)^{re.escape(good)}\s*=\s*\{{", text)
    if not match:
        raise ValueError(f"{good} definition not found in {path}")
    brace_start = text.index("{", match.start())
    block, _end = _collect_brace_block(text, brace_start)
    threshold = re.search(r"\bdevelopment_threshold\s*=\s*(-?[\d.]+)", block)
    return float(threshold.group(1)) if threshold else None


def _render_goods_injections(
    rows: List[Tuple[str, float, Dict[str, float]]],
) -> str:
    inject = _parse_inject_file(STABLE_POP_GOODS).get("lumber")
    if not inject:
        raise ValueError(f"SOL lumber injection not found in {STABLE_POP_GOODS}")

    vanilla = load_vanilla_goods()["lumber"]
    pp_add = _parse_injected_demand_add(PP_LUMBER_FILE, "lumber")
    pre_compat = {
        pop_type: (
            vanilla["add"][pop_type] * vanilla["mult"][pop_type]
            + inject["inject_add"].get(pop_type, 0.0)
            + pp_add.get(pop_type, 0.0)
        )
        for pop_type in POP_TYPES
    }
    corrections = {pop_type: -value for pop_type, value in pre_compat.items()}
    for pop_type in POP_TYPES:
        final = pre_compat[pop_type] + corrections[pop_type]
        if abs(final) > EPSILON:
            raise ValueError(f"lumber demand correction failed for {pop_type}: {final}")
    lines = [
        GENERATED_HEADER.rstrip(),
        "# PP cancels vanilla lumber pop demand after SOL has added its calibrated",
        "# adjustment. This third demand_add cancels the remaining SOL adjustment,",
        "# leaving final lumber pop demand at exactly zero.",
        "INJECT:lumber = {",
        "\tdemand_add = {",
    ]
    for pop_type in POP_TYPES:
        value = corrections[pop_type]
        if abs(value) <= EPSILON:
            continue
        lines.append(f"\t\t{pop_type} = {_format_float(value)}")
    # Base SOL already cancels vanilla slave demand; undo PP's duplicate cancellation.
    pp_text = _read(PP_LUMBER_FILE)
    pp_match = re.search(r"(?:TRY_)?INJECT:lumber\s*=\s*\{", pp_text)
    if pp_match is None:
        raise ValueError("PP lumber injection missing")
    pp_body, _ = _collect_brace_block(pp_text, pp_text.index("{", pp_match.start()))
    slave_correction = -_slave_demand(pp_body)
    if abs(slave_correction) > EPSILON:
        lines.append(f"\t\tslaves = {_format_float(slave_correction)}")
    lines.extend(["\t}", "}", ""])

    # Apply this target's basket calibration after the full SOL baseline. Keep
    # the shared data/target_demand.csv and other deploy targets unchanged.
    base_rows = {good: quantities for good, _price, quantities in _load_good_rows()}
    compat_rows = {good: quantities for good, _price, quantities in rows}
    for good in sorted(base_rows):
        if good == "lumber":
            continue
        deltas = {
            pop_type: compat_rows[good][pop_type] - base_rows[good][pop_type]
            for pop_type in POP_TYPES
            if abs(compat_rows[good][pop_type] - base_rows[good][pop_type]) >= 0.000005
        }
        if not deltas:
            continue
        lines.extend([f"# PP compatch basket calibration: {good}.", f"INJECT:{good} = {{", "\tdemand_add = {"])
        for pop_type, delta in deltas.items():
            lines.append(f"\t\t{pop_type} = {_format_float(delta)}")
        lines.extend(["\t}", "}", ""])

    silk_row = next(row for row in rows if row[0] == "silk")
    _good, _price, silk_quantities = silk_row
    lines.extend([
        "# Add the initial SOL luxury-goods basket for PP's silk; PP's native",
        "# nobles/clergy/burghers silk demand and its condition modifiers remain active.",
        "INJECT:silk = {",
        "\tdemand_add = {",
    ])
    for pop_type in POP_TYPES:
        value = silk_quantities[pop_type]
        if abs(value) > EPSILON:
            lines.append(f"\t\t{pop_type} = {_format_float(value)}")
    lines.extend(["\t}", "}", ""])

    # PP's victuals is a real trade good, but it must have no population demand
    # in the SOL accounting layer. Cancel its complete native demand explicitly.
    victuals_text = _read(PP_VICTUALS_FILE)
    victuals_match = re.search(r"(?m)^victuals\s*=\s*\{", victuals_text)
    if victuals_match is None:
        raise ValueError("PP victuals definition missing")
    victuals_body, _ = _collect_brace_block(victuals_text, victuals_text.index("{", victuals_match.start()))
    parsed_victuals = _parse_vanilla_goods_file(PP_VICTUALS_FILE).get("victuals")
    if parsed_victuals is None:
        raise ValueError(f"victuals definition not found in {PP_VICTUALS_FILE}")
    lines.extend([
        "# Remove PP's native victuals population demand completely.",
        "INJECT:victuals = {",
        "\tdemand_add = {",
    ])
    for pop_type in POP_TYPES:
        # EU5 applies an injected demand_add after the native demand_multiply:
        # (native_add * native_mult + injected_add).  Cancel the effective
        # PP baseline, rather than only the pre-multiplier add value.
        native_final = parsed_victuals["add"][pop_type] * parsed_victuals["mult"][pop_type]
        if abs(native_final) > EPSILON:
            lines.append(f"\t\t{pop_type} = {_format_float(-native_final)}")
    slave_quantity = _slave_demand(victuals_body)
    if abs(slave_quantity) > EPSILON:
        lines.append(f"\t\tslaves = {_format_float(-slave_quantity)}")
    lines.extend(["\t}", "}", ""])
    lines.extend([
        "# PP 0.10 fur demand conditions are copied as fixed compat inputs.",
        "TRY_INJECT:fur = {",
        "\tblock_rgo_upgrade = yes",
        "\tfood = 0",
        "\twinter_demand_modifier = { none = 0.5 mild = 0.75 normal = 1 severe = 1.25 }",
        "\tclimate_demand_modifier = { tropical = 0 ha1300_climate_tropical_monsoon = 0 ha1300_climate_savanna = 0 arid = 0.5 hot_semi_arid = 0.5 }",
        "\tmarket_unavailability_demand_modifier = 1.5",
        "}",
        "",
    ])
    return "\n".join(lines)


def _market_reset(good: str, value: int) -> str:
    return (
        f"\t\tremove_from_global_variable_map = {{ name = sol_market_consumes_{good} key = scope:sol_market_cache }}\n"
        f"\t\tadd_to_global_variable_map = {{ name = sol_market_consumes_{good} key = scope:sol_market_cache value = {value} }}"
    )


def _country_market_check(good: str) -> str:
    return (
        "\t\tif = {\n"
        "\t\t\tlimit = {\n"
        f"\t\t\t\thas_global_variable_map = sol_market_consumes_{good}\n"
        f"\t\t\t\tis_key_in_global_variable_map = {{ name = sol_market_consumes_{good} target = scope:gls_panel_market }}\n"
        f"\t\t\t\t\"global_variable_map(sol_market_consumes_{good}|scope:gls_panel_market)\" > 0\n"
        "\t\t\t}\n"
        f"\t\t\tremove_from_global_variable_map = {{ name = gls_country_consumes_{good} key = scope:gls_panel_country }}\n"
        f"\t\t\tadd_to_global_variable_map = {{ name = gls_country_consumes_{good} key = scope:gls_panel_country value = 1 }}\n"
        "\t\t}"
    )


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def _render_effects(rows: List[Tuple[str, float, Dict[str, float]]]) -> str:
    from sol_substitution import render_country_runtime, render_location_spending
    text = _read(STABLE_EFFECTS)
    refresh = _generate_refresh_block(rows)
    save_scope = "\t\tsave_scope_as = sol_market_cache"
    refresh = _replace_once(
        refresh,
        save_scope,
        save_scope + "\n\n\t\t# PP requires final lumber pop demand to be zero. Clear saved-map residue.\n" + _market_reset("lumber", 0),
        "market cache scope",
    )
    block_start, block_end = _find_effect_block(text)
    text = text[:block_start] + refresh + text[block_end:]

    lumber_init = (
        "\tremove_from_global_variable_map = { name = gls_country_consumes_lumber key = scope:gls_panel_country }\n"
        "\tadd_to_global_variable_map = { name = gls_country_consumes_lumber key = scope:gls_panel_country value = 0 }"
    )
    text = _replace_once(text, lumber_init, lumber_init, "country goods reset")

    lumber_check = _country_market_check("lumber")
    text = _replace_once(
        text,
        lumber_check,
        lumber_check + "\n" + _country_market_check("silk"),
        "country market aggregation",
    )

    lumber_count = (
        "\tif = { limit = { \"global_variable_map(gls_country_consumes_lumber|scope:gls_panel_country)\" > 0 } "
        "change_local_variable = { name = gls_country_consumed_goods_count add = 1 } }"
    )
    silk_count = lumber_count.replace("lumber", "silk")
    text = _replace_once(text, lumber_count, lumber_count + "\n" + silk_count, "country goods count")
    lines = [
        GENERATED_HEADER.rstrip(),
        "# Replace only the two SOL effects whose bodies differ in the PP stack.",
    ]
    for key in ("sol_refresh_market_pop_demand_maps", "gls_accumulate_panel_stats"):
        block = _find_named_block_in_text(text, key, str(STABLE_EFFECTS))
        lines.extend(["", f"REPLACE:{key} = {{", block, "}"])
    lines.append("")
    runtime = render_country_runtime(rows, removed_goods={"lumber"}).replace(
        "\nsol_", "\nREPLACE:sol_"
    )
    return "\n".join(lines) + runtime + render_location_spending(
        rows, replace=True, extra_goods=COMPAT_EXTRA_GOODS, removed_goods={"lumber"}
    )


def _render_gui(source: Path, section_marker: str, variable_map: str, scope: str) -> str:
    """Rebuild the goods block with PP's silk added.

    The old approach inserted one widget by line and consumed a trailing spacer, which
    only worked while the goods were a flat lattice. The block is now grouped by demand
    group, so silk lands in the luxury-goods row and every row's membership has to be
    recomputed - hence a whole-block rebuild via the shared renderer.
    """
    text = _read(source)
    goods = [good for good, _price, _quantities in _compat_good_rows() if good != "lumber"]
    if "silk" not in goods or "victuals" in goods:
        raise ValueError("PP goods rows must contain silk and exclude victuals")
    rendered = replace_goods_vbox(text, section_marker, goods, variable_map, scope)
    # SOL already owns the generic silk localization keys. The PP target needs
    # a distinct caption because its silk membership differs from SOL's base
    # data, and localization keys are global across the loaded mod stack.
    rendered = rendered.replace("SOL_GOOD_SUB_silk", "SOL_PP_GOOD_SUB_silk")
    rendered = rendered.replace("SOL_SUB_PRICE_silk", "SOL_PP_SUB_PRICE_silk")
    if rendered.count('tooltip = "@silk!') != 1:
        raise ValueError(f"Rebuilt GUI does not contain exactly one silk cell in {source}")
    for good in ("weaponry", "lumber"):
        expected = sum(good in members for members in GROUP_MEMBERS.values())
        if rendered.count(f'tooltip = "@{good}!') != expected:
            raise ValueError(f"Rebuilt GUI does not contain all {expected} {good} memberships in {source}")
    return GENERATED_HEADER + rendered


PP_LOCATION_BUTTON_ANCHOR_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)expand = \{\}[ \t]*\r?\n"
    r"(?:[ \t]*\r?\n)*(?P=indent)subheader_unified_icon = \{[ \t]*\r?\n"
    r'[ \t]+visible = "\[HasPopBreakdownIntelOn\(Location\.Self\)\]"'
)
def _render_location_window() -> str:
    """Inject the shared SOL button into PP's complete location-window owner."""
    text = _read(PP_LOCATION_GUI)
    anchor_matches = list(PP_LOCATION_BUTTON_ANCHOR_RE.finditer(text))
    if len(anchor_matches) != 1:
        raise ValueError(
            "Expected one PP location-window anchor after average satisfaction, "
            f"found {len(anchor_matches)}"
        )
    if "sol_location_living_standard_button = {}" in text:
        raise ValueError("PP location window already contains the SOL button")
    match = anchor_matches[0]
    indent = match.group("indent")
    button = (
        f"{indent}# SOL-PP compatibility insertion: shared location living-standard button.\n"
        f"{indent}sol_location_living_standard_button = {{}}\n\n"
    )
    insert_at = match.start()
    text = text[:insert_at] + button + text[insert_at:]
    return GENERATED_HEADER + add_great_projects(text, expected_queue_actions=6)


def _render_auto_modifiers() -> str:
    lines = [
        GENERATED_HEADER.rstrip(),
        "# PP owns economic balance by default; the CMF opt-in restores SOL's",
        "# trigger-gated Economic Balance auto modifiers when explicitly enabled.",
    ]
    lines.extend([
        "",
        "# PP-only silk member of SOL's luxury_goods substitute group.",
        "sol_substitute_silk = {",
        "\tcategory = country",
        "\trequires_real = no",
        "\tpotential_trigger = { sol_substitution_is_on = yes has_variable = sol_sub_size_silk }",
        "\tscales_with = sol_substitute_silk_scale",
        "\tglobal_silk_pop_demand = 1",
        "}",
    ])
    lines.append("")
    return "\n".join(lines)


def _render_static_cleanup() -> str:
    lines = [
        GENERATED_HEADER.rstrip(),
        "# Remove SOL's location-base rebalance while preserving PP's independently",
        "# injected location values. The low-control construction penalty is kept.",
        "",
        "TRY_INJECT:location_base_values = {",
    ]
    for field, value in _numeric_fields(STABLE_STATIC_MODIFIERS, "location_base_values"):
        lines.append(f"\t{field} = {_format_float(-value)}")
    lines.append("}")

    for key in ("prosperity", "devastation"):
        lines.extend([
            "",
            "# Preserve PP's native food consumption; cancel SOL's feedback delta.",
            f"TRY_INJECT:{key} = {{",
        ])
        for field, value in _numeric_fields(STABLE_STATIC_MODIFIERS, key):
            lines.append(f"\t{field} = {_format_float(-value)}")
        lines.append("}")

    for key in ("cheap_food_in_location", "expensive_food_in_location"):
        lines.extend(["", "# Preserve PP food-price effects; cancel SOL's calibration delta.",
                      f"TRY_INJECT:{key} = {{"])
        for field, value in _numeric_fields(STABLE_STATIC_MODIFIERS, key):
            lines.append(f"\t{field} = {_format_float(-value)}")
        lines.append("}")

    lines.append("")
    return "\n".join(lines)


def _append_bool_setting(
    lines: List[str], setting_id: str, tab_id: str, group_id: str,
    alias: str, add_scripted_gui: bool = True, default_value: int = 1,
) -> None:
    lines.extend([
        "\tcmm_register_global_bool_setting = {",
        "\t\tmod_id = sol",
        f"\t\tsetting_id = {setting_id}",
        f"\t\ttab_id = {tab_id}",
        f"\t\tgroup_id = {group_id}",
        f"\t\tdefault_value = {default_value}",
        "\t}",
    ])
    lines.extend([
        "\tcmm_sync_bool_alias = {",
        f"\t\tsetting = sol__{setting_id}",
        f"\t\talias = {alias}",
        "\t}",
    ])
    if add_scripted_gui:
        lines.extend([
            "\tcmm_add_scripted_gui = {",
            "\t\tmod_id = sol",
            f"\t\tsetting_id = {setting_id}",
            "\t}",
        ])
    lines.append("")


def _append_slider_setting(
    lines: List[str], setting_id: str, alias: str, default: str,
    minimum: str, maximum: str, step: str,
) -> None:
    lines.extend([
        "\tcmm_register_global_slider_setting = {",
        "\t\tmod_id = sol",
        f"\t\tsetting_id = {setting_id}",
        "\t\ttab_id = feat",
        "\t\tgroup_id = as",
        f"\t\tdefault_value = {default}",
        f"\t\tmin_value = {minimum}",
        f"\t\tmax_value = {maximum}",
        f"\t\tstep_value = {step}",
        "\t}",
        "\tcmm_sync_setting_alias = {",
        f"\t\tsetting = sol__{setting_id}",
        f"\t\talias = {alias}",
        "\t}",
        "\tcmm_add_scripted_gui = {",
        "\t\tmod_id = sol",
        f"\t\tsetting_id = {setting_id}",
        "\t}",
        "",
    ])


def _append_callback(lines: List[str], setting_id: str, alias: str, numeric: bool = False) -> None:
    sync_effect = "cmm_sync_setting_alias" if numeric else "cmm_sync_bool_alias"
    lines.extend([
        f"\t\tflag:sol__{setting_id} = {{",
        f"\t\t\t{sync_effect} = {{",
        f"\t\t\t\tsetting = sol__{setting_id}",
        f"\t\t\t\talias = {alias}",
        "\t\t\t}",
    ])
    if setting_id == "sol_on":
        lines.extend([
            "\t\t\tif = {",
            "\t\t\t\tlimit = { has_global_variable = sol_sol_on_enabled }",
            "\t\t\t\tgls_recalculate_global_living_standard = yes",
            "\t\t\t}",
        ])
    if setting_id == "substitution":
        lines.extend(["\t\tevery_country = { sol_clear_country_substitution = yes }", "\t\tif = { limit = { sol_sol_is_on = yes } gls_recalculate_global_living_standard = yes }"])
    if setting_id == "sol_on":
        lines.append("\t\telse = { every_country = { sol_clear_country_substitution = yes every_owned_location = { remove_location_modifier = sol_local_pop_demand_modifier sol_clear_location_living_standard_modifiers = yes } } }")
    lines.append("\t\t}")


def _render_cmm_effects() -> str:
    source = _read(STABLE_CMM_EFFECTS)
    for setting_id in ("difficulty", "gdp_dev", "ai_pr"):
        if f"setting_id = {setting_id}" not in source:
            raise ValueError(f"Source CMM setting {setting_id} missing from {STABLE_CMM_EFFECTS}")

    lines = [
        GENERATED_HEADER.rstrip(),
        "# Keep PP-compatible defaults while allowing explicit CMF opt-in to SOL",
        "# Economic Balance controls.",
        "REPLACE:sol_initialize_cmm_bool_alias_defaults = {",
        "\tset_global_variable = { name = sol_substitution_enabled value = yes }",
        "\tset_global_variable = { name = sol_sol_on_enabled value = yes }",
        "\tset_global_variable = { name = sol_sol_map_enabled value = yes }",
        "\tremove_global_variable = sol_as_enabled",
        "\tremove_global_variable = sol_ae_enabled",
        "\tremove_global_variable = sol_difficulty_enabled",
        "\tremove_global_variable = sol_gdp_dev_enabled",
        "\tset_global_variable = { name = sol_hw_enabled value = yes }",
        "\tset_global_variable = { name = sol_iwe_enabled value = yes }",
        "\tset_global_variable = { name = sol_hwe_enabled value = yes }",
        "\tset_global_variable = { name = sol_rwe_enabled value = yes }",
        "\tset_global_variable = { name = sol_ai_reduced_freq_enabled value = yes }",
        "\tset_global_variable = { name = sol_solver_human_exact_enabled value = yes }",
        "\tset_global_variable = { name = sol_solver_human_approx_enabled value = yes }",
        "\tset_global_variable = { name = sol_solver_ai_exact_enabled value = yes }",
        "\tset_global_variable = { name = sol_solver_ai_approx_enabled value = yes }",
        "}",
        "",
        "REPLACE:sol_register_cmf_mod = {",
    ]
    _append_bool_setting(lines, "sol_on", "feat", "sol", "sol_sol_on_enabled", False)
    _append_bool_setting(lines, "sol_map", "feat", "sol", "sol_sol_map_enabled")
    _append_bool_setting(lines, "substitution", "feat", "sol", "sol_substitution_enabled", False)
    _append_bool_setting(lines, "pp_as_on", "feat", "as", "sol_as_enabled", False, default_value=0)
    _append_slider_setting(lines, "bte", "sol_bte", "-15", "-30", "30", "1")
    _append_bool_setting(lines, "ae", "feat", "as", "sol_ae_enabled")
    _append_slider_setting(lines, "cts", "sol_cts", "-5", "-20", "0", "1")
    _append_slider_setting(lines, "ds", "sol_ds", "-5", "-20", "0", "1")
    _append_bool_setting(lines, "difficulty", "feat", "as", "sol_difficulty_enabled")
    _append_bool_setting(lines, "gdp_dev", "feat", "as", "sol_gdp_dev_enabled")
    _append_slider_setting(lines, "ai_pr", "sol_ai_pr", "0.5", "0", "2", "0.1")
    _append_bool_setting(lines, "hw_on", "feat", "hw", "sol_hw_enabled", False)
    _append_bool_setting(lines, "iwe", "feat", "hw", "sol_iwe_enabled")
    _append_bool_setting(lines, "hwe", "feat", "hw", "sol_hwe_enabled")
    _append_bool_setting(lines, "rwe", "feat", "hw", "sol_rwe_enabled")
    # Performance (perf) tab. Registration order sets render order, so the
    # calculation-frequency group comes before the solver group.
    _append_bool_setting(lines, "ai_reduced_freq", "perf", "calc_freq", "sol_ai_reduced_freq_enabled")
    _append_bool_setting(lines, "solver_human_exact", "perf", "country_solver", "sol_solver_human_exact_enabled", False)
    _append_bool_setting(lines, "solver_human_approx", "perf", "country_solver", "sol_solver_human_approx_enabled", False)
    _append_bool_setting(lines, "solver_ai_exact", "perf", "country_solver", "sol_solver_ai_exact_enabled", False)
    _append_bool_setting(lines, "solver_ai_approx", "perf", "country_solver", "sol_solver_ai_approx_enabled", False)
    if lines[-1] == "":
        lines.pop()
    lines.extend(["}", "", "REPLACE:sol_handle_cmf_callback = {", "\tswitch = {", "\t\ttrigger = var:cmf_callback"])
    for setting_id, alias, numeric in (
        ("sol_on", "sol_sol_on_enabled", False),
        ("substitution", "sol_substitution_enabled", False),
        ("sol_map", "sol_sol_map_enabled", False),
        ("pp_as_on", "sol_as_enabled", False),
        ("bte", "sol_bte", True),
        ("ae", "sol_ae_enabled", False),
        ("cts", "sol_cts", True),
        ("ds", "sol_ds", True),
        ("difficulty", "sol_difficulty_enabled", False),
        ("gdp_dev", "sol_gdp_dev_enabled", False),
        ("ai_pr", "sol_ai_pr", True),
        ("hw_on", "sol_hw_enabled", False),
        ("iwe", "sol_iwe_enabled", False),
        ("hwe", "sol_hwe_enabled", False),
        ("rwe", "sol_rwe_enabled", False),
        ("ai_reduced_freq", "sol_ai_reduced_freq_enabled", False),
        ("solver_human_exact", "sol_solver_human_exact_enabled", False),
        ("solver_human_approx", "sol_solver_human_approx_enabled", False),
        ("solver_ai_exact", "sol_solver_ai_exact_enabled", False),
        ("solver_ai_approx", "sol_solver_ai_approx_enabled", False),
    ):
        _append_callback(lines, setting_id, alias, numeric)
    lines.extend(["\t}", "}", ""])
    rendered = "\n".join(lines)
    for setting_id in VISIBLE_CMM_SETTINGS:
        if f"setting_id = {setting_id}" not in rendered:
            raise ValueError(f"Active compact CMM setting is not registered: {setting_id}")
    for setting_id in HIDDEN_CMM_SETTINGS:
        if f"setting_id = {setting_id}" in rendered or f"flag:sol__{setting_id}" in rendered:
            raise ValueError(f"Disabled compact CMM setting is still visible: {setting_id}")
    return rendered


def _render_disabled_triggers() -> str:
    lines = [
        GENERATED_HEADER.rstrip(),
        "# SOL Economic Balance is off by default in the PP stack and can be",
        "# enabled explicitly through the PP-specific CMF master setting.",
        "",
        "REPLACE:sol_as_is_on = {",
        "\tAND = {",
        "\t\thas_global_variable_map = cmm",
        "\t\thas_global_variable = sol_as_enabled",
        "\t}",
        "}",
    ]
    for trigger, alias in (
        ("sol_ae_is_on", "sol_ae_enabled"),
        ("sol_difficulty_is_on", "sol_difficulty_enabled"),
        ("sol_gdp_dev_is_on", "sol_gdp_dev_enabled"),
    ):
        lines.extend([
            "",
            f"REPLACE:{trigger} = {{",
            "\tAND = {",
            "\t\tsol_as_is_on = yes",
            f"\t\thas_global_variable = {alias}",
            "\t}",
            "}",
        ])
    lines.append("")
    return "\n".join(lines)


def _render_cmm_scripted_gui() -> str:
    # SOL already defines these callbacks. PP registers their setting IDs but
    # must not load duplicate scripted-GUI keys alongside the base SOL mod.
    return GENERATED_HEADER


def _render_on_actions() -> str:
    return GENERATED_HEADER + """on_game_started_after_lobby = {
\ton_actions = { sol_pp_compatibility_cleanup }
}

sol_pp_compatibility_cleanup = {
\teffect = {
\t\tevery_country = {
\t\t\tlimit = { sol_ae_is_on = no }
\t\t\tremove_country_modifier = sol_ae_age_1_modifier
\t\t\tremove_country_modifier = sol_ae_age_2_modifier
\t\t\tremove_country_modifier = sol_ae_age_3_modifier
\t\t\tremove_country_modifier = sol_ae_age_4_modifier
\t\t\tremove_country_modifier = sol_ae_age_5_modifier
\t\t\tremove_country_modifier = sol_ae_age_6_modifier
\t\t}
\t\tevery_location_in_the_world = {
\t\t\tlimit = { sol_gdp_dev_is_on = no }
\t\t\tremove_location_modifier = gdp_to_development_modifier
\t\t}
\t}
}
"""


def _render_cmm_localization(language: str) -> str:
    if language not in {"english", "simp_chinese"}:
        raise ValueError(f"Unsupported localization language: {language}")
    if language == "english":
        return (
            "l_english:\n"
            ' sol__pp_as_on_name: "Enable SOL Economic Balance with PP?"\n'
            ' sol__pp_as_on_desc: "Off by default. Enables SOL\'s trigger-gated economic settings alongside Prosper or Perish; PP remains the default economic authority."\n'
            ' sol__pp_as_on: "sol__pp_as_on"\n'
        )
    return (
        "l_simp_chinese:\n"
        ' sol__pp_as_on_name: "启用SOL经济平衡（PP兼容）？"\n'
        ' sol__pp_as_on_desc: "默认关闭。开启后在Prosper or Perish兼容层中启用SOL的经济开关控制；默认经济权仍由PP负责。"\n'
        ' sol__pp_as_on: "sol__pp_as_on"\n'
    )


def _render_substitution_localization(language: str) -> str:
    if language == "english":
        return (
            "l_english:\n"
            ' SOL_PP_GOOD_SUB_silk: "Luxury goods @fine_cloth! @fur! @porcelain! @lacquerware! @marble! @glass!"\n'
            ' SOL_PP_SUB_PRICE_silk: "$SOL_SUB_PRICE_WEIGHT$ [GetVariableFromGlobalVariableMap(\'sol_market_substitute_weight_silk\', Location.GetMarket.MakeScope).GetValue|2]"\n'
            ' AUTO_MODIFIER_NAME_sol_substitute_silk: "Goods substitution ($silk$)"\n'
            ' AUTO_MODIFIER_DESC_sol_substitute_silk: "Adjusts population demand for $silk$ through goods substitution."\n'
            ' SOL_LSHUD_GOOD_ICON_silk: "@silk!"\n'
        )
    return (
        "l_simp_chinese:\n"
        ' SOL_PP_GOOD_SUB_silk: "奢侈品 @fine_cloth! @fur! @porcelain! @lacquerware! @marble! @glass!"\n'
        ' SOL_PP_SUB_PRICE_silk: "$SOL_SUB_PRICE_WEIGHT$ [GetVariableFromGlobalVariableMap(\'sol_market_substitute_weight_silk\', Location.GetMarket.MakeScope).GetValue|2]"\n'
        ' AUTO_MODIFIER_NAME_sol_substitute_silk: "商品替代（$silk$）"\n'
        ' AUTO_MODIFIER_DESC_sol_substitute_silk: "通过商品替代调整$silk$的人口需求。"\n'
        ' SOL_LSHUD_GOOD_ICON_silk: "@silk!"\n'
    )


def _render_outputs() -> Dict[Path, str]:
    _validate_pp_version()
    _validate_pp_fixed_inputs()
    _validate_pp_road_price_ownership()
    state = _activate_pp_substitution_goods()
    try:
        return _render_outputs_active()
    finally:
        _restore_pp_substitution_goods(state)


def _render_outputs_active() -> Dict[Path, str]:
    # Repeated price scalar fields replace earlier values rather than adding.
    # PP therefore owns roads through same-operation filename order; no compact
    # price cleanup file must be generated.
    rows = _compat_good_rows()
    return {
        VALUES_OUTPUT: _render_values(rows),
        EFFECTS_OUTPUT: _render_effects(rows),
        LUMBER_OUTPUT: _render_goods_injections(rows),
        LOCATION_GUI_OUTPUT: _render_gui(
            STABLE_LOCATION_GUI,
            "SOL_GUI_SECTION_LOCAL_GOODS",
            "sol_market_consumes",
            "Location.GetMarket.MakeScope",
        ),
        LOCATION_WINDOW_OUTPUT: _render_location_window(),
        SITUATION_GUI_OUTPUT: _render_gui(
            STABLE_SITUATION_GUI,
            "SOL_GUI_SECTION_COUNTRY_GOODS",
            "gls_country_consumes",
            "Player.MakeScope",
        ),
        AUTO_MODIFIERS_OUTPUT: _render_auto_modifiers(),
        CMM_EFFECTS_OUTPUT: _render_cmm_effects(),
        CMM_TRIGGERS_OUTPUT: _render_disabled_triggers(),
        CMM_SCRIPTED_GUI_OUTPUT: _render_cmm_scripted_gui(),
        ENGLISH_CMM_LOC_OUTPUT: _render_cmm_localization("english"),
        CHINESE_CMM_LOC_OUTPUT: _render_cmm_localization("simp_chinese"),
        ENGLISH_SUB_LOC_OUTPUT: _render_substitution_localization("english"),
        CHINESE_SUB_LOC_OUTPUT: _render_substitution_localization("simp_chinese"),
        STATIC_CLEANUP_OUTPUT: _render_static_cleanup(),
        WAR_OVERLAP_CLEANUP_OUTPUT: _render_inverse_injections(
            STABLE_WAR_STATIC_MODIFIERS,
            PP_OWNED_WAR_LOCATION_KEYS,
            "# PP owns these shared local war-state modifiers in the compact stack.",
        ),
        # Keep the output to overwrite obsolete inverse deltas on deployment.
        WEATHER_OUTPUT: GENERATED_HEADER + "# SOL leaves winter modifiers unchanged; PP owns weather values.\n",
        LIA_OUTPUT: _render_inverse_injections(
            STABLE_STATIC_MODIFIERS,
            LIA_KEYS,
            "# Restore PP's Little Ice Age values by removing only SOL's deltas.",
        ),
        ON_ACTION_OUTPUT: _render_on_actions(),
    }


def _check(outputs: Dict[Path, str]) -> bool:
    ok = True
    for path, expected in outputs.items():
        relative = path.relative_to(REPO_ROOT)
        if not path.exists():
            print(f"[FAIL] Missing generated target: {relative}")
            ok = False
            continue
        if path.read_bytes()[:3] != UTF8_BOM:
            print(f"[FAIL] Missing UTF-8 BOM: {relative}")
            ok = False
            continue
        if _read(path) != expected:
            print(f"[FAIL] Out of date: {relative}")
            ok = False
            continue
        print(f"[OK] Up to date: {relative}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SOL-PP compatibility overrides.")
    parser.add_argument("--check", action="store_true", help="Check outputs without writing files.")
    args = parser.parse_args()

    outputs = _render_outputs()
    if args.check:
        raise SystemExit(0 if _check(outputs) else 1)

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(UTF8_BOM + content.encode("utf-8"))
        print(f"[gen_sol_pp_compat] Wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
