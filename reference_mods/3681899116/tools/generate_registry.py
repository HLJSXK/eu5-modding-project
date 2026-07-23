#!/usr/bin/env python3
"""Generate country_events_registry.json from game event files.

Parses every .txt file in game/in_game/events/, extracts events
with dynamic_historical_event blocks, groups them by individual country
tag, and organises into century-based sections.

Also generates / updates auto localization entries for new events,
reading game loc files for titles and descriptions.

Usage:
    python generate_registry.py --game-root "C:/Program Files (x86)/Steam/steamapps/common/Europa Universalis V"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import generated_text_i18n as gti18n
from country_runtime_aliases import COUNTRY_SUCCESSOR_BUNDLES, FORMABLE_GEOGRAPHY_BUCKET_ALIASES

SCRIPT_PATH = Path(__file__).resolve()
MOD_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_REGISTRY = MOD_ROOT / "data" / "country_events_registry.json"
DEFAULT_LOC_DIR = MOD_ROOT / "main_menu" / "localization"
DEFAULT_BUILD_STATE = MOD_ROOT / "data" / "registry_build_state.json"
DEFAULT_BUILD_STATUS = MOD_ROOT / "data" / "registry_build_status.json"
DEFAULT_VIEWER_TRIGGERS = (
    MOD_ROOT
    / "in_game"
    / "common"
    / "scripted_triggers"
    / "country_events_runtime_requirements.txt"
)
DEFAULT_VIEWER_EFFECTS = (
    MOD_ROOT
    / "in_game"
    / "common"
    / "scripted_effects"
    / "country_events_runtime_effects.txt"
)
DEFAULT_LINEAGE_EFFECTS = (
    MOD_ROOT
    / "in_game"
    / "common"
    / "scripted_effects"
    / "country_events_runtime_lineage.txt"
)

LANGUAGES = [
    "braz_por", "english", "french", "german", "japanese",
    "korean", "polish", "russian", "simp_chinese", "spanish", "turkish",
]

ICON = "gfx/interface/icons/flat_icons/tabicons/info_flat_icon.dds"
STEAM_APP_ID = "3450310"
CURRENT_GAME_LOC: dict[str, str] = {}
SCRIPTED_EFFECT_DEFS: dict[str, list["ClausewitzNode"]] = {}
OPTION_EFFECT_METADATA_KEYS = {
    "ai_chance",
    "historical_option",
    "name",
    "trigger",
}
NON_GAMEPLAY_EFFECT_KEYS = OPTION_EFFECT_METADATA_KEYS | {
    "save_scope_as",
    "save_temporary_scope_as",
    "event_illustration_estate_effect",
    "set_variable",
    "remove_variable",
    "add_to_list",
    "ordered_in_list",
}
LOGIC_BLOCK_KEYS = {
    "and",
    "or",
    "not",
    "nor",
    "nand",
}
UNSAFE_RUNTIME_VIEWER_KEYS = {
    "c",
}
UNSAFE_RUNTIME_VIEWER_KEY_FRAGMENTS = (
    "raw_material",
)
UNSAFE_RUNTIME_VIEWER_VALUE_FRAGMENTS = (
    "raw_material",
    "target_character",
    "target_advisor",
    "robber_baron_province",
)
UNSAFE_RUNTIME_PREVIEW_KEYS = {
    "add_country_to_international_organization",
    "ai_will_select",
    "annex_country",
    "banish_character",
    "change_player",
    "change_religion",
    "change_religion_for_ruler_and_family",
    "create_country_from_cores_in_our_locations",
    "create_country_from_location",
    "declare_war_with_cb",
    "form_country",
    "international_organization",
    "kill_character",
    "kill_character_silently",
    "make_subject_of",
    "move_country",
    "remove_country_from_international_organization",
    "rename_location",
    "scope",
    "destroy_building",
    "create_holy_site",
    "set_capital",
    "set_new_ruler",
    "set_new_ruler_with_union_if_senior",
    "trigger_event",
    "trigger_event_non_silently",
    "trigger_event_silently",
    "while",
    "random",
    "random_list",
    "switch",
    "case",
}
UNSAFE_RUNTIME_PREVIEW_KEY_PREFIXES = (
    "add_country_to_international_organization",
    "change_religion",
    "create_country",
    "declare_war_with_cb",
    "international_organization:",
    "kill_character",
    "remove_country_from_international_organization",
    "set_capital",
    "set_new_ruler",
    "trigger_event",
)
UNSAFE_RUNTIME_PREVIEW_KEY_FRAGMENTS = (
    "variable",
    "_list",
    "list_size",
    "distance_to",
    "culture_percentage",
    "culture_group_percentage",
    "culture_population",
    "international_organization:",
    "religion_percentage",
)
UNSAFE_RUNTIME_PREVIEW_VALUE_FRAGMENTS = (
    "international_organization:",
    "raw_material",
    "target_character",
    "target_advisor",
    "robber_baron_province",
)
COMPLEX_RUNTIME_PREVIEW_KEY_PREFIXES = (
    "any_",
    "area:",
    "consort",
    "create_",
    "dynasty",
    "every_",
    "heir",
    "house",
    "location:",
    "ordered_",
    "province:",
    "random_",
    "region:",
    "ruler",
    "spouse",
)
PREVIEW_PARTIAL_EFFECT_TOOLTIP_KEY = "COUNTRY_EVENTS_PREVIEW_PARTIAL_EFFECTS"

PREVIEW_BOOTSTRAP_MUTATION_KEYS = {
    "annex_country",
    "banish_character",
    "change_player",
    "create_holy_site",
    "declare_war_with_cb",
    "destroy_building",
    "form_country",
    "found_dynasty",
    "kill_character",
    "kill_character_silently",
    "move_country",
    "rename_location",
    "set_capital",
    "set_new_ruler",
    "trigger_event",
    "trigger_event_non_silently",
    "trigger_event_silently",
}
PREVIEW_BOOTSTRAP_MUTATION_PREFIXES = (
    "add_",
    "remove_",
    "set_",
    "change_",
    "create_",
    "destroy_",
    "construct_",
    "grant_",
    "join_",
    "move_",
    "rename_",
)

CENTURY_ROMAN = {
    13: "XIII",
    14: "XIV",
    15: "XV",
    16: "XVI",
    17: "XVII",
    18: "XVIII",
    19: "XIX",
}


@dataclass(frozen=True)
class ContentSource:
    name: str
    kind: str
    root: Path
    events_dir: Path
    loc_dir: Path


@dataclass(frozen=True)
class ClausewitzNode:
    key: str
    operator: str
    value: str | list["ClausewitzNode"]


@dataclass(frozen=True)
class CountryTagProfile:
    culture: str
    language: str
    culture_groups: tuple[str, ...]
    setup_bucket: str


@dataclass(frozen=True)
class FormableCountrySpec:
    tag: str
    explicit_tags: tuple[str, ...]
    cultures: tuple[str, ...]
    culture_groups: tuple[str, ...]
    languages: tuple[str, ...]
    geography_ids: tuple[str, ...]


FORM_COUNTRY_REF_PATTERN = re.compile(r"\bform_country\s*=\s*formable_country:([A-Za-z0-9_]+)")
DIRECT_TAG_CHANGE_PATTERN = re.compile(
    r"\bchange_tag\s*=\s*(?:\{[^{}]*?\btag\s*=\s*([A-Z0-9_]+)\b[^{}]*?\}|([A-Z0-9_]+))",
    re.S,
)
COSMETIC_TAG_CHANGE_PATTERN = re.compile(
    r"\bchange_tag_cosmetic\s*=\s*(?:\{[^{}]*?\btag\s*=\s*([A-Z0-9_]+)\b[^{}]*?\}|([A-Z0-9_]+))",
    re.S,
)


def format_section_label(century: int, count: int) -> str:
    """Return a compact section label for the UI tabs."""
    roman = CENTURY_ROMAN.get(century)
    if roman is None:
        return f"S.{century} ({count})"
    return f"S.{roman} ({count})"


def parse_descriptor_name(descriptor_path: Path) -> str:
    """Read a mod display name from descriptor.mod if present."""
    if not descriptor_path.is_file():
        return ""
    text = descriptor_path.read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_descriptor_value(descriptor_path: Path, key: str) -> str:
    """Read a scalar descriptor.mod field if present."""
    if not descriptor_path.is_file():
        return ""
    text = descriptor_path.read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def discover_external_mod_sources(game_root: Path, extra_mod_roots: list[Path]) -> list[ContentSource]:
    """Discover local and Workshop mods that may contribute events or loc."""
    docs_mod_dir = Path.home() / "Documents" / "Paradox Interactive" / game_root.name / "mod"
    workshop_dir = game_root.parent.parent / "workshop" / "content" / STEAM_APP_ID
    current_mod_root = MOD_ROOT.resolve()
    current_mod_descriptor = current_mod_root / "descriptor.mod"
    current_mod_name = parse_descriptor_name(current_mod_descriptor)
    current_mod_remote_id = parse_descriptor_value(current_mod_descriptor, "remote_file_id")

    candidates: list[tuple[str, Path]] = []
    if docs_mod_dir.is_dir():
        candidates.extend(("local_mod", path) for path in sorted(docs_mod_dir.iterdir()) if path.is_dir())
    if workshop_dir.is_dir():
        candidates.extend(("workshop_mod", path) for path in sorted(workshop_dir.iterdir()) if path.is_dir())
    candidates.extend(("extra_mod", path.resolve()) for path in extra_mod_roots if path.is_dir())

    sources: list[ContentSource] = []
    seen_roots: set[Path] = set()
    for kind, root in candidates:
        resolved = root.resolve()
        if resolved == current_mod_root:
            continue
        if resolved in seen_roots:
            continue

        events_dir = resolved / "in_game" / "events"
        loc_dir = resolved / "main_menu" / "localization"
        descriptor = resolved / "descriptor.mod"
        descriptor_name = parse_descriptor_name(descriptor) if descriptor.is_file() else ""
        descriptor_remote_id = (
            parse_descriptor_value(descriptor, "remote_file_id") if descriptor.is_file() else ""
        )

        has_event_files = events_dir.is_dir() and any(events_dir.rglob("*.txt"))
        has_loc_files = loc_dir.is_dir() and any(loc_dir.rglob("*.yml"))

        if not descriptor.is_file() and not has_event_files and not has_loc_files:
            continue
        if current_mod_remote_id and descriptor_remote_id == current_mod_remote_id:
            continue
        if kind == "workshop_mod" and current_mod_name and descriptor_name == current_mod_name:
            continue

        seen_roots.add(resolved)
        name = descriptor_name or resolved.name
        sources.append(
            ContentSource(
                name=name,
                kind=kind,
                root=resolved,
                events_dir=events_dir,
                loc_dir=loc_dir,
            )
        )

    return sources


def load_loc_tree(loc_root: Path, lang: str) -> dict[str, str]:
    """Load and merge every loc file for a language from one content root."""
    lang_dir = loc_root / lang
    merged: dict[str, str] = {}
    if not lang_dir.is_dir():
        return merged
    for yml in sorted(lang_dir.rglob("*.yml")):
        merged.update(parse_loc_file(yml))
    return merged


def load_merged_loc(game_root: Path, lang: str, external_sources: list[ContentSource]) -> dict[str, str]:
    """Load loc for a language from base game and every detected mod source."""
    merged = load_loc_tree(game_root / "game" / "main_menu" / "localization", lang)
    for source in external_sources:
        merged.update(load_loc_tree(source.loc_dir, lang))
    return merged


def iter_registry_input_files(
    sources: list[ContentSource],
    *,
    include_loc: bool,
    preserve_non_dhe: bool,
    registry_path: Path,
) -> list[Path]:
    """Return the files that can affect the registry and auto-loc outputs."""
    files: list[Path] = [
        SCRIPT_PATH,
        SCRIPT_PATH.parent / "country_runtime_aliases.py",
        SCRIPT_PATH.parent / "generated_text_i18n.py",
    ]

    if preserve_non_dhe and registry_path.is_file():
        files.append(registry_path)

    for source in sources:
        if source.events_dir.is_dir():
            files.extend(sorted(source.events_dir.rglob("*.txt")))
        if include_loc and source.loc_dir.is_dir():
            files.extend(sorted(source.loc_dir.rglob("*.yml")))

    seen: set[Path] = set()
    unique_files: list[Path] = []
    for path in files:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        unique_files.append(resolved)
    return unique_files


def build_registry_input_fingerprint(
    game_root: Path,
    sources: list[ContentSource],
    *,
    include_loc: bool,
    preserve_non_dhe: bool,
    registry_path: Path,
    extra_mod_roots: list[Path],
    skip_external_mods: bool,
) -> str:
    """Build a cheap fingerprint from file stats and build arguments."""
    hasher = hashlib.md5()
    resolved_registry_path = registry_path.resolve()
    tool_inputs = [
        SCRIPT_PATH.resolve(),
        (SCRIPT_PATH.parent / "country_runtime_aliases.py").resolve(),
        (SCRIPT_PATH.parent / "generate_country_events_loc.py").resolve(),
        (SCRIPT_PATH.parent / "cleanup_auto_loc.py").resolve(),
        (SCRIPT_PATH.parent / "generated_text_i18n.py").resolve(),
    ]
    context = {
        "game_root": str(game_root),
        "include_loc": include_loc,
        "preserve_non_dhe": preserve_non_dhe,
        "skip_external_mods": skip_external_mods,
        "sources": [str(source.root.resolve()) for source in sources],
        "extra_mod_roots": [str(path.resolve()) for path in extra_mod_roots],
        "tool_inputs": [str(path) for path in tool_inputs],
    }
    hasher.update(json.dumps(context, sort_keys=True).encode("utf-8"))

    for path in tool_inputs:
        if not path.is_file():
            continue
        stat = path.stat()
        file_info = f"{path}|{stat.st_size}|{stat.st_mtime_ns}\n"
        hasher.update(file_info.encode("utf-8", errors="replace"))

    for path in iter_registry_input_files(
        sources,
        include_loc=include_loc,
        preserve_non_dhe=preserve_non_dhe,
        registry_path=registry_path,
    ):
        if preserve_non_dhe and path == resolved_registry_path:
            payload = path.read_bytes()
            hasher.update(f"{path}|registry-content|{len(payload)}\n".encode("utf-8"))
            hasher.update(hashlib.md5(payload).digest())
            continue
        stat = path.stat()
        file_info = f"{path}|{stat.st_size}|{stat.st_mtime_ns}\n"
        hasher.update(file_info.encode("utf-8", errors="replace"))

    return hasher.hexdigest()


def read_json_file(path: Path) -> dict:
    """Read a JSON file if present, otherwise return an empty object."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json_file(path: Path, payload: dict) -> None:
    """Write a small JSON helper file with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def dedupe_events_by_id(events: list[dict]) -> tuple[list[dict], int]:
    """Keep the highest-priority copy of each event id (later sources win)."""
    deduped: dict[str, dict] = {}
    overrides = 0
    for event in events:
        if event["id"] in deduped:
            overrides += 1
        deduped[event["id"]] = event
    return list(deduped.values()), overrides


def is_generated_dhe_entry(entry: dict) -> bool:
    """Return True for entries that were extracted from event files."""
    if entry.get("registry_origin") == "dhe_extracted":
        return True
    if entry.get("source_kind") in {"game", "local_mod", "workshop_mod", "extra_mod"}:
        return True
    return str(entry.get("source_file", "")).startswith("DHE/")

# ---------------------------------------------------------------------------
# Clausewitz script parser (minimal, for DHE extraction)
# ---------------------------------------------------------------------------

def strip_comments(text: str) -> str:
    """Remove line comments (# ...) but preserve strings."""
    lines = []
    for line in text.split("\n"):
        # Naïve: strip from first # that isn't inside quotes
        result = []
        in_quotes = False
        for ch in line:
            if ch == '"':
                in_quotes = not in_quotes
            elif ch == '#' and not in_quotes:
                break
            result.append(ch)
        lines.append("".join(result))
    return "\n".join(lines)


def find_matching_brace(text: str, start: int) -> int:
    """Return index of closing brace matching the opening brace at *start*."""
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
        elif ch == '"':
            # Skip quoted strings
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
        i += 1
    return -1


def extract_top_blocks(text: str) -> list[tuple[str, str]]:
    """Yield (key, body) for every top-level `key = { body }` block."""
    results = []
    i = 0
    while i < len(text):
        # Find pattern:  identifier = {
        m = re.search(r'(\S+)\s*=\s*\{', text[i:])
        if not m:
            break
        key = m.group(1)
        brace_pos = i + m.end() - 1  # position of {
        close = find_matching_brace(text, brace_pos)
        if close == -1:
            break
        body = text[brace_pos + 1:close]
        results.append((key, body))
        i = close + 1
    return results


def extract_kv(text: str, key: str) -> str | None:
    """Extract value for `key = value` (simple scalar)."""
    m = re.search(rf'\b{re.escape(key)}\s*=\s*(\S+)', text)
    if m:
        return m.group(1).strip('"')
    return None


def extract_all_values(text: str, key: str) -> list[str]:
    """Extract all values for repeated `key = value` lines."""
    return [m.group(1).strip('"') for m in re.finditer(rf'\b{re.escape(key)}\s*=\s*(\S+)', text)]


def extract_block(text: str, key: str) -> str | None:
    """Extract body of `key = { ... }` block."""
    pattern = rf'\b{re.escape(key)}\s*=\s*\{{'
    m = re.search(pattern, text)
    if not m:
        return None
    brace_pos = text.index('{', m.start())
    close = find_matching_brace(text, brace_pos)
    if close == -1:
        return None
    return text[brace_pos + 1:close]


def extract_all_blocks(text: str, key: str) -> list[str]:
    """Extract bodies of all `key = { ... }` blocks."""
    results = []
    pattern = rf'\b{re.escape(key)}\s*=\s*\{{'
    start = 0
    while True:
        m = re.search(pattern, text[start:])
        if not m:
            break
        brace_pos = start + text[start:].index('{', m.start())
        close = find_matching_brace(text, brace_pos)
        if close == -1:
            break
        results.append(text[brace_pos + 1:close])
        start = close + 1
    return results


def extract_block_values(text: str, key: str) -> list[str]:
    """Extract scalar identifiers from every `key = { ... }` block."""
    values: list[str] = []
    for body in extract_all_blocks(text, key):
        values.extend(re.findall(r"[A-Za-z0-9_:.]+", body))
    return values


def extract_top_level_scalar(text: str, key: str) -> str | None:
    """Return a scalar top-level key from a Clausewitz block body."""
    for node in parse_clausewitz_block(text):
        if node.key != key or isinstance(node.value, list):
            continue
        return str(node.value).strip('"')
    return None


def extract_scalar_line(text: str, key: str, *, last: bool = False) -> str | None:
    """Return a simple `key = value` line match from a block body."""
    matches = [
        m.group(1).strip('"')
        for m in re.finditer(rf"(?m)^\s*{re.escape(key)}\s*=\s*(\S+)\s*$", text)
    ]
    if not matches:
        return None
    return matches[-1] if last else matches[0]


def append_unique(values: list[str], value: str) -> None:
    """Append *value* only once, preserving insertion order."""
    if value and value not in values:
        values.append(value)


def extend_unique(values: list[str], items: tuple[str, ...] | list[str]) -> None:
    """Append each item from *items* once, preserving order."""
    for item in items:
        append_unique(values, item)


def normalize_bundle_token(token: str) -> str:
    """Normalize a geography token so region and setup bucket names can match."""
    token = token.strip().lower()
    if not token:
        return ""

    alias_map = {
        "anatolia": "anatol",
        "britain": "brit",
        "british": "brit",
        "caucasian": "caucasus",
        "carpathian": "carpath",
        "egyptian": "egypt",
        "french": "france",
        "german": "germany",
        "iberian": "iberia",
        "indonesian": "indonesia",
        "irish": "ireland",
        "italian": "italy",
        "maghrebi": "maghreb",
        "maori": "maori",
        "northumbrian": "northumbria",
        "persian": "persia",
        "scandinavian": "scandinavia",
        "welsh": "wales",
    }
    if token in alias_map:
        return alias_map[token]

    if token.endswith("ies") and len(token) > 4:
        token = token[:-3] + "y"
    elif token.endswith("ian") and len(token) > 5:
        token = token[:-3]
    elif token.endswith("ish") and len(token) > 5:
        token = token[:-3]
    elif token.endswith("ese") and len(token) > 5:
        token = token[:-3]
    elif token.endswith("ia") and len(token) > 5:
        token = token[:-2]

    return token


def lineage_variable_name(tag: str) -> str:
    """Return the persistent country-variable name used to mirror has_or_had_tag."""
    return f"ce_had_tag_{str(tag).strip().upper()}"


def identifier_tokens(value: str) -> set[str]:
    """Tokenize identifiers like `north_german_region` for fuzzy bucket matching."""
    tokens: set[str] = set()
    for raw in re.split(r"[^a-z0-9]+", value.lower()):
        if not raw:
            continue
        if raw in {"area", "region", "province", "location"}:
            continue
        token = normalize_bundle_token(raw)
        if token in {"", "north", "south", "east", "west", "greater", "lesser", "central"}:
            continue
        tokens.add(token)
    return tokens


def load_culture_metadata(game_root: Path) -> dict[str, tuple[tuple[str, ...], str]]:
    """Return `culture -> (groups, language)` metadata from the base game."""
    cultures_dir = game_root / "game" / "in_game" / "common" / "cultures"
    metadata: dict[str, tuple[tuple[str, ...], str]] = {}
    if not cultures_dir.is_dir():
        return metadata

    for path in sorted(cultures_dir.glob("*.txt")):
        text = strip_comments(path.read_text(encoding="utf-8-sig", errors="replace"))
        for culture, body in extract_top_blocks(text):
            groups: list[str] = []
            for value in extract_block_values(body, "culture_groups"):
                if re.fullmatch(r"[A-Za-z0-9_]+", value):
                    append_unique(groups, value)
            metadata[culture] = (
                tuple(groups),
                extract_scalar_line(body, "language") or "",
            )
    return metadata


def load_country_tag_profiles(game_root: Path) -> dict[str, CountryTagProfile]:
    """Return culture and setup-bucket metadata for country tags."""
    setup_dir = game_root / "game" / "in_game" / "setup" / "countries"
    profiles: dict[str, CountryTagProfile] = {}
    culture_metadata = load_culture_metadata(game_root)
    if not setup_dir.is_dir():
        return profiles

    for path in sorted(setup_dir.glob("*.txt")):
        text = strip_comments(path.read_text(encoding="utf-8-sig", errors="replace"))
        bucket = path.stem
        for tag, body in extract_top_blocks(text):
            if not re.fullmatch(r"[A-Z0-9_]+", tag):
                continue
            culture = extract_scalar_line(body, "culture_definition") or ""
            culture_groups, language = culture_metadata.get(culture, ((), ""))
            profiles[tag] = CountryTagProfile(
                culture=culture,
                language=language,
                culture_groups=tuple(culture_groups),
                setup_bucket=bucket,
            )
    return profiles


def load_formable_country_specs(game_root: Path) -> dict[str, FormableCountrySpec]:
    """Parse formable country definitions into lightweight bundle specs."""
    formable_path = (
        game_root / "game" / "in_game" / "common" / "formable_countries" / "00_formable_countries.txt"
    )
    specs: dict[str, FormableCountrySpec] = {}
    if not formable_path.is_file():
        return specs

    text = strip_comments(formable_path.read_text(encoding="utf-8-sig", errors="replace"))
    for _, body in extract_top_blocks(text):
        target_tag = extract_scalar_line(body, "tag", last=True)
        if not target_tag or not re.fullmatch(r"[A-Z0-9_]+", target_tag):
            continue

        explicit_tags: list[str] = []
        for source_tag in extract_all_values(body, "tag"):
            if re.fullmatch(r"[A-Z0-9_]+", source_tag) and source_tag != target_tag:
                append_unique(explicit_tags, source_tag)
        for source_tag in re.findall(r"\bhas_or_had_tag\s*=\s*([A-Z0-9_]+)\b", body):
            if source_tag != target_tag:
                append_unique(explicit_tags, source_tag)
        for source_tag in re.findall(r"\bcountry_exists\s*=\s*c:([A-Z0-9_]+)\b", body):
            if source_tag != target_tag:
                append_unique(explicit_tags, source_tag)
        for source_tag in re.findall(r"\bthis\s*!=\s*c:([A-Z0-9_]+)\b", body):
            if source_tag != target_tag:
                append_unique(explicit_tags, source_tag)

        cultures: list[str] = []
        for source_culture in re.findall(r"(?m)^\s*culture\s*=\s*(?:culture:)?([A-Za-z0-9_]+)\s*$", body):
            append_unique(cultures, source_culture)

        culture_groups: list[str] = []
        for source_group in re.findall(r"culture_group:([A-Za-z0-9_]+)", body):
            append_unique(culture_groups, source_group)

        languages: list[str] = []
        for source_language in re.findall(r"language:([A-Za-z0-9_]+)", body):
            append_unique(languages, source_language)

        geography_ids: list[str] = []
        for block_key in ("regions", "areas", "provinces"):
            for identifier in extract_block_values(body, block_key):
                plain_identifier = identifier.split(":", 1)[-1]
                if re.fullmatch(r"[A-Za-z0-9_]+", plain_identifier):
                    append_unique(geography_ids, plain_identifier)

        specs[target_tag] = FormableCountrySpec(
            tag=target_tag,
            explicit_tags=tuple(explicit_tags),
            cultures=tuple(cultures),
            culture_groups=tuple(culture_groups),
            languages=tuple(languages),
            geography_ids=tuple(geography_ids),
        )

    return specs


def load_country_transition_targets(game_root: Path) -> dict[str, set[str]]:
    """Collect country-transition targets referenced directly by game scripts."""
    in_game_root = game_root / "game" / "in_game"
    formable_specs = load_formable_country_specs(game_root)

    formable_targets = set(formable_specs)
    direct_tag_targets: set[str] = set()
    cosmetic_tag_targets: set[str] = set()
    scripted_formable_targets: set[str] = set()
    unresolved_formable_refs: set[str] = set()

    if not in_game_root.is_dir():
        return {
            "formable_targets": formable_targets,
            "direct_tag_targets": direct_tag_targets,
            "cosmetic_tag_targets": cosmetic_tag_targets,
            "scripted_formable_targets": scripted_formable_targets,
            "unresolved_formable_refs": unresolved_formable_refs,
        }

    for path in sorted(in_game_root.rglob("*.txt")):
        relative_parts = path.relative_to(in_game_root).parts
        if relative_parts[:2] == ("common", "effect_localization"):
            continue

        text = strip_comments(path.read_text(encoding="utf-8-sig", errors="replace"))

        for ref in FORM_COUNTRY_REF_PATTERN.findall(text):
            target_tag = ref[:-2] if ref.endswith("_f") else ref
            if target_tag in formable_specs:
                scripted_formable_targets.add(target_tag)
            else:
                unresolved_formable_refs.add(ref)

        for match in DIRECT_TAG_CHANGE_PATTERN.finditer(text):
            target_tag = (match.group(1) or match.group(2) or "").strip()
            if target_tag:
                direct_tag_targets.add(target_tag)

        for match in COSMETIC_TAG_CHANGE_PATTERN.finditer(text):
            target_tag = (match.group(1) or match.group(2) or "").strip()
            if target_tag:
                cosmetic_tag_targets.add(target_tag)

    return {
        "formable_targets": formable_targets,
        "direct_tag_targets": direct_tag_targets,
        "cosmetic_tag_targets": cosmetic_tag_targets,
        "scripted_formable_targets": scripted_formable_targets,
        "unresolved_formable_refs": unresolved_formable_refs,
    }


def match_geography_buckets(
    geography_ids: tuple[str, ...],
    bucket_names: set[str],
) -> list[str]:
    """Resolve formable geography into setup bucket names."""
    matched: list[str] = []
    bucket_tokens = {
        bucket: identifier_tokens(bucket)
        for bucket in bucket_names
    }

    for geography_id in geography_ids:
        for alias_bucket in FORMABLE_GEOGRAPHY_BUCKET_ALIASES.get(geography_id, ()):
            if alias_bucket in bucket_names:
                append_unique(matched, alias_bucket)

    scored: list[tuple[int, str]] = []
    seen_scored: set[str] = set()
    for geography_id in geography_ids:
        geo_tokens = identifier_tokens(geography_id)
        if not geo_tokens:
            continue
        for bucket, tokens in bucket_tokens.items():
            score = len(geo_tokens & tokens)
            if score <= 0:
                continue
            if bucket in seen_scored:
                continue
            seen_scored.add(bucket)
            scored.append((score, bucket))

    for _, bucket in sorted(scored, key=lambda item: (-item[0], item[1])):
        append_unique(matched, bucket)

    return matched


def derive_successor_bundles(
    game_root: Path,
    available_tags: set[str],
    *,
    extra_target_tags: set[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Infer synthetic successor bundles for formable tags without direct content."""
    profiles = load_country_tag_profiles(game_root)
    culture_metadata = load_culture_metadata(game_root)
    formable_specs = load_formable_country_specs(game_root)

    bucket_to_tags: dict[str, list[str]] = defaultdict(list)
    for tag in sorted(available_tags):
        profile = profiles.get(tag)
        if not profile or not profile.setup_bucket:
            continue
        bucket_to_tags[profile.setup_bucket].append(tag)

    derived: dict[str, tuple[str, ...]] = {}
    sorted_available_tags = sorted(available_tags)
    bucket_names = set(bucket_to_tags.keys())

    def append_profile_matches(
        sources: list[str],
        *,
        cultures: list[str] | tuple[str, ...] = (),
        culture_groups: list[str] | tuple[str, ...] = (),
        languages: list[str] | tuple[str, ...] = (),
        buckets: list[str] | tuple[str, ...] = (),
    ) -> None:
        for culture in cultures:
            for source_tag in sorted_available_tags:
                profile = profiles.get(source_tag)
                if profile and profile.culture == culture:
                    append_unique(sources, source_tag)

        for culture_group in culture_groups:
            for source_tag in sorted_available_tags:
                profile = profiles.get(source_tag)
                if profile and culture_group in profile.culture_groups:
                    append_unique(sources, source_tag)

        for language in languages:
            for source_tag in sorted_available_tags:
                profile = profiles.get(source_tag)
                if profile and profile.language == language:
                    append_unique(sources, source_tag)

        for bucket in buckets:
            for source_tag in bucket_to_tags.get(bucket, []):
                append_unique(sources, source_tag)

    candidate_target_tags = set(COUNTRY_SUCCESSOR_BUNDLES)
    candidate_target_tags.update(formable_specs)
    candidate_target_tags.update(extra_target_tags or ())

    for target_tag in sorted(candidate_target_tags):
        if target_tag in available_tags:
            continue

        sources: list[str] = []
        target_profile = profiles.get(target_tag)
        spec = formable_specs.get(target_tag)

        for source_tag in COUNTRY_SUCCESSOR_BUNDLES.get(target_tag, ()):
            if source_tag in available_tags and source_tag != target_tag:
                append_unique(sources, source_tag)

        if spec:
            for source_tag in spec.explicit_tags:
                if source_tag in available_tags and source_tag != target_tag:
                    append_unique(sources, source_tag)

        if target_profile:
            append_profile_matches(
                sources,
                cultures=[target_profile.culture] if target_profile.culture else (),
                culture_groups=target_profile.culture_groups,
                languages=[target_profile.language] if target_profile.language else (),
                buckets=[target_profile.setup_bucket] if target_profile.setup_bucket else (),
            )

        if spec:
            expanded_spec_cultures: list[str] = list(spec.cultures)
            expanded_spec_culture_groups: list[str] = list(spec.culture_groups)
            expanded_spec_languages: list[str] = list(spec.languages)
            for culture in spec.cultures:
                groups, language = culture_metadata.get(culture, ((), ""))
                extend_unique(expanded_spec_culture_groups, list(groups))
                if language:
                    append_unique(expanded_spec_languages, language)

            append_profile_matches(
                sources,
                cultures=expanded_spec_cultures,
                culture_groups=expanded_spec_culture_groups,
                languages=expanded_spec_languages,
            )

            append_profile_matches(
                sources,
                buckets=match_geography_buckets(spec.geography_ids, bucket_names),
            )

        if sources:
            derived[target_tag] = tuple(sources)

    return derived


def extract_event_comment(raw_text: str, event_id: str) -> str:
    """Extract an inline or immediately preceding comment for an event definition."""
    pattern = re.compile(rf"{re.escape(event_id)}\s*=\s*\{{(?:\s*#\s*(?P<inline>[^\r\n]+))?")
    match = pattern.search(raw_text)
    if not match:
        return ""

    def is_valid_comment_hint(value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if re.match(r"^https?://", stripped, re.IGNORECASE):
            return False
        if "wikipedia.org" in stripped.lower():
            return False
        return True

    inline = (match.group("inline") or "").strip()
    if is_valid_comment_hint(inline):
        return inline

    for line in reversed(raw_text[:match.start()].splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            candidate = stripped.lstrip("#").strip()
            if is_valid_comment_hint(candidate):
                return candidate
            continue
        break

    return ""


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _parse_clausewitz_token(text: str, index: int) -> tuple[str, int]:
    index = _skip_ws(text, index)
    if index >= len(text):
        return "", index

    if text[index] == '"':
        index += 1
        start = index
        while index < len(text):
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == '"':
                return text[start:index], index + 1
            index += 1
        return text[start:], index

    start = index
    while index < len(text) and not text[index].isspace() and text[index] not in "{}=<>?!":
        index += 1
    return text[start:index], index


def parse_clausewitz_items(text: str, index: int = 0) -> tuple[list[ClausewitzNode], int]:
    """Parse a Clausewitz block body into key/operator/value nodes."""
    items: list[ClausewitzNode] = []
    while index < len(text):
        index = _skip_ws(text, index)
        if index >= len(text):
            break
        if text[index] == "}":
            return items, index + 1

        key, index = _parse_clausewitz_token(text, index)
        if not key:
            index += 1
            continue

        index = _skip_ws(text, index)
        operator = ""
        for candidate in ("!=", "?=", ">=", "<=", "=", ">", "<"):
            if text.startswith(candidate, index):
                operator = candidate
                index += len(candidate)
                break

        if not operator:
            continue

        index = _skip_ws(text, index)
        if index < len(text) and text[index] == "{":
            value, index = parse_clausewitz_items(text, index + 1)
        else:
            value, index = _parse_clausewitz_token(text, index)

        items.append(ClausewitzNode(key=key, operator=operator, value=value))

    return items, index


def parse_clausewitz_block(text: str) -> list[ClausewitzNode]:
    nodes, _ = parse_clausewitz_items(text, 0)
    return nodes


def expand_local_scripted_effects(
    nodes: list[ClausewitzNode],
    local_scripted_effects: dict[str, list[ClausewitzNode]] | None,
    *,
    expansion_stack: tuple[str, ...] = (),
) -> list[ClausewitzNode]:
    """Inline local scripted_effect calls so runtime wrappers can live outside the event file."""
    if not local_scripted_effects:
        return nodes

    expanded: list[ClausewitzNode] = []
    for node in nodes:
        if (
            node.key in local_scripted_effects
            and node.operator in {"=", "?="}
            and isinstance(node.value, str)
            and node.value.strip().lower() == "yes"
        ):
            if node.key in expansion_stack:
                expanded.append(node)
            else:
                expanded.extend(
                    expand_local_scripted_effects(
                        local_scripted_effects[node.key],
                        local_scripted_effects,
                        expansion_stack=expansion_stack + (node.key,),
                    )
                )
            continue

        if isinstance(node.value, list):
            expanded.append(
                ClausewitzNode(
                    key=node.key,
                    operator=node.operator,
                    value=expand_local_scripted_effects(
                        node.value,
                        local_scripted_effects,
                        expansion_stack=expansion_stack,
                    ),
                )
            )
            continue

        expanded.append(node)

    return expanded


def expand_local_trigger_nodes(
    nodes: list[ClausewitzNode],
    local_scripted_triggers: dict[str, list[ClausewitzNode]] | None,
    *,
    expansion_stack: tuple[str, ...] = (),
) -> list[ClausewitzNode]:
    """Inline local scripted_trigger calls for transition-aware trigger analysis."""
    if not local_scripted_triggers:
        return nodes

    expanded: list[ClausewitzNode] = []
    for node in nodes:
        if (
            node.key in local_scripted_triggers
            and node.operator in {"=", "?="}
            and isinstance(node.value, str)
            and node.value.strip().lower() == "yes"
        ):
            if node.key in expansion_stack:
                expanded.append(node)
            else:
                expanded.extend(
                    expand_local_trigger_nodes(
                        local_scripted_triggers[node.key],
                        local_scripted_triggers,
                        expansion_stack=expansion_stack + (node.key,),
                    )
                )
            continue

        if isinstance(node.value, list):
            expanded.append(
                ClausewitzNode(
                    key=node.key,
                    operator=node.operator,
                    value=expand_local_trigger_nodes(
                        node.value,
                        local_scripted_triggers,
                        expansion_stack=expansion_stack,
                    ),
                )
            )
            continue

        expanded.append(node)

    return expanded


def combine_tag_logic_and(results: list[tuple[bool, bool]]) -> tuple[bool, bool]:
    """Return (can_be_true, can_be_false) for an AND-like group."""
    if not results:
        return (True, False)
    return (
        all(can_be_true for can_be_true, _ in results),
        any(can_be_false for _, can_be_false in results),
    )


def combine_tag_logic_or(results: list[tuple[bool, bool]]) -> tuple[bool, bool]:
    """Return (can_be_true, can_be_false) for an OR-like group."""
    if not results:
        return (False, True)
    return (
        any(can_be_true for can_be_true, _ in results),
        all(can_be_false for _, can_be_false in results),
    )


def evaluate_tag_logic_node(
    node: ClausewitzNode,
    *,
    current_tag: str,
    former_tags: set[str],
) -> tuple[bool, bool]:
    """Evaluate whether tag-related constraints can be true after a retag."""
    if not isinstance(node.value, list):
        value = str(node.value).strip().strip('"')
        normalized_value = value.upper()
        normalized_operator = "=" if node.operator == "?=" else node.operator

        if node.key == "tag" and normalized_operator in {"=", "!="}:
            matches = current_tag == normalized_value
            if normalized_operator == "!=":
                matches = not matches
            return (matches, not matches)

        if node.key == "has_or_had_tag" and normalized_operator in {"=", "!="}:
            matches = normalized_value == current_tag or normalized_value in former_tags
            if normalized_operator == "!=":
                matches = not matches
            return (matches, not matches)

        return (True, True)

    if node.key == "OR":
        return combine_tag_logic_or(
            [
                evaluate_tag_logic_node(child, current_tag=current_tag, former_tags=former_tags)
                for child in node.value
            ]
        )

    if node.key == "NOT":
        inner = combine_tag_logic_and(
            [
                evaluate_tag_logic_node(child, current_tag=current_tag, former_tags=former_tags)
                for child in node.value
            ]
        )
        return (inner[1], inner[0])

    if node.key == "NOR":
        inner = combine_tag_logic_or(
            [
                evaluate_tag_logic_node(child, current_tag=current_tag, former_tags=former_tags)
                for child in node.value
            ]
        )
        return (inner[1], inner[0])

    if node.key == "calc_true_if":
        try:
            required = max(0, int(child_scalar(node.value, "amount") or "1"))
        except ValueError:
            required = 1
        child_results = [
            evaluate_tag_logic_node(child, current_tag=current_tag, former_tags=former_tags)
            for child in node.value
            if child.key != "amount"
        ]
        can_be_true = sum(1 for can_be_true, _ in child_results if can_be_true) >= required
        can_be_false = sum(1 for _, can_be_false in child_results if can_be_false) > max(
            0,
            len(child_results) - required,
        )
        return (can_be_true, can_be_false)

    return combine_tag_logic_and(
        [
            evaluate_tag_logic_node(child, current_tag=current_tag, former_tags=former_tags)
            for child in node.value
        ]
    )


def event_supports_successor_lineage(event: dict[str, object]) -> bool:
    """Return True when the event can still make sense after forming a successor tag."""
    tags = {
        str(tag).strip().upper()
        for tag in event.get("tags", [])
        if str(tag).strip()
    }
    if not tags:
        return False

    trigger_raw = str(event.get("trigger_raw", "")).strip()
    if not trigger_raw:
        return True

    expanded_nodes = expand_local_trigger_nodes(
        parse_clausewitz_block(trigger_raw),
        event.get("local_scripted_triggers") or {},
    )
    can_be_true, _ = combine_tag_logic_and(
        [
            evaluate_tag_logic_node(
                node,
                current_tag="__CE_SUCCESSOR__",
                former_tags=tags,
            )
            for node in expanded_nodes
        ]
    )
    return can_be_true


def annotate_event_transition_metadata(all_events: list[dict[str, object]]) -> None:
    """Attach successor-lineage metadata used by synthetic bundles and viewers."""
    for event in all_events:
        tags = sorted(
            {
                str(tag).strip().upper()
                for tag in event.get("tags", [])
                if str(tag).strip()
            }
        )
        successor_compatible = event_supports_successor_lineage(event)
        event["successor_compatible"] = successor_compatible
        event["successor_lineage_tags"] = tags if successor_compatible else []


def filter_option_effect_nodes(nodes: list[ClausewitzNode]) -> list[ClausewitzNode]:
    """Drop metadata/cosmetic nodes that are not meaningful gameplay effects."""
    filtered: list[ClausewitzNode] = []
    for node in nodes:
        if node.key in NON_GAMEPLAY_EFFECT_KEYS:
            continue
        if isinstance(node.value, list):
            child_nodes = filter_option_effect_nodes(node.value)
            if not child_nodes:
                continue
            filtered.append(ClausewitzNode(key=node.key, operator=node.operator, value=child_nodes))
            continue
        filtered.append(node)
    return filtered


def iter_clausewitz_nodes(nodes: list[ClausewitzNode]) -> list[ClausewitzNode]:
    """Flatten a Clausewitz tree into a pre-order list."""
    flattened: list[ClausewitzNode] = []
    stack: list[ClausewitzNode] = list(reversed(nodes))
    while stack:
        node = stack.pop()
        flattened.append(node)
        if isinstance(node.value, list):
            stack.extend(reversed(node.value))
    return flattened


def looks_like_country_scope_key(key: str) -> bool:
    """Return True for direct tag-scope keys such as PRU = { ... }."""
    stripped = key.strip()
    lowered = stripped.lower()
    if lowered in LOGIC_BLOCK_KEYS:
        return False
    if not stripped or stripped != stripped.upper():
        return False
    if ":" in stripped or "." in stripped:
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]{1,4}", stripped))


COUNTRY_SCOPE_REF_RE = re.compile(r"^c:([A-Z][A-Z0-9_]{1,4})(?:\b|[.:])")
SAVED_SCOPE_REF_RE = re.compile(r"^scope:([A-Za-z0-9_]+)(?:\b|[.:])", re.IGNORECASE)


def extract_country_scope_ref(raw: str) -> str | None:
    """Return normalized c:TAG scope refs from a key or value when present."""
    text = str(raw).strip()
    if not text:
        return None
    match = COUNTRY_SCOPE_REF_RE.match(text)
    if not match:
        return None
    return f"c:{match.group(1)}"


def extract_saved_scope_ref(raw: str) -> str | None:
    """Return the base saved-scope name from a `scope:foo` key or value."""
    text = str(raw).strip()
    if not text:
        return None
    match = SAVED_SCOPE_REF_RE.match(text)
    if not match:
        return None
    return match.group(1).lower()


def collect_saved_scope_names(nodes: list[ClausewitzNode]) -> set[str]:
    """Collect every saved-scope identifier assigned inside a node tree."""
    saved_scopes: set[str] = set()
    for node in iter_clausewitz_nodes(nodes):
        if (
            not isinstance(node.value, list)
            and node.key in {"save_scope_as", "save_temporary_scope_as"}
            and isinstance(node.value, str)
        ):
            scope_name = node.value.strip().lower()
            if scope_name:
                saved_scopes.add(scope_name)
    return saved_scopes


def subtree_contains_saved_scope_assignment(node: ClausewitzNode) -> bool:
    return bool(
        isinstance(node.value, list)
        and any(
            child.key in {"save_scope_as", "save_temporary_scope_as"}
            or subtree_contains_saved_scope_assignment(child)
            for child in node.value
        )
    )


def subtree_has_bootstrap_mutation(node: ClausewitzNode) -> bool:
    """Detect side-effecting nodes that should not run in preview bootstrap wrappers."""
    for descendant in iter_clausewitz_nodes([node]):
        key_lower = descendant.key.strip().lower()
        if key_lower in {"save_scope_as", "save_temporary_scope_as", "limit", "trigger"}:
            continue
        if key_lower in LOGIC_BLOCK_KEYS:
            continue
        if key_lower in PREVIEW_BOOTSTRAP_MUTATION_KEYS:
            return True
        if any(key_lower.startswith(prefix) for prefix in PREVIEW_BOOTSTRAP_MUTATION_PREFIXES):
            return True
    return False


def extract_runtime_preview_bootstrap_nodes(nodes: list[ClausewitzNode]) -> list[ClausewitzNode]:
    """Return safe immediate nodes that only establish saved scopes used by previews."""
    bootstrap_nodes: list[ClausewitzNode] = []
    seen_scope_names: set[str] = set()

    for node in nodes:
        if not isinstance(node.value, list):
            continue
        if not subtree_contains_saved_scope_assignment(node):
            continue
        if subtree_has_bootstrap_mutation(node):
            continue

        candidate_scopes = collect_saved_scope_names([node])
        if not candidate_scopes:
            continue
        if candidate_scopes.issubset(seen_scope_names):
            continue

        bootstrap_nodes.append(node)
        seen_scope_names.update(candidate_scopes)

    return bootstrap_nodes


def sanitize_runtime_viewer_nodes(nodes: list[ClausewitzNode]) -> list[ClausewitzNode]:
    """Inject safe country-existence guards and normalize direct tag scopes."""
    guarded_scopes = {
        value.strip()
        for node in nodes
        if not isinstance(node.value, list)
        and node.key in {"country_exists", "exists"}
        and isinstance(node.value, str)
        and (value := extract_country_scope_ref(node.value))
    }

    sanitized: list[ClausewitzNode] = []
    inserted_scopes: set[str] = set()

    for node in nodes:
        normalized_node = node
        refs_to_guard: list[str] = []

        direct_tag_scope = looks_like_country_scope_key(node.key)
        key_lower = node.key.strip().lower()
        if direct_tag_scope:
            normalized_key = f"c:{node.key.strip()}"
        elif key_lower == "country_exists":
            normalized_key = "exists"
        else:
            normalized_key = node.key

        if isinstance(node.value, list):
            normalized_node = ClausewitzNode(
                key=normalized_key,
                operator=node.operator,
                value=sanitize_runtime_viewer_nodes(node.value),
            )
        elif normalized_key != node.key:
            normalized_node = ClausewitzNode(
                key=normalized_key,
                operator=node.operator,
                value=node.value,
            )

        if direct_tag_scope:
            refs_to_guard.append(normalized_key)
        else:
            key_scope = extract_country_scope_ref(normalized_node.key)
            if key_scope:
                refs_to_guard.append(key_scope)

        if isinstance(normalized_node.value, str):
            value_scope = extract_country_scope_ref(normalized_node.value)
            if value_scope:
                refs_to_guard.append(value_scope)

        for scope_ref in refs_to_guard:
            if scope_ref not in guarded_scopes and scope_ref not in inserted_scopes:
                sanitized.append(
                    ClausewitzNode(key="exists", operator="=", value=scope_ref)
                )
                inserted_scopes.add(scope_ref)

        sanitized.append(normalized_node)

    return sanitized


def sanitize_runtime_preview_nodes(nodes: list[ClausewitzNode]) -> list[ClausewitzNode]:
    """Normalize direct tag scopes inside effect previews without injecting trigger-only guards."""
    sanitized: list[ClausewitzNode] = []

    for node in nodes:
        normalized_node = node

        direct_tag_scope = looks_like_country_scope_key(node.key)
        key_lower = node.key.strip().lower()
        if direct_tag_scope:
            normalized_key = f"c:{node.key.strip()}"
        elif key_lower == "country_exists":
            normalized_key = "exists"
        else:
            normalized_key = node.key

        if isinstance(node.value, list):
            normalized_node = ClausewitzNode(
                key=normalized_key,
                operator=node.operator,
                value=sanitize_runtime_preview_nodes(node.value),
            )
        elif normalized_key != node.key:
            normalized_node = ClausewitzNode(
                key=normalized_key,
                operator=node.operator,
                value=node.value,
            )

        sanitized.append(normalized_node)

    return sanitized


def preview_node_is_too_complex(node: ClausewitzNode) -> bool:
    """Return True when a preview node should fall back to textual rendering."""
    key_lower = node.key.strip().lower()
    if any(key_lower.startswith(prefix) for prefix in COMPLEX_RUNTIME_PREVIEW_KEY_PREFIXES):
        return True
    if key_lower == "custom_tooltip" and isinstance(node.value, list):
        return any(child.key != "text" for child in node.value)
    return False


def is_runtime_viewer_safe(nodes: list[ClausewitzNode]) -> bool:
    """Return False for triggers that routinely error outside real event scope."""
    for node in iter_clausewitz_nodes(nodes):
        key = node.key.strip()
        key_lower = key.lower()
        if (
            key_lower in UNSAFE_RUNTIME_VIEWER_KEYS
            or key_lower.startswith("owner:")
            or key_lower.startswith("raw_material:")
            or looks_like_country_scope_key(key)
            or any(fragment in key_lower for fragment in UNSAFE_RUNTIME_VIEWER_KEY_FRAGMENTS)
        ):
            return False

        if isinstance(node.value, str):
            value_lower = node.value.strip().lower()
            if (
                value_lower == "none"
                or any(fragment in value_lower for fragment in UNSAFE_RUNTIME_VIEWER_VALUE_FRAGMENTS)
            ):
                return False
    return True


def is_runtime_preview_safe(
    nodes: list[ClausewitzNode],
    *,
    allowed_saved_scopes: set[str] | None = None,
) -> bool:
    """Return False for effect previews that are unsafe or noisy in generic UI scope."""
    allowed_saved_scopes = {scope.lower() for scope in (allowed_saved_scopes or set())}

    for node in iter_clausewitz_nodes(nodes):
        key = node.key.strip()
        key_lower = key.lower()
        if key_lower in {"save_scope_as", "save_temporary_scope_as"}:
            continue
        key_saved_scope = extract_saved_scope_ref(key)
        if key_saved_scope:
            if key_saved_scope not in allowed_saved_scopes:
                return False
        elif (
            "(" in key
            or key_lower in UNSAFE_RUNTIME_PREVIEW_KEYS
            or key_lower.startswith("owner:")
            or preview_node_is_too_complex(node)
            or any(key_lower.startswith(prefix) for prefix in UNSAFE_RUNTIME_PREVIEW_KEY_PREFIXES)
            or any(fragment in key_lower for fragment in UNSAFE_RUNTIME_PREVIEW_KEY_FRAGMENTS)
        ):
            return False

        if isinstance(node.value, str):
            value_lower = node.value.strip().lower()
            value_saved_scope = extract_saved_scope_ref(node.value)
            if value_saved_scope:
                if value_saved_scope not in allowed_saved_scopes:
                    return False
                continue
            if (
                value_lower == "none"
                or "(" in value_lower
                or ")" in value_lower
                or any(value_lower.startswith(prefix) for prefix in UNSAFE_RUNTIME_PREVIEW_KEY_PREFIXES)
                or any(fragment in value_lower for fragment in UNSAFE_RUNTIME_PREVIEW_VALUE_FRAGMENTS)
            ):
                return False
    return True


def build_preview_partial_note_nodes() -> list[ClausewitzNode]:
    """Return a native-effect note explaining that part of a preview was omitted."""
    return [
        ClausewitzNode(
            key="custom_tooltip",
            operator="=",
            value=[
                ClausewitzNode(
                    key="text",
                    operator="=",
                    value=PREVIEW_PARTIAL_EFFECT_TOOLTIP_KEY,
                )
            ],
        )
    ]


def prune_runtime_preview_nodes(
    nodes: list[ClausewitzNode],
    *,
    allowed_saved_scopes: set[str] | None = None,
) -> tuple[list[ClausewitzNode], bool]:
    """Drop unsafe preview nodes while preserving the safe subset for native rendering."""
    allowed_saved_scopes = {scope.lower() for scope in (allowed_saved_scopes or set())}
    pruned: list[ClausewitzNode] = []
    omitted_any = False

    for node in nodes:
        key = node.key.strip()
        key_lower = key.lower()
        if key_lower in {"save_scope_as", "save_temporary_scope_as"}:
            continue

        key_saved_scope = extract_saved_scope_ref(key)
        if key_saved_scope:
            if key_saved_scope not in allowed_saved_scopes:
                omitted_any = True
                continue
        elif (
            "(" in key
            or key_lower in UNSAFE_RUNTIME_PREVIEW_KEYS
            or key_lower.startswith("owner:")
            or preview_node_is_too_complex(node)
            or any(key_lower.startswith(prefix) for prefix in UNSAFE_RUNTIME_PREVIEW_KEY_PREFIXES)
            or any(fragment in key_lower for fragment in UNSAFE_RUNTIME_PREVIEW_KEY_FRAGMENTS)
        ):
            omitted_any = True
            continue

        if isinstance(node.value, list):
            child_nodes, child_omitted = prune_runtime_preview_nodes(
                node.value,
                allowed_saved_scopes=allowed_saved_scopes,
            )
            omitted_any = omitted_any or child_omitted
            if not child_nodes:
                omitted_any = True
                continue
            if key_lower in {"if", "else_if", "else", "trigger_if"} and not any(
                child.key != "limit" for child in child_nodes
            ):
                omitted_any = True
                continue
            pruned.append(ClausewitzNode(key=node.key, operator=node.operator, value=child_nodes))
            continue

        value_lower = node.value.strip().lower()
        value_saved_scope = extract_saved_scope_ref(node.value)
        if value_saved_scope:
            if value_saved_scope not in allowed_saved_scopes:
                omitted_any = True
                continue
        elif (
            value_lower == "none"
            or "(" in value_lower
            or ")" in value_lower
            or any(value_lower.startswith(prefix) for prefix in UNSAFE_RUNTIME_PREVIEW_KEY_PREFIXES)
            or any(fragment in value_lower for fragment in UNSAFE_RUNTIME_PREVIEW_VALUE_FRAGMENTS)
        ):
            omitted_any = True
            continue

        pruned.append(node)

    return pruned, omitted_any


def build_preview_wrapper_nodes(
    event: dict[str, object],
    raw_block: str,
    *,
    bootstrap_nodes: list[ClausewitzNode] | None = None,
    allowed_saved_scopes: set[str] | None = None,
) -> list[ClausewitzNode]:
    """Build the native preview wrapper, falling back to a partial safe subset when needed."""
    preview_nodes = build_runtime_preview_nodes(
        event,
        raw_block,
        bootstrap_nodes=bootstrap_nodes,
    )
    if not preview_nodes:
        return []
    if is_runtime_preview_safe(preview_nodes, allowed_saved_scopes=allowed_saved_scopes):
        return preview_nodes

    pruned_nodes, omitted_any = prune_runtime_preview_nodes(
        preview_nodes,
        allowed_saved_scopes=allowed_saved_scopes,
    )
    if omitted_any:
        pruned_nodes = [*pruned_nodes, *build_preview_partial_note_nodes()]
    return pruned_nodes


def serialize_clausewitz_key(key: str) -> str:
    """Serialize a Clausewitz key, re-quoting expression-style keys when needed."""
    raw = str(key)
    if "(" in raw or ")" in raw:
        escaped = raw.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return raw


def serialize_clausewitz_nodes(nodes: list[ClausewitzNode], *, indent_level: int = 1) -> list[str]:
    """Serialize parsed Clausewitz nodes back into script text."""
    lines: list[str] = []
    indent = "    " * indent_level
    for node in nodes:
        serialized_key = serialize_clausewitz_key(node.key)
        if isinstance(node.value, list):
            lines.append(f"{indent}{serialized_key} {node.operator} {{")
            lines.extend(serialize_clausewitz_nodes(node.value, indent_level=indent_level + 1))
            lines.append(f"{indent}}}")
            continue
        lines.append(f"{indent}{serialized_key} {node.operator} {node.value}")
    return lines


def extract_local_scripted_effects(text: str) -> dict[str, list[ClausewitzNode]]:
    """Extract `scripted_effect foo = { ... }` blocks from an event file."""
    results: dict[str, list[ClausewitzNode]] = {}
    pattern = re.compile(r"\bscripted_effect\s+(\S+)\s*=\s*\{")
    start = 0
    while True:
        match = pattern.search(text, start)
        if not match:
            break
        name = match.group(1)
        brace_pos = text.find("{", match.start())
        close = find_matching_brace(text, brace_pos)
        if close == -1:
            break
        body = text[brace_pos + 1:close]
        results[name] = parse_clausewitz_block(body)
        start = close + 1
    return results


def extract_local_scripted_triggers(text: str) -> dict[str, list[ClausewitzNode]]:
    """Extract `scripted_trigger foo = { ... }` blocks from an event file."""
    results: dict[str, list[ClausewitzNode]] = {}
    pattern = re.compile(r"\bscripted_trigger\s+(\S+)\s*=\s*\{")
    start = 0
    while True:
        match = pattern.search(text, start)
        if not match:
            break
        name = match.group(1)
        brace_pos = text.find("{", match.start())
        close = find_matching_brace(text, brace_pos)
        if close == -1:
            break
        body = text[brace_pos + 1:close]
        results[name] = parse_clausewitz_block(body)
        start = close + 1
    return results


def load_scripted_effect_definitions(sources: list[ContentSource]) -> dict[str, list[ClausewitzNode]]:
    """Load scripted effect definitions from common/scripted_effects across sources."""
    definitions: dict[str, list[ClausewitzNode]] = {}
    for source in sources:
        scripted_dir = source.root / "in_game" / "common" / "scripted_effects"
        if not scripted_dir.is_dir():
            continue
        for filepath in sorted(scripted_dir.rglob("*.txt")):
            text = strip_comments(filepath.read_text(encoding="utf-8-sig", errors="replace"))
            for name, body in extract_top_blocks(text):
                definitions[name] = parse_clausewitz_block(body)
    return definitions


# ---------------------------------------------------------------------------
# Event extraction
# ---------------------------------------------------------------------------

def parse_event_file(
    filepath: Path,
    events_root: Path,
    *,
    source_kind: str,
    source_name: str,
) -> list[dict]:
    """Parse an event .txt file and return dynamic historical country events."""
    raw = filepath.read_text(encoding="utf-8-sig", errors="replace")
    text = strip_comments(raw)
    local_scripted_effects = extract_local_scripted_effects(text)
    local_scripted_triggers = extract_local_scripted_triggers(text)

    # Extract namespace
    ns_match = re.search(r'^\s*namespace\s*=\s*(\S+)', text, re.MULTILINE)
    namespace = ns_match.group(1) if ns_match else filepath.stem

    events = []
    # Find event blocks: namespace.N = { ... }
    pattern = re.compile(rf'({re.escape(namespace)}\.(\d+))\s*=\s*\{{')
    for m in pattern.finditer(text):
        event_id = m.group(1)
        brace_pos = m.end() - 1
        close = find_matching_brace(text, brace_pos)
        if close == -1:
            continue
        body = text[brace_pos + 1:close]

        # Must be a country_event
        evt_type = extract_kv(body, "type")
        if evt_type != "country_event":
            continue

        # Must have dynamic_historical_event
        dhe_body = extract_block(body, "dynamic_historical_event")
        if dhe_body is None:
            continue

        tags = extract_all_values(dhe_body, "tag")
        date_from = extract_kv(dhe_body, "from") or "1300.1.1"
        date_to = extract_kv(dhe_body, "to") or "1800.1.1"
        monthly_chance = extract_kv(dhe_body, "monthly_chance") or "5"

        # Extract trigger and options for loc generation
        trigger_body = extract_block(body, "trigger") or ""
        immediate_body = extract_block(body, "immediate") or ""
        option_bodies = extract_all_blocks(body, "option")
        option_names = []
        option_blocks = []
        for opt in option_bodies:
            name = extract_kv(opt, "name")
            if name:
                option_names.append(name)
            option_blocks.append({
                "name": name or "",
                "historical_option": extract_kv(opt, "historical_option") == "yes",
                "body_raw": opt.strip(),
            })

        events.append({
            "id": event_id,
            "namespace": namespace,
            "tags": [t.upper() for t in tags],
            "date_from": date_from,
            "date_to": date_to,
            "monthly_chance": monthly_chance,
            "source_file": filepath.relative_to(events_root).as_posix(),
            "source_kind": source_kind,
            "source_mod": source_name,
            "comment_hint": extract_event_comment(raw, event_id),
            "trigger_raw": trigger_body.strip(),
            "immediate_raw": immediate_body.strip(),
            "option_names": option_names,
            "option_blocks": option_blocks,
            "local_scripted_effects": local_scripted_effects,
            "local_scripted_triggers": local_scripted_triggers,
        })

    return events


def date_century(date_str: str) -> int:
    """Extract the displayed century bucket from a Clausewitz date string."""
    try:
        year = int(date_str.split(".")[0])
        # UI expectation: 1400-1499 -> XV, etc.  Game starts 1337 so XIV is first playable.
        return max(14, min(19, (year // 100) + 1))
    except (ValueError, IndexError):
        return 15  # default


def event_sort_key(evt: dict) -> tuple:
    """Sort key: by from-date year, then event number."""
    try:
        year = int(evt["date_from"].split(".")[0])
    except (ValueError, IndexError):
        year = 1500
    try:
        num = int(evt["id"].rsplit(".", 1)[-1])
    except (ValueError, IndexError):
        num = 0
    return (year, num)


# ---------------------------------------------------------------------------
# Localization reading
# ---------------------------------------------------------------------------

def parse_loc_file(path: Path) -> dict[str, str]:
    """Parse a Paradox YAML loc file into key->value dict."""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("l_") or line.startswith("#"):
            continue
        parsed = split_loc_key_value(line)
        if not parsed:
            continue
        key, rest = parsed
        if rest and rest[0].isdigit():
            space_pos = rest.find(" ")
            if space_pos != -1:
                rest = rest[space_pos + 1:]
        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]
        result[key] = unescape_loc_value(rest)
    return result


def parse_loc_entries(path: Path, lang: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Parse a loc file preserving entry order and version numbers."""
    if not path.is_file():
        return f"l_{lang}:", []

    header = ""
    entries: list[tuple[str, str, str]] = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("l_"):
            header = stripped
            continue

        parsed = split_loc_key_value(stripped)
        if not parsed:
            continue
        key, rest = parsed

        version = "0"
        if rest and rest[0].isdigit():
            space_pos = rest.find(" ")
            if space_pos != -1:
                version = rest[:space_pos]
                rest = rest[space_pos + 1:]

        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]

        entries.append((key, version, unescape_loc_value(rest)))

    return (header or f"l_{lang}:"), entries


def split_loc_key_value(line: str) -> tuple[str, str] | None:
    """Parse a loc entry, including malformed `0: KEY: value` lines in some files."""
    colon_pos = line.find(":")
    if colon_pos == -1:
        return None

    key = line[:colon_pos].strip()
    rest = line[colon_pos + 1:].strip()
    if key.isdigit():
        second_colon = rest.find(":")
        if second_colon != -1:
            alt_key = rest[:second_colon].strip()
            alt_rest = rest[second_colon + 1:].strip()
            if alt_key and not any(ch.isspace() for ch in alt_key):
                key = alt_key
                rest = f"{line[:colon_pos].strip()} {alt_rest}".strip()

    if not key or any(ch.isspace() for ch in key):
        return None
    return key, rest


def write_loc_entries(
    path: Path,
    header: str,
    entries: list[tuple[str, str, str]],
) -> None:
    """Write a full loc file with preserved order and explicit versions."""
    lines = [header]
    for key, version, value in entries:
        lines.append(f' {key}:{version} "{escape_loc_value(value)}"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig", newline="\n")


# ---------------------------------------------------------------------------
# Auto loc generation for new events
# ---------------------------------------------------------------------------

def slug_from_id(event_id: str) -> str:
    """Convert event ID to slug: flavor_brapru.1 -> FLAVOR_BRAPRU_1."""
    return event_id.replace(".", "_").upper()


def viewer_trigger_name(event: dict[str, object]) -> str:
    """Return the scripted trigger name used by the live requirements viewer."""
    slug = str(event.get("slug") or slug_from_id(str(event.get("id", "")))).strip().lower()
    if not slug:
        raise ValueError(f"Cannot derive viewer trigger name for event: {event!r}")
    return f"{slug}_viewer"


def runtime_effect_prefix(event: dict[str, object]) -> str:
    """Return the shared runtime scripted-effect prefix for an event."""
    slug = str(event.get("slug") or slug_from_id(str(event.get("id", "")))).strip().lower()
    if not slug:
        raise ValueError(f"Cannot derive runtime effect prefix for event: {event!r}")
    return f"ce_{slug}"


def immediate_effect_name(event: dict[str, object]) -> str:
    """Return the generated scripted-effect name for an event immediate block."""
    return f"{runtime_effect_prefix(event)}_immediate"


def option_effect_name(event: dict[str, object], index: int) -> str:
    """Return the generated scripted-effect name for one option block."""
    return f"{runtime_effect_prefix(event)}_option_{index}"


def option_title_loc_key(slug: str, index: int) -> str:
    """Return the generated loc key used for one option title."""
    return f"COUNTRY_EVENTS_AUTO_{slug}_OPTION_{index}_TITLE"


RUNTIME_VARIABLE_LINE_RE = re.compile(r"^(\s*)(has_global_variable|has_variable)\s*=\s*([A-Za-z0-9_]+)\s*$")
RUNTIME_VARIABLE_COMPARISON_LINE_RE = re.compile(
    r"^(\s*)(global_var|var):([A-Za-z0-9_]+)\s*(>=|<=|>|<|=|\?=)\s*([^\n]+?)\s*$"
)
RUNTIME_BOOLEAN_LINE_RE = re.compile(r"^(\s*)([A-Za-z][A-Za-z0-9_]+)\s*=\s*(yes|no)\s*$")


def runtime_variable_tooltip_key(kind: str, variable_name: str) -> str:
    prefix = "GLOBAL_" if kind == "has_global_variable" else ""
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", str(variable_name).strip()).strip("_").upper()
    return f"COUNTRY_EVENTS_RT_{prefix}VAR_{safe_name}"


def split_runtime_variable_name(variable_name: str, game_loc: dict[str, str] | None = None) -> tuple[str, str]:
    raw = str(variable_name).strip()
    match = re.match(r"^([A-Za-z]{2,4})_(.+)$", raw)
    if not match:
        return "", raw

    country_name = resolve_named_entity(f"c:{match.group(1).upper()}", game_loc)
    if not country_name:
        return "", raw
    return country_name, match.group(2)


def runtime_flag_tooltip_key(flag_name: str, value: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", str(flag_name).strip()).strip("_").upper()
    return f"COUNTRY_EVENTS_RT_FLAG_{safe_name}_{str(value).strip().upper()}"


def runtime_variable_comparison_tooltip_key(scope_kind: str, variable_name: str, operator: str, value: str) -> str:
    payload = f"{scope_kind}:{variable_name}:{operator}:{value.strip()}".encode("utf-8")
    digest = hashlib.md5(payload).hexdigest().upper()[:16]
    return f"COUNTRY_EVENTS_RT_CMP_{digest}"


def runtime_variable_existence_kind(scope_kind: str) -> str:
    return "has_global_variable" if scope_kind == "global_var" else "has_variable"


def runtime_variable_display_name(variable_name: str, game_loc: dict[str, str]) -> str:
    country_name, base_raw = split_runtime_variable_name(variable_name, game_loc)
    lowered = base_raw.lower()

    for suffix in ("_not_active", "_active", "_var", "_variable"):
        if lowered.endswith(suffix):
            base_raw = base_raw[: -len(suffix)]
            break

    base_text = format_runtime_variable_base(base_raw, game_loc)
    base_text = re.sub(r"\bHre\b", "HRE", base_text)
    return f"{base_text} ({country_name})" if country_name else base_text


def format_runtime_variable_base(base_raw: str, game_loc: dict[str, str]) -> str:
    raw = str(base_raw).strip()
    if not raw:
        return ""

    lowered = raw.lower()
    special_labels = {
        "seat": "patriarchal seat",
        "literati_purges": "number of literati purges",
        "samuel_pepys_diary_entries": "number of Samuel Pepys diary entries",
    }
    if lowered in special_labels:
        return special_labels[lowered]
    resolved = resolve_named_entity(raw, game_loc) or resolve_loc_text(raw, game_loc)
    if resolved and resolved.lower() != raw.lower():
        return resolved
    if lowered.startswith("num_of_"):
        return f"number of {humanize_identifier(raw[7:]).lower()}"
    if lowered.endswith("_entries"):
        return f"number of {humanize_identifier(raw[:-8])} entries"
    return humanize_identifier(raw)


def describe_runtime_variable_condition(variable_name: str, game_loc: dict[str, str], lang: str) -> str:
    display_name = runtime_variable_display_name(variable_name, game_loc)
    lowered = str(variable_name).strip().lower()
    if lowered.endswith("_not_active"):
        english = f"{display_name} must not be active."
    elif lowered.endswith("_active"):
        english = f"{display_name} must be active."
    else:
        english = f"{display_name} must exist."

    return capitalize_sentence_start(gti18n.localize_generated_text(english, lang))


def iter_runtime_variable_requirements(trigger_raw: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for raw_line in str(trigger_raw or "").splitlines():
        match = RUNTIME_VARIABLE_LINE_RE.match(raw_line.rstrip())
        if match:
            matches.append((match.group(2), match.group(3)))
    return matches


def should_wrap_runtime_boolean(summary: str | None, key: str) -> bool:
    lowered = key.lower()
    if summary and summary.lower().endswith(("must be yes", "must be no")):
        return True
    if lowered.endswith("_trigger"):
        return True
    if lowered.startswith("enable_"):
        return True
    if lowered.endswith(("_enabled", "_allowed", "_active", "_inactive")):
        return True
    country_name, _ = split_runtime_variable_name(key)
    if country_name:
        return True
    return False


def describe_runtime_flag_condition(flag_name: str, value: str, game_loc: dict[str, str], lang: str) -> str:
    node = ClausewitzNode(key=flag_name, operator="=", value=value)
    summary = summarize_trigger_node(node)
    if summary and not summary.lower().endswith(("must be yes", "must be no")):
        return capitalize_sentence_start(gti18n.localize_generated_text(summary.rstrip(".") + ".", lang))

    country_name, base_raw = split_runtime_variable_name(flag_name, game_loc)
    lowered = base_raw.lower()

    def decorate(base_text: str) -> str:
        base_text = re.sub(r"\bHre\b", "HRE", base_text)
        return f"{base_text} ({country_name})" if country_name else base_text

    if lowered.startswith("enable_") and lowered.endswith("_events"):
        base_text = decorate(humanize_identifier(base_raw[7:-7]) + " events")
        english = f"{base_text} must be enabled." if value == "yes" else f"{base_text} must not be enabled."
    elif lowered.endswith("_enabled"):
        base_text = decorate(humanize_identifier(base_raw[:-8]))
        english = f"{base_text} must be enabled." if value == "yes" else f"{base_text} must not be enabled."
    elif lowered.endswith("_allowed"):
        base_text = decorate(humanize_identifier(base_raw[:-8]))
        english = f"{base_text} must be allowed." if value == "yes" else f"{base_text} must not be allowed."
    elif lowered.endswith("_trigger"):
        base_text = decorate(humanize_identifier(base_raw[:-8]))
        english = f"Must satisfy {base_text}." if value == "yes" else f"Must not satisfy {base_text}."
    elif lowered.startswith("is_"):
        base_text = humanize_identifier(base_raw[3:])
        english = (
            f"{country_name} must be {base_text}." if country_name else f"Must be {base_text}."
        ) if value == "yes" else (
            f"{country_name} must not be {base_text}." if country_name else f"Must not be {base_text}."
        )
    elif lowered.startswith("has_"):
        base_text = humanize_identifier(base_raw[4:])
        english = (
            f"{country_name} must have {base_text}." if country_name else f"Must have {base_text}."
        ) if value == "yes" else (
            f"{country_name} must not have {base_text}." if country_name else f"Must not have {base_text}."
        )
    else:
        base_text = decorate(humanize_identifier(base_raw))
        english = f"{base_text} must be active." if value == "yes" else f"{base_text} must not be active."

    return capitalize_sentence_start(gti18n.localize_generated_text(english, lang))


def describe_runtime_variable_comparison(
    scope_kind: str,
    variable_name: str,
    operator: str,
    value: str,
    game_loc: dict[str, str],
    lang: str,
) -> str:
    label = runtime_variable_display_name(variable_name, game_loc)
    english = describe_comparison(label, "=" if operator == "?=" else operator, value.strip())
    if scope_kind == "global_var":
        english = english.replace(label, f"Global {label}", 1)
    return capitalize_sentence_start(gti18n.localize_generated_text(english.rstrip(".") + ".", lang))


def iter_runtime_scalar_tooltips(
    trigger_raw: str,
    game_loc: dict[str, str],
    lang: str,
) -> list[tuple[str, str]]:
    entries: dict[str, str] = {}

    for raw_line in str(trigger_raw or "").splitlines():
        line = raw_line.rstrip()
        if not line:
            continue

        variable_match = RUNTIME_VARIABLE_LINE_RE.match(line)
        if variable_match:
            _, kind, variable_name = variable_match.groups()
            entries[runtime_variable_tooltip_key(kind, variable_name)] = describe_runtime_variable_condition(
                variable_name,
                game_loc,
                lang,
            )
            continue

        comparison_match = RUNTIME_VARIABLE_COMPARISON_LINE_RE.match(line)
        if comparison_match:
            _, scope_kind, variable_name, operator, value = comparison_match.groups()
            if value.strip() != "{":
                entries[runtime_variable_comparison_tooltip_key(scope_kind, variable_name, operator, value)] = (
                    describe_runtime_variable_comparison(scope_kind, variable_name, operator, value, game_loc, lang)
                )
            continue

        boolean_match = RUNTIME_BOOLEAN_LINE_RE.match(line)
        if boolean_match:
            _, key, value = boolean_match.groups()
            summary = summarize_trigger_node(ClausewitzNode(key=key, operator="=", value=value))
            if should_wrap_runtime_boolean(summary, key):
                entries[runtime_flag_tooltip_key(key, value)] = describe_runtime_flag_condition(key, value, game_loc, lang)

    return sorted(entries.items())


def strip_loc_dynamic(text: str) -> str:
    """Replace dynamic loc tokens with readable generic placeholders."""

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        lower = token.lower()

        def scoped_person_ref(kind: str) -> str:
            if "root.getcountry.getgovernment.getruler" in lower or "target_ruler" in lower:
                mapping = {
                    "subject": "the ruler",
                    "possessive": "the ruler's",
                    "object": "the ruler",
                    "reflexive": "the ruler",
                }
                return mapping[kind]
            if "target_artist" in lower:
                mapping = {
                    "subject": "the artist",
                    "possessive": "the artist's",
                    "object": "the artist",
                    "reflexive": "the artist",
                }
                return mapping[kind]
            if "mlo_dal_verme_scope" in lower:
                mapping = {
                    "subject": "this condottiero",
                    "possessive": "this condottiero's",
                    "object": "this condottiero",
                    "reflexive": "this condottiero",
                }
                return mapping[kind]
            if "mlo_bernardino_corio_scope" in lower:
                mapping = {
                    "subject": "this writer",
                    "possessive": "this writer's",
                    "object": "this writer",
                    "reflexive": "this writer",
                }
                return mapping[kind]
            if (
                "target_character" in lower
                or "character:" in lower
                or "target_spouse" in lower
                or "target_rival" in lower
            ):
                mapping = {
                    "subject": "this character",
                    "possessive": "this character's",
                    "object": "this character",
                    "reflexive": "this character",
                }
                return mapping[kind]
            mapping = {
                "subject": "this figure",
                "possessive": "this figure's",
                "object": "this figure",
                "reflexive": "this figure",
            }
            return mapping[kind]

        if "getherselfhimself" in lower:
            return scoped_person_ref("reflexive")
        if "getherhim" in lower or "gethimher" in lower:
            return scoped_person_ref("object")
        if "getherhis" in lower or "gethisher" in lower:
            return scoped_person_ref("possessive")
        if "getshehe" in lower:
            return scoped_person_ref("subject")
        if "getdaughterson" in lower:
            return "child"

        name_replacements = [
            ("root.getcountry.getgovernment.getruler.getdynasty", "the ruling dynasty"),
            ("root.getcountry.getgovernment.getruler", "the ruler"),
            ("root.getcountry.getcapital", "the capital"),
            ("root.getcountry.getgovernment.getcourttitle", "court"),
            ("root.getcountry.getgovernment.getheirtitle", "heir"),
            ("root.getcountry.getgovernment.getrulertitle", "ruler"),
            ("root.getcountry.getgovernment.getadjective", "our"),
            ("root.getcountry.getgovernment.getestatename", "estate"),
            ("root.getcountry.getgovernment.getgovernmenttype", "government"),
            ("root.getcountry.getname", "our country"),
            ("root.getcountry.getlongname", "our country"),
            ("root.getcountry.getflavorrank", "realm"),
            ("target_artist", "the artist"),
            ("target_character", "this character"),
            ("target_ruler", "the ruler"),
            ("target_spouse", "the spouse"),
            ("target_dynasty", "that dynasty"),
            ("target_country", "that country"),
            ("target_location2", "the second city"),
            ("target_location", "the city"),
            ("target_province", "the province"),
            ("target_rival", "the rival"),
            ("target_old_country", "the other country"),
            ("mlo_dal_verme_scope", "this condottiero"),
            ("mlo_bernardino_corio_scope", "this writer"),
            ("root.getcountry", "the country"),
            ("showlocationname", "the city"),
            ("showlocationnamewithnotooltip", "the city"),
            ("showprovincename", "the province"),
            ("showregionname", "the region"),
            ("showareaname", "the area"),
            ("showbuildingtypename", "the building"),
            ("showgovernmenttypename", "the government"),
            ("showdisastername", "the disaster"),
            ("shownamedvalue", "a value"),
        ]
        for marker, replacement in name_replacements:
            if marker in lower:
                return replacement

        return "(...)"

    text = re.sub(r"\[([^\]]+)\]", replace_token, text)
    text = re.sub(r"#\w+\s*", "", text)
    text = text.replace("#!", "")
    text = re.sub(r"\$([^$]+)\$", lambda m: humanize_identifier(m.group(1)), text)
    text = re.sub(r"\(\.\.\.\)\s*\(\.\.\.\)", "(...)", text)
    text = re.sub(r"\bthe the country\b", "the country", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe our country\b", "our country", text, flags=re.IGNORECASE)
    text = re.sub(r"\bour the country\b", "our country", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe the ruler\b", "the ruler", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe ruler own\b", "the ruler's own", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe ruler leadership\b", "the ruler's leadership", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe ruler sight\b", "the ruler's sight", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe ruler eyes\b", "the ruler's eyes", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe ruler faith\b", "the ruler's faith", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe ruler connection\b", "the ruler's connection", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe ruler rule\b", "the ruler's rule", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe city's\b", "the city's", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthe country's\b", "the country's", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def resolve_inline_loc_tokens(text: str, game_loc: dict[str, str], max_depth: int = 5) -> str:
    """Resolve inline $other_key$ references using the merged localization map."""
    if not text or "$" not in text:
        return text

    result = text
    for _ in range(max_depth):
        changed = False

        def replace_token(match: re.Match[str]) -> str:
            nonlocal changed
            loc_key = match.group(1)
            resolved = game_loc.get(loc_key)
            if not resolved:
                return match.group(0)
            changed = True
            return resolved

        updated = re.sub(r"\$([^$]+)\$", replace_token, result)
        result = updated
        if not changed or "$" not in result:
            break
    return result


SPECIAL_LOC_ADJECTIVES = {
    "calvinist": "Calvinist",
    "catholic": "Catholic",
    "christian": "Christian",
    "folk_african_group": "African Folk",
    "hindu": "Hindu",
    "judaism": "Jewish",
    "jewish": "Jewish",
    "lollardy": "Lollard",
    "lutheran": "Lutheran",
    "miaphysite": "Miaphysite",
    "muslim": "Muslim",
    "orthodox": "Orthodox",
    "persia": "Persian",
    "romuva": "Romuva",
    "shia": "Shia",
    "sunni": "Sunni",
    "waldensian": "Waldensian",
}


def derive_loc_adjective(name: str, raw_key: str = "") -> str:
    """Best-effort adjective fallback when the game has no explicit _ADJ loc key."""
    if not name:
        return ""

    lowered_key = raw_key.lower()
    if lowered_key in SPECIAL_LOC_ADJECTIVES:
        return SPECIAL_LOC_ADJECTIVES[lowered_key]

    lowered_name = name.lower()
    if lowered_name == "christianity":
        return "Christian"
    if lowered_name == "catholicism":
        return "Catholic"
    if lowered_name == "judaism":
        return "Jewish"
    if lowered_name.endswith("ity") and len(name) > 4:
        return name[:-3]
    if lowered_name.endswith("ism") and len(name) > 4:
        return name[:-3]
    return name


def resolve_loc_argument(arg: str, game_loc: dict[str, str], *, adjective: bool = False) -> str:
    """Resolve a quoted loc/script identifier such as a tag, religion or culture key."""
    raw = str(arg).strip().strip('"').strip("'")
    if not raw:
        return ""

    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        candidate = candidate.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    if adjective:
        add(f"{raw}_adj")
        add(f"{raw}_ADJ")
        add(f"{raw.upper()}_ADJ")
        add(f"{raw.upper()}_adj")

    add(raw)
    add(raw.upper())
    add(raw.lower())

    if re.fullmatch(r"[A-Z0-9]{2,4}", raw.upper()):
        add(f"c:{raw.upper()}")

    for candidate in candidates:
        if candidate.startswith("c:"):
            resolved = resolve_named_entity(candidate, game_loc)
        else:
            raw_value = game_loc.get(candidate, "")
            if raw_value:
                resolved_input = resolve_inline_loc_tokens(raw_value, game_loc)
                if f"[{candidate.lower()}." in resolved_input.lower():
                    resolved = strip_loc_dynamic(resolved_input).strip()
                else:
                    resolved = strip_loc_dynamic(resolve_bracket_loc_tokens(resolved_input, game_loc)).strip()
            else:
                resolved = ""
            if not resolved and re.fullmatch(r"[A-Z0-9]{2,4}", candidate.upper()):
                resolved = resolve_named_entity(f"c:{candidate.upper()}", game_loc)
        if not resolved:
            continue
        cleaned = strip_loc_dynamic(resolve_inline_loc_tokens(resolved, game_loc)).strip()
        if cleaned:
            return derive_loc_adjective(cleaned, raw) if adjective else cleaned

    fallback = resolve_named_entity(raw, game_loc) or humanize_identifier(raw)
    if not fallback:
        return ""
    return derive_loc_adjective(fallback, raw) if adjective else fallback


def event_country_adjective(event: dict | None, game_loc: dict[str, str]) -> str:
    tags = (event or {}).get("tags") or []
    if not tags:
        return ""
    return resolve_loc_argument(tags[0], game_loc, adjective=True)


def dynamic_scope_placeholder(scope: str, *, adjective: bool = False) -> str:
    lower = scope.lower()
    if adjective:
        if lower in {"root_country", "root"}:
            return "our"
        if "country" in lower or "nation" in lower:
            return "foreign"
        return ""

    if lower in {"root_country", "root"}:
        return "our country"
    if "explorer" in lower:
        return "the explorer"
    if "artist" in lower:
        return "the artist"
    if "writer" in lower:
        return "the writer"
    if "ruler" in lower:
        return "the ruler"
    if "heir" in lower or "spouse" in lower or "rival" in lower or "character" in lower:
        return "this character"
    if "dynasty" in lower:
        return "that dynasty"
    if "country" in lower or "nation" in lower:
        return "that country"
    if "organization" in lower:
        return "that organization"
    if "location" in lower or "city" in lower:
        return "the city"
    if "province" in lower or "area" in lower or "region" in lower:
        return "the province"
    if "culture" in lower:
        return "that culture"
    return ""


def looks_like_specific_named_scope(scope: str) -> bool:
    """Return True for scope ids that look like an actual named character/entity, not a generic placeholder."""
    lower = scope.lower()
    generic_prefixes = (
        "root",
        "target",
        "current",
        "neighbor",
        "favored",
        "foreign",
        "other",
        "another",
        "our",
        "their",
        "this",
        "that",
        "random",
    )
    return not lower.startswith(generic_prefixes)


def resolve_bracket_dynamic_token(token: str, game_loc: dict[str, str], event: dict | None = None) -> str:
    """Resolve common dynamic loc expressions used in event titles, descriptions and options."""
    base = token.split("|", 1)[0].strip()
    if not base:
        return ""

    if re.fullmatch(r"ROOT\.GetCountry\.Get(?:LongName|Name)(?:WithNoTooltip)?", base, flags=re.IGNORECASE):
        return event_country_display_name(event or {}, game_loc) or "our country"

    if re.fullmatch(r"ROOT\.GetCountry\.GetAdjective(?:WithNoTooltip)?", base, flags=re.IGNORECASE):
        return event_country_adjective(event, game_loc) or "our"

    if re.fullmatch(r"ROOT\.GetCountry\.GetGovernment\.GetRulerTitle(?:WithNoTooltip)?", base, flags=re.IGNORECASE):
        return "ruler"

    estate_match = re.fullmatch(
        r"(?:ROOT\.GetCountry\.GetGovernment|[A-Za-z0-9_]+\.GetGovernment)\.GetEstateName(?:WithNoTooltip)?\('([^']+)'\)",
        base,
        flags=re.IGNORECASE,
    )
    if estate_match:
        return resolve_loc_argument(estate_match.group(1), game_loc)

    show_match = re.fullmatch(
        r"Show([A-Za-z0-9_]+?)(Name|TypeName|AreaName|RegionName|LocationName|ProvinceName|CountryName|CharacterName|"
        r"GoodsName|LawName|PolicyName|InstitutionName|GovernmentReformName|GovernmentTypeName|BuildingTypeName|"
        r"WorkOfArtName|DynastyName|CultureName|ReligionName|ReligionGroupName|Adjective|RulerTitle)(?:WithNoTooltip)?\('([^']+?)'?\)",
        base,
        flags=re.IGNORECASE,
    )
    if show_match:
        accessor = show_match.group(2).lower()
        loc_arg = show_match.group(3)
        if accessor == "adjective":
            return resolve_loc_argument(loc_arg, game_loc, adjective=True)
        if accessor == "rulertitle":
            return "ruler"
        return resolve_loc_argument(loc_arg, game_loc)

    country_match = re.fullmatch(
        r"GetCountry\('([^']+)'\)\.Get(LongName|Name|Adjective)(?:WithNoTooltip)?",
        base,
        flags=re.IGNORECASE,
    )
    if country_match:
        loc_arg = country_match.group(1)
        accessor = country_match.group(2).lower()
        return resolve_loc_argument(loc_arg, game_loc, adjective=accessor == "adjective")

    country_ruler_match = re.fullmatch(
        r"GetCountry\('([^']+)'\)\.GetGovernment\.GetRulerTitle(?:WithNoTooltip)?",
        base,
        flags=re.IGNORECASE,
    )
    if country_ruler_match:
        country_tag = country_ruler_match.group(1).upper()
        if country_tag == "PAP":
            return resolve_loc_text("game_concept_pope", game_loc) or "Pope"
        adjective = resolve_loc_argument(country_tag, game_loc, adjective=True)
        country_name = resolve_loc_argument(country_tag, game_loc)
        if adjective:
            return f"{adjective} ruler"
        if country_name:
            return f"ruler of {country_name}"
        return "ruler"

    character_match = re.fullmatch(
        r"GetCharacter\('([^']+)'\)\.Get(ShortName|Name|LastName)(?:WithNoTooltip)?",
        base,
        flags=re.IGNORECASE,
    )
    if character_match:
        human = humanize_identifier(character_match.group(1))
        accessor = character_match.group(2).lower()
        if accessor == "lastname":
            return human.split()[-1] if human else ""
        return human

    dynasty_match = re.fullmatch(
        r"GetDynasty\('([^']+)'\)\.GetName(?:WithNoTooltip)?",
        base,
        flags=re.IGNORECASE,
    )
    if dynasty_match:
        return re.sub(r"\s+Dynasty$", "", humanize_identifier(dynasty_match.group(1)), flags=re.IGNORECASE)

    scope_name_match = re.fullmatch(
        r"([A-Za-z0-9_]+)\.Get(ShortName|Name|LongName|LastName|Adjective)(?:WithNoTooltip)?",
        base,
        flags=re.IGNORECASE,
    )
    if scope_name_match:
        scope_name = scope_name_match.group(1)
        accessor = scope_name_match.group(2).lower()
        if accessor in {"shortname", "name", "longname", "lastname"} and event:
            resolved = _resolve_title_scope_name(scope_name, event, game_loc)
            if resolved:
                if accessor == "lastname":
                    return resolved.split()[-1]
                return resolved
        if accessor == "adjective":
            if scope_name.lower() in {"root", "root_country"}:
                resolved = event_country_adjective(event, game_loc)
                if resolved:
                    return resolved
            if event:
                resolved = _resolve_title_scope_adjective(scope_name, event, game_loc)
                if resolved:
                    return resolved
            resolved = resolve_loc_argument(scope_name, game_loc, adjective=True)
            if resolved and looks_like_specific_named_scope(scope_name):
                return resolved
            return dynamic_scope_placeholder(scope_name, adjective=True)
        if looks_like_specific_named_scope(scope_name):
            resolved = resolve_loc_argument(scope_name, game_loc)
            if resolved:
                if accessor == "lastname":
                    return resolved.split()[-1]
                return resolved
            humanized = humanize_identifier(scope_name)
            if humanized:
                if accessor == "lastname":
                    return humanized.split()[-1]
                return humanized
        return dynamic_scope_placeholder(scope_name)

    scope_culture_match = re.fullmatch(
        r"([A-Za-z0-9_]+)\.GetCulture\.GetName(?:WithNoTooltip)?",
        base,
        flags=re.IGNORECASE,
    )
    if scope_culture_match:
        scope_name = scope_culture_match.group(1)
        if scope_name.lower() == "root_country":
            return "our culture"
        return dynamic_scope_placeholder(scope_name) or "that culture"

    scope_ruler_title_match = re.fullmatch(
        r"([A-Za-z0-9_]+)\.GetGovernment\.GetRulerTitle(?:WithNoTooltip)?",
        base,
        flags=re.IGNORECASE,
    )
    if scope_ruler_title_match:
        return "ruler"

    if re.fullmatch(r"[A-Za-z0-9_]+\.GetWomanMan", base, flags=re.IGNORECASE):
        return "person"

    return ""


def resolve_bracket_loc_tokens(
    text: str,
    game_loc: dict[str, str],
    max_depth: int = 3,
    event: dict | None = None,
) -> str:
    """Resolve common dynamic loc expressions into readable localized text."""
    if not text or ("[" not in text and "Show" not in text):
        return text

    result = text

    for _ in range(max_depth):
        changed = False

        def replace_token(match: re.Match[str]) -> str:
            nonlocal changed
            token = match.group(1).strip()
            resolved = resolve_bracket_dynamic_token(token, game_loc, event)
            if not resolved:
                return match.group(0)
            changed = True
            return resolved

        updated = re.sub(r"\[([^\]]+)\]", replace_token, result)
        result = updated
        if not changed or ("[" not in result and "Show" not in result):
            break

    return result


def title_is_usable(title: str) -> bool:
    """Check if a resolved title is usable (not broken)."""
    if not title or len(title) < 3:
        return False
    if re.fullmatch(
        r"(?i)(the|a|an|la|le|les|el|los|las|lo|der|die|das|den|dem|des|ein|eine|einer|einem|einen|o|os|as|um|uma|un|une|l')",
        title.strip(" -:;,."),
    ):
        return False
    if title.startswith("$"):
        return False
    # Check for raw event ID pattern
    if re.match(r"^[\w_]+\.\d+(?:\.title)?$", title):
        return False
    if re.match(r"^Event:\s*[\w_]+\.\d+$", title):
        return False
    return True


def title_needs_fallback_hint(title: str) -> bool:
    lower = title.lower()
    visible = re.sub(r"\(\.\.\.\)", " ", lower)
    word_count = len(re.findall(r"[A-Za-zÀ-ÿĀ-žЁёА-я一-龯ぁ-んァ-ン]+", visible))
    # Generic placeholder titles should still fall back even when they are long enough.
    generic_markers = (
        "someone",
        "a city",
        "the city",
        "a second city",
        "the second city",
        "a dynasty",
        "the ruling dynasty",
        "a country",
        "the country",
        "our country",
        "current country",
        "that country",
        "country",
        "a province",
        "the province",
        "the ruler",
        "the artist",
        "the spouse",
        "the rival",
        "the region",
        "the area",
        "realm",
        "a condottiero",
        "this condottiero",
        "a writer",
        "this writer",
        "this character",
        "(...)",
    )
    if any(marker in lower for marker in generic_markers):
        return True
    if re.search(r"\b(?:the|a|an)\s+(?:our|foreign)\b", lower):
        return True
    return word_count < 3


def template_requests_specific_adjective(template: str) -> bool:
    """Return True when the original loc template expects a concrete adjective."""
    if not template:
        return False
    return bool(re.search(r"get(?:government\.)?adjective(?:withnotooltip)?", template, flags=re.IGNORECASE))


def title_has_generic_adjective_artifact(title: str, template: str) -> bool:
    """Detect titles/options that degraded to generic adjective placeholders like 'our' or 'foreign'."""
    if not title or not template_requests_specific_adjective(template):
        return False
    lowered = f" {title.lower()} "
    return " our " in lowered or " foreign " in lowered


def sanitize_generated_title(title: str) -> str:
    """Remove auto-generated comment/formatting fragments from event titles."""
    if not title:
        return title
    title = strip_loc_dynamic(title)
    title = title.replace('\\"', '"').replace("\t", " ")
    title = re.sub(r"^\s*#+\s*", "", title)
    title = re.sub(r"\s+triggered by\b.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+when it selects\b.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+#.*$", "", title)
    title = title.replace("#!", "")
    title = title.replace("#", "")
    title = re.sub(r"\s*\(\(\.\.\.\)\)\s*$", "", title).strip()
    title = re.sub(r"\s*\(\.\.\.\)\s*$", "", title).strip()
    title = re.sub(
        r"\s+(?:of|with|against|from|for|to|de la|de los|de las|de|del|des|do|da|du|di|en|in|auf|sur|von|van|der|den|dem|la|le|el|los|las|the)$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    title = re.sub(r"\s{2,}", " ", title).strip()
    return title.strip(" -:;,.")


def strip_preview_title_placeholders(title: str) -> str:
    """Remove unresolved placeholder fragments from translated preview titles."""
    if not title:
        return title
    title = re.sub(r'["\'“”„«»「」『』]*\(\.\.\.\)["\'“”„«»「」『』]*', " ", title)
    title = re.sub(r"\(\s*\)", " ", title)
    title = re.sub(r"\s{2,}", " ", title).strip()
    title = re.sub(
        r"\s+(?:of|with|against|from|for|to|de la|de los|de las|de|del|des|do|da|du|di|en|in|auf|sur|von|van|der|den|dem|la|le|el|los|las|the)$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    return title.strip(" -:;,.")


def strip_generic_title_context(title: str) -> str:
    """Drop generic dynamic-scope fragments so fallback titles stay readable."""
    if not title:
        return title
    cleaned = sanitize_generated_title(strip_preview_title_placeholders(title))
    cleaned = re.sub(
        r"\b(?:this|that|target)\s+character(?:['’]s)?\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:from|of|with|against|to|for|in)\s+(?:that|this|target|our|current)\s+(?:country|character|province|city|area|region|culture|dynasty)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:that|this|target|our|current)\s+(?:country|character|province|city|area|region|culture|dynasty)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -:;,.")
    return cleaned


def replace_generic_scope_phrases(
    text: str,
    saved_scope_hints: dict[str, dict[str, str]] | None,
    game_loc: dict[str, str],
) -> str:
    """Replace generic fallback phrases with concrete saved-scope names when known."""
    if not text:
        return text

    def possessive(name: str) -> str:
        return f"{name}'" if name.endswith(("s", "S")) else f"{name}'s"

    replacements = {
        "target_character": ("this character", "target character"),
        "target_country": ("that country", "target country"),
        "target_location": ("the city", "target location"),
        "target_dynasty": ("that dynasty", "target dynasty"),
        "target_ruler": ("the ruler", "target ruler"),
        "target_artist": ("the artist", "target artist"),
    }

    updated = text
    for scope_name, phrases in replacements.items():
        resolved = resolve_saved_scope_hint_name(scope_name, saved_scope_hints, game_loc)
        if not resolved:
            continue
        resolved_lower = resolved.lower()
        if resolved_lower in {
            "this character",
            "that country",
            "target country",
            "target character",
            "the city",
            "target location",
            "that dynasty",
            "the ruler",
            "target ruler",
            "the artist",
            "target artist",
        }:
            continue
        for phrase in phrases:
            updated = re.sub(
                rf"\b{re.escape(phrase)}['’]s\b",
                possessive(resolved),
                updated,
                flags=re.IGNORECASE,
            )
            updated = re.sub(
                rf"\b{re.escape(phrase)}\b",
                resolved,
                updated,
                flags=re.IGNORECASE,
            )
    return updated


def event_country_display_name(event: dict, game_loc: dict[str, str]) -> str:
    tags = event.get("tags") or []
    if not tags:
        return ""
    return resolve_named_entity(f"c:{tags[0]}", game_loc) or tags[0]


def repair_generated_title(title: str, event: dict, game_loc: dict[str, str]) -> str:
    """Repair common unresolved title placeholders into something readable."""
    repaired = sanitize_generated_title(title)
    repaired = re.sub(r"^\(\.\.\.\)(?:年の|年|년\s*)", "", repaired).strip()
    repaired = re.sub(r"^\(\.\.\.\)\s+", "", repaired).strip()
    repaired = re.sub(r"\s+(?:of|de|do|da|du|w)\s+\(\.\.\.\)(?:\s+(?:roku))?$", "", repaired, flags=re.IGNORECASE).strip()
    repaired = re.sub(r"\s+\(\.\.\.\)\s*года$", "", repaired, flags=re.IGNORECASE).strip()
    repaired = re.sub(r"\s+\(\.\.\.\)\s*roku$", "", repaired, flags=re.IGNORECASE).strip()

    country_name = event_country_display_name(event, game_loc)
    placeholder_removed = re.sub(
        r"(?:^|\s)the country(?:[A-Za-zÀ-ÿĀ-žЀ-ӿ_-]+)?(?:の|的)?",
        " ",
        repaired,
        flags=re.IGNORECASE,
    )
    placeholder_removed = re.sub(
        r"(?:^|\s)(?:our|current) country(?:[A-Za-zÀ-ÿĀ-žЀ-ӿ_-]+)?(?:の|的)?",
        " ",
        placeholder_removed,
        flags=re.IGNORECASE,
    )
    placeholder_removed = re.sub(
        r"(?:^|\s)(?:this|that|target)\s+character(?:'s)?",
        " ",
        placeholder_removed,
        flags=re.IGNORECASE,
    )
    placeholder_removed = re.sub(
        r"(?:^|\s)(?:the|this|target)\s+(?:artist|writer|explorer|heir|ruler|rival)(?:'s)?",
        " ",
        placeholder_removed,
        flags=re.IGNORECASE,
    )
    placeholder_removed = re.sub(
        r"(?:^|\s)(?:the\s+)?that culture(?:'s)?",
        " ",
        placeholder_removed,
        flags=re.IGNORECASE,
    )
    placeholder_removed = re.sub(r"\s{2,}", " ", placeholder_removed).strip(" -:;,.")
    if placeholder_removed and placeholder_removed != repaired:
        repaired = f"{placeholder_removed} ({country_name})" if country_name else placeholder_removed

    lowered = repaired.lower()
    for suffix in ("the country", "our country", "current country"):
        token = f" {suffix}"
        if lowered.endswith(token):
            base = repaired[: -len(token)].strip(" -:;,.")
            return f"{base} ({country_name})" if country_name else base
    return repaired


def normalize_title_case(title: str) -> str:
    if not title:
        return title
    title = sanitize_generated_title(title)
    if not title:
        return title
    return title[0].upper() + title[1:]


def _get_saved_scope_title_hints(event: dict) -> dict[str, dict[str, str]]:
    hints = event.get("_saved_scope_title_hints")
    if hints is None:
        expanded_nodes = expand_local_scripted_effects(
            parse_clausewitz_block(event.get("immediate_raw", "")),
            event.get("local_scripted_effects") or {},
        )
        tags = event.get("tags") or []
        hints = extract_saved_scope_title_hints_from_nodes(
            expanded_nodes,
            root_country_tag=str(tags[0]).strip().upper() if tags else "",
        )
        event["_saved_scope_title_hints"] = hints
    return hints


def _resolve_title_scope_name(saved_scope: str, event: dict, game_loc: dict[str, str]) -> str:
    hints = _get_saved_scope_title_hints(event)
    hint = hints.get(saved_scope.lower())
    if hint:
        if hint.get("kind") == "character":
            parts: list[str] = []
            for key in ("first_name", "last_name"):
                value = (hint.get(key) or "").strip()
                if not value:
                    continue
                parts.append(resolve_loc_text(value, game_loc) or humanize_identifier(value))
            if hint.get("dynasty"):
                dynasty_raw = hint["dynasty"].split(":", 1)[1] if ":" in hint["dynasty"] else hint["dynasty"]
                dynasty_name = humanize_identifier(dynasty_raw)
                dynasty_name = re.sub(r"\s+Dynasty$", "", dynasty_name, flags=re.IGNORECASE)
                if dynasty_name and (not parts or len(parts) == 1):
                    parts.append(dynasty_name)
            name = " ".join(part for part in parts if part).strip()
            if name:
                return name
        if hint.get("kind") == "entity":
            ref = hint.get("ref", "")
            resolved = resolve_named_entity(ref, game_loc)
            if resolved:
                return resolved
            if ref:
                return humanize_identifier(ref)
        if hint.get("kind") == "dynasty":
            ref = hint.get("ref", "")
            if ref.startswith("dynasty:"):
                dynasty_raw = ref.split(":", 1)[1]
                return re.sub(r"\s+Dynasty$", "", humanize_identifier(dynasty_raw), flags=re.IGNORECASE)

    return ""


def _resolve_title_scope_adjective(saved_scope: str, event: dict, game_loc: dict[str, str]) -> str:
    hints = _get_saved_scope_title_hints(event)
    hint = hints.get(saved_scope.lower())
    if not hint:
        return ""

    if hint.get("kind") == "entity":
        ref = hint.get("ref", "")
        if ref.startswith("c:"):
            return resolve_loc_argument(ref.split(":", 1)[1], game_loc, adjective=True)
        resolved = resolve_named_entity(ref, game_loc)
        if resolved:
            return derive_loc_adjective(resolved, ref)
    return ""


def _resolve_title_scope_dynasty(saved_scope: str, event: dict, game_loc: dict[str, str]) -> str:
    hints = _get_saved_scope_title_hints(event)
    hint = hints.get(saved_scope.lower())
    if not hint:
        return ""

    if hint.get("kind") == "character" and hint.get("dynasty"):
        dynasty_raw = hint["dynasty"].split(":", 1)[1] if ":" in hint["dynasty"] else hint["dynasty"]
        return re.sub(r"\s+Dynasty$", "", humanize_identifier(dynasty_raw), flags=re.IGNORECASE)

    if hint.get("kind") == "dynasty":
        ref = hint.get("ref", "")
        if ref.startswith("dynasty:"):
            dynasty_raw = ref.split(":", 1)[1]
            return re.sub(r"\s+Dynasty$", "", humanize_identifier(dynasty_raw), flags=re.IGNORECASE)

    return ""


def generic_dynamic_title_token(token: str) -> str:
    lower = token.lower()
    if "root.getcountry.getgovernment.getruler.getdynasty" in lower:
        return "the ruling dynasty"
    if ".getdynasty." in lower:
        if "target_dynasty" in lower:
            return "that dynasty"
        return "the dynasty"
    placeholder = strip_loc_dynamic(f"[{token}]")
    if placeholder and placeholder != "(...)":
        return placeholder
    return "(...)"


def resolve_dynamic_title_hint(title_key: str, event: dict, game_loc: dict[str, str]) -> str:
    """Resolve dynamic title placeholders from event setup when possible."""
    raw_title = (game_loc.get(title_key) or "").strip()
    if not raw_title:
        return ""

    raw_title = resolve_inline_loc_tokens(raw_title, game_loc)
    raw_title = resolve_bracket_loc_tokens(raw_title, game_loc, event=event)
    raw_title = raw_title.replace("#italic", "").replace("#!", "").strip()

    if "[" not in raw_title:
        return sanitize_generated_title(raw_title)

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        lower = token.lower()

        if lower in {
            "root.getcountry.getgovernment.getruler.getdynasty.getnamewithnotooltip",
            "root.getcountry.getgovernment.getruler.getdynasty.getname",
        }:
            return "the ruling dynasty"

        scope_match = re.fullmatch(r"(\w+)\.(?:getnamewithnotooltip|getname)", lower)
        if scope_match:
            resolved = _resolve_title_scope_name(scope_match.group(1), event, game_loc)
            return resolved or generic_dynamic_title_token(token)

        dynasty_match = re.fullmatch(r"(\w+)\.getdynasty\.(?:getnamewithnotooltip|getname)", lower)
        if dynasty_match:
            resolved = _resolve_title_scope_dynasty(dynasty_match.group(1), event, game_loc)
            return resolved or generic_dynamic_title_token(token)

        return generic_dynamic_title_token(token)

    replaced = re.sub(r"\[([^\]]+)\]", replace_token, raw_title)
    if replaced != raw_title or "[" not in replaced:
        return sanitize_generated_title(replaced)
    return ""


def generate_event_title(event: dict, game_loc: dict[str, str], lang: str) -> str:
    """Generate title for an event from game loc."""
    for title_key in (f"{event['id']}.title", f"{event['id']}.title.fallback", f"{event['id']}.t"):
        raw_template = resolve_loc_template_text(title_key, game_loc)
        resolved = resolve_dynamic_title_hint(title_key, event, game_loc) or resolve_loc_text(title_key, game_loc)
        resolved = repair_generated_title(resolved, event, game_loc)
        raw_clean = strip_generic_title_context(strip_preview_title_placeholders(normalize_title_case(resolved)))
        clean = strip_generic_title_context(strip_preview_title_placeholders(
            normalize_title_case(gti18n.postprocess_generated_title(gti18n.localize_generated_text(raw_clean, lang), lang))
        ))
        if title_is_usable(clean):
            if (
                title_needs_fallback_hint(raw_clean)
                or title_needs_fallback_hint(clean)
                or preview_has_unresolved_placeholders(clean)
                or title_has_generic_adjective_artifact(raw_clean, raw_template)
                or title_has_generic_adjective_artifact(clean, raw_template)
            ):
                fallback_hint = event.get("comment_hint", "").strip() or resolve_dynamic_title_hint(title_key, event, game_loc)
                comment_hint = strip_generic_title_context(strip_preview_title_placeholders(
                    normalize_title_case(
                        gti18n.postprocess_generated_title(gti18n.localize_generated_text(fallback_hint, lang), lang)
                    )
                ))
                if (
                    title_is_usable(comment_hint)
                    and not preview_has_unresolved_placeholders(comment_hint)
                    and not title_needs_fallback_hint(comment_hint)
                ):
                    return comment_hint
                if title_is_usable(raw_clean):
                    return raw_clean
            return clean
    comment_hint = normalize_title_case(
        gti18n.postprocess_generated_title(
            gti18n.localize_generated_text(
                event.get("comment_hint", "").strip() or resolve_dynamic_title_hint(f"{event['id']}.title", event, game_loc),
                lang,
            ),
            lang,
        )
    )
    comment_hint = strip_generic_title_context(strip_preview_title_placeholders(comment_hint))
    if comment_hint and not title_needs_fallback_hint(comment_hint):
        return comment_hint
    return normalize_title_case(gti18n.localize_generated_text(humanize_identifier(event["id"]), lang))


def generate_event_subtitle(event: dict, lang: str) -> str:
    """Generate the prominent timeline and chance line shown beneath the title."""
    return generate_event_window_summary(event, lang)


def generate_event_desc(event: dict, game_loc: dict[str, str], lang: str) -> str:
    """Generate description for an event from game loc."""
    candidates: list[str] = []
    for key in (f"{event['id']}.desc", f"{event['id']}.historical_info"):
        raw_text = game_loc.get(key, "")
        if not raw_text:
            continue
        clean = gti18n.localize_generated_text(
            strip_loc_dynamic(resolve_bracket_loc_tokens(resolve_inline_loc_tokens(raw_text, game_loc), game_loc, event=event)),
            lang,
        )
        if len(clean) > 10:
            candidates.append(clean)
    if candidates:
        def score(candidate: str) -> tuple[int, int]:
            lowered = candidate.lower()
            placeholder_count = candidate.count("(...)")
            generic_count = sum(
                lowered.count(marker)
                for marker in ("this character", "that country", "this figure", "current scope")
            )
            return (placeholder_count + generic_count, -len(candidate))

        best = min(candidates, key=score)
        return sanitize_preview_paragraph(truncate_generated_text(best, 500), lang)
    fallback = gti18n.localize_generated_text(f"No detailed description available. Source: {event['id']}.", lang)
    return sanitize_preview_paragraph(fallback, lang)


def truncate_generated_text(text: str, limit: int) -> str:
    """Trim long generated text without leaving broken escape markers behind."""
    if len(text) <= limit:
        return text
    trimmed = text[: max(0, limit - 3)].rstrip()
    trimmed = trimmed.rstrip("\\")
    return trimmed + "..."


def dedupe_text_lines(lines: list[str]) -> list[str]:
    """Preserve order while removing empty or immediately repeated lines."""
    result: list[str] = []
    previous: str | None = None
    for line in lines:
        normalized = re.sub(r"[ \t]+", " ", line.rstrip())
        if not normalized or normalized == previous:
            continue
        previous = normalized
        result.append(line.rstrip())
    return result


def preview_has_unresolved_placeholders(text: str) -> bool:
    return "(...)" in (text or "")


def preview_desc_fallback(lang: str) -> str:
    english = "This event uses dynamic vanilla text that cannot be previewed cleanly before it fires."
    localized = gti18n.localize_generated_text(english, lang)
    return localize_generated_line(localized, lang)


def preview_requirements_fallback(lang: str) -> str:
    english = "- Some dynamic requirements cannot be previewed cleanly outside the live event scope."
    localized = gti18n.localize_generated_text(english, lang)
    return localize_generated_line(localized, lang)


def preview_outcomes_fallback(lang: str) -> str:
    english = "- Some dynamic outcomes cannot be previewed cleanly before the event fires."
    localized = gti18n.localize_generated_text(english, lang)
    return localize_generated_line(localized, lang)


def sanitize_preview_paragraph(text: str, lang: str) -> str:
    if not preview_has_unresolved_placeholders(text):
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or preview_has_unresolved_placeholders(sentence):
            continue
        kept.append(sentence)

    cleaned = " ".join(dedupe_text_lines(kept)).strip()
    if cleaned:
        return truncate_generated_text(cleaned, 500)
    return preview_desc_fallback(lang)


def sanitize_preview_block(lines: list[str], fallback_line: str) -> list[str]:
    cleaned: list[str] = []
    dropped_placeholder = False
    previous_normalized: str | None = None
    previous_blank = True

    for raw_line in lines:
        line = raw_line.rstrip()
        if preview_has_unresolved_placeholders(line):
            dropped_placeholder = True
            continue

        normalized = re.sub(r"[ \t]+", " ", line).strip()
        if not normalized:
            if cleaned and not previous_blank:
                cleaned.append("")
            previous_blank = True
            continue

        if normalized == previous_normalized:
            previous_blank = False
            continue

        cleaned.append(line)
        previous_normalized = normalized
        previous_blank = False

    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    if dropped_placeholder:
        if cleaned:
            cleaned.append("")
        cleaned.append(fallback_line)

    return cleaned


def ensure_sentence(text: str) -> str:
    if not text:
        return text
    if text.endswith((".", "!", "?", ":")):
        return text
    return f"{text}."


def capitalize_sentence_start(text: str) -> str:
    if not text:
        return text
    first = text[0]
    if first.isalpha() and first.islower():
        return first.upper() + text[1:]
    return text


def capitalize_outcome_bullets(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith("  - "):
            prefix = "  - "
            body = line[len(prefix):]
            lines.append(prefix + capitalize_sentence_start(body))
            continue
        lines.append(line)
    return "\n".join(lines)


def format_bullet(text: str, indent: int = 0) -> str:
    return f"{'  ' * indent}- {ensure_sentence(text)}"


def encode_loc_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def unescape_loc_value(value: str) -> str:
    """Decode common Paradox loc escapes and discard invalid trailing escape markers."""
    result: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\" or i + 1 >= len(value):
            result.append(ch)
            i += 1
            continue

        nxt = value[i + 1]
        if nxt == "n":
            result.append("\n")
        elif nxt == "r":
            result.append("\r")
        elif nxt == "t":
            result.append("\t")
        elif nxt == '"':
            result.append('"')
        elif nxt == "\\":
            result.append("\\")
        else:
            result.append(nxt)
        i += 2
    return "".join(result)


def resolve_loc_text(key: str, game_loc: dict[str, str]) -> str:
    """Resolve a localization key, following simple $other.key$ aliases."""
    if not key:
        return ""

    seen: set[str] = set()
    current_key = key
    current_value = game_loc.get(current_key, "")

    while current_value.startswith("$") and current_value.endswith("$"):
        next_key = current_value[1:-1]
        if next_key in seen:
            break
        seen.add(next_key)
        next_value = game_loc.get(next_key, "")
        if not next_value:
            break
        current_key = next_key
        current_value = next_value

    current_value = resolve_inline_loc_tokens(current_value, game_loc)
    current_value = resolve_bracket_loc_tokens(current_value, game_loc)
    return strip_loc_dynamic(current_value).strip()


def resolve_loc_template_text(key: str, game_loc: dict[str, str]) -> str:
    """Resolve simple $aliases$ but keep dynamic loc markup untouched."""
    if not key:
        return ""

    seen: set[str] = set()
    current_key = key
    current_value = game_loc.get(current_key, "")

    while current_value.startswith("$") and current_value.endswith("$"):
        next_key = current_value[1:-1]
        if next_key in seen:
            break
        seen.add(next_key)
        next_value = game_loc.get(next_key, "")
        if not next_value:
            break
        current_key = next_key
        current_value = next_value

    return current_value.strip()


def set_current_game_loc(game_loc: dict[str, str]) -> None:
    """Set the active localization map for name resolution during one language pass."""
    global CURRENT_GAME_LOC
    CURRENT_GAME_LOC = game_loc or {}


def resolve_named_entity(value: str, game_loc: dict[str, str] | None = None) -> str:
    """Resolve a script identifier to a localized display name when possible."""
    loc = game_loc if game_loc is not None else CURRENT_GAME_LOC
    raw = str(value).strip().strip('"')
    if not raw or not loc:
        return ""

    core = raw[2:] if raw.startswith("c:") else raw
    if ":" in core and not core.startswith("scope:"):
        core = core.split(":", 1)[1]
    core = core.strip()
    if not core:
        return ""

    candidates: list[str] = [core]
    for suffix in (
        ".province_definition",
        ".location_definition",
        ".province",
        ".location",
        ".owner",
        ".controller",
        ".ruler",
        ".dynasty",
        ".market",
    ):
        if core.endswith(suffix):
            candidates.append(core[: -len(suffix)])
    if core.endswith("_culture"):
        candidates.append(core[: -len("_culture")])

    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        resolved = resolve_loc_text(candidate, loc)
        if not resolved:
            continue
        cleaned = strip_loc_dynamic(
            resolve_bracket_loc_tokens(resolve_inline_loc_tokens(resolved, loc), loc)
        ).strip()
        if cleaned and (cleaned.lower() != candidate.lower() or candidate != core):
            return re.sub(r"\s{2,}", " ", cleaned)
    return ""


def humanize_identifier(value: str) -> str:
    raw = str(value).strip().strip('"')
    if not raw:
        return ""
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return raw
    if raw.startswith("estate_type:"):
        raw = raw[len("estate_type:"):]
        raw = raw.replace(".", " ").replace("_", " ").strip()
        raw = re.sub(r"\s+", " ", raw)
        return raw.title()
    raw_lower = raw.lower()
    direct_labels = {
        "root": "current country",
        "this": "current scope",
        "prev": "previous scope",
        "prevprev": "the scope before that",
        "ruler": "the ruler",
        "regent": "the regent",
        "heir": "heir",
        "owner": "owner",
        "controller": "controller",
        "leader": "leader",
        "target": "target",
        "type": "type",
        "value": "value",
        "name": "name",
        "count": "count",
        "father": "father",
        "mother": "mother",
        "female": "female",
        "adult": "adult",
        "married": "married",
        "capital": "capital",
        "root.capital": "the current capital",
    }
    if raw_lower in direct_labels:
        return direct_labels[raw_lower]
    resolved_name = resolve_named_entity(raw)
    if resolved_name:
        return resolved_name
    if raw_lower in {"root.ruler", "root.government.ruler"}:
        return "the ruler"
    if raw_lower == "root.regent":
        return "the regent"
    if raw_lower == "capital.market":
        return "the capital market"
    if raw.startswith("c:"):
        return raw[2:].upper()
    if re.fullmatch(r"[A-Z0-9]{2,4}", raw):
        return raw.upper()

    had_prefix = False
    for prefix in (
        "religion:",
        "religion_group:",
        "culture:",
        "culture_group:",
        "language:",
        "casus_belli:",
        "estate_type:",
        "estate_privilege:",
        "dynasty:",
        "scope:",
        "location:",
        "location_definition:",
        "character:",
        "country:",
        "modifier:",
        "province:",
        "province_definition:",
        "region:",
        "area:",
        "goods:",
        "government_type:",
        "government_reform:",
        "building_type:",
        "international_organization:",
        "advance_type:",
        "work_of_art:",
        "institution:",
        "policy:",
        "law:",
        "continent:",
        "relation_type:",
        "special_status:",
        "heir_selection:",
        "pop_type:",
        "situation:",
        "disease:",
        "disaster_type:",
    ):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            had_prefix = True
            break

    raw = re.sub(r"_scope$", "", raw, flags=re.IGNORECASE)
    raw = raw.replace(".", " ").replace("_", " ").strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw.title() if had_prefix or ":" in raw or "_" in raw or " " in raw else raw


def display_scripted_effect_name(value: str) -> str:
    raw = str(value).strip().strip('"')
    if raw.endswith("_effect"):
        raw = raw[:-7]
    return humanize_identifier(raw)


def build_scripted_effect_params(
    value: str | list[ClausewitzNode],
) -> dict[str, str]:
    if not isinstance(value, list):
        return {}
    params: dict[str, str] = {}
    for child in value:
        if isinstance(child.value, str):
            params[child.key] = child.value
    return params


def substitute_scripted_effect_value(
    value: str | list[ClausewitzNode],
    params: dict[str, str],
) -> str | list[ClausewitzNode]:
    if isinstance(value, list):
        return [
            ClausewitzNode(
                key=node.key,
                operator=node.operator,
                value=substitute_scripted_effect_value(node.value, params),
            )
            for node in value
        ]

    text = str(value)
    for key, replacement in params.items():
        text = text.replace(f"${key}$", replacement)
    return text


def summarize_builtin_scripted_effect(
    effect_name: str,
    value: str | list[ClausewitzNode],
) -> list[str] | None:
    params = build_scripted_effect_params(value)

    if effect_name == "change_gold_effect":
        scale = params.get("scale", "").strip()
        try:
            return ["Decreases treasury"] if float(scale) < 0 else ["Increases treasury"]
        except ValueError:
            return ["Changes treasury"]

    if effect_name == "change_estate_gold_effect":
        estate = params.get("estate", "")
        estate_text = humanize_identifier(estate) if estate else "an estate"
        return [f"Transfers gold to {estate_text}"]

    return None


def expand_scripted_effect_nodes(
    effect_name: str,
    value: str | list[ClausewitzNode],
    local_scripted_effects: dict[str, list[ClausewitzNode]] | None,
) -> list[ClausewitzNode] | None:
    definition = None
    if local_scripted_effects:
        definition = local_scripted_effects.get(effect_name)
    if definition is None:
        definition = SCRIPTED_EFFECT_DEFS.get(effect_name)
    if definition is None:
        return None

    params = build_scripted_effect_params(value)
    return substitute_scripted_effect_value(definition, params)  # type: ignore[return-value]


def format_character_ref(value: str) -> str:
    raw = str(value).strip().strip('"')
    if raw.startswith("character:"):
        raw = raw[len("character:"):]
    raw = re.sub(r"^[a-z]{3,4}_", "", raw)
    return humanize_identifier(raw)


def resolve_saved_scope_hint_name(
    value: str,
    saved_scope_hints: dict[str, dict[str, str]] | None = None,
    game_loc: dict[str, str] | None = None,
) -> str:
    raw = str(value).strip().strip('"')
    if not raw:
        return ""
    hints = saved_scope_hints or {}
    hint = hints.get(raw.lower())
    if not hint:
        return ""

    if hint.get("kind") == "character":
        parts: list[str] = []
        for key in ("first_name", "last_name"):
            piece = (hint.get(key) or "").strip()
            if not piece:
                continue
            resolved = resolve_loc_text(piece, game_loc) if game_loc else ""
            parts.append(resolved or humanize_identifier(piece))
        if not parts and hint.get("dynasty"):
            dynasty_raw = hint["dynasty"].split(":", 1)[1] if ":" in hint["dynasty"] else hint["dynasty"]
            parts.append(re.sub(r"\s+Dynasty$", "", humanize_identifier(dynasty_raw), flags=re.IGNORECASE))
        return " ".join(part for part in parts if part).strip()

    if hint.get("kind") == "entity":
        ref = hint.get("ref", "")
        resolved = resolve_named_entity(ref, game_loc) if ref and game_loc else ""
        return resolved or humanize_identifier(ref)

    if hint.get("kind") == "dynasty":
        ref = hint.get("ref", "")
        if ref.startswith("dynasty:"):
            return re.sub(r"\s+Dynasty$", "", humanize_identifier(ref.split(":", 1)[1]), flags=re.IGNORECASE)

    return ""


def format_country_ref(
    value: str,
    saved_scope_hints: dict[str, dict[str, str]] | None = None,
    game_loc: dict[str, str] | None = None,
) -> str:
    raw = str(value).strip().strip('"')
    if raw.lower() == "root":
        return "current country"
    if raw.startswith("scope:"):
        return format_scalar_value(raw, saved_scope_hints=saved_scope_hints, game_loc=game_loc)
    resolved_name = resolve_named_entity(raw if raw.startswith("c:") else f"c:{raw}")
    if resolved_name:
        return resolved_name
    if raw.startswith("c:"):
        raw = raw[2:]
    if re.fullmatch(r"[A-Z0-9]{2,4}", raw):
        return raw.upper()
    return humanize_identifier(raw)


def format_dynasty_ref(value: str) -> str:
    text = humanize_identifier(value)
    if text.lower().endswith("dynasty"):
        return text
    return f"{text} Dynasty"


def format_cb_ref(value: str) -> str:
    raw = str(value).strip().strip('"')
    if raw.startswith("casus_belli:"):
        raw = raw.split(":", 1)[1]
    raw = re.sub(r"^cb_", "", raw, flags=re.IGNORECASE)
    return humanize_identifier(raw)


def format_modifier_ref(value: str) -> str:
    raw = str(value).strip().strip('"')
    raw = re.sub(r"^[A-Za-z]{2,4}_", "", raw)
    raw = re.sub(r"_modifier$", "", raw, flags=re.IGNORECASE)
    resolved_name = resolve_named_entity(raw)
    if resolved_name:
        return resolved_name
    return humanize_identifier(raw)


def format_building_ref(value: str) -> str:
    resolved_name = resolve_named_entity(value)
    if resolved_name:
        return resolved_name
    return humanize_identifier(value)


def format_trait_ref(value: str) -> str:
    resolved_name = resolve_named_entity(value)
    if resolved_name:
        return resolved_name
    return humanize_identifier(value)


def format_event_ref(value: str, game_loc: dict[str, str]) -> str:
    raw = str(value).strip().strip('"')
    if not raw:
        return ""
    resolved = normalize_title_case(resolve_loc_text(f"{raw}.title", game_loc))
    if resolved and "$" not in resolved and not re.fullmatch(r"[\w_]+\.\d+", resolved):
        cleaned = strip_generic_title_context(resolved)
        if title_is_usable(cleaned) and not title_needs_fallback_hint(cleaned):
            return cleaned
        if title_needs_fallback_hint(resolved):
            return "a follow-up event"
        return resolved
    return raw


def format_saved_scope_name(
    value: str,
    saved_scope_hints: dict[str, dict[str, str]] | None = None,
    game_loc: dict[str, str] | None = None,
) -> str:
    raw = str(value).strip().strip('"')
    if not raw:
        return ""
    resolved_hint = resolve_saved_scope_hint_name(raw, saved_scope_hints, game_loc)
    if resolved_hint:
        return resolved_hint
    aliases = {
        "target_colony": "target colony",
        "target_country": "target country",
        "target_location": "target location",
        "target_location2": "second target location",
        "target_province": "target province",
        "target_character": "target character",
        "target_ruler": "target ruler",
        "target_artist": "target artist",
        "current_wife": "current wife",
        "target_root_country": "target root country",
    }
    lowered = raw.lower()
    if lowered in aliases:
        return aliases[lowered]
    emigration_match = re.fullmatch(r"emigration_province_(\d+)", lowered)
    if emigration_match:
        ordinal = {
            "1": "first",
            "2": "second",
            "3": "third",
        }.get(emigration_match.group(1), emigration_match.group(1))
        suffix = " emigration province" if ordinal.isalpha() else ""
        return f"{ordinal}{suffix}".strip()
    return humanize_identifier(raw)


def format_scalar_value(
    value: str,
    saved_scope_hints: dict[str, dict[str, str]] | None = None,
    game_loc: dict[str, str] | None = None,
) -> str:
    raw = str(value).strip().strip('"')
    if not raw:
        return ""
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return raw
    if raw.lower() == "root":
        return "current country"
    if raw.lower() == "this":
        return "current scope"
    if raw.lower() == "prev":
        return "previous scope"
    if raw.lower() == "prevprev":
        return "the scope before that"
    if raw.lower() in {"root.ruler", "root.government.ruler"}:
        return "the current ruler"
    if raw.lower() == "root.ruler.dynasty":
        return "the dynasty of the current ruler"
    if raw.lower() == "root.regent":
        return "the regent"
    if raw.lower() == "root.capital":
        return "the current capital"
    if raw.lower() in {"this.location", "this.location_definition", "this.province", "this.province_definition"}:
        return "this province"
    if raw == "ruler":
        return "the ruler"
    if raw == "capital.market":
        return "the capital market"
    if raw.startswith("scope:emigration_province_") and (
        raw.endswith(".province_definition")
        or raw.endswith(".location_definition")
        or raw.endswith(".province")
        or raw.endswith(".location")
    ):
        scoped = raw[6:]
        emigration_match = re.fullmatch(
            r"emigration_province_(\d+)\.(?:province_definition|location_definition|province|location)",
            scoped.lower(),
        )
        if emigration_match:
            ordinal = {
                "1": "first",
                "2": "second",
                "3": "third",
            }.get(emigration_match.group(1), emigration_match.group(1))
            suffix = " emigration province" if ordinal.isalpha() else ""
            return f"the {ordinal}{suffix}".strip()
    if raw.endswith(".province_definition") or raw.endswith(".location_definition"):
        suffix = ".province_definition" if raw.endswith(".province_definition") else ".location_definition"
        return f"the province of {format_scalar_value(raw[:-len(suffix)], saved_scope_hints, game_loc)}"
    if raw.endswith(".location"):
        return f"the location of {format_scalar_value(raw[:-9], saved_scope_hints, game_loc)}"
    if raw.endswith(".owner"):
        return f"the owner of {humanize_identifier(raw[:-6])}"
    if raw.endswith(".ruler"):
        return f"the ruler of {humanize_identifier(raw[:-6])}"
    if raw.endswith(".dynasty"):
        return f"the dynasty of {format_scalar_value(raw[:-8], saved_scope_hints, game_loc)}"
    if raw.endswith(".province"):
        return f"the province of {humanize_identifier(raw[:-9])}"
    if raw.endswith(".market"):
        return f"the market of {humanize_identifier(raw[:-7])}"
    if raw.startswith("c:"):
        return format_country_ref(raw, saved_scope_hints=saved_scope_hints, game_loc=game_loc)
    if raw.startswith("scope:"):
        scoped = raw[6:]
        emigration_match = re.fullmatch(
            r"emigration_province_(\d+)\.(?:province_definition|location_definition|province|location)",
            scoped.lower(),
        )
        if emigration_match:
            ordinal = {
                "1": "first",
                "2": "second",
                "3": "third",
            }.get(emigration_match.group(1), emigration_match.group(1))
            suffix = " emigration province" if ordinal.isalpha() else ""
            return f"the {ordinal}{suffix}".strip()
        if scoped.endswith(".owner"):
            return f"the owner of {format_saved_scope_name(scoped[:-6], saved_scope_hints, game_loc)}"
        if scoped.endswith(".ruler"):
            return f"the ruler of {format_saved_scope_name(scoped[:-6], saved_scope_hints, game_loc)}"
        if scoped.endswith(".dynasty"):
            return f"the dynasty of {format_saved_scope_name(scoped[:-8], saved_scope_hints, game_loc)}"
        if scoped.endswith(".province_definition") or scoped.endswith(".location_definition"):
            suffix = ".province_definition" if scoped.endswith(".province_definition") else ".location_definition"
            return f"the province of {format_saved_scope_name(scoped[:-len(suffix)], saved_scope_hints, game_loc)}"
        if scoped.endswith(".province") or scoped.endswith(".location"):
            suffix = ".province" if scoped.endswith(".province") else ".location"
            return f"the province of {format_saved_scope_name(scoped[:-len(suffix)], saved_scope_hints, game_loc)}"
        return format_saved_scope_name(scoped, saved_scope_hints, game_loc)
    if raw.startswith("casus_belli:"):
        return format_cb_ref(raw)
    if raw.startswith("dynasty:") or raw.endswith("_dynasty"):
        return format_dynasty_ref(raw)
    if raw.startswith("character:"):
        return format_character_ref(raw)
    if raw.startswith("var:"):
        return humanize_identifier(raw[4:])
    if raw.startswith("location:") or raw.startswith("province:") or raw.startswith("location_definition:") or raw.startswith("province_definition:"):
        resolved_name = resolve_named_entity(raw)
        if resolved_name:
            return resolved_name
        text = humanize_identifier(raw)
        if text.endswith(" Province"):
            text = text[:-9]
        return text
    if raw.startswith("religion:") or raw.startswith("culture:") or raw.startswith("religion_group:") or raw.startswith("culture_group:"):
        resolved_name = resolve_named_entity(raw)
        if resolved_name:
            return resolved_name
        return humanize_identifier(raw)
    if raw.lower() in {"yes", "no"}:
        return raw.lower()
    resolved_name = resolve_named_entity(raw)
    if resolved_name:
        return resolved_name
    return humanize_identifier(raw) if ":" in raw or "_" in raw else raw


def join_phrases(phrases: list[str]) -> str:
    filtered = [phrase.strip() for phrase in phrases if phrase.strip()]
    if not filtered:
        return ""
    if len(filtered) == 1:
        return filtered[0]
    if len(filtered) == 2:
        return f"{filtered[0]} and {filtered[1]}"
    return ", ".join(filtered[:-1]) + f", and {filtered[-1]}"


def strip_subject_prefix(text: str, subject: str) -> str:
    prefix = f"{subject} "
    return text[len(prefix):] if text.startswith(prefix) else text


def scopeify_condition(text: str) -> str:
    lower = text.lower()
    if lower.startswith("owner must have "):
        return "owner has " + text[len("Owner must have "):]
    if lower.startswith("owner must be "):
        return "owner is " + text[len("Owner must be "):]
    if lower.startswith("must be able to "):
        return "can " + text[len("Must be able to "):]
    if lower.startswith("must be alive"):
        return "is alive"
    if lower.startswith("must not be alive"):
        return "is not alive"
    if lower.startswith("must exist"):
        return "exists"
    if lower.startswith("must not exist"):
        return "does not exist"
    if lower.startswith("must not be "):
        return "is not " + text[len("Must not be "):]
    if lower.startswith("must be "):
        return "is " + text[len("Must be "):]
    if lower.startswith("must have "):
        return "has " + text[len("Must have "):]
    if lower.startswith("must own "):
        return "owns " + text[len("Must own "):]
    return text[0].lower() + text[1:] if text else text


def find_child(nodes: list[ClausewitzNode], key: str) -> ClausewitzNode | None:
    for node in nodes:
        if node.key == key:
            return node
    return None


def child_scalar(nodes: list[ClausewitzNode], key: str) -> str:
    node = find_child(nodes, key)
    if node and isinstance(node.value, str):
        return node.value
    return ""


def extract_saved_scope_title_hints_from_nodes(
    nodes: list[ClausewitzNode],
    *,
    root_country_tag: str = "",
) -> dict[str, dict[str, str]]:
    """Collect simple saved-scope names we can reuse for dynamic titles."""
    hints: dict[str, dict[str, str]] = {}

    def walk(current_nodes: list[ClausewitzNode], *, current_scope_ref: str = "") -> None:
        for node in current_nodes:
            if not isinstance(node.value, list):
                if node.key in {"save_scope_as", "save_temporary_scope_as"} and current_scope_ref:
                    scope_name = str(node.value).strip()
                    if scope_name:
                        hints[scope_name.lower()] = {
                            "kind": "entity",
                            "ref": current_scope_ref,
                        }
                continue

            scope_name = (
                child_scalar(node.value, "save_scope_as")
                or child_scalar(node.value, "save_temporary_scope_as")
            ).strip()

            if node.key == "create_character" and scope_name:
                hints[scope_name.lower()] = {
                    "kind": "character",
                    "first_name": child_scalar(node.value, "first_name"),
                    "last_name": child_scalar(node.value, "last_name"),
                    "dynasty": child_scalar(node.value, "dynasty"),
                }
            elif scope_name and (
                node.key.startswith("location:")
                or node.key.startswith("province:")
                or node.key.startswith("location_definition:")
                or node.key.startswith("province_definition:")
                or node.key.startswith("c:")
            ):
                hints[scope_name.lower()] = {
                    "kind": "entity",
                    "ref": node.key,
                }
            elif scope_name and node.key.startswith("dynasty:"):
                hints[scope_name.lower()] = {
                    "kind": "dynasty",
                    "ref": node.key,
                }
            elif scope_name and node.key.startswith("character:"):
                hints[scope_name.lower()] = {
                    "kind": "entity",
                    "ref": node.key,
                }

            next_scope_ref = current_scope_ref
            if (
                node.key.startswith("location:")
                or node.key.startswith("province:")
                or node.key.startswith("location_definition:")
                or node.key.startswith("province_definition:")
                or node.key.startswith("c:")
                or node.key.startswith("character:")
                or node.key.startswith("dynasty:")
            ):
                next_scope_ref = node.key

            walk(node.value, current_scope_ref=next_scope_ref)

    initial_scope_ref = f"c:{root_country_tag.strip().upper()}" if root_country_tag else ""
    walk(nodes, current_scope_ref=initial_scope_ref)
    return hints


def extract_saved_scope_title_hints(block_text: str) -> dict[str, dict[str, str]]:
    """Collect simple saved-scope names we can reuse for dynamic titles."""
    if not block_text.strip():
        return {}
    return extract_saved_scope_title_hints_from_nodes(parse_clausewitz_block(block_text))


def infer_direction(value: str) -> int:
    raw = str(value).strip().lower()
    try:
        numeric = float(raw)
        if numeric > 0:
            return 1
        if numeric < 0:
            return -1
        return 0
    except ValueError:
        pass

    positive = ("bonus", "boost", "increase", "gain", "positive", "good")
    negative = ("penalty", "malus", "decrease", "loss", "negative", "cost", "bad")
    if any(marker in raw for marker in positive):
        return 1
    if any(marker in raw for marker in negative):
        return -1
    return 0


def describe_comparison(stat_label: str, operator: str, value: str) -> str:
    display = format_scalar_value(value)
    if operator == "=":
        if display in {"yes", "no"}:
            return f"{stat_label} must be {display}"
        return f"{stat_label} must be {display}"
    if operator == ">=":
        return f"{stat_label} must be at least {display}"
    if operator == "<=":
        return f"{stat_label} must be at most {display}"
    if operator == ">":
        return f"{stat_label} must be greater than {display}"
    if operator == "<":
        return f"{stat_label} must be less than {display}"
    return f"{stat_label} must satisfy {operator} {display}"


def is_country_scope_key(key: str) -> bool:
    return key.startswith("c:")


def format_scope_subject(
    key: str,
    saved_scope_hints: dict[str, dict[str, str]] | None = None,
    game_loc: dict[str, str] | None = None,
) -> str:
    raw = str(key).strip().strip('"')
    if not raw:
        return ""
    if raw.lower() == "root":
        return "Current country"
    if raw.lower() == "this":
        return "Current scope"
    if raw.lower() == "prev":
        return "Previous scope"
    if raw.lower() in {"root.ruler", "root.government.ruler"}:
        return "The ruler"
    if raw.lower() == "root.regent":
        return "The regent"
    if raw == "culture":
        return "The culture"
    if raw == "ruler":
        return "The ruler"
    if raw == "capital":
        return "The capital"
    if raw == "capital.market":
        return "The capital market"
    if raw == "ruler_or_regent":
        return "The ruler or regent"
    if raw == "ruler_or_heir_if_regent":
        return "The ruler or heir if regent"
    if raw == "owner":
        return "The owner"
    if raw == "controller":
        return "The controller"
    if raw == "leader":
        return "The leader"
    if raw.endswith(".owner"):
        return f"The owner of {humanize_identifier(raw[:-6])}"
    if raw.endswith(".ruler"):
        return f"The ruler of {humanize_identifier(raw[:-6])}"
    if raw.endswith(".continent"):
        return f"The continent of {humanize_identifier(raw[:-10])}"
    if raw.endswith(".market"):
        return f"The market of {humanize_identifier(raw[:-7])}"
    if raw.startswith("character:"):
        return format_character_ref(raw)
    if raw.startswith("location:") or raw.startswith("location_definition:"):
        return humanize_identifier(raw)
    if raw.startswith("province:") or raw.startswith("province_definition:"):
        return humanize_identifier(raw)
    if raw.startswith("religion:") or raw.startswith("culture:"):
        return humanize_identifier(raw)
    if raw.startswith("scope:"):
        return capitalize_sentence_start(format_scalar_value(raw, saved_scope_hints, game_loc))
    if raw.startswith("international_organization:"):
        return humanize_identifier(raw)
    if raw.startswith("root."):
        return humanize_identifier(raw)
    if is_country_scope_key(raw):
        return format_country_ref(raw, saved_scope_hints=saved_scope_hints, game_loc=game_loc)
    return ""


def format_quantifier_label(key: str) -> str:
    quantifier_labels = {
        "any_rival": "At least one rival must satisfy:",
        "any_subject": "At least one subject must satisfy:",
        "any_character": "At least one character must satisfy:",
        "any_artist": "At least one artist must satisfy:",
        "any_cabinet_character": "At least one cabinet character must satisfy:",
        "any_pop": "At least one pop must satisfy:",
        "any_rebel": "At least one rebel must satisfy:",
        "any_country_sub_unit": "At least one country sub-unit must satisfy:",
        "any_owned_rural_location": "At least one owned rural location must satisfy:",
        "random_rival": "A rival must satisfy:",
        "any_owned_location": "At least one owned location must satisfy:",
        "every_owned_location": "Every owned location must satisfy:",
    }
    return quantifier_labels.get(key, "")


def format_condition_label(key: str) -> str:
    raw = str(key).strip().strip('"')
    if not raw:
        return ""

    function_match = re.match(r"([^(]+)\((.+)\)$", raw)
    if function_match:
        fn = function_match.group(1)
        arg = format_scalar_value(function_match.group(2))
        if fn == "religion_percentage_in_country":
            return f"Share of {arg} religion in country"
        if fn == "religion_group_percentage_in_country":
            return f"Share of {arg} religion group in country"
        if fn == "culture_percentage_in_country":
            return f"Share of {arg} culture in country"
        if fn == "culture_group_percentage_in_country":
            return f"Share of {arg} culture group in country"
        if fn == "language_percentage_in_country":
            return f"Share of {arg} language in country"
        if fn == "estate_power":
            return f"Power of {arg}"
        return f"{humanize_identifier(fn)} of {arg}"

    direct_labels = {
        "religion.group": "Religion group",
        "ruler": "Ruler",
        "owner": "Owner",
        "controller": "Controller",
        "leader": "Leader",
        "target": "Target",
        "value": "Value",
        "type": "Type",
        "name": "Name",
        "count": "Count",
        "father": "Father",
        "mother": "Mother",
        "province_definition": "Province",
        "location_definition": "Location",
        "subject_type": "Subject type",
        "subject_of": "Subject of",
        "age_in_years": "Age in years",
        "num_of_children": "Number of children",
        "average_satisfaction": "Average satisfaction",
        "expected_army_size": "Expected army size",
        "capital_sub_continent": "Capital sub-continent",
        "first_spouse": "First spouse",
        "monthly_balance": "Monthly balance",
        "num_loans": "Number of loans",
        "relation_type": "Relation type",
        "special_status": "Special status",
    }
    if raw in direct_labels:
        return direct_labels[raw]
    if raw.endswith(".owner"):
        return f"Owner of {humanize_identifier(raw[:-6])}"
    if raw.endswith(".continent"):
        return f"Continent of {humanize_identifier(raw[:-10])}"
    if raw.startswith("estate_satisfaction:"):
        return f"{humanize_identifier(raw.split(':', 1)[1])} satisfaction"
    if raw.startswith("num_estate_privileges:"):
        return f"Number of privileges for {humanize_identifier(raw.split(':', 1)[1])}"
    if raw.startswith("societal_value:"):
        return f"{humanize_identifier(raw.split(':', 1)[1])} value"
    if raw.startswith("var:"):
        return f"{humanize_identifier(raw[4:])} variable"
    return humanize_identifier(raw)


def summarize_generic_scalar_condition(key: str, operator: str, value: str) -> str | None:
    normalized_operator = "=" if operator == "?=" else operator
    label = format_condition_label(key)
    display = format_scalar_value(value)

    if key.startswith("own_entire_area"):
        return f"Must own the entire area {display}"
    if key.startswith("own_entire_province"):
        if display.endswith(" Province"):
            display = display[:-9]
        return f"Must own the entire province {display}"
    if key == "has_presence_in":
        return f"Must have a presence in {display}"
    if key == "has_or_had_tag":
        return f"Country must have or have had tag {display}"
    if key == "has_advance":
        return f"Must have advance {display}"
    if key == "has_policy":
        return f"Must have policy {display}"
    if key == "has_reform":
        return f"Must have reform {display}"
    if key == "has_law":
        return f"Must have law {display}"
    if key == "has_embraced_institution":
        return f"Must have embraced institution {display}"
    if key == "has_religious_aspect":
        return f"Must have religious aspect {display}"
    if key == "has_disease":
        return f"Must have disease {display}"
    if key == "country_has_disease":
        return f"Country must have disease {display}"
    if key == "province_definition":
        return f"Province must be {display}"
    if key == "location_definition":
        return f"Location must be {display}"
    if key == "controller":
        return f"Controller must be {display}"
    if key == "subject_of":
        return f"Must be subject of {display}"
    if key == "subject_type":
        return f"Subject type must be {display}"
    if key == "disaster_type":
        return f"Disaster type must be {display}"
    if key == "has_accepted_culture":
        return f"Must have accepted culture {display}"
    if key == "has_variable":
        return f"Must have variable {display}"
    if key == "has_global_variable":
        return f"Global variable {display} must exist"
    if key == "has_building":
        return f"Must have building {display}"
    if key == "has_heir":
        return "Must have heir" if value == "yes" else "Must not have heir"
    if key == "has_regent":
        return "Must have a regent" if value == "yes" else "Must not have a regent"
    if key == "is_ai":
        return "Must be AI-controlled" if value == "yes" else "Must not be AI-controlled"
    if key == "is_adult":
        return "Must be adult" if value == "yes" else "Must not be adult"
    if key == "is_female":
        return "Must be female" if value == "yes" else "Must not be female"
    if key == "is_heir":
        return "Must be heir" if value == "yes" else "Must not be heir"
    if key == "is_ruler":
        return "Must be ruler" if value == "yes" else "Must not be ruler"
    if key == "is_subject_of":
        return f"Must be subject of {display}" if value not in {"yes", "no"} else None
    if key == "is_core_of":
        return f"Must be core of {display}" if value not in {"yes", "no"} else None
    if key == "is_discovered_by":
        return f"Must be discovered by {display}" if value not in {"yes", "no"} else None
    if key == "is_member_of_international_organization":
        return f"Must be member of international organization {display}" if value not in {"yes", "no"} else None
    if key == "is_leader_of_international_organization":
        return f"Must be leader of international organization {display}" if value not in {"yes", "no"} else None
    if key == "is_subject":
        return "Must be a subject" if value == "yes" else "Must be independent"
    if key == "is_great_power":
        return "Must be a great power" if value == "yes" else "Must not be a great power"
    if key == "is_situation_active":
        return f"Situation {display} must be active"
    if key == "is_at_war_with":
        return f"Must be at war with {display}"
    if key == "has_royal_marriage_with":
        return f"Must have royal marriage with {display}"
    if key == "country_rank":
        return describe_comparison("Country rank", normalized_operator, value)
    if key == "has_unlocked_any_unit_of_category":
        return f"Must have unlocked a unit in category {display}"
    if key == "discovered_route_to_india":
        return "Must have discovered a route to India" if value == "yes" else "Must not have discovered a route to India"
    if key.startswith("has_"):
        suffix = humanize_identifier(key[4:])
        if value == "yes":
            return f"Must have {suffix}"
        if value == "no":
            return f"Must not have {suffix}"
        return f"Must have {suffix} {display}"
    if key.startswith("is_"):
        suffix = humanize_identifier(key[3:])
        if value == "yes":
            return f"Must be {suffix}"
        if value == "no":
            return f"Must not be {suffix}"
        return f"Must be {suffix} {display}"

    if normalized_operator in {"=", ">=", "<=", ">", "<"} and label:
        return describe_comparison(label, normalized_operator, value)

    return None


def summarize_trigger_node(node: ClausewitzNode) -> str | None:
    if isinstance(node.value, list):
        if node.key.isdigit():
            child_bits = [summarize_trigger_node(child) for child in node.value]
            child_bits = [bit for bit in child_bits if bit]
            return join_phrases(child_bits) if child_bits else None

        if node.key == "limit":
            child_bits = [summarize_trigger_node(child) for child in node.value]
            child_bits = [bit for bit in child_bits if bit]
            return join_phrases(child_bits) if child_bits else None

        if node.key == "has_casus_belli_of_type_on":
            cb_type = child_scalar(node.value, "type")
            target = child_scalar(node.value, "target")
            cb_text = format_cb_ref(cb_type) or "valid"
            target_text = format_country_ref(target) if target else "the target"
            return f"Must have a {cb_text} casus belli on {target_text}"

        if node.key == "has_traits_of_type":
            trait_type = child_scalar(node.value, "type")
            if trait_type:
                return f"Must have a trait of type {format_scalar_value(trait_type)}"
            return "Must have the required trait type"

        if node.key == "opinion":
            target = child_scalar(node.value, "target")
            value_node = find_child(node.value, "value")
            if target and value_node and isinstance(value_node.value, str):
                return describe_comparison(
                    f"Opinion of {format_country_ref(target)}",
                    value_node.operator,
                    value_node.value,
                )
            return None

        if node.key == "work_of_art_exists":
            work = child_scalar(node.value, "work_of_art")
            if work:
                return f"{humanize_identifier(work)} must exist"
            return "A required work of art must exist"

        if node.key == "any_work_of_art_in_location":
            work = child_scalar(node.value, "this")
            if work:
                return f"Must contain {humanize_identifier(work)}"
            return "Must contain the required work of art"

        if node.key == "religious_view":
            target = child_scalar(node.value, "target")
            value = child_scalar(node.value, "value")
            if target and value:
                return f"View of {format_scalar_value(target)} must be {format_scalar_value(value)}"
            return None

        subject = format_scope_subject(node.key)
        if subject:
            child_bits = [summarize_trigger_node(child) for child in node.value]
            child_bits = [scopeify_condition(strip_subject_prefix(bit, subject)) for bit in child_bits if bit]
            if child_bits:
                if len(child_bits) > 1:
                    return None
                child_lower = child_bits[0].lower()
                if child_lower.startswith((
                    "dominant ",
                    "owner ",
                    "controller ",
                    "religion ",
                    "culture ",
                    "religion group ",
                    "culture group ",
                    "language ",
                    "province ",
                    "location ",
                    "government type ",
                    "disaster type ",
                    "subject type ",
                )):
                    return None
                return f"{subject} {join_phrases(child_bits)}"
            return None

        return None

    value = node.value
    if node.operator == "!=":
        positive = summarize_trigger_node(ClausewitzNode(key=node.key, operator="=", value=value))
        return negate_trigger_summary(positive) if positive else None
    if node.operator == "?=":
        node = ClausewitzNode(key=node.key, operator="=", value=value)

    if node.key == "country_exists":
        return f"{format_country_ref(value)} must exist"
    if node.key == "dynasty_exists":
        return f"The {format_dynasty_ref(value)} must exist"
    if node.key == "at_war":
        return "Must be at war" if value == "yes" else "Must not be at war"
    if node.key == "exists":
        return "Must exist" if value == "yes" else "Must not exist"
    if node.key == "is_alive":
        return "Must be alive" if value == "yes" else "Must not be alive"
    if node.key == "tag":
        return f"Country must be {format_country_ref(value)}"
    if node.key == "has_or_had_tag":
        return f"Country must currently be or have been {format_country_ref(value)}"
    if node.key == "religion":
        return f"Religion must be {format_scalar_value(value)}"
    if node.key == "culture":
        return f"Culture must be {format_scalar_value(value)}"
    if node.key == "ruler":
        return f"Ruler must be {format_scalar_value(value)}"
    if node.key == "government_type":
        return f"Government type must be {humanize_identifier(value)}"
    if node.key == "dynasty":
        return f"Dynasty must be {format_dynasty_ref(value)}"
    if node.key == "can_declare_war_on":
        return f"Must be able to declare war on {format_country_ref(value)}"
    if node.key == "owner":
        return f"Owner must be {format_scalar_value(value)}"
    if node.key == "has_truce_with":
        return f"Must have a truce with {format_scalar_value(value)}"
    if node.key == "is_rival_of":
        return f"Must be a rival of {format_scalar_value(value)}"
    if node.key == "is_enemy_of":
        return f"Must be an enemy of {format_scalar_value(value)}"
    if node.key == "has_ruler" and value == "yes":
        return "Must have a ruler"
    if node.key == "owns":
        return f"Must own {humanize_identifier(value)}"
    if node.key == "has_estate_privilege":
        return f"Must have estate privilege {humanize_identifier(value)}"
    if node.key == "has_dynasty" and value == "yes":
        return "Must have a dynasty"
    if node.key == "country_has_owner" and value == "yes":
        return "Country must have an owner"
    if node.key == "has_country_modifier":
        return f"Must have the {format_modifier_ref(value)} modifier"
    if node.key == "is_in_list":
        return f"Must be in {humanize_identifier(value)}"
    if node.key == "peaceful_and_rich" and value == "yes":
        return "Country must be peaceful and rich"
    if node.key == "region":
        return f"Must be in {humanize_identifier(value)}"
    if node.key == "is_produced_in_market":
        return f"Market must produce {humanize_identifier(value)}"

    comparison_labels = {
        "stability": "Stability",
        "prestige": "Prestige",
        "legitimacy": "Legitimacy",
        "num_of_owned_locations": "Owned locations",
        "total_development": "Total development",
        "total_abilities": "Total abilities",
        "amount": "Amount",
    }
    if node.key in comparison_labels:
        return describe_comparison(comparison_labels[node.key], node.operator, value)

    generic = summarize_generic_scalar_condition(node.key, node.operator, value)
    if generic:
        return generic

    return None


def negate_trigger_summary(text: str) -> str:
    if text.startswith("Must not "):
        return "Must " + text[9:]
    if text.startswith("Must "):
        return "Must not " + text[5:].lower()
    if " must exist" in text:
        return text.replace(" must exist", " must not exist")
    if " must be " in text:
        return text.replace(" must be ", " must not be ")
    return f"NOT ({text})"


def render_trigger_node(node: ClausewitzNode, indent: int = 0) -> list[str]:
    summary = summarize_trigger_node(node)
    if summary:
        return [format_bullet(summary, indent)]

    if not isinstance(node.value, list):
        return []

    if node.key == "AND":
        lines: list[str] = []
        for child in node.value:
            lines.extend(render_trigger_node(child, indent))
        return lines

    if node.key == "NOT":
        child_bits = [summarize_trigger_node(child) for child in node.value]
        child_bits = [bit for bit in child_bits if bit]
        if len(child_bits) == 1:
            return [format_bullet(negate_trigger_summary(child_bits[0]), indent)]
        lines = [format_bullet("None of these may be true:", indent)]
        for child in child_bits:
            lines.append(format_bullet(child, indent + 1))
        return lines

    if node.key in {"OR", "NOR"}:
        header = "At least one of these must be true:" if node.key == "OR" else "None of these may be true:"
        lines = [format_bullet(header, indent)]
        for child in node.value:
            child_lines = render_trigger_node(child, indent + 1)
            if child_lines:
                lines.extend(child_lines)
        return lines

    if node.key == "calc_true_if":
        amount = child_scalar(node.value, "amount") or "1"
        lines = [format_bullet(f"At least {amount} of these must be true:", indent)]
        for child in node.value:
            if child.key == "amount":
                continue
            child_lines = render_trigger_node(child, indent + 1)
            if child_lines:
                lines.extend(child_lines)
        return lines

    quantifier_label = format_quantifier_label(node.key)
    if quantifier_label:
        lines = [format_bullet(quantifier_label, indent)]
        for child in node.value:
            child_lines = render_trigger_node(child, indent + 1)
            if child_lines:
                lines.extend(child_lines)
        return lines

    subject = format_scope_subject(node.key)
    if subject:
        lines = [format_bullet(f"{subject} must satisfy:", indent)]
        for child in node.value:
            lines.extend(render_trigger_node(child, indent + 1))
        return lines

    lines: list[str] = []
    for child in node.value:
        lines.extend(render_trigger_node(child, indent))
    return lines


def interpret_trigger(trigger_text: str) -> str:
    """Interpret trigger conditions using a structured Clausewitz parser."""
    nodes = parse_clausewitz_block(trigger_text)
    lines: list[str] = []
    for node in nodes:
        lines.extend(render_trigger_node(node))
    return "\n".join(dedupe_text_lines(lines))


def describe_numeric_effect(stat_label: str, value: str) -> str:
    raw = str(value).strip()
    direction = infer_direction(raw)
    display = format_scalar_value(raw)
    stat = stat_label.lower()

    try:
        number = float(raw)
        if number > 0:
            return f"Increases {stat} by {display}"
        if number < 0:
            return f"Decreases {stat} by {format_scalar_value(str(abs(number)))}"
        return f"Affects {stat}"
    except ValueError:
        pass

    if direction > 0:
        return f"Increases {stat}"
    if direction < 0:
        return f"Decreases {stat}"
    return f"Affects {stat}"


def prefix_effect_subject(subject: str, line: str) -> str:
    clean = line.strip().rstrip(".")
    if not clean:
        return ""
    lowered = clean.lower()
    if lowered in {"kills current scope", "kills this character", "kills this figure"}:
        return f"Kills {subject}"
    if lowered in {"moves to current country", "moves to the country", "moves to our country"}:
        return f"{subject} joins the court"
    if subject.lower() == "the culture" and lowered.startswith(
        ("increases cultural tradition", "decreases cultural tradition", "increases cultural influence", "decreases cultural influence")
    ):
        return clean
    if clean.lower().startswith(subject.lower()):
        return clean
    return f"{subject} {clean[0].lower() + clean[1:]}"


def interpret_effect_nodes(
    nodes: list[ClausewitzNode],
    game_loc: dict[str, str],
    local_scripted_effects: dict[str, list[ClausewitzNode]] | None = None,
    scripted_effect_stack: tuple[str, ...] = (),
    saved_scope_hints: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    lines: list[str] = []
    scoped_scalar = lambda value: format_scalar_value(value, saved_scope_hints, game_loc)
    scoped_country = lambda value: format_country_ref(value, saved_scope_hints, game_loc)
    scoped_subject = lambda key: format_scope_subject(key, saved_scope_hints, game_loc)

    for node in nodes:
        if node.key in {
            "name",
            "ai_chance",
            "save_scope_as",
            "save_temporary_scope_as",
            "add_to_list",
            "ordered_in_list",
            "random_current_war",
            "random_list",
            "event_illustration_estate_effect",
            "trigger",
            "show_as_tooltip",
            "set_variable",
            "remove_variable",
            "else",
            "else_if",
            "limit",
        }:
            continue

        if isinstance(node.value, list):
            if node.key == "if":
                nested = interpret_effect_nodes(
                    [child for child in node.value if child.key != "limit"],
                    game_loc,
                    local_scripted_effects,
                    scripted_effect_stack,
                    saved_scope_hints,
                )
                if nested:
                    lines.extend(nested)
                continue

            scope_subject = scoped_subject(node.key)
            if scope_subject:
                nested = interpret_effect_nodes(
                    node.value,
                    game_loc,
                    local_scripted_effects,
                    scripted_effect_stack,
                    saved_scope_hints,
                )
                if nested:
                    lines.extend(prefix_effect_subject(scope_subject, line) for line in nested)
                continue

            if node.key == "add_country_modifier":
                modifier = child_scalar(node.value, "modifier")
                if modifier:
                    lines.append(f"Gains country modifier: {format_modifier_ref(modifier)}")
                continue

            if node.key == "remove_country_modifier":
                modifier = child_scalar(node.value, "modifier")
                if modifier:
                    lines.append(f"Loses country modifier: {format_modifier_ref(modifier)}")
                continue

            if node.key == "add_estate_satisfaction":
                estate = child_scalar(node.value, "type")
                value = child_scalar(node.value, "value")
                estate_text = humanize_identifier(estate) if estate else "an estate"
                if value:
                    lines.append(describe_numeric_effect(f"{estate_text} satisfaction", value))
                else:
                    lines.append(f"Changes {estate_text.lower()} satisfaction")
                continue

            if node.key == "add_gold_to_estate":
                estate = child_scalar(node.value, "estate_type") or child_scalar(node.value, "type")
                estate_text = humanize_identifier(estate) if estate else "an estate"
                lines.append(f"Transfers gold to {estate_text}")
                continue

            if node.key == "add_all_estate_satisfaction":
                value = child_scalar(node.value, "value") or child_scalar(node.value, "VALUE")
                if value:
                    lines.append(describe_numeric_effect("all estate satisfaction", value))
                else:
                    lines.append("Changes all estate satisfaction")
                continue

            if node.key == "annex_country":
                country = child_scalar(node.value, "country")
                if country:
                    lines.append(f"Annexes {scoped_scalar(country)}")
                else:
                    lines.append("Annexes a country")
                continue

            if node.key == "add_opinion":
                target = child_scalar(node.value, "target")
                modifier = child_scalar(node.value, "modifier")
                years = child_scalar(node.value, "years")
                target_text = scoped_country(target) if target else "the target"
                if modifier:
                    text = f"Gains opinion modifier {format_modifier_ref(modifier)} toward {target_text}"
                else:
                    text = f"Changes opinion toward {target_text}"
                if years:
                    text += f" for {scoped_scalar(years)} years"
                lines.append(text)
                continue

            if node.key == "add_spy_network":
                value = child_scalar(node.value, "value")
                if value:
                    lines.append(describe_numeric_effect("Spy network", value))
                else:
                    lines.append("Changes spy network")
                continue

            if node.key == "remove_opinion":
                target = child_scalar(node.value, "target")
                modifier = child_scalar(node.value, "modifier")
                target_text = scoped_country(target) if target else "the target"
                if modifier:
                    lines.append(f"Loses opinion modifier {format_modifier_ref(modifier)} toward {target_text}")
                else:
                    lines.append(f"Removes an opinion effect toward {target_text}")
                continue

            if node.key == "declare_war_with_cb":
                target = child_scalar(node.value, "target")
                cb_type = child_scalar(node.value, "type")
                target_text = scoped_country(target) if target else "the target"
                cb_text = format_cb_ref(cb_type) or "valid"
                lines.append(f"Declares war on {target_text} using the {cb_text} casus belli")
                continue

            if node.key in {"trigger_event", "trigger_event_silently", "trigger_event_non_silently", "country_event"}:
                event_id = child_scalar(node.value, "id") or child_scalar(node.value, "event")
                if event_id:
                    lines.append(f"Triggers follow-up event: {format_event_ref(event_id, game_loc)}")
                continue

            if node.key == "change_societal_value":
                axis = child_scalar(node.value, "type")
                value = child_scalar(node.value, "value")
                axis_text = humanize_identifier(axis) if axis else "a societal value"
                normalized_value = str(value or "").lower()
                if normalized_value.endswith("move_to_left"):
                    lines.append(f"Shifts {axis_text} toward the left")
                elif normalized_value.endswith("move_to_right"):
                    lines.append(f"Shifts {axis_text} toward the right")
                elif value:
                    lines.append(f"Changes societal value {axis_text}: {humanize_identifier(value)}")
                else:
                    lines.append(f"Changes societal value {axis_text}")
                continue

            if node.key == "add_casus_belli":
                target = child_scalar(node.value, "target")
                cb_type = child_scalar(node.value, "type")
                province = child_scalar(node.value, "province")
                target_text = scoped_scalar(target) if target else "the target"
                cb_text = format_cb_ref(cb_type) if cb_type else "valid"
                text = f"Gains the {cb_text} casus belli against {target_text}"
                if province:
                    text += f" for {scoped_scalar(province)}"
                lines.append(text)
                continue

            if node.key == "add_gold":
                value = child_scalar(node.value, "value")
                multiply = child_scalar(node.value, "multiply")
                if value and not multiply:
                    lines.append(describe_numeric_effect("Treasury", value))
                elif value and multiply:
                    lines.append(f"Changes treasury using {scoped_scalar(value)} scaled by {scoped_scalar(multiply)}")
                else:
                    lines.append("Changes treasury")
                continue

            if node.key == "add_migration":
                owner = child_scalar(node.value, "owner")
                src = child_scalar(node.value, "from")
                dst = child_scalar(node.value, "to")
                amount = child_scalar(node.value, "amount")
                months = child_scalar(node.value, "months")
                culture = child_scalar(node.value, "culture")
                text = "Starts migration"
                if amount:
                    text += f" of {scoped_scalar(amount)}"
                if culture:
                    text += f" {humanize_identifier(culture)}"
                if src:
                    text += f" from {scoped_scalar(src)}"
                if dst:
                    text += f" to {scoped_scalar(dst)}"
                if owner:
                    text += f" under {scoped_scalar(owner)}"
                if months:
                    text += f" over {scoped_scalar(months)} months"
                lines.append(text)
                continue

            if node.key == "add_character_modifier":
                modifier = child_scalar(node.value, "modifier")
                if modifier:
                    lines.append(f"Gains character modifier: {format_modifier_ref(modifier)}")
                else:
                    lines.append("Gains a character modifier")
                continue

            if node.key == "add_location_modifier":
                modifier = child_scalar(node.value, "modifier")
                if modifier:
                    lines.append(f"Gains location modifier: {format_modifier_ref(modifier)}")
                else:
                    lines.append("Gains a location modifier")
                continue

            if node.key == "construct_building":
                building = child_scalar(node.value, "building_type") or child_scalar(node.value, "type")
                if building:
                    lines.append(f"Constructs {format_building_ref(building)}")
                else:
                    lines.append("Constructs a building")
                continue

            if node.key == "create_art":
                lines.append("Creates a work of art")
                continue

            if node.key == "create_character":
                lines.append("Creates a new character")
                continue

            if node.key == "kill_character":
                target = child_scalar(node.value, "target")
                if target:
                    lines.append(f"Kills {scoped_scalar(target)}")
                else:
                    lines.append("Kills a character")
                continue

            if node.key in {"grant_estate_privilege", "add_policy", "add_reform"}:
                value = child_scalar(node.value, "type") or child_scalar(node.value, "privilege") or child_scalar(node.value, "reform")
                if not value:
                    scalar_child = next((child.value for child in node.value if isinstance(child.value, str)), "")
                    value = scalar_child
                label = {
                    "grant_estate_privilege": "Grants estate privilege",
                    "add_policy": "Adopts policy",
                    "add_reform": "Enacts reform",
                }[node.key]
                if value:
                    lines.append(f"{label}: {humanize_identifier(value)}")
                else:
                    lines.append(label)
                continue

            if node.key == "change_religion_for_ruler_and_family":
                religion = child_scalar(node.value, "religion")
                country = child_scalar(node.value, "country")
                religion_text = humanize_identifier(religion) if religion else "a new religion"
                if country:
                    lines.append(f"Converts the ruler and family of {scoped_scalar(country)} to {religion_text}")
                else:
                    lines.append(f"Converts the ruler and family to {religion_text}")
                continue

            if node.key == "join_war_as_attacker":
                text = "Joins the war as an attacker"
                if child_scalar(node.value, "call_in_subjects") == "yes":
                    text += " and calls in subjects"
                lines.append(text)
                continue

            if node.key == "every_in_list":
                join_node = find_child(node.value, "join_war_as_attacker")
                if join_node and isinstance(join_node.value, list):
                    text = "Countries in the prepared list join the war as attackers"
                    if child_scalar(join_node.value, "call_in_subjects") == "yes":
                        text += " and call in their subjects"
                    lines.append(text)
                    continue
                nested = interpret_effect_nodes(
                    node.value,
                    game_loc,
                    local_scripted_effects,
                    scripted_effect_stack,
                    saved_scope_hints,
                )
                if nested:
                    lines.extend(nested)
                continue

            if node.key in {"custom_tooltip", "hidden_effect"}:
                nested_nodes = [child for child in node.value if child.key != "text"]
                nested = interpret_effect_nodes(
                    nested_nodes,
                    game_loc,
                    local_scripted_effects,
                    scripted_effect_stack,
                    saved_scope_hints,
                )
                if nested:
                    lines.extend(nested)
                    continue
                tooltip_key = child_scalar(node.value, "text")
                tooltip_text = resolve_loc_text(tooltip_key, game_loc)
                if tooltip_text and "$" not in tooltip_text:
                    lines.append(tooltip_text)
                continue

            if node.key.endswith("_effect"):
                builtin_summary = summarize_builtin_scripted_effect(node.key, node.value)
                if builtin_summary:
                    lines.extend(builtin_summary)
                    continue

                if node.key not in scripted_effect_stack and len(scripted_effect_stack) < 4:
                    expanded = expand_scripted_effect_nodes(node.key, node.value, local_scripted_effects)
                    if expanded:
                        nested = interpret_effect_nodes(
                            expanded,
                            game_loc,
                            local_scripted_effects,
                            scripted_effect_stack + (node.key,),
                            saved_scope_hints,
                        )
                        if nested:
                            lines.extend(nested)
                            continue

                lines.append(f"Triggers scripted effect: {display_scripted_effect_name(node.key)}")
                continue

            nested = interpret_effect_nodes(
                node.value,
                game_loc,
                local_scripted_effects,
                scripted_effect_stack,
                saved_scope_hints,
            )
            lines.extend(nested)
            continue

        if node.key == "add_prestige":
            lines.append(describe_numeric_effect("Prestige", node.value))
            continue
        if node.key == "add_stability":
            lines.append(describe_numeric_effect("Stability", node.value))
            continue
        if node.key in {"add_treasury", "add_gold", "add_money"}:
            lines.append(describe_numeric_effect("Treasury", node.value))
            continue
        if node.key == "add_government_power":
            lines.append(describe_numeric_effect("Government power", node.value))
            continue
        if node.key == "add_manpower":
            lines.append(describe_numeric_effect("Manpower", node.value))
            continue
        if node.key == "add_legitimacy":
            lines.append(describe_numeric_effect("Legitimacy", node.value))
            continue
        if node.key == "add_war_exhaustion":
            lines.append(describe_numeric_effect("War exhaustion", node.value))
            continue
        if node.key == "add_inflation":
            lines.append(describe_numeric_effect("Inflation", node.value))
            continue
        if node.key == "add_army_tradition":
            lines.append(describe_numeric_effect("Army tradition", node.value))
            continue
        if node.key == "add_navy_tradition":
            lines.append(describe_numeric_effect("Navy tradition", node.value))
            continue
        if node.key == "add_research_progress":
            lines.append(describe_numeric_effect("Research progress", node.value))
            continue
        if node.key == "add_religious_influence":
            lines.append(describe_numeric_effect("Religious influence", node.value))
            continue
        if node.key == "add_republican_tradition":
            lines.append(describe_numeric_effect("Republican tradition", node.value))
            continue
        if node.key == "add_liberty_desire":
            lines.append(describe_numeric_effect("Liberty desire", node.value))
            continue
        if node.key == "add_yearly_gold":
            lines.append(describe_numeric_effect("Yearly gold income", node.value))
            continue
        if node.key == "add_doom":
            lines.append(describe_numeric_effect("Doom", node.value))
            continue
        if node.key == "add_religious_influence_if_valid":
            lines.append(describe_numeric_effect("Religious influence", node.value))
            continue
        if node.key == "add_cultural_influence":
            lines.append(describe_numeric_effect("Cultural influence", node.value))
            continue
        if node.key == "add_cultural_tradition":
            lines.append(describe_numeric_effect("Cultural tradition", node.value))
            continue
        if node.key in {"add_adm_power", "add_dip_power", "add_mil_power"}:
            lines.append(describe_numeric_effect(humanize_identifier(node.key[4:]), node.value))
            continue
        if node.key == "add_adm":
            lines.append(describe_numeric_effect("Administrative skill", node.value))
            continue
        if node.key == "add_dip":
            lines.append(describe_numeric_effect("Diplomatic skill", node.value))
            continue
        if node.key == "add_mil":
            lines.append(describe_numeric_effect("Military skill", node.value))
            continue
        if node.key == "set_capital":
            lines.append(f"Moves the capital to {scoped_scalar(node.value)}")
            continue
        if node.key == "set_new_ruler":
            lines.append(f"Installs {scoped_scalar(node.value)} as ruler")
            continue
        if node.key == "move_country":
            lines.append(f"Moves to {scoped_scalar(node.value)}")
            continue
        if node.key in {"trigger_event", "trigger_event_silently", "trigger_event_non_silently", "country_event"}:
            lines.append(f"Triggers follow-up event: {format_event_ref(node.value, game_loc)}")
            continue
        if node.key == "banish_character":
            destination = scoped_scalar(node.value) if str(node.value).strip() else ""
            lines.append(f"Is banished to {destination}" if destination else "Is banished")
            continue
        if node.key in {"kill_character_silently", "destroy_rebel"}:
            lines.append("Is removed")
            continue
        if node.key == "change_religion":
            lines.append(f"Changes religion to {humanize_identifier(node.value)}")
            continue
        if node.key == "change_country_name":
            lines.append("Changes the country name")
            continue
        if node.key == "change_player":
            lines.append("Transfers player control")
            continue
        if node.key == "cancel_subject":
            lines.append(f"Ends subject ties with {scoped_scalar(node.value)}")
            continue
        if node.key == "annex_country":
            lines.append(f"Annexes {scoped_scalar(node.value)}")
            continue
        if node.key == "nudge_towards_openness":
            lines.append("Shifts outward vs inward toward openness")
            continue
        if node.key == "change_development":
            lines.append(describe_numeric_effect("Development", node.value))
            continue
        if node.key == "change_prosperity":
            lines.append(describe_numeric_effect("Prosperity", node.value))
            continue
        if node.key == "add_policy":
            lines.append(f"Adopts policy: {humanize_identifier(node.value)}")
            continue
        if node.key == "add_reform":
            lines.append(f"Enacts reform: {humanize_identifier(node.value)}")
            continue
        if node.key == "grant_estate_privilege":
            lines.append(f"Grants estate privilege: {humanize_identifier(node.value)}")
            continue
        if node.key == "add_trait":
            lines.append(f"Gains trait: {format_trait_ref(node.value)}")
            continue
        if node.key == "add_random_trait_from_category":
            lines.append(f"Gains a random trait from category {humanize_identifier(node.value)}")
            continue
        if node.key == "add_tribal_cohesion":
            lines.append(describe_numeric_effect("Tribal cohesion", node.value))
            continue
        if node.key == "nudge_towards_isolationism":
            lines.append("Shifts outward vs inward toward isolationism")
            continue
        if node.key.endswith("_effect"):
            builtin_summary = summarize_builtin_scripted_effect(node.key, node.value)
            if builtin_summary:
                lines.extend(builtin_summary)
                continue
            if node.key not in scripted_effect_stack and len(scripted_effect_stack) < 4:
                expanded = expand_scripted_effect_nodes(node.key, node.value, local_scripted_effects)
                if expanded:
                    nested = interpret_effect_nodes(
                        expanded,
                        game_loc,
                        local_scripted_effects,
                        scripted_effect_stack + (node.key,),
                        saved_scope_hints,
                    )
                    if nested:
                        lines.extend(nested)
                        continue
            lines.append(f"Triggers scripted effect: {display_scripted_effect_name(node.key)}")
            continue

    return dedupe_text_lines(lines)


def split_outcome_effect_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    """Separate direct readable effects from raw scripted-effect calls."""
    direct_lines: list[str] = []
    scripted_effects: list[str] = []

    for line in lines:
        match = re.match(r"^Triggers scripted effect: (.+?)\.?$", line.strip())
        if match:
            scripted_effects.append(match.group(1).strip())
        else:
            direct_lines.append(line)

    return direct_lines, scripted_effects


def build_option_label(option: dict[str, object], game_loc: dict[str, str], index: int, lang: str) -> str:
    historical_option = bool(option.get("historical_option"))
    fallback_index = 0 if historical_option else index + 1
    fallback = gti18n.localized_option_fallback(fallback_index, lang)

    option_name_key = str(option.get("name", "")).strip()
    raw_template = resolve_loc_template_text(option_name_key, game_loc)
    resolved = sanitize_generated_title(resolve_loc_text(option_name_key, game_loc))

    if not resolved or "$" in resolved or len(resolved) < 3:
        return fallback
    if "(...)" in resolved or "[" in resolved:
        return fallback
    if ".custom(" in raw_template.lower():
        return fallback
    if resolved.lower() in {"historical option", "alternative option"}:
        return fallback
    if title_needs_fallback_hint(resolved) or title_has_generic_adjective_artifact(resolved, raw_template):
        return fallback
    return gti18n.localize_generated_text(resolved, lang)


def localize_generated_line(line: str, lang: str) -> str:
    if lang != "spanish" or not line:
        return line

    prefix_match = re.match(r"^(\s*(?:-\s*)?)(.*)$", line)
    prefix = prefix_match.group(1) if prefix_match else ""
    content = prefix_match.group(2) if prefix_match else line

    exact_map = {
        "Interpreted requirements:": "Requisitos interpretados:",
        "Historical choice": "Opción histórica",
        "No options available.": "No hay opciones disponibles.",
        "Applies complex scripted effects.": "Aplica efectos de script complejos.",
        "This event uses dynamic vanilla text that cannot be previewed cleanly before it fires.": "Este evento usa texto dinamico de vanilla que no puede previsualizarse limpiamente antes de activarse.",
        "Some dynamic requirements cannot be previewed cleanly outside the live event scope.": "Algunos requisitos dinamicos no pueden previsualizarse limpiamente fuera del scope vivo del evento.",
        "Some dynamic outcomes cannot be previewed cleanly before the event fires.": "Algunos resultados dinamicos no pueden previsualizarse limpiamente antes de que el evento se active.",
        "Must be at war.": "Debe estar en guerra.",
        "Must not be at war.": "No debe estar en guerra.",
        "Must exist.": "Debe existir.",
        "Must not exist.": "No debe existir.",
        "Must be alive.": "Debe estar vivo.",
        "Must not be alive.": "No debe estar vivo.",
        "Must have a ruler.": "Debe tener un gobernante.",
        "Must have a dynasty.": "Debe tener una dinastía.",
        "Country must have an owner.": "El país debe tener un propietario.",
        "Country must be peaceful and rich.": "El país debe ser pacífico y próspero.",
        "Creates a work of art.": "Crea una obra de arte.",
        "Creates a new character.": "Crea un personaje nuevo.",
        "Changes the country name.": "Cambia el nombre del país.",
        "Transfers player control.": "Transfiere el control del jugador.",
        "Is removed.": "Es eliminado.",
        "Is banished.": "Es desterrado.",
        "Joins the war as an attacker.": "Se une a la guerra como atacante.",
        "Joins the war as an attacker and calls in subjects.": "Se une a la guerra como atacante y llama a sus súbditos.",
        "Shifts outward vs inward toward openness.": "Desplaza apertura vs. repliegue hacia la apertura.",
        "Shifts outward vs inward toward isolationism.": "Desplaza apertura vs. repliegue hacia el aislacionismo.",
    }
    if content in exact_map:
        return prefix + exact_map[content]

    regex_rules: list[tuple[str, str]] = [
        (r"^Historical window: (.+?) \| monthly chance: (.+)$", r"Ventana histórica: \1 | probabilidad mensual: \2"),
        (r"^Choice: (.+)$", r"Opción: \1"),
        (r"^Alternative option (\d+)$", r"Opción alternativa \1"),
        (r"^Complex trigger conditions \(see game files for details\)\.$", r"Condiciones de activación complejas (consulta los archivos del juego para más detalles)."),
        (r"^At least one of these must be true:$", r"Al menos una de estas condiciones debe cumplirse:"),
        (r"^None of these may be true:$", r"Ninguna de estas condiciones puede cumplirse:"),
        (r"^At least (\d+) of these must be true:$", r"Al menos \1 de estas condiciones deben cumplirse:"),
        (r"^At least one rival must satisfy:$", r"Al menos un rival debe cumplir:"),
        (r"^At least one subject must satisfy:$", r"Al menos un súbdito debe cumplir:"),
        (r"^At least one character must satisfy:$", r"Al menos un personaje debe cumplir:"),
        (r"^At least one artist must satisfy:$", r"Al menos un artista debe cumplir:"),
        (r"^At least one cabinet character must satisfy:$", r"Al menos un miembro del gabinete debe cumplir:"),
        (r"^At least one pop must satisfy:$", r"Al menos un grupo de población debe cumplir:"),
        (r"^At least one rebel must satisfy:$", r"Al menos un rebelde debe cumplir:"),
        (r"^At least one country sub-unit must satisfy:$", r"Al menos una subunidad del país debe cumplir:"),
        (r"^At least one owned rural location must satisfy:$", r"Al menos una localización rural poseída debe cumplir:"),
        (r"^A rival must satisfy:$", r"Un rival debe cumplir:"),
        (r"^At least one owned location must satisfy:$", r"Al menos una localización poseída debe cumplir:"),
        (r"^Every owned location must satisfy:$", r"Cada localización poseída debe cumplir:"),
        (r"^Current country (.+)$", r"El país actual \1"),
        (r"^The ruler or regent (.+)$", r"El gobernante o regente \1"),
        (r"^The ruler (.+)$", r"El gobernante \1"),
        (r"^The ruler's (.+)$", r"El gobernante \1"),
        (r"^The capital (.+)$", r"La capital \1"),
        (r"^Country must be (.+)$", r"El país debe ser \1"),
        (r"^Religion must be (.+)$", r"La religión debe ser \1"),
        (r"^Religion group must be (.+)$", r"El grupo religioso debe ser \1"),
        (r"^Culture must be (.+)$", r"La cultura debe ser \1"),
        (r"^Government type must be (.+)$", r"El tipo de gobierno debe ser \1"),
        (r"^Dynasty must be (.+)$", r"La dinastía debe ser \1"),
        (r"^Owner must be (.+)$", r"El propietario debe ser \1"),
        (r"^Situation (.+) must be active$", r"La situación \1 debe estar activa"),
        (r"^Market must produce (.+)$", r"El mercado debe producir \1"),
        (r"^Must have a truce with (.+)$", r"Debe tener una tregua con \1"),
        (r"^Must be able to declare war on (.+)$", r"Debe poder declarar la guerra a \1"),
        (r"^Must be a rival of (.+)$", r"Debe ser rival de \1"),
        (r"^Must be an enemy of (.+)$", r"Debe ser enemigo de \1"),
        (r"^Must own (.+)$", r"Debe poseer \1"),
        (r"^Must contain (.+)$", r"Debe contener \1"),
        (r"^Must have (.+)$", r"Debe tener \1"),
        (r"^Must not have (.+)$", r"No debe tener \1"),
        (r"^Must not be (.+)$", r"No debe ser \1"),
        (r"^Must be (.+)$", r"Debe ser \1"),
        (r"^(.+) must exist$", r"\1 debe existir"),
        (r"^(.+) must be at least (.+)$", r"\1 debe ser al menos \2"),
        (r"^(.+) must be at most (.+)$", r"\1 debe ser como máximo \2"),
        (r"^(.+) must be greater than (.+)$", r"\1 debe ser mayor que \2"),
        (r"^(.+) must be less than (.+)$", r"\1 debe ser menor que \2"),
        (r"^(.+) must be (.+)$", r"\1 debe ser \2"),
        (r"^Increases (.+) by (.+)\.$", r"Aumenta \1 en \2."),
        (r"^Decreases (.+) by (.+)\.$", r"Reduce \1 en \2."),
        (r"^Increases (.+)\.$", r"Aumenta \1."),
        (r"^Decreases (.+)\.$", r"Reduce \1."),
        (r"^Affects (.+)\.$", r"Afecta a \1."),
        (r"^Gains country modifier: (.+)\.$", r"Obtiene el modificador de país: \1."),
        (r"^Loses country modifier: (.+)\.$", r"Pierde el modificador de país: \1."),
        (r"^Gains character modifier: (.+)\.$", r"Obtiene el modificador de personaje: \1."),
        (r"^Gains location modifier: (.+)\.$", r"Obtiene el modificador de localización: \1."),
        (r"^Gains trait: (.+)\.$", r"Obtiene el rasgo: \1."),
        (r"^Gains a random trait from category (.+)\.$", r"Obtiene un rasgo aleatorio de la categoría \1."),
        (r"^Gains opinion modifier (.+) toward (.+) for (.+) years\.$", r"Obtiene el modificador de opinión \1 hacia \2 durante \3 años."),
        (r"^Gains opinion modifier (.+) toward (.+)\.$", r"Obtiene el modificador de opinión \1 hacia \2."),
        (r"^Changes opinion toward (.+)\.$", r"Cambia la opinión hacia \1."),
        (r"^Loses opinion modifier (.+) toward (.+)\.$", r"Pierde el modificador de opinión \1 hacia \2."),
        (r"^Removes an opinion effect toward (.+)\.$", r"Elimina un efecto de opinión hacia \1."),
        (r"^Declares war on (.+) using the (.+) casus belli\.$", r"Declara la guerra a \1 usando el casus belli \2."),
        (r"^Triggers follow-up event: (.+)\.$", r"Activa el evento posterior: \1."),
        (r"^Changes societal value (.+): (.+)\.$", r"Cambia el valor social \1: \2."),
        (r"^Changes societal value (.+)\.$", r"Cambia el valor social \1."),
        (r"^Shifts (.+) toward the left\.$", r"Desplaza \1 hacia la izquierda."),
        (r"^Shifts (.+) toward the right\.$", r"Desplaza \1 hacia la derecha."),
        (r"^Gains the (.+) casus belli against (.+) for (.+)\.$", r"Obtiene el casus belli \1 contra \2 para \3."),
        (r"^Gains the (.+) casus belli against (.+)\.$", r"Obtiene el casus belli \1 contra \2."),
        (r"^Changes treasury using (.+) scaled by (.+)\.$", r"Cambia el tesoro usando \1 escalado por \2."),
        (r"^Changes treasury\.$", r"Cambia el tesoro."),
        (r"^Constructs (.+)\.$", r"Construye \1."),
        (r"^Kills (.+)\.$", r"Mata a \1."),
        (r"^Annexes (.+)\.$", r"Anexiona \1."),
        (r"^Moves the capital to (.+)\.$", r"Traslada la capital a \1."),
        (r"^Installs (.+) as ruler\.$", r"Instala a \1 como gobernante."),
        (r"^Moves to (.+)\.$", r"Se traslada a \1."),
        (r"^Adopts policy: (.+)\.$", r"Adopta la política: \1."),
        (r"^Enacts reform: (.+)\.$", r"Promulga la reforma: \1."),
        (r"^Grants estate privilege: (.+)\.$", r"Otorga el privilegio estamental: \1."),
        (r"^Changes religion to (.+)\.$", r"Cambia la religión a \1."),
        (r"^Ends subject ties with (.+)\.$", r"Rompe los lazos de vasallaje con \1."),
        (r"^Triggers scripted effect: (.+)\.$", r"Activa el efecto scriptado: \1."),
        (r"^Converts the ruler and family of (.+) to (.+)\.$", r"Convierte al gobernante y a la familia de \1 a \2."),
        (r"^Converts the ruler and family to (.+)\.$", r"Convierte al gobernante y a su familia a \1."),
        (r"^Is banished to (.+)\.$", r"Es desterrado a \1."),
        (r"^Starts migration of (.+) (.+) from (.+) to (.+) under (.+) over (.+) months\.$", r"Inicia una migración de \1 \2 desde \3 hacia \4 bajo \5 durante \6 meses."),
        (r"^Starts migration of (.+) from (.+) to (.+) over (.+) months\.$", r"Inicia una migración de \1 desde \2 hacia \3 durante \4 meses."),
        (r"^Starts migration of (.+) from (.+) to (.+)\.$", r"Inicia una migración de \1 desde \2 hacia \3."),
        (r"^Starts migration\.$", r"Inicia una migración."),
    ]

    for pattern, replacement in regex_rules:
        translated = re.sub(pattern, replacement, content)
        if translated != content:
            content = translated
            break

    phrase_map = {
        "current country": "país actual",
        "the target": "el objetivo",
        "the ruler": "el gobernante",
        "the province": "la provincia",
        "the market": "el mercado",
        "the owner": "el propietario",
        "the artist": "el artista",
        "the previous scope": "el ámbito anterior",
        "all estate satisfaction": "la satisfacción de todos los estamentos",
        "clergy estate satisfaction": "la satisfacción del estamento del clero",
        "nobility estate satisfaction": "la satisfacción del estamento de la nobleza",
        "burghers estate satisfaction": "la satisfacción del estamento de los burgueses",
        "religious influence": "la influencia religiosa",
        "army tradition": "la tradición del ejército",
        "navy tradition": "la tradición naval",
        "war exhaustion": "el agotamiento bélico",
        "government power": "el poder gubernamental",
        "research progress": "el progreso de investigación",
        "republican tradition": "la tradición republicana",
        "liberty desire": "el deseo de libertad",
        "yearly gold income": "los ingresos anuales de oro",
        "tribal cohesion": "la cohesión tribal",
        "manpower": "la reserva de mano de obra",
        "treasury": "el tesoro",
        "stability": "la estabilidad",
        "prestige": "el prestigio",
        "legitimacy": "la legitimidad",
        "inflation": "la inflación",
        "development": "el desarrollo",
        "prosperity": "la prosperidad",
    }
    for old, new in phrase_map.items():
        content = re.sub(rf"\b{re.escape(old)}\b", new, content, flags=re.IGNORECASE)

    return prefix + content


def localize_generated_text(text: str, lang: str) -> str:
    if lang != "spanish":
        return text
    return "\n".join(localize_generated_line(line, lang) for line in text.split("\n"))


def format_monthly_chance(value: object) -> str:
    """Render monthly chance as a percentage when it is a plain numeric value."""
    text = str(value or "").strip()
    if not text:
        return "0%"
    if text.endswith("%"):
        return text
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return f"{text}%"
    return text


def format_display_date(value: object) -> str:
    """Shorten exact year-start dates while preserving specific month/day windows."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}\.1\.1", text):
        return text.split(".", 1)[0]
    if re.fullmatch(r"\d{4}\.12\.(?:30|31)", text):
        return text.split(".", 1)[0]
    return text


def generate_event_window_summary(event: dict, lang: str) -> str:
    """Generate the readable historical window and monthly chance summary."""
    date_from = format_display_date(event["date_from"])
    date_to = format_display_date(event["date_to"])
    monthly_chance = format_monthly_chance(event["monthly_chance"])
    if lang == "spanish":
        return f"{date_from} - {date_to} | {monthly_chance} de probabilidad mensual"
    return f"{date_from} - {date_to} | {monthly_chance} Monthly Chance"


def generate_event_meta(event: dict, lang: str) -> str:
    """Generate the source line shown beneath the event description."""
    source_mod = event.get("source_mod", "")
    if lang == "spanish":
        parts = [f"Origen: {event['id']}", f"Archivo: {event['source_file']}"]
        if source_mod and source_mod != "Base Game":
            parts.append(f"Mod: {source_mod}")
        return " | ".join(parts)
    parts = [f"Source: {event['id']}", f"File: {event['source_file']}"]
    if source_mod and source_mod != "Base Game":
        parts.append(f"Mod: {source_mod}")
    return " | ".join(parts)


def generate_event_requirements(event: dict, lang: str) -> str:
    """Generate structured requirements text from event metadata."""
    parts = [generate_event_window_summary(event, lang)]
    if event.get("trigger_raw"):
        parts.append("")
        parts.append("Interpreted requirements:")
        interpreted = interpret_trigger(event["trigger_raw"])
        if interpreted:
            parts.append(interpreted)
        else:
            parts.append("- Complex trigger conditions (see game files for details).")
    localized = gti18n.localize_generated_text("\n".join(parts), lang)
    sanitized = sanitize_preview_block(localized.split("\n"), preview_requirements_fallback(lang))
    return "\n".join(sanitized)


def generate_event_outcomes(event: dict, game_loc: dict[str, str], lang: str) -> str:
    """Generate structured outcomes text from option labels and option effects."""
    option_blocks = event.get("option_blocks") or []
    if not option_blocks and not event.get("option_names"):
        return gti18n.localize_generated_text("- No options available.", lang)

    if not option_blocks:
        option_blocks = [{"name": name, "historical_option": False, "body_raw": ""} for name in event.get("option_names", [])]

    parts: list[str] = []
    saved_scope_hints = _get_saved_scope_title_hints(event)
    for index, option in enumerate(option_blocks):
        label = build_option_label(option, game_loc, index, lang)
        if parts:
            parts.append("")
        parts.append(f"- Choice: {label}")

        effect_lines = interpret_effect_nodes(
            parse_clausewitz_block(option.get("body_raw", "")),
            game_loc,
            event.get("local_scripted_effects"),
            saved_scope_hints=saved_scope_hints,
        )
        direct_lines, scripted_effects = split_outcome_effect_lines(effect_lines)

        if direct_lines:
            for line in direct_lines:
                parts.append(f"  - {capitalize_sentence_start(ensure_sentence(line))}")

        if scripted_effects:
            joined = "; ".join(
                dict.fromkeys(effect.strip() for effect in scripted_effects if effect.strip())
            )
            if joined:
                parts.append(f"  - Additional scripted changes: {joined}.")

        if not direct_lines and not scripted_effects and option.get("body_raw", "").strip():
            parts.append("  - Applies complex scripted effects.")

    localized = gti18n.localize_generated_text("\n".join(parts) if parts else "- No options available.", lang)
    localized = replace_generic_scope_phrases(localized, saved_scope_hints, game_loc)
    sanitized = sanitize_preview_block(localized.split("\n"), preview_outcomes_fallback(lang))
    return capitalize_outcome_bullets("\n".join(sanitized))


# ---------------------------------------------------------------------------
# Registry building
# ---------------------------------------------------------------------------

def build_entry_viewer_metadata(event: dict[str, object]) -> str:
    """Return the runtime viewer trigger name when the trigger is safe for GUI evaluation."""
    trigger_raw = str(event.get("trigger_raw", "")).strip()
    if not trigger_raw:
        return viewer_trigger_name(event)

    expanded_nodes = sanitize_runtime_viewer_nodes(
        expand_local_trigger_nodes(
            parse_clausewitz_block(trigger_raw),
            event.get("local_scripted_triggers") or {},
        )
    )
    return viewer_trigger_name(event) if is_runtime_viewer_safe(expanded_nodes) else ""


def build_runtime_preview_nodes(
    event: dict[str, object],
    raw_block: str,
    *,
    bootstrap_nodes: list[ClausewitzNode] | None = None,
) -> list[ClausewitzNode]:
    """Return preview wrapper nodes for one effect block, including safe saved-scope bootstrap."""
    local_scripted_effects = event.get("local_scripted_effects") or {}
    expanded_nodes = expand_local_scripted_effects(
        parse_clausewitz_block(str(raw_block).strip()),
        local_scripted_effects,
    )
    effect_nodes = sanitize_runtime_preview_nodes(filter_option_effect_nodes(expanded_nodes))
    if not effect_nodes:
        return []

    if bootstrap_nodes:
        return [*bootstrap_nodes, *effect_nodes]
    return effect_nodes


def build_entry_effect_metadata(event: dict[str, object], slug: str) -> tuple[str, list[dict[str, str]]]:
    """Return runtime scripted-effect references used by the UI for one event."""
    local_scripted_effects = event.get("local_scripted_effects") or {}
    expanded_immediate_nodes = expand_local_scripted_effects(
        parse_clausewitz_block(str(event.get("immediate_raw", "")).strip()),
        local_scripted_effects,
    )
    bootstrap_nodes = sanitize_runtime_preview_nodes(
        extract_runtime_preview_bootstrap_nodes(expanded_immediate_nodes)
    )
    allowed_saved_scopes = collect_saved_scope_names(bootstrap_nodes)
    immediate_nodes = build_preview_wrapper_nodes(
        event,
        str(event.get("immediate_raw", "")).strip(),
        bootstrap_nodes=bootstrap_nodes,
        allowed_saved_scopes=allowed_saved_scopes,
    )
    immediate_effect = immediate_effect_name(event) if immediate_nodes else ""

    option_effects: list[dict[str, str]] = []
    for index, option in enumerate(event.get("option_blocks") or []):
        effect_nodes = build_preview_wrapper_nodes(
            event,
            str(option.get("body_raw", "")).strip(),
            bootstrap_nodes=bootstrap_nodes,
            allowed_saved_scopes=allowed_saved_scopes,
        )
        if not effect_nodes:
            continue
        option_effects.append(
            {
                "title_loc": option_title_loc_key(slug, index),
                "effect": option_effect_name(event, index),
            }
        )

    return immediate_effect, option_effects


def build_registry(
    all_events: list[dict],
    existing_registry: dict | None = None,
    *,
    game_root: Path | None = None,
) -> dict:
    """Build the complete registry JSON structure."""
    # Group events by tag
    tag_events: dict[str, list[dict]] = defaultdict(list)
    for evt in all_events:
        for tag in evt["tags"]:
            tag_events[tag].append(evt)

    # Mirror vanilla DHE behavior: a newly formed country only keeps events
    # that are explicitly tagged for its destination tag. Do not synthesize
    # successor bundles for formables like ITA/GER/HRE that have no native DHE.

    # Also include existing non-DHE entries from previous registry
    existing_non_dhe: dict[str, list[dict]] = defaultdict(list)
    if existing_registry:
        for group in existing_registry.get("groups", []):
            for tag in group.get("country_tags", []):
                for section in group.get("sections", []):
                    for entry in section.get("entries", []):
                        if not is_generated_dhe_entry(entry):
                            existing_non_dhe[tag].append(entry)

    # Build groups
    groups = []
    all_tags = sorted(set(list(tag_events.keys()) + list(existing_non_dhe.keys())))
    total_events = 0

    for tag in all_tags:
        dhe_evts = tag_events.get(tag, [])
        non_dhe_entries = existing_non_dhe.get(tag, [])

        if not dhe_evts and not non_dhe_entries:
            continue

        # Sort DHE events by date
        dhe_evts.sort(key=event_sort_key)

        # Group into century sections
        century_buckets: dict[int, list] = defaultdict(list)

        # Add DHE events
        for evt in dhe_evts:
            century = date_century(evt["date_from"])
            slug = slug_from_id(evt["id"])
            viewer_trigger = build_entry_viewer_metadata(evt)
            immediate_effect, option_effects = build_entry_effect_metadata(evt, slug)
            entry = {
                "id": evt["id"],
                "slug": slug,
                "icon": ICON,
                "title_loc": f"COUNTRY_EVENTS_AUTO_{slug}_TITLE",
                "subtitle_loc": f"COUNTRY_EVENTS_AUTO_{slug}_SUBTITLE",
                "desc_loc": f"COUNTRY_EVENTS_AUTO_{slug}_DESC",
                "requirements_loc": f"COUNTRY_EVENTS_AUTO_{slug}_REQUIREMENTS",
                "outcomes_loc": f"COUNTRY_EVENTS_AUTO_{slug}_OUTCOMES",
                "source_file": evt["source_file"],
                "source_kind": evt.get("source_kind", "game"),
                "source_mod": evt.get("source_mod", ""),
                "registry_origin": "dhe_extracted",
                "date_from": evt["date_from"],
                "date_to": evt["date_to"],
                "viewer_trigger": viewer_trigger,
                "immediate_effect": immediate_effect,
                "option_effects": option_effects,
                "source_tags": sorted(
                    {
                        str(source_tag).strip().upper()
                        for source_tag in evt.get("tags", [])
                        if str(source_tag).strip()
                    }
                ),
                "lineage_tags": sorted(
                    {
                        str(lineage_tag).strip().upper()
                        for lineage_tag in evt.get("successor_lineage_tags", [])
                        if str(lineage_tag).strip()
                    }
                ),
            }
            century_buckets[century].append(entry)

        # Add non-DHE events (preserve from existing registry)
        for entry in non_dhe_entries:
            century = date_century(entry.get("date_from", "1500.1.1"))
            # Avoid duplicates
            existing_ids = {e["id"] for e in century_buckets[century]}
            if entry["id"] not in existing_ids:
                century_buckets[century].append(entry)

        if not century_buckets:
            continue

        # Build sections
        sections = []
        tag_lower = tag.lower()
        for century in sorted(century_buckets.keys()):
            entries = century_buckets[century]
            # Sort entries by date_from
            entries.sort(key=lambda e: (e.get("date_from", ""), e.get("id", "")))
            total_events += len(entries)

            section = {
                "id": f"{tag_lower}_c{century}",
                "label_loc": f"COUNTRY_EVENTS_AUTO_TAG_{tag}_PERIOD_C{century}",
                "entries": entries,
            }
            sections.append(section)

        # Determine default event
        first_entry = sections[0]["entries"][0] if sections and sections[0]["entries"] else None
        default_event_id = first_entry["id"] if first_entry else ""

        group = {
            "id": f"tag_{tag_lower}",
            "country_tags": [tag],
            "summary_loc": f"COUNTRY_EVENTS_AUTO_TAG_{tag}_SUMMARY",
            "default_event_id": default_event_id,
            "sections": sections,
        }
        groups.append(group)

    # Count extracted events (those with auto loc content)
    registry = {
        "summary": {
            "groups": len(groups),
            "events": total_events,
            "extracted_events": total_events,
            "game_filter": "country_event with dynamic_historical_event in base game and detected installed mods",
            "heuristic": "per-tag groups: each tag gets all dynamic historical events where it appears from base game plus detected mods, plus preserved custom non-game entries from previous registry",
        },
        "groups": groups,
    }
    return registry


# ---------------------------------------------------------------------------
# Auto loc generation
# ---------------------------------------------------------------------------

def escape_loc_value(value: str) -> str:
    """Escape a string for Paradox YAML loc."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\\", "\\\\")
    value = value.replace("\n", "\\n")
    return value.replace('"', '\\"')


def generate_auto_loc(
    all_events: list[dict],
    game_loc: dict[str, str],
    existing_loc: dict[str, str],
    lang: str,
) -> dict[str, str]:
    """Generate auto loc entries for every extracted event."""
    set_current_game_loc(game_loc)
    new_entries: dict[str, str] = {}
    seen_slugs: set[str] = set()

    for evt in all_events:
        slug = slug_from_id(evt["id"])
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        new_entries[f"COUNTRY_EVENTS_AUTO_{slug}_TITLE"] = generate_event_title(evt, game_loc, lang)
        new_entries[f"COUNTRY_EVENTS_AUTO_{slug}_SUBTITLE"] = generate_event_subtitle(evt, lang)
        new_entries[f"COUNTRY_EVENTS_AUTO_{slug}_DESC"] = generate_event_desc(evt, game_loc, lang)
        new_entries[f"COUNTRY_EVENTS_AUTO_{slug}_META"] = generate_event_meta(evt, lang)
        new_entries[f"COUNTRY_EVENTS_AUTO_{slug}_REQUIREMENTS"] = generate_event_requirements(evt, lang)
        new_entries[f"COUNTRY_EVENTS_AUTO_{slug}_OUTCOMES"] = generate_event_outcomes(evt, game_loc, lang)
        option_blocks = evt.get("option_blocks") or []
        if not option_blocks and evt.get("option_names"):
            option_blocks = [{"name": name, "historical_option": False, "body_raw": ""} for name in evt.get("option_names", [])]
        for index, option in enumerate(option_blocks):
            new_entries[option_title_loc_key(slug, index)] = build_option_label(option, game_loc, index, lang)
        for key, value in iter_runtime_scalar_tooltips(evt.get("trigger_raw", ""), game_loc, lang):
            new_entries[key] = value

    return new_entries


def update_auto_loc_file(
    filepath: Path,
    lang: str,
    new_entries: dict[str, str],
    authoritative_period_keys: set[str] | None = None,
) -> int:
    """Upsert generated entries while pruning stale generated period labels."""
    if not new_entries:
        return 0

    def is_generated_period_key(key: str) -> bool:
        return key.startswith("COUNTRY_EVENTS_AUTO_TAG_") and "_PERIOD_" in key

    def is_generated_auto_key(key: str) -> bool:
        return key.startswith("COUNTRY_EVENTS_AUTO_")

    header, existing_entries = parse_loc_entries(filepath, lang)

    values: dict[str, str] = {}
    versions: dict[str, str] = {}
    ordered_keys: list[str] = []
    seen_keys: set[str] = set()
    removed = 0

    for key, version, value in existing_entries:
        if is_generated_auto_key(key) and key not in new_entries:
            removed += 1
            continue

        if (
            authoritative_period_keys is not None
            and is_generated_period_key(key)
            and key not in authoritative_period_keys
        ):
            removed += 1
            continue

        values[key] = value
        if key not in seen_keys:
            ordered_keys.append(key)
            versions[key] = version
            seen_keys.add(key)

    changed = 0
    for key, value in sorted(new_entries.items()):
        if values.get(key) != value:
            changed += 1
        values[key] = value
        if key not in seen_keys:
            ordered_keys.append(key)
            versions[key] = "0"
            seen_keys.add(key)

    if changed == 0 and removed == 0:
        return 0

    merged_entries = [(key, versions.get(key, "0"), values[key]) for key in ordered_keys]
    write_loc_entries(filepath, header, merged_entries)
    return changed + removed


# ---------------------------------------------------------------------------
# Section label loc generation
# ---------------------------------------------------------------------------

def generate_section_labels(registry: dict) -> dict[str, str]:
    """Generate section label loc entries for all groups."""
    labels: dict[str, str] = {}
    for group in registry.get("groups", []):
        for section in group.get("sections", []):
            label_key = section["label_loc"]
            # Extract century number from section ID
            m = re.search(r'_c(\d+)$', section["id"])
            if m:
                century = int(m.group(1))
                count = len(section.get("entries", []))
                labels[label_key] = format_section_label(century, count)
    return labels


def generate_summary_loc(registry: dict) -> dict[str, str]:
    """Generate summary loc entries for all groups."""
    summaries: dict[str, str] = {}
    for group in registry.get("groups", []):
        key = group["summary_loc"]
        total = sum(len(s.get("entries", [])) for s in group.get("sections", []))
        section_count = len(group.get("sections", []))
        section_label = "section" if section_count == 1 else "sections"
        summaries[key] = (
            f"Own dynamic historical events detected: {total}. "
            f"Organized into {section_count} chronological {section_label}. "
            "Select one to inspect its description, documented requirements, and effect."
        )
    return summaries


def build_viewer_triggers_content(all_events: list[dict]) -> str:
    """Generate scripted triggers used by the GUI live requirements list."""
    lines = [
        "# Auto-generated live requirement triggers for Unique Events Tab.",
        "# Regenerated by tools/generate_registry.py.",
    ]

    def append_scalar_viewer_line(raw_line: str) -> None:
        line = raw_line.rstrip()
        if not line:
            return

        variable_match = RUNTIME_VARIABLE_LINE_RE.match(line)
        if variable_match:
            indent, kind, variable_name = variable_match.groups()
            tooltip_key = runtime_variable_tooltip_key(kind, variable_name)
            lines.append(f"    {indent}custom_tooltip = {{")
            lines.append(f"    {indent}    text = {tooltip_key}")
            lines.append(f"    {indent}    {kind} = {variable_name}")
            lines.append(f"    {indent}}}")
            return

        comparison_match = RUNTIME_VARIABLE_COMPARISON_LINE_RE.match(line)
        if comparison_match:
            indent, scope_kind, variable_name, operator, value = comparison_match.groups()
            if value.strip() != "{":
                tooltip_key = runtime_variable_comparison_tooltip_key(scope_kind, variable_name, operator, value)
                existence_kind = runtime_variable_existence_kind(scope_kind)
                lines.append(f"    {indent}custom_tooltip = {{")
                lines.append(f"    {indent}    text = {tooltip_key}")
                lines.append(f"    {indent}    AND = {{")
                lines.append(f"    {indent}        {existence_kind} = {variable_name}")
                lines.append(f"    {indent}        trigger_if = {{")
                lines.append(f"    {indent}            limit = {{ {existence_kind} = {variable_name} }}")
                lines.append(f"    {indent}            {scope_kind}:{variable_name} {operator} {value.strip()}")
                lines.append(f"    {indent}        }}")
                lines.append(f"    {indent}    }}")
                lines.append(f"    {indent}}}")
                return

        boolean_match = RUNTIME_BOOLEAN_LINE_RE.match(line)
        if boolean_match:
            indent, key, value = boolean_match.groups()
            summary = summarize_trigger_node(ClausewitzNode(key=key, operator="=", value=value))
            if should_wrap_runtime_boolean(summary, key):
                tooltip_key = runtime_flag_tooltip_key(key, value)
                lines.append(f"    {indent}custom_tooltip = {{")
                lines.append(f"    {indent}    text = {tooltip_key}")
                lines.append(f"    {indent}    {key} = {value}")
                lines.append(f"    {indent}}}")
                return

        lines.append(f"    {line}")

    def append_viewer_nodes(
        nodes: list[ClausewitzNode],
        *,
        local_scripted_triggers: dict[str, list[ClausewitzNode]],
        indent_level: int = 1,
        expansion_stack: tuple[str, ...] = (),
    ) -> None:
        indent = "    " * indent_level
        for node in nodes:
            serialized_key = serialize_clausewitz_key(node.key)
            if (
                node.key in local_scripted_triggers
                and node.operator in {"=", "?="}
                and isinstance(node.value, str)
                and node.value.strip().lower() == "yes"
            ):
                if node.key in expansion_stack:
                    append_scalar_viewer_line(f"{indent}{node.key} {node.operator} {node.value}")
                else:
                    append_viewer_nodes(
                        local_scripted_triggers[node.key],
                        local_scripted_triggers=local_scripted_triggers,
                        indent_level=indent_level,
                        expansion_stack=expansion_stack + (node.key,),
                    )
                continue

            if isinstance(node.value, list):
                lines.append(f"    {indent}{serialized_key} {node.operator} {{")
                append_viewer_nodes(
                    node.value,
                    local_scripted_triggers=local_scripted_triggers,
                    indent_level=indent_level + 1,
                    expansion_stack=expansion_stack,
                )
                lines.append(f"    {indent}}}")
                continue

            append_scalar_viewer_line(f"{indent}{serialized_key} {node.operator} {node.value}")

    for event in sorted(all_events, key=lambda item: str(item.get("id", "")).lower()):
        viewer_name = build_entry_viewer_metadata(event)
        if not viewer_name:
            continue

        trigger_raw = str(event.get("trigger_raw", "")).strip()
        expanded_nodes = []
        if trigger_raw:
            expanded_nodes = sanitize_runtime_viewer_nodes(
                expand_local_trigger_nodes(
                    parse_clausewitz_block(trigger_raw),
                    event.get("local_scripted_triggers") or {},
                )
            )

        lines.append("")
        lines.append(f"{viewer_name} = {{")
        lines.append(f"    current_date > {event['date_from']}")
        lines.append(f"    current_date < {event['date_to']}")

        if expanded_nodes:
            append_viewer_nodes(
                expanded_nodes,
                local_scripted_triggers=event.get("local_scripted_triggers") or {},
            )

        lineage_tags = [
            str(tag).strip().upper()
            for tag in event.get("successor_lineage_tags", [])
            if str(tag).strip()
        ]
        if lineage_tags:
            if len(lineage_tags) == 1:
                lines.append(f"    has_or_had_tag = {lineage_tags[0]}")
            else:
                lines.append("    OR = {")
                for lineage_tag in lineage_tags:
                    lines.append(f"        has_or_had_tag = {lineage_tag}")
                lines.append("    }")

        lines.append("}")

    return "\n".join(lines).rstrip() + "\n"


def build_viewer_effects_content(all_events: list[dict]) -> str:
    """Build generated scripted-effect wrappers for immediate and option previews."""
    lines = [
        "### Auto-generated by tools/generate_registry.py.",
        "### Runtime scripted effects for Unique Events Tab UI previews.",
    ]

    for event in sorted(all_events, key=lambda item: str(item.get("id", "")).lower()):
        local_scripted_effects = event.get("local_scripted_effects") or {}
        expanded_immediate_nodes = expand_local_scripted_effects(
            parse_clausewitz_block(str(event.get("immediate_raw", "")).strip()),
            local_scripted_effects,
        )
        bootstrap_nodes = sanitize_runtime_preview_nodes(
            extract_runtime_preview_bootstrap_nodes(expanded_immediate_nodes)
        )
        allowed_saved_scopes = collect_saved_scope_names(bootstrap_nodes)

        immediate_nodes = build_preview_wrapper_nodes(
            event,
            str(event.get("immediate_raw", "")).strip(),
            bootstrap_nodes=bootstrap_nodes,
            allowed_saved_scopes=allowed_saved_scopes,
        )
        if immediate_nodes:
            lines.append("")
            lines.append(f"{immediate_effect_name(event)} = {{")
            lines.extend(serialize_clausewitz_nodes(immediate_nodes))
            lines.append("}")

        for index, option in enumerate(event.get("option_blocks") or []):
            effect_nodes = build_preview_wrapper_nodes(
                event,
                str(option.get("body_raw", "")).strip(),
                bootstrap_nodes=bootstrap_nodes,
                allowed_saved_scopes=allowed_saved_scopes,
            )
            if not effect_nodes:
                continue

            lines.append("")
            lines.append(f"{option_effect_name(event, index)} = {{")
            lines.extend(serialize_clausewitz_nodes(effect_nodes))
            lines.append("}")

    return "\n".join(lines).rstrip() + "\n"


def collect_lineage_tags(
    all_events: list[dict[str, object]],
    registry: dict[str, object],
) -> list[str]:
    """Return every country tag that should be mirrored into a GUI-readable lineage variable."""
    tags: set[str] = set()
    for event in all_events:
        for tag in event.get("tags", []):
            normalized = str(tag).strip().upper()
            if normalized:
                tags.add(normalized)
        for tag in event.get("successor_lineage_tags", []):
            normalized = str(tag).strip().upper()
            if normalized:
                tags.add(normalized)

    for group in registry.get("groups", []):
        for tag in group.get("country_tags", []):
            normalized = str(tag).strip().upper()
            if normalized:
                tags.add(normalized)

    return sorted(tags)


def build_lineage_effects_content(lineage_tags: list[str]) -> str:
    """Build a generated scripted effect that mirrors has_or_had_tag into country variables."""
    lines = [
        "### Auto-generated by tools/generate_registry.py.",
        "### Mirrors has_or_had_tag into persistent country variables readable from GUI.",
        "",
        "ce_sync_country_events_lineage = {",
    ]

    for tag in lineage_tags:
        var_name = lineage_variable_name(tag)
        lines.extend(
            [
                "    if = {",
                f"        limit = {{ has_or_had_tag = {tag} NOT = {{ has_variable = {var_name} }} }}",
                f"        set_variable = {{ name = {var_name} value = 1 }}",
                "    }",
            ]
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def write_viewer_triggers(all_events: list[dict], output_path: Path) -> None:
    """Write the generated live requirement trigger file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_viewer_triggers_content(all_events),
        encoding="utf-8-sig",
        newline="\n",
    )


def write_viewer_effects(all_events: list[dict], output_path: Path) -> None:
    """Write the generated runtime scripted-effect wrapper file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_viewer_effects_content(all_events),
        encoding="utf-8-sig",
        newline="\n",
    )


def write_lineage_effects(lineage_tags: list[str], output_path: Path) -> None:
    """Write the generated lineage-sync scripted effect file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_lineage_effects_content(lineage_tags),
        encoding="utf-8-sig",
        newline="\n",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate country events registry from DHE files.")
    parser.add_argument(
        "--game-root", type=Path, required=True,
        help="Europa Universalis V install root.",
    )
    parser.add_argument(
        "--registry", type=Path, default=DEFAULT_REGISTRY,
        help=f"Output registry JSON path. Default: {DEFAULT_REGISTRY}",
    )
    parser.add_argument(
        "--loc-dir", type=Path, default=DEFAULT_LOC_DIR,
        help=f"Localization output directory. Default: {DEFAULT_LOC_DIR}",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_BUILD_STATE,
        help=f"Build cache state file. Default: {DEFAULT_BUILD_STATE}",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=DEFAULT_BUILD_STATUS,
        help=f"Build status file. Default: {DEFAULT_BUILD_STATUS}",
    )
    parser.add_argument(
        "--viewer-triggers",
        type=Path,
        default=DEFAULT_VIEWER_TRIGGERS,
        help=f"Generated scripted trigger path for live requirements. Default: {DEFAULT_VIEWER_TRIGGERS}",
    )
    parser.add_argument(
        "--viewer-effects",
        type=Path,
        default=DEFAULT_VIEWER_EFFECTS,
        help=f"Generated scripted effect path for UI previews. Default: {DEFAULT_VIEWER_EFFECTS}",
    )
    parser.add_argument(
        "--lineage-effects",
        type=Path,
        default=DEFAULT_LINEAGE_EFFECTS,
        help=f"Generated scripted effect path for GUI lineage sync. Default: {DEFAULT_LINEAGE_EFFECTS}",
    )
    parser.add_argument(
        "--preserve-non-dhe", action="store_true", default=True,
        help="Preserve non-DHE entries from existing registry (default: true).",
    )
    parser.add_argument(
        "--skip-loc", action="store_true",
        help="Skip auto loc generation.",
    )
    parser.add_argument(
        "--skip-external-mods",
        action="store_true",
        help="Scan only the base game and ignore local/Workshop mods.",
    )
    parser.add_argument(
        "--extra-mod-root",
        type=Path,
        action="append",
        default=[],
        help="Additional mod root to scan. Can be passed multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    registry_path = args.registry.resolve()
    loc_dir = args.loc_dir.resolve()
    state_file_path = args.state_file.resolve()
    status_file_path = args.status_file.resolve()
    viewer_triggers_path = args.viewer_triggers.resolve()
    viewer_effects_path = args.viewer_effects.resolve()
    lineage_effects_path = args.lineage_effects.resolve()

    base_events_dir = game_root / "game" / "in_game" / "events"
    if not base_events_dir.is_dir():
        print(f"error: events directory not found: {base_events_dir}", file=sys.stderr)
        return 1

    external_sources = [] if args.skip_external_mods else discover_external_mod_sources(
        game_root,
        [path.resolve() for path in args.extra_mod_root],
    )
    if external_sources:
        print("Detected external mod sources:")
        for source in external_sources:
            print(f"  - [{source.kind}] {source.name}: {source.root}")
    else:
        print("Detected external mod sources: none")

    sources = [
        ContentSource(
            name="Base Game",
            kind="game",
            root=game_root.resolve(),
            events_dir=base_events_dir,
            loc_dir=game_root / "game" / "main_menu" / "localization",
        ),
        *external_sources,
    ]
    input_fingerprint = build_registry_input_fingerprint(
        game_root,
        sources,
        include_loc=not args.skip_loc,
        preserve_non_dhe=args.preserve_non_dhe,
        registry_path=registry_path,
        extra_mod_roots=args.extra_mod_root,
        skip_external_mods=args.skip_external_mods,
    )
    expected_outputs = [registry_path, viewer_triggers_path, viewer_effects_path, lineage_effects_path]
    if not args.skip_loc:
        expected_outputs.extend(
            loc_dir / lang / f"country_events_auto_l_{lang}.yml"
            for lang in LANGUAGES
        )
    state = read_json_file(state_file_path)
    if (
        state.get("input_fingerprint") == input_fingerprint
        and all(path.is_file() for path in expected_outputs)
    ):
        print("\nRegistry inputs unchanged; skipping registry rebuild.")
        write_json_file(
            status_file_path,
            {
                "changed": False,
                "input_fingerprint": input_fingerprint,
            },
        )
        return 0

    # Parse all event files and keep only country events with dynamic_historical_event
    print(f"Scanning event files in {base_events_dir}...")
    all_events: list[dict] = []
    file_count = 0

    global SCRIPTED_EFFECT_DEFS
    SCRIPTED_EFFECT_DEFS = load_scripted_effect_definitions(sources)
    print(f"Loaded {len(SCRIPTED_EFFECT_DEFS)} scripted effect definitions.")

    for source in sources:
        if not source.events_dir.is_dir():
            continue
        print(f"  Source: {source.name} ({source.kind})")
        for filepath in sorted(source.events_dir.rglob("*.txt")):
            events = parse_event_file(
                filepath,
                source.events_dir,
                source_kind=source.kind,
                source_name=source.name,
            )
            all_events.extend(events)
            file_count += 1
            if events:
                tags = set()
                for event in events:
                    tags.update(event["tags"])
                relpath = filepath.relative_to(source.events_dir).as_posix()
                print(f"    {relpath}: {len(events)} events, tags: {sorted(tags)}")

    raw_event_count = len(all_events)
    all_events, override_count = dedupe_events_by_id(all_events)
    annotate_event_transition_metadata(all_events)
    print(
        f"\nParsed {file_count} event files, found {raw_event_count} dynamic historical events "
        f"total, {len(all_events)} unique after {override_count} overrides."
    )

    # Unique tags
    all_tags = set()
    for evt in all_events:
        all_tags.update(evt["tags"])
    print(f"Unique country tags: {len(all_tags)}")

    # Load existing registry for non-DHE preservation
    existing_registry = None
    if args.preserve_non_dhe and registry_path.is_file():
        existing_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        non_dhe_count = sum(
            1 for g in existing_registry.get("groups", [])
            for s in g.get("sections", [])
            for e in s.get("entries", [])
            if not is_generated_dhe_entry(e)
        )
        print(f"Preserving {non_dhe_count} non-DHE entries from existing registry.")

    # Build registry
    registry = build_registry(all_events, existing_registry, game_root=game_root)
    print(f"\nRegistry: {registry['summary']['groups']} groups, {registry['summary']['events']} events.")

    # Write registry
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {registry_path}")

    write_viewer_triggers(all_events, viewer_triggers_path)
    print(f"Wrote {viewer_triggers_path}")

    write_viewer_effects(all_events, viewer_effects_path)
    print(f"Wrote {viewer_effects_path}")

    lineage_tags = collect_lineage_tags(all_events, registry)
    write_lineage_effects(lineage_tags, lineage_effects_path)
    print(f"Wrote {lineage_effects_path}")

    # Generate auto loc
    if not args.skip_loc:
        print("\nGenerating auto localization...")
        english_loc_base = load_merged_loc(game_root, "english", external_sources)
        for lang in LANGUAGES:
            print(f"  Processing {lang}...")
            # Load base game + mod loc for titles/descriptions, with English fallback.
            if lang == "english":
                game_loc = dict(english_loc_base)
            else:
                game_loc = dict(english_loc_base)
                game_loc.update(load_merged_loc(game_root, lang, external_sources))
            print(f"    Merged loc keys loaded: {len(game_loc)}")

            # Load existing auto loc
            auto_loc_path = loc_dir / lang / f"country_events_auto_l_{lang}.yml"
            existing_loc = parse_loc_file(auto_loc_path)

            # Generate new entries
            new_entries = generate_auto_loc(all_events, game_loc, existing_loc, lang)

            # Also generate section labels and summaries
            section_labels = generate_section_labels(registry)
            summary_entries = generate_summary_loc(registry)
            # Period labels must always be regenerated so counts and format stay in sync.
            new_entries.update(section_labels)
            # Summaries are generated from the current registry and should stay in sync too.
            new_entries.update(summary_entries)

            if new_entries:
                count = update_auto_loc_file(
                    auto_loc_path,
                    lang,
                    new_entries,
                    authoritative_period_keys=set(section_labels),
                )
                print(f"    Updated {count} entries in {auto_loc_path.name}")
            else:
                print(f"    No new entries needed for {lang}")

    # Summary
    max_secs = 0
    max_evts = 0
    for group in registry.get("groups", []):
        sections = group.get("sections", [])
        max_secs = max(max_secs, len(sections))
        for section in sections:
            max_evts = max(max_evts, len(section.get("entries", [])))

    print(f"\nMax sections per group: {max_secs}")
    print(f"Max events per section: {max_evts}")
    print(f"\nIMPORTANT: After running this script, regenerate:")
    print(f"  1. GUI: python tools/generate_country_events_gui.py --game-root <path>")
    print(f"  2. Slot loc: python tools/generate_country_events_loc.py")
    print(f"  3. Cleanup: python tools/cleanup_auto_loc.py --game-loc-root <path>/game/main_menu/localization")

    final_input_fingerprint = build_registry_input_fingerprint(
        game_root,
        sources,
        include_loc=not args.skip_loc,
        preserve_non_dhe=args.preserve_non_dhe,
        registry_path=registry_path,
        extra_mod_roots=args.extra_mod_root,
        skip_external_mods=args.skip_external_mods,
    )
    write_json_file(
        state_file_path,
        {
            "input_fingerprint": final_input_fingerprint,
        },
    )
    write_json_file(
        status_file_path,
        {
            "changed": True,
            "input_fingerprint": final_input_fingerprint,
        },
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
