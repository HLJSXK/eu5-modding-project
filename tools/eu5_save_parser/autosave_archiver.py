"""Keep one EU5 save per N game years while a long (observer) game runs.

EU5 only keeps a few rotating autosaves (3 by default), so a 300-year observer
run would otherwise leave nothing but its last months. This watcher polls the
local ``save games`` folder, reads each finished save's in-game date, and
copies the first save it sees in every N-year bucket (default: one per
calendar decade, 1330s/1340s/...) into an archive folder. It runs entirely
locally next to the game, needs no mod changes and no network, and uses only
the standard library.

Typical use (PowerShell, from the project root, game launched with
``-debug_mode`` so saves stay plaintext for ``tools.eu5_save_parser``)::

    $env:PYTHONUTF8='1'
    & $env:EU5_PYTHON -m tools.eu5_save_parser.autosave_archiver

Stop with Ctrl+C. Restarting resumes from ``archive_state.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "saves" / "observer_archive"
STATE_NAME = "archive_state.json"
HEAD_BYTES = 256 * 1024

# Header digits 6-7 follow the Jomini save-header convention. Only kind 0
# (plaintext, produced by -debug_mode) is verified on EU5 1.4.1 saves; the
# other labels are informative only and never drive behaviour.
HEADER_KINDS = {
    0: "text",
    1: "binary",
    2: "zip-text",
    3: "zip-binary",
    4: "split-text",
    5: "split-binary",
}

_HEADER_RE = re.compile(rb"^SAV([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})")
_DATE_RE = re.compile(rb"(?m)^\s*date=(\d{1,4})\.(\d{1,2})\.(\d{1,2})(?:\.\d+)?\s*$")
_PID_RE = re.compile(rb'playthrough_id="([^"]+)"')
_PNAME_RE = re.compile(rb'playthrough_name="([^"]*)"')
_VERSION_RE = re.compile(rb'(?m)^\s*version="([^"]+)"')
_NAME_DATE_RE = re.compile(r"(?:^|_)(\d{3,4})_(\d{1,2})_(\d{1,2})(?=_|$)")
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


@dataclass(frozen=True)
class SaveInfo:
    year: int
    month: int
    day: int
    playthrough_id: str
    playthrough_name: str
    version: str
    kind: str
    date_source: str

    @property
    def date(self) -> str:
        return f"{self.year}.{self.month}.{self.day}"

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (self.year, self.month, self.day)


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def read_save_info(path: Path) -> SaveInfo | None:
    """Return the save's in-game date and playthrough, or None if unknown.

    Order: plaintext metadata at the file head, then a text member of a zip
    container, then the ``..._YYYY_MM_DD_...`` pattern of the file name.
    """
    with path.open("rb") as stream:
        head = stream.read(HEAD_BYTES)

    kind = "unknown"
    header = _HEADER_RE.match(head)
    if header:
        kind = HEADER_KINDS.get(int(header.group(2), 16), f"kind-{header.group(2).decode()}")

    texts: list[tuple[str, bytes]] = [("metadata", head)]
    if not _DATE_RE.search(head):
        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        with archive.open(member) as handle:
                            texts.append((f"zip:{member.filename}", handle.read(HEAD_BYTES)))
        except (OSError, zipfile.BadZipFile):
            pass

    pid = pname = version = ""
    for source, blob in texts:
        if not pid and (m := _PID_RE.search(blob)):
            pid = _decode(m.group(1))
        if not pname and (m := _PNAME_RE.search(blob)):
            pname = _decode(m.group(1))
        if not version and (m := _VERSION_RE.search(blob)):
            version = _decode(m.group(1))

    date: tuple[int, int, int] | None = None
    date_source = ""
    for source, blob in texts:
        if m := _DATE_RE.search(blob):
            date = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            date_source = source
            break
    if date is None and (m := _NAME_DATE_RE.search(path.stem)):
        date = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        date_source = "filename"
    if date is None:
        return None
    if not pid and (m := _UUID_RE.search(path.stem)):
        pid = m.group(0)
    return SaveInfo(*date, pid or "unknown", pname, version, kind, date_source)


def default_save_dirs() -> list[Path]:
    home = Path.home()
    tail = Path("Paradox Interactive") / "Europa Universalis V" / "save games"
    candidates = [home / "Documents" / tail, home / "OneDrive" / "Documents" / tail,
                  home / "OneDrive" / "文档" / tail]
    return [path for path in candidates if path.is_dir()]


def _safe_dir_name(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    return cleaned or "unknown"


class Archiver:
    def __init__(self, save_dirs: Iterable[Path], out: Path, *, interval: int = 10,
                 anchor: int = 0, pattern: str = "*.eu5", settle: float = 3.0,
                 playthrough: str | None = None, min_free_bytes: int = 5 * 1024**3,
                 dry_run: bool = False) -> None:
        if interval < 1:
            raise ValueError("interval must be at least one year")
        self.save_dirs = [Path(path) for path in save_dirs]
        self.out = Path(out)
        self.interval = interval
        self.anchor = anchor
        self.pattern = pattern
        self.settle = settle
        self.playthrough = playthrough
        self.min_free_bytes = min_free_bytes
        self.dry_run = dry_run
        self.state_path = self.out / STATE_NAME
        self.state = self._load_state()
        self._last_seen: dict[Path, tuple[int, int]] = {}
        self._done: set[tuple[str, int, int]] = set()
        self._warned: set[str] = set()

    # -- state -------------------------------------------------------------
    def _load_state(self) -> dict:
        if self.state_path.is_file():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            old = (state.get("interval"), state.get("anchor"))
            if old != (self.interval, self.anchor):
                _log(f"warning: state was written with interval/anchor {old}; "
                     f"buckets are now {self.interval}/{self.anchor}")
            state["interval"], state["anchor"] = self.interval, self.anchor
            return state
        return {"interval": self.interval, "anchor": self.anchor, "playthroughs": {}}

    def _save_state(self) -> None:
        if self.dry_run:
            return
        self.out.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".json.part")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def bucket(self, year: int) -> int:
        return (year - self.anchor) // self.interval

    def bucket_label(self, bucket: int) -> str:
        start = self.anchor + bucket * self.interval
        return f"{start}-{start + self.interval - 1}"

    # -- scanning ----------------------------------------------------------
    def _candidates(self) -> list[Path]:
        out = self.out.resolve()
        files: list[Path] = []
        for directory in self.save_dirs:
            if not directory.is_dir():
                continue
            for path in directory.glob(self.pattern):
                if path.is_file() and out not in path.resolve().parents:
                    files.append(path)
        return files

    def _ready(self, files: list[Path]) -> list[tuple[Path, tuple[int, int]]]:
        """Files whose size and mtime are unchanged since the previous poll."""
        now = time.time()
        ready = []
        seen: dict[Path, tuple[int, int]] = {}
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            signature = (stat.st_size, stat.st_mtime_ns)
            seen[path] = signature
            if (path.name, *signature) in self._done:
                continue
            if self._last_seen.get(path) == signature and now - stat.st_mtime >= self.settle:
                ready.append((path, signature))
        self._last_seen = seen
        return ready

    def poll(self) -> list[dict]:
        """Run one scan; return records of saves archived during it."""
        infos: list[tuple[SaveInfo, Path, tuple[int, int]]] = []
        for path, signature in self._ready(self._candidates()):
            try:
                info = read_save_info(path)
            except OSError as error:
                _log(f"cannot read {path.name} yet ({error}); retrying")
                continue
            if info is None:
                _log(f"skip {path.name}: no in-game date found")
                self._done.add((path.name, *signature))
                continue
            infos.append((info, path, signature))

        archived = []
        for info, path, signature in sorted(infos, key=lambda item: item[0].sort_key):
            record = self._consider(info, path, signature)
            if record is not None:
                archived.append(record)
        return archived

    def _consider(self, info: SaveInfo, path: Path, signature: tuple[int, int]) -> dict | None:
        key = (path.name, *signature)
        if self.playthrough and info.playthrough_id != self.playthrough:
            self._done.add(key)
            return None
        play = self.state["playthroughs"].setdefault(
            info.playthrough_id, {"name": info.playthrough_name, "buckets": {}})
        if info.playthrough_name:
            play["name"] = info.playthrough_name
        if info.kind != "text" and info.playthrough_id not in self._warned:
            self._warned.add(info.playthrough_id)
            _log(f"warning: {path.name} is a '{info.kind}' save; tools.eu5_save_parser "
                 "needs plaintext saves (launch EU5 with -debug_mode). Archiving anyway.")
        bucket = self.bucket(info.year)
        if str(bucket) in play["buckets"]:
            self._done.add(key)
            return None

        target_dir = self.out / _safe_dir_name(info.playthrough_id)
        target = target_dir / f"{info.year:04d}.{info.month:02d}.{info.day:02d}_{path.name}"
        size = signature[0]
        if self.dry_run:
            _log(f"[dry-run] would archive {info.date} ({self.bucket_label(bucket)}) -> {target}")
            record = {"date": info.date, "file": target.name, "dry_run": True}
            play["buckets"][str(bucket)] = record  # in memory only; state is not written
            self._done.add(key)
            return record

        target_dir.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(target_dir).free
        if free - size < self.min_free_bytes:
            if f"disk:{key}" in self._warned:
                return None
            self._warned.add(f"disk:{key}")
            _log(f"NOT archiving {info.date}: {free / 1024**3:.1f} GB free, file is "
                 f"{size / 1024**3:.2f} GB, reserve is {self.min_free_bytes / 1024**3:.1f} GB. "
                 "Free space or pass --out/--min-free-gb; will retry.")
            return None

        partial = target.with_name(target.name + ".part")
        try:
            shutil.copyfile(path, partial)
            after = path.stat()
        except OSError as error:
            partial.unlink(missing_ok=True)
            _log(f"copy of {path.name} failed ({error}); will retry if it still exists")
            return None
        if (after.st_size, after.st_mtime_ns) != signature or partial.stat().st_size != size:
            partial.unlink(missing_ok=True)
            _log(f"{path.name} changed while copying; will retry")
            return None
        os.replace(partial, target)

        record = {
            "date": info.date,
            "file": target.name,
            "source": path.name,
            "bytes": size,
            "format": info.kind,
            "version": info.version,
            "date_source": info.date_source,
            "archived_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        play["buckets"][str(bucket)] = record
        self._done.add(key)
        self._save_state()
        _log(f"archived {info.date} ({self.bucket_label(bucket)}, {size / 1024**2:.0f} MB) -> {target}")
        return record

    def summary(self) -> str:
        lines = []
        for pid, play in self.state["playthroughs"].items():
            buckets = play.get("buckets", {})
            lines.append(f"{play.get('name') or pid} [{pid}]: {len(buckets)} saves")
            for bucket in sorted(buckets, key=int):
                lines.append(f"  {self.bucket_label(int(bucket)):>9}  {buckets[bucket]['date']}")
        return "\n".join(lines) or "no saves archived yet"


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch the EU5 save folder and keep one save per N game years.")
    parser.add_argument("--save-dir", type=Path, action="append",
                        help="EU5 'save games' folder (repeatable; default: Documents\\Paradox "
                             "Interactive\\Europa Universalis V\\save games)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"archive folder (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})")
    parser.add_argument("--interval", type=int, default=10, help="game years per kept save (default 10)")
    parser.add_argument("--anchor", type=int, default=0,
                        help="bucket alignment year; 0 = calendar decades 1330s, 1340s... (default 0)")
    parser.add_argument("--poll", type=float, default=5.0, help="seconds between scans (default 5)")
    parser.add_argument("--settle", type=float, default=3.0,
                        help="a file must be unchanged this many seconds before copying (default 3)")
    parser.add_argument("--pattern", default="*.eu5", help="file glob inside save dirs (default *.eu5)")
    parser.add_argument("--playthrough", help="only archive this playthrough_id")
    parser.add_argument("--min-free-gb", type=float, default=5.0,
                        help="keep at least this much free space on the archive drive (default 5)")
    parser.add_argument("--once", action="store_true",
                        help="scan the current files once (two passes) and exit")
    parser.add_argument("--dry-run", action="store_true", help="report what would be copied")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    save_dirs = args.save_dir or default_save_dirs()
    if not save_dirs:
        print("EU5 save folder not found; pass --save-dir", file=sys.stderr)
        return 2
    missing = [str(path) for path in save_dirs if not path.is_dir()]
    if missing:
        print(f"save folder does not exist: {', '.join(missing)}", file=sys.stderr)
        return 2

    archiver = Archiver(save_dirs, args.out, interval=args.interval, anchor=args.anchor,
                        pattern=args.pattern, settle=args.settle, playthrough=args.playthrough,
                        min_free_bytes=int(args.min_free_gb * 1024**3), dry_run=args.dry_run)
    _log("watching " + "; ".join(str(path) for path in save_dirs))
    _log(f"archive -> {args.out} (one save per {args.interval} game years)")
    try:
        if args.once:
            archiver.settle = 0.0
            archiver.poll()
            archiver.poll()
        else:
            while True:
                archiver.poll()
                time.sleep(args.poll)
    except KeyboardInterrupt:
        _log("stopped")
    print(archiver.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
