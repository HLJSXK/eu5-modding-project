#!/usr/bin/env python3
"""Project entry point for the shared EU5 error log filter."""
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
shared = root / ".eu5-base" / "error_log_filter.py"
if not shared.is_file():
    raise SystemExit("Run scripts/bootstrap_base.py first")
if "--config" not in sys.argv:
    sys.argv[1:1] = ["--config", str(root / "error_log_filter_config.json")]
runpy.run_path(str(shared), run_name="__main__")
