#!/usr/bin/env python3
"""
EU5 Mod Static Validator
Catches common errors before game loading. Reads docs/knowledge/*.yaml for patterns.

Usage:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/validate.py                   # validate entire src/
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/validate.py src/stable/       # validate one directory
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/validate.py --changed         # validate git-changed files under src/
"""

import json
import re
import sys
import subprocess
import os
from functools import lru_cache
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
MOD_SOURCE_DIR = REPO_ROOT / "src"
KNOWLEDGE_DIR = REPO_ROOT / "docs" / "knowledge"
_BASE_DEFAULT = REPO_ROOT / ".eu5-base"
if not _BASE_DEFAULT.exists():
    _BASE_DEFAULT = REPO_ROOT.parent / "eu5-modding-base"
BASE_ROOT = Path(os.environ.get("EU5_MODDING_BASE", str(_BASE_DEFAULT))).resolve()
sys.path.insert(0, str(BASE_ROOT / "docs" / "knowledge"))
from knowledge_loader import load_anti_patterns, load_valid_enums
sys.path.insert(0, str(BASE_ROOT / "ai_gui_assessment" / "renderer"))
from eu5_gui_renderer.pdx import parse as parse_script, parse_file
MODIFIER_TYPES_FILE = (
    REPO_ROOT
    / ".eu5-base" / "reference_game_files"
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
        if (
            p.exists()
            and MOD_SOURCE_DIR in p.parents
            and p.suffix in {".txt", ".gui", ".yml"}
        ):
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


def strip_script_comments(content: str) -> str:
    """Mask comments without moving source offsets or removing # inside strings."""
    return re.sub(
        r'"(?:[^"\\]|\\.)*"|#[^\n]*',
        lambda match: match[0] if match[0].startswith('"') else " " * len(match[0]),
        content,
    )


def walk_script(nodes):
    for node in nodes:
        yield node
        if node.is_block():
            yield from walk_script(node.value)


@lru_cache(maxsize=16)
def reference_objects(base: Path, database: str) -> dict:
    objects = {}
    for source in sorted((base / "reference_game_files/game/in_game/common" / database).glob("*.txt")):
        if source.stem.lower() == "readme":
            continue
        for node in parse_file(source):
            if node.is_block():
                objects[node.key] = node
    return objects


def mod_search_roots(mod_root: Path) -> list[Path]:
    """Include assets supplied by declared dependencies available in this workspace."""
    roots = [mod_root]
    metadata = {}
    for source in (REPO_ROOT / "src").glob("*/.metadata/metadata.json"):
        data = json.loads(source.read_text(encoding="utf-8-sig"))
        metadata[source.parent.parent] = data
    by_id = {data["id"]: root for root, data in metadata.items() if "id" in data}
    for root in roots:
        for relation in metadata.get(root, {}).get("relationships", []):
            dependency = by_id.get(relation.get("id"))
            if relation.get("rel_type") == "dependency" and dependency and dependency not in roots:
                roots.append(dependency)
    return roots


def missing_io_icons(path: Path) -> list[str]:
    try:
        target = path.relative_to(REPO_ROOT / "src").parts[0]
    except ValueError:
        return []
    mod_root = REPO_ROOT / "src" / target
    sources = sorted((mod_root / "in_game/common/international_organizations").glob("*.txt"))
    if not sources:
        return []
    vanilla = reference_objects(BASE_ROOT, "international_organizations")
    roots = mod_search_roots(mod_root)
    missing = set()
    for source in sources:
        for node in parse_file(source):
            key = node.key.rsplit(":", 1)[-1]
            if not node.is_block() or key in vanilla:
                continue
            icon = Path("main_menu/gfx/interface/icons/international_organizations") / f"{key}.dds"
            if not any((root / icon).is_file() for root in roots):
                missing.add(key)
    return sorted(missing)


def check_anti_patterns(path: Path, content: str, patterns: list[dict]):
    path_str = str(path).replace("\\", "/")
    code = strip_script_comments(content)
    nodes = None
    for entry in patterns:
        regex = entry.get("pattern", "")
        if not regex:
            continue
        # This rule describes generic-action selection slots. Resolutions use
        # the separate native recipient/vote contract (benedictus_deus.txt).
        if entry.get("id") == "select_trigger_custom_target_flag" and "/generic_actions/" not in path_str:
            continue
        # Restrict to specific path substrings if specified
        only_in = entry.get("only_in_paths", [])
        if only_in and not any(sub in path_str for sub in only_in):
            continue
        try:
            ident = entry.get("id")
            detail = ""
            if ident == "change_variable_uses_value_key":
                if path.suffix not in {".txt", ".gui"} or "change_variable" not in code:
                    continue
                if nodes is None:
                    nodes = parse_script(code, str(path))
                # An arithmetic operand may itself contain a script-value block.
                lines = [child.line for node in walk_script(nodes)
                         if node.key == "change_variable" and node.is_block()
                         for child in node.value if child.key == "value" and child.op == "="]
            elif ident == "custom_goods_reuses_vanilla_goods_color":
                if "/common/goods/" not in path_str or path.suffix != ".txt":
                    continue
                if nodes is None:
                    nodes = parse_script(code, str(path))
                vanilla = reference_objects(BASE_ROOT, "goods")
                colors = {child.value for node in vanilla.values() for child in node.value
                          if child.key == "color" and isinstance(child.value, str)}
                lines = [child.line for node in nodes
                         if node.is_block() and node.key.rsplit(":", 1)[-1] not in vanilla
                         for child in node.value if child.key == "color"
                         and isinstance(child.value, str) and child.value in colors]
            elif ident == "mod_io_geticon_without_matching_texture":
                match = re.search(regex, code)
                missing = missing_io_icons(path) if match else []
                if not missing:
                    continue
                lines = [code[:match.start()].count("\n") + 1]
                detail = " Missing custom IO icons: " + ", ".join(missing) + "."
            else:
                lines = [code[:m.start()].count("\n") + 1
                         for m in re.finditer(regex, code, re.MULTILINE | re.IGNORECASE)]
            for line_num in lines:
                issues.append(
                    f"[{entry.get('category', 'pattern').upper()}] "
                    f"{path.relative_to(REPO_ROOT)}:{line_num} -- "
                    f"Bad: \"{entry['bad']}\" -> {entry['correction']}{detail}"
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
                    f"[ENUM] {path.relative_to(REPO_ROOT)}:{line_num} -- "
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
                    f"[MODIFIER] {path.relative_to(REPO_ROOT)}:{i} -- "
                    f"Unknown modifier name '{name}'; verify in 00_modifier_types.txt"
                )


# ---------------------------------------------------------------------------
# SOL demand baseline checks
# ---------------------------------------------------------------------------

def check_inject_demand_multiply(path: Path, content: str) -> None:
    """Ensure no INJECT block in z_SOL_pop_goods.txt contains demand_multiply."""
    if path.name != "z_SOL_pop_goods.txt":
        return

    # Find every INJECT:good = { ... } block and scan its interior
    for m in re.finditer(r"\bINJECT\s*:\s*(\w+)\s*=\s*\{", content):
        good = m.group(1)
        brace_start = m.end() - 1  # points at '{'
        depth = 0
        i = brace_start
        inner_start = brace_start + 1
        while i < len(content):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    inner = content[inner_start:i]
                    # Strip comments before checking
                    inner_no_comments = re.sub(r"#[^\n]*", "", inner)
                    if re.search(r"\bdemand_multiply\b", inner_no_comments):
                        line_num = content[:m.start()].count("\n") + 1
                        issues.append(
                            f"[GOODS] {path.relative_to(REPO_ROOT)}:{line_num} -- "
                            f"demand_multiply forbidden inside INJECT block '{good}'"
                        )
                    break
            i += 1


_GLOBAL_MAP_EFFECT_RE = re.compile(
    r"\b(?P<op>add_to_global_variable_map|remove_from_global_variable_map)"
    r"\s*=\s*\{(?P<body>[^{}]*)\}"
)
_GLOBAL_MAP_FIELD_RE = re.compile(r"\b(name|key)\s*=\s*([^\s{}]+)")


def _parse_global_map_effect(line: str):
    code = line.split("#", 1)[0]
    m = _GLOBAL_MAP_EFFECT_RE.search(code)
    if not m:
        return None
    fields = dict(_GLOBAL_MAP_FIELD_RE.findall(m.group("body")))
    name = fields.get("name")
    key = fields.get("key")
    if not name or not key:
        return None
    return (m.group("op"), name, key)


def check_global_variable_map_updates(path: Path, content: str) -> None:
    """Require remove+add when writing global_variable_map values.

    add_to_global_variable_map is insert-only. If the key exists, the old value
    is silently kept, so every add must be preceded by a same-name same-key remove.
    """
    lines = content.splitlines()
    previous_meaningful_effect = None

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        effect = _parse_global_map_effect(line)
        if not effect:
            previous_meaningful_effect = None
            continue

        op, name, key = effect
        if op == "add_to_global_variable_map":
            expected = ("remove_from_global_variable_map", name, key)
            if previous_meaningful_effect != expected:
                issues.append(
                    f"[GLOBAL_MAP] {path.relative_to(REPO_ROOT)}:{i} -- "
                    "add_to_global_variable_map does not update existing keys; "
                    "put remove_from_global_variable_map with the same name/key "
                    "immediately before it"
                )

        previous_meaningful_effect = effect


_LOCAL_VARIABLE_EFFECT_RE = re.compile(
    r"\b(?P<op>set_local_variable|change_local_variable|remove_local_variable)"
    r"\s*=\s*(?:\{\s*name\s*=\s*)?(?P<name>[A-Za-z0-9_$]+)",
    re.MULTILINE,
)


def check_local_variable_cleanup(path: Path, content: str) -> None:
    """Require every local scratch variable written in a file to be removed."""
    code = re.sub(r"#[^\n]*", "", content)
    writes: dict[str, int] = {}
    removed: set[str] = set()

    for match in _LOCAL_VARIABLE_EFFECT_RE.finditer(code):
        name = match.group("name")
        if match.group("op") == "remove_local_variable":
            removed.add(name)
        else:
            writes.setdefault(name, match.start())

    for name, start in sorted(writes.items()):
        if name not in removed:
            line_num = code[:start].count("\n") + 1
            issues.append(
                f"[LOCAL_VARIABLE] {path.relative_to(REPO_ROOT)}:{line_num} -- "
                f"temporary local variable '{name}' is written but never removed"
            )


def check_loc_coverage() -> None:
    """Verify every key in English localization also exists in simp_chinese."""
    en_dir = REPO_ROOT / "src" / "stable" / "main_menu" / "localization" / "english"
    zh_dir = REPO_ROOT / "src" / "stable" / "main_menu" / "localization" / "simp_chinese"
    if not en_dir.exists():
        return
    key_pat = re.compile(r"^\s+(\w+)\s*:")
    for en_file in sorted(en_dir.glob("*_l_english.yml")):
        stem = en_file.stem[: -len("_l_english")]
        zh_file = zh_dir / f"{stem}_l_simp_chinese.yml"
        en_keys = {m.group(1) for line in en_file.read_text(encoding="utf-8-sig").splitlines() if (m := key_pat.match(line))}
        if not zh_file.exists():
            issues.append(f"[LOC] Missing simp_chinese file: {zh_file.relative_to(REPO_ROOT)}")
            continue
        zh_keys = {m.group(1) for line in zh_file.read_text(encoding="utf-8-sig").splitlines() if (m := key_pat.match(line))}
        missing = sorted(en_keys - zh_keys)
        if missing:
            issues.append(
                f"[LOC] {zh_file.relative_to(REPO_ROOT)}: "
                f"{len(missing)} key(s) missing from simp_chinese: "
                + ", ".join(missing)
            )


def check_autogenerated_staged() -> None:
    """Warn if any staged file contains the @AUTOGENERATED marker (generated output, not source)."""
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    for name in staged.stdout.splitlines():
        name = name.strip()
        if not name:
            continue
        p = REPO_ROOT / name
        if not p.exists() or p.suffix not in {".txt", ".gui", ".yml"}:
            continue
        try:
            first_line = p.read_text(encoding="utf-8-sig").splitlines()[0]
        except (IndexError, UnicodeDecodeError):
            continue
        if "@AUTOGENERATED" in first_line:
            issues.append(
                f"[AUTOGEN] {name} is auto-generated — edit its source script/data instead "
                f"(see first-line comment for the generator)"
            )


def _parse_issue_structured(raw: str) -> dict:
    """Parse a raw issue string into a structured dict for --ai-report output."""
    # Pattern: [CATEGORY] path/to/file.txt:42 -- Bad: "bad" -> fix
    m = re.match(r"^\[(\w+)\]\s+([^:]+):(\d+)\s+--\s+Bad:\s+\"([^\"]*)\"\s+->\s+(.+)$", raw)
    if m:
        return {"rule": m.group(1).lower(), "file": m.group(2), "line": int(m.group(3)),
                "bad": m.group(4), "fix": m.group(5).strip()}
    # Pattern: [CATEGORY] path/to/file.txt:42 -- message
    m = re.match(r"^\[(\w+)\]\s+([^:]+):(\d+)\s+--\s+(.+)$", raw)
    if m:
        return {"rule": m.group(1).lower(), "file": m.group(2), "line": int(m.group(3)),
                "message": m.group(4).strip()}
    # Pattern: [CATEGORY] message (no file/line)
    m = re.match(r"^\[(\w+)\]\s+(.+)$", raw, re.DOTALL)
    if m:
        return {"rule": m.group(1).lower(), "message": m.group(2).strip()}
    return {"raw": raw}


def main():
    anti_patterns = load_anti_patterns(REPO_ROOT)
    enum_data = load_valid_enums(REPO_ROOT)
    modifier_whitelist = load_modifier_whitelist()

    use_changed = "--changed" in sys.argv
    ai_report = "--ai-report" in sys.argv
    targets = [a for a in sys.argv[1:] if not a.startswith("-")]

    if use_changed:
        files = get_changed_files()
        if not files:
            if ai_report:
                print(json.dumps({"pass": True, "errors": [], "warnings": [], "files_checked": 0}))
            else:
                print("[OK] No changed mod files to validate.")
            sys.exit(0)
    elif targets:
        files = []
        for t in targets:
            files.extend(collect_files(REPO_ROOT / t))
    else:
        files = collect_files(MOD_SOURCE_DIR)

    if not files:
        if ai_report:
            print(json.dumps({"pass": True, "errors": [], "warnings": [], "files_checked": 0}))
        else:
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
        check_inject_demand_multiply(path, content)
        check_global_variable_map_updates(path, content)
        check_local_variable_cleanup(path, content)

    # File-independent checks
    check_loc_coverage()
    check_autogenerated_staged()

    # Staging generated outputs is normal in this repository. The reminder is
    # informational in both report modes; genuine validation errors still fail.
    errors = [i for i in issues if not i.startswith("[AUTOGEN]")]
    warnings = [i for i in issues if i.startswith("[AUTOGEN]")]
    if ai_report:
        print(json.dumps({
            "pass": len(errors) == 0,
            "errors": [_parse_issue_structured(i) for i in errors],
            "warnings": [_parse_issue_structured(i) for i in warnings],
            "files_checked": len(files),
        }, ensure_ascii=False, indent=2))
        sys.exit(0 if len(errors) == 0 else 1)

    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        print(f"[FAIL] {len(errors)} error(s) found:\n")
        for issue in errors:
            print(f"  {issue}")
        sys.exit(1)
    else:
        suffix = f"; {len(warnings)} warning(s)" if warnings else ""
        print(f"[OK] Validated {len(files)} file(s) -- no errors{suffix}.")
        sys.exit(0)


if __name__ == "__main__":
    main()
