#!/usr/bin/env python3
"""
Build fast-lookup symbol indexes for AI coding sessions.

Scans reference and source files and writes flat text indexes to data/index/:
  icons.txt            — all @icon_name! entries from font_icons.gui
  scripted_triggers.txt — all scripted_trigger names (vanilla + mod)
  scripted_effects.txt  — all scripted_effect names (vanilla + mod)
  static_modifiers.txt  — all modifier names from 00_modifier_types.txt
  loc_keys_en.txt       — all English localization keys in src/

Usage:
  conda run -n eu5 python scripts/gen_index.py
  conda run -n eu5 python scripts/gen_index.py --verbose

Called automatically by gen_brief.py before generating BRIEF.md.
"""

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "data" / "index"

FONT_ICONS_FILE = (
    REPO_ROOT / "reference_game_files" / "game" / "main_menu" / "gui" / "shared" / "font_icons.gui"
)
MODIFIER_TYPES_FILE = (
    REPO_ROOT / "reference_game_files" / "game" / "main_menu" / "common"
    / "modifier_type_definitions" / "00_modifier_types.txt"
)
VANILLA_TRIGGERS_DIR = REPO_ROOT / "reference_game_files" / "game" / "in_game" / "common" / "scripted_triggers"
VANILLA_EFFECTS_DIR  = REPO_ROOT / "reference_game_files" / "game" / "in_game" / "common" / "scripted_effects"
MOD_TRIGGERS_DIRS = [
    REPO_ROOT / "src" / "stable" / "in_game" / "common" / "scripted_triggers",
    REPO_ROOT / "src" / "develop" / "in_game" / "common" / "scripted_triggers",
]
MOD_EFFECTS_DIRS = [
    REPO_ROOT / "src" / "stable" / "in_game" / "common" / "scripted_effects",
    REPO_ROOT / "src" / "develop" / "in_game" / "common" / "scripted_effects",
]
LOC_EN_DIRS = [
    REPO_ROOT / "src" / "stable" / "main_menu" / "localization" / "english",
    REPO_ROOT / "src" / "develop" / "main_menu" / "localization" / "english",
]


def _write_index(path: Path, entries: list[str], verbose: bool, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sorted(set(entries))) + "\n", encoding="utf-8")
    if verbose:
        print(f"[index] {path.relative_to(REPO_ROOT)}: {len(set(entries))} entries")


def build_icons_index(verbose: bool) -> None:
    """Extract all @icon_name! names from font_icons.gui."""
    if not FONT_ICONS_FILE.exists():
        print(f"[WARN] font_icons.gui not found: {FONT_ICONS_FILE}")
        return
    text = FONT_ICONS_FILE.read_text(encoding="utf-8-sig")
    # texticon blocks use `icon = <name>` at depth 1
    icon_pat = re.compile(r"^\s+icon\s*=\s*(\w+)", re.MULTILINE)
    names = [f"@{m.group(1)}!" for m in icon_pat.finditer(text)]
    _write_index(INDEX_DIR / "icons.txt", names, verbose, "GUI icons")


def _extract_top_level_names(txt_files: list[Path]) -> list[str]:
    """Extract top-level `name = {` block definitions from a list of .txt files."""
    names = []
    # Top-level block: starts at column 0, word chars, `=`, `{`; not a comment
    top_pat = re.compile(r"^([a-zA-Z_]\w*)\s*=\s*\{", re.MULTILINE)
    for path in txt_files:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for m in top_pat.finditer(text):
            # Skip known structural keys that are not definitions
            name = m.group(1)
            if name not in {"category", "color", "method", "ai", "potential", "on_valid"}:
                names.append(name)
    return names


def build_scripted_triggers_index(verbose: bool) -> None:
    dirs = [VANILLA_TRIGGERS_DIR] + MOD_TRIGGERS_DIRS
    files = []
    for d in dirs:
        if d.exists():
            files.extend(d.glob("*.txt"))
    names = _extract_top_level_names(files)
    _write_index(INDEX_DIR / "scripted_triggers.txt", names, verbose, "scripted triggers")


def build_scripted_effects_index(verbose: bool) -> None:
    dirs = [VANILLA_EFFECTS_DIR] + MOD_EFFECTS_DIRS
    files = []
    for d in dirs:
        if d.exists():
            files.extend(d.glob("*.txt"))
    names = _extract_top_level_names(files)
    _write_index(INDEX_DIR / "scripted_effects.txt", names, verbose, "scripted effects")


def build_static_modifiers_index(verbose: bool) -> None:
    """Extract modifier names from 00_modifier_types.txt (same source as validate.py whitelist)."""
    if not MODIFIER_TYPES_FILE.exists():
        print(f"[WARN] modifier_types file not found: {MODIFIER_TYPES_FILE}")
        return
    whitelist = []
    pat = re.compile(r"^(\w+)\s*=\s*\{")
    with MODIFIER_TYPES_FILE.open(encoding="utf-8-sig") as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                whitelist.append(m.group(1))
    _write_index(INDEX_DIR / "static_modifiers.txt", whitelist, verbose, "static modifiers")


def build_loc_keys_en_index(verbose: bool) -> None:
    """Extract all English localization key names from src/."""
    key_pat = re.compile(r"^\s+(\w+)\s*:", re.MULTILINE)
    keys = []
    for loc_dir in LOC_EN_DIRS:
        if not loc_dir.exists():
            continue
        for yml in loc_dir.glob("*_l_english.yml"):
            try:
                text = yml.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            for m in key_pat.finditer(text):
                keys.append(m.group(1))
    _write_index(INDEX_DIR / "loc_keys_en.txt", keys, verbose, "English loc keys")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", "-v", action="store_true", help="Print entry counts per index")
    args = ap.parse_args()

    build_icons_index(args.verbose)
    build_scripted_triggers_index(args.verbose)
    build_scripted_effects_index(args.verbose)
    build_static_modifiers_index(args.verbose)
    build_loc_keys_en_index(args.verbose)

    if not args.verbose:
        counts = {f.name: sum(1 for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip())
                  for f in sorted(INDEX_DIR.glob("*.txt")) if f.exists()}
        summary = ", ".join(f"{n}: {c}" for n, c in counts.items())
        print(f"[OK] Indexes written to {INDEX_DIR.relative_to(REPO_ROOT)}/ — {summary}")


if __name__ == "__main__":
    main()
