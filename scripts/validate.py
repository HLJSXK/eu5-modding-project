#!/usr/bin/env python3
"""
EU5 Mod Static Validator
Catches common errors before game loading. Reads docs/knowledge/*.yaml for patterns.

Usage:
  python scripts/validate.py                   # validate entire src/
  python scripts/validate.py src/stable/       # validate one directory
  python scripts/validate.py --changed         # validate only git-changed files
"""

import re
import sys
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
KNOWLEDGE_DIR = REPO_ROOT / "docs" / "knowledge"
MODIFIER_TYPES_FILE = (
    REPO_ROOT
    / "reference_game_files"
    / "game"
    / "main_menu"
    / "common"
    / "modifier_type_definitions"
    / "00_modifier_types.txt"
)
UTF8_BOM = b"\xef\xbb\xbf"

issues = []


def load_yaml(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_modifier_whitelist() -> set[str]:
    if not MODIFIER_TYPES_FILE.exists():
        return set()
    whitelist = set()
    pattern = re.compile(r"^(\w+)\s*=\s*\{")
    with MODIFIER_TYPES_FILE.open(encoding="utf-8-sig") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                whitelist.add(m.group(1))
    return whitelist


def get_changed_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    names = set()
    for r in [result, staged, untracked]:
        for name in r.stdout.splitlines():
            names.add(name.strip())
    paths = []
    for name in names:
        p = REPO_ROOT / name
        if p.exists() and p.suffix in {".txt", ".gui", ".yml"}:
            paths.append(p)
    return paths


def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return [
        p
        for p in target.rglob("*")
        if p.suffix in {".txt", ".gui", ".yml"} and p.is_file()
    ]


def check_bom(path: Path):
    with path.open("rb") as f:
        header = f.read(3)
    if header != UTF8_BOM:
        issues.append(f"[ENCODING] Missing UTF-8 BOM: {path.relative_to(REPO_ROOT)}")


def check_anti_patterns(path: Path, content: str, patterns: list[dict]):
    path_str = str(path).replace("\\", "/")
    for entry in patterns:
        regex = entry.get("pattern", "")
        if not regex:
            continue
        # Restrict to specific path substrings if specified
        only_in = entry.get("only_in_paths", [])
        if only_in and not any(sub in path_str for sub in only_in):
            continue
        try:
            for m in re.finditer(regex, content, re.MULTILINE | re.IGNORECASE):
                line_num = content[: m.start()].count("\n") + 1
                issues.append(
                    f"[{entry.get('category', 'pattern').upper()}] "
                    f"{path.relative_to(REPO_ROOT)}:{line_num} — "
                    f"Bad: \"{entry['bad']}\" → {entry['correction']}"
                )
        except re.error:
            pass


def check_enums(path: Path, content: str, enums: dict):
    for enum_name, enum_data in enums.items():
        valid_values = set(enum_data.get("values", []))
        pattern = re.compile(
            rf"{re.escape(enum_name)}\s*\??\s*=\s*{re.escape(enum_name)}:(\w+)"
        )
        for m in pattern.finditer(content):
            val = m.group(1)
            if val not in valid_values:
                line_num = content[: m.start()].count("\n") + 1
                issues.append(
                    f"[ENUM] {path.relative_to(REPO_ROOT)}:{line_num} — "
                    f"Invalid {enum_name}:{val}. Valid: {', '.join(sorted(valid_values))}"
                )


def check_modifier_names(path: Path, content: str, whitelist: set[str]):
    if not whitelist:
        return
    # Only check .txt files in common/auto_modifiers and common/static_modifiers
    rel = str(path.relative_to(REPO_ROOT))
    if "auto_modifiers" not in rel and "static_modifiers" not in rel:
        return
    # Find bare modifier name = value lines (not comments, not known structural keys)
    structural = {
        "category", "type", "icon", "requires_real", "potential_trigger",
        "scales_with", "limit", "hide_effects", "alert", "boolean", "percent",
        "already_percent", "decimals", "game_data", "min", "max",
        "cap_zero_to_one", "scale_with_pop", "format", "ai", "bias_type",
        "should_show_in_modifiers_tab", "color",
    }
    line_pattern = re.compile(r"^\s*(\w+)\s*=\s*[-\d.]+")
    for i, line in enumerate(content.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        m = line_pattern.match(line)
        if m:
            name = m.group(1)
            if name not in structural and name not in whitelist:
                issues.append(
                    f"[MODIFIER] {path.relative_to(REPO_ROOT)}:{i} — "
                    f"Unknown modifier name '{name}'; verify in 00_modifier_types.txt"
                )


def main():
    anti_patterns = load_yaml(KNOWLEDGE_DIR / "anti_patterns.yaml") or []
    enum_data = load_yaml(KNOWLEDGE_DIR / "valid_enums.yaml") or {}
    modifier_whitelist = load_modifier_whitelist()

    use_changed = "--changed" in sys.argv
    targets = [a for a in sys.argv[1:] if not a.startswith("-")]

    if use_changed:
        files = get_changed_files()
        if not files:
            print("[OK] No changed mod files to validate.")
            sys.exit(0)
    elif targets:
        files = []
        for t in targets:
            files.extend(collect_files(REPO_ROOT / t))
    else:
        files = collect_files(REPO_ROOT / "src")

    if not files:
        print("[OK] No files found to validate.")
        sys.exit(0)

    for path in files:
        # BOM check for .yml and .txt (commented it is done in build.bat)
        # if path.suffix in {".yml", ".txt"}:
        #     check_bom(path)

        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            issues.append(f"[ENCODING] Cannot decode as UTF-8: {path.relative_to(REPO_ROOT)}")
            continue

        # Skip the knowledge files themselves
        if KNOWLEDGE_DIR in path.parents:
            continue

        check_anti_patterns(path, content, anti_patterns)
        check_enums(path, content, enum_data)
        check_modifier_names(path, content, modifier_whitelist)

    if issues:
        print(f"[FAIL] {len(issues)} issue(s) found:\n")
        for issue in issues:
            print(f"  {issue}")
        sys.exit(1)
    else:
        print(f"[OK] Validated {len(files)} file(s) — no issues found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
