# SOL substitution: cached country auto modifiers

Updated: 2026-10-23 (Asia/Shanghai).

The 56 country goods modifiers are generated under `in_game/common/auto_modifiers/`.
`sol_substitute_<good>` has category `country`, includes non-real countries as the
previous scripted grants did, and uses `sol_substitute_<good>_scale`. That script
value returns zero when disabled or when its cache is missing; otherwise it reads
only `sol_sub_size_<good>`. Neither the auto modifier nor its scale reads prices,
population, markets, variable maps or aggregate modifiers.
Zero deltas are removed after effective spending and maximum-size statistics
have consumed them. Missing size caches make the corresponding potential false,
so neutral goods do not activate zero-strength auto modifiers. The engine may
still check each definition's potential; this does not eliminate those checks.

The existing `sol_refresh_country_substitution` runs before the country demand
solver: monthly for humans and normal-cadence AI, yearly on the country's own
anniversary for reduced-frequency AI. Start/load initialization and explicit
setting/manual refresh paths retain immediate recomputation. It aggregates
population by market and stratum, evaluates subscribed whole-group baskets and
overlaps with algorithm A, then publishes:

```
external = max(1 + total_goods_modifier - active_cached_substitution_delta, 0)
multiplier = target_spending / baseline_spending  # 1 when baseline is zero
sol_sub_size_<good> = external * (multiplier - 1)
sol_good_effective_<good> = max(external + sol_sub_size_<good>, 0)
```

The first line reads the same guarded scale used by the auto modifier before
overwriting that good's cache. This prevents the previous substitution delta from
feeding back into the next scheduled solve. Changes to external modifiers wait
for that solve; frequent auto reevaluation continues to read the previous result.
The seven country-adjusted market spending totals retain their owner isolation
and are invalidated after refresh or cleanup.

Cleanup removes the caches, so auto scales immediately become zero. A disabled
refresh retains only external-demand spending for the ordinary SOL solver.
Static definitions and all explicit substitution grants/removals are deleted,
along with the unused apply effect, snapshot checker, per-location snapshots and
live/request readbacks. There is no migration for the previous implementation.
The enabled-refresh counter and its `sol_sub_perf_human` control flag remain for
save diagnostics. The save report can still inspect historical dirty fields,
but the new runtime does not produce them.

Stable and standalone share generated definitions and values. PP regenerates its
country runtime with lumber excluded from groups and victuals neutral; JTG inherits the base runtime; M&T regenerates its country runtime with
its calibrated quantities and prices. Both retain their spending overrides.
Both languages generate `AUTO_MODIFIER_NAME_sol_substitute_<good>` and
`AUTO_MODIFIER_DESC_sol_substitute_<good>`. Bare static-modifier localization
keys are removed. The current vanilla `auto_modifiers_l_english.yml:161-162`
contains both name and description keys; the older shared-registry claim that
auto modifiers have no description keys is outdated for this reference corpus.

Source evidence: vanilla `auto_modifiers/readme.txt` documents `category`,
`requires_real`, `potential_trigger` and `scales_with`; `country.txt:331-337`
demonstrates a script-value scale. The official `types/industry_types.txt:10`
documents the generated `global_<good>_pop_demand` modifier family.

Offline regression tests execute generated pulse effects and auto definitions,
compare mixed-market/stratum results with the independent oracle, repeatedly
evaluate all auto scales while rejecting economic reads or writes, and cover
missing caches, toggles, external offsets, self-accumulation, spending isolation
and scheduling. These float fixtures do not establish EU5 demand refresh timing,
engine invalidation behavior or intermediate fixed-point rounding; those require
in-game acceptance.
