"""Command-line entry point for the SOL-focused EU5 save parser."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .parser import SaveFormatError, export_analysis, parse_save


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract population, location, country, and cached SOL class data "
            "from an uncompressed EU5 debug save."
        )
    )
    parser.add_argument("save", type=Path, help="path to the .eu5 debug save")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help=(
            "output directory (default: data/save_analysis/<save filename>)"
        ),
    )
    parser.add_argument(
        "--country",
        action="append",
        default=[],
        metavar="TAG",
        help="export only locations owned by this tag; may be repeated",
    )
    parser.add_argument(
        "--emit-populations",
        action="store_true",
        help="also write the individual population-group table",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="report rather than reject broken id relationships",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    output = args.output or Path("data/save_analysis") / args.save.stem
    started = time.perf_counter()
    try:
        parsed = parse_save(args.save, strict=not args.no_strict)
        paths = export_analysis(
            parsed,
            output,
            country_tags=args.country,
            emit_populations=args.emit_populations,
        )
    except (OSError, SaveFormatError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    elapsed = time.perf_counter() - started
    print(
        f"Parsed {len(parsed.populations):,} population records and "
        f"{len(parsed.locations):,} locations in {elapsed:.2f}s."
    )
    for key, value in parsed.diagnostics.items():
        print(f"  {key}: {value:,}")
    print("Wrote:")
    for path in paths:
        print(f"  {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
