#!/usr/bin/env python3
"""Post-process country_events_auto localization files to fix quality issues.

Fixes applied:
1. Raw event ID titles → look up real titles from game localization
2. "NOT must be X ." → "Must NOT be X."
3. Raw scope references (Root, ROOT, Prev) → human-readable text
4. "Character X ? must satisfy:" → "Character X must satisfy:"
5. "Historical: Historical option" → "Historical choice"
6. "Applies several scripted internal effects." → better wording
7. "Automatically generated technical reference..." → cleaner description
8. Strip dynamic function calls from game loc titles [ShowXxx(...)]
9. Orphaned closing parentheses at start of requirements
10. "Changes gold production or income." → "Affects treasury or income."
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
MOD_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_LOC_DIR = MOD_ROOT / "main_menu" / "localization"

LANGUAGES = [
    "braz_por", "english", "french", "german", "japanese",
    "korean", "polish", "russian", "simp_chinese", "spanish", "turkish",
]


# ---------------------------------------------------------------------------
# Game title lookup
# ---------------------------------------------------------------------------

def build_game_title_map(game_loc_root: Path, lang: str) -> dict[str, str]:
    """Parse game event localization for a specific language to map event_id → title text."""
    titles: dict[str, str] = {}
    events_dir = game_loc_root / lang / "events"
    if not events_dir.is_dir():
        return titles

    for yml_path in events_dir.rglob("*.yml"):
        try:
            text = yml_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("l_"):
                continue
            # Match: event_id.title: "value"  or  event_id.t: "value"
            m = re.match(
                r'([\w.]+)\.(title|t)\s*:\s*(?:\d+\s+)?"(.+)"', line
            )
            if m:
                event_id = m.group(1)
                raw_title = m.group(3)
                # Strip dynamic function calls like [ShowXxx('yyy')]
                clean = sanitize_title_text(raw_title)
                if not title_is_incomplete(clean):
                    titles[event_id] = clean
    return titles


def strip_dynamic_refs(text: str) -> str:
    """Remove [FunctionName('arg')] or [Xxx.Yyy] patterns from game text,
    replacing with contextual placeholders."""
    # Replace [...] blocks with a placeholder marker
    result = re.sub(r"\[.*?\]", "\x00", text)
    # Clean up multiple placeholders
    result = re.sub(r"\x00+", "\x00", result)
    # Remove placeholders that are surrounded by text (mid-sentence)
    # Keep the sentence flowing by joining words
    result = result.replace("\x00", " (...) ")
    # Clean up double spaces and leading/trailing
    result = re.sub(r"  +", " ", result).strip()
    # Remove leading placeholders and normalize dangling trailing ones later.
    result = re.sub(r"^\s*\(\.\.\.\)\s*", "", result).strip()

    trailing_placeholder = bool(re.search(r"\s*\(\.\.\.\)\s*$", result))
    result = re.sub(r"\s*\(\.\.\.\)\s*$", "", result).strip()

    dangling_tail_pattern = (
        r"\b("
        r"of|the|in|to|for|from|by|as|and|or|a|an|on|at|with|against|"
        r"de|del|la|el|los|las|al|"
        r"do|da|dos|das|o|a|os|as|"
        r"du|des|le|les|l'|d'|"
        r"des|der|die|das|dem|den|ein|eine|einer|einem|einen"
        r")\s*$"
    )
    if trailing_placeholder or re.search(dangling_tail_pattern, result, re.IGNORECASE):
        result = result.strip() + " (...)"
    return result


def sanitize_title_text(text: str) -> str:
    """Remove formatter/comment leftovers from generated titles."""
    if not text:
        return text
    text = strip_dynamic_refs(text)
    text = text.replace('\\"', '"').replace("\t", " ")
    text = re.sub(r"^\s*#+\s*", "", text)
    text = re.sub(r"\s+triggered by\b.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+when it selects\b.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+#.*$", "", text)
    text = text.replace("#!", "")
    text = text.replace("#", "")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text.strip(" -:;,.")


def title_is_incomplete(title: str) -> bool:
    """Check if a cleaned title is too incomplete to be useful."""
    if not title or len(title) < 3:
        return True
    t = title.strip()
    # Only ellipsis placeholder
    if t == "(...)":
        return True
    if "(...)" in t:
        return True
    # Contains unresolved loc references ($xxx$)
    if "$" in t:
        return True
    if any(marker in t.lower() for marker in ("that culture", "this character", "that country", "current scope")):
        return True
    if re.search(r"\b(?:do|da|de|del|der|des)\([a-z]+\)$", t, re.IGNORECASE):
        return True
    # Starts with a lowercase word (broken sentence fragment)
    if t[0].islower():
        return True
    # Too short after stripping ellipsis
    core = t.replace("(...)", "").strip()
    if len(core) < 3:
        return True
    # Ends with a preposition/article without ellipsis (truly broken)
    if not t.endswith("(...)") and re.search(
        r"\b("
        r"of|the|in|to|for|from|by|as|and|or|a|an|on|at|with|against|"
        r"de|del|la|el|los|las|al|"
        r"do|da|dos|das|o|a|os|as|"
        r"du|des|le|les|l'|d'|"
        r"der|die|das|dem|den|des|ein|eine|einer|einem|einen"
        r")\s*$",
        t, re.IGNORECASE
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Text cleanup functions
# ---------------------------------------------------------------------------

def fix_not_must_be(text: str) -> str:
    """'NOT must be X .' → 'Must NOT be X.'
       'NOT must be X.' → 'Must NOT be X.'"""
    # Pattern: NOT must be <something> . (with optional trailing space before dot)
    text = re.sub(
        r"NOT must be (.+?) \.",
        r"Must NOT be \1.",
        text,
    )
    # Also handle without space before dot
    text = re.sub(
        r"NOT must be (.+?)\.",
        r"Must NOT be \1.",
        text,
    )
    return text


def fix_scope_references(text: str) -> str:
    """Replace raw scope references with human-readable text."""
    # Specific patterns first (more context = better replacement)
    replacements = [
        # Subject/alliance/war relationships
        (r"Is Subject Of = Root", "is a subject of our country"),
        (r"Is Subject Of = root", "is a subject of our country"),
        (r"Is Allied With = Target = Root", "is allied with our country"),
        (r"Is Allied With = Root", "is allied with our country"),
        (r"Is At War With = Root", "is at war with us"),
        (r"Is At War With = root", "is at war with us"),
        (r"Top Owner = Root", "is ultimately owned by us"),
        (r"Top Owner = root", "is ultimately owned by us"),

        # Owner/ruler references
        (r"Owner must be ROOT\b", "Must be owned by us"),
        (r"Owner must be Root\b", "Must be owned by us"),
        (r"Owner must be root\b", "Must be owned by us"),
        (r"Ruler must be Root\.ruler\b", "Must have our current ruler"),
        (r"Ruler must be Root\.Ruler\b", "Must have our current ruler"),

        # Opinion checks (various formats)
        (r"Opinion = Target = Root Value must be at least (\d+)",
         r"Opinion of us must be at least \1"),
        (r"Opinion = Target = Root Value must be at most (\d+)",
         r"Opinion of us must be at most \1"),
        (r"Opinion = Target = Root Value ([<>]=?) (\d+)",
         r"Opinion of us must be \1 \2"),
        (r"Opinion must be Target = Root Value ([<>]) (\d+)",
         r"Opinion of us must be \1 \2"),
        (r"Opinion = Target = Prev Value must be at least (\d+)",
         r"Opinion of the target must be at least \1"),
        (r"Opinion = Target = Prev Value ([<>]=?) (\d+)",
         r"Opinion of the target must be \1 \2"),
        (r"Root = Opinion = Target = Prev Value must be at least (\d+)",
         r"Our opinion of the target must be at least \1"),
        (r"Root = Opinion = Target = Prev Value ([<>]=?) (\d+)",
         r"Our opinion of the target must be \1 \2"),
        (r"Root\.expected Navy Size", "our expected navy size"),

        # Owner/Controller = Root in complex expressions
        (r"Owner = Root Controller", "owned and controlled by us"),
        (r"Owner = Root Has Building", "owned by us, Has Building"),
        (r"Owner = Root\b", "owned by us"),
        (r"Country = Root\b", "our country"),

        # Is Rival/At War/Enemy/Core with Root
        (r"Is Rival Of must be Root\b", "Must be our rival"),
        (r"Is At War With must be Root\b", "Must be at war with us"),
        (r"Is Enemy Of must be Root\b", "Must be our enemy"),
        (r"Is Core Of must be Root\b", "Must be our core"),

        # Property comparisons with Root
        (r"Ruler\.dynasty = Root\.ruler\.dynasty", "Must share our ruler's dynasty"),
        (r"Religion = Root\.religion\b", "Must share our religion"),
        (r"Religion\.group = Root\.religion\.group\b", "Must share our religious group"),
        (r"Religion = Root\.ruler\b", "Must share our ruler's religion"),
        (r"Religion = ROOT\.religion\b", "Must share our religion"),
        (r"Culture = Root\.culture\b", "Must share our culture"),
        (r"Location = Root\.capital\b", "Must be in our capital"),
        (r"Continent = Root\.capital\.sub\b", "Must be on our capital's continent"),
        (r"This = Root\.ruler\b", "Must be our ruler"),
        (r"This = Root\b", "Must be our country"),
        (r"This = ROOT\b", "Must be our country"),
        (r"Attacker = Root\b", "Attacker must be us"),
        (r"Member = Root\b", "Must include our country"),
        (r"Value = Root\.monthly\b", "based on our monthly value"),
        (r"By = ROOT\b", "by us"),

        # Generic With/Of/Target = Root/ROOT at end
        (r"With = Root\.", "with our country."),
        (r"With = ROOT\.", "with our country."),
        (r"Of = Root\.", "of our country."),
        (r"Of = ROOT\.", "of our country."),
        (r"Target = ROOT\.", "our country."),
        (r"Owner = ROOT\.", "us."),

        # Catch-all = Root/ROOT
        (r"= Root\.", "our country."),
        (r"= ROOT\.", "our country."),
        (r"= Prev\.", "the previous scope."),
        (r"= PREV\.", "the previous scope."),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text


def fix_character_question_mark(text: str) -> str:
    """'Character Xxx Yyy ? must satisfy:' → 'Character Xxx Yyy must satisfy:'"""
    return re.sub(
        r"Character (.+?) \? must satisfy:",
        r"Character \1 must satisfy:",
        text,
    )


def fix_historical_option_label(text: str) -> str:
    """'Historical: Historical option' → 'Historical choice'
       But keep 'Historical: Actual Name' as is."""
    text = text.replace("Historical: Historical option", "Historical choice")
    return text


def fix_scripted_effects(text: str) -> str:
    """'Applies several scripted internal effects.' → better wording."""
    text = text.replace(
        "Applies several scripted internal effects.",
        "Applies complex game effects (details not extractable from script).",
    )
    return text


def fix_boilerplate_desc(text: str) -> str:
    """Clean up auto-generated boilerplate descriptions."""
    m = re.match(
        r"Automatically generated technical reference for '(.+?)'\. "
        r"Source: (.+?)\. See the historical window and documented trigger below\.",
        text,
    )
    if m:
        name = m.group(1)
        source = m.group(2)
        # If name is a raw event ID, just say no description available
        if re.match(r"[\w_]+\.\d+", name):
            return f"No detailed description available. Source: {source}."
        else:
            return (
                f"Event: {name}. "
                f"No detailed description available. Source: {source}."
            )
    return text


def fix_orphaned_parens(text: str) -> str:
    """Fix orphaned closing parentheses like 'Clergy Estate) must be'."""
    # Pattern: word) must be → word must be
    text = re.sub(r"(\w+)\) must be", r"\1 must be", text)
    return text


def fix_alternative_option_dedup(text: str) -> str:
    """When multiple options all say 'Alternative option' with same effects,
    number them for clarity."""
    parts = text.split("\\n- Alternative option\\n")
    if len(parts) <= 2:
        return text
    # Multiple alternative options - number them
    result = parts[0]
    for i, part in enumerate(parts[1:], 1):
        result += f"\\n- Alternative option {i}\\n" + part
    return result


def _slug_to_event_id(slug: str) -> str | None:
    """Try to reverse a slug like FLAVOR_TUR_49 to event ID flavor_tur.49.

    Convention: the last numeric segment after _ is the event number,
    everything before is the namespace with . replaced by _.
    E.g. FLAVOR_CAS_RIO_SALADO_5 → flavor_cas_rio_salado.5
         DECLINE_OF_MALI_10 → decline_of_mali.10
    """
    # Find the last _N segment where N is a number
    m = re.match(r"^(.+)_(\d+)$", slug)
    if not m:
        return None
    prefix = m.group(1).lower()
    number = m.group(2)
    return f"{prefix}.{number}"


def cleanup_value(
    key: str,
    value: str,
    game_titles: dict[str, str],
    generated_english_titles: dict[str, str] | None = None,
) -> str:
    """Apply all cleanup transformations to a localization value."""

    generated_english_titles = generated_english_titles or {}

    is_option_title = bool(re.search(r"_OPTION_\d+_TITLE$", key))

    if key.endswith("_TITLE") and not is_option_title:
        original_value = value
        value = sanitize_title_text(value)
    else:
        original_value = value
        value = re.sub(r"^\s*#+\s*", "", value)

    if is_option_title:
        return value

    if key.endswith("_TITLE"):
        # Derive event_id from key for reverse lookup
        slug = key.replace("COUNTRY_EVENTS_AUTO_", "").replace("_TITLE", "")
        event_id = _slug_to_event_id(slug)

        def best_title(eid: str) -> str:
            game_title = game_titles.get(eid, "")
            if game_title and not title_is_incomplete(game_title):
                return game_title
            generated_title = generated_english_titles.get(eid, "")
            if generated_title and not title_is_incomplete(generated_title):
                return generated_title
            return ""

        # Check if title is a raw event ID
        if re.match(r"^[\w_]+\.\d+$", value):
            # Try to look up from game localization
            preferred_title = best_title(value)
            if preferred_title:
                return preferred_title
            else:
                return f"Event: {value}"
        # Check if title was previously processed as "Event: xxx"
        m = re.match(r"^Event: ([\w_]+\.\d+)$", value)
        if m:
            eid = m.group(1)
            preferred_title = best_title(eid)
            if preferred_title:
                return preferred_title
            return value  # keep "Event: xxx" as is

        # If sanitize destroyed the value, try reverse lookup before giving up
        if title_is_incomplete(value) and event_id:
            preferred_title = best_title(event_id)
            if preferred_title:
                return preferred_title
            # No game title available — use event ID as fallback
            if not value:
                return f"Event: {event_id}"

        # Check if current title can be improved from game loc
        if event_id:
            game_title = best_title(event_id)
            if (
                game_title
                and not title_is_incomplete(game_title)
                and game_title != value
                and title_is_incomplete(value)
            ):
                return game_title
        return value

    if key.endswith("_DESC"):
        value = fix_boilerplate_desc(value)
        value = fix_scope_references(value)
        return value

    if key.endswith("_REQUIREMENTS"):
        value = fix_not_must_be(value)
        value = fix_scope_references(value)
        value = fix_character_question_mark(value)
        value = fix_orphaned_parens(value)
        return value

    if key.endswith("_OUTCOMES"):
        value = fix_historical_option_label(value)
        value = fix_scripted_effects(value)
        value = fix_scope_references(value)
        value = fix_alternative_option_dedup(value)
        return value

    return value


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def parse_loc_file(path: Path) -> tuple[str, list[tuple[str, str, str]]]:
    """Parse a Paradox loc YAML file. Returns (header_line, [(key, version, value)])."""
    entries: list[tuple[str, str, str]] = []
    header = ""
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("l_"):
            header = stripped
            continue

        colon_pos = stripped.find(":")
        if colon_pos == -1:
            continue
        key = stripped[:colon_pos].strip()
        rest = stripped[colon_pos + 1:].strip()

        # Extract version number
        version = "0"
        if rest and rest[0].isdigit():
            space_pos = rest.find(" ")
            if space_pos != -1:
                version = rest[:space_pos]
                rest = rest[space_pos + 1:]

        # Remove surrounding quotes
        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]

        entries.append((key, version, unescape_loc_value(rest)))

    return header, entries


def write_loc_file(
    path: Path,
    header: str,
    entries: list[tuple[str, str, str]],
) -> None:
    """Write a Paradox loc YAML file with BOM."""
    lines = [header]
    for key, version, value in entries:
        escaped = escape_loc_value(value)
        lines.append(f' {key}:{version} "{escaped}"')
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8-sig", newline="\n")


def unescape_loc_value(value: str) -> str:
    """Decode common Paradox loc escapes and discard broken ones safely."""
    result: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\" or i + 1 >= len(value):
            result.append(ch)
            i += 1
            continue

        nxt = value[i + 1]
        if nxt == "n":
            result.append("\n")
        elif nxt == "r":
            result.append("\r")
        elif nxt == "t":
            result.append("\t")
        elif nxt == '"':
            result.append('"')
        elif nxt == "\\":
            result.append("\\")
        else:
            result.append(nxt)
        i += 2
    return "".join(result)


def escape_loc_value(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\\", "\\\\")
    value = value.replace("\n", "\\n")
    return value.replace('"', '\\"')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-process auto localization files to fix quality issues."
    )
    parser.add_argument(
        "--loc-dir",
        type=Path,
        default=DEFAULT_LOC_DIR,
        help=f"Localization directory. Default: {DEFAULT_LOC_DIR}",
    )
    parser.add_argument(
        "--game-loc",
        type=Path,
        default=None,
        help="Game localization root (contains english/ etc). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes without writing files.",
    )
    return parser.parse_args()


def find_game_loc_root() -> Path | None:
    """Try to auto-detect the game localization directory."""
    candidates = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\main_menu\localization"),
        Path(r"C:\Program Files\Steam\steamapps\common\Europa Universalis V\game\main_menu\localization"),
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return None


def main() -> int:
    args = parse_args()
    loc_dir = args.loc_dir.resolve()

    # Find game localization for title lookups
    game_loc = args.game_loc
    if game_loc is None:
        game_loc = find_game_loc_root()
    if not game_loc or not game_loc.is_dir():
        print("Warning: Game localization not found. Raw titles won't be resolved.")
        game_loc = None
    else:
        print(f"Game localization root: {game_loc}")

    total_fixes = 0
    files_written = 0

    # Cache English titles as fallback
    english_titles: dict[str, str] = {}
    if game_loc:
        english_titles = build_game_title_map(game_loc, "english")
        print(f"  English fallback: {len(english_titles)} titles")

    english_generated_titles: dict[str, str] = {}
    english_generated_path = loc_dir / "english" / "country_events_auto_l_english.yml"
    if english_generated_path.is_file():
        _, english_generated_entries = parse_loc_file(english_generated_path)
        for key, _version, value in english_generated_entries:
            if not key.startswith("COUNTRY_EVENTS_AUTO_") or not key.endswith("_TITLE"):
                continue
            if re.search(r"_OPTION_\d+_TITLE$", key):
                continue
            slug = key.replace("COUNTRY_EVENTS_AUTO_", "").replace("_TITLE", "")
            event_id = _slug_to_event_id(slug)
            clean = sanitize_title_text(value)
            if event_id and clean and not title_is_incomplete(clean):
                english_generated_titles[event_id] = clean

    for lang in LANGUAGES:
        paths = [
            loc_dir / lang / f"country_events_auto_l_{lang}.yml",
            loc_dir / lang / f"country_events_slots_l_{lang}.yml",
        ]

        # Build title map for this specific language
        if game_loc:
            if lang == "english":
                game_titles = english_titles
            else:
                game_titles = build_game_title_map(game_loc, lang)
                # Fallback to English when the localized title is missing or incomplete.
                for eid, title in english_titles.items():
                    if eid not in game_titles or title_is_incomplete(game_titles[eid]):
                        game_titles[eid] = title
            print(f"  {lang}: {len(game_titles)} game titles loaded")
        else:
            game_titles = {}

        lang_fixes = 0
        lang_written = 0

        for loc_path in paths:
            if not loc_path.is_file():
                continue

            header, entries = parse_loc_file(loc_path)
            new_entries: list[tuple[str, str, str]] = []
            path_fixes = 0

            for key, version, value in entries:
                if key.startswith("COUNTRY_EVENTS_AUTO_"):
                    new_value = cleanup_value(key, value, game_titles, english_generated_titles)
                    if new_value != value:
                        path_fixes += 1
                        if args.dry_run and lang == "english":
                            print(f"  FIX [{key}]:")
                            old_short = value[:100] + "..." if len(value) > 100 else value
                            new_short = new_value[:100] + "..." if len(new_value) > 100 else new_value
                            print(f"    OLD: {old_short}")
                            print(f"    NEW: {new_short}")
                    new_entries.append((key, version, new_value))
                else:
                    new_entries.append((key, version, value))

            if path_fixes > 0:
                if not args.dry_run:
                    write_loc_file(loc_path, header, new_entries)
                    files_written += 1
                    lang_written += 1
                total_fixes += path_fixes
                lang_fixes += path_fixes

        if lang_fixes > 0:
            print(f"  {lang}: {lang_fixes} fixes applied")
        else:
            print(f"  {lang}: no fixes needed")

    if args.dry_run:
        print(f"\nDry run complete. {total_fixes} total fixes would be applied.")
    else:
        print(f"\nWrote {files_written} files. {total_fixes} total fixes applied.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
