# EU5 Validator

Static script-analysis tool that checks EU5 mod source files **without loading the game**.

## What it checks

| File type | Check |
|-----------|-------|
| `.yml` (localisation) | UTF-8-BOM encoding, non-ASCII smart quotes |
| `.txt` (scripts) | Known-bad patterns, `auto_modifier` key names, brace balance |

### Known-bad patterns (`.txt`)

| Pattern | Reason |
|---------|--------|
| `location_rank:village` | Invalid enum — use `rural_settlement`/`town`/`city` |
| `mean_time_to_happen` | EU4 syntax; EU5 fires events via `on_actions` |
| Smart-quote characters | PDX parser only accepts ASCII `"` |
| Full-width `＝` | Copy-paste corruption |

## Usage

```bash
# From repo root — scan src/ directory
python tools/validator/eu5_validator.py

# Scan a different directory
python tools/validator/eu5_validator.py --src src/develop

# Machine-readable JSON output (for CI / editor integration)
python tools/validator/eu5_validator.py --json

# Treat warnings as errors (strict mode)
python tools/validator/eu5_validator.py --strict
```

Exit code `0` = no errors; `1` = errors found (or warnings in `--strict` mode).

## Adding new rules

Edit `known_patterns.py`:

- **Bad pattern** — append a `(description, re.compile(…))` tuple to `BAD_PATTERNS`.
- **New forbidden YAML char** — add the Unicode codepoint to `FORBIDDEN_YAML_QUOTE_CHARS`.
- **New auto_modifier structural key** — add to `AUTO_MODIFIER_KNOWN_KEYS`.

## Requirements

Python 3.10+ (standard library only — no pip install needed).
