"""Draw the inline living-standard unit icon (@sol_living_standard!).

The gold coin icon misreads SOL as money. The unit icon is a small home with
a lit window and chimney smoke, distinct from the SOL emblem (scales) and the
tier medallions (bowls), cropped tight and outlined for 16-20px text.
Writes a 64px DXT5 DDS next to the tier icons plus a PNG preview sheet.

usage: python make_sol_texticon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_tier_icons as tiers  # noqa: E402
from dds_image_lib import RgbaImage, write_dds  # noqa: E402  (path added by make_tier_icons)

SIZE = 64
OUT = tiers.OUT / "sol_living_standard_texticon.dds"
PREVIEW = tiers.PREVIEW.parent / "sol_texticon_preview.png"


def _shape(points=None, rect=None) -> Image.Image:
    m = Image.new("L", (tiers.S, tiers.S), 0)
    d = ImageDraw.Draw(m)
    if points:
        d.polygon(points, fill=255)
    if rect:
        d.rectangle(rect, fill=255)
    return m


def house_glyph() -> Image.Image:
    """A small home with a lit window and chimney smoke: household welfare.

    Deliberately unlike the SOL emblem (scales) and the tier medallions (bowls),
    so the unit icon never reads as a second tier badge.
    """
    img = tiers.layer()
    cx = tiers.C
    eave, ridge, base = 230, 70, 450
    wall_l, wall_r = cx - 150, cx + 150
    # chimney behind the roof, smoke above it
    img.alpha_composite(tiers.fill(_shape(rect=(cx + 70, 80, cx + 120, 200)),
                                   tiers.linear((176, 96, 70), (100, 50, 36), 160)))
    smoke = tiers.layer()
    sd = ImageDraw.Draw(smoke)
    for k, (dx, dy, r) in enumerate(((0, 0, 26), (26, -40, 22), (8, -78, 18))):
        sd.ellipse((cx + 95 + dx - r, 52 + dy - r, cx + 95 + dx + r, 52 + dy + r), fill=(226, 222, 214, 210 - 40 * k))
    img.alpha_composite(smoke)
    # walls: warm plaster
    img.alpha_composite(tiers.fill(_shape(rect=(wall_l, eave - 10, wall_r, base)),
                                   tiers.linear((246, 228, 190), (196, 166, 120), 135)))
    # roof: terracotta, overhanging the walls
    roof = _shape(points=[(cx, ridge), (wall_r + 50, eave + 10), (wall_l - 50, eave + 10)])
    img.alpha_composite(tiers.fill(roof, tiers.linear((214, 96, 60), (126, 44, 28), 150)))
    rd = ImageDraw.Draw(img)
    rd.line([(wall_l - 50, eave + 10), (wall_r + 50, eave + 10)], fill=(90, 32, 20, 255), width=10)
    # door (dark wood) and lit window (glowing)
    img.alpha_composite(tiers.fill(_shape(rect=(cx - 110, 320, cx - 40, base)),
                                   tiers.linear((128, 82, 46), (70, 40, 22), 160)))
    glow = tiers.ellipse_mask((cx + 10, 270, cx + 140, 400)).filter(tiers.ImageFilter.GaussianBlur(14))
    halo = Image.new("RGBA", (tiers.S, tiers.S), (255, 214, 110, 0))
    halo.putalpha(glow.point(lambda v: v * 120 // 255))
    img.alpha_composite(halo)
    win = (cx + 30, 290, cx + 120, 380)
    img.alpha_composite(tiers.fill(_shape(rect=win), tiers.radial((255, 244, 170), (240, 160, 40), cx + 75, 335, 70)))
    wd = ImageDraw.Draw(img)
    wd.rectangle(win, outline=(90, 56, 30, 255), width=9)
    wd.line([(cx + 75, 290), (cx + 75, 380)], fill=(90, 56, 30, 255), width=7)
    wd.line([(cx + 30, 335), (cx + 120, 335)], fill=(90, 56, 30, 255), width=7)
    return tiers.outline(img, 12)


def glyph() -> Image.Image:
    big = house_glyph()
    box = big.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    crop = big.crop(box)
    side = max(crop.size) + 8
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return square.resize((SIZE, SIZE), Image.LANCZOS)


def preview(icon: Image.Image) -> None:
    sheet = Image.new("RGBA", (420, 120), (38, 42, 50, 255))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    x = 10
    for px in (16, 20, 24, 64):
        sheet.alpha_composite(icon.resize((px, px), Image.LANCZOS), (x, 40 - px // 2 + 10))
        x += px + 16
    sheet.alpha_composite(icon.resize((20, 20), Image.LANCZOS), (10, 84))
    d.text((34, 84), "18.0    192.0   9.4", font=font, fill=(240, 230, 200, 255))
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(PREVIEW)


def main() -> None:
    icon = glyph()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_dds(RgbaImage(icon.width, icon.height, icon.tobytes()), OUT, "DXT5", overwrite=True, mipmaps=True)
    preview(icon)
    print(f"[OK] Written: {OUT}")
    print(f"[OK] Preview: {PREVIEW}")


if __name__ == "__main__":
    main()
