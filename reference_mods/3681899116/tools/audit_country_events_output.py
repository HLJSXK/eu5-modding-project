#!/usr/bin/env python3
"""Audit generated Unique Events Tab outputs for common regressions.

Checks:
 - missing live requirement viewers
 - missing native effect previews
 - suspicious placeholder phrases in generated text
 - suspicious generated English titles
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
MOD_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_REGISTRY = MOD_ROOT / "data" / "country_events_registry.json"
DEFAULT_ENGLISH_LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "country_events_auto_l_english.yml"
DEFAULT_RUNTIME_REQUIREMENTS = MOD_ROOT / "in_game" / "common" / "scripted_triggers" / "country_events_runtime_requirements.txt"
DEFAULT_RUNTIME_EFFECTS = MOD_ROOT / "in_game" / "common" / "scripted_effects" / "country_events_runtime_effects.txt"

TEXT_PLACEHOLDER_PATTERNS = {
    "ellipsis": re.compile(r"\(\.\.\.\)", re.IGNORECASE),
    "this_character": re.compile(r"\bthis character\b", re.IGNORECASE),
    "that_country": re.compile(r"\bthat country\b", re.IGNORECASE),
    "the_our": re.compile(r"\bthe our\b", re.IGNORECASE),
}

TITLE_RED_FLAG_PATTERNS = {
    "the_foreign": re.compile(r'_TITLE:0 "The foreign\b'),
    "the_our": re.compile(r'_TITLE:0 "The our\b'),
    "a_foreign": re.compile(r'_TITLE:0 "A foreign\b'),
    "a_our": re.compile(r'_TITLE:0 "A our\b'),
    "an_foreign": re.compile(r'_TITLE:0 "An foreign\b'),
    "an_our": re.compile(r'_TITLE:0 "An our\b'),
}

UNQUOTED_EXPRESSION_KEY_RE = re.compile(
    r"^\s*(?!\")(?P<expr>[^\s\"{}][^=<>!?{}]*\([^{}]*\))\s*(?:!=|\?=|>=|<=|=|>|<)\s",
    re.MULTILINE,
)


def load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_entries(registry: dict):
    for group in registry.get("groups", []):
        group_id = str(group.get("id", ""))
        for section in group.get("sections", []):
            section_id = str(section.get("id", ""))
            for entry in section.get("entries", []):
                yield group_id, section_id, entry


def has_native_effect_preview(entry: dict) -> bool:
    if str(entry.get("immediate_effect", "")).strip():
        return True
    for option in entry.get("option_effects", []):
        if str(option.get("effect", "")).strip():
            return True
    return False


def audit_registry(registry: dict) -> dict[str, object]:
    entries = list(iter_entries(registry))
    total_entries = len(entries)

    missing_viewers: list[tuple[str, str, str, str]] = []
    missing_native_effects: list[tuple[str, str, str, str]] = []
    placeholder_hits: dict[str, list[tuple[str, str]]] = {key: [] for key in TEXT_PLACEHOLDER_PATTERNS}

    for group_id, section_id, entry in entries:
        event_id = str(entry.get("id", ""))
        source_file = str(entry.get("source_file", ""))
        if not str(entry.get("viewer_trigger", "")).strip():
            missing_viewers.append((event_id, group_id, section_id, source_file))
        if not has_native_effect_preview(entry):
            missing_native_effects.append((event_id, group_id, section_id, source_file))

        for field in ("title", "desc", "requirements", "outcomes"):
            text = str(entry.get(field, ""))
            for name, pattern in TEXT_PLACEHOLDER_PATTERNS.items():
                if pattern.search(text):
                    placeholder_hits[name].append((event_id, field))

    return {
        "total_entries": total_entries,
        "missing_viewers": missing_viewers,
        "missing_native_effects": missing_native_effects,
        "placeholder_hits": placeholder_hits,
    }


def audit_english_titles(path: Path) -> dict[str, list[str]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    hits: dict[str, list[str]] = {key: [] for key in TITLE_RED_FLAG_PATTERNS}
    for line in lines:
        for name, pattern in TITLE_RED_FLAG_PATTERNS.items():
            if pattern.search(line):
                hits[name].append(line.strip())
    return hits


def audit_runtime_expression_keys(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    hits: list[str] = []
    for match in UNQUOTED_EXPRESSION_KEY_RE.finditer(text):
        line = match.group(0).strip()
        hits.append(line)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated Unique Events Tab outputs.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--english-loc", type=Path, default=DEFAULT_ENGLISH_LOC)
    parser.add_argument("--runtime-requirements", type=Path, default=DEFAULT_RUNTIME_REQUIREMENTS)
    parser.add_argument("--runtime-effects", type=Path, default=DEFAULT_RUNTIME_EFFECTS)
    args = parser.parse_args()

    registry = load_registry(args.registry)
    registry_report = audit_registry(registry)
    title_hits = audit_english_titles(args.english_loc)
    runtime_requirements_hits = audit_runtime_expression_keys(args.runtime_requirements)
    runtime_effect_hits = audit_runtime_expression_keys(args.runtime_effects)

    print(f"total_entries: {registry_report['total_entries']}")
    print(f"missing_viewers: {len(registry_report['missing_viewers'])}")
    for item in registry_report["missing_viewers"][:20]:
        print(f"  viewer_missing: {item[0]} [{item[1]} / {item[2]}] {item[3]}")

    print(f"missing_native_effects: {len(registry_report['missing_native_effects'])}")
    for item in registry_report["missing_native_effects"][:20]:
        print(f"  native_effect_missing: {item[0]} [{item[1]} / {item[2]}] {item[3]}")

    for name, hits in registry_report["placeholder_hits"].items():
        print(f"text_placeholder_{name}: {len(hits)}")
        for event_id, field in hits[:10]:
            print(f"  placeholder_{name}: {event_id} field={field}")

    title_red_flag_total = 0
    for name, hits in title_hits.items():
        print(f"title_red_flag_{name}: {len(hits)}")
        title_red_flag_total += len(hits)
        for line in hits[:10]:
            print(f"  title_red_flag: {line}")

    print(f"runtime_requirements_unquoted_expression_keys: {len(runtime_requirements_hits)}")
    for line in runtime_requirements_hits[:10]:
        print(f"  runtime_requirements_unquoted: {line}")

    print(f"runtime_effects_unquoted_expression_keys: {len(runtime_effect_hits)}")
    for line in runtime_effect_hits[:10]:
        print(f"  runtime_effects_unquoted: {line}")

    # Strict success only when the generated output is fully clean by these checks.
    if (
        registry_report["missing_viewers"]
        or registry_report["missing_native_effects"]
        or any(registry_report["placeholder_hits"].values())
        or title_red_flag_total
        or runtime_requirements_hits
        or runtime_effect_hits
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
