#!/usr/bin/env python3
"""
Pure-Python helpers that turn a flat-background generated picture into a
vanilla-style EU5 icon: transparent background, subject trimmed and fitted
to the canvas with a small margin, area-averaged downscaling.

Used by scripts/generate_sol_icon.py and scripts/compose_sol_mapmode_icons.py.
The image relay cannot return transparent PNGs, so icons are generated on a
solid key colour (magenta by default) and keyed out here.
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dds_image_lib import RgbaImage  # noqa: E402


def estimate_key_color(image: RgbaImage, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Median colour of the outer 2px border; falls back if the border is not key-like."""
    w, h, px = image.width, image.height, image.rgba
    reds: list[int] = []
    greens: list[int] = []
    blues: list[int] = []
    for y in range(h):
        for x in range(w):
            if 2 <= x < w - 2 and 2 <= y < h - 2:
                continue
            pos = (y * w + x) * 4
            reds.append(px[pos])
            greens.append(px[pos + 1])
            blues.append(px[pos + 2])
    reds.sort()
    greens.sort()
    blues.sort()
    mid = len(reds) // 2
    found = (reds[mid], greens[mid], blues[mid])
    if sum(abs(a - b) for a, b in zip(found, fallback)) > 150:
        return fallback
    return found


def chroma_key(
    image: RgbaImage,
    key: tuple[int, int, int],
    opaque_keyness: float = 24.0,
    clear_margin: float = 30.0,
) -> RgbaImage:
    """
    Remove a flat, saturated key-colour background (e.g. magenta).

    A pixel is modelled as P = a*C + (1-a)*K. Alpha is estimated from the
    pixel's "key-ness" s(P) = min(key-high channels) - max(key-low channels):
    s(K) is large, object colours are ~0 or negative, and mixtures fall
    linearly in between. This handles soft dark shadows correctly, which a
    plain colour-distance test turns into a magenta halo.

    s >= s(K) - clear_margin -> transparent; s <= opaque_keyness -> opaque.
    Semi-transparent pixels are un-mixed so edges keep their true colour.
    """
    kr, kg, kb = key
    hi = [i for i, v in enumerate(key) if v >= 128]
    lo = [i for i, v in enumerate(key) if v < 128]
    if not hi or not lo:
        raise ValueError("chroma_key needs a saturated key colour (e.g. magenta 255,0,255)")

    def keyness(rgb: tuple[int, int, int]) -> int:
        return min(rgb[i] for i in hi) - max(rgb[i] for i in lo)

    s_key = keyness(key)
    s_clear = s_key - clear_margin
    s_opaque = opaque_keyness
    span = max(1.0, s_clear - s_opaque)
    src = image.rgba
    out = bytearray(len(src))
    for pos in range(0, len(src), 4):
        r, g, b, a0 = src[pos], src[pos + 1], src[pos + 2], src[pos + 3]
        s = keyness((r, g, b))
        if s >= s_clear:
            continue  # stays fully transparent (zeros)
        if s <= s_opaque:
            out[pos:pos + 4] = bytes((r, g, b, a0))
            continue
        alpha = (s_clear - s) / span
        inv = 1.0 - alpha
        cr = (r - inv * kr) / alpha
        cg = (g - inv * kg) / alpha
        cb = (b - inv * kb) / alpha
        out[pos] = max(0, min(255, int(round(cr))))
        out[pos + 1] = max(0, min(255, int(round(cg))))
        out[pos + 2] = max(0, min(255, int(round(cb))))
        out[pos + 3] = int(round(alpha * a0))
    return RgbaImage(image.width, image.height, bytes(out))


def suppress_key_spill(image: RgbaImage, key: tuple[int, int, int]) -> RgbaImage:
    """Clamp residual magenta tint: for magenta keys, limit min(R,B) to G + 40 on edge pixels."""
    if not (key[0] > 180 and key[2] > 180 and key[1] < 80):
        return image
    px = bytearray(image.rgba)
    for pos in range(0, len(px), 4):
        a = px[pos + 3]
        if a == 0 or a == 255:
            continue
        r, g, b = px[pos], px[pos + 1], px[pos + 2]
        limit = g + 40
        if r > limit and b > limit:
            px[pos] = limit if limit < 255 else 255
            px[pos + 2] = limit if limit < 255 else 255
    return RgbaImage(image.width, image.height, bytes(px))


def alpha_bbox(image: RgbaImage, threshold: int = 8) -> tuple[int, int, int, int] | None:
    w, h, px = image.width, image.height, image.rgba
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row = y * w * 4
        for x in range(w):
            if px[row + x * 4 + 3] > threshold:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0:
        return None
    return min_x, min_y, max_x + 1, max_y + 1


def area_resample(
    image: RgbaImage,
    rect: tuple[float, float, float, float],
    width: int,
    height: int,
) -> RgbaImage:
    """Area-average (box) resample of rect=(left, top, w, h) into width x height, alpha-premultiplied.
    Pixels of rect outside the source are treated as transparent."""
    left, top, rw, rh = rect
    sw, sh, px = image.width, image.height, image.rgba
    sx = rw / width
    sy = rh / height
    out = bytearray(width * height * 4)
    for oy in range(height):
        y0 = top + oy * sy
        y1 = y0 + sy
        iy0 = int(y0 // 1)
        iy1 = int(-(-y1 // 1))
        for ox in range(width):
            x0 = left + ox * sx
            x1 = x0 + sx
            ix0 = int(x0 // 1)
            ix1 = int(-(-x1 // 1))
            acc_r = acc_g = acc_b = acc_a = 0.0
            for iy in range(iy0, iy1):
                wy = min(y1, iy + 1) - max(y0, iy)
                if wy <= 0 or iy < 0 or iy >= sh:
                    continue
                row = iy * sw * 4
                for ix in range(ix0, ix1):
                    wx = min(x1, ix + 1) - max(x0, ix)
                    if wx <= 0 or ix < 0 or ix >= sw:
                        continue
                    pos = row + ix * 4
                    a = px[pos + 3]
                    if a == 0:
                        continue
                    wa = wx * wy * a
                    acc_r += px[pos] * wa
                    acc_g += px[pos + 1] * wa
                    acc_b += px[pos + 2] * wa
                    acc_a += wa
            pos = (oy * width + ox) * 4
            area = sx * sy
            if acc_a > 0:
                out[pos] = max(0, min(255, int(round(acc_r / acc_a))))
                out[pos + 1] = max(0, min(255, int(round(acc_g / acc_a))))
                out[pos + 2] = max(0, min(255, int(round(acc_b / acc_a))))
                out[pos + 3] = max(0, min(255, int(round(acc_a / area))))
    return RgbaImage(width, height, bytes(out))


def fit_to_canvas(image: RgbaImage, width: int, height: int, margin_px: int) -> RgbaImage:
    """Trim to the visible subject, centre it in a square, keep margin_px around it at target size."""
    bbox = alpha_bbox(image)
    if bbox is None:
        raise ValueError("Keyed image is fully transparent; check the key colour")
    x0, y0, x1, y1 = bbox
    side = max(x1 - x0, y1 - y0)
    inner = max(1, min(width, height) - 2 * margin_px)
    full = side * min(width, height) / inner
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    rect = (cx - full / 2.0, cy - full / 2.0, full, full)
    return area_resample(image, rect, width, height)


def flatten_onto(image: RgbaImage, color: tuple[int, int, int]) -> RgbaImage:
    """Composite onto a solid colour (used to put style references on the key background)."""
    px = image.rgba
    out = bytearray(len(px))
    for pos in range(0, len(px), 4):
        a = px[pos + 3] / 255.0
        for c in range(3):
            out[pos + c] = int(round(px[pos + c] * a + color[c] * (1.0 - a)))
        out[pos + 3] = 255
    return RgbaImage(image.width, image.height, bytes(out))


def composite_over(base: RgbaImage, overlay: RgbaImage, offset: tuple[int, int] = (0, 0)) -> RgbaImage:
    """Standard alpha 'over' compositing of overlay onto base at offset."""
    bw, bh = base.width, base.height
    out = bytearray(base.rgba)
    ox, oy = offset
    src = overlay.rgba
    for y in range(overlay.height):
        ty = y + oy
        if ty < 0 or ty >= bh:
            continue
        for x in range(overlay.width):
            tx = x + ox
            if tx < 0 or tx >= bw:
                continue
            sp = (y * overlay.width + x) * 4
            sa = src[sp + 3] / 255.0
            if sa <= 0:
                continue
            dp = (ty * bw + tx) * 4
            da = out[dp + 3] / 255.0
            oa = sa + da * (1.0 - sa)
            for c in range(3):
                val = (src[sp + c] * sa + out[dp + c] * da * (1.0 - sa)) / oa
                out[dp + c] = max(0, min(255, int(round(val))))
            out[dp + 3] = max(0, min(255, int(round(oa * 255))))
    return RgbaImage(bw, bh, bytes(out))


def key_and_fit(
    image: RgbaImage,
    key: tuple[int, int, int],
    width: int,
    height: int,
    margin_px: int,
    opaque_keyness: float = 24.0,
    clear_margin: float = 30.0,
) -> RgbaImage:
    actual_key = estimate_key_color(image, key)
    keyed = chroma_key(image, actual_key, opaque_keyness, clear_margin)
    keyed = suppress_key_spill(keyed, actual_key)
    return fit_to_canvas(keyed, width, height, margin_px)
