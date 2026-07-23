#!/usr/bin/env python3
"""
Sync EU5 vanilla game files into reference_game_files/ as a curated text-only subset.

Mirrors <EU5_GAME>/in_game/ and <EU5_GAME>/main_menu/ into
reference_game_files/game/, applying three filter layers plus two
directory-level prunes:

  Directory prune (before walking):
    - Any directory named 'gfx' is skipped entirely (asset descriptors,
      not modding scripts).
    - Under any 'localization/' directory, only language subdirs in
      LOC_LANGS_KEPT are descended into.

  File-level filters:
    1. Extension whitelist  -- text-based modding formats only.
    2. Per-file size cap    -- skip individual files above --max-file-mb.
    3. Per-leaf-dir size cap -- skip whole directories whose post-filter
                                non-recursive size exceeds --max-dir-mb.

Run:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/sync_reference.py --dry-run
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/sync_reference.py
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/sync_reference.py --max-file-mb 8 --max-dir-mb 25

After a real (non-dry) sync, you should also run:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_index.py --verbose
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_brief.py
"""

import argparse
import os
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game")
DEFAULT_DEST = REPO_ROOT / "reference_game_files" / "game"
LOG_FILE = REPO_ROOT / "data" / "sync_reference.log"

SUBTREES = ["in_game", "main_menu"]

EXT_WHITELIST = {".txt", ".yml", ".gui", ".json", ".info"}

# Directory names pruned from the walk entirely (asset descriptors, etc.).
DIR_BLACKLIST = {"gfx"}

# When walking into a directory named 'localization', only these language
# children are descended into. Project is a Chinese mod so simp_chinese is
# kept alongside english as the authoritative reference.
LOC_LANGS_KEPT = {"english", "simp_chinese"}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--source",
        type=Path,
        default=Path(os.environ.get("EU5_GAME_PATH", str(DEFAULT_SOURCE))),
        help="EU5 game install dir (default: %(default)s; env EU5_GAME_PATH overrides)",
    )
    ap.add_argument(
        "--dest", type=Path, default=DEFAULT_DEST,
        help="Destination dir (default: %(default)s)",
    )
    ap.add_argument(
        "--max-file-mb", type=float, default=10.0,
        help="Per-file size cap in MB (default: %(default)s)",
    )
    ap.add_argument(
        "--max-dir-mb", type=float, default=30.0,
        help="Per-leaf-directory size cap in MB; whole dir skipped if exceeded (default: %(default)s)",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Scan and report only; do not write files",
    )
    return ap.parse_args()


def detect_game_version(source: Path) -> str:
    """Best-effort read of the game version from a launcher-settings.json next to the game/ dir."""
    candidates = [
        source.parent / "launcher-settings.json",
        source / "launcher-settings.json",
        source.parent / "launcher" / "launcher-settings.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            import json
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            for key in ("rawVersion", "version"):
                if key in data:
                    return str(data[key])
        except (OSError, ValueError):
            continue
    return "unknown"


def collect_candidates(
    source: Path, max_file_bytes: int
) -> tuple[list[tuple[Path, Path, int]], dict[str, list[Path]]]:
    """Walk source subtrees and split files into candidates + per-reason skip buckets.

    Returns (candidates, skipped) where:
      candidates = list of (abs_src, rel_path_from_source, size_bytes) passing layers 1+2.
      skipped   = {"ext": [...], "size": [...]} -- files dropped at each layer.
    """
    candidates: list[tuple[Path, Path, int]] = []
    skipped: dict[str, list[Path]] = {"ext": [], "size": []}

    for sub in SUBTREES:
        root = source / sub
        if not root.exists():
            print(f"[WARN] source subtree missing: {root}")
            continue
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            # Prune blacklisted dirs (gfx/) before descending.
            dirnames[:] = [d for d in dirnames if d not in DIR_BLACKLIST]
            # Inside any 'localization' dir, only descend into kept languages.
            if Path(dirpath).name == "localization":
                dirnames[:] = [d for d in dirnames if d in LOC_LANGS_KEPT]
            for name in filenames:
                abs_path = Path(dirpath) / name
                rel = abs_path.relative_to(source)
                ext = abs_path.suffix.lower()
                if ext not in EXT_WHITELIST:
                    skipped["ext"].append(rel)
                    continue
                try:
                    size = abs_path.stat().st_size
                except OSError:
                    skipped["ext"].append(rel)
                    continue
                if size > max_file_bytes:
                    skipped["size"].append(rel)
                    continue
                candidates.append((abs_path, rel, size))
    return candidates, skipped


def apply_dir_cap(
    candidates: list[tuple[Path, Path, int]], max_dir_bytes: int
) -> tuple[list[tuple[Path, Path, int]], list[tuple[Path, int, int]]]:
    """Drop entire leaf dirs whose aggregated post-filter non-recursive size > cap.

    Returns (kept, skipped_dirs) where skipped_dirs = [(rel_dir, total_bytes, file_count), ...].
    """
    by_dir: dict[Path, list[tuple[Path, Path, int]]] = defaultdict(list)
    for abs_path, rel, size in candidates:
        by_dir[rel.parent].append((abs_path, rel, size))

    kept: list[tuple[Path, Path, int]] = []
    skipped_dirs: list[tuple[Path, int, int]] = []
    for rel_dir, items in by_dir.items():
        total = sum(size for _, _, size in items)
        if total > max_dir_bytes:
            skipped_dirs.append((rel_dir, total, len(items)))
        else:
            kept.extend(items)
    skipped_dirs.sort(key=lambda x: -x[1])
    return kept, skipped_dirs


def wipe_dest(dest: Path) -> None:
    """Remove dest dir tree if present, then re-create it empty.

    The sibling reference_game_files/README.md is untouched (it lives one level up).
    """
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)


def copy_files(
    kept: list[tuple[Path, Path, int]], source: Path, dest: Path
) -> tuple[int, int]:
    """Copy files preserving relative path under source. Returns (count, bytes)."""
    count = 0
    total_bytes = 0
    for i, (abs_src, rel, size) in enumerate(kept, 1):
        dst_path = dest / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(abs_src, dst_path)
        count += 1
        total_bytes += size
        if i % 200 == 0:
            print(f"[copy] {i}/{len(kept)} files, {total_bytes / (1024 * 1024):.1f} MB so far")
    return count, total_bytes


def fmt_mb(n: int) -> str:
    return f"{n / (1024 * 1024):.2f} MB"


def write_log(
    args: argparse.Namespace,
    version: str,
    elapsed: float,
    kept_count: int,
    kept_bytes: int,
    skipped_ext: list[Path],
    skipped_size: list[Path],
    skipped_dirs: list[tuple[Path, int, int]],
) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "DRY-RUN" if args.dry_run else "SYNC"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"=== {timestamp} [{mode}] EU5 version: {version} ===\n")
        f.write(f"source: {args.source}\n")
        f.write(f"dest:   {args.dest}\n")
        f.write(f"caps:   file<={args.max_file_mb}MB  leaf-dir<={args.max_dir_mb}MB\n")
        f.write(f"kept:   {kept_count} files, {fmt_mb(kept_bytes)}\n")
        f.write(f"skipped(ext):  {len(skipped_ext)}\n")
        for p in skipped_ext[:5]:
            f.write(f"  - {p}\n")
        f.write(f"skipped(size): {len(skipped_size)}\n")
        for p in skipped_size[:5]:
            f.write(f"  - {p}\n")
        f.write(f"skipped(leaf-dir cap): {len(skipped_dirs)} dirs\n")
        for rel_dir, total, n in skipped_dirs:
            f.write(f"  - {rel_dir}  ({fmt_mb(total)}, {n} files)\n")
        f.write(f"elapsed: {elapsed:.1f}s\n\n")


def main() -> int:
    args = parse_args()

    if not args.source.exists():
        print(f"[ERROR] source path does not exist: {args.source}")
        return 2

    max_file_bytes = int(args.max_file_mb * 1024 * 1024)
    max_dir_bytes = int(args.max_dir_mb * 1024 * 1024)

    version = detect_game_version(args.source)
    print(f"[info] EU5 version: {version}")
    print(f"[info] source: {args.source}")
    print(f"[info] dest:   {args.dest}")
    print(f"[info] caps:   file<={args.max_file_mb}MB  leaf-dir<={args.max_dir_mb}MB")

    t0 = time.time()
    print("[scan] walking source tree...")
    candidates, skipped = collect_candidates(args.source, max_file_bytes)
    print(f"[scan] candidates after layers 1+2: {len(candidates)} files")
    print(f"[scan] skipped(ext): {len(skipped['ext'])}  skipped(size): {len(skipped['size'])}")

    kept, skipped_dirs = apply_dir_cap(candidates, max_dir_bytes)
    kept_bytes_estimate = sum(s for _, _, s in kept)
    print(f"[scan] after leaf-dir cap: {len(kept)} files, {fmt_mb(kept_bytes_estimate)}")
    if skipped_dirs:
        print(f"[scan] {len(skipped_dirs)} leaf dir(s) exceeded {args.max_dir_mb}MB and were dropped:")
        for rel_dir, total, n in skipped_dirs:
            print(f"  - {rel_dir}  ({fmt_mb(total)}, {n} files)")

    if args.dry_run:
        # Print breakdowns to help tune thresholds and spot unexpected bloat.
        by_top: dict[str, int] = defaultdict(int)
        by_leaf: dict[Path, int] = defaultdict(int)
        ext_bytes: dict[str, int] = defaultdict(int)
        ext_count: dict[str, int] = defaultdict(int)
        for _, rel, size in kept:
            parts = rel.parts
            top = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
            by_top[top] += size
            by_leaf[rel.parent] += size
            ext_bytes[rel.suffix.lower()] += size
            ext_count[rel.suffix.lower()] += 1

        print("\n[dry-run] kept bytes by 2nd-level dir (top 25):")
        for top, b in sorted(by_top.items(), key=lambda x: -x[1])[:25]:
            print(f"  {fmt_mb(b):>10}  {top}")

        print("\n[dry-run] kept bytes by leaf dir (top 20):")
        for leaf, b in sorted(by_leaf.items(), key=lambda x: -x[1])[:20]:
            print(f"  {fmt_mb(b):>10}  {leaf}")

        print("\n[dry-run] kept bytes by extension:")
        for ext, b in sorted(ext_bytes.items(), key=lambda x: -x[1]):
            print(f"  {fmt_mb(b):>10}  {ext}  ({ext_count[ext]} files)")

        elapsed = time.time() - t0
        print(f"\n[dry-run] no files written. elapsed {elapsed:.1f}s")
        write_log(args, version, elapsed, len(kept), kept_bytes_estimate,
                  skipped["ext"], skipped["size"], skipped_dirs)
        return 0

    print(f"[wipe] clearing {args.dest}/ ...")
    wipe_dest(args.dest)
    print(f"[copy] copying {len(kept)} files...")
    count, total_bytes = copy_files(kept, args.source, args.dest)
    elapsed = time.time() - t0
    print(f"\n[OK] copied {count} files, {fmt_mb(total_bytes)} in {elapsed:.1f}s")

    write_log(args, version, elapsed, count, total_bytes,
              skipped["ext"], skipped["size"], skipped_dirs)
    print(f"[log] {LOG_FILE.relative_to(REPO_ROOT)}")
    print("\nNext steps:")
    print("  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_index.py --verbose")
    print("  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/gen_brief.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
