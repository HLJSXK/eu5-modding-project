# SOL HUD data and ranking implementation

Updated 2026-10-23. Stable and standalone register `gui/SOL_lshud.gui = sol_lshud4_root`: a 570×36 four-section row below the nine left-panel buttons. Compatibility submods inherit the base HUD and country runtime. The first-section contract supersedes the historical income display; see `SOL_Topbar_PCI_Removal_Boundary_20261023.md`.

## Living standard and population

The wrapper resets country SOL and population totals, then both full and raw-only solver paths call `sol_ls_accumulate_country_living_standard` inside their existing owned-location pass. That one accumulator collects five strata's SOL totals and population weights; commoners group peasants, laborers and soldiers. No additional location traversal is introduced. National income accumulation, PCI publication and their six per-location income writes are removed. Location net-income caches remain inputs to liquid funds and demand; `gls_income_*` panel diagnostics remain separate.

Each estate's SOL is `max(0, flat bonuses + max(0, 1 + summed percentage bonuses) × annual liquid funds per thousand people)`. Country SOL is population weighted. `sol_ls_annualization_factor = 12` belongs to `SOL_living_standard_values.txt`. An absent population removes current SOL; HUD sections 1/4 and the country ranking tooltip then show pending content.

Section 1 displays `sol_ls_sol|1`, its tier badge and SOL annual change, without a coin or additional unit icon beside the badge. Tooltip 1 shows a tier-only heading, large SOL amount, formula, and `Estate | Population (k) | Living standard | Annual change`. Columns and padding fill 460 units. A dedicated house icon, `@sol_living_standard!`, accompanies SOL amounts in this tooltip and the ranking tooltip. `SOL_font_icons.gui` registers it with 20×20 size, offset `{ 0 4 }`, fontsize 16; that filename also permits the existing renderer's `*font_icons*.gui` discovery. The approved DDS ships in both targets.

## Annual history

After current SOL is finalized, `sol_ls_finalize_country_living_standard_yoy` compares it with the same month exactly one year earlier, retaining the prior-year denominator during repeated refreshes and honoring the recorded day. Samples use **new** `sol_ls_sol_sample_<month>_*` names. Legacy `sol_ls_sample_*` held income and must never supply SOL denominators. Old save variables remain untouched and unread.

Current SOL displays on the first solve. Missing, skipped-year or not-yet-due comparisons clear `sol_ls_sol_prev*`, `sol_ls_sol_yoy*` and `sol_ls_sol_yoy_class*`; absent estates are not sampled. Zero prior SOL gives zero change without division. Trend boundaries remain ≥5%, >0, >−5% and ≤−5%, with zero in class −1. Building bonuses affect this change because they affect SOL. Human and AI sampling retain their existing solve cadence.

## Ranking, maps and compatibility

January and explicit global refreshes rank current `sol_ls_sol` without requiring annual history. Population-weighted world SOL sets tiers: strictly below 0.75× average is low; strictly above 1.33× is high. Country/estate ranks, percentiles, top-country and neighbour caches remain unchanged by this migration. Tooltip 4 and country map tooltip 4 now check the displayed country's SOL readiness.

The four sections retain hover previews and left-click map selection. Section 2, purchasing-power map, location tooltip and situation bars continue to display purchasing power. Substitution, spending and the Glorp compatibility shim retain their existing behavior.

## Ownership and verification

- `living_standard_4sections/build.py` owns active GUI and Chinese text. Older HUD/leftrow GUI prototypes are historical; their shared fixtures use SOL.
- `gen_sol_lshud.py` owns both targets' HUD, icon registration/asset, bilingual localization, ranking and map outputs. Retired HUD helpers and localization keys are removed.
- `sol_living_standard_source.py` owns SOL, population accumulation and annualization. The historical `sol_lshud_income_source.py` module now emits only SOL history/trends through the economy generator.
- `test_sol_lshud_income.py` executes SOL history, calendar/day guards, repeated refreshes, zero baselines, absent populations, old-save isolation and modifier-driven change. Ranking, living-standard, map, cadence and UI suites cover their respective contracts.

Regenerate both targets, run those suites and `validate.py --changed`, using the direct EU5 Python environment. `SOL_LSHUD_PREVIEW_OUT` retains bilingual shipped-target previews under `ai_gui_assessment/images/sol_topbar_20261023/`.

Offline fixtures do not establish engine fixed-point behavior, native hover, input pass-through, icon baseline alignment, UI scaling or actual Workshop load order. Those remain in-game acceptance items.
