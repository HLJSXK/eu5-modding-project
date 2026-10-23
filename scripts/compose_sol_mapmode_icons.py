#!/usr/bin/env python3
"""
Install the shared SOL icon and its map-mode variants into every mod target.

Vanilla EU5 distinguishes related map modes by keeping one main object and
adding a small badge in the lower-right corner (peasants -> peasants_percentage,
control -> missing_control, ...). SOL follows the same convention:

  sol_living_standard   base icon
  sol_purchasing_power  base + small coin stack
  sol_ranking           base + up arrow
  sol_substitution      base + exchange arrows

The badges are 128x128 transparent PNGs in data/generated_icons/_vanilla_badges/,
cut from vanilla map-mode icons (economical_base, missing_control) with a soft
dark outline baked in so they stay readable over light parts of the base.

Usage:
  $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/compose_sol_mapmode_icons.py \
      --base data/generated_icons/sol_living_standard.png [--overwrite] [--preview-only]

The base PNG may be a prepared 128x128 transparent icon or a raw magenta-key
generation (it is keyed and fitted automatically when it is not 128x128).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dds_image_lib import (  # noqa: E402
    RgbaImage,
    build_dds_header,
    build_mipmap_chain,
    encode_dxt5,
    encode_png_rgba,
    read_image_rgba,
)
from icon_keying import composite_over, key_and_fit  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BADGE_DIR = REPO_ROOT / "data" / "generated_icons" / "_vanilla_badges"
# Checked-in base icon (rendered from assets/icons/sol_living_standard.svg by render_sol_icon.py).
DEFAULT_BASE = REPO_ROOT / "assets" / "icons" / "sol_living_standard.png"
PREVIEW_DIR = REPO_ROOT / "data" / "generated_icons" / "variants"
TARGETS = ("stable", "sol_standalone")
ICON_ROOT = Path("main_menu") / "gfx" / "interface" / "icons"

# Shared base icon destinations (relative to each target's ICON_ROOT).
BASE_PATHS = (
    "sol/sol_living_standard.dds",
    "map_modes/sol_living_standard.dds",
    "situations/global_living_standard.dds",
    "modifier_types/sol_living_standard.dds",
)
# Map-mode variant -> badge PNG stem.
VARIANTS = {
    "sol_purchasing_power": "purchasing_coins",
    "sol_ranking": "rank_arrow_up",
    "sol_substitution": "substitution_exchange",
}
SIZE = 128
MAX_DDS_BYTES = 100_000


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose and install the SOL icon set.")
    parser.add_argument("--base", default=str(DEFAULT_BASE), help="Base icon PNG (prepared 128x128 or raw magenta-key generation).")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing DDS files.")
    parser.add_argument("--preview-only", action="store_true", help="Only write preview PNGs to data/generated_icons/variants/.")
    return parser.parse_args(argv)


def load_base(path: Path) -> RgbaImage:
    image = read_image_rgba(path)
    if (image.width, image.height) != (SIZE, SIZE):
        print(f"[base] {path.name} is {image.width}x{image.height}; keying magenta and fitting to {SIZE}x{SIZE}")
        image = key_and_fit(image, (255, 0, 255), SIZE, SIZE, 6)
    return image


def build_icons(base: RgbaImage) -> dict[str, RgbaImage]:
    icons = {"sol_living_standard": base}
    for name, badge_stem in VARIANTS.items():
        badge = read_image_rgba(BADGE_DIR / f"{badge_stem}.png")
        if (badge.width, badge.height) != (SIZE, SIZE):
            raise ValueError(f"Badge {badge_stem}.png must be {SIZE}x{SIZE}")
        icons[name] = composite_over(base, badge)
    return icons


def dds_bytes(image: RgbaImage) -> bytes:
    """Deterministic DXT5 DDS with a full mip chain (128 -> 1 = 8 levels)."""
    levels = [encode_dxt5(level) for level in build_mipmap_chain(image, 1)]
    payload = build_dds_header(image.width, image.height, len(levels[0]), "DXT5", len(levels)) + b"".join(levels)
    if len(payload) > MAX_DDS_BYTES:
        raise RuntimeError(f"DDS is {len(payload)} bytes, above {MAX_DDS_BYTES}")
    return payload


def variant_dds(base_path: Path = DEFAULT_BASE) -> dict[str, bytes]:
    """Map-mode key -> DDS bytes for every SOL map mode (base + badge variants).
    Used by gen_sol_lshud.py so regenerating the map modes keeps the badges."""
    return {name: dds_bytes(image) for name, image in build_icons(load_base(base_path)).items()}


def write_one(image: RgbaImage, path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        print(f"[skip] {path.relative_to(REPO_ROOT)} exists (use --overwrite)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dds_bytes(image))
    print(f"[dds] {path.relative_to(REPO_ROOT)} ({path.stat().st_size} bytes)")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    base_path = Path(args.base)
    if not base_path.is_absolute():
        base_path = REPO_ROOT / base_path
    icons = build_icons(load_base(base_path))

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for name, image in icons.items():
        (PREVIEW_DIR / f"{name}.png").write_bytes(encode_png_rgba(image))
    print(f"[preview] {PREVIEW_DIR.relative_to(REPO_ROOT)}/*.png")
    if args.preview_only:
        return 0

    for target in TARGETS:
        icon_root = REPO_ROOT / "src" / target / ICON_ROOT
        for rel in BASE_PATHS:
            write_one(icons["sol_living_standard"], icon_root / rel, args.overwrite)
        for name in VARIANTS:
            write_one(icons[name], icon_root / "map_modes" / f"{name}.dds", args.overwrite)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001 - command-line helper should fail tersely.
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from None
