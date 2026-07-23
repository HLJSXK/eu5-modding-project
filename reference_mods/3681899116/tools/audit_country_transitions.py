#!/usr/bin/env python3
"""Audit country-transition coverage for the generated event windows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from country_runtime_aliases import group_runtime_keys
from generate_country_events_gui import DEFAULT_WINDOWS_DIR, WINDOW_FILE_PREFIX
from generate_registry import DEFAULT_REGISTRY, load_country_transition_targets


SCRIPT_PATH = Path(__file__).resolve()
MOD_ROOT = SCRIPT_PATH.parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that all scripted country transitions resolve to generated event windows."
    )
    parser.add_argument(
        "--game-root",
        type=Path,
        default=Path.cwd(),
        help="Game root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"Registry JSON path. Default: {DEFAULT_REGISTRY}",
    )
    parser.add_argument(
        "--windows-dir",
        type=Path,
        default=DEFAULT_WINDOWS_DIR,
        help=f"Generated country window directory. Default: {DEFAULT_WINDOWS_DIR}",
    )
    return parser.parse_args()


def load_registry_groups(registry_path: Path) -> list[dict[str, object]]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    groups = payload.get("groups", [])
    if not isinstance(groups, list):
        raise ValueError("Registry JSON must contain a top-level 'groups' list.")
    return groups


def collect_generated_window_keys(windows_dir: Path) -> set[str]:
    keys: set[str] = set()
    for path in windows_dir.glob(f"{WINDOW_FILE_PREFIX}*.gui"):
        stem = path.stem
        if not stem.startswith(WINDOW_FILE_PREFIX):
            continue
        keys.add(stem[len(WINDOW_FILE_PREFIX):])
    return keys


def print_set(label: str, values: set[str] | list[str]) -> None:
    items = sorted(values)
    print(f"{label}: {len(items)}")
    if items:
        print(f"{label}_items: {items}")


def main() -> int:
    args = parse_args()
    groups = load_registry_groups(args.registry)
    canonical_tags = {str(tag) for group in groups for tag in group.get("country_tags", [])}

    runtime_keys: set[str] = set()
    for group in groups:
        runtime_keys.update(group_runtime_keys(group, canonical_tags))

    generated_window_keys = collect_generated_window_keys(args.windows_dir)
    transition_targets = load_country_transition_targets(args.game_root)

    formable_targets = transition_targets["formable_targets"]
    scripted_formable_targets = transition_targets["scripted_formable_targets"]
    direct_tag_targets = transition_targets["direct_tag_targets"]
    cosmetic_tag_targets = transition_targets["cosmetic_tag_targets"]
    unresolved_formable_refs = transition_targets["unresolved_formable_refs"]

    formable_targets_without_native_dhe = formable_targets - canonical_tags
    scripted_formable_targets_without_native_dhe = scripted_formable_targets - canonical_tags
    direct_tag_targets_without_native_dhe = direct_tag_targets - canonical_tags
    missing_cosmetic_runtime = cosmetic_tag_targets - runtime_keys
    expected_window_targets = (
        (formable_targets & canonical_tags)
        | (scripted_formable_targets & canonical_tags)
        | (direct_tag_targets & canonical_tags)
        | cosmetic_tag_targets
    )
    missing_transition_windows = expected_window_targets - generated_window_keys

    print(f"registry_groups: {len(groups)}")
    print(f"registry_runtime_keys: {len(runtime_keys)}")
    print(f"generated_windows: {len(generated_window_keys)}")
    print_set("formable_targets", formable_targets)
    print_set("scripted_formable_targets", scripted_formable_targets)
    print_set("direct_tag_targets", direct_tag_targets)
    print_set("cosmetic_tag_targets", cosmetic_tag_targets)
    print_set("formable_targets_without_native_dhe", formable_targets_without_native_dhe)
    print_set(
        "scripted_formable_targets_without_native_dhe",
        scripted_formable_targets_without_native_dhe,
    )
    print_set("direct_tag_targets_without_native_dhe", direct_tag_targets_without_native_dhe)
    print_set("missing_cosmetic_runtime", missing_cosmetic_runtime)
    print_set("missing_transition_windows", missing_transition_windows)
    print_set("unresolved_formable_refs", unresolved_formable_refs)

    failed = any(
        (
            missing_cosmetic_runtime,
            missing_transition_windows,
            unresolved_formable_refs,
        )
    )
    if failed:
        return 1

    print("transition_audit: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
