"""
EU5 Validator — Known Patterns Database

This module centralises every rule that the static analyser enforces.
Add new patterns here as the AI coding agent encounters new violations.
"""

# ---------------------------------------------------------------------------
# location_rank enum values
# Source: reference_official_defines/ (pdx engine defines)
# ---------------------------------------------------------------------------
VALID_LOCATION_RANKS = {
    "rural_settlement",
    "town",
    "city",
}

INVALID_LOCATION_RANK_EXAMPLES = {
    "village",   # common hallucination
    "hamlet",
    "metropolis",
    "province",
}

# ---------------------------------------------------------------------------
# auto_modifier required / optional keys
# Source: reference_official_defines/types/auto_modifiers.txt
# ---------------------------------------------------------------------------
AUTO_MODIFIER_KNOWN_KEYS = {
    # structural
    "category",
    "type",
    "icon",
    "requires_real",
    "potential_trigger",
    "scales_with",
    "limit",
    "hide_effects",
    "alert",
}

# ---------------------------------------------------------------------------
# Known bad patterns: (description, regex_pattern)
# Each entry is a 2-tuple; the regex is searched inside .txt files.
# ---------------------------------------------------------------------------
import re

BAD_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "Invalid location_rank enum (e.g. 'village'); use rural_settlement/town/city",
        re.compile(r"\blocation_rank\s*:\s*(village|hamlet|metropolis|province)\b"),
    ),
    (
        "Non-ASCII curly/smart quote in script — PDX parser only accepts ASCII double-quotes",
        re.compile(r"[\u201c\u201d\u2018\u2019]"),
    ),
    (
        "Non-ASCII equals sign — possible copy-paste corruption",
        re.compile(r"[＝]"),
    ),
    (
        "Bare 'mean_time_to_happen' — EU5 does not support MTTH; fire events via on_actions",
        re.compile(r"\bmean_time_to_happen\b"),
    ),
]

# ---------------------------------------------------------------------------
# Localization: non-ASCII quote characters that break the PDX YAML parser
# ---------------------------------------------------------------------------
FORBIDDEN_YAML_QUOTE_CHARS = [
    "\u201c",  # "  LEFT DOUBLE QUOTATION MARK
    "\u201d",  # "  RIGHT DOUBLE QUOTATION MARK
    "\u2018",  # '  LEFT SINGLE QUOTATION MARK
    "\u2019",  # '  RIGHT SINGLE QUOTATION MARK
    "\u00ab",  # «  LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
    "\u00bb",  # »  RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
]
