#!/usr/bin/env python3
"""
Continuously filter the EU5 error.log file.

Default usage:
  python error_log_filter.py

Useful while testing:
  python error_log_filter.py --once

The source path, output path, polling interval, and vanilla-error filter file
are editable in error_log_filter_config.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "error_log_filter_config.json"
DEFAULT_SOURCE_LOG = (
    "C:/Users/Diwuji/Documents/Paradox Interactive/"
    "Europa Universalis V/logs/error.log"
)
DEFAULT_OUTPUT_LOG = "docs/error_log/error.log"
DEFAULT_VANILLA_FILTERS = "vanilla_error_filters.txt"
DEFAULT_INTERVAL_SECONDS = 1.0

TIMESTAMP_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]")
FILTER_MODES = {"contains", "exact", "regex"}


@dataclass(frozen=True)
class Settings:
    source_log: Path
    output_log: Path
    vanilla_filters: Path
    interval_seconds: float


@dataclass(frozen=True)
class FilterRule:
    mode: str
    value: str
    line_number: int
    regex: re.Pattern[str] | None = None


@dataclass(frozen=True)
class FilterStats:
    source_entries: int
    duplicate_entries_removed: int
    vanilla_entries_removed: int
    output_entries: int
    output_changed: bool


def resolve_path(value: str, base_dir: Path = REPO_ROOT) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return base_dir / path


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return loaded


def load_settings(args: argparse.Namespace) -> Settings:
    config_path = resolve_path(args.config)
    config = load_config(config_path)

    source_log = args.source_log or config.get("source_log") or DEFAULT_SOURCE_LOG
    output_log = args.output_log or config.get("output_log") or DEFAULT_OUTPUT_LOG
    vanilla_filters = (
        args.vanilla_filters
        or config.get("vanilla_filters")
        or DEFAULT_VANILLA_FILTERS
    )
    interval_seconds = (
        args.interval
        if args.interval is not None
        else config.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)
    )

    try:
        interval_seconds = float(interval_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("interval_seconds must be a number") from exc
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than 0")

    return Settings(
        source_log=resolve_path(str(source_log)),
        output_log=resolve_path(str(output_log)),
        vanilla_filters=resolve_path(str(vanilla_filters)),
        interval_seconds=interval_seconds,
    )


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return handle.read()


def write_text_if_changed(path: Path, content: str) -> bool:
    existing = None
    if path.exists():
        existing = read_text(path)
    if existing == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8", errors="replace", newline="") as handle:
        handle.write(content)
    temp_path.replace(path)
    return True


def split_log_entries(content: str) -> list[str]:
    entries: list[str] = []
    current: list[str] = []

    for line in content.splitlines(keepends=True):
        if TIMESTAMP_RE.match(line) and current:
            entries.append("".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        entries.append("".join(current))
    return entries


def entry_body_without_timestamp(entry: str) -> str:
    first_line_end = entry.find("\n")
    if first_line_end == -1:
        first_line = entry
        remainder = ""
    else:
        first_line = entry[: first_line_end + 1]
        remainder = entry[first_line_end + 1 :]
    return TIMESTAMP_RE.sub("", first_line, count=1) + remainder


def match_key(entry: str) -> str:
    return entry_body_without_timestamp(entry).rstrip()


def escape_filter_value(value: str) -> str:
    return value.replace("\t", r"\t").replace("\n", r"\n")


def unescape_filter_value(value: str) -> str:
    return value.replace(r"\n", "\n").replace(r"\t", "\t")


def filter_mode_from_line(line: str) -> str | None:
    if ":" not in line:
        return None
    prefix, _ = line.split(":", 1)
    if prefix in FILTER_MODES:
        return prefix
    return None


def should_stop_timestamp_filter_block(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or TIMESTAMP_RE.match(line) is not None
        or stripped.startswith("#")
        or filter_mode_from_line(stripped) is not None
    )


def canonicalize_filter_content(content: str) -> tuple[str, bool]:
    lines = content.splitlines(keepends=True)
    canonical_lines: list[str] = []
    changed = False
    index = 0

    while index < len(lines):
        line = lines[index]
        if TIMESTAMP_RE.match(line):
            entry_lines = [line]
            index += 1
            while index < len(lines) and not should_stop_timestamp_filter_block(
                lines[index]
            ):
                entry_lines.append(lines[index])
                index += 1

            exact_value = escape_filter_value(match_key("".join(entry_lines)))
            canonical_lines.append(f"exact:{exact_value}\n")
            changed = True
            continue

        canonical_lines.append(line)
        index += 1

    return "".join(canonical_lines), changed


def canonicalize_filter_file(path: Path) -> None:
    if not path.exists():
        return
    content = read_text(path)
    canonical_content, changed = canonicalize_filter_content(content)
    if changed:
        write_text_if_changed(path, canonical_content)


def load_filter_rules(path: Path) -> list[FilterRule]:
    if not path.exists():
        return []

    canonicalize_filter_file(path)

    rules: list[FilterRule] = []
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            mode = "contains"
            value = line
            if filter_mode_from_line(line):
                mode, value = line.split(":", 1)
                value = value.strip()

            value = unescape_filter_value(value)
            regex = None
            if mode == "regex":
                try:
                    regex = re.compile(value, re.MULTILINE | re.DOTALL)
                except re.error as exc:
                    raise ValueError(
                        f"Invalid regex in {path}:{line_number}: {exc}"
                    ) from exc

            rules.append(
                FilterRule(mode=mode, value=value, line_number=line_number, regex=regex)
            )
    return rules


def is_vanilla_filtered(entry_key: str, rules: list[FilterRule]) -> bool:
    for rule in rules:
        if rule.mode == "contains" and rule.value in entry_key:
            return True
        if rule.mode == "exact" and rule.value.rstrip() == entry_key:
            return True
        if rule.mode == "regex" and rule.regex and rule.regex.search(entry_key):
            return True
    return False


def filter_entries(entries: list[str], rules: list[FilterRule]) -> tuple[list[str], int, int]:
    seen: set[str] = set()
    kept: list[str] = []
    duplicate_entries_removed = 0
    vanilla_entries_removed = 0

    for entry in entries:
        key = match_key(entry)
        if key in seen:
            duplicate_entries_removed += 1
            continue
        seen.add(key)

        if is_vanilla_filtered(key, rules):
            vanilla_entries_removed += 1
            continue

        kept.append(entry)

    return kept, duplicate_entries_removed, vanilla_entries_removed


def run_once(settings: Settings) -> FilterStats | None:
    if not settings.source_log.exists():
        print(f"[WARN] Source log not found: {settings.source_log}")
        return None

    source = read_text(settings.source_log)
    rules = load_filter_rules(settings.vanilla_filters)
    entries = split_log_entries(source)
    kept_entries, duplicate_entries_removed, vanilla_entries_removed = filter_entries(
        entries,
        rules,
    )
    output_changed = write_text_if_changed(settings.output_log, "".join(kept_entries))

    return FilterStats(
        source_entries=len(entries),
        duplicate_entries_removed=duplicate_entries_removed,
        vanilla_entries_removed=vanilla_entries_removed,
        output_entries=len(kept_entries),
        output_changed=output_changed,
    )


def format_stats(stats: FilterStats) -> str:
    changed = "updated" if stats.output_changed else "unchanged"
    return (
        f"entries={stats.source_entries}, "
        f"duplicates_removed={stats.duplicate_entries_removed}, "
        f"vanilla_removed={stats.vanilla_entries_removed}, "
        f"output_entries={stats.output_entries}, "
        f"output={changed}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Continuously filter EU5 error.log entries.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to JSON config file.",
    )
    parser.add_argument("--source-log", help="Override the source error.log path.")
    parser.add_argument("--output-log", help="Override the filtered output log path.")
    parser.add_argument(
        "--vanilla-filters",
        help="Override the human-maintained vanilla filter file path.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        help="Override polling interval in seconds.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one filtering pass and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.once:
        settings = load_settings(args)
        stats = run_once(settings)
        if stats is not None:
            print(format_stats(stats))
        return 0

    print("Starting error.log filter. Press Ctrl+C to stop.")
    print(f"Config: {resolve_path(args.config)}")

    last_report = ""
    sleep_interval = DEFAULT_INTERVAL_SECONDS
    try:
        while True:
            try:
                settings = load_settings(args)
                sleep_interval = settings.interval_seconds
                stats = run_once(settings)
                if stats is not None:
                    report = format_stats(stats)
                    if report != last_report or stats.output_changed:
                        print(report)
                        last_report = report
            except Exception as exc:  # noqa: BLE001 - keep watcher alive on bad config.
                print(f"[ERROR] {exc}")
            time.sleep(max(sleep_interval, 0.001))
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
