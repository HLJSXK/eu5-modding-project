#!/usr/bin/env python3
"""
Generate a syntactically valid EU5 skeleton file from a template library.

Templates are derived verbatim from confirmed vanilla/mod examples (3-step rule, Step 3).
Each output file has a # AUTO_SCAFFOLD_FROM header and TODO markers for fields to fill in.

Usage:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scaffold.py --type event     --name SOL_my_event
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scaffold.py --type scripted_effect  --name SOL_my_effect
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scaffold.py --type scripted_trigger --name SOL_my_trigger
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scaffold.py --type static_modifier  --name SOL_my_mod --category location
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scaffold.py --type on_action  --name my_hook
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scaffold.py --type situation  --name SOL_my_situation
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scaffold.py --type localization --name SOL_MY_KEY

  --out   Output directory (default: stdout / dry run)
  --dry   Print scaffold to stdout without writing a file

Supported types:
  event             country_event with one option (reference: civil_war.txt)
  scripted_effect   TRY_REPLACE effect block (reference: A_SOL_economy_effects.txt)
  scripted_trigger  country-scope trigger block (reference: SOL_cmm_triggers.txt)
  static_modifier   location or country static modifier (reference: A_SOL_economy_modifiers.txt)
  on_action         yearly_country_pulse hook block (reference: SOL_economy_on_actions.txt)
  situation         minimal situation skeleton (reference: SOL_economy_situation.txt)
  localization      l_english YAML with one key (reference: SOL_substitute_goods_l_english.yml)
"""

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAFFOLD_HEADER = "# AUTO_SCAFFOLD_FROM: scripts/gen_scaffold.py — fill in TODO markers, then remove this line."

# ── Default output directories per type ──────────────────────────────────────

DEFAULT_DIRS = {
    "event":            "src/stable/in_game/events",
    "scripted_effect":  "src/stable/in_game/common/scripted_effects",
    "scripted_trigger": "src/stable/in_game/common/scripted_triggers",
    "static_modifier":  "src/stable/main_menu/common/static_modifiers",
    "on_action":        "src/stable/in_game/common/on_action",
    "situation":        "src/stable/in_game/common/situations",
    "localization":     "src/stable/main_menu/localization/english",
}

DEFAULT_EXTENSIONS = {
    "localization": ".yml",
}

# ── Template functions ────────────────────────────────────────────────────────
# Each returns (filename_stem, file_content, encoding)
# References (Step 3 compliance):
#   event            → reference_game_files/game/in_game/events/civil_war.txt
#   scripted_effect  → src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt
#   scripted_trigger → src/stable/in_game/common/scripted_triggers/SOL_cmm_triggers.txt
#   static_modifier  → src/stable/main_menu/common/static_modifiers/A_SOL_economy_modifiers.txt
#   on_action        → src/stable/in_game/common/on_action/SOL_economy_on_actions.txt
#   situation        → src/stable/in_game/common/situations/SOL_economy_situation.txt
#   localization     → src/stable/main_menu/localization/english/SOL_substitute_goods_l_english.yml


def _tpl_event(name: str) -> tuple[str, str, str]:
    # namespace = first word up to first dot or the whole name
    namespace = name.split(".")[0] if "." in name else name
    event_id = name if "." in name else f"{name}.1"
    content = f"""{SCAFFOLD_HEADER}
namespace = {namespace}

{event_id} = {{
\ttype = country_event

\ttitle = {event_id}.title
\tdesc = {event_id}.desc

\ttrigger = {{
\t\t# TODO: add trigger conditions
\t\talways = yes
\t}}

\timmediate = {{
\t\t# TODO: immediate effects (hidden, no player choice needed)
\t}}

\toption = {{
\t\tname = {event_id}.a
\t\t# TODO: add effects
\t}}
}}
"""
    return name, content, "utf-8-sig"


def _tpl_scripted_effect(name: str) -> tuple[str, str, str]:
    content = f"""{SCAFFOLD_HEADER}
# Scope: TODO (country / location / character)

{name} = {{
\t# TODO: add effects
}}
"""
    return name, content, "utf-8-sig"


def _tpl_scripted_trigger(name: str) -> tuple[str, str, str]:
    content = f"""{SCAFFOLD_HEADER}
# Scope: country
# Returns yes when: TODO

{name} = {{
\tcustom_description = {{
\t\ttext = {name}_desc
\t\t# TODO: add trigger logic
\t\talways = yes
\t}}
}}
"""
    return name, content, "utf-8-sig"


def _tpl_static_modifier(name: str, category: str) -> tuple[str, str, str]:
    # category: "location" or "country" (default: country)
    # Reference: A_SOL_economy_modifiers.txt uses TRY_REPLACE for location modifiers
    prefix = "TRY_REPLACE:" if category == "location" else ""
    content = f"""{SCAFFOLD_HEADER}
{prefix}{name} = {{
\tgame_data = {{
\t\tcategory = {category}
\t}}
\t# TODO: add modifier values (see reference_game_files/.../modifier_type_definitions/)
}}
"""
    return name, content, "utf-8-sig"


def _tpl_on_action(name: str) -> tuple[str, str, str]:
    content = f"""{SCAFFOLD_HEADER}
{name} = {{
\ttrigger = {{
\t\t# TODO: add trigger conditions (runs for every country that matches)
\t\talways = yes
\t}}
\teffect = {{
\t\t# TODO: add effects
\t}}
}}
"""
    return name, content, "utf-8-sig"


def _tpl_situation(name: str) -> tuple[str, str, str]:
    content = f"""{SCAFFOLD_HEADER}
{name} = {{
\tmonthly_spawn_chance = 1

\tcan_start = {{
\t\t# TODO: conditions for situation to start
\t\tcurrent_date >= 1337.2.1
\t}}

\tcan_end = {{
\t\t# TODO: conditions for situation to end (always = no for permanent)
\t\talways = no
\t}}

\tvisible = {{
\t\t# TODO: visibility condition (toggle check)
\t\talways = yes
\t}}

\ton_monthly = {{
\t\t# TODO: monthly recurring effects
\t}}
}}
"""
    return name, content, "utf-8-sig"


def _tpl_localization(name: str) -> tuple[str, str, str]:
    # UTF-8 BOM required (encoding="utf-8-sig"); only ASCII double-quotes valid
    # Reference: SOL_substitute_goods_l_english.yml line 1: `l_english:`
    content = f"""l_english:
 {name}: "TODO: fill in English text"
"""
    return name, content, "utf-8-sig"


# ── Dispatch table ────────────────────────────────────────────────────────────

def build_scaffold(type_: str, name: str, category: str) -> tuple[str, str, str]:
    """Returns (filename_stem, content, encoding)."""
    if type_ == "event":
        return _tpl_event(name)
    if type_ == "scripted_effect":
        return _tpl_scripted_effect(name)
    if type_ == "scripted_trigger":
        return _tpl_scripted_trigger(name)
    if type_ == "static_modifier":
        return _tpl_static_modifier(name, category)
    if type_ == "on_action":
        return _tpl_on_action(name)
    if type_ == "situation":
        return _tpl_situation(name)
    if type_ == "localization":
        return _tpl_localization(name)
    raise ValueError(f"Unknown scaffold type: {type_!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--type", required=True, choices=list(DEFAULT_DIRS), help="EU5 file type to scaffold")
    ap.add_argument("--name", required=True, help="Identifier / namespace / key name for the new file")
    ap.add_argument("--category", default="country", choices=["country", "location"],
                    help="Modifier category (only for --type static_modifier)")
    ap.add_argument("--out", default=None, help="Output directory (default: standard location for type)")
    ap.add_argument("--dry", action="store_true", help="Print scaffold to stdout without writing")
    args = ap.parse_args()

    stem, content, encoding = build_scaffold(args.type, args.name, args.category)
    ext = DEFAULT_EXTENSIONS.get(args.type, ".txt")
    filename = f"{stem}{ext}"

    if args.dry:
        print(f"--- {filename} ({encoding}) ---")
        print(content)
        return

    out_dir = Path(args.out) if args.out else (REPO_ROOT / DEFAULT_DIRS[args.type])
    out_path = out_dir / filename

    if out_path.exists():
        print(f"[WARN] {out_path.relative_to(REPO_ROOT)} already exists — skipping. Use --out to override directory.")
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding=encoding)
    print(f"[OK] Scaffold written: {out_path.relative_to(REPO_ROOT)}")
    print(f"     Fill in TODO markers, then run: $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/validate.py --changed")


if __name__ == "__main__":
    main()
