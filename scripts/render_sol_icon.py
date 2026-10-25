#!/usr/bin/env python3
"""
Render the hand-drawn SOL icon (assets/icons/sol_living_standard.svg) to a
vanilla-style 128x128 transparent PNG.

Steps: rasterise the SVG at 1024px, darken a thin band just inside the
silhouette (vanilla icons have a soft darker edge, not a black outline),
trim to the subject, fit it with a 6px margin and downscale with
premultiplied alpha.

Requires cairosvg and Pillow (`pip install cairosvg pillow`). The rendered
PNG is checked in at assets/icons/sol_living_standard.png, so only rerun
this after editing the SVG; then install with:

  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/render_sol_icon.py
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/compose_sol_mapmode_icons.py --base assets/icons/sol_living_standard.png --overwrite
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import xml.etree.ElementTree as ET  # noqa: E402

import cairosvg  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SVG = REPO_ROOT / "assets" / "icons" / "sol_living_standard.svg"
DEFAULT_PNG = REPO_ROOT / "assets" / "icons" / "sol_living_standard.png"
# Inline text icon (@sol_living_standard!, drawn at 20px): same drawing without class="detail" elements.
TEXTICON_PNG = REPO_ROOT / "assets" / "icons" / "sol_living_standard_texticon.png"
TEXTICON_SIZE = 64
TEXTICON_MARGIN = 1
SVG_NS = "http://www.w3.org/2000/svg"
RENDER = 1024
SIZE = 128
MARGIN = 6
EDGE_DARKEN = 0.45


def svg_source(svg: Path, simplified: bool) -> bytes:
    """SVG bytes; when simplified, drop every element tagged class="detail"."""
    if not simplified:
        return svg.read_bytes()
    ET.register_namespace("", SVG_NS)
    tree = ET.parse(svg)
    for parent in tree.iter():
        for child in list(parent):
            if "detail" in (child.get("class") or "").split():
                parent.remove(child)
    return ET.tostring(tree.getroot())


def render(svg: Path, simplified: bool = False, edge_darken: float = EDGE_DARKEN) -> Image.Image:
    png = cairosvg.svg2png(bytestring=svg_source(svg, simplified), output_width=RENDER, output_height=RENDER)
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    px = np.asarray(image).astype(np.float64)
    alpha = px[..., 3] / 255.0
    inner = Image.fromarray((alpha * 255).astype("uint8")).filter(ImageFilter.MinFilter(9)).filter(ImageFilter.GaussianBlur(4))
    band = np.clip(alpha - np.asarray(inner) / 255.0, 0.0, 1.0)
    px[..., :3] *= (1.0 - edge_darken * band)[..., None]
    return Image.fromarray(px.clip(0, 255).astype("uint8"))


def fit(image: Image.Image, size: int = SIZE, margin: int = MARGIN) -> Image.Image:
    bbox = image.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox is None:
        raise ValueError("SVG rendered fully transparent")
    side = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    full = side * size / (size - 2 * margin)
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    box = (int(round(cx - full / 2)), int(round(cy - full / 2)), int(round(cx + full / 2)), int(round(cy + full / 2)))
    crop = np.asarray(image.crop(box)).astype(np.float64)
    premult = crop.copy()
    premult[..., :3] *= crop[..., 3:4] / 255.0
    small = np.asarray(Image.fromarray(premult.clip(0, 255).astype("uint8")).resize((size, size), Image.LANCZOS)).astype(np.float64)
    alpha = small[..., 3:4]
    rgb = np.where(alpha > 0, small[..., :3] * 255.0 / np.maximum(alpha, 1.0), 0.0)
    return Image.fromarray(np.dstack([rgb, alpha]).clip(0, 255).astype("uint8"), "RGBA")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render the hand-drawn SOL icon SVG to a 128x128 PNG.")
    parser.add_argument("--svg", default=str(DEFAULT_SVG))
    parser.add_argument("--out", default=str(DEFAULT_PNG))
    parser.add_argument("--texticon-out", default=str(TEXTICON_PNG),
                        help="Also render the simplified inline text icon here ('' to skip).")
    args = parser.parse_args(argv)
    out = Path(args.out)
    fit(render(Path(args.svg))).save(out)
    print(f"[png] {out}")
    if args.texticon_out:
        tex = Path(args.texticon_out)
        # Stronger edge so the silhouette survives on the dark tooltip background at 20px.
        fit(render(Path(args.svg), simplified=True, edge_darken=0.6), TEXTICON_SIZE, TEXTICON_MARGIN).save(tex)
        print(f"[png] {tex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
