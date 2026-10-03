#!/usr/bin/env python3
"""
Sync reference_game_files/game/ from an installed EU5 game folder.

Mirrors every top-level directory found directly under <source>/game/ (in_game,
main_menu, loading_screen, dlc, and any other directory the installed game ships)
except "mod" (installed Steam Workshop mods, not vanilla content — see
EXCLUDED_TOP_LEVEL_DIRS), applying a filter policy that keeps modding-relevant
script/localization text and drops engine assets and other locales:

  - any directory named "gfx" is pruned
  - inside a "localization" directory, other known locale subdirs are pruned;
    english/simp_chinese and non-locale containers such as jomini are kept
  - flat locale-suffixed files (e.g. foo_l_russian.yml) are kept only for
    english/simp_chinese, regardless of directory
  - files with a known-binary/media extension (.png, .dat, .mp3, ...) are dropped
  - any remaining file is sniffed for binary content (NUL byte in the first 8 KB)
    and dropped if it looks binary; everything else is treated as text and kept
    regardless of extension, so small unrecognized text-format files (e.g. .font,
    .map, .csv, .settings, .guistateset) are no longer silently dropped
  - a single file over --max-file-mb is skipped
  - a directory whose own (non-recursive) filtered files exceed --max-dir-mb is
    skipped entirely

Usage:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/sync_reference.py --dry-run --verbose
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/sync_reference.py --verbose

See reference_game_files/README.md for the full policy writeup.
"""

import argparse
import datetime
import os
import re
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_ROOT = REPO_ROOT / "reference_game_files" / "game"
LOG_FILE = REPO_ROOT / "data" / "sync_reference.log"

DEFAULT_SOURCE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V")

# Top-level directories under <source>/game/ that are never mirrored, regardless of
# their contents' size/binary-ness: "mod" holds installed Steam Workshop mods (other
# authors' mods plus this project's own deployed build output), not vanilla/official
# game content, so it is excluded by name rather than by the generic file filters.
EXCLUDED_TOP_LEVEL_DIRS = {"mod"}

# Known-binary/media extensions, dropped without opening the file. Everything else is
# sniffed for binary content (see is_binary_content) rather than gated by an extension
# whitelist, so unrecognized small text-format files are kept, not silently dropped.
BINARY_EXTENSIONS = {
    ".png", ".dds", ".tga", ".bmp", ".jpg", ".jpeg",
    ".dat", ".bin",
    ".mp3", ".wav", ".ogg",
    ".ttf", ".otf", ".woff", ".woff2",
    ".fbx", ".mesh",
    ".mp4", ".webm",
    ".zip", ".rar", ".7z",
    ".dll", ".exe", ".so", ".pdb",
}
BINARY_SNIFF_BYTES = 8192
KEEP_LOCALES = {"english", "simp_chinese"}
# All locale-named subdirectories observed directly under any "localization" dir in the
# source game (in_game and main_menu). Other subdirectories of "localization" (e.g.
# "jomini", "music_player_gui") are NOT locale dirs themselves — they hold flat
# locale-suffixed files one level deeper, so they must be descended into rather than
# pruned; the flat-file suffix filter below does the locale filtering for those.
ALL_LOCALE_DIRS = {
    "braz_por", "english", "french", "german", "japanese", "korean",
    "polish", "russian", "simp_chinese", "spanish", "turkish",
}
LOCALE_SUFFIX_RE = re.compile(r"_l_([a-z_]+)\.yml$", re.IGNORECASE)

MB = 1024 * 1024


def resolve_source(cli_source):
    if cli_source:
        return Path(cli_source)
    env_source = os.environ.get("EU5_GAME_PATH")
    if env_source:
        return Path(env_source)
    return DEFAULT_SOURCE


class SyncStats:
    def __init__(self):
        self.kept_files = []  # list of (relpath, size)
        self.skipped_binary_ext = 0
        self.skipped_binary_content = 0
        self.skipped_locale_dir = 0
        self.skipped_locale_file = 0
        self.skipped_oversized_file = []
        self.skipped_oversized_dir = []

    @property
    def total_size(self):
        return sum(size for _, size in self.kept_files)


def locale_of_flat_file(filename):
    match = LOCALE_SUFFIX_RE.search(filename)
    return match.group(1).lower() if match else None


def is_binary_content(file_path):
    """Best-effort binary sniff: a NUL byte in the first BINARY_SNIFF_BYTES means binary."""
    try:
        with file_path.open("rb") as f:
            chunk = f.read(BINARY_SNIFF_BYTES)
    except OSError:
        return True
    return b"\x00" in chunk


def plan_top_level(source_game_dir, top_name, max_file_bytes, max_dir_bytes, stats, verbose):
    """Walk source_game_dir/top_name and record files that survive the filter policy."""
    top_dir = source_game_dir / top_name
    if not top_dir.is_dir():
        print(f"  [WARN] source directory missing, skipped: {top_dir}")
        return

    for root, dirnames, filenames in os.walk(top_dir):
        root_path = Path(root)

        if "gfx" in dirnames:
            dirnames.remove("gfx")

        if root_path.name == "localization":
            to_prune = [d for d in dirnames if d in ALL_LOCALE_DIRS and d not in KEEP_LOCALES]
            for d in to_prune:
                dirnames.remove(d)
            stats.skipped_locale_dir += len(to_prune)

        dir_kept = []
        for filename in filenames:
            suffix = Path(filename).suffix.lower()
            if suffix in BINARY_EXTENSIONS:
                stats.skipped_binary_ext += 1
                continue

            locale = locale_of_flat_file(filename)
            if locale is not None and locale not in KEEP_LOCALES:
                stats.skipped_locale_file += 1
                continue

            file_path = root_path / filename
            if is_binary_content(file_path):
                stats.skipped_binary_content += 1
                continue

            size = file_path.stat().st_size
            dir_kept.append((filename, size))

        dir_total = sum(size for _, size in dir_kept)
        if dir_total > max_dir_bytes:
            stats.skipped_oversized_dir.append((str(root_path), dir_total))
            if verbose:
                print(f"  [SKIP-DIR] {root_path} ({dir_total / MB:.1f} MB > cap) - directory dropped entirely")
            continue

        for filename, size in dir_kept:
            if size > max_file_bytes:
                stats.skipped_oversized_file.append((str(root_path / filename), size))
                if verbose:
                    print(f"  [SKIP-FILE] {root_path / filename} ({size / MB:.1f} MB > cap)")
                continue
            rel = (root_path / filename).relative_to(source_game_dir)
            stats.kept_files.append((rel, size))


def discover_top_level_dirs(source_game_dir):
    """Every directory directly under <source>/game/, in sorted order, minus EXCLUDED_TOP_LEVEL_DIRS."""
    return sorted(
        p.name for p in source_game_dir.iterdir()
        if p.is_dir() and p.name not in EXCLUDED_TOP_LEVEL_DIRS
    )


def build_plan(source_root, max_file_mb, max_dir_mb, verbose):
    source_game_dir = source_root / "game"
    stats = SyncStats()
    max_file_bytes = max_file_mb * MB
    max_dir_bytes = max_dir_mb * MB

    for top_name in discover_top_level_dirs(source_game_dir):
        plan_top_level(source_game_dir, top_name, max_file_bytes, max_dir_bytes, stats, verbose)

    return stats


def current_dest_files():
    if not DEST_ROOT.is_dir():
        return set()
    return {
        p.relative_to(DEST_ROOT)
        for p in DEST_ROOT.rglob("*")
        if p.is_file()
    }


def print_dry_run_summary(stats):
    planned = {rel for rel, _ in stats.kept_files}
    existing = current_dest_files()
    to_add = planned - existing
    to_remove = existing - planned
    to_keep = planned & existing

    print()
    print("=== Dry run summary ===")
    print(f"Planned files:      {len(planned)}  ({stats.total_size / MB:.1f} MB)")
    print(f"Currently tracked:  {len(existing)}")
    print(f"Would add:          {len(to_add)}")
    print(f"Would remove:       {len(to_remove)}")
    print(f"Unchanged path:     {len(to_keep)}")
    print()
    print(f"Skipped (binary extension):           {stats.skipped_binary_ext}")
    print(f"Skipped (binary content sniff):       {stats.skipped_binary_content}")
    print(f"Skipped (locale dir pruned):          {stats.skipped_locale_dir}")
    print(f"Skipped (flat locale file):           {stats.skipped_locale_file}")
    print(f"Skipped (oversized file):              {len(stats.skipped_oversized_file)}")
    print(f"Skipped (oversized dir):                {len(stats.skipped_oversized_dir)}")

    if stats.skipped_oversized_file:
        print()
        print("Oversized files skipped:")
        for path, size in stats.skipped_oversized_file:
            print(f"  {path}  ({size / MB:.1f} MB)")

    if stats.skipped_oversized_dir:
        print()
        print("Oversized directories skipped:")
        for path, size in stats.skipped_oversized_dir:
            print(f"  {path}  ({size / MB:.1f} MB)")

    if to_remove:
        print()
        preview = sorted(str(p) for p in to_remove)
        print(f"Sample of paths that would be removed (showing up to 20 of {len(to_remove)}):")
        for p in preview[:20]:
            print(f"  - {p}")

    if to_add:
        print()
        preview = sorted(str(p) for p in to_add)
        print(f"Sample of paths that would be added (showing up to 20 of {len(to_add)}):")
        for p in preview[:20]:
            print(f"  + {p}")


def apply_sync(source_root, stats):
    source_game_dir = source_root / "game"

    if DEST_ROOT.exists():
        shutil.rmtree(DEST_ROOT)
    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    for rel, _ in stats.kept_files:
        src_path = source_game_dir / rel
        dest_path = DEST_ROOT / rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)


def append_log(source_root, stats, dry_run):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    mode = "dry-run" if dry_run else "sync"
    lines = [
        f"[{timestamp}] mode={mode} source={source_root}",
        f"  files={len(stats.kept_files)} total_size_mb={stats.total_size / MB:.1f}",
        f"  skipped_binary_ext={stats.skipped_binary_ext} skipped_binary_content={stats.skipped_binary_content}"
        f" skipped_locale_dir={stats.skipped_locale_dir} skipped_locale_file={stats.skipped_locale_file}",
        f"  skipped_oversized_file={len(stats.skipped_oversized_file)}"
        f" skipped_oversized_dir={len(stats.skipped_oversized_dir)}",
    ]
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", help="EU5 install root (contains game/). Overrides EU5_GAME_PATH.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without touching disk.")
    parser.add_argument("--max-file-mb", type=float, default=10.0, help="Per-file size cap in MB (default 10).")
    parser.add_argument("--max-dir-mb", type=float, default=30.0, help="Per-directory size cap in MB (default 30).")
    parser.add_argument("--verbose", action="store_true", help="Print each skipped file/directory as it happens.")
    args = parser.parse_args()

    source_root = resolve_source(args.source)
    if not source_root.is_dir():
        print(f"[ERROR] source path does not exist: {source_root}")
        sys.exit(1)
    if not (source_root / "game").is_dir():
        print(f"[ERROR] no game/ folder found under source: {source_root}")
        sys.exit(1)

    print(f"Source: {source_root}")
    print(f"Dest:   {DEST_ROOT}")
    print(f"Mode:   {'dry-run' if args.dry_run else 'sync (will wipe and re-mirror dest)'}")
    print()

    stats = build_plan(source_root, args.max_file_mb, args.max_dir_mb, args.verbose)

    if args.dry_run:
        print_dry_run_summary(stats)
        append_log(source_root, stats, dry_run=True)
        return

    apply_sync(source_root, stats)
    append_log(source_root, stats, dry_run=False)

    print(f"Synced {len(stats.kept_files)} files ({stats.total_size / MB:.1f} MB) into {DEST_ROOT}")
    print(f"Skipped: binary_ext={stats.skipped_binary_ext} binary_content={stats.skipped_binary_content} "
          f"locale_dir={stats.skipped_locale_dir} locale_file={stats.skipped_locale_file} "
          f"oversized_file={len(stats.skipped_oversized_file)} "
          f"oversized_dir={len(stats.skipped_oversized_dir)}")
    print()
    print("Next steps:")
    print(r"  C:\Users\Hades\anaconda3\envs\eu5\python.exe scripts\gen_index.py --verbose")
    print(r"  C:\Users\Hades\anaconda3\envs\eu5\python.exe scripts\gen_brief.py")


if __name__ == "__main__":
    main()
