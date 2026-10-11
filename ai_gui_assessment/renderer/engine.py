"""Layout + render engine for expanded Jomini GUI element trees."""
from __future__ import annotations

import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from data import Unknown, format_number, parse_expr
from gui import Element
from text import RichText, TextStyle
from textures import TEXTURES, compose, lower_spec, sprite, select_frame, to_np, from_np, blend, parse_color

INF = 1e9
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

    # ------------------------------------------------------------ data helpers
    def push(self, el):
        it = getattr(el, "ctx_item", None)
        if it is not None:
            self.ev.item_stack.append(it)
            return True
        return False

    def pop(self, pushed):
        if pushed:
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

    def richtext(self, el, max_width=None):
        key = ("rt", max_width)
        cache = el.__dict__.setdefault("_rt", {})
        if key in cache:
            return cache[key]
        s = self.text_of(el) or ""
        font = el.props.get("font", "StandardGameFont")
        size = num(el.props.get("fontsize"), 15)
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
        if dm and el.item is not None:
            items = self.ev.eval_str(dm)
            if isinstance(items, list):
                for it in items:
                    ch = self.ex.build_lazy(el.item)
                    ch.ctx_item = it
                    ch.props["__dm_item__"] = True
                    el.children.append(ch)

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
        mnh = num(mn[1], -1) if mn else -1
        mxw = num(mx[0], -1) if mx else -1
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
        if kind in BOX:
            kids = self.vis_children(el)
            sp = num(el.props.get("spacing"), 0)
            inner_avail = None if avail_w is None else max(0, avail_w - l - r)
            ms = [self.measure(c, inner_avail if kind == "vbox" else None) for c in kids]
            if kind == "hbox":
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
            hh = max(sh or 0, th) if (autoresize or el.props.get("multiline") == "yes") else (sh if sh is not None else th)
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
            if vertical:
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
            for c in kids:
                if c.props.get("set_parent_size_to_minimum") == "yes" or c.props.get("resizeparent") == "yes":
                    m = self.measure(c, avail_w)
                    hw = max(hw, m["hint"][0])
                    hh = max(hh, m["hint"][1])
            if kind in ("icon", "button") and sw is None and sh is None and not size:
                tex = self.resolve(el.props.get("texture"))
                img = TEXTURES.load(tex) if isinstance(tex, str) else None
                if img is not None:
                    img = select_frame(img, lower_spec(el.props))
                    d = num(el.props.get("texture_density"), 1) or 1
                    hw, hh = img.width / d, img.height / d
            mw, mh = 0, 0
        if sw is not None and not (kind in TEXT and el.props.get("autoresize") == "yes"):
            hw = sw
            mw = sw
        if sh is not None and kind not in BOX:
            hh = max(sh, hh) if kind in TEXT else sh
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
            cx, cy = x + l, y + t
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
        kids = self.vis_children(el)
        if not kids:
            return
        sp = num(el.props.get("spacing"), 0)
        main_total = w if axis == 0 else h
        cross_total = h if axis == 0 else w
        items = []
        for c in kids:
            pu = self.push(c)
            m = self.measure(c, w if axis == 1 else None)
            pol = self.policy(c, axis)
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
            stretch = num(c.props.get("layoutstretchfactor_horizontal" if axis == 0 else "layoutstretchfactor_vertical"), 0)
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
    def render(self, el, img, alpha=1.0, clip=None):
        p = self.push(el)
        try:
            self._render(el, img, alpha, clip)
        finally:
            self.pop(p)

    def px(self, v):
        return int(round(v * self.scale))

    def _paste(self, img, layer, x, y, clip):
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
        if X >= img.width or Y >= img.height or X + layer.width <= 0 or Y + layer.height <= 0:
            return
        if X < 0 or Y < 0:
            layer = layer.crop((max(0, -X), max(0, -Y), layer.width, layer.height))
            X, Y = max(0, X), max(0, Y)
        img.alpha_composite(layer, (X, Y))

    def _res_tex(self, v):
        r = self.resolve(v)
        return r if isinstance(r, str) else None

    def _render(self, el, img, alpha, clip):
        a = alpha * num(el.props.get("alpha"), 1.0)
        if a <= 0.001 or el.w < 0 or el.h < 0:
            return
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
            if layer is not None and a < 1:
                arr = to_np(layer)
                arr[..., 3] *= a
                layer = from_np(arr)
            self._paste(img, layer, el.x - l, el.y - t, clip)
        # own content
        if el.kind in ("icon", "button") and el.props.get("texture") and el.w > 0 and el.h > 0:
            spec = dict(el.props)
            spec["modifies"] = el.modifies
            if el.kind == "button":
                down = el.props.get("down")
                spec["frame"] = spec.get("downframe", 1) if (down and self.ev.truthy(down, False)) else spec.get("upframe", 1)
            layer = compose(spec, self.px(el.w), self.px(el.h), self.scale, self._res_tex)
            if layer is not None:
                if el.glows:
                    self._glow(img, layer, el, clip, a)
                if a < 1:
                    arr = to_np(layer)
                    arr[..., 3] *= a
                    layer = from_np(arr)
                self._paste(img, layer, el.x, el.y, clip)
        if el.kind == "piechart":
            self._pie(el, img, a, clip)
        if el.kind == "ecs_scene_viewer_widget":
            self._scene(el, img, clip)
        if el.kind in TEXT:
            self._text(el, img, a, clip)
        kids = self.vis_children(el)
        cclip = clip
        if getattr(el, "clip", None):
            cclip = el.clip if clip is None else self._intersect(clip, el.clip)
        for c in kids:
            if c.kind == "pieslice":
                continue
            self.render(c, img, a, cclip)
        if el.kind == "scrollarea" and el.props.get("scrollbar_vertical") and kids:
            self._scrollbar(el, img, max(k.h for k in kids), clip)

    def _scrollbar(self, el, img, content_h, clip):
        """ScrollbarVertical (loading_screen/gui/custom_loading_screen.gui:296), hard-coded track/slider specs."""
        if content_h <= el.h + 0.5:
            return
        track = {"texture": "gfx/interface/colors/black.dds", "spritetype": "Corneredtiled", "spriteborder": ["0", "10"],
                 "alpha": "0.3", "modifies": [{"texture": "gfx/interface/component_masks/mask_fade_horizontal_middle_thick_vertical.dds",
                                                 "blend_mode": "alphamultiply", "spriteType": "Corneredstretched", "spriteborder": ["0", "12"]}]}
        x = el.x + el.w - 12
        layer = compose(track, self.px(12), self.px(el.h), self.scale, self._res_tex)
        self._paste(img, layer, x, el.y, clip)
        sh = max(30, el.h * el.h / content_h)
        slider = {"texture": "gfx/interface/scrollbars/scrollbar_slider.dds", "texture_density": "2", "spritetype": "Corneredtiled",
                  "spriteborder": ["8", "8"], "framesize": ["8", "20"], "upframe": "1",
                  "modifies": [{"texture": "gfx/interface/component_overlay/overlay_stone.dds", "blend_mode": "overlay"}]}
        layer = compose(slider, self.px(8), self.px(sh), self.scale, self._res_tex)
        self._paste(img, layer, x + 2, el.y, clip)

    def _intersect(self, a, b):
        x0, y0 = max(a[0], b[0]), max(a[1], b[1])
        x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
        return (x0, y0, max(0, x1 - x0), max(0, y1 - y0))

    def _glow(self, img, layer, el, clip, a):
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
        self._paste(img, from_np(out), el.x - pad / self.scale, el.y - pad / self.scale, clip)

    def _text(self, el, img, a, clip):
        l, t, r, b = self.margins(el)
        maxw = None
        if el.props.get("multiline") == "yes":
            maxw = max(1, el.w - l - r)
        rt = self.richtext(el, maxw)
        align = str(el.props.get("align", "left")).lower()
        bw, bh = el.w - l - r, el.h - t - b
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
        self._paste(img, layer, el.x - 20, el.y - 10, clip if clip else None)

    def _pie(self, el, img, a, clip):
        slices = []
        for c in self.vis_children(el):
            for s in ([c] if c.kind == "pieslice" else []):
                pu = self.push(s)
                v = self.ev.eval_str(str(s.props.get("value", "0")))
                col = None
                tex = self._res_tex(s.props.get("texture"))
                if isinstance(s.props.get("color"), list):
                    col = parse_color(s.props.get("color"))
                    if isinstance(s.props.get("color"), str):
                        col = None
                cv = self.resolve(s.props.get("color")) if isinstance(s.props.get("color"), str) else None
                if isinstance(cv, tuple):
                    col = list(cv)
                if tex:
                    timg = TEXTURES.load(tex)
                    if timg is not None:
                        arr = np.asarray(timg.convert("RGBA"), dtype=np.float32)
                        msk = arr[..., 3] > 128
                        if msk.any():
                            tc = arr[msk][:, :3].mean(0) / 255
                            col = [tc[0] * (col[0] if col else 1), tc[1] * (col[1] if col else 1), tc[2] * (col[2] if col else 1), 1]
                self.pop(pu)
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    v = 0
                slices.append((max(0.0, v), col or [0.6, 0.6, 0.6, 1]))
        tot = sum(s[0] for s in slices)
        if tot <= 0:
            return
        W, H = self.px(el.w), self.px(el.h)
        layer = Image.new("RGBA", (max(W, 1), max(H, 1)))
        d = ImageDraw.Draw(layer)
        ang = -90.0
        for v, col in slices:
            sweep = 360 * v / tot
            d.pieslice((0, 0, W - 1, H - 1), ang, ang + sweep, fill=tuple(int(c * 255) for c in col[:3]) + (int(230 * a),))
            ang += sweep
        self._paste(img, layer, el.x, el.y, clip)

    def _scene(self, el, img, clip):
        W, H = self.px(el.w), self.px(el.h)
        if W <= 0 or H <= 0:
            return
        layer = Image.new("RGBA", (W, H), (58, 66, 60, 255))
        d = ImageDraw.Draw(layer)
        d.text((W / 2, H / 2), "3D scene (ecs_scene_viewer_widget)", fill=(200, 200, 200, 255), anchor="mm")
        self._paste(img, layer, el.x, el.y, clip)
