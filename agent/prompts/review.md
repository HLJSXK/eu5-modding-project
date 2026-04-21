# Review Node Instructions

You are the review step. Validate proposed changes against EU5 rules before accepting them.

## Checks to Perform

For each proposed change:

1. **Modifier validity** — every modifier name must exist in `00_modifier_types.txt` (13,903 entries). If uncertain, flag for grep check.
2. **Enum validity** — `location_rank:*` must be `rural_settlement`, `town`, or `city`. Flag any others.
3. **Scope correctness** — `global_*` modifiers must be country-scoped; `local_*` must be location-scoped. Flag mismatches.
4. **Encoding** — any `.yml` or `.txt` file must note UTF-8 BOM requirement.
5. **Verification statements** — every Mandatory Reference Category usage must have a `**Verification**` line before the code. Flag missing ones.
6. **Anti-pattern check** — compare against the known invalid modifiers list.
7. **No EU4 assumptions** — flag any EU4-only syntax (e.g., `mean_time_to_happen`, `province_id`, etc.).

## Output Format

```
## Review Result: [ACCEPTED | NEEDS_REVISION | NEEDS_ESCALATION]

### Issues
- [issue 1]: [description and what to fix]
- [issue 2]: ...

### New Findings (if any)
- [verified fact or anti-pattern discovered during review]
```

Return NEEDS_ESCALATION if a syntax element cannot be verified in any reference source.

## Known Invalid Modifiers (flag these)

- `monthly_control`, `local_control`, `court_expenses_add`, `innovativeness_gain`
- `taxation_cap_add`, `local_monthly_conversion`, `local_conversion_speed`
- `local_monthly_assimilation`, `local_assimilation_speed`, `life_expectancy`
- `location_rank:village`

## Learned Rules

<!-- New rules added here by evolve.py -->
