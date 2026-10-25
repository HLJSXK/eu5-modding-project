"""Draw the three living-standard tier icons from scratch (design prototype).

One shared medallion so the three read as a scale, not as siblings:
  rim metal   iron -> bronze -> gold
  bowl        empty -> one loaf -> heaped with bread, fruit and a coin, with rays
  gems        1 -> 2 -> 3 lit sockets on the lower rim
Drawn at 512px with Pillow, downsampled to 128px, written as DXT5 DDS with
scripts/dds_image_lib.py (texture_density = 2 -> 64 GUI units).

usage: python make_tier_icons.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
sys.path.insert(0, str(WORKSPACE / "scripts"))
from dds_image_lib import RgbaImage, write_dds  # noqa: E402

OUT = HERE / "gfx" / "interface" / "sol_lshud_proto"
PREVIEW = WORKSPACE / "ai_gui_assessment/images/living_standard_4sections_20261018/tier_icons/custom"
S, C = 512, 256
R_OUT, R_IN = 246, 200

TIERS = {
    "low": {"metal": ((176, 176, 174), (112, 112, 114), (52, 52, 56)), "disc": ((70, 62, 58), (36, 32, 32)),
            "bowl": ((170, 140, 110), (98, 76, 58)), "gems": 1, "gem": (196, 92, 70)},
    "mid": {"metal": ((236, 170, 110), (176, 106, 56), (84, 46, 22)), "disc": ((30, 46, 62), (14, 22, 32)),
            "bowl": ((196, 104, 64), (116, 54, 30)), "gems": 2, "gem": (120, 196, 214)},
    "high": {"metal": ((255, 238, 160), (222, 172, 58), (116, 78, 18)), "disc": ((44, 46, 82), (18, 18, 40)),
             "bowl": ((246, 240, 226), (176, 166, 150)), "gems": 3, "gem": (120, 230, 140)},
}


def layer():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def mask_of(img):
    return img.getchannel("A")


def linear(c0, c1, angle=135):
    """Full-canvas linear gradient from c0 (light side) to c1."""
    g = Image.new("RGBA", (S, S))
    px = g.load()
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    for y in range(S):
        for x in range(S):
            t = ((x - C) * dx + (y - C) * dy) / (S * 0.72) + 0.5
            t = min(1.0, max(0.0, t))
            px[x, y] = tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3)) + (255,)
    return g


def radial(c0, c1, cx=C, cy=C, r=R_IN):
    g = Image.new("RGBA", (S, S))
    px = g.load()
    for y in range(S):
        for x in range(S):
            t = min(1.0, math.hypot(x - cx, y - cy) / r)
            px[x, y] = tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3)) + (255,)
    return g


def fill(shape_mask, paint):
    out = layer()
    out.paste(paint, (0, 0), shape_mask)
    return out


def outline(img, width=10, colour=(10, 8, 6, 230)):
    a = mask_of(img).filter(ImageFilter.MaxFilter(width * 2 + 1)).filter(ImageFilter.GaussianBlur(1.5))
    out = Image.new("RGBA", (S, S), colour[:3] + (0,))
    out.putalpha(a.point(lambda v: v * colour[3] // 255))
    out.alpha_composite(img)
    return out


def ellipse_mask(box):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse(box, fill=255)
    return m


def medallion(t):
    spec = TIERS[t]
    light, mid, dark = spec["metal"]
    img = layer()
    # soft drop shadow
    sh = ellipse_mask((C - R_OUT + 6, C - R_OUT + 12, C + R_OUT + 6, C + R_OUT + 12)).filter(ImageFilter.GaussianBlur(10))
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.putalpha(sh.point(lambda v: v * 150 // 255))
    img.alpha_composite(shadow)
    # rim: bevelled metal ring
    ring = ImageChops.subtract(ellipse_mask((C - R_OUT, C - R_OUT, C + R_OUT, C + R_OUT)),
                               ellipse_mask((C - R_IN, C - R_IN, C + R_IN, C + R_IN)))
    img.alpha_composite(fill(ring, linear(light, dark, 120)))
    bevel = ImageChops.subtract(ellipse_mask((C - R_OUT + 12, C - R_OUT + 12, C + R_OUT - 12, C + R_OUT - 12)),
                                ellipse_mask((C - R_IN - 8, C - R_IN - 8, C + R_IN + 8, C + R_IN + 8)))
    img.alpha_composite(fill(bevel, linear(dark, light, 120)).filter(ImageFilter.GaussianBlur(2)))
    inner_line = ImageChops.subtract(ellipse_mask((C - R_IN - 3, C - R_IN - 3, C + R_IN + 3, C + R_IN + 3)),
                                     ellipse_mask((C - R_IN, C - R_IN, C + R_IN, C + R_IN)))
    img.alpha_composite(fill(inner_line, Image.new("RGBA", (S, S), dark + (255,))))
    # disc
    d0, d1 = spec["disc"]
    img.alpha_composite(fill(ellipse_mask((C - R_IN, C - R_IN, C + R_IN, C + R_IN)), radial(d0, d1, C, C - 40)))
    return img


def rays(alpha=110):
    g = layer()
    d = ImageDraw.Draw(g)
    cx, cy = C, 268
    for k in range(12):
        a0 = math.radians(k * 30 - 90 - 6)
        a1 = math.radians(k * 30 - 90 + 6)
        d.polygon([(cx, cy), (cx + 260 * math.cos(a0), cy + 260 * math.sin(a0)),
                   (cx + 260 * math.cos(a1), cy + 260 * math.sin(a1))], fill=(255, 214, 110, alpha))
    glow = ellipse_mask((C - 150, 120, C + 150, 400)).filter(ImageFilter.GaussianBlur(40))
    halo = Image.new("RGBA", (S, S), (255, 210, 120, 0))
    halo.putalpha(glow.point(lambda v: v * 150 // 255))
    g.alpha_composite(halo)
    clip = ellipse_mask((C - R_IN, C - R_IN, C + R_IN, C + R_IN))
    g.putalpha(ImageChops.multiply(mask_of(g), clip).filter(ImageFilter.GaussianBlur(3)))
    return g


def loaf(box, colour=((236, 182, 104), (150, 92, 40))):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).pieslice(box, 180, 360, fill=255)
    out = fill(m, linear(colour[0], colour[1], 110))
    d = ImageDraw.Draw(out)
    x0, y0, x1, y1 = box
    w = x1 - x0
    for k in (0.32, 0.5, 0.68):
        cx = x0 + w * k
        d.line([(cx - w * 0.05, y0 + (y1 - y0) * 0.30), (cx + w * 0.05, y0 + (y1 - y0) * 0.14)],
               fill=(120, 70, 30, 220), width=max(4, round(w / 34)))
    hl = ellipse_mask((x0 + w * 0.18, y0 + (y1 - y0) * 0.08, x0 + w * 0.5, y0 + (y1 - y0) * 0.28)).filter(ImageFilter.GaussianBlur(8))
    shine = Image.new("RGBA", (S, S), (255, 238, 200, 0))
    shine.putalpha(ImageChops.multiply(hl.point(lambda v: v * 120 // 255), m))
    out.alpha_composite(shine)
    return out


def ball(cx, cy, r, c0, c1):
    m = ellipse_mask((cx - r, cy - r, cx + r, cy + r))
    out = fill(m, radial(c0, c1, cx - r * 0.35, cy - r * 0.35, r * 1.6))
    return out


def coin(cx, cy, r):
    out = ball(cx, cy, r, (255, 240, 160), (176, 120, 30))
    d = ImageDraw.Draw(out)
    d.ellipse((cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62), outline=(140, 92, 20, 255), width=max(3, r // 7))
    return out


def bowl(t):
    spec = TIERS[t]
    b0, b1 = spec["bowl"]
    top, cx, rx, ry = 286, C, 172, 40
    img = layer()
    # contents behind the front lip
    contents = layer()
    if t == "mid":
        contents.alpha_composite(loaf((cx - 128, top - 110, cx + 128, top + 70)))
    elif t == "high":
        contents.alpha_composite(loaf((cx - 128, top - 150, cx + 60, top + 60)))
        contents.alpha_composite(loaf((cx - 30, top - 118, cx + 132, top + 48), ((246, 200, 120), (164, 104, 46))))
        for gx, gy in ((cx + 70, top - 40), (cx + 92, top - 18), (cx + 50, top - 14), (cx + 74, top + 4)):
            contents.alpha_composite(ball(gx, gy, 22, (176, 112, 220), (70, 30, 110)))
        contents.alpha_composite(ball(cx - 96, top - 26, 40, (255, 120, 96), (150, 24, 20)))
        contents.alpha_composite(coin(cx + 6, top - 10, 36))
    # bowl body (lower half ellipse) + foot
    body = Image.new("L", (S, S), 0)
    bd = ImageDraw.Draw(body)
    bd.pieslice((cx - rx, top - 140, cx + rx, top + 140), 0, 180, fill=255)
    bd.polygon([(cx - 60, top + 124), (cx + 60, top + 124), (cx + 78, top + 156), (cx - 78, top + 156)], fill=255)
    body_img = fill(body, linear(b0, b1, 160))
    if t == "high":
        band = Image.new("L", (S, S), 0)
        ImageDraw.Draw(band).rectangle((0, top + 36, S, top + 54), fill=255)
        band = ImageChops.multiply(band, body)
        body_img.alpha_composite(fill(band, linear((255, 226, 120), (170, 112, 24), 160)))
        band2 = Image.new("L", (S, S), 0)
        ImageDraw.Draw(band2).rectangle((0, top + 70, S, top + 80), fill=255)
        body_img.alpha_composite(fill(ImageChops.multiply(band2, body), Image.new("RGBA", (S, S), (60, 86, 168, 255))))
    # inside of the bowl (dark opening) - visible only where contents do not cover
    opening = ellipse_mask((cx - rx, top - ry, cx + rx, top + ry))
    inside = fill(opening, linear(tuple(v // 3 for v in b1), tuple(v // 2 for v in b0), 270))
    if t == "low":
        d = ImageDraw.Draw(inside)
        for gx, gy in ((cx - 30, top + 10), (cx + 18, top + 16), (cx + 2, top + 4)):
            d.ellipse((gx - 7, gy - 4, gx + 7, gy + 4), fill=(170, 140, 90, 255))
    if t == "low":
        cd = ImageDraw.Draw(body_img)
        cd.line([(cx + 40, top + 6), (cx + 22, top + 52), (cx + 48, top + 82), (cx + 30, top + 118)], fill=(40, 28, 20, 255), width=8)
    img.alpha_composite(inside)
    img.alpha_composite(contents)
    img.alpha_composite(body_img)
    # front lip highlight
    lip = Image.new("L", (S, S), 0)
    ImageDraw.Draw(lip).arc((cx - rx, top - ry, cx + rx, top + ry), 0, 180, fill=255, width=10)
    img.alpha_composite(fill(lip, Image.new("RGBA", (S, S), tuple(min(255, v + 40) for v in b0) + (255,))))
    return outline(img, 9)


def gems(t):
    spec = TIERS[t]
    img = layer()
    r_mid = (R_OUT + R_IN) / 2
    for k, ang in enumerate((124, 90, 56)):
        a = math.radians(ang)
        gx, gy = C + r_mid * math.cos(a), C + r_mid * math.sin(a)
        socket = ball(round(gx), round(gy), 30, (30, 26, 24), (8, 6, 6))
        img.alpha_composite(socket)
        if k < spec["gems"]:
            g = spec["gem"]
            img.alpha_composite(ball(round(gx), round(gy), 24, tuple(min(255, v + 90) for v in g), tuple(v // 3 for v in g)))
    return img


def draw(t):
    img = medallion(t)
    if t == "high":
        img.alpha_composite(rays())
    img.alpha_composite(bowl(t))
    img.alpha_composite(gems(t))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    finals = {}
    for t in TIERS:
        big = draw(t)
        small = big.resize((128, 128), Image.LANCZOS)
        finals[t] = small
        small.save(PREVIEW / f"tier_{t}.png")
        write_dds(RgbaImage(128, 128, small.tobytes()), OUT / f"tier_{t}.dds", "DXT5", overwrite=True, mipmaps=True)
    # readability sheet at the sizes the GUI uses (bar 20/28, tooltip 40/58, 128 master)
    sizes = (20, 28, 40, 58, 128)
    sheet = Image.new("RGBA", (sum(sizes) * 3 + 200, 150), (24, 30, 38, 255))
    x = 10
    for t in TIERS:
        for s in sizes:
            sheet.alpha_composite(finals[t].resize((s, s), Image.LANCZOS), (x, 140 - s))
            x += s + 6
        x += 30
    sheet.save(PREVIEW / "tier_sizes.png")
    print("wrote", ", ".join(str(OUT / f"tier_{t}.dds") for t in TIERS))


if __name__ == "__main__":
    main()
