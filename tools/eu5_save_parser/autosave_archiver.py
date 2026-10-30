"""Compatibility entry point for the shared EU5 autosave archiver."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "saves" / "observer_archive"
SHARED = REPO_ROOT / ".eu5-base/scripts/autosave_archiver.py"
if not SHARED.is_file():
    raise SystemExit("Shared autosave archiver missing; run scripts/bootstrap_base.py "
                     "or update .eu5-base first.")

_spec = importlib.util.spec_from_file_location("_eu5_shared_autosave_archiver", SHARED)
_shared = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _shared  # dataclasses resolve their module during import
_spec.loader.exec_module(_shared)

# Preserve the old public API for project scripts that import the watcher.
Archiver = _shared.Archiver
SaveInfo = _shared.SaveInfo
read_save_info = _shared.read_save_info
default_save_dirs = _shared.default_save_dirs
STATE_NAME = _shared.STATE_NAME
HEAD_BYTES = _shared.HEAD_BYTES
HEADER_KINDS = _shared.HEADER_KINDS


def main(argv: list[str] | None = None) -> int:
    return _shared.main(argv, default_workspace=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
