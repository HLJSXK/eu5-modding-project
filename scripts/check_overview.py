#!/usr/bin/env python3
"""
Stop hook: remind AI to check PROJECT_OVERVIEW.md after every task.
Always emits the reminder so the check is never silently skipped.
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print(
    "[PROJECT_OVERVIEW] Read docs/knowledge/PROJECT_OVERVIEW.md and decide "
    "if project features or directory structure changed this session. "
    "If yes: update the file and run gen_brief.py. If no: no action needed."
)
