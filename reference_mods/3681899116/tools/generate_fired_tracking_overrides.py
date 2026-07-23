#!/usr/bin/env python3
"""Generate fired-status script values for tracked DHEs.

This replaces the old event-override approach. The mod no longer mirrors
vanilla event files under ``in_game/events`` just to track fired status.
Instead it emits script_values that query the native
``has_fired_unique_event`` trigger for fire_only_once DHEs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import generate_registry as registry_tools


SCRIPT_PATH = Path(__file__).resolve()
MOD_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_REGISTRY = MOD_ROOT / "data" / "country_events_registry.json"
DEFAULT_OUTPUT_FILE = (
    MOD_ROOT / "in_game" / "common" / "script_values" / "country_events_fired_status_values.txt"
)
LEGACY_OUTPUT_ROOT = MOD_ROOT / "in_game" / "events"
DEFAULT_MANIFEST = MOD_ROOT / "data" / "generated_fired_tracking_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate fired-status script values for tracked DHEs and remove legacy "
            "event overrides."
        )
    )
    parser.add_argument(
        "--game-root",
        type=Path,
        required=True,
        help="Europa Universalis V install root.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"Registry JSON path. Default: {DEFAULT_REGISTRY}",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Generated script_values output path. Default: {DEFAULT_OUTPUT_FILE}",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Generated-file manifest path. Default: {DEFAULT_MANIFEST}",
    )
    parser.add_argument(
        "--skip-external-mods",
        action="store_true",
        help="Generate fired tracking only for base-game events.",
    )
    parser.add_argument(
        "--extra-mod-root",
        type=Path,
        action="append",
        default=[],
        help="Additional mod root to scan. Can be passed multiple times.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if generated overrides differ from disk.",
    )
    return parser.parse_args()


def fired_variable_name(slug: str) -> str:
    return f"ce_fired_{slug.lower()}"


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def mask_comments_preserve_length(text: str) -> str:
    """Replace comment text with spaces while preserving indices and newlines."""
    masked_lines: list[str] = []
    for line in normalize_text(text).splitlines(keepends=True):
        hash_pos = line.find("#")
        if hash_pos == -1:
            masked_lines.append(line)
            continue
        comment = line[hash_pos:]
        comment_mask = "".join("\n" if ch == "\n" else " " for ch in comment)
        masked_lines.append(line[:hash_pos] + comment_mask)
    return "".join(masked_lines)


def iter_event_blocks(text: str) -> list[tuple[str, int, int]]:
    ns_match = registry_tools.re.search(r"^\s*namespace\s*=\s*(\S+)", text, registry_tools.re.MULTILINE)
    namespace = ns_match.group(1) if ns_match else ""
    if not namespace:
        return []

    pattern = registry_tools.re.compile(rf"({registry_tools.re.escape(namespace)}\.(\d+))\s*=\s*\{{")
    blocks: list[tuple[str, int, int]] = []
    for match in pattern.finditer(text):
        event_id = match.group(1)
        brace_pos = match.end() - 1
        close = registry_tools.find_matching_brace(text, brace_pos)
        if close == -1:
            continue
        blocks.append((event_id, brace_pos, close))
    return blocks


def collect_tracked_events(registry_data: dict[str, object]) -> dict[tuple[str, str, str], dict[str, str]]:
    tracked_by_file: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    for group in registry_data.get("groups", []):
        for section in group.get("sections", []):
            for entry in section.get("entries", []):
                if not registry_tools.is_generated_dhe_entry(entry):
                    continue
                event_id = str(entry.get("id", "")).strip()
                slug = str(entry.get("slug", "")).strip()
                source_file = str(entry.get("source_file", "")).strip()
                source_kind = str(entry.get("source_kind", "")).strip()
                source_mod = str(entry.get("source_mod", "")).strip()
                if not event_id or not slug or not source_file or not source_kind or not source_mod:
                    continue
                tracked_by_file[(source_kind, source_mod, source_file)][event_id] = slug
    return tracked_by_file


def collect_fire_once_event_ids(source_text: str, tracked_events: dict[str, str]) -> tuple[set[str], list[str]]:
    masked = mask_comments_preserve_length(source_text)
    found_ids = set(tracked_events)
    fire_once_ids: set[str] = set()

    for event_id, brace_pos, close in iter_event_blocks(masked):
        if event_id not in tracked_events:
            continue
        found_ids.discard(event_id)
        event_body = masked[brace_pos + 1 : close]
        if registry_tools.extract_kv(event_body, "type") != "country_event":
            continue
        if registry_tools.extract_block(event_body, "dynamic_historical_event") is None:
            continue
        if registry_tools.extract_kv(event_body, "fire_only_once") == "yes":
            fire_once_ids.add(event_id)

    return fire_once_ids, sorted(found_ids)


def build_fired_status_content(
    registry_data: dict[str, object],
    fire_once_ids: set[str],
) -> str:
    entries: dict[str, str] = {}
    for group in registry_data.get("groups", []):
        for section in group.get("sections", []):
            for entry in section.get("entries", []):
                if not registry_tools.is_generated_dhe_entry(entry):
                    continue
                event_id = str(entry.get("id", "")).strip()
                slug = str(entry.get("slug", "")).strip()
                if event_id and slug and event_id not in entries:
                    entries[event_id] = slug

    lines = [
        "# Auto-generated fired-status script values for Unique Events Tab.",
        "# Regenerated by tools/generate_fired_tracking_overrides.py.",
        "",
    ]

    for event_id, slug in sorted(entries.items(), key=lambda item: item[1]):
        name = fired_variable_name(slug)
        if event_id in fire_once_ids:
            lines.extend(
                [
                    f"{name} = {{",
                    "\tvalue = 0",
                    "\tif = {",
                    f"\t\tlimit = {{ has_fired_unique_event = {event_id} }}",
                    "\t\tvalue = 1",
                    "\t}",
                    "}",
                    "",
                ]
            )
        else:
            lines.append(f"{name} = 0")

    return "\n".join(lines).rstrip() + "\n"


def build_source_index(
    game_root: Path,
    *,
    skip_external_mods: bool,
    extra_mod_roots: list[Path],
) -> dict[tuple[str, str], list[Path]]:
    source_index: dict[tuple[str, str], list[Path]] = defaultdict(list)
    source_index[("game", "Base Game")].append(game_root / "game" / "in_game" / "events")

    if skip_external_mods:
        return source_index

    for source in registry_tools.discover_external_mod_sources(game_root, extra_mod_roots):
        if source.events_dir.is_dir():
            source_index[(source.kind, source.name)].append(source.events_dir)
    return source_index


def resolve_source_path(
    source_index: dict[tuple[str, str], list[Path]],
    *,
    source_kind: str,
    source_mod: str,
    source_file: str,
) -> Path | None:
    candidates = source_index.get((source_kind, source_mod), [])
    resolved: list[Path] = []
    for events_dir in candidates:
        candidate = events_dir / source_file
        if candidate.is_file():
            resolved.append(candidate)
    if not resolved:
        return None
    return resolved[-1]


def load_manifest(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    files = data.get("files", [])
    if not isinstance(files, list):
        return set()
    return {str(item) for item in files}


def write_manifest(manifest_path: Path, output_root: Path, outputs: dict[Path, str]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rel_files = sorted(output_path.relative_to(output_root).as_posix() for output_path in outputs)
    content = json.dumps({"files": rel_files}, indent=2) + "\n"
    manifest_path.write_text(content, encoding="utf-8", newline="\n")


def remove_stale_outputs(output_root: Path, stale_rel_paths: set[str]) -> int:
    removed = 0
    for rel_path in sorted(stale_rel_paths):
        target = output_root / rel_path
        if target.is_file():
            target.unlink()
            removed += 1

        parent = target.parent
        while parent != output_root and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return removed


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    registry_path = args.registry.resolve()
    output_file = args.output_file.resolve()
    legacy_output_root = LEGACY_OUTPUT_ROOT.resolve()
    manifest_path = args.manifest.resolve()

    if not registry_path.is_file():
        raise FileNotFoundError(f"Registry not found: {registry_path}")

    registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    tracked_by_file = collect_tracked_events(registry_data)
    source_index = build_source_index(
        game_root,
        skip_external_mods=args.skip_external_mods,
        extra_mod_roots=[path.resolve() for path in args.extra_mod_root],
    )

    unresolved_files: list[str] = []
    missing_events: list[str] = []
    fire_once_ids: set[str] = set()

    for (source_kind, source_mod, source_file), tracked_events in sorted(tracked_by_file.items()):
        source_path = resolve_source_path(
            source_index,
            source_kind=source_kind,
            source_mod=source_mod,
            source_file=source_file,
        )
        if source_path is None:
            unresolved_files.append(f"[{source_kind}] {source_mod}: {source_file}")
            continue

        raw = source_path.read_text(encoding="utf-8-sig", errors="replace")
        source_fire_once_ids, missing_ids = collect_fire_once_event_ids(raw, tracked_events)
        fire_once_ids.update(source_fire_once_ids)
        missing_events.extend(f"{source_file}: {event_id}" for event_id in missing_ids)

    previous_outputs = load_manifest(manifest_path)
    stale_outputs = previous_outputs

    if args.check:
        check_failed = False
        desired_content = build_fired_status_content(registry_data, fire_once_ids)
        current = output_file.read_text(encoding="utf-8-sig") if output_file.is_file() else ""
        if current != desired_content:
            print(f"Out of date: {output_file}")
            check_failed = True
        for rel_path in sorted(stale_outputs):
            print(f"Stale generated override: {legacy_output_root / rel_path}")
            check_failed = True
        return 1 if check_failed else 0

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        build_fired_status_content(registry_data, fire_once_ids),
        encoding="utf-8-sig",
        newline="\n",
    )

    removed = remove_stale_outputs(legacy_output_root, stale_outputs)
    write_manifest(manifest_path, legacy_output_root, {})

    total_entries = sum(len(file_events) for file_events in tracked_by_file.values())
    non_unique = total_entries - len(fire_once_ids)
    print(f"Wrote fired-status script values to {output_file.name}.")
    print(f"Trackable fire_only_once events: {len(fire_once_ids)}")
    if removed:
        print(f"Removed {removed} stale fired-tracking override files.")
    if unresolved_files:
        print(f"warning: skipped {len(unresolved_files)} source files that could not be resolved.")
        for item in unresolved_files[:20]:
            print(f"  - {item}")
    if missing_events:
        print(f"warning: {len(missing_events)} tracked events were not found inside their source files.")
        for item in missing_events[:20]:
            print(f"  - {item}")
    if non_unique > 0:
        print(f"Non-unique / repeatable tracked events exposed as constant 0: {non_unique}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
