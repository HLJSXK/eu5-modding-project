"""
EU5 Doc Updater — Knowledge Base Auto-Update Tool

Scans the project source files to detect patterns that might need to be
recorded as new violations or rules, then appends them to the Documented
Violations table in docs/guides/AI_Tool_Workflow_Prompt.md.

Usage:
    python update_knowledge.py [--src <path>] [--docs <path>] [--dry-run]

The tool:
  1. Reads the current Documented Violations table from the workflow guide.
  2. Scans src/ for TODO/FIXME comments that mention syntax issues.
  3. Scans git log for recent commits whose messages contain keywords like
     "wrong syntax", "fix modifier", "incorrect enum", etc.
  4. Prints any candidate new violations and (unless --dry-run) appends them.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns used to detect candidate violations in source comments
# ---------------------------------------------------------------------------

# Match lines like:  # TODO: wrong syntax — location_rank:village used
TODO_VIOLATION_RE = re.compile(
    r"#\s*(TODO|FIXME|HACK|NOTE).*?"
    r"(wrong.syntax|bad.pattern|invalid.enum|incorrect.modifier|"
    r"hallucin|guessed|ai.error|agent.error)",
    re.IGNORECASE,
)

# Git commit subject keywords that suggest a syntax correction
GIT_VIOLATION_KEYWORDS = re.compile(
    r"(fix.*syntax|fix.*modifier|wrong.*enum|"
    r"incorrect.*trigger|invalid.*effect|"
    r"revert.*ai|correct.*script)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Documented Violations table helpers
# ---------------------------------------------------------------------------

TABLE_HEADER = "| Date | Violation | Root cause | Correct behavior |"
TABLE_SEP    = "|---|---|---|---|"
TABLE_ROW_RE = re.compile(r"^\|\s*\d{4}-\d{2}")  # starts with | YYYY-MM


def _read_violations(guide_path: Path) -> list[str]:
    """Return existing table rows (data rows only, no header/separator)."""
    lines = guide_path.read_text(encoding="utf-8").splitlines()
    rows = []
    in_table = False
    for line in lines:
        if TABLE_HEADER in line:
            in_table = True
            continue
        if in_table and TABLE_SEP in line:
            continue
        if in_table:
            if TABLE_ROW_RE.match(line):
                rows.append(line)
            elif line.strip() and not line.startswith("|"):
                in_table = False
    return rows


def _append_violation(guide_path: Path, row: str) -> None:
    """Append one new table row after the last existing violation row."""
    content = guide_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    insert_at = None
    in_table = False
    for i, line in enumerate(lines):
        if TABLE_HEADER in line:
            in_table = True
        if in_table and TABLE_ROW_RE.match(line):
            insert_at = i
    if insert_at is None:
        print("[WARN] Could not locate Documented Violations table — appending at end.")
        lines.append(row + "\n")
    else:
        lines.insert(insert_at + 1, row + "\n")
    guide_path.write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Source scan
# ---------------------------------------------------------------------------

def scan_source_comments(src: Path) -> list[dict]:
    """Return list of candidate violation dicts from TODO/FIXME comments."""
    candidates = []
    for dirpath, _dirs, files in os.walk(src):
        for fname in files:
            if not fname.endswith((".txt", ".yml", ".gui", ".py")):
                continue
            fpath = Path(dirpath) / fname
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if TODO_VIOLATION_RE.search(line):
                    candidates.append({
                        "file": str(fpath.relative_to(src.parent)),
                        "line": lineno,
                        "comment": line.strip(),
                    })
    return candidates


# ---------------------------------------------------------------------------
# Git log scan
# ---------------------------------------------------------------------------

def scan_git_log(repo: Path, days: int = 30) -> list[dict]:
    """Return recent commits whose subject suggests a syntax fix."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-merges"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    commits = []
    for line in result.stdout.splitlines():
        if GIT_VIOLATION_KEYWORDS.search(line):
            parts = line.split(" ", 1)
            commits.append({
                "sha": parts[0] if parts else "",
                "subject": parts[1] if len(parts) > 1 else line,
            })
    return commits


# ---------------------------------------------------------------------------
# Interactive prompt
# ---------------------------------------------------------------------------

def _prompt_new_row(candidate: dict, source: str) -> str | None:
    """
    Ask the user whether this candidate should be added as a violation row.
    Returns the table row string, or None to skip.
    """
    print(f"\n{'─'*60}")
    print(f"[{source}] {candidate.get('file','')}"
          f":{candidate.get('line','')}")
    print(f"  → {candidate.get('comment', candidate.get('subject',''))}")
    answer = input("Add as violation? [y/N/skip-all] ").strip().lower()
    if answer == "skip-all":
        return "SKIP_ALL"
    if answer != "y":
        return None

    today = datetime.date.today().strftime("%Y-%m")
    violation   = input("  Violation description: ").strip()
    root_cause  = input("  Root cause: ").strip()
    correct     = input("  Correct behavior: ").strip()
    return f"| {today} | {violation} | {root_cause} | {correct} |"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="EU5 Doc Updater — scan for new violation patterns and "
                    "append them to the AI workflow guide."
    )
    parser.add_argument("--src",  default="src",  help="Source root to scan")
    parser.add_argument("--docs", default="docs", help="Docs root")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print candidates but do not write to any files",
    )
    parser.add_argument(
        "--git-days", type=int, default=30,
        help="How many days of git log to scan (default: 30)",
    )
    parser.add_argument(
        "--no-interactive", action="store_true",
        help="Non-interactive mode: only print candidates, skip prompts",
    )
    args = parser.parse_args()

    repo  = Path(".").resolve()
    src   = (repo / args.src).resolve()
    docs  = (repo / args.docs).resolve()
    guide = docs / "guides" / "AI_Tool_Workflow_Prompt.md"

    if not guide.exists():
        print(f"ERROR: workflow guide not found at {guide}", file=sys.stderr)
        return 1

    print(f"Scanning source: {src}")
    print(f"Guide file:      {guide}")

    # --- collect candidates ---
    candidates_src = scan_source_comments(src)
    candidates_git = scan_git_log(repo, days=args.git_days)

    if not candidates_src and not candidates_git:
        print("\nNo new violation candidates found.")
        return 0

    existing_rows = _read_violations(guide)

    print(f"\nFound {len(candidates_src)} source comment(s), "
          f"{len(candidates_git)} git commit(s) as candidates.\n")

    if args.no_interactive or args.dry_run:
        for c in candidates_src:
            print(f"  [src] {c['file']}:{c['line']} — {c['comment']}")
        for c in candidates_git:
            print(f"  [git] {c['sha']} — {c['subject']}")
        if args.dry_run:
            print("\n(dry-run: no files written)")
        return 0

    # --- interactive mode ---
    skip_all = False
    added = 0
    for candidate in candidates_src:
        if skip_all:
            break
        row = _prompt_new_row(candidate, "src")
        if row == "SKIP_ALL":
            skip_all = True
            break
        if row:
            _append_violation(guide, row)
            added += 1

    for candidate in candidates_git:
        if skip_all:
            break
        row = _prompt_new_row(candidate, "git")
        if row == "SKIP_ALL":
            break
        if row:
            _append_violation(guide, row)
            added += 1

    print(f"\nAdded {added} new violation row(s) to {guide}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
