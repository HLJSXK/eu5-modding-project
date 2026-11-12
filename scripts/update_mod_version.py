#!/usr/bin/env python3
"""Set SOL metadata, migration marker and notification versions from one date.

Versions use YYMMDD. By default the local system date and all deploy targets
are used; --date makes release builds reproducible.
"""

import argparse
from datetime import date, datetime
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_NAMES = (
    "stable",
    "sol_standalone",
    "sol_pp_compatibility_submod",
    "sol_mnt_compatibility_submod",
    "sol_jtg_compatibility_submod",
)
VERSION_LINE = re.compile(
    r'^(?P<prefix>[ \t]*"version"[ \t]*:[ \t]*)"[^"]*"'
    r'(?P<suffix>[ \t]*,?[ \t]*)$',
    re.MULTILINE,
)
MIGRATION_ACTION_PATH = Path("src/stable/in_game/common/on_action/SOL_migration_on_actions.txt")
MIGRATION_MARKER = re.compile(r"\bSOL_migration_(?:v\d+|\d{6})_seen\b")
MIGRATION_LANGUAGES = ("english", "simp_chinese")
MIGRATION_DESCRIPTION_VERSION = re.compile(
    r'^(?P<prefix>[ \t]*sol_migration\.1\.desc:[ \t]*(?:\d+[ \t]*)?"[^"\r\n]*?\bv)'
    r'(?P<version>\d+(?:\.\d+)*)',
    re.MULTILINE,
)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid date {value!r}; expected YYYY-MM-DD"
        ) from exc


def _resolve_targets(target: str) -> list[str]:
    if target == "all":
        return list(TARGET_NAMES)
    return [target]


def _set_metadata_version(path: Path, version: str, check: bool) -> bool:
    original = path.read_text(encoding="utf-8")
    try:
        metadata = json.loads(original)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.relative_to(REPO_ROOT)}: {exc}") from exc

    current = metadata.get("version")
    if not isinstance(current, str):
        raise ValueError(
            f"missing string version in {path.relative_to(REPO_ROOT)}"
        )

    if current == version:
        print(f"[OK] {path.relative_to(REPO_ROOT)}: {version}")
        return False

    if check:
        print(
            f"[FAIL] {path.relative_to(REPO_ROOT)}: "
            f"found {current!r}, expected {version!r}"
        )
        return True

    updated, replacements = VERSION_LINE.subn(
        lambda match: (
            f'{match.group("prefix")}"{version}"{match.group("suffix")}'
        ),
        original,
        count=1,
    )
    if replacements != 1:
        raise ValueError(
            f"could not locate top-level version in {path.relative_to(REPO_ROOT)}"
        )

    parsed = json.loads(updated)
    if parsed.get("version") != version:
        raise ValueError(
            f"version replacement did not update the top-level field in "
            f"{path.relative_to(REPO_ROOT)}"
        )

    path.write_text(updated, encoding="utf-8")
    print(f"[UPDATED] {path.relative_to(REPO_ROOT)}: {current} -> {version}")
    return False


def _set_migration_marker(path: Path, version: str, check: bool) -> bool:
    raw = path.read_bytes()
    original = raw.decode("utf-8-sig")
    markers = set(MIGRATION_MARKER.findall(original))
    if len(markers) != 1:
        raise ValueError(
            f"expected one consistent migration marker in {path.relative_to(REPO_ROOT)}, "
            f"found {sorted(markers)}"
        )
    current = markers.pop()
    expected = f"SOL_migration_{version}_seen"
    if current == expected:
        print(f"[OK] {path.relative_to(REPO_ROOT)}: {expected}")
        return False
    if check:
        print(f"[FAIL] {path.relative_to(REPO_ROOT)}: found {current!r}, expected {expected!r}")
        return True
    updated = MIGRATION_MARKER.sub(expected, original)
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    path.write_bytes(bom + updated.encode("utf-8"))
    print(f"[UPDATED] {path.relative_to(REPO_ROOT)}: {current} -> {expected}")
    return False


def _set_notification_version(path: Path, version: str, check: bool) -> bool:
    # Byte IO preserves BOM, line endings and all unrelated translated text.
    raw = path.read_bytes()
    original = raw.decode("utf-8-sig")
    matches = list(MIGRATION_DESCRIPTION_VERSION.finditer(original))
    if len(matches) != 1:
        raise ValueError(f"expected one notification version in {path.relative_to(REPO_ROOT)}")
    current = matches[0].group("version")
    if current == version and raw.startswith(b"\xef\xbb\xbf"):
        print(f"[OK] {path.relative_to(REPO_ROOT)}: v{version}")
        return False
    if check:
        print(f"[FAIL] {path.relative_to(REPO_ROOT)}: expected v{version} and UTF-8 BOM")
        return True
    updated = MIGRATION_DESCRIPTION_VERSION.sub(
        lambda match: match.group("prefix") + version, original
    )
    path.write_bytes(b"\xef\xbb\xbf" + updated.encode("utf-8"))
    print(f"[UPDATED] {path.relative_to(REPO_ROOT)}: v{current} -> v{version}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update SOL metadata, migration marker and notification using YYMMDD."
    )
    parser.add_argument(
        "--target",
        choices=[*TARGET_NAMES, "all"],
        default="all",
        help="Metadata target to update (default: all).",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=None,
        help="Release date in YYYY-MM-DD form (default: local system date).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check metadata, migration marker and notification versions without writing changes.",
    )
    args = parser.parse_args()

    release_date = args.date or date.today()
    version = release_date.strftime("%y%m%d")
    failed = False

    for target in _resolve_targets(args.target):
        path = REPO_ROOT / "src" / target / ".metadata" / "metadata.json"
        if not path.is_file():
            raise SystemExit(f"[ERROR] Metadata file not found: {path}")
        try:
            failed = _set_metadata_version(path, version, args.check) or failed
            if target == "stable":
                failed = _set_migration_marker(REPO_ROOT / MIGRATION_ACTION_PATH, version, args.check) or failed
                for language in MIGRATION_LANGUAGES:
                    notification = REPO_ROOT / "src/stable/main_menu/localization" / language / f"SOL_migration_events_l_{language}.yml"
                    failed = _set_notification_version(notification, version, args.check) or failed
        except ValueError as exc:
            raise SystemExit(f"[ERROR] {exc}") from exc

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
