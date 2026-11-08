# SOL direct wealth input (2026-11-09)

SOL reads location wealth directly from `location_potential_tax_base` (EU5 1.4).
The five estate income pools are `W - T * estate_tax_rate`, where W is wealth
and T is actual `location_tax_base`. Existing estate shares, serfdom transfers,
building maintenance, nonnegative net-income clamps and solver consumers remain
in place. Actual tax-base displays and taxed components retain tax-base semantics.

`local_control_loss_component` remains a compatible `W - T` helper.
`local_gdp_from_taxbase_control_display` remains a public alias of direct wealth.
`local_effective_control` displays actual control with no one-percent floor.
Stable and standalone own identical handwritten core values; PP, M&T and JTG
compatibility layers inherit them without overriding these values.

The retained demand simulator engine and its archived UI accept explicit `wealth`
and `tax_base` independently. Bundled preset wealth was migrated once from each
historical tax-base/control pair to preserve the old scenario value; it is not
an observed engine read. New presets must supply wealth explicitly. The current
v3 app imports savings-curve helpers and does not construct these scenarios.

Evidence: shared `location_wealth_inferred_from_tax_base_control` records the
1.4 Beta Added Value, vanilla raid script and tutorial/interface localization.
`scripts/test_sol_wealth.py` executes the real base script values for all estates
and checks normal, sub-one-percent and zero control; positive wealth with zero
tax base; zero wealth; tax rates including distinct estate rates; unchanged
maintenance deductions; inherited compatibility definitions; and tool inputs.

Native acceptance remains: load EU5 1.4, compare wealth/tax-base/control and
purchasing power in positive-, low- and zero-control locations, verify fresh
monthly/yearly solver caches, and check the overview at zero control. Offline
arithmetic does not prove native refresh timing or fixed-point rounding.


## Offline validation outcome

`test_sol_wealth.py`: 4 tests passed. `test_sol_economy_cadence.py`: 17
passed. `test_sol_spending_cache.py`: 8 passed. `validate.py --changed`
validated both changed source files without errors. Both knowledge registries
have unique IDs and required metadata; both-root loaders yield 375 shared /
433 merged rules and two enum families. Both briefs were regenerated.

Generation checks pass for PP, M&T, messages and both location windows. The
full-chain check stops at existing stable/standalone `market_tooltips.gui`
drift: the generator uses `TooltipStringPairList` where checked-in outputs use
`TooltipScrolledStringPairList` (line 4084). Independent JTG generation check
finds the same existing market-tooltip drift. These outputs equal HEAD and
were left unchanged. All preceding shared/economy generator checks passed.

The related `test_sol_lshud_income.py` suite has 13 passing tests and one
pre-existing failure: `test_both_solver_paths_accumulate_inside_existing_preparation_pass`
expects `sol_ls_reset_country_living_standard` as the first wrapper call, but
existing generated effects start with `sol_oos_trace_country`. Test source
(newline-normalized) and both effect files equal HEAD; this unrelated failure
was retained for separate work.
