#!/usr/bin/env python3
"""Generate slot-based localization files from the country events registry.

This creates two sets of localization keys:

1. Slot-mapping keys (CE_*) used by the generic GUI to discover which
   sections and events exist per country tag:
   - CE_HAS_{TAG}          = "1"                (country has events)
   - CE_SV_{TAG}_{SEC}     = "1"                (section exists)
   - CE_SL_{TAG}_{SEC}     = "S.XIV (27)"       (section label)
   - CE_EV_{TAG}_{SEC}_{EVT} = "1"             (event slot exists)

2. Content keys (COUNTRY_EVENTS_AUTO_*) using indexed slugs so the
   generic GUI can construct them with Concatenate(Player.GetTag, ...):
   - COUNTRY_EVENTS_AUTO_{TAG}_{SEC}_{EVT}_TITLE
   - COUNTRY_EVENTS_AUTO_{TAG}_{SEC}_{EVT}_SUBTITLE
   - COUNTRY_EVENTS_AUTO_{TAG}_{SEC}_{EVT}_DESC
   - COUNTRY_EVENTS_AUTO_{TAG}_{SEC}_{EVT}_META
   - COUNTRY_EVENTS_AUTO_{TAG}_{SEC}_{EVT}_REQUIREMENTS
   - COUNTRY_EVENTS_AUTO_{TAG}_{SEC}_{EVT}_OUTCOMES
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from country_runtime_aliases import group_runtime_keys

SCRIPT_PATH = Path(__file__).resolve()
MOD_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_REGISTRY = MOD_ROOT / "data" / "country_events_registry.json"
DEFAULT_LOC_DIR = MOD_ROOT / "main_menu" / "localization"

LANGUAGES = [
    "braz_por",
    "english",
    "french",
    "german",
    "japanese",
    "korean",
    "polish",
    "russian",
    "simp_chinese",
    "spanish",
    "turkish",
]

CONTENT_SUFFIXES = ["TITLE", "SUBTITLE", "DESC", "META", "REQUIREMENTS", "OUTCOMES"]
UI_LOC_KEYS = {
    "COUNTRY_EVENTS_FILTER_ALL": {
        "english": "All",
        "spanish": "Todos",
        "french": "Tous",
        "german": "Alle",
        "braz_por": "Todos",
        "polish": "Wszystkie",
    },
    "COUNTRY_EVENTS_FILTER_AVAILABLE": {
        "english": "Available",
        "spanish": "Disponibles",
        "french": "Disponibles",
        "german": "Verfugbar",
        "braz_por": "Disponiveis",
        "polish": "Dostepne",
    },
    "COUNTRY_EVENTS_FILTER_UPCOMING": {
        "english": "Upcoming",
        "spanish": "Proximos",
        "french": "A venir",
        "german": "Bevorstehend",
        "braz_por": "Em breve",
        "polish": "Nadchodzace",
    },
    "COUNTRY_EVENTS_FILTER_EXPIRED": {
        "english": "Expired",
        "spanish": "Expirados",
        "french": "Expires",
        "german": "Abgelaufen",
        "braz_por": "Expirados",
        "polish": "Wygasle",
    },
    "COUNTRY_EVENTS_FILTER_FIRED": {
        "english": "Fired",
        "spanish": "Disparados",
        "french": "Declenches",
        "german": "Ausgelost",
        "braz_por": "Disparados",
        "polish": "Uruchomione",
    },
    "COUNTRY_EVENTS_PREVIEW_PARTIAL_EFFECTS": {
        "english": "Some dynamic effects could not be previewed fully before the event fires.",
        "spanish": "Algunos efectos dinamicos no han podido previsualizarse por completo antes de que se dispare el evento.",
        "french": "Some dynamic effects could not be previewed fully before the event fires.",
        "german": "Some dynamic effects could not be previewed fully before the event fires.",
        "braz_por": "Some dynamic effects could not be previewed fully before the event fires.",
        "polish": "Some dynamic effects could not be previewed fully before the event fires.",
    },
}

CENTURY_ROMAN = {
    13: "XIII",
    14: "XIV",
    15: "XV",
    16: "XVI",
    17: "XVII",
    18: "XVIII",
    19: "XIX",
}


def escape_loc_value(value: str) -> str:
    """Escape a string for use inside a YAML localization value."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\\", "\\\\")
    value = value.replace("\n", "\\n")
    return value.replace('"', '\\"')


def unescape_loc_value(value: str) -> str:
    """Decode common Paradox loc escapes and discard broken ones safely."""
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


def format_section_label(label_key: str, count: int, fallback: str) -> str:
    """Prefer compact century labels like S.XVII (18) for the top tabs."""
    match = re.search(r"_C(\d+)$", label_key)
    if not match:
        return fallback

    century = int(match.group(1))
    roman = CENTURY_ROMAN.get(century)
    if roman is None:
        return fallback
    return f"S.{roman} ({count})"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate slot-based localization from the country events registry."
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"Registry JSON path. Default: {DEFAULT_REGISTRY}",
    )
    parser.add_argument(
        "--loc-dir",
        type=Path,
        default=DEFAULT_LOC_DIR,
        help=f"Localization output directory. Default: {DEFAULT_LOC_DIR}",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if generated output differs from current files.",
    )
    return parser.parse_args()


def build_loc_entries(
    registry_data: dict[str, object],
    lang: str,
    existing_loc: dict[str, str],
) -> list[str]:
    """Build localization lines for one language."""
    groups = registry_data.get("groups", [])
    lines: list[str] = []
    canonical_tags = {
        str(group.get("country_tags", [])[0])
        for group in groups
        if len(group.get("country_tags", [])) == 1
    }

    for key, translations in UI_LOC_KEYS.items():
        value = translations.get(lang, translations["english"])
        lines.append(f' {key}:0 "{escape_loc_value(value)}"')

    for group in groups:
        tags = group.get("country_tags", [])
        if len(tags) != 1:
            continue
        sections = group.get("sections", [])
        for runtime_key in group_runtime_keys(group, canonical_tags):
            # CE_HAS_{TAG}
            lines.append(f' CE_HAS_{runtime_key}:0 "1"')

            for sec_idx, section in enumerate(sections):
                entries = section.get("entries", [])

                # CE_SV_{TAG}_{SEC} - section visible
                lines.append(f' CE_SV_{runtime_key}_{sec_idx}:0 "1"')

                # CE_SL_{TAG}_{SEC} - section label
                label_key = section.get("label_loc", "")
                fallback_label = existing_loc.get(label_key, label_key)
                label_text = format_section_label(label_key, len(entries), fallback_label)
                lines.append(
                    f' CE_SL_{runtime_key}_{sec_idx}:0 "{escape_loc_value(label_text)}"'
                )

                for evt_idx, entry in enumerate(entries):
                    slug = entry.get("slug", "")

                    # CE_EV_{TAG}_{SEC}_{EVT} - event visible
                    lines.append(f' CE_EV_{runtime_key}_{sec_idx}_{evt_idx}:0 "1"')

                    # Content keys: COUNTRY_EVENTS_AUTO_{TAG}_{SEC}_{EVT}_{SUFFIX}
                    for suffix in CONTENT_SUFFIXES:
                        old_key = f"COUNTRY_EVENTS_AUTO_{slug}_{suffix}"
                        value = existing_loc.get(old_key, "")
                        new_key = f"COUNTRY_EVENTS_AUTO_{runtime_key}_{sec_idx}_{evt_idx}_{suffix}"
                        lines.append(
                            f' {new_key}:0 "{escape_loc_value(value)}"'
                        )

    return lines


def parse_loc_file(path: Path) -> dict[str, str]:
    """Parse a Paradox localization YAML file into a key→value dict."""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("l_") or line.startswith("#"):
            continue
        colon_pos = line.find(":")
        if colon_pos == -1:
            continue
        key = line[:colon_pos].strip()
        rest = line[colon_pos + 1 :].strip()
        # Skip version number (e.g., "0 ")
        if rest and rest[0].isdigit():
            space_pos = rest.find(" ")
            if space_pos != -1:
                rest = rest[space_pos + 1 :]
        # Remove surrounding quotes
        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]
        result[key] = unescape_loc_value(rest)
    return result


def main() -> int:
    args = parse_args()
    registry_path = args.registry.resolve()
    loc_dir = args.loc_dir.resolve()

    if not registry_path.is_file():
        raise FileNotFoundError(f"Registry not found: {registry_path}")

    registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    groups = registry_data.get("groups", [])
    total_events = sum(
        len(e)
        for g in groups
        for s in g.get("sections", [])
        for e in [s.get("entries", [])]
    )

    files_written = 0
    check_failed = False

    for lang in LANGUAGES:
        lang_dir = loc_dir / lang
        lang_dir.mkdir(parents=True, exist_ok=True)

        # Read existing auto loc to get content values
        existing_path = lang_dir / f"country_events_auto_l_{lang}.yml"
        existing_loc = parse_loc_file(existing_path)

        loc_lines = build_loc_entries(registry_data, lang, existing_loc)
        content = f"l_{lang}:\n" + "\n".join(loc_lines) + "\n"

        output_path = lang_dir / f"country_events_slots_l_{lang}.yml"

        if args.check:
            current = output_path.read_text(encoding="utf-8-sig") if output_path.exists() else ""
            if current != content:
                print(f"Out of date: {output_path}")
                check_failed = True
            continue

        output_path.write_text(content, encoding="utf-8-sig", newline="\n")
        files_written += 1

    if args.check:
        return 1 if check_failed else 0

    print(f"Wrote {files_written} localization files")
    print(f"Generated slot keys for {len(groups)} countries, {total_events} events")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
