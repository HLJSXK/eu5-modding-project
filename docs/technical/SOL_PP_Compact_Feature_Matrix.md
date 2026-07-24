# SOL-PP Compact Feature Matrix

Date: 2026-07-24

## Stack Contract

Required load order:

1. Community Mod Framework
2. Prosper or Perish
3. Full Standard of Living
4. SOL-PP Compact Compatibility Submod

The compatibility submod is the final rules layer. PP owns shared price values;
SOL price changes survive only when PP does not modify the same price object.

## Retained SOL Features

| Feature | Final compact behavior |
| --- | --- |
| Pop demand | Income-based monthly `local_pop_demand` remains active. PP `victuals` is included and lumber remains at PP's zero pop demand. |
| UI | Location and Living Standard panels include `victuals`; SOL situation and map displays remain active. |
| Age escalation | Only `global_build_buildings_efficiency`, `city_upgrade_cost_modifier`, and `town_upgrade_cost_modifier` remain. |
| Low control | SOL's `inverse_control` construction-efficiency penalty remains additive. |
| Base tax | Default -15% tax efficiency remains CMF-adjustable. |
| Difficulty and AI recovery | SOL's difficulty tax-bonus adjustments remain toggleable, and AI devastation recovery remains controlled by the `ai_pr` slider. |
| Diplomacy and stability | Used diplomatic capacity affects diplomatic spending; cultural tradition reduces stability investment cost. |
| War and expansion | War exhaustion, total/capital occupation pressure, wartime cabinet restriction, hostile-troop/raiding/razing trauma, colonial restrictions, and the 30-favor call-to-war cost remain. PP alone owns the shared blockade, siege, occupation, and looting location modifiers. |
| Prices | Gold-transfer scaling and non-conflicting advisor, commander, religious, diplomatic, and action prices remain. Shared roads and institution prices resolve to PP. |

## Removed SOL Features

| Removed feature | Enforcement |
| --- | --- |
| GDP-to-development | The CMF setting is removed and `sol_gdp_dev_is_on` is hard-disabled. |
| SOL base location/RGO rebalance | The compatibility layer inverses SOL's `location_base_values` delta, leaving PP's independent delta intact. PP's `TRY_REPLACE` definitions already own `total_population` and `raised_levies`. |
| SOL winter and Little Ice Age balance | Generated inverse injections remove only SOL deltas, retaining PP additions. |
| Age prosperity, food, and RGO expansion scaling | Compact replacements contain only the three retained age fields. Tooltip modifiers use the same reduced field list. |
| SOL blockade, siege, occupation, and looting location deltas | Generated inverse injections remove SOL's fields from the four shared modifiers, leaving vanilla plus PP. |

## Shared Price Resolution

| Price | Resolution |
| --- | --- |
| `embrace_institution` | PP's later `TRY_REPLACE` remains final. |
| Four road prices | No compatibility price file is emitted. Within the shared `TRY_INJECT` operation type, `pp_road_gold_adjustments.txt` loads after `A_SOL_economy_prices.txt`, so PP's repeated `gold` fields replace SOL's. |
| All other SOL price keys | Retained because the checked-in PP reference does not modify those keys. |

## CMF UI Whitelist

The compatibility layer replaces full SOL's `sol_register_cmf_mod` effect. CMF
rebuilds each group's setting list during registration, so settings omitted by
the compact registration also disappear when an older save is loaded.

Visible settings: `sol_on`, `sol_map`, `as_on`, `bte`, `ae`, `cts`, `ds`,
`difficulty`, `ai_pr`, `hw_on`, `iwe`, `hwe`, and `rwe`.

Hidden settings: `gdp_dev`. Its callback is absent and its gameplay trigger is
also hard-disabled, so UI and runtime behavior cannot diverge.

## Verification Boundary

`scripts/gen_sol_pp_compat.py --check` verifies generated source consistency
against the checked-in full SOL and PP references. `scripts/validate.py --changed`
checks static syntax and project invariants. A combined in-game load and runtime
log check is still required before claiming runtime compatibility.

The generated scripted-effect layer contains explicit `REPLACE` blocks only for
`sol_refresh_market_pop_demand_maps` and `gls_accumulate_panel_stats`. Its
script-value layer adds only the six nonzero PP `victuals` constants, avoiding
duplicate full-SOL database keys.
