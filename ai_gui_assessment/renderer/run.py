"""Render a GUI screen from the real game/SOL .gui files.

usage: run.py situation|location|tooltip|event|market|government|battle
"""
import os
import sys
import time
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.setrecursionlimit(20000)
import threading
threading.stack_size(256 * 1024 * 1024 - 4096)

from PIL import Image

import scenarios
from data import Evaluator, Formats, Loc, TextIcons
from engine import Engine
from gui import Expander, GuiDB, dump
from textures import TEXTURES

OUT = Path(__file__).resolve().parents[1] / "images"
if os.environ.get("RENDER_OUT"):
    OUT = OUT / os.environ["RENDER_OUT"]
# 1080p, UI scale 100%: 1 GUI unit = 1 screen pixel; lateral panel height = 1080 - topbar 40 - panel bar 90
SCREEN_H = 1080
PANEL_H = SCREEN_H - 130
SCALE = float(os.environ.get("RENDER_SCALE", "1"))


def setup(mocks):
    t = time.time()
    db = GuiDB()
    loc = Loc()
    log = []
    ev = Evaluator(mocks, loc, log)
    ex = Expander(db)
    eng = Engine(ex, ev, loc, Formats(), TextIcons(), SCALE)
    print(f"loaded in {time.time() - t:.1f}s")
    return db, ex, ev, eng, log


def walk(el):
    yield el
    for c in el.children:
        yield from walk(c)


def find_root(db, suffix, key=None, name=None):
    for path, nodes in db.roots.items():
        if path.replace("\\", "/").endswith(suffix):
            for n in nodes:
                if (key is None or n.key == key) and (name is None or any(
                    c.key == "name" and c.value == name for c in n.value if n.is_block()
                )):
                    return path, n
    raise SystemExit(f"root not found {suffix} {key}")


def report(eng, log, el):
    c = Counter(log)
    print("unknown expressions:", len(c))
    for k, v in c.most_common(400):
        print(f"  {v:4d}  {k}")
    if eng.unresolved_contexts:
        print("unresolved datacontexts:", len(eng.unresolved_contexts))
        for path in sorted(eng.unresolved_contexts):
            print(f"  {path}")
    if TEXTURES.missing:
        print("missing textures:", sorted(TEXTURES.missing)[:30])


def render_panel(eng, el, w, h, extra_bottom=0, bg=(12, 14, 18, 255)):
    eng.place(el, 0, 0, w, h + extra_bottom)
    img = Image.new("RGBA", (int(w * SCALE), int(h * SCALE)), bg)
    eng.render(el, img)
    return img


def situation(panel_h=PANEL_H):
    db, ex, ev, eng, log = setup(scenarios.situation())
    path, n = find_root(db, "panels/situation/global_living_standard.gui")
    el = ex.build(n.key, n.value, {}, path, n.line)
    img = render_panel(eng, el, 570, panel_h, extra_bottom=130)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / "r1_situation_panel.png")
    # unclipped variant: grow the panel until the scroll area shows everything
    sa = [e for e in walk(el) if e.kind == "scrollarea" and e.w > 0]
    grow = max([max([c.h for c in s_.children if c.h] or [0]) - s_.h for s_ in sa] or [0])
    el2 = ex.build(n.key, n.value, {}, path, n.line)
    render_panel(eng, el2, 570, panel_h + max(0, grow), extra_bottom=130).save(OUT / "r1_situation_panel_full.png")
    report(eng, log, el)
    Path(OUT / "r1_tree.txt").write_text("\n".join(dump(el)), encoding="utf-8")


def location(panel_h=PANEL_H, tab="demography", tag="r2"):
    db, ex, ev, eng, log = setup(scenarios.location(tab))
    path, n = find_root(db, "in_game/gui/location_window.gui", "lateralview")
    el = ex.build(n.key, n.value, {}, path, n.line)
    img = render_panel(eng, el, 570, panel_h, extra_bottom=130)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{tag}_location_window.png")
    sa = [e for e in walk(el) if e.kind == "scrollarea" and e.w > 0]
    grow = max([max([c.h for c in s_.children if c.h] or [0]) - s_.h for s_ in sa] or [0])
    if grow > 20:  # only worth a second image when the scroll content is clipped noticeably
        el2 = ex.build(n.key, n.value, {}, path, n.line)
        render_panel(eng, el2, 570, panel_h + grow, extra_bottom=130).save(OUT / f"{tag}_location_window_full.png")
    report(eng, log, el)
    Path(OUT / f"{tag}_tree.txt").write_text("\n".join(dump(el)), encoding="utf-8")


def tooltip():
    db, ex, ev, eng, log = setup(scenarios.tooltip())
    body = db.templates["StandardofLiving_tooltip"]
    tt = [n for n in body if n.is_block()][0]
    el = ex.build(tt.key, tt.value, {}, "SOL_economy_local.gui", 0)
    m = eng.measure(el, None)
    w, h = m["hint"]
    print("tooltip size", w, h)
    pad = 20
    eng.place(el, pad, pad, w, h)
    img = Image.new("RGBA", (int((w + 2 * pad) * SCALE), int((h + 2 * pad) * SCALE)), (40, 52, 46, 255))
    eng.render(el, img)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / "r3_location_sol_tooltip.png")
    report(eng, log, el)
    Path(OUT / "r3_tree.txt").write_text(chr(10).join(dump(el)), encoding="utf-8")



def goods_tooltip(good="wine"):
    """Render the goods tooltip with the SOL substitute-group section.

    The section lives in the overridden main_menu/gui/shared/goods_details.gui, which
    every goods tooltip splices with `using = goods_details`, so this checks the one
    file that reaches Goods_tooltip, Goods_Cards_tooltip and SpecificGoodsMarket_tooltip.
    """
    db, ex, ev, eng, log = setup(scenarios.goods_tooltip(good))
    body = db.templates["Goods_tooltip"]
    tt = [n for n in body if n.is_block()][0]
    el = ex.build(tt.key, tt.value, {}, "in_game/gui/shared/production_tooltips.gui", 0)
    m = eng.measure(el, None)
    w, h = m["hint"]
    print("goods tooltip size", w, h)
    pad = 20
    eng.place(el, pad, pad, w, h)
    img = Image.new("RGBA", (int((w + 2 * pad) * SCALE), int((h + 2 * pad) * SCALE)), (40, 52, 46, 255))
    eng.render(el, img)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / "r4_goods_tooltip.png")
    report(eng, log, el)
    Path(OUT / "r4_tree.txt").write_text(chr(10).join(dump(el)), encoding="utf-8")


def ui_library(tab="cards", *subs, w=1920, h=1080):
    """run.py ui_library TAB [var=value ...]  e.g. ui_library cards ui_library_text_tabs=cards1"""
    sub = dict(x.split("=", 1) for x in subs) or None
    db, ex, ev, eng, log = setup(scenarios.ui_library(tab, sub))
    path, n = find_root(db, "in_game/gui/ui_library.gui", "window")
    el = ex.build(n.key, n.value, {}, path, n.line)
    eng.place(el, 0, 0, w, h)
    img = Image.new("RGBA", (int(w * SCALE), int(h * SCALE)), (0, 0, 0, 255))
    eng.render(el, img)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"lib_{tab}" + ("_" + "_".join(sub.values()) if sub else "")
    img.save(OUT / f"{tag}.png")
    report(eng, log, el)
    Path(OUT / f"{tag}_tree.txt").write_text(chr(10).join(dump(el)), encoding="utf-8")


def vanilla(which, w=1920, h=1080):
    """Render one data-backed vanilla screen on a full-size canvas.

    The map and 3D scenes are intentionally left as the neutral canvas; the
    lateral/window itself uses the same GUI files and layout as the game.
    """
    configs = {
        "event": (scenarios.event, "in_game/gui/eventwindow.gui", "window", 0, 0, w, h),
        "market": (scenarios.market, "in_game/gui/selected_market_view.gui", "lateralview", 0, 130, 570, h - 130),
        "government": (scenarios.government, "in_game/gui/government_lateralview.gui", "lateralview", 0, 130, 570, h - 130),
        "battle": (scenarios.battle, "in_game/gui/battle_lateralview.gui", "lateralview", 0, 130, 570, h - 130),
    }
    make_scenario, suffix, key, x, y, pw, ph = configs[which]
    db, ex, ev, eng, log = setup(make_scenario())
    path, n = find_root(db, suffix, key, "event_window" if which == "event" else None)
    el = ex.build(n.key, n.value, {}, path, n.line)
    if which == "event":
        mw, mh = eng.measure(el, None)["hint"]
        x, y, pw, ph = (w - mw) / 2, max(130.0, (h - mh) / 2), mw, mh
    eng.place(el, x, y, pw, ph)
    img = Image.new("RGBA", (int(w * SCALE), int(h * SCALE)), (29, 35, 42, 255))
    eng.render(el, img)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{which}.png")
    report(eng, log, el)
    Path(OUT / f"{which}_tree.txt").write_text(chr(10).join(dump(el)), encoding="utf-8")

def _main():
    which = sys.argv[1] if len(sys.argv) > 1 else "situation"
    if which in ("event", "market", "government", "battle"):
        vanilla(which, *sys.argv[2:])
    else:
        globals()[which](*sys.argv[2:])


if __name__ == "__main__":
    # deep GUI trees (e.g. the 19k-line ui_library) need a big stack
    error = []

    def run_main():
        try:
            _main()
        except BaseException:
            error.append(sys.exc_info())

    t = threading.Thread(target=run_main)
    t.start()
    t.join()
    if error:
        _, exc, tb = error[0]
        raise exc.with_traceback(tb)
