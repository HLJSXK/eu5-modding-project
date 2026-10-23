"""Generate SOL substitution pulse effects, cached values and country auto modifiers."""
import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gen_market_unit_consumption import _load_good_rows
from sol_substitution import CORE, render_country_runtime, render_location_spending, render_modifiers, render_values

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--target", choices=("stable", "sol_standalone", "all"), default="all")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    targets = ("stable", "sol_standalone") if args.target == "all" else (args.target,)
    rows = _load_good_rows()
    files = {
        "in_game/common/scripted_effects/C_SOL_substitution.txt": render_country_runtime(rows) + render_location_spending(rows),
        "in_game/common/script_values/SOL_country_substitute_values.txt": render_values(),
        "in_game/common/auto_modifiers/SOL_substitute_global_modifiers.txt": render_modifiers(),
        "in_game/common/scripted_triggers/SOL_substitution_triggers.txt": 'sol_substitution_is_on = {\n\tsol_sol_is_on = yes\n\tOR = { NOT = { has_global_variable_map = cmm } has_global_variable = sol_substitution_enabled }\n}\n',
    }
    # Names carry no colon: breakdowns split a name at the colon and right-align the rest.
    for language, label, description in (
        ("english", "Goods substitution (${good}$)", "Adjusts population demand for ${good}$ through goods substitution."),
        ("simp_chinese", "商品替代（${good}$）", "商品替代调整${good}$的人口需求。"),
    ):
        content = f"l_{language}:\n"
        for good in CORE:
            content += f' AUTO_MODIFIER_NAME_sol_substitute_{good}: "{label.format(good=good)}"\n'
            content += f' AUTO_MODIFIER_DESC_sol_substitute_{good}: "{description.format(good=good)}"\n'
        files[f"main_menu/localization/{language}/SOL_substitution_modifiers_l_{language}.yml"] = content
    failed = False
    for target in targets:
        for relative, content in files.items():
            if target == "sol_standalone" and "scripted_triggers" in relative:
                content = "sol_substitution_is_on = { always = yes }\n"
            path = ROOT / "src" / target / relative
            data = b"\xef\xbb\xbf" + content.encode("utf-8")
            if args.check:
                ok = path.exists() and path.read_bytes() == data
                print(f"[{'OK' if ok else 'FAIL'}] {path.relative_to(ROOT)}")
                failed |= not ok
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                print(f"[WRITE] {path.relative_to(ROOT)}")
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
