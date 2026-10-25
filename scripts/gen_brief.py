#!/usr/bin/env python3
"""
Generate docs/knowledge/BRIEF.md from docs/knowledge/*.yaml.
Run after editing anti_patterns.yaml or valid_enums.yaml.

Usage:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_brief.py
"""

from datetime import date
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    raise SystemExit(1)

REPO_ROOT = Path(__file__).parent.parent
_BASE_DEFAULT = REPO_ROOT / ".eu5-base"
if not _BASE_DEFAULT.exists():
    _BASE_DEFAULT = REPO_ROOT.parent / "eu5-modding-base"
BASE_ROOT = Path(os.environ.get("EU5_MODDING_BASE", str(_BASE_DEFAULT))).resolve()
sys.path.insert(0, str(BASE_ROOT / "docs" / "knowledge"))
from knowledge_loader import load_anti_patterns, load_valid_enums
KNOWLEDGE_DIR = REPO_ROOT / "docs" / "knowledge"
OUTPUT = KNOWLEDGE_DIR / "BRIEF.md"
OVERVIEW = KNOWLEDGE_DIR / "PROJECT_OVERVIEW.md"
INDEX_DIR = REPO_ROOT / "data" / "index"

# Codegen script map: (script, inputs, outputs, when_to_run)
CODEGEN_SCRIPTS = [
    ("gen_sol_lshud.py", "SOL four-section source + SOL history/ranking/map emitters + vendored Glorp UI types", "stable/standalone HUD, Glorp offset shim, four map modes, scoped map tooltips, font icon registration/asset, bilingual localization and ranking caches", "Run by gen_sol_chain; supports --check; stable must load after Glorp UI; verify with test_sol_lshud_income/ranking/ui.py and test_sol_map_modes.py"),
    ("gen_sol_substitution.py", "goods_weights.csv + pop_group_baskets.csv + substitute_groups.json + calibrated demand", "country pulse effects, guarded cache/display values, triggers and 56 auto modifiers", "Run by gen_sol_chain; edit sol_substitution.py, regenerate, then run test_sol_substitution.py"),
    ("gen_whole_group_baskets.py", "pop_group_baskets.csv + goods_weights.csv + calibrated demand", "whole-group and emittable-net checks; one-time budget-preserving target_demand.csv migration", "--check runs first in gen_sol_chain; --fill migrates incomplete baskets once"),
    ("update_mod_version.py", "local date or explicit --date", "selected src/<target>/.metadata/metadata.json version fields", "Run automatically by build.bat before deployment; supports --target and --check"),
    ("gen_sol_chain.py",  "SOL demand data + vanilla/PP/M&T/JTG goods + Glorp UI", "active SOL generated files for all deploy targets", "Preferred one-shot SOL generation entry; build.bat runs it automatically"),
    ("gen_sol_messages.py", "SOL resolution message definition", "stable/standalone main_menu/gui/messagetypes/SOL_messages.txt (SOL entries only)", "Run by gen_sol_chain; supports --check; removes its obsolete full-copy database for EU5 1.4.3"),
    ("gen_sol_pp_compat.py", "stable SOL outputs + PP definitions", "SOL-PP compact feature, demand, effects, and GUI overrides; validates PP road-price filename ownership", "After changing SOL balance/demand/effects/UI or updating the PP reference; run by gen_sol_chain"),
    ("gen_sol_mnt_compat.py", "data/target_demand.csv + stable SOL + M&T definitions", "SOL-M&T goods, accounting, EPBM, CMM residual cleanup, actions, and location GUI", "After changing SOL demand/effects/UI or updating the M&T reference; run by gen_sol_chain"),
    ("gen_sol_jtg_compat.py", "data/jtg_pop_demand.csv + stable SOL outputs", "SOL-JTG demand, values, effects, and 82-good GUI overrides", "After changing JTG demand data or updating the Just Goods Workshop reference; run by gen_sol_chain"),
    ("sync_location_window.py", "Glorp UI location window + extracted vanilla types", "Current Glorp UI-based stable window with optional Construction Manager references, one SOL tooltip button, synchronized type support, and backward-compatible 1.4 API migration", "After updating the Glorp UI reference; run by gen_sol_chain for stable/all"),
    ("gen_sol_economy_effects.py", "scripts/sol_economy_effects_source.py + scripts/sol_country_demand_solver_source.py + scripts/sol_living_standard_source.py + data/demand_price_table.csv", "economy/solver effects, annual SOL values, flat/percent modifier types, icons, 17 building injections, migration/growth static modifiers and bilingual names", "After changing SOL economy emitters, country solver emitters, or demand data; run by gen_sol_chain for stable|sol_standalone|all"),
    ("gen_pop_goods.py",  "data/target_demand.csv",             "src/<target>/.../z_SOL_pop_goods.txt",            "After editing calibrated demand_add baseline; supports --target stable|sol_standalone|all"),
    ("gen_demand_csv.py", "z_SOL_pop_goods.txt + vanilla goods", "data/demand_price_table.csv",                      "After gen_pop_goods.py"),
    ("gen_market_unit_consumption.py", "data/demand_price_table.csv", "src/<target>/.../SOL_market_unit_consumption_values.txt", "After gen_demand_csv.py or SOL market base-spending logic changes; supports --target stable|sol_standalone|all; market refresh block is embedded by gen_sol_economy_effects"),
    ("generate_sol_location_window.py", "vanilla location_window.gui", "src/sol_standalone/in_game/gui/location_window.gui", "After vanilla location_window.gui changes; run by gen_sol_chain for sol_standalone/all"),
    ("gen_brief.py",      "anti_patterns.yaml + valid_enums.yaml + PROJECT_OVERVIEW.md", "docs/knowledge/BRIEF.md", "After editing any YAML knowledge file"),
    ("gen_index.py",      "reference_game_files + src/",         "data/index/*.txt symbol indexes",                  "Run by gen_brief.py automatically"),
    ("gen_scaffold.py",   "--type argument",                     "Scaffold .txt/.yml file in specified directory",   "When creating a new EU5 file"),
    ("validate.py",       "src/ mod files + knowledge YAML",     "Console report (exit 0/1)",                        "Before launching game; --changed for quick check"),
]

# Auto-generated files: (relative path, generator script)
AUTOGENERATED_FILES = [
    *[(f"src/{target}/main_menu/gui/messagetypes/SOL_messages.txt", "gen_sol_messages.py")
      for target in ("stable", "sol_standalone")],
    *[(f"src/{target}/{path}", "gen_sol_economy_effects.py")
      for target in ("stable", "sol_standalone")
      for path in ("main_menu/common/static_modifiers/SOL_living_standard_modifiers.txt",
                   "main_menu/common/modifier_type_definitions/SOL_living_standard_modifier_types.txt",
                   "main_menu/common/modifier_icons/SOL_living_standard_modifier_icons.txt",
                   "in_game/common/building_types/SOL_living_standard_buildings.txt",
                   "main_menu/localization/english/SOL_living_standard_modifier_types_l_english.yml",
                   "main_menu/localization/simp_chinese/SOL_living_standard_modifier_types_l_simp_chinese.yml",
                   "main_menu/localization/english/SOL_living_standard_modifiers_l_english.yml",
                   "main_menu/localization/simp_chinese/SOL_living_standard_modifiers_l_simp_chinese.yml")],
    ("src/stable/in_game/common/goods/z_SOL_pop_goods.txt",                                     "gen_pop_goods.py"),
    ("src/sol_standalone/in_game/common/goods/z_SOL_pop_goods.txt",                             "gen_pop_goods.py"),
    ("src/stable/in_game/common/script_values/SOL_market_unit_consumption_values.txt",          "gen_market_unit_consumption.py"),
    ("src/sol_standalone/in_game/common/script_values/SOL_market_unit_consumption_values.txt",  "gen_market_unit_consumption.py"),
    ("src/stable/in_game/common/scripted_effects/A_SOL_economy_effects.txt",                    "gen_sol_economy_effects.py"),
    ("src/sol_standalone/in_game/common/scripted_effects/A_SOL_economy_effects.txt",            "gen_sol_economy_effects.py"),
    ("src/stable/in_game/common/scripted_effects/B_SOL_country_demand_solver.txt",               "gen_sol_economy_effects.py"),
    ("src/sol_standalone/in_game/common/scripted_effects/B_SOL_country_demand_solver.txt",       "gen_sol_economy_effects.py"),
    ("src/stable/in_game/common/script_values/SOL_living_standard_values.txt",                   "gen_sol_economy_effects.py"),
    ("src/sol_standalone/in_game/common/script_values/SOL_living_standard_values.txt",           "gen_sol_economy_effects.py"),
    ("src/sol_standalone/in_game/gui/location_window.gui",                                      "generate_sol_location_window.py"),
    ("src/stable/in_game/gui/location_window.gui",                                              "sync_location_window.py"),
    ("src/stable/in_game/gui/vanilla/cmfg_location_window_vanilla_types.gui",                   "sync_location_window.py"),
    ("src/sol_pp_compatibility_submod/in_game/common/goods/zz_SOL_PP_lumber_demand.txt",         "gen_sol_pp_compat.py"),
    ("src/sol_pp_compatibility_submod/in_game/common/script_values/zz_SOL_market_unit_consumption_values.txt", "gen_sol_pp_compat.py"),
    ("src/sol_pp_compatibility_submod/in_game/common/scripted_effects/zz_A_SOL_economy_effects.txt", "gen_sol_pp_compat.py"),
    ("src/sol_pp_compatibility_submod/in_game/gui/zz_SOL_economy_local.gui",                      "gen_sol_pp_compat.py"),
    ("src/sol_pp_compatibility_submod/in_game/gui/panels/situation/global_living_standard.gui",  "gen_sol_pp_compat.py"),
    ("src/sol_pp_compatibility_submod/in_game/common/auto_modifiers/zz_SOL_PP_compact_economy_auto_modifiers.txt", "gen_sol_pp_compat.py"),
    ("src/sol_pp_compatibility_submod/main_menu/common/static_modifiers/zz_SOL_PP_compact_static_cleanup.txt", "gen_sol_pp_compat.py"),
    ("src/sol_pp_compatibility_submod/main_menu/common/static_modifiers/zz_SOL_PP_compact_war_overlap_cleanup.txt", "gen_sol_pp_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/goods/zz_SOL_MnT_pop_goods.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/script_values/zz_SOL_MnT_market_unit_consumption_values.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/script_values/SOL_cmm_values.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/scripted_effects/zz_SOL_MnT_compat_effects.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/scripted_effects/zz_SOL_MnT_cmm_effects.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/scripted_guis/SOL_cmm_scripted_gui.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/scripted_triggers/zz_SOL_MnT_disabled_triggers.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/prices/zz_SOL_MnT_price_authority.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/cabinet_actions/zz_SOL_MnT_war_cabinet.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/common/generic_actions/zz_SOL_MnT_colonial_actions.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/in_game/gui/location_window.gui", "gen_sol_mnt_compat.py"),
    ("src/sol_mnt_compatibility_submod/main_menu/common/static_modifiers/zz_SOL_MnT_economic_static_authority.txt", "gen_sol_mnt_compat.py"),
    ("src/sol_jtg_compatibility_submod/in_game/common/goods/zz_SOL_JTG_pop_goods.txt",          "gen_sol_jtg_compat.py"),
    ("src/sol_jtg_compatibility_submod/in_game/common/script_values/zz_SOL_market_unit_consumption_values.txt", "gen_sol_jtg_compat.py"),
    ("src/sol_jtg_compatibility_submod/in_game/common/scripted_effects/zz_A_SOL_economy_effects.txt", "gen_sol_jtg_compat.py"),
    ("src/sol_jtg_compatibility_submod/in_game/gui/zz_SOL_economy_local.gui",                   "gen_sol_jtg_compat.py"),
    ("src/sol_jtg_compatibility_submod/in_game/gui/panels/situation/global_living_standard.gui", "gen_sol_jtg_compat.py"),
    ("docs/knowledge/BRIEF.md",                                                                  "gen_brief.py"),
    ("data/demand_price_table.csv",                                                              "gen_demand_csv.py"),
    ("data/index/icons.txt",                                                                     "gen_index.py"),
    ("data/index/scripted_triggers.txt",                                                         "gen_index.py"),
    ("data/index/scripted_effects.txt",                                                          "gen_index.py"),
    ("data/index/static_modifiers.txt",                                                          "gen_index.py"),
    ("data/index/loc_keys_en.txt",                                                               "gen_index.py"),
]


AUTOGENERATED_FILES.extend(
    (f"src/{target}/{relative}", "gen_sol_lshud.py")
    for target in ("stable", "sol_standalone")
    for relative in (
        "in_game/gui/SOL_lshud.gui",
        "in_game/gui/SOL_font_icons.gui",
        "in_game/gfx/interface/sol_proto/sol_living_standard_texticon.dds",
        "in_game/gui/SOL_lshud_glorp_compat.gui",
        "in_game/gui/scripted_widgets/SOL_lshud_scripted_widgets.txt",
        "in_game/common/scripted_effects/D_SOL_lshud_ranking.txt",
        "in_game/common/script_values/SOL_lshud_ranking_values.txt",
        "in_game/gfx/map/map_modes/SOL_map_modes.txt",
        "in_game/common/script_values/SOL_map_values.txt",
        "in_game/gui/SOL_map_tooltips.gui",
        "main_menu/gfx/interface/icons/map_modes/sol_purchasing_power.dds",
        "main_menu/gfx/interface/icons/map_modes/sol_substitution.dds",
        "main_menu/gfx/interface/icons/map_modes/sol_ranking.dds",
        "main_menu/localization/english/SOL_map_modes_l_english.yml",
        "main_menu/localization/simp_chinese/SOL_map_modes_l_simp_chinese.yml",
        "main_menu/localization/english/SOL_lshud_l_english.yml",
        "main_menu/localization/simp_chinese/SOL_lshud_l_simp_chinese.yml",
    )
)


def load(filename: str):
    path = KNOWLEDGE_DIR / filename
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def md_row(*cols: str) -> str:
    return "| " + " | ".join(str(c) for c in cols) + " |"


def _run_gen_index() -> None:
    """Run gen_index.py as a subprocess so indexes are fresh before reading counts."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "gen_index.py")],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        print(f"[WARN] gen_index.py failed: {stderr}")
    elif (result.stdout or "").strip():
        print(result.stdout.strip())


def main():
    _run_gen_index()
    anti_patterns = load_anti_patterns(REPO_ROOT)
    enums = load_valid_enums(REPO_ROOT)

    lines: list[str] = []
    lines.append("# EU5 Knowledge Brief")
    lines.append("")
    lines.append(
        "> **Auto-generated** — do not edit this file directly.  "
    )
    lines.append(
        "> Edit `docs/knowledge/anti_patterns.yaml`, `valid_enums.yaml`, or `PROJECT_OVERVIEW.md`, "
        "then run `$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_brief.py`.  "
    )
    lines.append(f"> Last updated: {date.today()}")
    lines.append("")

    # ── Project overview ──────────────────────────────────────────────────────
    if OVERVIEW.exists():
        overview_text = OVERVIEW.read_text(encoding="utf-8")
        # Skip the H1 title line and the blank line after it; keep everything else.
        body_lines = overview_text.splitlines()
        start = next((i for i, ln in enumerate(body_lines) if ln.startswith("## ")), 0)
        lines.append("\n".join(body_lines[start:]).strip())
        lines.append("")

    # ── Anti-patterns ────────────────────────────────────────────────────────
    lines.append("## Known Anti-Patterns")
    lines.append("")
    lines.append(md_row("Category", "Scope", "Bad Form", "Correct Form", "Notes"))
    lines.append(md_row("---", "---", "---", "---", "---"))
    for p in anti_patterns:
        lines.append(
            md_row(
                p.get("category", ""),
                p.get("scope", ""),
                p.get("bad", ""),
                p.get("correction", ""),
                p.get("notes", ""),
            )
        )
    lines.append("")

    # ── Valid enums ───────────────────────────────────────────────────────────
    lines.append("## Valid Enum Values")
    lines.append("")
    lines.append(md_row("Enum", "Valid Values", "Notes"))
    lines.append(md_row("---", "---", "---"))
    for enum_name, enum_data in enums.items():
        values = ", ".join(enum_data.get("values", []))
        notes = enum_data.get("notes", "")
        lines.append(md_row(enum_name, values, notes))
    lines.append("")

    # ── Quick-ref rules ───────────────────────────────────────────────────────
    lines.append("## Quick Reference Rules")
    lines.append("")
    lines.append("- **3-Step Rule**: Direct edit only if 100% certain → `reference_official_defines/` → `reference_game_files/` + `reference_mods/`")
    lines.append("- **Mandatory Step 2/3** for: `blockoverride` names, `custom_tooltip` keys, `situation_card_common` structure, `location_rank:*`, modifier names, scripted triggers/effects, localization YAML encoding, GUI expressions")
    lines.append("- **Verification format**: output `**Verification** — Step [2/3], Reference: file:line, Quote: \"exact text\"` before any code")
    lines.append("- **Bug fix rule**: Replace syntax with verified form; do NOT remove the feature")
    lines.append("- **Pre-test**: Run `$env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/validate.py --changed` before launching game")
    lines.append("- **Float precision**: EU5 truncates all floats at 5 decimal places; never emit 6+ dp in mod files")
    lines.append("")

    # ── Symbol quick-reference ─────────────────────────────────────────────
    lines.append("## Symbol Quick-Reference")
    lines.append("")
    lines.append("> Read `data/index/<name>.txt` for the full list (one entry per line).  ")
    lines.append("> For icon availability, check `data/index/icons.txt` before using `@icon_name!` inline syntax.")
    lines.append("")
    lines.append(md_row("Category", "Count", "Index file", "Notes"))
    lines.append(md_row("---", "---", "---", "---"))
    index_meta = [
        ("GUI Icons (`@xxx!`)", "icons.txt",            "Use `@name!` in raw_text/text fields and YAML values"),
        ("Scripted Triggers",   "scripted_triggers.txt", "Verify name before using in `trigger = { ... }`"),
        ("Scripted Effects",    "scripted_effects.txt",  "Verify name before using in `effect = { ... }`"),
        ("Static Modifiers",    "static_modifiers.txt",  "Modifier name whitelist; validate.py checks these"),
        ("English Loc Keys",    "loc_keys_en.txt",       "All defined EN keys; cross-check before adding duplicates"),
    ]
    for label, fname, notes in index_meta:
        index_path = INDEX_DIR / fname
        count = "—"
        if index_path.exists():
            count = str(sum(1 for ln in index_path.read_text(encoding="utf-8").splitlines() if ln.strip()))
        lines.append(md_row(label, count, f"`data/index/{fname}`", notes))
    lines.append("")

    # ── Codegen script map ─────────────────────────────────────────────────
    lines.append("## Codegen Script Map")
    lines.append("")
    lines.append(md_row("Script", "Input(s)", "Output(s)", "When to run"))
    lines.append(md_row("---", "---", "---", "---"))
    for script, inputs, outputs, when in CODEGEN_SCRIPTS:
        lines.append(md_row(f"`scripts/{script}`", inputs, outputs, when))
    lines.append("")

    # ── Auto-generated files ───────────────────────────────────────────────
    lines.append("## Auto-Generated Files (do not edit directly)")
    lines.append("")
    lines.append("> These files have `# @AUTOGENERATED` on line 1.  ")
    lines.append("> `validate.py` warns if any of them appear in `git diff --cached`.")
    lines.append("")
    lines.append(md_row("File", "Generator"))
    lines.append(md_row("---", "---"))
    for rel_path, generator in AUTOGENERATED_FILES:
        lines.append(md_row(f"`{rel_path}`", f"`scripts/{generator}`"))
    lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    overview_status = "with overview" if OVERVIEW.exists() else "no overview"
    index_counts = {fname: (INDEX_DIR / fname).exists() for _, fname, _ in index_meta}
    index_status = f", index {'ready' if all(index_counts.values()) else 'missing (run gen_index.py)'}"
    print(f"[OK] Generated {OUTPUT.relative_to(REPO_ROOT)} ({len(anti_patterns)} patterns, {len(enums)} enums, {overview_status}{index_status})")


if __name__ == "__main__":
    main()
