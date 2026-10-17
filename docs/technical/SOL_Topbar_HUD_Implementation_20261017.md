# SOL HUD row data and ranking implementation — 2026-10-17

The 2026-10-17 topbar badge design was replaced the following day by the left-row UI documented in `ai_gui_assessment/prototypes/living_standard_leftrow/DESIGN.md`. Stable and standalone register `gui/SOL_lshud.gui = sol_lshud_leftrow_root`. The compatibility submods inherit the stable UI and country runtime. The contracts below include the 2026-10-18 correction separating current income availability from YoY history.

## Income and history

The existing solver's initial owned-location traversal calls `sol_ls_accumulate_country_income` in both its full and raw-only paths. The wrapper resets and finalizes country totals; no extra location iterator is introduced. Cached `sol_location_<estate>_net_income` values already deduct building maintenance and floor each estate at zero. Their sum, `sol_location_total_income`, is the HUD total. This differs deliberately from the old `local_sol_total_income` display helper, which floors after allowing losses to offset other estates. Existing panel values are preserved.

Population uses the five established strata, with commoners grouping peasants, laborers and soldiers; slaves remain outside that established SOL measure. Population is in thousands, income is monthly gold, and the named annualization factor is twelve. Displayed PCI is therefore annual net gold per thousand people. No arbitrary scaling to the prototype's invented 1–3 figures is applied.

Estate income figures include the native `@gold!` ducat icon. Their diverging YoY bars saturate at ±20% (±10% fills half of the corresponding side); the numeric YoY remains uncapped. Both language captions use the same ±20% range.

Human samples follow the existing monthly solves. AI follows its existing annual anniversary cadence, or monthly cadence when stable's frequency setting requests it. Every solve publishes current PCI immediately, including the first sample. Each month has a dated income baseline and a retained prior-year baseline. Only previous income, YoY and trend require the same month, exactly the preceding year and a day no later than the current day. Repeated refreshes within a month preserve the prior-year denominator. Missing comparisons clear those three public variables for every estate and the total; the GUI shows no-prior-year-data placeholders while retaining current income and rank. Previous income at zero yields zero change rather than dividing by zero. Trend boundaries remain ≥5%, >0, >−5%, and ≤−5%, with zero in the contract's −1 class.

## World ranking

`sol_ls_recalculate_world_ranking` runs in January in the existing global monthly situation callback and after explicit global full refreshes, including startup/load and the manual recalculation resolution. The manual action hides ranking writes from its effect tooltip. It reads country caches only. Eligible countries need population, territory, a current PCI and positive cached SOL population; no YoY history is required. Thus an April 1337 start can rank at initialization and in January 1338, even though its first same-month YoY arrives in April 1338. A census computes count and population-weighted world income; one `ordered_country` pass, using `sol_ls_pci_order_value` and `max = global_var:sol_ls_rank_count`, writes all ordinal ranks, percentiles, top-ten country slots and two neighbours in each direction. Equal incomes receive consecutive ordinal ranks in the engine's tie order.

Before rebuilding, old rank/tier/neighbour values and all top-ten slots are cleared. Single-country percentile is zero. Threshold equality stays in the middle tier: low is strictly below 0.75×world income, high strictly above 1.33×world income. An all-zero world is therefore middle tier and the GUI guards its bar denominator. Before the first ranking exists, income can display with separate ranking/tier pending text.

## Ownership and checks

- `scripts/gen_sol_lshud.py`: GUI, registration, Chinese/English localization, ranking effects and named unit/threshold values for both independent targets; part of `gen_sol_chain.py`.
- `scripts/sol_lshud_income_source.py`: country income/history effects, emitted through `gen_sol_economy_effects.py`.
- `scripts/sol_lshud_ranking_source.py`: world ranking effects and named ranking values.
- `scripts/test_sol_lshud_income.py`, `scripts/test_sol_lshud_ranking.py`: execute emitted effects against offline scope fixtures, including units, full-year guards, repeated refresh, net-income maintenance, sorting, ties, all ranks, neighbours, thresholds and stale-reference removal.
- `scripts/test_sol_lshud_ui.py`: renders the shipped GUI for both targets and languages using installed game assets and invented country values; `SOL_LSHUD_PREVIEW_OUT` retains images.

Run the direct EU5 environment interpreter for the three HUD tests, `test_sol_economy_cadence.py`, `gen_sol_chain.py --check`, and `validate.py --changed`. Representative Chinese/English and pending-state previews are saved under `ai_gui_assessment/images/living_standard_hud_implementation/`.

Offline execution uses floating-point fixtures, not the engine's fixed-point implementation. In-game acceptance is still required for scripted-widget layer order, empty-area input pass-through, native hover, different graphical cultures, UI scale, and actual annual scheduling. No in-game pass is claimed.

The regression suite includes 12 income tests, 14 ranking/entry-point tests (including the first January without YoY), 6 GUI tests covering 32 bilingual target/state combinations, 10 existing economic-cadence tests, and 4 validator tests. Current-income/no-YoY previews are saved under `ai_gui_assessment/images/living_standard_immediate_income/`. The validator's generic-action slot rule is restricted to generic actions so the manual resolution's native `recipient`/`vote` selectors remain accepted; invalid custom generic-action slots still fail.
