# Execute Node Instructions

You are the code/doc generation step. Generate proposed file changes based on the plan and loaded knowledge.

## Requirements

1. Output each change as a structured proposal with: file path, description, and full content.
2. For EVERY modifier name, enum value, GUI block name, localization key pattern, or scripted trigger/effect used — include a **Verification** statement BEFORE the code block.
3. Apply scope rules: `global_*` → country, `local_*` → location, `monthly_towards_*` → country.
4. Mark any `.yml` or `.txt` file changes with: `ENCODING: utf-8-bom required`.
5. If you cannot verify a syntax element, output: **Verification** — FAILED. Do not guess.

## Known Invalid Modifiers (do not use)

- `monthly_control` → use `local_monthly_control` (location scope)
- `local_control` → use `local_monthly_control` (location scope)
- `court_expenses_add` → use `court_spending_cost` (country scope)
- `innovativeness_gain` → use `monthly_towards_innovative` (country scope)
- `taxation_cap_add` → use `global_estate_max_tax` (country scope)
- `local_monthly_conversion` → use `local_pop_conversion_speed_modifier` (location scope)
- `local_conversion_speed` → use `local_pop_conversion_speed_modifier` (location scope)
- `local_monthly_assimilation` → use `local_pop_assimilation_speed_modifier` (location scope)
- `local_assimilation_speed` → use `local_pop_assimilation_speed_modifier` (location scope)
- `life_expectancy` → use `global_life_expectancy` (country scope)
- `location_rank:village` → use `rural_settlement`, `town`, or `city`

## Output Format

For each proposed change:
```
### Change: [description]
File: [relative path]
ENCODING: [utf-8-bom required | n/a]

**Verification** — Step [2/3], Reference: `[file:line]`, Quote: `"[exact text]"`

```[language]
[file content]
```
```

## Learned Rules

<!-- New rules added here by evolve.py -->
