#!/usr/bin/env python3
"""Generate lightweight Country Events GUI files from the registry."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from country_runtime_aliases import group_runtime_keys
from generate_registry import discover_external_mod_sources


SCRIPT_PATH = Path(__file__).resolve()
MOD_ROOT = SCRIPT_PATH.parent.parent
IN_GAME_ROOT = MOD_ROOT / "in_game"
DEFAULT_REGISTRY = MOD_ROOT / "data" / "country_events_registry.json"
DEFAULT_OUTPUT = IN_GAME_ROOT / "gui" / "country_events_lateralview.gui"
DEFAULT_WINDOWS_DIR = IN_GAME_ROOT / "gui" / "country_events_windows"
DEFAULT_RUNTIME_RESOLVER = IN_GAME_ROOT / "gui" / "country_events_runtime_resolver.gui"
WINDOW_FILE_PREFIX = "country_events_window_"
WINDOW_WIDGET_NAME = "country_events_window"
TAB_ICON_TEXTURE = "gfx/interface/icons/flat_icons/tabicons/content_flat_icon.dds"
WINDOW_BASE_CLOSE_ACTIONS = [
    f"[ExecuteConsoleCommand('gui.ClearWidgets {WINDOW_WIDGET_NAME}')]",
    "[GetVariableSystem.Clear('ce_window_open')]",
    "[GetVariableSystem.Clear('ce_window_pending_open')]",
    "[GetVariableSystem.Clear('ce_open_tag')]",
    "[GetVariableSystem.Clear('ce_display_tag')]",
    "[GetVariableSystem.Clear('ce_active_sec')]",
    "[GetVariableSystem.Clear('ce_filter_mode')]",
    "[GetVariableSystem.Clear('ce_selected_event_slug')]",
    "[GetVariableSystem.Clear('ce_selected_event_viewer')]",
]
FILTER_ALL_VALUE = "all"
FILTER_ALL_OR_UNSET_EXPR = (
    f"Or(Not(GetVariableSystem.Exists('ce_filter_mode')), "
    f"GetVariableSystem.HasValue('ce_filter_mode', '{FILTER_ALL_VALUE}'))"
)
DEFAULT_SECTION_VALUE = "0"
GAME_START_YEAR = 1337
GAME_START_MONTH = 1
SELECTED_EVENT_NATIVE_EFFECTS_VAR = "ce_selected_event_native_effects"
SELECTED_EVENT_HAS_OPTIONS_VAR = "ce_selected_event_has_option_effects"
SELECTED_EVENT_IMMEDIATE_EFFECT_VAR = "ce_selected_event_immediate_effect"
SELECTED_EVENT_AGE_ICON_VAR = "ce_selected_event_age_icon"
RUNTIME_RESOLVED_FOR_VAR = "ce_runtime_resolved_for"
RUNTIME_RESOLVED_TAG_VAR = "ce_resolved_runtime_tag"
RUNTIME_UNMATCHED_TAG_VAR = "ce_runtime_unmatched_tag"
RUNTIME_READY_FOR_VAR = "ce_runtime_resolution_ready_for"
PLAYER_CURRENT_YEAR_EXPR = "Player.MakeScope.GetVariable('ce_current_year').GetValue"
PLAYER_CURRENT_MONTH_EXPR = "Player.MakeScope.GetVariable('ce_current_month').GetValue"
PLAYER_DATE_READY_EXPR = (
    "And(Player.MakeScope.GetVariable('ce_current_year').IsSet, "
    "Player.MakeScope.GetVariable('ce_current_month').IsSet)"
)
DEFAULT_AGE_BUCKETS = (
    {
        "value": "0",
        "id": "age_1_traditions",
        "title": "AGE_OF_TRADITIONS",
        "icon": "gfx/interface/icons/age/age_1_traditions.dds",
        "tab_label": "I",
        "year_start": 1,
        "year_end": 1399,
    },
    {
        "value": "1",
        "id": "age_2_renaissance",
        "title": "AGE_OF_RENAISSANCE",
        "icon": "gfx/interface/icons/age/age_2_renaissance.dds",
        "tab_label": "II",
        "year_start": 1400,
        "year_end": 1443,
    },
    {
        "value": "2",
        "id": "age_3_discovery",
        "title": "AGE_OF_DISCOVERY",
        "icon": "gfx/interface/icons/age/age_3_discovery.dds",
        "tab_label": "III",
        "year_start": 1444,
        "year_end": 1529,
    },
    {
        "value": "3",
        "id": "age_4_reformation",
        "title": "AGE_OF_REFORMATION",
        "icon": "gfx/interface/icons/age/age_4_reformation.dds",
        "tab_label": "IV",
        "year_start": 1530,
        "year_end": 1599,
    },
    {
        "value": "4",
        "id": "age_5_absolutism",
        "title": "AGE_OF_ABSOLUTISM",
        "icon": "gfx/interface/icons/age/age_5_absolutism.dds",
        "tab_label": "V",
        "year_start": 1600,
        "year_end": 1699,
    },
    {
        "value": "5",
        "id": "age_6_revolutions",
        "title": "AGE_OF_REVOLUTIONS",
        "icon": "gfx/interface/icons/age/age_6_revolutions.dds",
        "tab_label": "VI",
        "year_start": 1700,
        "year_end": None,
    },
)
AGE_BUCKETS = tuple({**bucket} for bucket in DEFAULT_AGE_BUCKETS)
AGE_HEADER_PATTERN = re.compile(r"^([A-Za-z0-9_]+)\s*=\s*\{")
AGE_YEAR_PATTERN = re.compile(r"^year\s*=\s*(\d+)\b")


class GuiWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def line(self, level: int = 0, text: str = "") -> None:
        if text:
            indent = "\t" * level
            self.lines.append(f"{indent}{text}")
        else:
            self.lines.append("")

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"


def combine_expr(operator: str, parts: list[str]) -> str:
    """Combine GUI expressions into a nested binary function call."""
    filtered = [part for part in parts if part]
    if not filtered:
        return ""
    expr = filtered[0]
    for part in filtered[1:]:
        expr = f"{operator}({expr}, {part})"
    return expr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate country event GUI files from data/country_events_registry.json."
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"Registry JSON path. Default: {DEFAULT_REGISTRY}",
    )
    parser.add_argument(
        "--game-root",
        type=Path,
        default=Path.cwd(),
        help="Europa Universalis V install root used to resolve age boundaries.",
    )
    parser.add_argument(
        "--skip-external-mods",
        action="store_true",
        help="Resolve age boundaries from the base game only.",
    )
    parser.add_argument(
        "--extra-mod-root",
        type=Path,
        action="append",
        default=[],
        help="Additional mod root to scan for age overrides. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Fallback GUI path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--windows-dir",
        type=Path,
        default=DEFAULT_WINDOWS_DIR,
        help=f"Per-country GUI directory. Default: {DEFAULT_WINDOWS_DIR}",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any generated output differs from disk.",
    )
    return parser.parse_args()


def group_tag(group: dict[str, object]) -> str:
    tags = group.get("country_tags", [])
    if len(tags) != 1:
        raise ValueError(
            f"Group {group.get('id')} must contain exactly one country tag, found {tags!r}."
        )
    return str(tags[0])


def age_dir_from_game_root(game_root: Path) -> Path | None:
    candidate = game_root / "game" / "in_game" / "common" / "age"
    if candidate.is_dir():
        return candidate
    direct_candidate = game_root / "in_game" / "common" / "age"
    if direct_candidate.is_dir():
        return direct_candidate
    return None


def iter_age_definition_dirs(
    game_root: Path,
    *,
    skip_external_mods: bool,
    extra_mod_roots: list[Path],
) -> list[Path]:
    game_root = Path(game_root)
    age_dirs: list[Path] = []
    seen: set[Path] = set()

    def add_candidate(root: Path) -> None:
        age_dir = age_dir_from_game_root(root.resolve())
        if age_dir is None:
            return
        resolved = age_dir.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        age_dirs.append(resolved)

    add_candidate(game_root)

    if not skip_external_mods:
        extra_roots = [Path(path).resolve() for path in extra_mod_roots]
        for source in discover_external_mod_sources(game_root, extra_roots):
            add_candidate(source.root)

    return age_dirs


def parse_age_years_from_file(path: Path, expected_ids: set[str]) -> dict[str, int]:
    years: dict[str, int] = {}
    current_id: str | None = None
    depth = 0

    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if current_id is None:
            header_match = AGE_HEADER_PATTERN.match(line)
            if header_match:
                block_id = header_match.group(1)
                if block_id in expected_ids:
                    current_id = block_id
                    depth = line.count("{") - line.count("}")
                    if depth <= 0:
                        current_id = None
                        depth = 0
            continue

        if depth == 1:
            year_match = AGE_YEAR_PATTERN.match(line)
            if year_match and current_id not in years:
                years[current_id] = int(year_match.group(1))

        depth += line.count("{") - line.count("}")
        if depth <= 0:
            current_id = None
            depth = 0

    return years


def load_age_buckets(
    game_root: Path,
    *,
    skip_external_mods: bool,
    extra_mod_roots: list[Path],
) -> tuple[dict[str, object], ...]:
    age_dirs = iter_age_definition_dirs(
        game_root,
        skip_external_mods=skip_external_mods,
        extra_mod_roots=extra_mod_roots,
    )
    if not age_dirs:
        return tuple({**bucket} for bucket in DEFAULT_AGE_BUCKETS)

    expected_ids = {str(bucket["id"]) for bucket in DEFAULT_AGE_BUCKETS}
    parsed_years: dict[str, int] = {}
    for age_dir in age_dirs:
        for path in sorted(age_dir.glob("*.txt")):
            parsed_years.update(parse_age_years_from_file(path, expected_ids))

    buckets = [{**bucket} for bucket in DEFAULT_AGE_BUCKETS]
    for bucket in buckets:
        bucket_id = str(bucket["id"])
        if bucket_id in parsed_years:
            bucket["year_start"] = parsed_years[bucket_id]

    for index, bucket in enumerate(buckets):
        if index + 1 < len(buckets):
            bucket["year_end"] = int(buckets[index + 1]["year_start"]) - 1
        else:
            bucket["year_end"] = None

    return tuple(buckets)


def validate_groups(registry_data: dict[str, object]) -> list[dict[str, object]]:
    groups = registry_data.get("groups", [])
    if not isinstance(groups, list):
        raise ValueError("Registry JSON must contain a top-level 'groups' list.")

    expected_groups = registry_data.get("summary", {}).get("groups")
    if isinstance(expected_groups, int) and expected_groups != len(groups):
        raise ValueError(
            f"Registry summary says {expected_groups} groups, but found {len(groups)} actual groups."
        )

    seen_tags: set[str] = set()
    for group in groups:
        tag = group_tag(group)
        if tag in seen_tags:
            raise ValueError(f"Duplicate country tag in registry: {tag}")
        seen_tags.add(tag)

    seen_runtime_keys: set[str] = set()
    for group in groups:
        for runtime_key in group_runtime_keys(group, seen_tags):
            if runtime_key in seen_runtime_keys:
                raise ValueError(f"Duplicate runtime country key in registry output: {runtime_key}")
            seen_runtime_keys.add(runtime_key)
    return groups


def to_gui_vfs_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(IN_GAME_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"Path must be inside {IN_GAME_ROOT}: {path}") from exc


def resolve_default_entry(group: dict[str, object]) -> tuple[dict[str, object] | None, str]:
    default_id = group.get("default_event_id")
    sections = group.get("sections", [])

    if default_id:
        for section in sections:
            for entry in section.get("entries", []):
                if entry.get("id") == default_id:
                    return entry, str(age_bucket_for_entry(entry)["value"])

    for section in sections:
        entries = section.get("entries", [])
        if entries:
            return entries[0], str(age_bucket_for_entry(entries[0])["value"])

    return None, DEFAULT_SECTION_VALUE


def parse_date_parts(value: object) -> tuple[int, int, int]:
    parts = str(value or "").split(".")

    def parse_part(index: int, default: int) -> int:
        try:
            return int(parts[index])
        except (IndexError, TypeError, ValueError):
            return default

    return parse_part(0, 1), parse_part(1, 1), parse_part(2, 1)


def age_bucket_for_year(year: int) -> dict[str, object]:
    for bucket in AGE_BUCKETS:
        year_end = bucket["year_end"]
        if year >= bucket["year_start"] and (year_end is None or year <= year_end):
            return bucket
    return AGE_BUCKETS[-1]


def age_bucket_for_entry(entry: dict[str, object]) -> dict[str, object]:
    year, _, _ = parse_date_parts(entry.get("date_from"))
    return age_bucket_for_year(year)


def build_age_buckets(group: dict[str, object]) -> list[dict[str, object]]:
    bucket_entries: dict[str, list[dict[str, object]]] = {bucket["value"]: [] for bucket in AGE_BUCKETS}
    for section in group.get("sections", []):
        for entry in section.get("entries", []):
            bucket = age_bucket_for_entry(entry)
            bucket_entries[str(bucket["value"])].append(entry)

    buckets: list[dict[str, object]] = []
    for bucket in AGE_BUCKETS:
        entries = bucket_entries[str(bucket["value"])]
        if not entries:
            continue
        entries.sort(key=lambda entry: (entry.get("date_from", ""), entry.get("id", "")))
        buckets.append({**bucket, "entries": entries})
    return buckets


def resolve_bucket_default_entry(
    group_tag_value: str,
    age_bucket: dict[str, object],
) -> dict[str, object] | None:
    entries = age_bucket.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return None

    for entry in entries:
        source_tags = entry_string_list(entry, "source_tags")
        if not source_tags or group_tag_value in source_tags:
            return entry

    return entries[0]


def fixed_point(value: int) -> str:
    return f"'(CFixedPoint){value}'"


def bool_expr(value: bool) -> str:
    return (
        "EqualTo_int32('(int32)1', '(int32)1')"
        if value
        else "EqualTo_int32('(int32)1', '(int32)0')"
    )


def fired_variable_name(entry: dict[str, object]) -> str:
    slug = str(entry.get("slug", "")).strip().lower()
    return f"ce_fired_{slug}"


def viewer_trigger_name(entry: dict[str, object]) -> str:
    slug = str(entry.get("slug", "")).strip().lower()
    return f"{slug}_viewer"


def selected_option_effect_var(index: int) -> str:
    return f"ce_selected_event_option_{index}_effect"


def selected_option_title_loc_var(index: int) -> str:
    return f"ce_selected_event_option_{index}_title_loc"


def effect_runtime_var_names(max_option_slots: int) -> list[str]:
    names = [
        SELECTED_EVENT_AGE_ICON_VAR,
        SELECTED_EVENT_NATIVE_EFFECTS_VAR,
        SELECTED_EVENT_HAS_OPTIONS_VAR,
        SELECTED_EVENT_IMMEDIATE_EFFECT_VAR,
    ]
    for index in range(max_option_slots):
        names.append(selected_option_effect_var(index))
        names.append(selected_option_title_loc_var(index))
    return names


def entry_string_list(entry: dict[str, object], key: str) -> list[str]:
    value = entry.get(key, [])
    if not isinstance(value, list):
        return []
    return [
        str(item).strip().upper()
        for item in value
        if str(item).strip()
    ]


def lineage_variable_name(tag: str) -> str:
    return f"ce_had_tag_{str(tag).strip().upper()}"


def window_close_actions(max_option_slots: int) -> list[str]:
    return WINDOW_BASE_CLOSE_ACTIONS + [
        f"[GetVariableSystem.Clear('{name}')]"
        for name in effect_runtime_var_names(max_option_slots)
    ]


def build_current_before_expr(year: int, month: int) -> str:
    return (
        f"Or(LessThan_CFixedPoint({PLAYER_CURRENT_YEAR_EXPR}, {fixed_point(year)}), "
        f"And(EqualTo_CFixedPoint({PLAYER_CURRENT_YEAR_EXPR}, {fixed_point(year)}), "
        f"LessThan_CFixedPoint({PLAYER_CURRENT_MONTH_EXPR}, {fixed_point(month)})))"
    )


def build_current_after_expr(year: int, month: int) -> str:
    return (
        f"Or(GreaterThan_CFixedPoint({PLAYER_CURRENT_YEAR_EXPR}, {fixed_point(year)}), "
        f"And(EqualTo_CFixedPoint({PLAYER_CURRENT_YEAR_EXPR}, {fixed_point(year)}), "
        f"GreaterThan_CFixedPoint({PLAYER_CURRENT_MONTH_EXPR}, {fixed_point(month)})))"
    )


def build_status_exprs(entry: dict[str, object]) -> dict[str, str]:
    start_year, start_month, _ = parse_date_parts(entry.get("date_from"))
    end_year, end_month, _ = parse_date_parts(entry.get("date_to"))
    upcoming_core = build_current_before_expr(start_year, start_month)
    expired_core = build_current_after_expr(end_year, end_month)
    fallback_upcoming = (start_year, start_month) > (GAME_START_YEAR, GAME_START_MONTH)
    fallback_expired = (end_year, end_month) < (GAME_START_YEAR, GAME_START_MONTH)
    fallback_active = not fallback_upcoming and not fallback_expired
    return {
        "ready": PLAYER_DATE_READY_EXPR,
        "upcoming": f"And({PLAYER_DATE_READY_EXPR}, {upcoming_core})",
        "active": f"And3({PLAYER_DATE_READY_EXPR}, Not({upcoming_core}), Not({expired_core}))",
        "expired": f"And({PLAYER_DATE_READY_EXPR}, {expired_core})",
        "fallback_upcoming": bool_expr(fallback_upcoming),
        "fallback_active": bool_expr(fallback_active),
        "fallback_expired": bool_expr(fallback_expired),
    }


def build_filter_match_expr(entry: dict[str, object]) -> str:
    status_exprs = build_status_exprs(entry)
    fired_expr = (
        f"GreaterThan_CFixedPoint(Player.MakeScope.ScriptValue('{fired_variable_name(entry)}'), "
        f"{fixed_point(0)})"
    )
    filter_all = f"GetVariableSystem.HasValue('ce_filter_mode', '{FILTER_ALL_VALUE}')"
    filter_available = (
        "And3(GetVariableSystem.HasValue('ce_filter_mode', 'available'), "
        f"Not({fired_expr}), "
        f"Or(And(Not({status_exprs['ready']}), {status_exprs['fallback_active']}), "
        f"{status_exprs['active']}))"
    )
    filter_upcoming = (
        "And3(GetVariableSystem.HasValue('ce_filter_mode', 'upcoming'), "
        f"Not({fired_expr}), "
        f"Or(And(Not({status_exprs['ready']}), {status_exprs['fallback_upcoming']}), "
        f"{status_exprs['upcoming']}))"
    )
    filter_expired = (
        "And3(GetVariableSystem.HasValue('ce_filter_mode', 'expired'), "
        f"Not({fired_expr}), "
        f"Or(And(Not({status_exprs['ready']}), {status_exprs['fallback_expired']}), "
        f"{status_exprs['expired']}))"
    )
    filter_fired = (
        "And("
        "GetVariableSystem.HasValue('ce_filter_mode', 'fired'), "
        f"{fired_expr})"
    )
    return (
        f"And(IsPlayerValid, Or5({filter_all}, "
        f"{filter_available}, "
        f"{filter_upcoming}, "
        f"{filter_expired}, "
        f"{filter_fired}))"
    )


def build_lineage_match_expr(group_tag_value: str, entry: dict[str, object]) -> str:
    source_tags = entry_string_list(entry, "source_tags")
    if not source_tags or group_tag_value in source_tags:
        return bool_expr(True)

    lineage_tags = entry_string_list(entry, "lineage_tags")
    if not lineage_tags:
        return bool_expr(False)

    lineage_exprs = [
        f"Player.MakeScope.GetVariable('{lineage_variable_name(tag)}').IsSet"
        for tag in lineage_tags
    ]
    return combine_expr("Or", lineage_exprs) or bool_expr(False)


def build_entry_visible_expr(group_tag_value: str, entry: dict[str, object]) -> str:
    return combine_expr(
        "And",
        [
            build_lineage_match_expr(group_tag_value, entry),
            build_filter_match_expr(entry),
        ],
    )


def build_entry_selectable_expr(group_tag_value: str, entry: dict[str, object]) -> str:
    return combine_expr(
        "And",
        [
            "IsPlayerValid",
            build_lineage_match_expr(group_tag_value, entry),
        ],
    )


def entry_option_effects(entry: dict[str, object]) -> list[dict[str, str]]:
    value = entry.get("option_effects", [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def max_option_effect_slots(groups: list[dict[str, object]]) -> int:
    max_slots = 0
    for group in groups:
        for section in group.get("sections", []):
            for entry in section.get("entries", []):
                max_slots = max(max_slots, len(entry_option_effects(entry)))
    return max_slots


def emit_event_selection_actions(
    writer: GuiWriter,
    level: int,
    entry: dict[str, object],
    *,
    keyword: str,
    max_option_slots: int,
) -> None:
    slug = str(entry["slug"])
    age_bucket = age_bucket_for_entry(entry)
    viewer_trigger = str(entry.get("viewer_trigger", "")).strip()
    immediate_effect = str(entry.get("immediate_effect", "")).strip()
    option_effects = entry_option_effects(entry)

    writer.line(
        level,
        f'{keyword} = "[GetVariableSystem.Set(\'ce_selected_event_slug\', \'{slug}\')]"',
    )
    writer.line(level, f'{keyword} = "[GetVariableSystem.Clear(\'ce_selected_event_viewer\')]"')
    if viewer_trigger:
        writer.line(
            level,
            f'{keyword} = "[GetVariableSystem.Set(\'ce_selected_event_viewer\', \'{viewer_trigger}\')]"',
        )
    for var_name in effect_runtime_var_names(max_option_slots):
        writer.line(level, f'{keyword} = "[GetVariableSystem.Clear(\'{var_name}\')]"')
    writer.line(
        level,
        f'{keyword} = "[GetVariableSystem.Set(\'ce_active_sec\', \'{age_bucket["value"]}\')]"',
    )
    writer.line(
        level,
        f'{keyword} = "[GetVariableSystem.Set(\'{SELECTED_EVENT_AGE_ICON_VAR}\', \'{age_bucket["icon"]}\')]"',
    )

    if immediate_effect or option_effects:
        writer.line(
            level,
            f'{keyword} = "[GetVariableSystem.Set(\'{SELECTED_EVENT_NATIVE_EFFECTS_VAR}\', \'1\')]"',
        )
    if immediate_effect:
        writer.line(
            level,
            f'{keyword} = "[GetVariableSystem.Set(\'{SELECTED_EVENT_IMMEDIATE_EFFECT_VAR}\', \'{immediate_effect}\')]"',
        )
    if option_effects:
        writer.line(
            level,
            f'{keyword} = "[GetVariableSystem.Set(\'{SELECTED_EVENT_HAS_OPTIONS_VAR}\', \'1\')]"',
        )
    for slot_index, option in enumerate(option_effects):
        title_loc = str(option.get("title_loc", "")).strip()
        effect_name = str(option.get("effect", "")).strip()
        if title_loc:
            writer.line(
                level,
                f'{keyword} = "[GetVariableSystem.Set(\'{selected_option_title_loc_var(slot_index)}\', \'{title_loc}\')]"',
            )
        if effect_name:
            writer.line(
                level,
                f'{keyword} = "[GetVariableSystem.Set(\'{selected_option_effect_var(slot_index)}\', \'{effect_name}\')]"',
            )


def emit_clear_selected_event_actions(
    writer: GuiWriter,
    level: int,
    *,
    keyword: str,
    max_option_slots: int,
) -> None:
    writer.line(level, f'{keyword} = "[GetVariableSystem.Clear(\'ce_selected_event_slug\')]"')
    writer.line(level, f'{keyword} = "[GetVariableSystem.Clear(\'ce_selected_event_viewer\')]"')
    for var_name in effect_runtime_var_names(max_option_slots):
        writer.line(level, f'{keyword} = "[GetVariableSystem.Clear(\'{var_name}\')]"')


def emit_filter_bar(writer: GuiWriter, level: int, *, max_option_slots: int) -> None:
    writer.line(level, "hbox = {")
    writer.line(level + 1, "layoutpolicy_horizontal = expanding")
    writer.line(level + 1, "spacing = 4")
    writer.line(level + 1, "ignoreinvisible = yes")
    writer.line()

    filter_buttons = [
        ("all", "COUNTRY_EVENTS_FILTER_ALL"),
        ("available", "COUNTRY_EVENTS_FILTER_AVAILABLE"),
        ("upcoming", "COUNTRY_EVENTS_FILTER_UPCOMING"),
        ("expired", "COUNTRY_EVENTS_FILTER_EXPIRED"),
        ("fired", "COUNTRY_EVENTS_FILTER_FIRED"),
    ]

    for value, loc_key in filter_buttons:
        down_expr = (
            f"GetVariableSystem.HasValue('ce_filter_mode', '{FILTER_ALL_VALUE}')"
            if value == "all"
            else f"GetVariableSystem.HasValue('ce_filter_mode', '{value}')"
        )

        writer.line(level + 1, "button_secondary_tab_alt = {")
        writer.line(level + 2, "layoutpolicy_horizontal = expanding")
        writer.line(level + 2, "minimumsize = { -1 30 }")
        if value == "all":
            writer.line(
                level + 2,
                f'onclick = "[GetVariableSystem.Set(\'ce_filter_mode\', \'{FILTER_ALL_VALUE}\')]"',
            )
        else:
            writer.line(
                level + 2,
                f'onclick = "[GetVariableSystem.Set(\'ce_filter_mode\', \'{value}\')]"',
            )
        emit_clear_selected_event_actions(
            writer,
            level + 2,
            keyword="onclick",
            max_option_slots=max_option_slots,
        )
        writer.line(level + 2, f'down = "[{down_expr}]"')
        writer.line(level + 2, 'blockoverride "tab_text" {')
        writer.line(level + 3, f'text = "{loc_key}"')
        writer.line(level + 3, "fontsize = 12")
        writer.line(level + 2, "}")
        writer.line(level + 1, "}")
        writer.line()

    writer.line(level, "}")


def emit_not_curated_card(writer: GuiWriter, level: int, always_visible: bool) -> None:
    writer.line(level, "vbox = {")
    if not always_visible:
        writer.line(
            level + 1,
            'visible = "[And(IsPlayerValid, Not(EqualTo_string(Localize(Concatenate(\'CE_HAS_\', Player.GetTag)), \'1\')))]"',
        )
    writer.line(level + 1, "layoutpolicy_horizontal = expanding")
    writer.line(level + 1, "using = bg_paper_card")
    writer.line(level + 1, "margin = { 14 12 }")
    writer.line(level + 1, "spacing = 10")
    writer.line()
    writer.line(level + 1, "text_single = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, "using = Font_Type_Headers")
    writer.line(level + 2, 'default_format = "#yellow_titles"')
    writer.line(level + 2, 'text = "COUNTRY_EVENTS_NOT_CURATED_TITLE"')
    writer.line(level + 1, "}")
    writer.line()
    writer.line(level + 1, "text_multi = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, 'text = "COUNTRY_EVENTS_NOT_CURATED_DESC"')
    writer.line(level + 2, "multiline = yes")
    writer.line(level + 2, "autoresize = yes")
    writer.line(level + 2, 'default_format = "#color_light_gray"')
    writer.line(level + 1, "}")
    writer.line(level, "}")


def group_has_native_tag_content(group: dict[str, object]) -> bool:
    tag = group_tag(group)
    for section in group.get("sections", []):
        for entry in section.get("entries", []):
            if tag in entry_string_list(entry, "source_tags"):
                return True
    return False


def emit_no_native_tag_notice(writer: GuiWriter, level: int) -> None:
    writer.line(level, "vbox = {")
    writer.line(level + 1, "layoutpolicy_horizontal = expanding")
    writer.line(level + 1, "using = bg_paper_card")
    writer.line(level + 1, "margin = { 12 10 }")
    writer.line(level + 1, "spacing = 6")
    writer.line()
    writer.line(level + 1, "text_single = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, "using = Font_Type_Headers")
    writer.line(level + 2, 'default_format = "#yellow_titles"')
    writer.line(level + 2, 'text = "COUNTRY_EVENTS_NO_NATIVE_TAG_TITLE"')
    writer.line(level + 1, "}")
    writer.line()
    writer.line(level + 1, "text_multi = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, 'text = "COUNTRY_EVENTS_NO_NATIVE_TAG_DESC"')
    writer.line(level + 2, "multiline = yes")
    writer.line(level + 2, "autoresize = yes")
    writer.line(level + 2, 'default_format = "#color_light_gray"')
    writer.line(level + 1, "}")
    writer.line(level, "}")


def emit_group_widget(
    writer: GuiWriter,
    level: int,
    group: dict[str, object],
    *,
    include_tag_guard: bool,
    max_option_slots: int,
) -> None:
    tag = group_tag(group)
    has_native_tag_content = group_has_native_tag_content(group)
    age_buckets = build_age_buckets(group)
    default_entry, default_sec_value = resolve_default_entry(group)

    writer.line(level, "vbox = {")
    if include_tag_guard:
        writer.line(
            level + 1,
            f'visible = "[And(IsPlayerValid, EqualTo_string(Player.GetTag, \'{tag}\'))]"',
        )
    writer.line(level + 1, "using = layoutpolicy_expanding")
    writer.line(level + 1, "spacing = 6")
    writer.line(level + 1, "ignoreinvisible = yes")
    writer.line()

    writer.line(level + 1, "widget = {")
    writer.line(level + 2, "visible_at_creation = no")
    writer.line(level + 2, "ignore_layout = yes")
    writer.line(level + 2, "alwaystransparent = yes")
    writer.line(level + 2, "size = { 1 1 }")
    writer.line(level + 2, 'visible = "[Not(GetVariableSystem.Exists(\'ce_active_sec\'))]"')
    writer.line(level + 2, "state = {")
    writer.line(level + 3, "name = _show")
    writer.line(
        level + 3,
        f'on_start = "[GetVariableSystem.Set(\'ce_active_sec\', \'{default_sec_value}\')]"',
    )
    writer.line(level + 2, "}")
    writer.line(level + 1, "}")
    writer.line()

    if has_native_tag_content:
        for age_bucket in age_buckets:
            first_entry = resolve_bucket_default_entry(tag, age_bucket)
            if not first_entry:
                continue
            sec_value = str(age_bucket["value"])
            writer.line(level + 1, "widget = {")
            writer.line(level + 2, "visible_at_creation = no")
            writer.line(level + 2, "ignore_layout = yes")
            writer.line(level + 2, "alwaystransparent = yes")
            writer.line(level + 2, "size = { 1 1 }")
            writer.line(
                level + 2,
                (
                    f'visible = "[And3(Not(GetVariableSystem.Exists(\'ce_selected_event_slug\')), '
                    f'GetVariableSystem.HasValue(\'ce_active_sec\', \'{sec_value}\'), '
                    f'{FILTER_ALL_OR_UNSET_EXPR})]"'
                ),
            )
            writer.line(level + 2, "state = {")
            writer.line(level + 3, "name = _show")
            emit_event_selection_actions(
                writer,
                level + 3,
                first_entry,
                keyword="on_start",
                max_option_slots=max_option_slots,
            )
            writer.line(level + 2, "}")
            writer.line(level + 1, "}")
            writer.line()

    writer.line(level + 1, "hbox = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, "using = bg_card_header_01")
    writer.line(level + 2, "margin = { 4 0 }")
    writer.line(level + 2, "spacing = 4")
    writer.line(level + 2, "ignoreinvisible = yes")
    writer.line()

    for age_bucket in age_buckets:
        sec_value = str(age_bucket["value"])
        sec_visible_expr = f"GetVariableSystem.HasValue('ce_active_sec', '{sec_value}')"

        writer.line(level + 2, "button_secondary_tab_alt = {")
        writer.line(level + 3, "layoutpolicy_horizontal = expanding")
        writer.line(level + 3, "minimumsize = { -1 34 }")
        writer.line(
            level + 3,
            f"onclick = \"[GetVariableSystem.Set('ce_active_sec', '{sec_value}')]\"",
        )
        emit_clear_selected_event_actions(
            writer,
            level + 3,
            keyword="onclick",
            max_option_slots=max_option_slots,
        )
        writer.line(level + 3, f'down = "[{sec_visible_expr}]"')
        writer.line(level + 3, f'tooltip = "[Localize(\'{age_bucket["title"]}\')]"')
        writer.line(level + 3, "flowcontainer = {")
        writer.line(level + 4, "parentanchor = center")
        writer.line(level + 4, "position = { 0 4 }")
        writer.line(level + 4, "spacing = 0")
        writer.line(level + 4, "icon = {")
        writer.line(level + 5, "size = { 22 22 }")
        writer.line(level + 5, f'texture = "{age_bucket["icon"]}"')
        writer.line(level + 5, "texture_density = 2")
        writer.line(level + 4, "}")
        writer.line(level + 3, "}")
        writer.line(level + 2, "}")
        writer.line()

    writer.line(level + 1, "}")
    writer.line()

    emit_filter_bar(writer, level + 1, max_option_slots=max_option_slots)
    writer.line()

    if not has_native_tag_content:
        emit_no_native_tag_notice(writer, level + 1)
        writer.line()

    writer.line(level + 1, "scrollarea = {")
    writer.line(level + 2, "using = layoutpolicy_expanding")
    writer.line(level + 2, "scrollbarpolicy_vertical = as_needed")
    writer.line(level + 2, "scrollbarpolicy_horizontal = always_off")
    writer.line()
    writer.line(level + 2, "scrollbar_vertical = {")
    writer.line(level + 3, "using = Scrollbar_Vertical_Small")
    writer.line(level + 2, "}")
    writer.line()
    writer.line(level + 2, "scrollwidget = {")
    writer.line(level + 3, "vbox = {")
    writer.line(level + 4, "layoutpolicy_horizontal = expanding")
    writer.line(level + 4, "spacing = 2")
    writer.line(level + 4, "ignoreinvisible = yes")
    writer.line(level + 4, "margin = { 8 6 }")
    writer.line()

    for age_bucket in age_buckets:
        sec_value = str(age_bucket["value"])
        sec_visible_expr = f"GetVariableSystem.HasValue('ce_active_sec', '{sec_value}')"

        writer.line(level + 4, "vbox = {")
        writer.line(level + 5, "layoutpolicy_horizontal = expanding")
        writer.line(level + 5, "spacing = 2")
        writer.line(level + 5, "ignoreinvisible = yes")
        writer.line(level + 5, f'visible = "[{sec_visible_expr}]"')
        writer.line()

        for entry in age_bucket["entries"]:
            slug = entry["slug"]
            entry_visible_expr = build_entry_visible_expr(tag, entry)
            writer.line(level + 5, "vbox = {")
            writer.line(level + 6, "layoutpolicy_horizontal = expanding")
            writer.line(level + 6, "spacing = 0")
            writer.line(level + 6, "ignoreinvisible = yes")
            writer.line(level + 6, f'visible = "[{entry_visible_expr}]"')
            writer.line(level + 6, "button_secondary_tab_alt = {")
            writer.line(level + 7, "layoutpolicy_horizontal = expanding")
            writer.line(level + 7, "minimumsize = { -1 36 }")
            emit_event_selection_actions(
                writer,
                level + 7,
                entry,
                keyword="onclick",
                max_option_slots=max_option_slots,
            )
            writer.line(
                level + 7,
                f'down = "[GetVariableSystem.HasValue(\'ce_selected_event_slug\', \'{slug}\')]"',
            )
            writer.line(level + 7, 'blockoverride "tab_text" {')
            writer.line(level + 8, f'text = "{entry["title_loc"]}"')
            writer.line(level + 7, "}")
            writer.line(level + 6, "}")
            writer.line(level + 5, "}")
            writer.line()

        writer.line(level + 4, "}")
        writer.line()

    writer.line(level + 4, "expand = {}")
    writer.line(level + 3, "}")
    writer.line(level + 2, "}")
    writer.line(level + 1, "}")
    writer.line(level, "}")


def emit_section_card_start(
    writer: GuiWriter,
    level: int,
    *,
    title_value: str,
    icon_texture: str | None = None,
    visible_expr: str | None = None,
    header_using: str = "bg_card_header_01_geopolitics",
) -> None:
    writer.line(level, "vbox = {")
    if visible_expr:
        writer.line(level + 1, f'visible = "[{visible_expr}]"')
    writer.line(level + 1, "layoutpolicy_horizontal = expanding")
    writer.line(level + 1, "using = bg_paper_card_fancy")
    writer.line(level + 1, "spacing = 0")
    writer.line()
    writer.line(level + 1, "widget = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, "size = { -1 34 }")
    writer.line(level + 2, f"using = {header_using}")
    writer.line()
    writer.line(level + 2, "hbox = {")
    writer.line(level + 3, "layoutpolicy_horizontal = expanding")
    writer.line(level + 3, "margin = { 10 0 }")
    writer.line(level + 3, f"spacing = {6 if icon_texture else 0}")
    if icon_texture:
        writer.line()
        writer.line(level + 3, "icon = {")
        writer.line(level + 4, "size = { 20 20 }")
        writer.line(level + 4, f'texture = "{icon_texture}"')
        writer.line(level + 4, "texture_density = 2")
        writer.line(level + 3, "}")
        writer.line()
    writer.line(level + 3, "text_single = {")
    writer.line(level + 4, "layoutpolicy_horizontal = expanding")
    writer.line(level + 4, "using = Font_Type_Headers")
    writer.line(level + 4, "fontsize = 13")
    writer.line(level + 4, 'default_format = "#yellow_titles"')
    writer.line(level + 4, f"text = {title_value}")
    writer.line(level + 3, "}")
    writer.line(level + 2, "}")
    writer.line(level + 1, "}")
    writer.line()
    writer.line(level + 1, "vbox = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, "margin = { 12 10 }")
    writer.line(level + 2, "spacing = 6")


def emit_section_card_end(writer: GuiWriter, level: int) -> None:
    writer.line(level + 1, "}")
    writer.line(level, "}")


def emit_native_option_button(
    writer: GuiWriter,
    level: int,
    *,
    visible_expr: str,
    title_value: str,
    effect_var_name: str,
) -> None:
    writer.line(level, "button_regular_diamond = {")
    writer.line(level + 1, f'visible = "[{visible_expr}]"')
    writer.line(level + 1, "layoutpolicy_horizontal = expanding")
    writer.line(level + 1, "size = { -1 36 }")
    writer.line(level + 1, "fontsize = 12")
    writer.line(level + 1, "using = snd_UI_event_option_generic")
    writer.line(level + 1, f"text = {title_value}")
    writer.line(level + 1, "tooltipwidget = {")
    writer.line(level + 2, "ContextualTooltipType = {")
    writer.line(level + 3, 'blockoverride "title_text" {')
    writer.line(level + 4, f"text = {title_value}")
    writer.line(level + 3, "}")
    writer.line(level + 3, 'blockoverride "title_icon" {')
    writer.line(level + 4, "icon = {")
    writer.line(level + 5, "using = tooltip_title_icon_size")
    writer.line(level + 5, 'texture = "gfx/interface/icons/flat_icons/effect.dds"')
    writer.line(level + 5, "texture_density = 2")
    writer.line(level + 4, "}")
    writer.line(level + 3, "}")
    writer.line(level + 3, 'blockoverride "concept_link" {')
    writer.line(level + 4, "text = [effect|e]")
    writer.line(level + 3, "}")
    writer.line(level + 3, 'blockoverride "tooltip_content" {')
    writer.line(level + 4, "TooltipScrolledConditionList = {")
    writer.line(level + 5, 'blockoverride "block_scrollarea" { maximumsize = { -1 360 } }')
    writer.line(
        level + 5,
        f'textcontext = "[ShowScriptedEffect(GetVariableSystem.Get(\'{effect_var_name}\'),PlayerScope.Self)]"',
    )
    writer.line(level + 4, "}")
    writer.line(level + 3, "}")
    writer.line(level + 2, "}")
    writer.line(level + 1, "}")
    writer.line(level, "}")


def emit_details_panel(
    writer: GuiWriter,
    level: int,
    *,
    max_option_slots: int,
) -> None:
    selected_slug_expr = "GetVariableSystem.Get('ce_selected_event_slug')"
    selected_age_icon_expr = (
        "Select_CString("
        f"GetVariableSystem.Exists('{SELECTED_EVENT_AGE_ICON_VAR}'), "
        f"GetVariableSystem.Get('{SELECTED_EVENT_AGE_ICON_VAR}'), "
        f"'{TAB_ICON_TEXTURE}')"
    )
    title_loc_expr = (
        "Concatenate(Concatenate('COUNTRY_EVENTS_AUTO_', "
        f"{selected_slug_expr}), '_TITLE')"
    )
    subtitle_loc_expr = (
        "Concatenate(Concatenate('COUNTRY_EVENTS_AUTO_', "
        f"{selected_slug_expr}), '_SUBTITLE')"
    )
    desc_loc_expr = (
        "Concatenate(Concatenate('COUNTRY_EVENTS_AUTO_', "
        f"{selected_slug_expr}), '_DESC')"
    )
    meta_loc_expr = (
        "Concatenate(Concatenate('COUNTRY_EVENTS_AUTO_', "
        f"{selected_slug_expr}), '_META')"
    )
    requirements_loc_expr = (
        "Concatenate(Concatenate('COUNTRY_EVENTS_AUTO_', "
        f"{selected_slug_expr}), '_REQUIREMENTS')"
    )
    outcomes_loc_expr = (
        "Concatenate(Concatenate('COUNTRY_EVENTS_AUTO_', "
        f"{selected_slug_expr}), '_OUTCOMES')"
    )

    writer.line(level, "vbox = {")
    writer.line(level + 1, "using = layoutpolicy_expanding")
    writer.line(level + 1, "layoutpolicy_vertical = expanding")
    writer.line(level + 1, "using = bg_paper_card")
    writer.line()

    writer.line(level + 1, "widget = {")
    writer.line(level + 2, "layoutpolicy_horizontal = expanding")
    writer.line(level + 2, "size = { -1 48 }")
    writer.line(level + 2, "using = bg_card_header_01_geopolitics")
    writer.line()
    writer.line(level + 2, "hbox = {")
    writer.line(level + 3, "layoutpolicy_horizontal = expanding")
    writer.line(level + 3, "margin = { 12 0 }")
    writer.line(level + 3, "spacing = 8")
    writer.line()
    writer.line(level + 3, "icon = {")
    writer.line(level + 4, "size = { 32 32 }")
    writer.line(level + 4, f'texture = "[{selected_age_icon_expr}]"')
    writer.line(level + 4, "texture_density = 2")
    writer.line(level + 3, "}")
    writer.line()
    writer.line(level + 3, "vbox = {")
    writer.line(level + 4, "layoutpolicy_horizontal = expanding")
    writer.line(level + 4, "spacing = 1")
    writer.line()
    writer.line(level + 4, "text_single = {")
    writer.line(level + 5, 'visible = "[Not(GetVariableSystem.Exists(\'ce_selected_event_slug\'))]"')
    writer.line(level + 5, "layoutpolicy_horizontal = expanding")
    writer.line(level + 5, "align = left|nobaseline")
    writer.line(level + 5, "using = Font_Type_Headers")
    writer.line(level + 5, 'default_format = "#yellow_titles"')
    writer.line(level + 5, 'text = "COUNTRY_EVENTS_SELECT_EVENT_TITLE"')
    writer.line(level + 4, "}")
    writer.line()
    writer.line(level + 4, "text_single = {")
    writer.line(level + 5, 'visible = "[GetVariableSystem.Exists(\'ce_selected_event_slug\')]"')
    writer.line(level + 5, "layoutpolicy_horizontal = expanding")
    writer.line(level + 5, "align = left|nobaseline")
    writer.line(level + 5, "using = Font_Type_Headers")
    writer.line(level + 5, 'default_format = "#yellow_titles"')
    writer.line(level + 5, f'text = "[Localize({title_loc_expr})]"')
    writer.line(level + 4, "}")
    writer.line()
    writer.line(level + 4, "text_single = {")
    writer.line(level + 5, 'visible = "[GetVariableSystem.Exists(\'ce_selected_event_slug\')]"')
    writer.line(level + 5, "layoutpolicy_horizontal = expanding")
    writer.line(level + 5, "align = left|nobaseline")
    writer.line(level + 5, "fontsize = 12")
    writer.line(level + 5, 'default_format = "#subtle_name"')
    writer.line(level + 5, f'text = "[Localize({subtitle_loc_expr})]"')
    writer.line(level + 4, "}")
    writer.line(level + 3, "}")
    writer.line(level + 2, "}")
    writer.line(level + 1, "}")
    writer.line()

    writer.line(level + 1, "scrollarea = {")
    writer.line(level + 2, "using = layoutpolicy_expanding")
    writer.line(level + 2, "scrollbarpolicy_vertical = as_needed")
    writer.line(level + 2, "scrollbarpolicy_horizontal = always_off")
    writer.line()
    writer.line(level + 2, "scrollbar_vertical = {")
    writer.line(level + 3, "using = Scrollbar_Vertical_Small")
    writer.line(level + 2, "}")
    writer.line()
    writer.line(level + 2, "scrollwidget = {")
    writer.line(level + 3, "vbox = {")
    writer.line(level + 4, "layoutpolicy_horizontal = expanding")
    writer.line(level + 4, "spacing = 8")
    writer.line(level + 4, "ignoreinvisible = yes")
    writer.line(level + 4, "margin = { 10 10 }")
    writer.line()

    writer.line(level + 4, "vbox = {")
    writer.line(level + 5, 'visible = "[Not(GetVariableSystem.Exists(\'ce_selected_event_slug\'))]"')
    writer.line(level + 5, "layoutpolicy_horizontal = expanding")
    writer.line(level + 5, "using = bg_paper_card_fancy")
    writer.line(level + 5, "margin = { 12 10 }")
    writer.line(level + 5, "spacing = 6")
    writer.line()
    writer.line(level + 5, "text_multi = {")
    writer.line(level + 6, "layoutpolicy_horizontal = expanding")
    writer.line(level + 6, 'text = "COUNTRY_EVENTS_SELECT_EVENT_DESC"')
    writer.line(level + 6, "multiline = yes")
    writer.line(level + 6, "autoresize = yes")
    writer.line(level + 6, 'default_format = "#color_light_gray"')
    writer.line(level + 5, "}")
    writer.line(level + 4, "}")
    writer.line()

    writer.line(level + 4, "vbox = {")
    writer.line(level + 5, 'visible = "[GetVariableSystem.Exists(\'ce_selected_event_slug\')]"')
    writer.line(level + 5, "layoutpolicy_horizontal = expanding")
    writer.line(level + 5, "spacing = 8")
    writer.line()

    writer.line(level + 5, "vbox = {")
    writer.line(level + 6, "layoutpolicy_horizontal = expanding")
    writer.line(level + 6, "using = bg_paper_card_fancy")
    writer.line(level + 6, "margin = { 12 10 }")
    writer.line(level + 6, "spacing = 6")
    writer.line()
    writer.line(level + 6, "text_multi = {")
    writer.line(level + 7, "layoutpolicy_horizontal = expanding")
    writer.line(level + 7, f'text = "[Localize({desc_loc_expr})]"')
    writer.line(level + 7, "multiline = yes")
    writer.line(level + 7, "autoresize = yes")
    writer.line(level + 7, 'default_format = "#color_light_gray"')
    writer.line(level + 6, "}")
    writer.line()
    writer.line(level + 6, "text_single = {")
    writer.line(level + 7, "layoutpolicy_horizontal = expanding")
    writer.line(level + 7, "fontsize = 12")
    writer.line(level + 7, 'default_format = "#subtle_name"')
    writer.line(level + 7, f'text = "[Localize({meta_loc_expr})]"')
    writer.line(level + 6, "}")
    writer.line(level + 5, "}")
    writer.line()

    writer.line(level + 5, "vbox = {")
    writer.line(
        level + 6,
        f'visible = "[GetVariableSystem.Exists(\'{SELECTED_EVENT_NATIVE_EFFECTS_VAR}\')]"',
    )
    writer.line(level + 6, "layoutpolicy_horizontal = expanding")
    writer.line(level + 6, "spacing = 8")
    writer.line(level + 6, "ignoreinvisible = yes")
    writer.line()

    emit_section_card_start(
        writer,
        level + 6,
        title_value='"DECLARE_WAR_CONFIRMATION_STABHIT"',
        visible_expr=f"GetVariableSystem.Exists('{SELECTED_EVENT_IMMEDIATE_EFFECT_VAR}')",
    )
    writer.line(level + 8, "TooltipRequirementsList = {")
    writer.line(level + 9, "layoutpolicy_horizontal = expanding")
    writer.line(
        level + 9,
        f'textcontext = "[ShowScriptedEffect(GetVariableSystem.Get(\'{SELECTED_EVENT_IMMEDIATE_EFFECT_VAR}\'),PlayerScope.Self)]"',
    )
    writer.line(level + 8, "}")
    emit_section_card_end(writer, level + 6)
    writer.line()

    emit_section_card_start(
        writer,
        level + 6,
        title_value='"EVENT_POSSIBLE_OPTIONS"',
    )
    writer.line(level + 8, "vbox = {")
    writer.line(level + 9, "layoutpolicy_horizontal = expanding")
    writer.line(level + 9, "spacing = 4")
    writer.line(level + 9, "ignoreinvisible = yes")
    writer.line()
    for option_index in range(max_option_slots):
        emit_native_option_button(
            writer,
            level + 9,
            visible_expr=f"GetVariableSystem.Exists('{selected_option_effect_var(option_index)}')",
            title_value=f'"[Localize(GetVariableSystem.Get(\'{selected_option_title_loc_var(option_index)}\'))]"',
            effect_var_name=selected_option_effect_var(option_index),
        )
        if option_index != max_option_slots - 1:
            writer.line()
    writer.line(level + 8, "}")
    writer.line()
    writer.line(level + 8, "text_single = {")
    writer.line(
        level + 9,
        f'visible = "[Not(GetVariableSystem.Exists(\'{SELECTED_EVENT_HAS_OPTIONS_VAR}\'))]"',
    )
    writer.line(level + 9, "layoutpolicy_horizontal = expanding")
    writer.line(level + 9, 'text = "NONE"')
    writer.line(level + 9, 'default_format = "#color_light_gray"')
    writer.line(level + 8, "}")
    emit_section_card_end(writer, level + 6)
    writer.line(level + 5, "}")
    writer.line()

    writer.line(level + 5, "vbox = {")
    writer.line(
        level + 6,
        f'visible = "[Not(GetVariableSystem.Exists(\'{SELECTED_EVENT_NATIVE_EFFECTS_VAR}\'))]"',
    )
    writer.line(level + 6, "layoutpolicy_horizontal = expanding")
    emit_section_card_start(
        writer,
        level + 6,
        title_value='"COUNTRY_EVENTS_OUTCOMES_LABEL"',
        icon_texture="gfx/interface/icons/flat_icons/effect.dds",
    )
    writer.line(level + 8, "text_multi = {")
    writer.line(level + 9, "layoutpolicy_horizontal = expanding")
    writer.line(level + 9, f'text = "[Localize({outcomes_loc_expr})]"')
    writer.line(level + 9, "multiline = yes")
    writer.line(level + 9, "autoresize = yes")
    writer.line(level + 9, 'default_format = "#color_light_gray"')
    writer.line(level + 8, "}")
    emit_section_card_end(writer, level + 6)
    writer.line(level + 5, "}")
    writer.line()

    emit_section_card_start(
        writer,
        level + 5,
        title_value='"COUNTRY_EVENTS_REQUIREMENTS_LABEL"',
        icon_texture="gfx/interface/icons/text_icons/trigger_yes.dds",
    )
    writer.line(level + 7, "TooltipRequirementsList = {")
    writer.line(
        level + 8,
        'visible = "[And(GetVariableSystem.Exists(\'ce_selected_event_slug\'), GetVariableSystem.Exists(\'ce_selected_event_viewer\'))]"',
    )
    writer.line(level + 8, "layoutpolicy_horizontal = expanding")
    writer.line(
        level + 8,
        'textcontext = "[ShowTriggerConditions(GetVariableSystem.Get(\'ce_selected_event_viewer\'),PlayerScope.Self)]"',
    )
    writer.line(level + 7, "}")
    writer.line(level + 7, "text_multi = {")
    writer.line(
        level + 8,
        'visible = "[And(GetVariableSystem.Exists(\'ce_selected_event_slug\'), Not(GetVariableSystem.Exists(\'ce_selected_event_viewer\')))]"',
    )
    writer.line(level + 8, "layoutpolicy_horizontal = expanding")
    writer.line(level + 8, f'text = "[Localize({requirements_loc_expr})]"')
    writer.line(level + 8, "multiline = yes")
    writer.line(level + 8, "autoresize = yes")
    writer.line(level + 8, 'default_format = "#color_light_gray"')
    writer.line(level + 7, "}")
    emit_section_card_end(writer, level + 5)
    writer.line(level + 4, "}")
    writer.line(level + 3, "}")
    writer.line(level + 2, "}")
    writer.line(level + 1, "}")
    writer.line(level, "}")


def build_country_events_types(
    *,
    type_block_name: str,
    body_type_name: str,
    groups: list[dict[str, object]],
    include_not_curated: bool,
    not_curated_always_visible: bool,
    include_tag_guard: bool,
    max_option_slots: int,
) -> str:
    writer = GuiWriter()
    writer.line(0, f"types {type_block_name}")
    writer.line(0, "{")
    writer.line(1, f"type {body_type_name} = vbox {{")
    writer.line()
    writer.line(2, "using = layoutpolicy_expanding")
    writer.line(2, "using = bg_main_inner_alt")
    writer.line(2, "using = window_main_tabs_margin_alt")
    writer.line(2, "ignoreinvisible = yes")
    writer.line(2, "spacing = 6")
    writer.line()
    if include_not_curated:
        emit_not_curated_card(writer, 2, always_visible=not_curated_always_visible)
        writer.line()
    for group in groups:
        emit_group_widget(
            writer,
            2,
            group,
            include_tag_guard=include_tag_guard,
            max_option_slots=max_option_slots,
        )
        writer.line()
    emit_details_panel(writer, 2, max_option_slots=max_option_slots)
    writer.line()
    writer.line(1, "}")
    writer.line(0, "}")
    return writer.render().rstrip("\n")


def build_window_block(body_type_name: str, *, max_option_slots: int) -> str:
    close_actions = window_close_actions(max_option_slots)
    effect_clear_on_start_block = "".join(
        f'\t\t\t\t\ton_start = "[GetVariableSystem.Clear(\'{name}\')]"' + "\n"
        for name in effect_runtime_var_names(max_option_slots)
    )
    close_onclick_block = "".join(
        f'\t\t\t\t\t\t\tonclick = "{action}"\n' for action in close_actions
    )
    close_shortcut_button = (
        "\t\t\tbutton = {\n"
        "\t\t\t\tvisible = yes\n"
        "\t\t\t\tvisible_at_creation = no\n"
        "\t\t\t\tignore_layout = yes\n"
        "\t\t\t\talwaystransparent = yes\n"
        "\t\t\t\tsize = { 1 1 }\n"
        "\t\t\t\tparentanchor = left|top\n"
        "\t\t\t\ttooltip_enabled = no\n"
        '\t\t\t\tinput_action = "close_window"\n'
        "\t\t\t\tuse_global_input_instance = yes\n"
        + "".join(f'\t\t\t\ton_input_action_shortcut = "{action}"\n' for action in close_actions)
        + "\t\t\t}\n"
    )
    return (
        "window = {\n"
        f'\tname = "{WINDOW_WIDGET_NAME}"\n'
        '\tdatacontext = "[GetVariableSystem]"\n'
        "\tusing = lateralview_left_setup\n"
        "\tmovable = no\n"
        "\n"
        "\tvbox = {\n"
        "\t\tsize = { 100% 100% }\n"
        "\t\tusing = lateralview_margins\n"
        "\n"
        "\t\twidget = {\n"
        "\t\t\tvisible = \"[GetVariableSystem.Exists('ce_window_pending_open')]\"\n"
        "\t\t\tvisible_at_creation = no\n"
        "\t\t\tignore_layout = yes\n"
        "\t\t\talwaystransparent = yes\n"
        "\t\t\tsize = { 1 1 }\n"
        "\t\t\twidget = {\n"
        "\t\t\t\tvisible = \"[Not(Or(LeftView.IsShown, LeftView.IsSideAttached))]\"\n"
        "\t\t\t\tvisible_at_creation = no\n"
        "\t\t\t\tignore_layout = yes\n"
        "\t\t\t\talwaystransparent = yes\n"
        "\t\t\t\tsize = { 1 1 }\n"
        "\t\t\t\tstate = {\n"
        "\t\t\t\t\tname = _show\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_window_pending_open')]\"\n"
        "\t\t\t\t}\n"
        "\t\t\t}\n"
        "\t\t}\n"
        "\n"
        "\t\twidget = {\n"
        "\t\t\tvisible = \"[And3(GetVariableSystem.Exists('ce_window_open'), GetVariableSystem.Exists('ce_open_tag'), Not(GetVariableSystem.Exists('ce_window_pending_open')))]\"\n"
        "\t\t\tvisible_at_creation = no\n"
        "\t\t\tignore_layout = yes\n"
        "\t\t\talwaystransparent = yes\n"
        "\t\t\tsize = { 1 1 }\n"
        "\t\t\twidget = {\n"
        "\t\t\t\tvisible = \"[Or(LeftView.IsShown, LeftView.IsSideAttached)]\"\n"
        "\t\t\t\tvisible_at_creation = no\n"
        "\t\t\t\tignore_layout = yes\n"
        "\t\t\t\talwaystransparent = yes\n"
        "\t\t\t\tsize = { 1 1 }\n"
        "\t\t\t\tstate = {\n"
        "\t\t\t\t\tname = _show\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_window_open')]\"\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_window_pending_open')]\"\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_open_tag')]\"\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_active_sec')]\"\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_filter_mode')]\"\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_selected_event_slug')]\"\n"
        "\t\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_selected_event_viewer')]\"\n"
        + effect_clear_on_start_block
        + "\t\t\t\t}\n"
        "\t\t\t}\n"
        "\t\t}\n"
        "\n"
        "\t\twidget = {\n"
        "\t\t\tvisible = \"[Not(IsPlayerValid)]\"\n"
        "\t\t\tvisible_at_creation = no\n"
        "\t\t\tignore_layout = yes\n"
        "\t\t\talwaystransparent = yes\n"
        "\t\t\tsize = { 1 1 }\n"
        "\t\t\tstate = {\n"
        "\t\t\t\tname = _show\n"
        "\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_window_open')]\"\n"
        "\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_window_pending_open')]\"\n"
        "\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_open_tag')]\"\n"
        "\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_active_sec')]\"\n"
        "\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_filter_mode')]\"\n"
        "\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_selected_event_slug')]\"\n"
        "\t\t\t\ton_start = \"[GetVariableSystem.Clear('ce_selected_event_viewer')]\"\n"
        + effect_clear_on_start_block
        + "\t\t\t}\n"
        "\t\t}\n"
        "\n"
        "\t\twidget = {\n"
        "\t\t\tvisible = \"[And3(IsPlayerValid, GetVariableSystem.Exists('ce_window_open'), GetVariableSystem.Exists('ce_open_tag'))]\"\n"
        "\t\t\tdatacontext = \"[GetPlayer]\"\n"
        "\t\t\tsize = { 100% 100% }\n"
        "\t\t\tusing = layoutpolicy_expanding\n"
        "\t\t\talwaystransparent = no\n"
        "\t\t\tallow_outside = yes\n"
        "\n"
        + close_shortcut_button
        + "\n"
        + "\t\t\twidget = {\n"
        + "\t\t\t\tvisible = \"[Not(GetVariableSystem.Exists('ce_filter_mode'))]\"\n"
        + "\t\t\t\tvisible_at_creation = no\n"
        + "\t\t\t\tignore_layout = yes\n"
        + "\t\t\t\talwaystransparent = yes\n"
        + "\t\t\t\tsize = { 1 1 }\n"
        + "\t\t\t\tstate = {\n"
        + "\t\t\t\t\tname = _show\n"
        + f"\t\t\t\t\ton_start = \"[GetVariableSystem.Set('ce_filter_mode', '{FILTER_ALL_VALUE}')]\"\n"
        + "\t\t\t\t}\n"
        + "\t\t\t}\n"
        + "\n"
        + "\t\t\tusing = bg_lateralview\n"
        + "\n"
        + "\t\t\tvbox = {\n"
        + "\t\t\t\tsize = { 100% 100% }\n"
        + "\t\t\t\twindow_header_alt = {\n"
        + '\t\t\t\t\tblockoverride "header_text" {\n'
        + '\t\t\t\t\t\ttext = "COUNTRY_EVENTS_HEADER"\n'
        + "\t\t\t\t\t}\n"
        + '\t\t\t\t\tblockoverride "window_header_alt_color_texture" {\n'
        + "\t\t\t\t\t\tusing = color_geopolitics_texture\n"
        + "\t\t\t\t\t}\n"
        + "\t\t\t\t}\n"
        + "\n"
        + "\t\t\t\thbox = {\n"
        + "\t\t\t\t\tusing = layoutpolicy_expanding\n"
        + "\n"
        + "\t\t\t\t\twidget = {\n"
        + "\t\t\t\t\t\tusing = layoutpolicy_expanding\n"
        + "\n"
        + "\t\t\t\t\t\tvbox = {\n"
        + "\t\t\t\t\t\t\tusing = layoutpolicy_expanding\n"
        + f"\t\t\t\t\t\t\t{body_type_name} = {{}}\n"
        + "\t\t\t\t\t\t}\n"
        + "\n"
        + "\t\t\t\t\t\twindow_bottom_paper_template = {}\n"
        + "\t\t\t\t\t}\n"
        + "\n"
        + "\t\t\t\t}\n"
        + "\t\t\t}\n"
        + "\n"
        + "\t\t\twidget = {\n"
        + "\t\t\t\tsize = { 100% 40 }\n"
        + "\n"
        + "\t\t\t\twidget = {\n"
        + "\t\t\t\t\tparentanchor = right\n"
        + "\t\t\t\t\tsize = { 40 40 }\n"
        + "\n"
        + "\t\t\t\t\tui_direction_button_holder_right = {}\n"
        + "\n"
        + "\t\t\t\t\tbutton_close_alt = {\n"
        + '\t\t\t\t\t\tblockoverride "close_onclick" {\n'
        + close_onclick_block
        + "\t\t\t\t\t\t}\n"
        + "\n"
        + '\t\t\t\t\t\tblockoverride "close_inputaction" {\n'
        + '\t\t\t\t\t\t\tinput_action = "close_window"\n'
        + "\t\t\t\t\t\t\tuse_global_input_instance = yes\n"
        + "\t\t\t\t\t\t}\n"
        + "\t\t\t\t\t}\n"
        + "\t\t\t\t}\n"
        + "\t\t\t}\n"
        + "\n"
        + "\t\t\twindow_bottom_paper_template = {}\n"
        + "\t\t}\n"
        + "\t}\n"
        + "}"
    )


def build_gui_file(
    *,
    type_block_name: str,
    body_type_name: str,
    groups: list[dict[str, object]],
    include_not_curated: bool,
    not_curated_always_visible: bool,
    include_tag_guard: bool,
    max_option_slots: int,
) -> str:
    parts = [
        build_country_events_types(
            type_block_name=type_block_name,
            body_type_name=body_type_name,
            groups=groups,
            include_not_curated=include_not_curated,
            not_curated_always_visible=not_curated_always_visible,
            include_tag_guard=include_tag_guard,
            max_option_slots=max_option_slots,
        ),
        build_window_block(body_type_name, max_option_slots=max_option_slots),
    ]
    return "\n\n".join(parts) + "\n"


def build_runtime_resolver_file(runtime_keys: list[str]) -> str:
    writer = GuiWriter()
    pending_open_base_expr = combine_expr(
        "And",
        [
            "GetVariableSystem.Exists('ce_window_open')",
            "GetVariableSystem.Exists('ce_window_pending_open')",
            "GetVariableSystem.Exists('ce_open_tag')",
            f"GetVariableSystem.Exists('{RUNTIME_READY_FOR_VAR}')",
            "EqualTo_string(GetVariableSystem.Get('ce_open_tag'), Player.GetTag)",
            f"EqualTo_string(GetVariableSystem.Get('{RUNTIME_READY_FOR_VAR}'), Player.GetTag)",
        ],
    )
    pending_resolved_expr = combine_expr(
        "And",
        [
            pending_open_base_expr,
            f"GetVariableSystem.Exists('{RUNTIME_RESOLVED_TAG_VAR}')",
        ],
    )
    pending_fallback_expr = combine_expr(
        "And",
        [
            pending_open_base_expr,
            f"GetVariableSystem.Exists('{RUNTIME_UNMATCHED_TAG_VAR}')",
            f"EqualTo_string(GetVariableSystem.Get('{RUNTIME_UNMATCHED_TAG_VAR}'), Player.GetTag)",
        ],
    )
    writer.line(0, "types CountryEventsRuntimeResolverTypes")
    writer.line(0, "{")
    writer.line(1, "type country_events_runtime_resolver = widget {")
    writer.line(2, "visible_at_creation = no")
    writer.line(2, "ignore_layout = yes")
    writer.line(2, "alwaystransparent = yes")
    writer.line(2, "size = { 1 1 }")
    writer.line(2, 'visible = "[IsPlayerValid]"')
    writer.line()
    writer.line(2, "widget = {")
    writer.line(3, "visible_at_creation = no")
    writer.line(3, "ignore_layout = yes")
    writer.line(3, "alwaystransparent = yes")
    writer.line(3, "size = { 1 1 }")
    writer.line(
        3,
        f'visible = "[Or(Not(GetVariableSystem.Exists(\'ce_last_seen_tag\')), Not(EqualTo_string(Player.GetTag, GetVariableSystem.Get(\'ce_last_seen_tag\'))))]"',
    )
    writer.line(3, "state = {")
    writer.line(4, "name = _show")
    writer.line(4, 'on_start = "[GetVariableSystem.Set(\'ce_last_seen_tag\', Player.GetTag)]"')
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Set(\'{RUNTIME_RESOLVED_FOR_VAR}\', Player.GetTag)]"',
    )
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Clear(\'{RUNTIME_RESOLVED_TAG_VAR}\')]"',
    )
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Set(\'{RUNTIME_UNMATCHED_TAG_VAR}\', Player.GetTag)]"',
    )
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Clear(\'{RUNTIME_READY_FOR_VAR}\')]"',
    )
    writer.line(3, "}")
    writer.line(2, "}")
    writer.line()

    for runtime_key in runtime_keys:
        writer.line(2, "widget = {")
        writer.line(3, "visible_at_creation = no")
        writer.line(3, "ignore_layout = yes")
        writer.line(3, "alwaystransparent = yes")
        writer.line(3, "size = { 1 1 }")
        writer.line(
            3,
            f'visible = "[And(GetVariableSystem.Exists(\'{RUNTIME_RESOLVED_FOR_VAR}\'), EqualTo_string(GetVariableSystem.Get(\'{RUNTIME_RESOLVED_FOR_VAR}\'), \'{runtime_key}\'), Or(Not(GetVariableSystem.Exists(\'{RUNTIME_RESOLVED_TAG_VAR}\')), Not(EqualTo_string(GetVariableSystem.Get(\'{RUNTIME_RESOLVED_TAG_VAR}\'), \'{runtime_key}\'))))]"',
        )
        writer.line(3, "state = {")
        writer.line(4, "name = _show")
        writer.line(
            4,
            f'on_start = "[GetVariableSystem.Set(\'{RUNTIME_RESOLVED_TAG_VAR}\', \'{runtime_key}\')]"',
        )
        writer.line(
            4,
            f'on_start = "[GetVariableSystem.Clear(\'{RUNTIME_UNMATCHED_TAG_VAR}\')]"',
        )
        writer.line(3, "}")
        writer.line(2, "}")
        writer.line()

    writer.line(2, "widget = {")
    writer.line(3, "visible_at_creation = no")
    writer.line(3, "ignore_layout = yes")
    writer.line(3, "alwaystransparent = yes")
    writer.line(3, "size = { 1 1 }")
    writer.line(
        3,
        f'visible = "[And(GetVariableSystem.Exists(\'{RUNTIME_RESOLVED_TAG_VAR}\'), Or(Not(GetVariableSystem.Exists(\'ce_last_display_tag\')), Not(EqualTo_string(GetVariableSystem.Get(\'ce_last_display_tag\'), GetVariableSystem.Get(\'{RUNTIME_RESOLVED_TAG_VAR}\')))))]"',
    )
    writer.line(3, "state = {")
    writer.line(4, "name = _show")
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Set(\'ce_last_display_tag\', GetVariableSystem.Get(\'{RUNTIME_RESOLVED_TAG_VAR}\'))]"',
    )
    writer.line(3, "}")
    writer.line(2, "}")
    writer.line()

    writer.line(2, "widget = {")
    writer.line(3, "visible_at_creation = no")
    writer.line(3, "ignore_layout = yes")
    writer.line(3, "alwaystransparent = yes")
    writer.line(3, "size = { 1 1 }")
    writer.line(
        3,
        f'visible = "[And(GetVariableSystem.Exists(\'{RUNTIME_RESOLVED_FOR_VAR}\'), Or(Not(GetVariableSystem.Exists(\'{RUNTIME_READY_FOR_VAR}\')), Not(EqualTo_string(GetVariableSystem.Get(\'{RUNTIME_READY_FOR_VAR}\'), GetVariableSystem.Get(\'{RUNTIME_RESOLVED_FOR_VAR}\')))))]"',
    )
    writer.line(3, "state = {")
    writer.line(4, "name = _show")
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Set(\'{RUNTIME_READY_FOR_VAR}\', GetVariableSystem.Get(\'{RUNTIME_RESOLVED_FOR_VAR}\'))]"',
    )
    writer.line(3, "}")
    writer.line(2, "}")
    writer.line()

    writer.line(2, "widget = {")
    writer.line(3, "visible_at_creation = no")
    writer.line(3, "ignore_layout = yes")
    writer.line(3, "alwaystransparent = yes")
    writer.line(3, "size = { 1 1 }")
    writer.line(3, f'visible = "[{pending_resolved_expr}]"')
    writer.line(3, "state = {")
    writer.line(4, "name = _show")
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Set(\'ce_display_tag\', GetVariableSystem.Get(\'{RUNTIME_RESOLVED_TAG_VAR}\'))]"',
    )
    writer.line(
        4,
        f'on_start = "[GetVariableSystem.Set(\'ce_last_display_tag\', GetVariableSystem.Get(\'{RUNTIME_RESOLVED_TAG_VAR}\'))]"',
    )
    writer.line(
        4,
        f'on_start = "[ExecuteConsoleCommand(\'gui.ClearWidgets {WINDOW_WIDGET_NAME}\')]"',
    )
    writer.line(
        4,
        f'on_start = "[ExecuteConsoleCommand(Concatenate(\'gui.CreateWidget gui/country_events_windows/country_events_window_\', Concatenate(GetVariableSystem.Get(\'{RUNTIME_RESOLVED_TAG_VAR}\'), \'.gui {WINDOW_WIDGET_NAME}\')))]"',
    )
    writer.line(4, 'on_start = "[GetVariableSystem.Clear(\'ce_window_pending_open\')]"')
    writer.line(3, "}")
    writer.line(2, "}")
    writer.line()

    writer.line(2, "widget = {")
    writer.line(3, "visible_at_creation = no")
    writer.line(3, "ignore_layout = yes")
    writer.line(3, "alwaystransparent = yes")
    writer.line(3, "size = { 1 1 }")
    writer.line(3, f'visible = "[{pending_fallback_expr}]"')
    writer.line(3, "state = {")
    writer.line(4, "name = _show")
    writer.line(4, 'on_start = "[GetVariableSystem.Clear(\'ce_display_tag\')]"')
    writer.line(
        4,
        f'on_start = "[ExecuteConsoleCommand(\'gui.ClearWidgets {WINDOW_WIDGET_NAME}\')]"',
    )
    writer.line(
        4,
        f'on_start = "[ExecuteConsoleCommand(\'gui.CreateWidget gui/country_events_lateralview.gui {WINDOW_WIDGET_NAME}\')]"',
    )
    writer.line(4, 'on_start = "[GetVariableSystem.Clear(\'ce_window_pending_open\')]"')
    writer.line(3, "}")
    writer.line(2, "}")
    writer.line(1, "}")
    writer.line(0, "}")
    return writer.render()


def build_generated_outputs(
    groups: list[dict[str, object]],
    *,
    fallback_path: Path,
    windows_dir: Path,
) -> dict[Path, str]:
    global_max_option_slots = max_option_effect_slots(groups)
    runtime_resolver_path = fallback_path.parent / "country_events_runtime_resolver.gui"
    outputs: dict[Path, str] = {
        fallback_path: build_gui_file(
            type_block_name="CountryEventsFallbackTypes",
            body_type_name="country_events_body_fallback",
            groups=[],
            include_not_curated=True,
            not_curated_always_visible=True,
            include_tag_guard=False,
            max_option_slots=global_max_option_slots,
        )
    }

    canonical_tags = {group_tag(group) for group in groups}
    runtime_keys: list[str] = []
    seen_runtime_keys: set[str] = set()

    for group in groups:
        for runtime_key in group_runtime_keys(group, canonical_tags):
            if runtime_key not in seen_runtime_keys:
                seen_runtime_keys.add(runtime_key)
                runtime_keys.append(runtime_key)
            outputs[windows_dir / f"{WINDOW_FILE_PREFIX}{runtime_key}.gui"] = build_gui_file(
                type_block_name=f"CountryEvents{runtime_key}Types",
                body_type_name=f"country_events_body_{runtime_key}",
                groups=[group],
                include_not_curated=False,
                not_curated_always_visible=False,
                include_tag_guard=False,
                max_option_slots=global_max_option_slots,
            )
    outputs[runtime_resolver_path] = build_runtime_resolver_file(runtime_keys)
    return outputs


def generated_window_glob(windows_dir: Path) -> list[Path]:
    if not windows_dir.exists():
        return []
    return sorted(windows_dir.glob(f"{WINDOW_FILE_PREFIX}*.gui"))


def check_outputs(outputs: dict[Path, str], windows_dir: Path) -> int:
    expected_paths = set(outputs)
    needs_update = False

    for path, expected_text in sorted(outputs.items()):
        current_text = path.read_text(encoding="utf-8") if path.exists() else ""
        if current_text != expected_text:
            print(f"Out of date: {path}")
            needs_update = True

    for stale_path in generated_window_glob(windows_dir):
        if stale_path not in expected_paths:
            print(f"Stale generated file: {stale_path}")
            needs_update = True

    if needs_update:
        return 1

    print(f"Up to date: {len(outputs)} generated GUI files")
    return 0


def write_outputs(outputs: dict[Path, str], windows_dir: Path) -> None:
    expected_paths = set(outputs)
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    for stale_path in generated_window_glob(windows_dir):
        if stale_path not in expected_paths:
            stale_path.unlink()


def main() -> int:
    args = parse_args()
    global AGE_BUCKETS

    registry_path = args.registry.resolve()
    fallback_path = args.output.resolve()
    windows_dir = args.windows_dir.resolve()

    if not registry_path.is_file():
        raise FileNotFoundError(f"Registry JSON not found: {registry_path}")

    AGE_BUCKETS = load_age_buckets(
        args.game_root.resolve(),
        skip_external_mods=args.skip_external_mods,
        extra_mod_roots=args.extra_mod_root,
    )
    registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    groups = validate_groups(registry_data)
    outputs = build_generated_outputs(groups, fallback_path=fallback_path, windows_dir=windows_dir)
    runtime_resolver_path = fallback_path.parent / "country_events_runtime_resolver.gui"

    if args.check:
        return check_outputs(outputs, windows_dir)

    write_outputs(outputs, windows_dir)

    event_count = registry_data.get("summary", {}).get("events", "unknown")
    print(f"Wrote fallback GUI: {fallback_path}")
    print(f"Wrote runtime resolver GUI: {runtime_resolver_path}")
    print(f"Wrote {len(outputs) - 2} curated country GUIs: {windows_dir}")
    print(f"Generated {len(groups)} country groups from registry ({event_count} events in summary).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
