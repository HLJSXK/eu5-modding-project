"""Side-by-side / zoomed comparison of a screenshot region and a render.

usage: compare.py SHOT RENDER sx sy w h [rx ry] [zoom] OUT
  (sx,sy) = top-left of the region in the screenshot, (rx,ry) = same region in the render (default 0,0)
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw


def main():
    a = sys.argv[1:]
    shot, render = Image.open(a[0]).convert("RGB"), Image.open(a[1]).convert("RGB")
    sx, sy, w, h = map(int, a[2:6])
    rx, ry = (int(a[6]), int(a[7])) if len(a) > 9 else (0, 0)
    zoom = float(a[-2]) if len(a) > 8 else 1.0
    out = a[-1]
    A = shot.crop((sx, sy, sx + w, sy + h))
    B = render.crop((rx, ry, rx + w, ry + h))
    if zoom != 1:
        A = A.resize((int(w * zoom), int(h * zoom)), Image.NEAREST)
        B = B.resize((int(w * zoom), int(h * zoom)), Image.NEAREST)
    W, H = A.size
    c = Image.new("RGB", (W * 2 + 10, H + 20), (255, 255, 255))
    c.paste(A, (0, 20))
    c.paste(B, (W + 10, 20))
    d = ImageDraw.Draw(c)
    d.text((4, 4), "game", fill=(0, 0, 0))
    d.text((W + 14, 4), "render", fill=(0, 0, 0))
    # grid every 50 source px
    for gy in range(0, h, 50):
        for X in (0, W + 10):
            d.line((X, 20 + gy * zoom, X + 6, 20 + gy * zoom), fill=(255, 0, 255))
    c.save(out)


if __name__ == "__main__":
    main()
