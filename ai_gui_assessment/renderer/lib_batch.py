"""Render every UI Library page that has a matching screenshot (screenshots/ui_library/INDEX.txt), in one process.

usage: lib_batch.py [tag ...]
"""
import re
import sys
import threading
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.setrecursionlimit(20000)
threading.stack_size(256 * 1024 * 1024 - 4096)

from PIL import Image

import scenarios
from data import Evaluator, Formats, Loc, TextIcons
from engine import Engine
from gui import Expander, GuiDB, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "images" / "ui_library"
INDEX = ROOT / "screenshots" / "ui_library" / "INDEX.txt"


def pages():
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\S+ -> (\S+)\.png\s+\((.*)\)", line)
        if m:
            args = m.group(2).split()
            yield m.group(1), args[0], dict(a.split("=", 1) for a in args[1:])


def main():
    want = set(sys.argv[1:])
    t = time.time()
    db, loc, fm, ic = GuiDB(), Loc(), Formats(), TextIcons()
    print(f"loaded {time.time() - t:.1f}s")
    root = next((p, n) for p, nodes in db.roots.items() if p.replace("\\", "/").endswith("in_game/gui/ui_library.gui")
                for n in nodes if n.key == "window")
    OUT.mkdir(parents=True, exist_ok=True)
    for tag, tab, sub in pages():
        if want and tag not in want:
            continue
        log = []
        ev = Evaluator(scenarios.ui_library(tab, sub or None), loc, log)
        ex = Expander(db)
        eng = Engine(ex, ev, loc, fm, ic, 1.0)
        el = ex.build(root[1].key, root[1].value, {}, root[0], root[1].line)
        eng.place(el, 0, 0, 1920, 1080)
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 255))
        eng.render(el, img)
        img.save(OUT / f"{tag}.png")
        (OUT / f"{tag}_tree.txt").write_text("\n".join(dump(el)), encoding="utf-8")
        print(f"{tag:36s} unknown={len(set(log))}", flush=True)


if __name__ == "__main__":
    th = threading.Thread(target=main)
    th.start()
    th.join()
