"""Layout + render engine for expanded Jomini GUI element trees."""
from __future__ import annotations

import math
import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from data import Unknown, format_number, parse_expr
from gui import Element
from text import RichText, TextStyle
from textures import TEXTURES, compose, lower_spec, sprite, select_frame, to_np, from_np, blend, parse_color

INF = 1e9
ZERO = {"hint": (0.0, 0.0), "min": (0.0, 0.0), "max": (0.0, 0.0)}
BOX = ("hbox", "vbox")
TEXT = ("textbox", "editbox")


def num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def split_top(s: str, sep="|"):
    depth, q, out, cur = 0, False, [], ""
    for ch in s:
        if ch == "'":
            q = not q
        if not q:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == sep and depth == 0:
                out.append(cur)
                cur = ""
                continue
        cur += ch
    out.append(cur)
    return out


class Engine:
    def __init__(self, ex, ev, loc, formats, icons, scale=2.0):
        self.ex, self.ev, self.loc, self.formats, self.icons = ex, ev, loc, formats, icons
        self.scale = scale
        self.missing_text = []
        self.unresolved_contexts = set()

    # ------------------------------------------------------------ data helpers
    def push(self, el):
        count = 0
        it = getattr(el, "ctx_item", None)
        if it is not None:
            self.ev.item_stack.append(it)
            count += 1
        for expr in el.props.get("datacontexts", []):
            log_start = len(self.ev.log)
            context = self.ev.eval_str(expr)
            if isinstance(context, dict):
                self.ev.item_stack.append(context)
                count += 1
            elif isinstance(context, Unknown):
                self.unresolved_contexts.add(context.path)
                del self.ev.log[log_start:]
        return count

    def pop(self, pushed):
        for _ in range(pushed):
            self.ev.item_stack.pop()

    def visible(self, el) -> bool:
        v = el.props.get("visible")
        if v is None:
            return True
        return self.ev.truthy(v, default=True)

    def resolve(self, v):
        if isinstance(v, str) and v.startswith("[") and v.endswith("]"):
            r = self.ev.eval_str(v)
            return None if isinstance(r, Unknown) else r
        return v

    def expr_text(self, inner: str) -> str:
        parts = split_top(inner)
        e = parts[0]
        fmt = parts[1] if len(parts) > 1 else ""
        node = parse_expr(e)
        # concept references: [population_growth|e]
        if node[0] == "chain" and len(node[1]) == 1 and node[1][0][1] is None and fmt.lower() in ("e", "e", ""):
            name = node[1][0][0]
            for key in (f"game_concept_{name}", name):
                lv = self.loc.get(key)
                if lv and not isinstance(self.ev.lookup(name), (int, float, str)) :
                    lv = self.process(lv, raw=True)
                    return f"#E {lv}#!" if fmt else lv
        v = self.ev.eval(node)
        if isinstance(v, Unknown):
            self.missing_text.append(e)
            return f"#debug {e.split('.')[-1][:18]}#!"
        if isinstance(v, bool):
            return ""
        if isinstance(v, (int, float)):
            return format_number(v, fmt)
        s = str(v)
        if fmt in ("L", "l"):
            return s
        if fmt in ("E", "e"):
            return f"#E {s}#!"
        return s

    def process(self, s: str, raw=False, depth=0) -> str:
        if s is None:
            return ""
        s = str(s)
        # The engine consumes punctuation as part of the format name when a
        # separator is missing (#R- / #E/). Our rich-text parser used to accept it.
        for match in re.finditer(r"(?<!#)#([A-Za-z_][A-Za-z0-9_]*[-/])", s):
            error = f"INVALID TEXT FORMAT: missing whitespace after #{match.group(1)[:-1]}"
            if error not in self.ev.log:
                self.ev.log.append(error)
        if not raw and re.fullmatch(r"[A-Za-z0-9_.\-]+", s):
            lv = self.loc.get(s)
            if lv is not None:
                s = lv
        if depth > 4:
            return s
        s = re.sub(r"\$([A-Za-z0-9_.\-]+)(\|[^$]*)?\$", lambda m: self.process(self.loc.get(m.group(1)) or m.group(1), True, depth + 1), s)
        out, i = "", 0
        while i < len(s):
            if s[i] == "[":
                d, j = 0, i
                while j < len(s):
                    if s[j] == "[":
                        d += 1
                    elif s[j] == "]":
                        d -= 1
                        if d == 0:
                            break
                    j += 1
                inner = s[i + 1:j]
                out += self.process(self.expr_text(inner), True, depth + 1)
                i = j + 1
            else:
                out += s[i]
                i += 1
        return out

    def text_of(self, el) -> str | None:
        if "raw_text" in el.props:
            return self.process(el.props["raw_text"], raw=True)
        if "text" in el.props:
            return self.process(el.props["text"])
        return None

    def richtext(self, el, max_width=None, size_override=None):
        key = ("rt", max_width, size_override)
        cache = el.__dict__.setdefault("_rt", {})
        if key in cache:
            return cache[key]
        # Validate inherited text-colour bindings too. Previously the renderer
        # skipped this property, hiding missing ExtraTooltipInfo in panel text.
        if "fonttintcolor" in el.props:
            self.resolve(el.props["fonttintcolor"])
        s = self.text_of(el) or ""
        font = el.props.get("font", "StandardGameFont")
        size = size_override or num(el.props.get("fontsize"), 15)
        df = el.props.get("default_format")
        df = df[1:] if isinstance(df, str) and df.startswith("#") else df
        st = TextStyle(self.formats, font, size, df)
        multiline = el.props.get("multiline") == "yes"
        mw = max_width
        if el.props.get("max_width"):
            mw = min(mw or INF, num(el.props["max_width"]))
        rt = RichText(s, st, self.icons, self.scale, max_width=mw, multiline=multiline)
        cache[key] = rt
        return rt

    # ------------------------------------------------------------ datamodel expansion
    def realize(self, el: Element):
        """Instantiate datamodel items once (children appended, tagged with ctx_item)."""
        if getattr(el, "_realized", False):
            return
        el._realized = True
        dm = el.props.get("datamodel")
        # A dropdown's open list is a popup owned by the engine.  Its static
        # active item is already expanded by gui.Expander; realizing every
        # option here would paint the closed list on top of the control.
        if dm and el.item is not None and el.kind != "dropdown":
            items = self.ev.eval_str(dm)
            if isinstance(items, list):
                for index, it in enumerate(items):
                    if isinstance(it, dict):
                        # Jomini exposes the current data-model index through
                        # PdxGuiWidget while evaluating row backgrounds/layout.
                        it = dict(it)
                        it.setdefault("PdxGuiWidget.GetIndexInDataModel", index)
                        it.setdefault("PdxGuiWidget.GetIndexInParent", index)
                    ch = self.ex.build_lazy(el.item)
                    ch.ctx_item = it
                    ch.props["__dm_item__"] = True
                    el.children.append(ch)

    def layout_children(self, el):
        """Children taking part in box layout. Hidden children take neither size nor spacing, with or without
        `ignoreinvisible` (confirmed in game: situation panel card sits directly under the tab bar)."""
        return [c for c in self.vis_children(el) if c.props.get("ignore_layout") != "yes"]

    def _shown(self, c):
        p = self.push(c)
        v = self.visible(c)
        self.pop(p)
        return v

    def vis_children(self, el):
        self.realize(el)
        out = []
        for c in el.children:
            p = self.push(c)
            v = self.visible(c)
            self.pop(p)
            if v:
                out.append(c)
        return out

    # ------------------------------------------------------------ sizes
    def size_prop(self, el, key="size"):
        v = el.props.get(key)
        if v is None:
            return None
        if isinstance(v, str):
            r = self.resolve(v)
            if isinstance(r, tuple) and r and r[0] == "vec":
                return [str(r[1]), str(r[2])]
            return None
        return v

    def margins(self, el):
        m = el.props.get("margin")
        l = r = t = b = 0.0
        if isinstance(m, list):
            l = r = num(m[0])
            t = b = num(m[1] if len(m) > 1 else m[0])
        l = num(el.props.get("margin_left"), l)
        r = num(el.props.get("margin_right"), r)
        t = num(el.props.get("margin_top"), t)
        b = num(el.props.get("margin_bottom"), b)
        return l, t, r, b

    def policy(self, el, axis):
        p = el.props.get("layoutpolicy_horizontal" if axis == 0 else "layoutpolicy_vertical", "fixed")
        return str(p).lower()

    def minmax(self, el):
        mn = self.size_prop(el, "minimumsize")
        mx = self.size_prop(el, "maximumsize")
        mnw = num(mn[0], -1) if mn else -1
        # min_width / max_width on non-text elements act like minimumsize / maximumsize width
        # (confirmed in game: ui_library vbox_component_entry "min_width = 800")
        if el.kind not in TEXT and el.props.get("min_width") is not None:
            mnw = max(mnw, num(el.props["min_width"]))
        mnh = num(mn[1], -1) if mn else -1
        mxw = num(mx[0], -1) if mx else -1
        # text max_width caps the element width, so an expanding text_multi stops at max_width and the parent
        # box centres it (confirmed in game: ui_library descriptions are 600px blocks centred in their card)
        if el.kind in TEXT and el.props.get("max_width") is not None:
            l, t, r, b = self.margins(el)
            cap = num(el.props["max_width"]) + l + r
            mxw = cap if mxw < 0 else min(mxw, cap)
        mxh = num(mx[1], -1) if mx else -1
        return mnw, mnh, mxw, mxh

    def measure(self, el, avail_w=None):
        """-> dict(hint=(w,h), min=(w,h), max=(w,h))"""
        p = self.push(el)
        try:
            return self._measure(el, avail_w)
        finally:
            self.pop(p)

    def _measure(self, el, avail_w):
        cache = el.__dict__.setdefault("_meas", {})
        if avail_w in cache:
            return cache[avail_w]
        size = self.size_prop(el)
        sw = sh = None
        if size:
            s0, s1 = str(size[0]), str(size[1] if len(size) > 1 else size[0])
            sw = None if s0.endswith("%") or num(s0, -1) < 0 else num(s0)
            sh = None if s1.endswith("%") or num(s1, -1) < 0 else num(s1)
        l, t, r, b = self.margins(el)
        hw = hh = 0.0
        kind = el.kind
        multiline_expands = False
        if kind in BOX:
            kids = self.layout_children(el)
            sp = num(el.props.get("spacing"), 0)
            inner_avail = None if avail_w is None else max(0, avail_w - l - r)
            # If no parent width is available, use the declared minimum as the
            # wrapping width.  Once a parent supplies a wider box, its width
            # is the actual text width; treating the minimum as a cap would
            # wrap tooltip paragraphs one line too early.
            declared_min = self.size_prop(el, "minimumsize")
            if declared_min:
                declared_w = num(declared_min[0], -1)
                if declared_w >= 0 and inner_avail is None:
                    min_content = max(0, declared_w - l - r)
                    inner_avail = min_content
            measured = []
            for c in kids:
                if not self._shown(c):
                    measured.append(ZERO)
                    continue
                child_avail = inner_avail if kind == "vbox" else None
                # Multiline text in a row needs the row's available width in
                # order to wrap.  Other hbox children keep their intrinsic
                # width so columns and spacer widgets still measure normally.
                if (kind == "hbox" and inner_avail is not None and c.kind in TEXT
                        and c.props.get("multiline") == "yes"):
                    child_avail = inner_avail
                measured.append(self.measure(c, child_avail))
            ms = measured
            if kind == "hbox":
                multiline_expands = any(
                    c.kind in TEXT and c.props.get("multiline") == "yes"
                    and m["hint"][1] > 30.01
                    for c, m in zip(kids, ms)
                )
                hw = sum(m["hint"][0] for m in ms) + sp * max(0, len(ms) - 1)
                hh = max([m["hint"][1] for m in ms] or [0])
                mw = sum(m["min"][0] for m in ms) + sp * max(0, len(ms) - 1)
                mh = max([m["min"][1] for m in ms] or [0])
            else:
                hh = sum(m["hint"][1] for m in ms) + sp * max(0, len(ms) - 1)
                hw = max([m["hint"][0] for m in ms] or [0])
                mh = sum(m["min"][1] for m in ms) + sp * max(0, len(ms) - 1)
                mw = max([m["min"][0] for m in ms] or [0])
            hw += l + r
            hh += t + b
            mw += l + r
            mh += t + b
        elif kind in TEXT:
            autoresize = el.props.get("autoresize", "no") == "yes"
            maxw = None
            if el.props.get("multiline") == "yes":
                maxw = num(el.props.get("max_width"), 0) or sw or (avail_w - l - r if avail_w else None)
            rt = self.richtext(el, maxw)
            tw, th = rt.width + l + r, rt.height + t + b
            hw = tw if (autoresize or sw is None) else sw
            if el.props.get("max_width"):
                hw = min(hw, num(el.props["max_width"]) + l + r)
            if el.props.get("min_width"):
                hw = max(hw, num(el.props["min_width"]))
            # autoresize text takes its own line height (fontsize 15 -> 21) and ignores the template's size {0 23}
            hh = th if (autoresize or el.props.get("multiline") == "yes") else (sh if sh is not None else th)
            mw, mh = (hw if autoresize else 0), hh
        elif kind in ("fixedgridbox",):
            n = self._dm_count(el)
            cw = str(el.props.get("addcolumn", "0"))
            rh = num(el.props.get("addrow"), 0)
            wrap = int(num(el.props.get("datamodel_wrap"), 0) or num(el.props.get("maxhorizontalslots"), 0) or 0)
            if cw.endswith("%"):
                cols = 1
                hw = 0
            else:
                cols = wrap or max(n, 1)
                hw = num(cw) * min(cols, max(n, 1))
            rows = math.ceil(n / max(cols, 1)) if n else 0
            hh = rows * rh
            mw, mh = hw, hh
        elif kind in ("dynamicgridbox", "flowcontainer", "overlappingitembox", "container"):
            kids = self.vis_children(el)
            ms = [self.measure(c, avail_w) for c in kids]
            sp = num(el.props.get("spacing"), 0)
            vertical = el.props.get("direction") == "vertical" or kind == "dynamicgridbox"
            if el.props.get("flipdirection") == "yes" and kind == "dynamicgridbox":
                vertical = False
            wrap = int(num(el.props.get("datamodel_wrap"), 0)) if kind == "dynamicgridbox" and not vertical else 0
            if wrap > 0:
                rows = [ms[i:i + wrap] for i in range(0, len(ms), wrap)]
                hh = sum(max(m["hint"][1] for m in row) for row in rows) + sp * max(0, len(rows) - 1)
                hw = max((sum(m["hint"][0] for m in row) + sp * (len(row) - 1) for row in rows), default=0)
            elif vertical:
                hh = sum(m["hint"][1] for m in ms) + sp * max(0, len(ms) - 1)
                hw = max([m["hint"][0] for m in ms] or [0])
            else:
                hw = sum(m["hint"][0] for m in ms) + sp * max(0, len(ms) - 1)
                hh = max([m["hint"][1] for m in ms] or [0])
            hw += l + r
            hh += t + b
            mw, mh = hw, hh
        elif kind == "scrollarea":
            kids = self.vis_children(el)
            ms = [self.measure(c, avail_w) for c in kids]
            hw = max([m["hint"][0] for m in ms] or [0])
            hh = max([m["hint"][1] for m in ms] or [0])
            mw, mh = 0, 0
        else:
            # widget-like: hint from size; or from children that resize parent
            kids = self.vis_children(el)
            # Cap intrinsic tooltip text width, but retain a wider declared
            # minimum when a tooltip contains fixed-width columns.
            if kind == "tooltip_widget":
                # Frontend tooltips reserve a 420px content budget. The
                # contextual card uses the ordinary compact width, while the
                # frontend DLC card gets the wider budget.
                tooltip_avail = 450.0 if el.typename == "ContextualTooltipType" else 470.0
            else:
                tooltip_avail = avail_w
            child_min_w = 0.0
            for c in kids:
                if c.props.get("set_parent_size_to_minimum") == "yes" or c.props.get("resizeparent") == "yes":
                    # A shrinking child reports its intrinsic size.  Passing the
                    # free parent width into it makes expanding descendants
                    # consume the whole slot, which is wrong for contextual
                    # tooltips: their table content has a 400px minimum and the
                    # outer widget must remain a compact, centered card.
                    if kind == "tooltip_widget":
                        child_avail = tooltip_avail
                    else:
                        child_avail = None if self.policy(c, 0) == "shrinking" else avail_w
                    m = self.measure(c, child_avail)
                    hw = max(hw, m["hint"][0])
                    hh = max(hh, m["hint"][1])
                    child_min_w = max(child_min_w, m["min"][0])
            if kind in ("icon", "button") and sw is None and sh is None and not size:
                tex = self.resolve(el.props.get("texture"))
                img = TEXTURES.load(tex) if isinstance(tex, str) else None
                if img is not None:
                    img = select_frame(img, lower_spec(el.props))
                    d = num(el.props.get("texture_density"), 1) or 1
                    hw, hh = img.width / d, img.height / d
            mw, mh = 0, 0
            if kind == "tooltip_widget":
                hw = max(min(hw, tooltip_avail), child_min_w)
        if sw is not None and not (kind in TEXT and el.props.get("autoresize") == "yes"):
            hw = sw
            mw = sw
        if sh is not None and kind not in BOX:
            if not (kind in TEXT and (el.props.get("autoresize") == "yes" or el.props.get("multiline") == "yes")):
                hh = sh
            elif kind in TEXT and el.props.get("multiline") == "yes" and el.props.get("autoresize") != "yes":
                hh = max(sh, hh)
            mh = hh
        elif sh is not None:
            hh = mh = sh
        if sw is not None and kind in BOX:
            hw = mw = sw
        mnw, mnh, mxw, mxh = self.minmax(el)
        maxw, maxh = INF, INF
        if mnw >= 0:
            hw, mw = max(hw, mnw), max(mw, mnw)
        if mnh >= 0:
            hh, mh = max(hh, mnh), max(mh, mnh)
        if mxw >= 0:
            maxw = mxw
            hw, mw = min(hw, mxw), min(mw, mxw)
        if mxh >= 0:
            maxh = mxh
            # TooltipTableField declares a 30px row for ordinary one-line
            # values, but its text child is also a multiline autoresized
            # textbox.  The game lets that child grow the row when wrapping
            # produces more than one line; applying the hbox maximum here
            # would paint the following rows over the paragraph.
            if not (multiline_expands and hh > mxh + 0.01):
                hh, mh = min(hh, mxh), min(mh, mxh)
        res = {"hint": (hw, hh), "min": (mw, mh), "max": (maxw, maxh)}
        cache[avail_w] = res
        return res

    def _dm_count(self, el):
        self.realize(el)
        return len([c for c in el.children if c.props.get("__dm_item__")])

    # ------------------------------------------------------------ placement
    def place(self, el, x, y, w, h):
        p = self.push(el)
        try:
            self._place(el, x, y, w, h)
        finally:
            self.pop(p)

    def _place(self, el, x, y, w, h):
        el.x, el.y, el.w, el.h = x, y, w, h
        kind = el.kind
        l, t, r, b = self.margins(el)
        if kind in BOX:
            self._place_box(el, x + l, y + t, max(0, w - l - r), max(0, h - t - b), 0 if kind == "hbox" else 1)
        elif kind == "fixedgridbox":
            kids = [c for c in self.vis_children(el)]
            cw = str(el.props.get("addcolumn", "0"))
            colw = w * num(cw[:-1]) / 100 if cw.endswith("%") else num(cw)
            rh = num(el.props.get("addrow"), 0)
            wrap = int(num(el.props.get("datamodel_wrap"), 0) or num(el.props.get("maxhorizontalslots"), 0) or 0)
            cols = 1 if cw.endswith("%") else (wrap or max(len(kids), 1))
            for i, c in enumerate(kids):
                cx, cy = x + (i % cols) * colw, y + (i // cols) * rh
                self._place_free(c, cx, cy, colw, rh)
        elif kind in ("dynamicgridbox", "flowcontainer", "overlappingitembox", "container"):
            kids = self.vis_children(el)
            sp = num(el.props.get("spacing"), 0)
            vertical = el.props.get("direction") == "vertical" or kind == "dynamicgridbox"
            if el.props.get("flipdirection") == "yes" and kind == "dynamicgridbox":
                vertical = False
            wrap = int(num(el.props.get("datamodel_wrap"), 0)) if kind == "dynamicgridbox" and not vertical else 0
            cx, cy = x + l, y + t
            if wrap > 0:
                for start in range(0, len(kids), wrap):
                    row = kids[start:start + wrap]
                    heights = [self.measure(c, w)["hint"][1] for c in row]
                    row_h = max(heights)
                    cx = x + l
                    cell_w = (w - l - r - sp * (wrap - 1)) / wrap
                    for c in row:
                        cw_, ch_ = self.measure(c, cell_w)["hint"]
                        cell = cell_w if self.size_prop(c) and str(self.size_prop(c)[0]).endswith("%") else cw_
                        self._place_free(c, cx, cy, cell, ch_)
                        cx += cell + sp
                    cy += row_h + sp
            else:
                for c in kids:
                    m = self.measure(c, w)
                    cw_, ch_ = m["hint"]
                    if self.policy(c, 0) in ("expanding", "growing", "preferred") and vertical:
                        cw_ = w - l - r
                    self.place(c, cx, cy, cw_, ch_)
                    if vertical:
                        cy += ch_ + sp
                    else:
                        cx += cw_ + sp
        elif kind == "scrollarea":
            kids = self.vis_children(el)
            for c in kids:
                m = self.measure(c, w)
                ch_ = max(h, m["hint"][1])
                self.place(c, x, y, w, ch_)
            el.clip = (x, y, w, h)
        else:
            for c in self.vis_children(el):
                self._place_free(c, x, y, w, h)

    def _place_free(self, c, px, py, pw, ph):
        """Place a child of a free-positioning widget."""
        pu = self.push(c)
        try:
            m = self.measure(c, pw)
            size = self.size_prop(c)
            cw, ch = m["hint"]
            if size:
                s0, s1 = str(size[0]), str(size[1] if len(size) > 1 else size[0])
                if s0.endswith("%"):
                    cw = pw * num(s0[:-1]) / 100
                if s1.endswith("%"):
                    ch = ph * num(s1[:-1]) / 100
            if c.kind in BOX + ("scrollarea", "dynamicgridbox") and not size:
                if c.props.get("set_parent_size_to_minimum") != "yes":
                    cw, ch = pw, ph
                else:
                    cw, ch = m["hint"]
            pa = str(c.props.get("parentanchor", "top|left")).lower()
            wa = str(c.props.get("widgetanchor", pa)).lower()
            pos = c.props.get("position")
            ox = num(pos[0]) if isinstance(pos, list) else 0
            oy = num(pos[1]) if isinstance(pos, list) and len(pos) > 1 else 0

            def anc(a, total, horiz):
                if horiz:
                    if "right" in a:
                        return total
                    if "hcenter" in a or a.strip() == "center" or ("center" in a and "vcenter" not in a and "hcenter" not in a):
                        return total / 2
                    return 0
                if "bottom" in a:
                    return total
                if "vcenter" in a or a.strip() == "center" or ("center" in a and "hcenter" not in a and "vcenter" not in a):
                    return total / 2
                return 0

            x = px + anc(pa, pw, True) - anc(wa, cw, True) + ox
            y = py + anc(pa, ph, False) - anc(wa, ch, False) + oy
            self._place(c, x, y, cw, ch)
        finally:
            self.pop(pu)

    def _place_box(self, el, x, y, w, h, axis):
        # Out-of-flow decorations use the whole box as their percent-size and
        # anchor reference; they do not consume a layout slot or spacing.
        for c in self.vis_children(el):
            if c.props.get("ignore_layout") == "yes":
                self._place_free(c, x, y, w, h)
        kids = self.layout_children(el)
        rev = el.props.get("righttoleft" if axis == 0 else "bottomtotop") == "yes"
        if rev:
            kids = list(reversed(kids))
        if not kids:
            return
        sp = num(el.props.get("spacing"), 0)
        main_total = w if axis == 0 else h
        cross_total = h if axis == 0 else w
        items = []
        for c in kids:
            pu = self.push(c)
            measure_avail = w if axis == 1 else None
            if (axis == 0 and c.kind in TEXT and c.props.get("multiline") == "yes"):
                measure_avail = w
            m = self.measure(c, measure_avail) if self._shown(c) else ZERO
            pol = self.policy(c, axis) if m is not ZERO else "fixed"
            cpol = self.policy(c, 1 - axis)
            hint = m["hint"][axis]
            mn = m["min"][axis]
            mx = m["max"][axis]
            if pol == "fixed":
                lo, hi = hint, hint
            elif pol == "shrinking":
                lo, hi = mn, hint
            elif pol == "growing":
                lo, hi = hint, mx
            else:  # expanding / preferred
                lo, hi = mn, mx
            expansive = pol
            stretch_prop = c.props.get("layoutstretchfactor_horizontal" if axis == 0 else "layoutstretchfactor_vertical")
            if isinstance(stretch_prop, str) and stretch_prop.startswith("["):
                if self.ev.expression_type(parse_expr(stretch_prop[1:-1])) == "float":
                    self.ev.log.append("TYPE ERROR: layoutstretchfactor requires int32, got float: " + stretch_prop)
            stretch = int(self._resolved_num(stretch_prop, 0))
            items.append(dict(c=c, m=m, hint=hint, lo=min(lo, hint), hi=max(hi, hint), exp=expansive, st=stretch,
                              cpol=cpol, size=hint))
            self.pop(pu)
        avail = main_total - sp * (len(items) - 1)
        total_hint = sum(i["hint"] for i in items)
        extra = avail - total_hint
        if extra > 0.01:
            # expanding children take extra space first; growing (e.g. `expand = {}`) only gets leftovers
            for group in ([i for i in items if i["exp"] == "expanding"],
                          [i for i in items if i["exp"] == "growing"],
                          [i for i in items if i["hi"] > i["hint"] + 0.01]):
                active = [i for i in group if i["hi"] > i["size"] + 0.01]
                while extra > 0.01 and active:
                    wsum = sum(i["st"] or 1 for i in active)
                    used = 0
                    nxt = []
                    for i in active:
                        share = extra * (i["st"] or 1) / wsum
                        give = min(share, i["hi"] - i["size"])
                        i["size"] += give
                        used += give
                        if i["hi"] > i["size"] + 0.01:
                            nxt.append(i)
                    extra -= used
                    if used < 0.01:
                        break
                    active = nxt
                if extra <= 0.01:
                    break
        elif extra < -0.01:
            deficit = -extra
            active = [i for i in items if i["size"] > i["lo"] + 0.01]
            while deficit > 0.01 and active:
                tot = sum(i["size"] - i["lo"] for i in active)
                used = 0
                for i in active:
                    take = min(deficit * (i["size"] - i["lo"]) / tot, i["size"] - i["lo"])
                    i["size"] -= take
                    used += take
                deficit -= used
                active = [i for i in active if i["size"] > i["lo"] + 0.01]
                if used < 0.01:
                    break
        leftover = avail - sum(i["size"] for i in items)
        gap = sp
        start = 0.0
        if leftover > 0.01:
            if len(items) > 1:
                gap = sp + leftover / (len(items) - 1)
            else:
                start = leftover / 2
        pos = start
        for i in items:
            c = i["c"]
            m = i["m"]
            chint = m["hint"][1 - axis]
            cmax = m["max"][1 - axis]
            if i["cpol"] in ("expanding", "growing", "preferred"):
                cs = min(cross_total, cmax)
            else:
                cs = min(chint, cross_total) if chint > 0 else chint
            coff = (cross_total - cs) / 2
            if axis == 0:
                self.place(c, x + pos, y + coff, i["size"], cs)
            else:
                self.place(c, x + coff, y + pos, cs, i["size"])
            pos += i["size"] + gap

    # ------------------------------------------------------------ rendering
    def render(self, el, img, alpha=1.0, clip=None, mask=None):
        p = self.push(el)
        try:
            self._render(el, img, alpha, clip, mask)
        finally:
            self.pop(p)

    def px(self, v):
        return int(round(v * self.scale))

    def _paste(self, img, layer, x, y, clip, mask=None):
        if layer is None:
            return
        X, Y = self.px(x), self.px(y)
        if clip:
            cx0, cy0 = self.px(clip[0]), self.px(clip[1])
            cx1, cy1 = cx0 + self.px(clip[2]), cy0 + self.px(clip[3])
            lx0, ly0 = max(X, cx0), max(Y, cy0)
            lx1, ly1 = min(X + layer.width, cx1), min(Y + layer.height, cy1)
            if lx1 <= lx0 or ly1 <= ly0:
                return
            layer = layer.crop((lx0 - X, ly0 - Y, lx1 - X, ly1 - Y))
            X, Y = lx0, ly0
        if mask is not None:
            # ``mask`` is a global alpha image produced by a masked_button.
            # Apply it after rectangle clipping so the layer coordinates stay
            # aligned even when a scroll area has cropped the child.
            mx, my, ma = mask
            mx, my = self.px(mx), self.px(my)
            arr = to_np(layer)
            x0, y0 = max(X, mx), max(Y, my)
            x1, y1 = min(X + layer.width, mx + ma.shape[1]), min(Y + layer.height, my + ma.shape[0])
            if x1 <= x0 or y1 <= y0:
                return
            arr_y0, arr_y1 = y0 - Y, y1 - Y
            arr_x0, arr_x1 = x0 - X, x1 - X
            mask_y0, mask_y1 = y0 - my, y1 - my
            mask_x0, mask_x1 = x0 - mx, x1 - mx
            arr[arr_y0:arr_y1, arr_x0:arr_x1, 3] *= ma[mask_y0:mask_y1, mask_x0:mask_x1]
            # The mask is a hard clipping shape.  Clear any layer pixels
            # outside its bounds instead of letting them leak at the edges.
            if X < mx or Y < my or X + layer.width > mx + ma.shape[1] or Y + layer.height > my + ma.shape[0]:
                keep = np.zeros((layer.height, layer.width), dtype=np.float32)
                keep[arr_y0:arr_y1, arr_x0:arr_x1] = 1.0
                arr[..., 3] *= keep
            layer = from_np(arr)
        if X >= img.width or Y >= img.height or X + layer.width <= 0 or Y + layer.height <= 0:
            return
        if X < 0 or Y < 0:
            layer = layer.crop((max(0, -X), max(0, -Y), layer.width, layer.height))
            X, Y = max(0, X), max(0, Y)
        img.alpha_composite(layer, (X, Y))

    def _res_tex(self, v):
        """Resolver handed to compose(): strings for textures, tuples/lists for data-bound colours,
        numbers for data-bound frame indices."""
        r = self.resolve(v)
        return r if isinstance(r, (str, tuple, list, int, float)) else None

    def _grayscale(self, layer, spec):
        shader = str(spec.get("shaderfile", "")).lower()
        if layer is None or "pdxgui_grayscale.shader" not in shader:
            return layer
        arr = to_np(layer)
        gray = arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722
        arr[..., :3] = gray[..., None]
        return from_np(arr)

    def _mask_for(self, el):
        """Build the global alpha mask owned by a masked_button element."""
        path = self.resolve(el.props.get("mask"))
        if not isinstance(path, str) or el.w <= 0 or el.h <= 0:
            return None
        mimg = TEXTURES.load(path)
        if mimg is None:
            return None
        spec = lower_spec(el.props)
        mimg = select_frame(mimg, spec)
        mimg = sprite(mimg, spec, self.px(el.w), self.px(el.h), self.scale)
        return (el.x, el.y, to_np(mimg)[..., 3])

    def _render(self, el, img, alpha, clip, inherited_mask=None):
        a = alpha * self._resolved_num(el.props.get("alpha"), 1.0)
        if a <= 0.001 or el.w < 0 or el.h < 0:
            return
        own_mask = inherited_mask if str(el.props.get("inherit_mask", "")).lower() == "yes" else None
        descendant_mask = self._mask_for(el) or inherited_mask
        # backgrounds
        for bg in el.backgrounds:
            bgl = lower_spec(bg)
            l = r = t = b = 0.0
            m = bgl.get("margin")
            if isinstance(m, list):
                l = r = num(m[0])
                t = b = num(m[1] if len(m) > 1 else m[0])
            l = num(bgl.get("margin_left"), l)
            r = num(bgl.get("margin_right"), r)
            t = num(bgl.get("margin_top"), t)
            b = num(bgl.get("margin_bottom"), b)
            if bgl.get("visible") is not None and not self.ev.truthy(bgl.get("visible")):
                continue
            w, h = el.w + l + r, el.h + t + b
            if w <= 0 or h <= 0:
                continue
            layer = compose(bg, self.px(w), self.px(h), self.scale, self._res_tex)
            layer = self._grayscale(layer, bgl)
            if layer is not None and a < 1:
                arr = to_np(layer)
                arr[..., 3] *= a
                layer = from_np(arr)
            self._paste(img, layer, el.x - l, el.y - t, clip, own_mask)
        # own content
        if el.kind in ("icon", "button") and el.props.get("texture") and el.w > 0 and el.h > 0:
            spec = dict(el.props)
            spec["modifies"] = el.modifies
            if el.kind == "button":
                down = el.props.get("down")
                spec["frame"] = spec.get("downframe", 1) if (down and self.ev.truthy(down, False)) else spec.get("upframe", 1)
            spec["alpha"] = 1
            layer = compose(spec, self.px(el.w), self.px(el.h), self.scale, self._res_tex)
            layer = self._grayscale(layer, spec)
            if layer is not None:
                if el.glows:
                    self._glow(img, layer, el, clip, a, own_mask)
                if a < 1:
                    arr = to_np(layer)
                    arr[..., 3] *= a
                    layer = from_np(arr)
                self._paste(img, layer, el.x, el.y, clip, own_mask)
        if el.kind == "ranged_slider":
            self._ranged_slider(el, img, a, clip, own_mask)
        if el.kind == "piechart":
            self._pie(el, img, a, clip, own_mask)
        if el.kind == "progressbar":
            self._progressbar(el, img, a, clip, own_mask)
        if el.kind == "barchart":
            self._barchart(el, img, a, clip, own_mask)
        if el.kind == "ecs_scene_viewer_widget":
            self._scene(el, img, clip, own_mask)
        if el.kind in TEXT:
            self._text(el, img, a, clip, own_mask)
        kids = self.vis_children(el)
        cclip = clip
        if getattr(el, "clip", None):
            cclip = el.clip if clip is None else self._intersect(clip, el.clip)
        for c in kids:
            if c.kind in ("pieslice", "barslice", "barslice_no_highlight"):
                continue
            self.render(c, img, a, cclip, descendant_mask)
        if el.kind == "scrollarea" and el.props.get("scrollbar_vertical") and kids:
            self._scrollbar(el, img, max(k.h for k in kids), clip, own_mask)

    def _resolved_num(self, value, default):
        value = self.resolve(value)
        return num(value, default)

    def _texture_layer(self, el, texture, w, h, color=None):
        if not texture or w <= 0 or h <= 0:
            return None
        spec = dict(el.props)
        spec["texture"] = texture
        spec["modifies"] = el.modifies
        spec["alpha"] = 1
        if color is not None:
            spec["color"] = color
        return compose(spec, self.px(w), self.px(h), self.scale, self._res_tex)

    def _progressbar(self, el, img, alpha, clip, mask=None):
        """Render a full-width texture, then crop it to the filled segment."""
        if el.w <= 0 or el.h <= 0:
            return
        minimum = self._resolved_num(el.props.get("min"), 0.0)
        maximum = self._resolved_num(el.props.get("max"), 1.0)
        value = self._resolved_num(el.props.get("value"), minimum)
        fraction = 0.0 if maximum == minimum else (value - minimum) / (maximum - minimum)
        fraction = max(0.0, min(1.0, fraction))
        direction = str(el.props.get("direction", "horizontal")).lower()
        invert = str(el.props.get("invertprogress", "")).lower() == "yes"
        empty = self._texture_layer(el, self.resolve(el.props.get("noprogresstexture")), el.w, el.h)
        if empty is not None:
            arr = to_np(empty)
            arr[..., 3] *= alpha
            self._paste(img, from_np(arr), el.x, el.y, clip, mask)
        texture = self.resolve(el.props.get("progresstexture"))
        if direction == "vertical":
            filled_h = el.h * fraction
            if filled_h <= 0:
                return
            full = self._texture_layer(el, texture, el.w, el.h)
            if full is None:
                return
            full_h = full.height
            segment_h = max(1, min(full_h, self.px(filled_h)))
            if invert:
                layer = full.crop((0, 0, full.width, segment_h))
                y = el.y
            else:
                layer = full.crop((0, full_h - segment_h, full.width, full_h))
                y = el.y + el.h - filled_h
            if layer is not None and alpha < 1:
                arr = to_np(layer)
                arr[..., 3] *= alpha
                layer = from_np(arr)
            self._paste(img, layer, el.x, y, clip, mask)
        else:
            filled_w = el.w * fraction
            if filled_w <= 0:
                return
            full = self._texture_layer(el, texture, el.w, el.h)
            if full is None:
                return
            full_w = full.width
            segment_w = max(1, min(full_w, self.px(filled_w)))
            if invert:
                layer = full.crop((full_w - segment_w, 0, full_w, full.height))
                x = el.x + el.w - filled_w
            else:
                layer = full.crop((0, 0, segment_w, full.height))
                x = el.x
            if layer is not None and alpha < 1:
                arr = to_np(layer)
                arr[..., 3] *= alpha
                layer = from_np(arr)
            self._paste(img, layer, x, el.y, clip, mask)

    def _barchart(self, el, img, alpha, clip, mask=None):
        if el.w <= 0 or el.h <= 0:
            return
        slices = []
        for child in self.vis_children(el):
            if child.kind not in ("barslice", "barslice_no_highlight"):
                continue
            pushed = self.push(child)
            value = max(0.0, self._resolved_num(child.props.get("value"), 0.0))
            color = child.props.get("color")
            color = self.resolve(color) if isinstance(color, str) else color
            color = parse_color(color) if isinstance(color, list) else [1, 1, 1, 1]
            texture = self.resolve(child.props.get("texture"))
            slices.append((child, value, color, texture))
            self.pop(pushed)
        total = sum(item[1] for item in slices)
        if total <= 0:
            return
        vertical = str(el.props.get("direction", "horizontal")).lower() == "vertical"
        reverse = str(el.props.get("righttoleft", "")).lower() == "yes"
        offset = 0.0
        for child, value, color, texture in slices:
            span = (el.h if vertical else el.w) * value / total
            if span <= 0:
                continue
            if vertical:
                y = el.y + (el.h - offset - span if not reverse else offset)
                layer = self._texture_layer(child, texture, el.w, span, color)
                if layer is not None and alpha < 1:
                    arr = to_np(layer)
                    arr[..., 3] *= alpha
                    layer = from_np(arr)
                self._paste(img, layer, el.x, y, clip, mask)
            else:
                x = el.x + (el.w - offset - span if reverse else offset)
                layer = self._texture_layer(child, texture, span, el.h, color)
                if layer is not None and alpha < 1:
                    arr = to_np(layer)
                    arr[..., 3] *= alpha
                    layer = from_np(arr)
                self._paste(img, layer, x, el.y, clip, mask)
            offset += span

    def _slider_part(self, spec, w, h, x, y, img, alpha, clip, mask=None):
        if not isinstance(spec, dict) or w <= 0 or h <= 0:
            return
        for bg in spec.get("backgrounds", []):
            bgl = lower_spec(bg)
            if bgl.get("visible") is not None and not self.ev.truthy(bgl["visible"]):
                continue
            margin = bgl.get("margin")
            l = r = num(margin[0]) if isinstance(margin, list) and margin else 0.0
            t = b = num(margin[1] if len(margin) > 1 else margin[0]) if isinstance(margin, list) and margin else 0.0
            l = num(bgl.get("margin_left"), l)
            r = num(bgl.get("margin_right"), r)
            t = num(bgl.get("margin_top"), t)
            b = num(bgl.get("margin_bottom"), b)
            layer = compose(bg, self.px(w + l + r), self.px(h + t + b), self.scale, self._res_tex)
            if layer is not None and alpha * num(spec.get("alpha"), 1.0) < 1:
                arr = to_np(layer)
                arr[..., 3] *= alpha * num(spec.get("alpha"), 1.0)
                layer = from_np(arr)
            self._paste(img, layer, x - l, y - t, clip, mask)
        layer = compose(spec, self.px(w), self.px(h), self.scale, self._res_tex)
        if layer is None:
            return
        if alpha < 1:
            arr = to_np(layer)
            arr[..., 3] *= alpha
            layer = from_np(arr)
        self._paste(img, layer, x, y, clip, mask)

    def _ranged_slider(self, el, img, alpha, clip, mask=None):
        """Render the engine-owned ranged_slider parts from their GUI specs."""
        if el.w <= 0 or el.h <= 0:
            return
        track = el.props.get("track")
        track_range = el.props.get("track_range")
        track_highlight = el.props.get("track_highlight")
        slider = el.props.get("slider") or el.props.get("slider_low")
        slider_low = el.props.get("slider_low")
        dec = el.props.get("dec_button")
        inc = el.props.get("inc_button")
        dec_low = el.props.get("dec_button_low")
        inc_low = el.props.get("inc_button_low")

        # The vanilla layout reserves a 20px gap on either side of each 15px
        # step button, leaving the centre segment for the track.
        button_w = 15.0
        track_x = 36.0
        track_w = max(1.0, el.w - 2 * track_x)
        track_y = el.y + (el.h - 15.0) / 2
        self._slider_part(track, track_w, 15.0, el.x + track_x, track_y, img, alpha, clip, mask)
        self._slider_part(track_range, track_w, 15.0, el.x + track_x, track_y, img, alpha, clip, mask)

        lo = self._resolved_num(el.props.get("min"), 0.0)
        hi = self._resolved_num(el.props.get("max"), 1.0)
        span = max(hi - lo, 1e-6)
        val = min(hi, max(lo, self._resolved_num(el.props.get("value"), lo)))
        val_low = min(hi, max(lo, self._resolved_num(el.props.get("value_low"), val)))
        px = lambda v: el.x + track_x + track_w * ((v - lo) / span)
        x_low, x_high = px(val_low), px(val)
        left, right = min(x_low, x_high), max(x_low, x_high)
        self._slider_part(track_highlight, max(1.0, right - left), 15.0, left, track_y, img, alpha, clip, mask)

        # Step buttons sit just outside the track.  A two-handle slider uses
        # the low variants when present; these share the same visuals in the
        # UI Library reference.
        def step_button(spec, x, icon_name):
            self._slider_part(spec, button_w, button_w, x, el.y, img, alpha, clip, mask)
            if not isinstance(spec, dict):
                return
            icon = {
                "texture": f"gfx/interface/buttons/flats/{icon_name}.dds",
                "texture_density": 2,
                "modifies": [
                    {"texture": "gfx/interface/colors/gold.dds"},
                    {"texture": "gfx/interface/component_overlay/overlay_window.dds",
                     "texture_density": 2, "blend_mode": "overlay", "alpha": 0.9},
                ],
            }
            self._slider_part(icon, 11, 11, x + 2, el.y + 2, img, alpha, clip, mask)

        step_button(dec_low or dec, el.x, "minus")
        step_button(inc_low or inc, el.x + button_w, "add")
        step_button(dec, el.x + el.w - 2 * button_w, "minus")
        step_button(inc, el.x + el.w - button_w, "add")

        hs = 14.0
        self._slider_part(slider_low or slider, hs, hs, x_low - hs / 2, el.y + (el.h - hs) / 2, img, alpha, clip, mask)
        if slider is not None and abs(x_high - x_low) > 0.5:
            self._slider_part(slider, hs, hs, x_high - hs / 2, el.y + (el.h - hs) / 2, img, alpha, clip, mask)

    def _scrollbar(self, el, img, content_h, clip, mask=None):
        """ScrollbarVertical (loading_screen/gui/custom_loading_screen.gui:296), hard-coded track/slider specs."""
        if content_h <= el.h + 0.5:
            return
        track = {"texture": "gfx/interface/colors/black.dds", "spritetype": "Corneredtiled", "spriteborder": ["0", "10"],
                 "alpha": "0.3", "modifies": [{"texture": "gfx/interface/component_masks/mask_fade_horizontal_middle_thick_vertical.dds",
                                                 "blend_mode": "alphamultiply", "spriteType": "Corneredstretched", "spriteborder": ["0", "12"]}]}
        x = el.x + el.w - 12
        layer = compose(track, self.px(12), self.px(el.h), self.scale, self._res_tex)
        self._paste(img, layer, x, el.y, clip, mask)
        sh = max(30, el.h * el.h / content_h)
        slider = {"texture": "gfx/interface/scrollbars/scrollbar_slider.dds", "texture_density": "2", "spritetype": "Corneredtiled",
                  "spriteborder": ["8", "8"], "framesize": ["8", "20"], "upframe": "1",
                  "modifies": [{"texture": "gfx/interface/component_overlay/overlay_stone.dds", "blend_mode": "overlay"}]}
        layer = compose(slider, self.px(8), self.px(sh), self.scale, self._res_tex)
        self._paste(img, layer, x + 2, el.y, clip, mask)

    def _intersect(self, a, b):
        x0, y0 = max(a[0], b[0]), max(a[1], b[1])
        x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
        return (x0, y0, max(0, x1 - x0), max(0, y1 - y0))

    def _glow(self, img, layer, el, clip, a, mask=None):
        g = el.glows[0]
        rad = num(g.get("glow_radius"), 3)
        col = parse_color(g.get("color")) or [0, 0, 0, 1]
        ga = num(g.get("alpha"), 1.0) * a
        pad = int(rad * self.scale * 2)
        alpha = layer.split()[3]
        big = Image.new("L", (layer.width + 2 * pad, layer.height + 2 * pad), 0)
        big.paste(alpha, (pad, pad))
        big = big.filter(ImageFilter.GaussianBlur(rad * self.scale * 0.6))
        arr = np.asarray(big, dtype=np.float32) / 255.0
        out = np.zeros((big.height, big.width, 4), np.float32)
        out[..., :3] = col[:3]
        out[..., 3] = np.clip(arr * 1.5, 0, 1) * ga * col[3]
        self._paste(img, from_np(out), el.x - pad / self.scale, el.y - pad / self.scale, clip, mask)

    def _text(self, el, img, a, clip, mask=None):
        l, t, r, b = self.margins(el)
        maxw = None
        if el.props.get("multiline") == "yes":
            maxw = max(1, el.w - l - r)
        rt = self.richtext(el, maxw)
        align = str(el.props.get("align", "left")).lower()
        bw, bh = el.w - l - r, el.h - t - b
        # fontsize_min: fixed-size single-line text shrinks until it fits (confirmed in game: long culture names)
        if maxw is None and el.props.get("autoresize") != "yes" and rt.width > bw + 0.5:
            size = num(el.props.get("fontsize"), 15)
            fmin = num(el.props.get("fontsize_min"), 8)
            while rt.width > bw + 0.5 and size > fmin:
                size -= 1
                rt = self.richtext(el, maxw, size)
        # per-line horizontal alignment
        line_w = {}
        for (x, line, kind, payload, st, w) in rt.items:
            line_w[line] = max(line_w.get(line, 0), x + w)
        offs = []
        for li in range(rt.nlines):
            lw = line_w.get(li, 0)
            if "right" in align:
                offs.append(bw - lw)
            elif "hcenter" in align or align.split("|")[0] == "center":
                offs.append((bw - lw) / 2)
            else:
                offs.append(0)
        if "top" in align:
            oy = 0
        elif "bottom" in align:
            oy = bh - rt.height
        else:
            oy = (bh - rt.height) / 2
        layer = Image.new("RGBA", (max(1, self.px(el.w + 40)), max(1, self.px(el.h + 20))), (0, 0, 0, 0))
        rt.draw(layer, l + 20, t + oy + 10, self.scale, a, offs)
        # elide/clip horizontally to the box (+ small overflow allowance for glyph overhang)
        self._paste(img, layer, el.x - 20, el.y - 10, clip if clip else None, mask)

    def _pie(self, el, img, a, clip, mask=None):
        """Pie slices are drawn through each slice's texture (e.g. piechart_alpha.dds is a ring), tinted by its color."""
        slices = []
        for c in self.vis_children(el):
            if c.kind != "pieslice":
                continue
            pu = self.push(c)
            v = self.ev.eval_str(str(c.props.get("value", "0")))
            col = c.props.get("color")
            col = parse_color(col) if isinstance(col, list) else self.resolve(col)
            col = list(col) + [1.0] * (4 - len(col)) if isinstance(col, (list, tuple)) else [1, 1, 1, 1]
            tex = self._res_tex(c.props.get("texture"))
            salpha = num(c.props.get("alpha"), 1.0)
            self.pop(pu)
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = 0.0
            slices.append((max(0.0, v), col, tex, salpha))
        tot = sum(sl[0] for sl in slices)
        W, H = self.px(el.w), self.px(el.h)
        if tot <= 0 or W <= 0 or H <= 0:
            return
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        ang = (np.degrees(np.arctan2(xx - W / 2 + 0.5, -(yy - H / 2 + 0.5))) + 360) % 360  # 0 = up, clockwise
        out = np.zeros((H, W, 4), np.float32)
        start = 0.0
        for v, col, tex, salpha in slices:
            sweep = 360 * v / tot
            m = (ang >= start) & (ang < start + sweep)
            start += sweep
            timg = TEXTURES.load(tex) if tex else None
            t = to_np(timg.resize((W, H), Image.BILINEAR)) if timg is not None else np.ones((H, W, 4), np.float32)
            out[m, :3] = t[m, :3] * np.array(col[:3], np.float32)
            out[m, 3] = t[m, 3] * col[3] * salpha * a
        self._paste(img, from_np(out), el.x, el.y, clip, mask)

    def _scene(self, el, img, clip, mask=None):
        W, H = self.px(el.w), self.px(el.h)
        if W <= 0 or H <= 0:
            return
        layer = Image.new("RGBA", (W, H), (58, 66, 60, 255))
        d = ImageDraw.Draw(layer)
        d.text((W / 2, H / 2), "3D scene (ecs_scene_viewer_widget)", fill=(200, 200, 200, 255), anchor="mm")
        self._paste(img, layer, el.x, el.y, clip, mask)
