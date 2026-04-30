# EU5 Modding Project — Claude Instructions

## Session Start

For any non-trivial task, read `docs/knowledge/BRIEF.md` first. It is a compact summary of all known EU5 gotchas, valid enums, and scope rules. This avoids re-exploring docs for patterns already discovered.

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

## Critical EU5 Gotchas

- **Location `auto_modifiers` are NON-FUNCTIONAL** — use `TRY_REPLACE` in `main_menu/common/static_modifiers/` with `game_data = { category = location }` instead
- **`location_rank` enum** — only 3 valid values: `rural_settlement`, `town`, `city` (EU4 names like `village` cause silent failures)
- **Localization YAML** — must be UTF-8 BOM (not plain UTF-8); only straight ASCII double-quotes `"` are valid
- **`custom_tooltip`** — never remove it; dotted suffix format IS valid in event options; verify key format before changing
- **Pre-test validation** — run `python scripts/validate.py --changed` before launching the game

## Declarative Verification Requirement

Before writing code that falls under the above categories, output this line first:

> **Verification** — Step [2/3], Reference: `[file:line]`, Quote: `"[exact text from source]"`

If no reference is found:

> **Verification** — FAILED. Cannot verify `[syntax]`. Asking user before proceeding.

Then stop. Do not guess.

## Bug Fix Rule

When a script/GUI pattern causes a bug: verify and replace with correct syntax. Do NOT remove the feature. Removal is only allowed if Steps 2 and 3 both fail to find any reference, and the user is explicitly told.

## Python Script Requirements

Every new Python script in `scripts/` **must** include the following block immediately after the stdlib imports, before any module-level code:

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

`import sys` must also be present (add it if not already there). This is mandatory because Claude's Bash tool and Stop hooks run scripts via a non-TTY pipe; Python then falls back to the system locale encoding (GBK on Chinese Windows), causing `UnicodeEncodeError` for any non-ASCII output.

Also, always run scripts via `conda run -n eu5 python scripts/...` — never bare `python`.

## Path Mapping

- `docs/` — project docs; full workflow guide at `docs/guides/AI_Tool_Workflow_Prompt.md`
- `docs/knowledge/` — structured anti-patterns and enum whitelists; `BRIEF.md` is the compact session reference
- `reference_official_defines/` — official define/type reference files
- `reference_game_files/` — vanilla script source files
- `reference_mods/` — community mod examples

## Knowledge Capture

Knowledge capture is triggered by **either** of the following:

- You used Step 2 or Step 3 verification and discovered a new pattern.
- You fixed a runtime engine error (from `error.log` or in-game logs) that revealed an undocumented EU5 engine behavior — regardless of whether Steps 2/3 were consulted.

When triggered, do ALL of:

1. Add an entry to `docs/knowledge/anti_patterns.yaml` (copy the format of existing entries).
2. Add a row to the "Documented Violations" table in `docs/guides/AI_Tool_Workflow_Prompt.md`.
3. Update `docs/technical/EU5_Modding_Knowledge_Base.md` if the pattern is broadly applicable.
4. Run `python scripts/gen_brief.py` to regenerate `docs/knowledge/BRIEF.md`.

For minor discoveries (single modifier name, single typo fix), steps 1 and 4 only.

**Do not wait for the user to ask.** Knowledge capture must happen in the same response as the fix, before the task is marked complete.
