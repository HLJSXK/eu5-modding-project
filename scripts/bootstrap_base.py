#!/usr/bin/env python3
"""Connect this EU5 mod workspace to its sibling eu5-modding-base checkout.

Run from either mod project after cloning it beside eu5-modding-base. Set
EU5_MODDING_BASE when the base checkout lives elsewhere. The link is local and
ignored by Git; it is never a second copy of the shared reference corpus.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


WORKSPACE = Path(__file__).resolve().parents[1]
LINK = WORKSPACE / ".eu5-base"


def base_root() -> Path:
    configured = os.environ.get("EU5_MODDING_BASE")
    return Path(configured).expanduser().resolve() if configured else WORKSPACE.parent / "eu5-modding-base"


def main() -> int:
    base = base_root().resolve()
    required = ("CLAUDE.md", "reference_game_files/game", "reference_official_defines", "reference_mods")
    missing = [item for item in required if not (base / item).exists()]
    if missing:
        print(f"[ERROR] Incomplete eu5-modding-base at {base}; missing: {', '.join(missing)}")
        return 1
    if LINK.exists() or LINK.is_symlink():
        if LINK.resolve() != base:
            print(f"[ERROR] {LINK} points to {LINK.resolve()}, expected {base}. Remove the stale link manually.")
            return 1
        print(f"[OK] Shared EU5 base already connected: {LINK} -> {base}")
        return 0
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(LINK), str(base)], capture_output=True, text=True)
        if result.returncode:
            print(f"[ERROR] Could not create junction: {result.stderr or result.stdout}")
            return result.returncode
    else:
        LINK.symlink_to(base, target_is_directory=True)
    print(f"[OK] Connected shared EU5 base: {LINK} -> {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
