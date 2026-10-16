#!/usr/bin/env python3
"""Project entry point for the shared EU5 reference filter/synchronizer."""
from pathlib import Path
import runpy

shared = Path(__file__).resolve().parents[1] / ".eu5-base" / "scripts" / "sync_reference.py"
if not shared.is_file():
    raise SystemExit("Run scripts/bootstrap_base.py first")
runpy.run_path(str(shared), run_name="__main__")
