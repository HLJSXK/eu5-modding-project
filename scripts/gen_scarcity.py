#!/usr/bin/env python3
"""
gen_scarcity.py — regenerate all scarcity-tier files (3 shortage + 3 surplus tiers).

6 tiers:
  -3 (Very Cheap): price < 0.40×, weight ×2.00
  -2 (Cheap):      price < 0.65×, weight ×1.50
  -1 (Affordable): price < 0.85×, weight ×1.25
   0 (Normal):     0.85×–1.30×, weight ×1.00  (no list)
  +1 (Mild):       price > 1.30×, weight ×0.75
  +2 (Moderate):   price > 1.70×, weight ×0.50
  +3 (Severe):     price > 2.30×, weight ×0.25

Generates / rewrites:
  effects    → SOL_substitute_effects.txt       (full regen, header preserved)
  indicators → SOL_substitute_good_indicators.txt (full regen, header preserved)
  weights    → SOL_goods_weight_values.txt       (Part 1 string-replace per good)
  loc        → SOL_substitute_goods_l_english.yml (key upsert)

Implementation: delegates to scripts/scarcity/ submodules.
  scarcity/effects_gen.py    — gen_effects_file()
  scarcity/weights_gen.py    — patch_weights_file()
  scarcity/indicators_gen.py — gen_indicators_file(), gen_group_indicators_file()
  scarcity/loc_gen.py        — upsert_localization(), gen_subst_group_loc_keys(), gen_subst_ratio_loc_keys()
  scarcity/gui_gen.py        — _parse_goods_prices(), gen_goods_gui_override_file()

Usage:
    $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_scarcity.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add scripts/ to path so relative imports work when run as a top-level script
sys.path.insert(0, str(Path(__file__).parent))

from scarcity._data import (
    EFFECTS_FILE, WEIGHTS_FILE, INDICATORS_FILE, GROUP_INDICATORS_FILE,
    LOCALIZATION_FILE, LOCALIZATION_FILE_ZH, GUI_OVERRIDE_FILE,
    SCARCITY_SCORE_FILE,
    _write,
)
from scarcity.effects_gen import gen_effects_file, gen_scarcity_score_file
from scarcity.weights_gen import patch_weights_file
from scarcity.indicators_gen import gen_indicators_file, gen_group_indicators_file
from scarcity.loc_gen import (
    NEW_LOC_KEYS_EN, NEW_LOC_KEYS_ZH,
    upsert_localization, gen_subst_group_loc_keys, gen_subst_ratio_loc_keys,
)
from scarcity.gui_gen import _parse_goods_prices, gen_goods_gui_override_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without changing files")
    args = parser.parse_args()
    dry = args.dry_run

    # 0. Parse prices (needed for both indicators and GUI override)
    prices = _parse_goods_prices()

    # 1. Effects file (full regen)
    _write(EFFECTS_FILE, gen_effects_file(), dry)

    # 2. Weights file (Part 1 string-replace per good)
    weights_text = WEIGHTS_FILE.read_text(encoding="utf-8-sig")
    patched = patch_weights_file(weights_text)
    _write(WEIGHTS_FILE, patched, dry)

    # 3. Indicators file (full regen — price-weighted group denominators)
    _write(INDICATORS_FILE, gen_indicators_file(prices), dry)

    # 4. Group indicators file (full regen — fixes "variable never set" engine errors)
    _write(GROUP_INDICATORS_FILE, gen_group_indicators_file(), dry)

    # 5. Localization (upsert new keys; EU5 YAML requires UTF-8 BOM)
    subst_en, subst_zh = gen_subst_group_loc_keys(prices)
    ratio_en, ratio_zh = gen_subst_ratio_loc_keys(prices)
    for loc_file, keys in [
        (LOCALIZATION_FILE,    NEW_LOC_KEYS_EN + subst_en + ratio_en),
        (LOCALIZATION_FILE_ZH, NEW_LOC_KEYS_ZH + subst_zh + ratio_zh),
    ]:
        loc_text = loc_file.read_text(encoding="utf-8-sig")
        loc_new  = upsert_localization(loc_text, keys)
        _write(loc_file, loc_new, dry, encoding="utf-8-sig")

    # 6. GUI override file (full regen)
    _write(GUI_OVERRIDE_FILE, gen_goods_gui_override_file(prices), dry, encoding="utf-8")

    # 7. All-goods scarcity-score scripted effect (separate auto-generated file)
    _write(SCARCITY_SCORE_FILE, gen_scarcity_score_file(), dry)

    if not dry:
        print("\nDone. Run next:")
        print("  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/sync_location_window.py")
        print("  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_ui.py --target tooltips")
        print("  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/validate.py --changed")


if __name__ == "__main__":
    main()
