# AI Tool Workflow Prompt (EU5)

Use the following prompt for AI coding tools in this project:

```text
You are an expert Europa Universalis 5 (EU5) modder. EU5 uses an updated Jomini engine. Do not assume EU4 syntax works.

### Workflow: The 3-Step Resolution Rule
When proposing code edits or generating new scripts, you must evaluate your knowledge and follow this exact sequence:

1. **Direct Edit**: If you are 100% certain about the EU5 syntax (e.g., standard Jomini logic), write the script directly.
2. **Consult Docs**: If you are unsure about a specific `script_value`, `data_type`, trigger, or effect, you MUST read the reference files in the `reference_official_defines/` workspace folder first.
3. **Consult Source Files**: If the answer is not in `reference_official_defines/`, search the `reference_game_files/` and `reference_mods/` workspace folder for real-world implementations before writing the code.

### Mandatory Reference Categories (Step 1 is FORBIDDEN)

For the following syntax categories, you are **never** allowed to rely on memory or inference alone.
You MUST go directly to Step 2 or Step 3 before writing or modifying any code:

| Category | Why Step 1 is forbidden |
|---|---|
| `blockoverride` block names and their allowed child properties | Block names are template-specific; accepted property types differ per block |
| `custom_tooltip` key formats (e.g. dotted suffixes like `.tooltip`) | Suffix rules are not documented; guessing caused a feature to be incorrectly removed |
| `situation_card_common` / `card_common` template structure | Inner block rules are invisible without reading `cards.gui` |
| `location_rank:*` enum values | Enum values are engine-defined; wrong values (e.g. `village`) produce silent failures |
| Any `static_modifier`, `country_modifier`, `location_modifier` name | Modifier names must exist in defines; typos cause silent no-ops |
| Any `scripted_trigger` or `scripted_effect` not defined in this mod | Vanilla names change between patches |
| Localization key format rules (YAML encoding, quote characters) | PDX parser rejects non-ASCII quotes; encoding errors cascade silently |
| GUI expression syntax (`GetVariable`, `.IsSet`, `MakeScope`, etc.) | Expression language is undocumented; wrong patterns produce no visible error |
| Any GUI icon display | Must check `font_icons.gui` for `@xxx!` inline texticon before using widget or custom approach |

### Declarative Verification Requirement

Before writing or modifying any code that falls under the Mandatory Reference Categories above,
you MUST output a verification line in this exact format:

> **Verification** — Step [2/3], Reference: `[file path]:[line number]`, Quote: `"[exact text from source]"`

This line must appear **before** the code block. No code may be written without it.

If you cannot locate a suitable reference, output:

> **Verification** — FAILED. Cannot verify `[syntax in question]`. Reporting to user before proceeding.

Then stop and ask the user for guidance. Do NOT guess.

### Constraints
- NEVER hallucinate or guess Paradox script syntax.
- If you cannot verify a command using the steps above, explicitly tell the user: "I cannot verify this syntax, please check the official wiki or logs."
- If a syntax pattern causes bugs, do NOT remove the feature as a first response. You MUST follow the 3-step rule in order (Direct Edit -> reference_official_defines/ -> reference_game_files/) and replace it with a verified working syntax.
```

## Path Mapping In This Repository

- `docs/` -> project docs and technical notes
- `reference_official_defines/` -> official define/type reference files
- `reference_game_files/` -> vanilla script source files
- `reference_mods/` -> some representative community mods

## Required Behavior For Bug Fixing

- When a previously implemented script/GUI expression fails, the default action is **syntax replacement based on verification**, not feature removal.
- Removal or fallback simplification is only allowed when:
  - the syntax cannot be verified in `reference_official_defines/`, `reference_game_files/` and `reference_mods/`, and
  - the tool explicitly reports this uncertainty to the user.

## GUI Icon Display Priority

When displaying an icon in any UI context, AI tools MUST follow this priority and stop at the first applicable tier:

| Tier | Method | When to use |
|---|---|---|
| 1 | `@icon_name!` inline syntax | Icon exists in `font_icons.gui`; context is `raw_text`/`text`/localization YAML |
| 2 | Icon widget (`icon = { texture = "..." }`) | Standalone widget needed, or icon absent from `font_icons.gui` |
| 3 | From scratch (new `texticon` / new sprite) | Tiers 1 and 2 both inapplicable; must justify explicitly |

Authoritative icon list: `reference_game_files/game/main_menu/gui/shared/font_icons.gui` (180+ entries)

## Documented Violations (Learning Record)

The following violations occurred and informed the Mandatory Reference Categories above:

| Date | Violation | Root cause | Correct behavior |
|---|---|---|---|
| 2026-03 | Removed `custom_tooltip` from event options | Guessed dotted key format was invalid; skipped Steps 2/3 | Read `reference_game_files/`; `ali_qushji_settles.tooltip` confirms dotted keys are valid |
| 2026-03 | Used `location_rank:village` | Guessed enum value; did not check defines | Read `reference_official_defines/`; valid values are `rural_settlement`, `town`, `city` |
| 2026-03 | Placed child `text_single` inside `blockoverride "common_header_text"` | Guessed block accepted child widgets; skipped reading `cards.gui` | Read `cards.gui:1084`; block overrides a `text` property, not a widget container |
| 2026-04 | Used `value = location.local_*` inside a location-scope script value | Assumed `location.` prefix was always required for location variables | `location.` is a navigation link from another scope; inside a location-scope value, reference variables directly without the prefix |
| 2026-04 | Generated script_values with 6-decimal float literals (e.g. `0.084771`) | No awareness of EU5 engine's 5dp precision limit | Round all float literals to ≤5 decimal places in generated and hand-written mod files; engine silently truncates anything beyond the 5th digit |
| 2026-04 | Proposed `datamodel = "[GoodsView.GetGoods]"` inside ContextualTooltipType to filter by key and obtain a Goods datacontext | Assumed GoodsView is a globally accessible object; it is panel-scoped only | No all-goods datamodel exists in tooltip scope; GoodsView is only in goods_overview.gui; no GetGoods('key') string lookup exists anywhere in EU5 GUI |
| 2026-05 | Proposed `multiply_global_variable = { name = X value = 0.95 }` to scale a global variable in-place | Assumed EU5 has a multiply variant analogous to `change_global_variable` | No `multiply_global_variable` effect exists; use hardcoded `set_global_variable` values per case (idempotent) or compute in a local_variable first |
| 2026-05 | Wrote `multiply = global_var:sol_era_coeff` directly in script_values; engine validation pass ran before any on_action and emitted "Failed to fetch variable" / "Got value of type none" errors even with `on_game_start` init wired up | Assumed `on_game_start` was the earliest hook; in fact EU5 evaluates script_values during file-load validation BEFORE any on_action fires | Wrap unguarded global reads: `local_NAME = { value = <default>  if = { limit = { has_global_variable = NAME }  value = global_var:NAME } }`, then `multiply = local_NAME`. on_game_start init is still useful as defense-in-depth but cannot prevent the load-time error alone |
| 2026-05 | Codegen emitted `change_variable = { name = X  value = Y }`; engine logged "change_variable effect [ No operation specified ]" and silently dropped every delta | Mirrored `set_variable`'s `value =` syntax onto `change_variable` without adapting; assumed `value` was a generic write keyword | Use `change_variable = { name = X  add = Y }` (or subtract/multiply/divide). `value =` is reserved for `set_variable` only; `change_variable` requires an operation keyword |
| 2026-05 | Wrote `value = variable:sol_market_scarcity_adj_nobles` in a script_value; engine logged "Failed to find a valid event target link 'variable:NAME'" | Mistook the long form `variable:` (which appears in informal comments) for the actual event-target prefix | EU5's event-target prefix for scope variables is `var:` — short form only. `variable` is only a keyword inside `set_variable` / `change_variable` / `has_variable` blocks (as a field name), never as a `:` -prefixed reference |
| 2026-05 | Cached SOL per-stratum scarcity adjustments as location variables, computed by iterating `every_owned_location` and calling 5×`SOL_compute_scarcity_score_<strata>` per location every January 1; produced ~6.7M conditional checks per Jan-1 frame and reported in-game lag spike | Did not recognise that the 336 checks per stratum effect were all market-keyed (`market ?= { is_target_in_global_variable_list ... }`) and therefore identical for every owned location sharing a market | Cache market-keyed data once per market. For EU5 1.3 SOL, use `global_variable_map` with the market scope as key rather than storing synthetic variables on the market center location. Markets do NOT support direct `set_variable`, but they are valid global map keys. |
| 2026-06 | Stored SOL market consumed-goods flags on `market.location` and read them in GUI via `Location.GetMarket.GetCenterLocation.MakeScope.GetVariable(...)` | Treated the market center location as a convenient per-market cache owner even though the data is keyed by market identity | Use `global_variable_map` for market-keyed SOL caches. Script writes with `remove_from_global_variable_map` followed by `add_to_global_variable_map`, using `key = scope:sol_market_cache`; GUI reads with `GetVariableFromGlobalVariableMap('sol_market_*', Location.GetMarket.MakeScope)`. `GetCenterLocation` is only for cases that truly need the center Location object. |
| 2026-06 | Used `add_to_global_variable_map` alone to refresh an existing key | Assumed `add_to_*_variable_map` overwrites values like `set_variable`; the engine silently keeps the old value when the key already exists | Treat map writes as insert-only: first `remove_from_global_variable_map = { name = X key = scope:Y }`, then `add_to_global_variable_map = { name = X key = scope:Y value = Z }`. |
| 2026-05 | Used block syntax `wine = { value = "SOL_wine_demand" }` in pop_demand good entries; engine loaded only the first good and dropped all subsequent entries plus `category = pop_needs` | Assumed `{ value = ... }` block wrapper was valid for script value references in this context; it had worked in an earlier engine version | pop_demand good entries require plain direct assignment matching the vanilla pattern: `wine = SOL_wine_demand`. Both quoted strings and `{ value = }` block wrappers are broken — only `good = script_value` (no block, no quotes) is accepted |
| 2026-05 | anti_patterns regex `change_variable\s*=\s*\{[^}]*\bvalue\s*=` flagged the legal nested form `change_variable = { name = X  add = { value = Y  multiply = Z } }` as invalid (~73 false positives in `gls_accumulate_panel_stats`) | Used `[^}]*` which doesn't consume `}` but freely crosses `{`, so the scanner reached the inner `value = Y` of the nested `add`-with-operations block | Use `[^{}]*` instead — exclude both `{` and `}` from the span so the regex stops at any brace boundary and only matches top-level `value = ` keys inside the change_variable block |
| 2026-05 | EU5 1.2 emitted `Event #sol_ae.X is missing an outcome in events/SOL_economy_events.txt` for all 7 SOL events on game-load | 1.2 added a new validator (`event_database.cpp:648`) that requires every event block to declare a top-level `outcome = ...` field; events written under 1.1 did not need it | Add `outcome = neutral` (or `good` / `bad` / `positive` / `negative` to match flavor) under `desc = ...` in every event. Vanilla `ages_of_eu.1` at `reference_game_files/game/in_game/events/ages.txt:7` uses `outcome = neutral` for tooltip-only notification events, which fits the SOL `sol_ae.*` and `sol_migration.*` style |
| 2026-06 | Treated the EU5 1.3 `local_pop_demand` migration as a reason to remove the SOL `demand_add` baseline | Confused the monthly runtime multiplier with the calibrated baseline data; missed that project multipliers are calibrated against corrected `demand_add` from `data/target_demand.csv` | Keep `data/target_demand.csv -> src/stable/in_game/common/goods/z_SOL_pop_goods.txt` as the protected calibrated `demand_add` baseline. Apply `local_pop_demand` only as the monthly location-level multiplier, and remove only the obsolete pop_demands/substitute/scarcity/Engel runtime chain |
