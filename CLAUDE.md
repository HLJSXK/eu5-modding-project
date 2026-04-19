# EU5 Modding Project — Claude Instructions

## EU5 Syntax Rules

EU5 uses the Jomini engine. Do NOT assume EU4 syntax works.

## The 3-Step Resolution Rule

When writing or modifying EU5 scripts, follow this sequence:

1. **Direct Edit** — only if you are 100% certain about the syntax.
2. **Consult Docs** — read `reference_official_defines/` first if unsure.
3. **Consult Source** — search `reference_game_files/` and `reference_mods/` if Step 2 is insufficient.

## Mandatory Reference Categories (Step 1 FORBIDDEN)

For the categories below, you MUST go to Step 2 or 3 before writing any code. No exceptions.

- `blockoverride` block names and their allowed child properties
- `custom_tooltip` key formats (dotted suffixes, etc.)
- `situation_card_common` / `card_common` GUI template structure
- `location_rank:*` enum values
- Any `static_modifier`, `country_modifier`, `location_modifier` name
- Any `scripted_trigger` or `scripted_effect` not defined in this mod
- Localization YAML encoding and quote character rules
- GUI expression syntax (`GetVariable`, `.IsSet`, `MakeScope`, etc.)
- `auto_modifier` blocks: all structural keys (`category`, `type`, `icon`, `requires_real`, `potential_trigger`, `scales_with`, `limit`, `hide_effects`, `alert`) and every modifier effect name inside the block — Reference: `reference_official_defines/types/auto_modifiers.txt`

## Declarative Verification Requirement

Before writing code that falls under the above categories, output this line first:

> **Verification** — Step [2/3], Reference: `[file:line]`, Quote: `"[exact text from source]"`

If no reference is found:

> **Verification** — FAILED. Cannot verify `[syntax]`. Asking user before proceeding.

Then stop. Do not guess.

## Bug Fix Rule

When a script/GUI pattern causes a bug: verify and replace with correct syntax. Do NOT remove the feature. Removal is only allowed if Steps 2 and 3 both fail to find any reference, and the user is explicitly told.

## Automated Validation

Before committing any script changes, run the static validator (no game load required):

```bash
python tools/validator/eu5_validator.py
```

Fix all **errors** before committing. Address **warnings** when time permits.

If you discover a new AI error pattern during development:

1. Note which Mandatory Reference Category was violated (or add a new one above).
2. Run `python tools/doc_updater/update_knowledge.py` to record the violation.
3. Commit the updated `docs/guides/AI_Tool_Workflow_Prompt.md`.

## Path Mapping

- `docs/` — project docs; full workflow guide at `docs/guides/AI_Tool_Workflow_Prompt.md`
- `reference_official_defines/` — official define/type reference files
- `reference_game_files/` — vanilla script source files
- `reference_mods/` — community mod examples
