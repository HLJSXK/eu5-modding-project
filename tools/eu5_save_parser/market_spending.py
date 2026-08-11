"""Read SOL market-keyed global variable maps out of an EU5 save.

Reports the per-market unit spending that the yearly refresh persisted, plus
the engine's own consumed-goods filter. Unit spending is frozen between yearly
refreshes, so comparing consecutive saves shows exactly when it stepped.

Usage:
  python -m tools.eu5_save_parser.market_spending <save> [<save> ...] [--market N]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POP_TYPES = (
    "nobles",
    "clergy",
    "burghers",
    "laborers",
    "peasants",
    "soldiers",
    "tribesmen",
)
DEFAULT_MARKET = 22
FIXED_POINT_SCALE = 100_000

_PAIR = re.compile(
    rb"key=\{\s*type=mark\s*identity=(\d+)\s*\}\s*"
    rb"value=\{\s*type=value\s*identity=(\d+)\s*\}"
)


def variables_blob(path: Path) -> bytes:
    """Return the save's top-level variables block as raw bytes."""

    content = path.read_bytes()
    start = content.find(b"variables={")
    if start < 0:
        raise SystemExit(f"variables block not found in {path.name}")
    end = content.find(b"\nlanguage_manager={", start)
    return content[start : end if end > 0 else len(content)]


def read_market_map(blob: bytes, map_name: str, market_id: int) -> float | None:
    """Read one market key's value from a named global_variable_map."""

    anchor = blob.find(b'name="' + map_name.encode() + b'"')
    if anchor < 0:
        return None
    list_start = blob.find(b"list={", anchor)
    if list_start < 0:
        return None
    # Bound the scan at the next map so keys never leak across entries.
    next_anchor = blob.find(b'name="', list_start)
    list_end = next_anchor if next_anchor > 0 else len(blob)
    for pair in _PAIR.finditer(blob, list_start, list_end):
        if int(pair.group(1)) != market_id:
            continue
        raw = int(pair.group(2))
        if raw >= 1 << 63:
            raw -= 1 << 64
        return raw / FIXED_POINT_SCALE
    return None


def consumed_goods(blob: bytes, market_id: int) -> dict[str, float]:
    """Engine-reported supply per good, as cached by the yearly refresh.

    This is the authoritative filter the refresh uses. It is NOT the same as a
    good block's `supply` field inside market_manager -- recomputing unit
    spending from that field overstates it by 1.3-2.6x.
    """

    names = sorted(
        set(
            match.group(1).decode()
            for match in re.finditer(
                rb'name="sol_market_consumes_([a-z_]+)"', blob
            )
        )
    )
    found = {}
    for good in names:
        value = read_market_map(blob, f"sol_market_consumes_{good}", market_id)
        if value is not None and value > 0:
            found[good] = value
    return found


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read SOL per-market unit spending from one or more saves."
    )
    parser.add_argument("saves", nargs="+", type=Path)
    parser.add_argument("--market", type=int, default=DEFAULT_MARKET)
    parser.add_argument(
        "--goods", action="store_true",
        help="also list the engine's consumed-goods filter for this market",
    )
    args = parser.parse_args()

    print(f"market {args.market}\n")
    header = f"{'save':26} " + " ".join(f"{p[:8]:>10}" for p in POP_TYPES)
    print(header)
    print("-" * len(header))
    for path in args.saves:
        if not path.exists():
            print(f"{path.name[:26]:26} (not found)")
            continue
        blob = variables_blob(path)
        cells = []
        for pop_type in POP_TYPES:
            value = read_market_map(
                blob, f"sol_market_unit_spending_{pop_type}", args.market
            )
            cells.append(
                f"{value:10.5f}" if value is not None else f"{'--':>10}"
            )
        label = path.stem.replace("SP_HUN_", "")[:26]
        print(f"{label:26} " + " ".join(cells))

    if args.goods:
        for path in args.saves:
            if not path.exists():
                continue
            goods = consumed_goods(variables_blob(path), args.market)
            print(
                f"\n{path.stem[:40]}: {len(goods)} goods pass the engine filter"
            )
            print("  " + ", ".join(sorted(goods)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
