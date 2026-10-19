"""Tests for the decade autosave archiver using synthetic save folders."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .autosave_archiver import Archiver, main, read_save_info

PID = "404b38fa-7e27-4e42-ac4f-402a45292046"


def text_save(date: str, pid: str = PID, kind: str = "00") -> bytes:
    return (f"SAV03{kind}b0f2c9750004e8d500000000\nmetadata={{\n\tdate={date}\n"
            f'\tplaythrough_id="{pid}"\n\tplaythrough_name="观察者 #1"\n'
            f'\tsave_label="{date}"\n\tversion="1.4.1"\n}}\ngamestate=1\n').encode("utf-8")


class ArchiverTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.saves = root / "save games"
        self.out = root / "archive"
        self.saves.mkdir()
        self._clock = time.time() - 1000

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, name: str, payload: bytes) -> Path:
        path = self.saves / name
        path.write_bytes(payload)
        self._clock += 1
        os.utime(path, (self._clock, self._clock))
        return path

    def autosave(self, year: int, month: int = 1, pid: str = PID) -> Path:
        return self.write(f"SP_HUN_{year}_{month:02d}_01_{pid}.eu5", text_save(f"{year}.{month}.1", pid))

    def archiver(self, **kwargs) -> Archiver:
        kwargs.setdefault("settle", 0.0)
        kwargs.setdefault("min_free_bytes", 0)
        return Archiver([self.saves], self.out, **kwargs)

    def cycle(self, archiver: Archiver) -> list[dict]:
        return archiver.poll() + archiver.poll()

    def archived_dates(self) -> list[str]:
        state = json.loads((self.out / "archive_state.json").read_text(encoding="utf-8"))
        buckets = state["playthroughs"][PID]["buckets"]
        return [buckets[key]["date"] for key in sorted(buckets, key=int)]

    def test_reads_debug_text_metadata(self) -> None:
        info = read_save_info(self.write("x.eu5", text_save("1337.6.2.16")))
        self.assertEqual((info.date, info.playthrough_id, info.kind, info.version),
                         ("1337.6.2", PID, "text", "1.4.1"))
        self.assertEqual(info.playthrough_name, "观察者 #1")

    def test_one_save_per_decade_keeps_earliest(self) -> None:
        archiver = self.archiver()
        for year in (1337, 1338, 1339, 1340, 1341):
            self.autosave(year)
        self.cycle(archiver)
        self.assertEqual(self.archived_dates(), ["1337.1.1", "1340.1.1"])
        # Rotation: older autosaves vanish, the game keeps writing.
        for path in self.saves.iterdir():
            path.unlink()
        for year in (1349, 1350, 1351):
            self.autosave(year)
        self.cycle(archiver)
        self.assertEqual(self.archived_dates(), ["1337.1.1", "1340.1.1", "1350.1.1"])
        copied = sorted(p.name for p in (self.out / PID).iterdir())
        self.assertEqual(copied[0], f"1337.01.01_SP_HUN_1337_01_01_{PID}.eu5")
        self.assertEqual(len(copied), 3)
        self.assertEqual((self.out / PID / copied[1]).read_bytes(), text_save("1340.1.1"))

    def test_unstable_and_tmp_files_wait(self) -> None:
        archiver = self.archiver()
        self.write("SP_HUN_1340_01_01.tmp", text_save("1340.1.1"))
        path = self.autosave(1340)
        self.assertEqual(archiver.poll(), [])          # first sighting only
        path.write_bytes(text_save("1340.1.1") + b"more")  # still growing
        self.assertEqual(archiver.poll(), [])
        self.assertEqual(len(archiver.poll()), 1)
        self.assertFalse(any(p.suffix == ".part" for p in (self.out / PID).iterdir()))

    def test_settle_time_respected(self) -> None:
        archiver = self.archiver(settle=3600)
        self.autosave(1340)
        self.assertEqual(self.cycle(archiver), [])

    def test_resume_from_state(self) -> None:
        self.autosave(1340)
        self.cycle(self.archiver())
        self.autosave(1345)
        self.autosave(1350)
        self.cycle(self.archiver())
        self.assertEqual(self.archived_dates(), ["1340.1.1", "1350.1.1"])

    def test_playthrough_filter_and_separate_folders(self) -> None:
        other = "11111111-2222-3333-4444-555555555555"
        self.autosave(1340, pid=other)
        self.autosave(1340)
        self.cycle(self.archiver(playthrough=PID))
        self.assertFalse((self.out / other).exists())
        self.cycle(self.archiver())
        self.assertTrue((self.out / other).is_dir())

    def test_filename_fallback_for_non_text_save(self) -> None:
        path = self.write(f"SP_FRA_1450_03_01_{PID}.eu5", b"SAV0301deadbeef00000000000000\x00\x01\x02binary")
        info = read_save_info(path)
        self.assertEqual((info.date, info.playthrough_id, info.kind, info.date_source),
                         ("1450.3.1", PID, "binary", "filename"))

    def test_zip_text_metadata(self) -> None:
        path = self.saves / "autosave.eu5"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("meta", text_save("1612.7.1")[32:] * 50)
        self.assertNotIn(b"1612", path.read_bytes())
        self.assertEqual(read_save_info(path).date, "1612.7.1")

    def test_unknown_date_is_skipped(self) -> None:
        self.write("autosave.eu5", b"not a save")
        self.assertEqual(self.cycle(self.archiver()), [])

    def test_disk_reserve_blocks_copy_then_retries(self) -> None:
        self.autosave(1340)
        archiver = self.archiver(min_free_bytes=1 << 62)
        self.assertEqual(self.cycle(archiver), [])
        archiver.min_free_bytes = 0
        self.assertEqual(len(archiver.poll()), 1)

    def test_custom_interval_and_dry_run(self) -> None:
        for year in (1337, 1361, 1362, 1387):
            self.autosave(year)
        archiver = self.archiver(interval=25, anchor=1337, dry_run=True)
        self.assertEqual([r["date"] for r in self.cycle(archiver)], ["1337.1.1", "1362.1.1", "1387.1.1"])
        self.assertFalse(self.out.exists())

    def test_cli_once(self) -> None:
        self.autosave(1337)
        self.autosave(1340)
        with mock.patch("sys.stdout"):
            code = main(["--save-dir", str(self.saves), "--out", str(self.out), "--once",
                         "--min-free-gb", "0"])
        self.assertEqual(code, 0)
        self.assertEqual(self.archived_dates(), ["1337.1.1", "1340.1.1"])


if __name__ == "__main__":
    unittest.main()
