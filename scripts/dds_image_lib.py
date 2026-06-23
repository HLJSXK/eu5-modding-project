#!/usr/bin/env python3
"""Small PNG/DDS helpers used by asset generation scripts.

The module intentionally sticks to the Python standard library so icon and
illustration helpers do not depend on Pillow, texconv, ImageMagick, or DirectX
tooling being installed on the modding machine.
"""

from __future__ import annotations

import binascii
import math
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class RgbaImage:
    width: int
    height: int
    rgba: bytes

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        expected = self.width * self.height * 4
        if len(self.rgba) != expected:
            raise ValueError(f"RGBA payload length {len(self.rgba)} != {expected}")


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(chunk_type)
    crc = binascii.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def encode_png_rgba(image: RgbaImage) -> bytes:
    rows = bytearray()
    stride = image.width * 4
    for y in range(image.height):
        rows.append(0)
        start = y * stride
        rows.extend(image.rgba[start : start + stride])

    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def paeth_predictor(left: int, up: int, upper_left: int) -> int:
    p = left + up - upper_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - upper_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return upper_left


def decode_png_rgba(png_bytes: bytes) -> RgbaImage:
    if not png_bytes.startswith(PNG_SIGNATURE):
        raise ValueError("image is not a PNG file")

    width = height = bit_depth = color_type = compression = filter_method = interlace = None
    palette: list[tuple[int, int, int]] = []
    transparency: bytes | None = None
    idat_chunks: list[bytes] = []
    pos = len(PNG_SIGNATURE)

    while pos + 8 <= len(png_bytes):
        length = int.from_bytes(png_bytes[pos : pos + 4], "big")
        chunk_type = png_bytes[pos + 4 : pos + 8]
        chunk_start = pos + 8
        chunk_end = chunk_start + length
        if chunk_end + 4 > len(png_bytes):
            raise ValueError("PNG chunk extends beyond end of file")
        chunk_data = png_bytes[chunk_start:chunk_end]
        pos = chunk_end + 4

        if chunk_type == b"IHDR":
            if length != 13:
                raise ValueError("invalid PNG IHDR length")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
        elif chunk_type == b"PLTE":
            if length % 3:
                raise ValueError("invalid PNG palette length")
            palette = [(chunk_data[i], chunk_data[i + 1], chunk_data[i + 2]) for i in range(0, length, 3)]
        elif chunk_type == b"tRNS":
            transparency = chunk_data
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None or bit_depth is None:
        raise ValueError("PNG is missing IHDR")
    if compression != 0 or filter_method != 0:
        raise ValueError("unsupported PNG compression or filter method")
    if interlace != 0:
        raise ValueError("interlaced PNGs are not supported")
    if bit_depth != 8:
        raise ValueError("only 8-bit PNGs are supported")
    if color_type not in {0, 2, 3, 4, 6}:
        raise ValueError(f"unsupported PNG color type: {color_type}")
    if not idat_chunks:
        raise ValueError("PNG is missing IDAT data")

    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    channels = channels_by_type[color_type]
    stride = width * channels
    bytes_per_pixel = channels
    raw = zlib.decompress(b"".join(idat_chunks))
    expected_min = (stride + 1) * height
    if len(raw) < expected_min:
        raise ValueError("PNG decompressed data is shorter than expected")

    rows: list[bytes] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        scanline = bytearray(raw[offset : offset + stride])
        offset += stride

        for x in range(stride):
            left = scanline[x - bytes_per_pixel] if x >= bytes_per_pixel else 0
            up = previous[x]
            upper_left = previous[x - bytes_per_pixel] if x >= bytes_per_pixel else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                predictor = paeth_predictor(left, up, upper_left)
            else:
                raise ValueError(f"unsupported PNG row filter: {filter_type}")
            scanline[x] = (scanline[x] + predictor) & 0xFF

        rows.append(bytes(scanline))
        previous = scanline

    grayscale_transparent: int | None = None
    truecolor_transparent: tuple[int, int, int] | None = None
    if transparency:
        if color_type == 0 and len(transparency) >= 2:
            grayscale_transparent = int.from_bytes(transparency[:2], "big") & 0xFF
        elif color_type == 2 and len(transparency) >= 6:
            truecolor_transparent = (
                int.from_bytes(transparency[0:2], "big") & 0xFF,
                int.from_bytes(transparency[2:4], "big") & 0xFF,
                int.from_bytes(transparency[4:6], "big") & 0xFF,
            )

    rgba = bytearray(width * height * 4)
    out = 0
    for row in rows:
        for x in range(width):
            src = x * channels
            if color_type == 0:
                value = row[src]
                alpha = 0 if grayscale_transparent == value else 255
                red, green, blue = value, value, value
            elif color_type == 2:
                red, green, blue = row[src], row[src + 1], row[src + 2]
                alpha = 0 if truecolor_transparent == (red, green, blue) else 255
            elif color_type == 3:
                index = row[src]
                if index >= len(palette):
                    raise ValueError("PNG palette index out of range")
                red, green, blue = palette[index]
                alpha = transparency[index] if transparency and index < len(transparency) else 255
            elif color_type == 4:
                value, alpha = row[src], row[src + 1]
                red, green, blue = value, value, value
            else:
                red, green, blue, alpha = row[src], row[src + 1], row[src + 2], row[src + 3]

            rgba[out] = red
            rgba[out + 1] = green
            rgba[out + 2] = blue
            rgba[out + 3] = alpha
            out += 4

    return RgbaImage(width=width, height=height, rgba=bytes(rgba))


def _sample_bilinear(image: RgbaImage, sx: float, sy: float) -> tuple[int, int, int, int]:
    sx = min(max(sx, 0.0), image.width - 1.0)
    sy = min(max(sy, 0.0), image.height - 1.0)
    x0 = int(math.floor(sx))
    y0 = int(math.floor(sy))
    x1 = min(x0 + 1, image.width - 1)
    y1 = min(y0 + 1, image.height - 1)
    tx = sx - x0
    ty = sy - y0

    def pixel(x: int, y: int) -> tuple[int, int, int, int]:
        pos = (y * image.width + x) * 4
        return (
            image.rgba[pos],
            image.rgba[pos + 1],
            image.rgba[pos + 2],
            image.rgba[pos + 3],
        )

    p00 = pixel(x0, y0)
    p10 = pixel(x1, y0)
    p01 = pixel(x0, y1)
    p11 = pixel(x1, y1)
    result: list[int] = []
    for channel in range(4):
        top = p00[channel] * (1.0 - tx) + p10[channel] * tx
        bottom = p01[channel] * (1.0 - tx) + p11[channel] * tx
        result.append(int(round(top * (1.0 - ty) + bottom * ty)))
    return result[0], result[1], result[2], result[3]


def _resize_rect(image: RgbaImage, width: int, height: int, rect: tuple[float, float, float, float]) -> RgbaImage:
    if width <= 0 or height <= 0:
        raise ValueError("target dimensions must be positive")
    left, top, src_width, src_height = rect
    out = bytearray(width * height * 4)
    pos = 0
    for y in range(height):
        sy = top + ((y + 0.5) * src_height / height) - 0.5
        for x in range(width):
            sx = left + ((x + 0.5) * src_width / width) - 0.5
            red, green, blue, alpha = _sample_bilinear(image, sx, sy)
            out[pos] = red
            out[pos + 1] = green
            out[pos + 2] = blue
            out[pos + 3] = alpha
            pos += 4
    return RgbaImage(width=width, height=height, rgba=bytes(out))


def crop_resize_rgba(
    image: RgbaImage,
    rect: tuple[float, float, float, float],
    width: int,
    height: int,
) -> RgbaImage:
    left, top, src_width, src_height = rect
    if src_width <= 0 or src_height <= 0:
        raise ValueError("crop dimensions must be positive")
    if left < -0.001 or top < -0.001:
        raise ValueError("crop rectangle cannot start outside the image")
    if left + src_width > image.width + 0.001 or top + src_height > image.height + 0.001:
        raise ValueError("crop rectangle cannot extend outside the image")
    return _resize_rect(image, width, height, rect)


def resize_rgba(image: RgbaImage, width: int, height: int, mode: str = "cover") -> RgbaImage:
    mode = mode.lower().strip()
    if (image.width, image.height) == (width, height):
        return image

    if mode == "stretch":
        return _resize_rect(image, width, height, (0.0, 0.0, float(image.width), float(image.height)))

    source_aspect = image.width / image.height
    target_aspect = width / height
    if mode == "cover":
        if source_aspect > target_aspect:
            crop_width = image.height * target_aspect
            left = (image.width - crop_width) / 2.0
            rect = (left, 0.0, crop_width, float(image.height))
        else:
            crop_height = image.width / target_aspect
            top = (image.height - crop_height) / 2.0
            rect = (0.0, top, float(image.width), crop_height)
        return _resize_rect(image, width, height, rect)

    if mode == "contain":
        if source_aspect > target_aspect:
            fit_width = width
            fit_height = max(1, int(round(width / source_aspect)))
        else:
            fit_height = height
            fit_width = max(1, int(round(height * source_aspect)))
        fitted = _resize_rect(image, fit_width, fit_height, (0.0, 0.0, float(image.width), float(image.height)))
        out = bytearray(width * height * 4)
        x_offset = (width - fit_width) // 2
        y_offset = (height - fit_height) // 2
        for y in range(fit_height):
            src_start = y * fit_width * 4
            dst_start = ((y + y_offset) * width + x_offset) * 4
            out[dst_start : dst_start + fit_width * 4] = fitted.rgba[src_start : src_start + fit_width * 4]
        return RgbaImage(width=width, height=height, rgba=bytes(out))

    raise ValueError("resize mode must be cover, contain, or stretch")


def rgb_to_565(red: int, green: int, blue: int) -> int:
    return ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)


def rgb_from_565(value: int) -> tuple[int, int, int]:
    red = ((value >> 11) & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x3F) * 255 // 63
    blue = (value & 0x1F) * 255 // 31
    return red, green, blue


def color_distance_sq(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _color_palette(color0: int, color1: int, force_four_color: bool) -> list[tuple[int, int, int, int]]:
    palette0 = rgb_from_565(color0)
    palette1 = rgb_from_565(color1)
    if force_four_color or color0 > color1:
        return [
            (*palette0, 255),
            (*palette1, 255),
            (
                (2 * palette0[0] + palette1[0]) // 3,
                (2 * palette0[1] + palette1[1]) // 3,
                (2 * palette0[2] + palette1[2]) // 3,
                255,
            ),
            (
                (palette0[0] + 2 * palette1[0]) // 3,
                (palette0[1] + 2 * palette1[1]) // 3,
                (palette0[2] + 2 * palette1[2]) // 3,
                255,
            ),
        ]
    return [
        (*palette0, 255),
        (*palette1, 255),
        (
            (palette0[0] + palette1[0]) // 2,
            (palette0[1] + palette1[1]) // 2,
            (palette0[2] + palette1[2]) // 2,
            255,
        ),
        (0, 0, 0, 0),
    ]


def _choose_color_endpoints(block: Iterable[tuple[int, int, int, int]]) -> tuple[int, int]:
    pixels = [(red, green, blue) for red, green, blue, _alpha in block]
    avg = (
        sum(pixel[0] for pixel in pixels) // len(pixels),
        sum(pixel[1] for pixel in pixels) // len(pixels),
        sum(pixel[2] for pixel in pixels) // len(pixels),
    )
    first = max(pixels, key=lambda pixel: color_distance_sq(pixel, avg))
    second = max(pixels, key=lambda pixel: color_distance_sq(pixel, first))
    color0 = rgb_to_565(*first)
    color1 = rgb_to_565(*second)
    if color0 < color1:
        color0, color1 = color1, color0
    return color0, color1


def _get_block(image: RgbaImage, block_x: int, block_y: int) -> list[tuple[int, int, int, int]]:
    block: list[tuple[int, int, int, int]] = []
    for y in range(4):
        py = min(block_y + y, image.height - 1)
        for x in range(4):
            px = min(block_x + x, image.width - 1)
            pos = (py * image.width + px) * 4
            block.append((
                image.rgba[pos],
                image.rgba[pos + 1],
                image.rgba[pos + 2],
                image.rgba[pos + 3],
            ))
    return block


def _encode_dxt1_color_block(block: list[tuple[int, int, int, int]]) -> bytes:
    color0, color1 = _choose_color_endpoints(block)
    palette = _color_palette(color0, color1, force_four_color=True)
    indices = 0
    for index, pixel in enumerate(block):
        rgb = (pixel[0], pixel[1], pixel[2])
        best = min(
            range(4),
            key=lambda palette_index: color_distance_sq(rgb, palette[palette_index][:3]),
        )
        indices |= best << (2 * index)
    return struct.pack("<HHI", color0, color1, indices)


def _alpha_palette(alpha0: int, alpha1: int) -> list[int]:
    if alpha0 > alpha1:
        return [
            alpha0,
            alpha1,
            (6 * alpha0 + alpha1) // 7,
            (5 * alpha0 + 2 * alpha1) // 7,
            (4 * alpha0 + 3 * alpha1) // 7,
            (3 * alpha0 + 4 * alpha1) // 7,
            (2 * alpha0 + 5 * alpha1) // 7,
            (alpha0 + 6 * alpha1) // 7,
        ]
    return [
        alpha0,
        alpha1,
        (4 * alpha0 + alpha1) // 5,
        (3 * alpha0 + 2 * alpha1) // 5,
        (2 * alpha0 + 3 * alpha1) // 5,
        (alpha0 + 4 * alpha1) // 5,
        0,
        255,
    ]


def _encode_dxt5_alpha_block(block: list[tuple[int, int, int, int]]) -> bytes:
    alphas = [pixel[3] for pixel in block]
    alpha0 = max(alphas)
    alpha1 = min(alphas)
    palette = _alpha_palette(alpha0, alpha1)
    packed_indices = 0
    for index, alpha in enumerate(alphas):
        best = min(range(8), key=lambda palette_index: abs(alpha - palette[palette_index]))
        packed_indices |= best << (3 * index)
    return bytes([alpha0, alpha1]) + packed_indices.to_bytes(6, "little")


def encode_dxt1(image: RgbaImage) -> bytes:
    blocks_w = (image.width + 3) // 4
    blocks_h = (image.height + 3) // 4
    encoded = bytearray(blocks_w * blocks_h * 8)
    out = 0
    for block_y in range(0, blocks_h * 4, 4):
        for block_x in range(0, blocks_w * 4, 4):
            encoded[out : out + 8] = _encode_dxt1_color_block(_get_block(image, block_x, block_y))
            out += 8
    return bytes(encoded)


def encode_dxt5(image: RgbaImage) -> bytes:
    blocks_w = (image.width + 3) // 4
    blocks_h = (image.height + 3) // 4
    encoded = bytearray(blocks_w * blocks_h * 16)
    out = 0
    for block_y in range(0, blocks_h * 4, 4):
        for block_x in range(0, blocks_w * 4, 4):
            block = _get_block(image, block_x, block_y)
            encoded[out : out + 8] = _encode_dxt5_alpha_block(block)
            encoded[out + 8 : out + 16] = _encode_dxt1_color_block(block)
            out += 16
    return bytes(encoded)


def _blend_channel(source: int, alpha: int, background: int) -> int:
    return (source * alpha + background * (255 - alpha) + 127) // 255


def flatten_rgba(image: RgbaImage, background: tuple[int, int, int]) -> RgbaImage:
    rgba = bytearray(len(image.rgba))
    for pos in range(0, len(image.rgba), 4):
        alpha = image.rgba[pos + 3]
        rgba[pos] = _blend_channel(image.rgba[pos], alpha, background[0])
        rgba[pos + 1] = _blend_channel(image.rgba[pos + 1], alpha, background[1])
        rgba[pos + 2] = _blend_channel(image.rgba[pos + 2], alpha, background[2])
        rgba[pos + 3] = 255
    return RgbaImage(width=image.width, height=image.height, rgba=bytes(rgba))


def build_dds_header(
    width: int,
    height: int,
    data_size: int,
    fourcc: str,
    mipmap_count: int = 1,
) -> bytes:
    if fourcc not in {"DXT1", "DXT5"}:
        raise ValueError("DDS fourcc must be DXT1 or DXT5")
    if mipmap_count < 1:
        raise ValueError("mipmap_count must be at least 1")
    ddsd_caps = 0x00000001
    ddsd_height = 0x00000002
    ddsd_width = 0x00000004
    ddsd_mipmap_count = 0x00020000
    ddsd_pixel_format = 0x00001000
    ddsd_linear_size = 0x00080000
    ddpf_fourcc = 0x00000004
    ddscaps_complex = 0x00000008
    ddscaps_texture = 0x00001000
    ddscaps_mipmap = 0x00400000

    flags = ddsd_caps | ddsd_height | ddsd_width | ddsd_pixel_format | ddsd_linear_size
    caps = ddscaps_texture
    if mipmap_count > 1:
        flags |= ddsd_mipmap_count
        caps |= ddscaps_complex | ddscaps_mipmap

    header = bytearray()
    header += b"DDS "
    header += struct.pack(
        "<IIIIIII",
        124,
        flags,
        height,
        width,
        data_size,
        1,
        mipmap_count,
    )
    header += struct.pack("<11I", *([0] * 11))
    header += struct.pack("<II4sIIIII", 32, ddpf_fourcc, fourcc.encode("ascii"), 0, 0, 0, 0, 0)
    header += struct.pack("<IIIII", caps, 0, 0, 0, 0)
    if len(header) != 128:
        raise AssertionError(f"invalid DDS header length: {len(header)}")
    return bytes(header)


def build_mipmap_chain(image: RgbaImage, min_dimension: int = 1) -> list[RgbaImage]:
    if min_dimension < 1:
        raise ValueError("mipmap min dimension must be at least 1")
    levels = [image]
    current = image
    while max(current.width, current.height) > min_dimension and (current.width > 1 or current.height > 1):
        next_width = max(1, current.width // 2)
        next_height = max(1, current.height // 2)
        if (next_width, next_height) == (current.width, current.height):
            break
        current = resize_rgba(current, next_width, next_height, "stretch")
        levels.append(current)
    return levels


def encode_dds_level(image: RgbaImage, dds_format: str) -> bytes:
    return encode_dxt1(image) if dds_format == "DXT1" else encode_dxt5(image)


def write_dds(
    image: RgbaImage,
    path: Path,
    dds_format: str = "DXT5",
    overwrite: bool = False,
    opaque_background: tuple[int, int, int] = (0, 0, 0),
    mipmaps: bool = False,
    mipmap_min_dimension: int = 1,
) -> int:
    dds_format = dds_format.upper()
    if dds_format not in {"DXT1", "DXT5"}:
        raise ValueError("dds_format must be DXT1 or DXT5")
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing DDS: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    out_image = flatten_rgba(image, opaque_background) if dds_format == "DXT1" else image
    levels = build_mipmap_chain(out_image, mipmap_min_dimension) if mipmaps else [out_image]
    dxt_levels = [encode_dds_level(level, dds_format) for level in levels]
    path.write_bytes(
        build_dds_header(out_image.width, out_image.height, len(dxt_levels[0]), dds_format, len(dxt_levels))
        + b"".join(dxt_levels)
    )
    return len(levels)


def _decode_dxt1_color_block(block: bytes, force_four_color: bool) -> list[tuple[int, int, int, int]]:
    color0, color1, indices = struct.unpack("<HHI", block)
    palette = _color_palette(color0, color1, force_four_color=force_four_color)
    pixels: list[tuple[int, int, int, int]] = []
    for index in range(16):
        palette_index = (indices >> (2 * index)) & 0x03
        pixels.append(palette[palette_index])
    return pixels


def _decode_dxt5_alpha_block(block: bytes) -> list[int]:
    alpha0 = block[0]
    alpha1 = block[1]
    indices = int.from_bytes(block[2:8], "little")
    palette = _alpha_palette(alpha0, alpha1)
    return [palette[(indices >> (3 * index)) & 0x07] for index in range(16)]


def read_dds(path: Path) -> RgbaImage:
    data = path.read_bytes()
    if len(data) < 128 or not data.startswith(b"DDS "):
        raise ValueError(f"{path} is not a DDS file")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    fourcc = data[84:88].decode("ascii", errors="replace").upper()
    if fourcc not in {"DXT1", "DXT5"}:
        raise ValueError(f"unsupported DDS format {fourcc!r}; expected DXT1 or DXT5")

    blocks_w = (width + 3) // 4
    blocks_h = (height + 3) // 4
    block_bytes = 8 if fourcc == "DXT1" else 16
    expected = 128 + blocks_w * blocks_h * block_bytes
    if len(data) < expected:
        raise ValueError(f"DDS payload is shorter than expected for {width}x{height} {fourcc}")

    rgba = bytearray(width * height * 4)
    offset = 128
    for block_y in range(blocks_h):
        for block_x in range(blocks_w):
            block = data[offset : offset + block_bytes]
            offset += block_bytes
            if fourcc == "DXT1":
                pixels = _decode_dxt1_color_block(block, force_four_color=False)
            else:
                alphas = _decode_dxt5_alpha_block(block[:8])
                colors = _decode_dxt1_color_block(block[8:16], force_four_color=True)
                pixels = [(colors[i][0], colors[i][1], colors[i][2], alphas[i]) for i in range(16)]

            for y in range(4):
                py = block_y * 4 + y
                if py >= height:
                    continue
                for x in range(4):
                    px = block_x * 4 + x
                    if px >= width:
                        continue
                    src = y * 4 + x
                    dst = (py * width + px) * 4
                    red, green, blue, alpha = pixels[src]
                    rgba[dst] = red
                    rgba[dst + 1] = green
                    rgba[dst + 2] = blue
                    rgba[dst + 3] = alpha

    return RgbaImage(width=width, height=height, rgba=bytes(rgba))


def read_image_rgba(path: Path) -> RgbaImage:
    suffix = path.suffix.lower()
    if suffix == ".dds":
        return read_dds(path)
    if suffix == ".png":
        return decode_png_rgba(path.read_bytes())
    raise ValueError(f"unsupported image input {path}; expected .dds or .png")
