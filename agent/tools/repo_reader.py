"""Low-level file access tools for reading the EU5 repository."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def read_file(path: str) -> str:
    resolved = _resolve(path)
    with open(resolved, "r", encoding="utf-8-sig") as f:
        return f.read()


def read_file_lines(path: str, max_lines: int = 500) -> str:
    resolved = _resolve(path)
    lines = []
    with open(resolved, "r", encoding="utf-8-sig") as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                lines.append(f"... (truncated at {max_lines} lines)")
                break
            lines.append(line.rstrip())
    return "\n".join(lines)


def grep_file(path: str, pattern: str, context_lines: int = 2) -> list[str]:
    """Return lines matching pattern, with optional surrounding context."""
    resolved = _resolve(path)
    try:
        with open(resolved, "r", encoding="utf-8-sig") as f:
            all_lines = f.readlines()
    except FileNotFoundError:
        return []

    compiled = re.compile(pattern, re.IGNORECASE)
    results = []
    for i, line in enumerate(all_lines):
        if compiled.search(line):
            start = max(0, i - context_lines)
            end = min(len(all_lines), i + context_lines + 1)
            snippet = "".join(all_lines[start:end]).rstrip()
            results.append(f"[line {i + 1}]\n{snippet}")
    return results


def modifier_exists(modifier_name: str) -> bool:
    """Check whether a modifier name appears in the EU5 modifier definitions."""
    defs_path = REPO_ROOT / "reference_game_files/game/main_menu/common/modifier_type_definitions/00_modifier_types.txt"
    if not defs_path.exists():
        return True  # can't check; don't block
    pattern = rf"^{re.escape(modifier_name)}\s*=\s*\{{"
    with open(defs_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            if re.match(pattern, line):
                return True
    return False


def list_dir(path: str) -> list[str]:
    resolved = _resolve(path)
    if not resolved.exists():
        return []
    return [str(p.relative_to(REPO_ROOT)) for p in sorted(resolved.iterdir())]
