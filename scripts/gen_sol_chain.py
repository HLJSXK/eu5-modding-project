#!/usr/bin/env python3
"""
Run the active SOL code-generation chain for one or more deploy targets.

Usage:
  python scripts/gen_sol_chain.py
  python scripts/gen_sol_chain.py --target stable
  python scripts/gen_sol_chain.py --target sol_standalone
  python scripts/gen_sol_chain.py --check
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_NAMES = ("stable", "sol_standalone")


def _resolve_targets(target: str) -> list[str]:
    if target == "all":
        return list(TARGET_NAMES)
    if target in TARGET_NAMES:
        return [target]
    raise ValueError(f"Unknown target: {target}")


def _run(args: list[str]) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        env=env,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the active SOL generation chain."
    )
    parser.add_argument(
        "--target",
        choices=[*TARGET_NAMES, "all"],
        default="all",
        help="Deploy target to update/check (default: all).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated outputs without writing files.",
    )
    args = parser.parse_args()

    targets = _resolve_targets(args.target)
    target_arg = args.target
    mode_args = ["--check"] if args.check else []

    _run(["scripts/gen_pop_goods.py", "--target", target_arg, *mode_args])
    _run(["scripts/gen_demand_csv.py", *mode_args])
    _run(["scripts/gen_market_unit_consumption.py", "--target", target_arg, *mode_args])

    if "sol_standalone" in targets:
        location_args = ["--check"] if args.check else []
        _run(["scripts/generate_sol_location_window.py", *location_args])


if __name__ == "__main__":
    main()
