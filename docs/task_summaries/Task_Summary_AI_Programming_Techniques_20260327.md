# Task Summary: AI Programming Techniques (2026-03-27)

## Scope

This note summarizes practical AI-assisted programming techniques validated during this session, focused on EU5 script modding.

## 1) Start With Engine-Accurate Baseline Research

- Always confirm vanilla keys and scope before implementing formulas.
- Typical workflow:
  - locate original key usage in `reference_game_files/game/in_game/common/**`
  - confirm whether a value is trigger-only, script-value, or UI-only getter
  - only then design the mod-side implementation

Why it worked:

- Prevented incorrect key choices and reduced trial-and-error.
- Example: distinguishing `stability_cost` vs `stability_investment` usage by checking vanilla references first.

## 2) Prefer Dynamic Auto Modifiers For Runtime Scaling

- Use `common/auto_modifiers/*.txt` when a value must react continuously to game state.
- Pattern:
  - define an always-on modifier with `potential_trigger = { exists = yes }`
  - compute dynamic magnitude via `scales_with`
  - apply effect key with unit coefficient (e.g., `stability_cost = -1`)

Why it worked:

- Keeps behavior reactive without event spam.
- Matches existing engine patterns used in vanilla `country.txt` auto modifiers.

## 3) Translate Formulas Into Engine-Safe Arithmetic

Target formula style in design docs often needs rewriting for script constraints.

- Original math: `0.05 - 0.05/(x+1)`
- Engine-safe strategy:
  - avoid invalid nested expressions where parser rejects them
  - if needed, move math to `script_values` and reference from auto modifier

Why it worked:

- Avoided parser errors around nested arithmetic in `scales_with`.

## 4) Treat Scope As A First-Class Design Constraint

Most script failures came from scope mismatch rather than arithmetic itself.

- Validate each variable's expected scope before use.
- Example pitfall fixed in session:
  - `cultural_tradition` is culture-scoped, not country-scoped.
  - Correct access required culture pathing (`root.culture...`) with existence checks.

## 5) Add Defensive Existence Guards

When reading linked scopes (`owner`, `culture`, etc.), guard first.

- Pattern:
  - `if = { limit = { exists = ... } ... }`
  - provide safe default (`value = 0` or neutral multiplier)

Why it worked:

- Eliminated invalid-object and unset-scope runtime errors.
- Prevented `none`-typed values from flowing into auto modifier calculations.

## 6) Decouple Compute From Apply

Use two layers when complexity increases:

- compute layer: `common/script_values/*.txt`
- apply layer: `common/auto_modifiers/*.txt`

Why it worked:

- Easier debugging and reuse.
- Keeps auto modifier definitions compact and readable.

## 7) Keep Localization In Sync With New Auto Modifiers

For every new auto modifier key, add both:

- `AUTO_MODIFIER_NAME_<modifier_key>`
- `AUTO_MODIFIER_DESC_<modifier_key>`

in both language files used by the mod.

Why it worked:

- Avoided tooltip placeholders and improved in-game diagnosability.

## 8) Validate Every Change End-To-End

Use build/deploy after each meaningful edit batch.

- Command used repeatedly: `build.bat`
- Validate not only compile success but also log cleanliness in game runtime.

Why it worked:

- Caught integration issues early.
- Confirmed packaging/deployment path remained healthy.

## 9) Apply Minimal, Reversible Patches

- Prefer small targeted edits over broad rewrites.
- Preserve existing file structure and naming conventions.
- Avoid unrelated formatting changes.

Why it worked:

- Reduced regression risk in a large script surface area.
- Made follow-up debugging straightforward.

## 10) Debug Loop Used In This Session

1. Read error log and extract exact file/line.
2. Verify original engine behavior in `reference_game_files`.
3. Fix one root cause at a time (scope, type, arithmetic, then localization).
4. Rebuild and redeploy.
5. Recheck logs for next blocker.

This loop was consistently effective for resolving chained Jomini script errors.

## Reusable Checklist

Before shipping a new scripted mechanic:

1. Confirm target key exists in vanilla and supports intended context.
2. Confirm each variable scope (`country`, `culture`, `location`, etc.).
3. Add `exists` guards for all linked scopes.
4. Keep auto modifier arithmetic parser-safe.
5. Move complex math to `script_values` when needed.
6. Add localization (name + description, all languages used).
7. Run build/deploy and inspect runtime logs.
