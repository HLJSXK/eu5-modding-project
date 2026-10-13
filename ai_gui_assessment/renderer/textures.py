"""Texture loading and Jomini-style compositing (spriteType, modify_texture blend modes)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from gui import GAME, MOD

SEARCH = [MOD / "main_menu", MOD / "in_game", GAME / "in_game", GAME / "main_menu", GAME / "loading_screen"]
# Prototype assets that do not live in the mod yet (e.g. `run.py proto` designs): extra
# content roots, searched first, separated by os.pathsep.
SEARCH = [Path(p) for p in os.environ.get("RENDER_EXTRA_ROOTS", "").split(os.pathsep) if p] + SEARCH
SEARCH += [p for p in (GAME / "dlc").glob("*/*") if p.is_dir()]


class _Tex:
    def __init__(self):
        self.missing = set()

    @lru_cache(maxsize=4096)
    def load(self, path: str):
        if not path or not isinstance(path, str) or path.startswith("["):
            return None
        # GUI texture paths are sometimes written with a leading slash; it is
        # still relative to the selected game/mod content root.
        rel = path.replace("\\", "/").lstrip("/")
        for root in SEARCH:
            p = root / rel
            if p.exists():
                try:
                    return Image.open(p).convert("RGBA")
                except Exception:
                    break
        # SOL generated icon fallback (DDS written by the project generator)
        self.missing.add(rel)
        return None


TEXTURES = _Tex()


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def lower_spec(spec: dict) -> dict:
    return {k.lower() if isinstance(k, str) else k: v for k, v in spec.items()}


def select_frame(img: Image.Image, spec: dict, frame_default=1) -> Image.Image:
    fg = spec.get("frame_grid")
    fs = spec.get("framesize")
    frame = int(_f(spec.get("frame", spec.get("upframe", frame_default)), frame_default))
    if fg and isinstance(fg, list) and len(fg) >= 2:
        cols, rows = int(_f(fg[0], 1)), int(_f(fg[1], 1))
        fw, fh = img.width // max(cols, 1), img.height // max(rows, 1)
    elif fs and isinstance(fs, list) and len(fs) >= 2:
        # framesize is in GUI units like spriteborder: texture pixels = framesize * texture_density
        # (confirmed in game: checkbox.dds 160x80, density 2, framesize {40 40} -> two 80px frames)
        dens = _f(spec.get("texture_density"), 1.0) or 1.0
        fw, fh = int(round(_f(fs[0]) * dens)), int(round(_f(fs[1]) * dens))
        cols = max(1, img.width // max(fw, 1))
    else:
        return img
    i = max(0, frame - 1)
    cx, cy = (i % cols) * fw, (i // cols) * fh
    return img.crop((cx, cy, cx + fw, cy + fh))


def _tile(src: Image.Image, w: int, h: int) -> Image.Image:
    if w <= 0 or h <= 0:
        return Image.new("RGBA", (max(w, 1), max(h, 1)))
    out = Image.new("RGBA", (w, h))
    for yy in range(0, h, max(src.height, 1)):
        for xx in range(0, w, max(src.width, 1)):
            out.paste(src, (xx, yy))
    return out


def sprite(img: Image.Image, spec: dict, w: int, h: int, scale: float) -> Image.Image:
    """Draw texture into w x h pixels according to spriteType/spriteborder/texture_density."""
    w, h = max(1, int(round(w))), max(1, int(round(h))
    )
    st = str(spec.get("spritetype", "stretched")).strip('"').lower()
    dens = _f(spec.get("texture_density"), 1.0) or 1.0
    k = scale / dens  # texture px -> output px
    if spec.get("mirror"):
        m = str(spec.get("mirror"))
        if "horizontal" in m:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if "vertical" in m:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
    if st in ("corneredstretched", "corneredtiled"):
        sb = spec.get("spriteborder") or [0, 0]
        if not isinstance(sb, list):
            sb = [sb, sb]
        bl = br = int(_f(sb[0]))
        bt = bb = int(_f(sb[1] if len(sb) > 1 else sb[0]))
        bl = int(_f(spec.get("spriteborder_left", bl)))
        br = int(_f(spec.get("spriteborder_right", br)))
        bt = int(_f(spec.get("spriteborder_top", bt)))
        bb = int(_f(spec.get("spriteborder_bottom", bb)))
        tiled = st == "corneredtiled"
        W, H = img.size
        # spriteborder is in GUI (screen) units, not texture pixels: source border = border * texture_density.
        # Confirmed in game: pattern_bevel_vertical_bis (52px, density 2, border 12) shows a 12px strip, empty middle.
        obl, obr, obt, obb = [int(round(v * scale)) for v in (bl, br, bt, bb)]
        bl, br, bt, bb = [int(round(v * dens)) for v in (bl, br, bt, bb)]
        # keep at least a 1px middle slice when the borders cover the whole texture (e.g. paper_card: 400px, border 200)
        bl, br = min(bl, (W - 1) // 2), min(br, (W - 1) // 2)
        bt, bb = min(bt, (H - 1) // 2), min(bb, (H - 1) // 2)
        # avoid borders bigger than target
        if obl + obr > w:
            f = w / max(obl + obr, 1)
            obl, obr = int(obl * f), w - int(obl * f)
        if obt + obb > h:
            f = h / max(obt + obb, 1)
            obt, obb = int(obt * f), h - int(obt * f)
        out = Image.new("RGBA", (w, h))
        xs_src = [0, bl, W - br, W]
        ys_src = [0, bt, H - bb, H]
        xs_dst = [0, obl, w - obr, w]
        ys_dst = [0, obt, h - obb, h]
        for iy in range(3):
            for ix in range(3):
                sx0, sx1, sy0, sy1 = xs_src[ix], xs_src[ix + 1], ys_src[iy], ys_src[iy + 1]
                dx0, dx1, dy0, dy1 = xs_dst[ix], xs_dst[ix + 1], ys_dst[iy], ys_dst[iy + 1]
                if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                    continue
                piece = img.crop((sx0, sy0, sx1, sy1))
                if tiled and (ix == 1 or iy == 1):
                    # tile at texture density
                    pw = max(1, int(round(piece.width * k)))
                    ph = max(1, int(round(piece.height * k)))
                    piece = piece.resize((pw if ix == 1 else dx1 - dx0, ph if iy == 1 else dy1 - dy0), Image.BILINEAR)
                    piece = _tile(piece, dx1 - dx0, dy1 - dy0)
                else:
                    piece = piece.resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR)
                out.paste(piece, (dx0, dy0))
        return out
    if st == "tiled":
        pw = max(1, int(round(img.width * k)))
        ph = max(1, int(round(img.height * k)))
        return _tile(img.resize((pw, ph), Image.BILINEAR), w, h)
    return img.resize((w, h), Image.BILINEAR)


def to_np(img):
    return np.asarray(img, dtype=np.float32) / 255.0


def from_np(a):
    return Image.fromarray(np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGBA")


def blend(base: np.ndarray, mod: np.ndarray, mode: str, alpha: float) -> np.ndarray:
    b, m = base[..., :3], mod[..., :3]
    ma = mod[..., 3:4] * alpha
    mode = (mode or "normal").lower()
    out = base.copy()
    if mode == "alphamultiply":
        out[..., 3:4] = base[..., 3:4] * (1 - alpha + alpha * mod[..., 3:4])
        return out
    if mode == "multiply":
        c = b * m
    elif mode == "overlay":
        c = np.where(b < 0.5, 2 * b * m, 1 - 2 * (1 - b) * (1 - m))
    elif mode == "add":
        c = np.clip(b + m, 0, 1)
    elif mode == "colordodge":
        c = np.clip(b / np.maximum(1 - m, 1e-3), 0, 1)
    elif mode == "lighten":
        c = np.maximum(b, m)
    elif mode == "darken":
        c = np.minimum(b, m)
    else:  # normal
        c = m
    out[..., :3] = b * (1 - ma) + c * ma
    return out


def parse_color(v):
    if isinstance(v, (list, tuple)):
        vals = [_f(x, 1.0) for x in v]
        while len(vals) < 4:
            vals.append(1.0)
        return vals[:4]
    return None


def compose(spec: dict, w_px: int, h_px: int, scale: float, resolve) -> Image.Image | None:
    """Render a background/icon texture spec to an RGBA image of w_px x h_px."""
    spec = lower_spec(spec)
    tex = resolve(spec.get("texture")) if spec.get("texture") is not None else None
    img = TEXTURES.load(tex) if isinstance(tex, str) else None
    if img is None:
        return None
    if isinstance(spec.get("frame"), str) and spec["frame"].startswith("["):
        # data-driven frame, e.g. alert_settings.gui:163 `frame = "[Select_int32(...)]"`
        spec = dict(spec, frame=resolve(spec["frame"]))
    img = select_frame(img, spec)
    out = to_np(sprite(img, spec, w_px, h_px, scale))
    for ms in spec.get("modifies", []):
        ms = lower_spec(ms)
        col = ms.get("color")
        if isinstance(col, str):
            col = resolve(col)
            col = list(col) if isinstance(col, (list, tuple)) else None
        col = parse_color(col) if isinstance(col, list) else None
        mt = resolve(ms.get("texture")) if ms.get("texture") is not None else None
        mimg = TEXTURES.load(mt) if isinstance(mt, str) else None
        if mimg is None:
            if col is None or ms.get("texture"):
                continue
            # colour-only modify_texture: flat colour layer (e.g. bg_building_card_colors' "building_color")
            m = np.ones((out.shape[0], out.shape[1], 4), np.float32)
        else:
            mimg = select_frame(mimg, ms)
            m = to_np(sprite(mimg, ms, out.shape[1], out.shape[0], scale))
        if col:
            m[..., :3] *= np.array(col[:3], dtype=np.float32)
            m[..., 3] *= col[3]
        out = blend(out, m, ms.get("blend_mode", "normal"), _f(resolve(ms.get("alpha")), 1.0))
    # masked_button uses the mask's alpha as a hard shape for the composed button.
    # The mask follows the same frame/sprite sizing rules as the main texture.
    mask = resolve(spec.get("mask")) if spec.get("mask") is not None else None
    if isinstance(mask, str):
        mimg = TEXTURES.load(mask)
        if mimg is not None:
            mimg = select_frame(mimg, spec)
            ma = to_np(sprite(mimg, spec, out.shape[1], out.shape[0], scale))[..., 3:4]
            out[..., 3:4] *= ma
    col = parse_color(spec.get("color"))
    if col:
        out[..., :3] *= np.array(col[:3], dtype=np.float32)
        out[..., 3] *= col[3]
    out[..., 3] *= _f(resolve(spec.get("alpha")), 1.0)
    return from_np(out)
