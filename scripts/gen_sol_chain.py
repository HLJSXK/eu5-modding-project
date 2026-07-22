#!/usr/bin/env python3
"""
Run the active SOL code-generation chain for one or more deploy targets.

Usage:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py --target stable
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py --target sol_standalone
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py --target sol_pp_compatibility_submod
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py --target sol_jtg_compatibility_submod
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_sol_chain.py --check
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TARGET_NAMES = ("stable", "sol_standalone")
COMPAT_TARGET_NAMES = (
    "sol_pp_compatibility_submod",
    "sol_jtg_compatibility_submod",
)
TARGET_NAMES = (*BASE_TARGET_NAMES, *COMPAT_TARGET_NAMES)


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
    mode_args = ["--check"] if args.check else []

    base_targets = [target for target in targets if target in BASE_TARGET_NAMES]
    if base_targets:
        target_arg = "all" if len(base_targets) == len(BASE_TARGET_NAMES) else base_targets[0]
        _run(["scripts/gen_pop_goods.py", "--target", target_arg, *mode_args])
        _run(["scripts/gen_demand_csv.py", *mode_args])
        _run(["scripts/gen_market_unit_consumption.py", "--target", target_arg, *mode_args])

    if "sol_standalone" in base_targets:
        location_args = ["--check"] if args.check else []
        _run(["scripts/generate_sol_location_window.py", *location_args])

    if "sol_pp_compatibility_submod" in targets:
        _run(["scripts/gen_sol_pp_compat.py", *mode_args])

    if "sol_jtg_compatibility_submod" in targets:
        _run(["scripts/gen_sol_jtg_compat.py", *mode_args])


if __name__ == "__main__":
    main()
