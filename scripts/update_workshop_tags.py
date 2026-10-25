#!/usr/bin/env python3
"""SOL entry point for the shared Workshop tag tool; keeps the stable metadata default."""
from pathlib import Path
import runpy
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    shared = ROOT / ".eu5-base/scripts/update_workshop_tags.py"
    if not shared.is_file():
        raise SystemExit("Shared Workshop tag tool missing; bootstrap/update .eu5-base first.")
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not any(arg == "--metadata" or arg.startswith("--metadata=") for arg in arguments):
        arguments.extend(["--metadata", str(ROOT / "src/stable/.metadata/metadata.json")])
    return runpy.run_path(str(shared))["main"](arguments)


if __name__ == "__main__":
    raise SystemExit(main())
