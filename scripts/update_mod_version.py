#!/usr/bin/env python3
"""Set active SOL metadata versions from a calendar date.

Versions use YYMMDD. By default the local system date and all deploy targets
are used; --date makes release builds reproducible.
"""

import argparse
from datetime import date, datetime
import json
import re
import sys
from pathlib import Path


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update SOL metadata versions using the YYMMDD release format."
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
        help="Check metadata without writing changes.",
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
        except ValueError as exc:
            raise SystemExit(f"[ERROR] {exc}") from exc

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
