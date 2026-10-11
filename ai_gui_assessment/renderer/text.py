"""Rich text: #format#! runs, @icon! texticons, fonts, measurement and drawing."""
from __future__ import annotations

import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gui import GAME

FONT_DIR = GAME / "loading_screen" / "fonts"
# (latin file, CJK file) per fontfiles entry, simp_chinese groups (see loading_screen_fonts.font)
FONTFILES = {
    "NotoSerif-Regular": ("NotoSerif/NotoSerif_SemiCondensed-Regular.ttf", "NotoSansSC/NotoSansSC-Regular.ttf"),
    "NotoSerif-Medium": ("NotoSerif/NotoSerif_SemiCondensed-Medium.ttf", "NotoSansSC/NotoSansSC-Medium.ttf"),
    "NotoSerif-Italic": ("NotoSerif/NotoSerif_SemiCondensed-Italic.ttf", "NotoSansSC/NotoSansSC-Regular.ttf"),
    "NotoSerif-MediumItalic": ("NotoSerif/NotoSerif_SemiCondensed-MediumItalic.ttf", "NotoSansSC/NotoSansSC-Medium.ttf"),
    "NotoSerif-SemiBold": ("NotoSerif/NotoSerif_SemiCondensed-SemiBold.ttf", "NotoSansSC/NotoSansSC-SemiBold.ttf"),
    "NotoSerif-SemiBoldItalic": ("NotoSerif/NotoSerif_SemiCondensed-SemiBoldItalic.ttf", "NotoSansSC/NotoSansSC-SemiBold.ttf"),
    "NotoSerif-SemiBold-Header": ("NotoSerif/NotoSerif_SemiCondensed-SemiBold.ttf", "NotoSerifSC/NotoSerifSC-SemiBold.otf"),
    "NotoSerif-SemiBoldItalic-Header": ("NotoSerif/NotoSerif_SemiCondensed-SemiBoldItalic.ttf", "NotoSerifSC/NotoSerifSC-SemiBold.otf"),
    "NotoSerif-Bold-Header": ("NotoSerif/NotoSerif_SemiCondensed-Bold.ttf", "NotoSerifSC/NotoSerifSC-Bold.otf"),
    "NotoSerif-BoldItalic-Header": ("NotoSerif/NotoSerif_SemiCondensed-BoldItalic.ttf", "NotoSerifSC/NotoSerifSC-Bold.otf"),
    "NotoSans-Regular": ("NotoSans/NotoSans-Regular.ttf", "NotoSansSC/NotoSansSC-Regular.ttf"),
    "NotoSans-Medium": ("NotoSans/NotoSans-Medium.ttf", "NotoSansSC/NotoSansSC-Medium.ttf"),
    "NotoSans-Italic": ("NotoSans/NotoSans-Italic.ttf", "NotoSansSC/NotoSansSC-Regular.ttf"),
    "NotoSans-Light": ("NotoSans/NotoSans-Light.ttf", "NotoSansSC/NotoSansSC-Light.ttf"),
    "NotoSansMono-Medium": ("NotoSansMono/NotoSansMono_SemiCondensed-Medium.ttf", "NotoSansSC/NotoSansSC-Medium.ttf"),
}
FONTS = {
    "StandardGameFont": {"regular": "NotoSerif-Regular", "bold": "NotoSerif-Medium", "italic": "NotoSerif-Italic", "bold|italic": "NotoSerif-MediumItalic"},
    "SimpleFont": {"regular": "NotoSans-Regular", "bold": "NotoSans-Medium", "italic": "NotoSans-Italic", "bold|italic": "NotoSans-Medium", "semibold": "NotoSans-Light"},
    "HeadersFont": {"regular": "NotoSerif-SemiBold-Header", "italic": "NotoSerif-SemiBoldItalic-Header", "bold": "NotoSerif-Bold-Header", "bold|italic": "NotoSerif-BoldItalic-Header"},
    "FlavorFont": {"regular": "NotoSerif-Italic", "bold": "NotoSerif-SemiBoldItalic", "italic": "NotoSerif-Regular", "bold|italic": "NotoSerif-SemiBold"},
    "Debug": {"regular": "NotoSansMono-Medium", "bold": "NotoSansMono-Medium"},
    "ConsoleFont": {"regular": "NotoSansMono-Medium", "bold": "NotoSansMono-Medium"},
}


@lru_cache(maxsize=512)
def font_pair(fontname: str, style: str, px: int):
    fam = FONTS.get(fontname, FONTS["StandardGameFont"])
    ff = fam.get(style) or fam.get("bold" if "bold" in style else "regular") or fam["regular"]
    latin, cjk = FONTFILES.get(ff, FONTFILES["NotoSerif-Regular"])
    return (ImageFont.truetype(str(FONT_DIR / latin), px), ImageFont.truetype(str(FONT_DIR / cjk), px))


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x2E80 or 0x2190 <= o <= 0x21FF or 0x2500 <= o <= 0x257F or o in (0x00D7,) or 0x2010 <= o <= 0x206F


TOKEN = re.compile(r"(#![ ]?|#[A-Za-z_][A-Za-z0-9_]*[ ]?|@[A-Za-z0-9_]+!|\n)")


def parse_runs(s: str):
    """-> list of ('text', str, fmtstack) | ('icon', name, fmtstack) | ('nl',)"""
    out = []
    stack: list[str] = []
    for part in TOKEN.split(s):
        if not part:
            continue
        if part == "\n":
            out.append(("nl",))
        elif part.startswith("#!"):
            if stack:
                stack.pop()
        elif part.startswith("#") and len(part) > 1 and re.match(r"#[A-Za-z_]", part):
            stack.append(part[1:].strip())
        elif part.startswith("@") and part.endswith("!"):
            out.append(("icon", part[1:-1], tuple(stack)))
        else:
            out.append(("text", part, tuple(stack)))
    return out


class TextStyle:
    def __init__(self, formats, base_font="StandardGameFont", size=15, default_format=None):
        self.formats = formats
        self.base_font = base_font
        self.size = size
        self.default_format = default_format

    def resolve(self, stack):
        st = {"color": (0.94, 0.92, 0.85), "font": self.base_font, "size": self.size}
        names = ([self.default_format] if self.default_format else []) + list(stack)
        for n in names:
            st.update(self.formats.resolve(n))
        return st


def style_font(st, scale):
    style = "regular"
    if st.get("bold") and st.get("italic"):
        style = "bold|italic"
    elif st.get("bold"):
        style = "bold"
    elif st.get("italic"):
        style = "italic"
    elif st.get("semibold"):
        style = "semibold"
    return font_pair(st.get("font", "StandardGameFont"), style, max(4, int(round(st.get("size", 15) * scale))))


_NOTDEF = {}


def has_glyph(font, ch):
    key = (font.path, ch)
    if key in _GLYPH:
        return _GLYPH[key]
    if font.path not in _NOTDEF:
        _NOTDEF[font.path] = bytes(font.getmask("￿"))
    m = font.getmask(ch)
    ok = bytes(m) != _NOTDEF[font.path] or ch.isspace()
    _GLYPH[key] = ok
    return ok


_GLYPH = {}
_PRIMARY = ImageFont.truetype(str(FONT_DIR / "NotoSerif/NotoSerif_SemiCondensed-Regular.ttf"), 20)


def split_script(text):
    """split into (is_cjk, chunk): CJK font for CJK ranges and for glyphs missing in the latin font"""
    out = []
    for ch in text:
        c = is_cjk(ch) or not has_glyph(_PRIMARY, ch)
        if out and out[-1][0] == c:
            out[-1][1] += ch
        else:
            out.append([c, ch])
    return out


class RichText:
    """Laid-out rich text in UI units (scale handled at draw time)."""

    def __init__(self, s: str, style: TextStyle, icons, scale=2.0, max_width=None, multiline=False):
        self.style = style
        self.icons = icons
        self.scale = scale
        self.items = []  # (x, line, kind, payload, st, w)
        self.lines_h = []
        runs = parse_runs(s)
        x = 0.0
        line = 0
        self.width = 0.0
        lh = self._line_h(style.resolve(()))
        maxw = max_width if (multiline and max_width) else None

        def newline():
            nonlocal x, line
            self.width = max(self.width, x)
            x = 0.0
            line += 1

        for r in runs:
            if r[0] == "nl":
                if multiline:
                    newline()
                continue
            st = style.resolve(r[2])
            if r[0] == "icon":
                info = icons.get(r[1])
                w = (info.get("size") or [20, 20])[0]
                if maxw and x + w > maxw and x > 0:
                    newline()
                self.items.append((x, line, "icon", info, st, w))
                x += w
                continue
            lat, cjk = style_font(st, scale)
            # word wrapping at spaces and between CJK characters
            tokens = re.findall(r"\s+|[⺀-￿]|[^\s⺀-￿]+", r[1])
            for tok in tokens:
                w = sum((cjk if c else lat).getlength(chunk) for c, chunk in split_script(tok)) / scale
                if maxw and x + w > maxw and x > 0 and not tok.isspace():
                    newline()
                if x == 0 and tok.isspace() and line > 0:
                    continue
                self.items.append((x, line, "text", tok, st, w))
                x += w
        self.width = max(self.width, x)
        self.nlines = line + 1
        self.line_h = lh
        self.height = self.nlines * lh

    def _line_h(self, st):
        sz = st.get("size", 15)
        return round(sz * 1.45)

    def draw(self, img: Image.Image, ox, oy, scale, alpha=1.0, align_x=0.0):
        """ox, oy in UI units of the text box top-left; align_x is extra x offset (UI units) per line handled by caller."""
        d = ImageDraw.Draw(img)
        for (x, line, kind, payload, st, w) in self.items:
            lx = ox + x + (align_x[line] if isinstance(align_x, list) else align_x)
            ly = oy + line * self.line_h
            if kind == "icon":
                from textures import TEXTURES
                tex = TEXTURES.load(payload.get("texture", ""))
                if tex is None:
                    continue
                size = payload.get("size") or [20, 20]
                off = payload.get("offset") or [0, 4]
                iw, ih = int(size[0] * scale), int(size[1] * scale)
                im = tex.resize((max(1, iw), max(1, ih)), Image.LANCZOS)
                iy = ly + (self.line_h - size[1]) / 2 + (off[1] - 4) * 0.5
                img.alpha_composite(im, (int(lx * scale), int(iy * scale)))
                continue
            lat, cjk = style_font(st, scale)
            col = st.get("color", (1, 1, 1))
            rgba = tuple(int(c * 255) for c in col) + (int(255 * alpha),)
            glow = st.get("glow_color")
            cx = lx * scale
            base_y = (ly + self.line_h * 0.5) * scale
            for c, chunk in split_script(payload):
                f = cjk if c else lat
                if glow and glow[3] > 0:
                    off = st.get("glow_offset", (0, 1))
                    fw = int(f.getlength(chunk)) + 12
                    fh = int(f.size * 2) + 8
                    layer = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
                    ImageDraw.Draw(layer).text((6, fh / 2), chunk, font=f, anchor="lm",
                                               fill=tuple(int(g * 255) for g in glow[:3]) + (int(255 * min(1, glow[3] * 1.6) * alpha),))
                    layer = layer.filter(ImageFilter.GaussianBlur(scale * 0.9))
                    gx = int(cx + off[0] * scale * 0.5 - 6)
                    gy = int(base_y + off[1] * scale * 0.5 - fh / 2)
                    if gx >= 0 and gy >= 0:
                        img.alpha_composite(layer, (gx, gy))
                d.text((cx, base_y), chunk, font=f, fill=rgba, anchor="lm")
                cx += f.getlength(chunk)
