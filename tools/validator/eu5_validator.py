"""
EU5 Validator — Static Script Analysis Tool

Checks EU5 mod source files without loading the game.

Usage:
    python eu5_validator.py [--src <path>] [--json] [--strict]

Exit codes:
    0  — no errors (warnings may still exist)
    1  — one or more errors found

The validator checks:

    .yml files
        • UTF-8-BOM encoding required by the PDX localisation parser
        • Non-ASCII "smart quote" characters that break YAML parsing
        • Header line must match the declared language (e.g. l_english:)

    .txt script files
        • Known-bad patterns (location_rank:village, mean_time_to_happen, …)
        • auto_modifier block: only whitelisted top-level keys permitted
        • Unmatched curly braces (basic structural check)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from known_patterns import (
    AUTO_MODIFIER_KNOWN_KEYS,
    BAD_PATTERNS,
    FORBIDDEN_YAML_QUOTE_CHARS,
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warning"


@dataclass
class Finding:
    severity: str   # "error" | "warning"
    file: str
    line: int       # 1-based; 0 = file-level
    message: str

    def __str__(self) -> str:
        loc = f"{self.file}:{self.line}" if self.line else self.file
        tag = self.severity.upper()
        return f"[{tag}] {loc} — {self.message}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity: str, filepath: str, line: int, message: str) -> None:
        self.findings.append(Finding(severity, filepath, line, message))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARN]

    def to_dict(self) -> dict:
        return {
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "total": len(self.findings),
            },
            "findings": [
                {
                    "severity": f.severity,
                    "file": f.file,
                    "line": f.line,
                    "message": f.message,
                }
                for f in self.findings
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTF8_BOM = b"\xef\xbb\xbf"

LANG_HEADER_RE = re.compile(r"^l_[a-z0-9_]+\s*:\s*$")

# Regex to split a .txt file into top-level blocks:
#   <identifier> = { ... }
# We only extract the block name; inner parsing is done separately.
BLOCK_NAME_RE = re.compile(r"^(\w+)\s*=\s*\{", re.MULTILINE)

# auto_modifier key on its own line:  key = value  OR  key = { … }
MODIFIER_KEY_RE = re.compile(r"^\s+(\w+)\s*=")


def _relative(filepath: str, root: Path) -> str:
    try:
        return str(Path(filepath).relative_to(root))
    except ValueError:
        return filepath


def _iter_files(src: Path, extensions: tuple[str, ...]) -> Iterable[Path]:
    for dirpath, _dirs, files in os.walk(src):
        for fname in files:
            if fname.endswith(extensions):
                yield Path(dirpath) / fname


# ---------------------------------------------------------------------------
# Localisation (.yml) checks
# ---------------------------------------------------------------------------

def check_yml_file(filepath: Path, report: Report, rel: str) -> None:
    # --- encoding check (must be UTF-8-BOM) ---
    raw = filepath.read_bytes()
    if not raw.startswith(UTF8_BOM):
        report.add(SEVERITY_ERROR, rel, 0,
                   "File must be UTF-8-BOM encoded (missing BOM). "
                   "Save with 'UTF-8 with BOM' in your editor.")
        return   # remaining checks need decoded text

    text = raw[3:].decode("utf-8", errors="replace")
    lines = text.splitlines()

    # --- header line check ---
    if lines and not LANG_HEADER_RE.match(lines[0].strip()):
        report.add(SEVERITY_WARN, rel, 1,
                   f"First line should be a language header like 'l_english:' "
                   f"but got: {lines[0][:80]!r}")

    # --- smart-quote check ---
    for lineno, line in enumerate(lines, start=1):
        for ch in FORBIDDEN_YAML_QUOTE_CHARS:
            if ch in line:
                col = line.index(ch) + 1
                report.add(SEVERITY_ERROR, rel, lineno,
                            f"Forbidden non-ASCII quote character U+{ord(ch):04X} "
                            f"({ch!r}) at column {col}. "
                            "PDX YAML parser only accepts ASCII double-quotes.")


# ---------------------------------------------------------------------------
# Script (.txt) checks
# ---------------------------------------------------------------------------

def check_txt_file(filepath: Path, report: Report, rel: str) -> None:
    raw = filepath.read_bytes()
    # Strip BOM if present (some .txt files have it)
    if raw.startswith(UTF8_BOM):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        report.add(SEVERITY_WARN, rel, 0,
                   "File is not valid UTF-8; skipping content checks.")
        return

    lines = text.splitlines()

    # --- known-bad pattern scan ---
    for desc, pattern in BAD_PATTERNS:
        for lineno, line in enumerate(lines, start=1):
            # Skip comment lines
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if pattern.search(line):
                report.add(SEVERITY_ERROR, rel, lineno, desc)

    # --- auto_modifier block key validation ---
    _check_auto_modifier_keys(text, lines, filepath, report, rel)

    # --- unmatched brace check ---
    _check_brace_balance(lines, report, rel)


def _check_auto_modifier_keys(
    text: str,
    lines: list[str],
    filepath: Path,
    report: Report,
    rel: str,
) -> None:
    """
    Validate top-level keys inside every auto_modifier block.

    auto_modifier files live under common/auto_modifiers/.
    We only run this check for files in that directory to avoid false
    positives in other script files that use the same key names.
    """
    if "auto_modifiers" not in filepath.parts:
        return

    # Walk through lines, track brace depth to extract top-level block bodies.
    in_block = False
    depth = 0
    block_start_line = 0

    for lineno, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        if not in_block:
            # Look for a new top-level block definition
            if re.match(r"^\w+\s*=\s*\{", stripped):
                in_block = True
                depth = 1
                block_start_line = lineno
            continue

        # Inside a block
        opens  = line.count("{")
        closes = line.count("}")
        depth += opens - closes

        if depth <= 0:
            in_block = False
            depth = 0
            continue

        # At depth == 1 we are at the top level inside the block
        if depth == 1:
            m = MODIFIER_KEY_RE.match(line)
            if m:
                key = m.group(1)
                if key not in AUTO_MODIFIER_KNOWN_KEYS:
                    # Treat unknown keys as possible modifier names — warn, not error,
                    # because the full modifier name list is large and version-dependent.
                    report.add(
                        SEVERITY_WARN,
                        rel,
                        lineno,
                        f"auto_modifier key '{key}' is not a known structural key "
                        f"(category/type/icon/requires_real/potential_trigger/"
                        f"scales_with/limit/hide_effects/alert). "
                        f"If this is a modifier effect (e.g. tax_income_efficiency), "
                        f"verify its exact name in reference_official_defines/.",
                    )


def _check_brace_balance(lines: list[str], report: Report, rel: str) -> None:
    depth = 0
    for lineno, line in enumerate(lines, start=1):
        # Ignore comment portions
        code = line.split("#")[0]
        depth += code.count("{") - code.count("}")
    if depth != 0:
        report.add(
            SEVERITY_ERROR,
            rel,
            0,
            f"Unbalanced curly braces: net depth after full file = {depth:+d}. "
            "Check for unclosed or extra-closed blocks.",
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_validation(src: Path) -> Report:
    report = Report()
    root = src

    for filepath in _iter_files(src, (".yml",)):
        rel = _relative(str(filepath), root)
        check_yml_file(filepath, report, rel)

    for filepath in _iter_files(src, (".txt",)):
        rel = _relative(str(filepath), root)
        check_txt_file(filepath, report, rel)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EU5 Mod Static Validator — check script and localisation files "
                    "without loading the game.",
    )
    parser.add_argument(
        "--src",
        default="src",
        help="Root directory to scan (default: src)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit JSON report to stdout instead of human-readable text",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 1 if any warnings found)",
    )
    args = parser.parse_args()

    src_path = Path(args.src).resolve()
    if not src_path.is_dir():
        print(f"ERROR: source directory not found: {src_path}", file=sys.stderr)
        return 1

    report = run_validation(src_path)

    if args.json_output:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        for finding in report.findings:
            print(finding)

        n_err  = len(report.errors)
        n_warn = len(report.warnings)
        print(
            f"\n{'='*60}\n"
            f"Validation complete: {n_err} error(s), {n_warn} warning(s)\n"
            f"Source root: {src_path}\n"
            f"{'='*60}"
        )

    failed = len(report.errors) > 0 or (args.strict and len(report.warnings) > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
