import sys
sys.path.insert(0, "ai_gui_assessment/renderer")
import scenarios
from data import Evaluator, Formats, Loc, TextIcons
from engine import Engine
from gui import Expander, GuiDB

db = GuiDB()
loc = Loc()
ev = Evaluator(scenarios.ui_library("cards", {"ui_library_text_tabs": "cards1"}), loc, [])
ex = Expander(db)
eng = Engine(ex, ev, loc, Formats(), TextIcons(), 1.0)
path, node = next((p, n) for p, nodes in db.roots.items()
                  if p.replace("\\", "/").endswith("in_game/gui/ui_library.gui")
                  for n in nodes if n.key == "window")
el = ex.build(node.key, node.value, {}, path, node.line)

def show(e, depth=0):
    m = eng.measure(e, None)
    interesting = e.typename in {
        "ContextualTooltipType", "ContextualTooltipHeader", "TooltipBlockList",
        "TooltipBlockListContent", "TooltipContentSection", "TooltipTableField",
    }
    if interesting:
        props = {k: e.props[k] for k in (
            "minimumsize", "maximumsize", "layoutpolicy_horizontal", "layoutpolicy_vertical",
            "autoresize", "multiline", "max_width", "size", "set_parent_size_to_minimum",
        ) if k in e.props}
        print(" " * depth, e.typename, e.kind, "measure", m, "props", props)
    for c in e.children:
        show(c, depth + 1)

eng.place(el, 0, 0, 1920, 1080)

def find_cards(e):
    if e.typename in {"ExtraContentTooltipType", "TooltipUIActionBlock", "TooltipFunctionalBlock"}:
        print("NODE", e.typename, e.kind, "rect", e.x, e.y, e.w, e.h, "props", e.props)
        for c in e.children:
            print(" CHILD", c.typename, c.kind, "rect", c.x, c.y, c.w, c.h, "props", c.props)
            for cc in c.children:
                print("  GRAND", cc.typename, cc.kind, "rect", cc.x, cc.y, cc.w, cc.h, "props", cc.props)
                for ccc in cc.children:
                    if ccc.kind == "icon" or ccc.typename in {"TooltipFunctionalBlock", "TooltipUIActionBlock"}:
                        print("   GREAT", ccc.typename, ccc.kind, "rect", ccc.x, ccc.y, ccc.w, ccc.h, "props", ccc.props)
    for c in e.children:
        find_cards(c)

find_cards(el)

def active_icons(e):
    if e.kind == "icon" and e.w > 0:
        print("ACTIVE_ICON", e.typename, e.x, e.y, e.w, e.h, "size", e.props.get("size"), "tex", e.props.get("texture"))
    for c in e.children:
        active_icons(c)
active_icons(el)

for e in (x for x in [el] if False):
    pass
targets = [x for x in []]
def collect(e):
    if e.typename in {"ContextualTooltipType", "TooltipBlockList", "TooltipBlockListContent", "TooltipContentSection"}:
        targets.append(e)
    for c in e.children:
        collect(c)
collect(el)
for e in targets:
    print("TARGET", e.typename, "kind", e.kind, "props", e.props.get("minimumsize"))
    for aw in (None, 400, 420, 428, 430, 450, 749):
        print("  avail", aw, eng.measure(e, aw))

eng.place(el, 0, 0, 1920, 1080)
for e in targets:
    print("PLACED", e.typename, e.x, e.y, e.w, e.h)

def find(e):
    if e.typename == "TooltipFunctionalBlock":
        print("FUNCTIONAL", e.x, e.y, e.w, e.h)
        for c in e.children:
            print(" CHILD", c.typename, c.kind, c.x, c.y, c.w, c.h, c.props)
            for cc in c.children:
                print("  GRAND", cc.typename, cc.kind, cc.x, cc.y, cc.w, cc.h, cc.props)
                for ccc in cc.children:
                    print("   GREAT", ccc.typename, ccc.kind, ccc.x, ccc.y, ccc.w, ccc.h, ccc.props)
    for c in e.children:
        find(c)
find(el)
