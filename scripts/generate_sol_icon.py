#!/usr/bin/env python3
"""
Generate shared SOL 128x128 DDS icons through a gpt-image-2 Images API relay.

Usage:
  1. Edit generate_sol_icon_config.json if needed.
  2. Set PACKY_API_KEY, PACKY_SORA_TOKEN, RIGHT_API_KEY, or OPENAI_API_KEY,
     or put api.api_key in generate_sol_icon.local.json.
  3. Run: $env:PYTHONUTF8='1'; & $env:EU5_PYTHON scripts/generate_sol_icon.py

The output DDS files are intended to be reused by the SOL situation, the SOL
mapmode, and the location-window SOL button.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dds_image_lib import (  # noqa: E402
    PNG_SIGNATURE,
    RgbaImage,
    decode_png_rgba,
    encode_png_rgba,
    read_image_rgba,
    resize_rgba,
    write_dds,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "generate_sol_icon_config.json"
LOCAL_CONFIG_PATH = REPO_ROOT / "generate_sol_icon.local.json"
DEFAULT_GENERATIONS_ENDPOINT = "https://www.right.codes/draw/v1/images/generations"
DEFAULT_EDITS_ENDPOINT = "https://www.right.codes/draw/v1/images/edits"
DEFAULT_PNG_DIR = REPO_ROOT / "data" / "generated_icons"
DEFAULT_STYLE_REF_DIR = DEFAULT_PNG_DIR / "_style_refs"
DEFAULT_DDS_PATH = REPO_ROOT / "src" / "stable" / "main_menu" / "gfx" / "interface" / "icons" / "sol" / "sol_living_standard.dds"


@dataclass(frozen=True)
class RetrySettings:
    max_attempts: int
    initial_delay_seconds: float
    max_delay_seconds: float
    backoff_multiplier: float


@dataclass(frozen=True)
class UploadFile:
    field_name: str
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class IconTarget:
    name: str
    path: Path
    extra_paths: tuple[Path, ...]
    width: int
    height: int
    resize: str
    dds_format: str
    mipmaps: bool
    mipmap_min_dimension: int
    opaque_background: tuple[int, int, int]
    max_file_size_bytes: int
    image_size: str
    circle_crop: bool
    circle_crop_feather_px: int
    prompt_requirements: str
    style_reference_paths: tuple[str, ...]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    config = load_json_object(CONFIG_PATH)
    if LOCAL_CONFIG_PATH.exists():
        config = deep_merge(config, load_json_object(LOCAL_CONFIG_PATH))
    return config


def require_object(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the shared SOL DDS icon.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and print the API payload without calling the API or writing art.",
    )
    parser.add_argument(
        "--convert-existing-png",
        metavar="PATH",
        help="Convert an existing PNG to the configured DDS target without calling the API.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing DDS outputs instead of skipping them.",
    )
    return parser.parse_args(argv)


def resolve_repo_path(value: str | None, default_path: Path | None = None) -> Path:
    if not value:
        if default_path is None:
            raise ValueError("missing path")
        return default_path
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def safe_slug(value: str, default: str = "sol_living_standard") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or default


def parse_size(size: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", str(size).strip())
    if not match:
        raise ValueError(f"Invalid image size {size!r}; expected WIDTHxHEIGHT")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError("image size must be positive")
    if width % 16 or height % 16:
        raise ValueError("gpt-image-2 request sizes must use edges that are multiples of 16")
    if max(width, height) > 3840:
        raise ValueError("gpt-image-2 maximum edge length is 3840")
    if max(width, height) / min(width, height) > 3:
        raise ValueError("gpt-image-2 aspect ratio cannot exceed 3:1")
    pixels = width * height
    if pixels < 655_360 or pixels > 8_294_400:
        raise ValueError("gpt-image-2 total pixels must be 655360..8294400")
    return width, height


def parse_rgb(value: Any, key: str) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{key} must be a three-item RGB list")
    result = tuple(int(item) for item in value)
    if any(item < 0 or item > 255 for item in result):
        raise ValueError(f"{key} values must be between 0 and 255")
    return result  # type: ignore[return-value]


def parse_path_list(value: Any, key: str) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a string or list of strings")
    return value


def format_bytes(value: int) -> str:
    return f"{value:,} bytes"


def load_target(config: dict[str, Any]) -> IconTarget:
    output = require_object(config, "output")
    style_reference = require_object(config, "style_reference")
    asset_name = safe_slug(str(output.get("name") or "sol_living_standard"))
    path_template = str(output.get("path") or str(DEFAULT_DDS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"))
    path = resolve_repo_path(path_template.replace("{name}", asset_name), DEFAULT_DDS_PATH)
    extra_paths = tuple(
        resolve_repo_path(extra_path.replace("{name}", asset_name))
        for extra_path in parse_path_list(output.get("extra_paths", []), "output.extra_paths")
    )

    width = int(output.get("width", 128))
    height = int(output.get("height", 128))
    if (width, height) != (128, 128):
        raise ValueError("The shared SOL icon target must be exactly 128x128")

    dds_format = str(output.get("dds_format", "DXT5")).upper()
    if dds_format not in {"DXT1", "DXT5"}:
        raise ValueError("output.dds_format must be DXT1 or DXT5")

    resize = str(output.get("resize", "cover")).lower().strip()
    if resize not in {"cover", "contain", "stretch"}:
        raise ValueError("output.resize must be cover, contain, or stretch")

    image_size = str(output.get("image_size", "1024x1024"))
    if image_size != "auto":
        parse_size(image_size)

    paths = parse_path_list(style_reference.get("paths", []), "style_reference.paths")
    return IconTarget(
        name=asset_name,
        path=path,
        extra_paths=extra_paths,
        width=width,
        height=height,
        resize=resize,
        dds_format=dds_format,
        mipmaps=bool(output.get("mipmaps", True)),
        mipmap_min_dimension=int(output.get("mipmap_min_dimension", 1)),
        opaque_background=parse_rgb(output.get("opaque_background", [0, 0, 0]), "output.opaque_background"),
        max_file_size_bytes=int(output.get("max_file_size_bytes", 100_000)),
        image_size=image_size,
        circle_crop=bool(output.get("circle_crop", True)),
        circle_crop_feather_px=int(output.get("circle_crop_feather_px", 8)),
        prompt_requirements=str(output.get("prompt_requirements") or ""),
        style_reference_paths=tuple(paths),
    )


def clamp_float(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    t = clamp_float((value - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def apply_circle_icon_crop(image: RgbaImage, feather_px: int) -> RgbaImage:
    feather = max(0.0, float(feather_px))
    radius = min(image.width, image.height) / 2.0
    center_x = image.width / 2.0
    center_y = image.height / 2.0
    rgba = bytearray(image.rgba)
    for y in range(image.height):
        dy = (y + 0.5) - center_y
        for x in range(image.width):
            dx = (x + 0.5) - center_x
            dist = math.hypot(dx, dy)
            pos = (y * image.width + x) * 4
            if dist >= radius:
                rgba[pos + 3] = 0
                continue
            if feather > 0 and dist > radius - feather:
                falloff = smoothstep(radius, radius - feather, dist)
                rgba[pos + 3] = int(round(rgba[pos + 3] * falloff))
    return RgbaImage(image.width, image.height, bytes(rgba))


def prepare_target_image(source_image: RgbaImage, target: IconTarget) -> RgbaImage:
    image = resize_rgba(source_image, target.width, target.height, target.resize)
    if target.circle_crop:
        image = apply_circle_icon_crop(image, target.circle_crop_feather_px)
    return image


def resolve_api_key(api_config: dict[str, Any]) -> str:
    configured = str(api_config.get("api_key") or "").strip()
    env_names = api_config.get(
        "api_key_env",
        ["PACKY_API_KEY", "PACKY_SORA_TOKEN", "RIGHT_API_KEY", "OPENAI_API_KEY"],
    )
    if isinstance(env_names, str):
        env_names = [env_names]
    if not isinstance(env_names, list) or not all(isinstance(item, str) for item in env_names):
        raise ValueError("api.api_key_env must be a string or list of strings")
    for name in env_names:
        token = os.environ.get(name, "").strip()
        if token:
            return token
    if configured:
        return configured
    env_hint = ", ".join(env_names)
    raise RuntimeError(
        "Missing image API token. Set one of these environment variables "
        f"({env_hint}) or put api.api_key in {LOCAL_CONFIG_PATH.name}."
    )


def load_retry_settings(api_config: dict[str, Any]) -> RetrySettings:
    max_attempts = int(api_config.get("max_attempts", 4))
    initial_delay = float(api_config.get("retry_initial_delay_seconds", 3))
    max_delay = float(api_config.get("retry_max_delay_seconds", 30))
    backoff = float(api_config.get("retry_backoff_multiplier", 2))
    if max_attempts < 1:
        raise ValueError("api.max_attempts must be at least 1")
    if initial_delay < 0:
        raise ValueError("api.retry_initial_delay_seconds cannot be negative")
    if max_delay < initial_delay:
        raise ValueError("api.retry_max_delay_seconds must be >= retry_initial_delay_seconds")
    if backoff < 1:
        raise ValueError("api.retry_backoff_multiplier must be >= 1")
    return RetrySettings(max_attempts, initial_delay, max_delay, backoff)


def load_proxy_url(api_config: dict[str, Any]) -> str:
    proxy_url = str(api_config.get("proxy_url") or "").strip()
    if not proxy_url:
        return ""
    if "://" not in proxy_url:
        proxy_url = f"http://{proxy_url}"
    return proxy_url


def build_url_opener(proxy_url: str) -> urllib.request.OpenerDirector:
    if not proxy_url:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))


def validate_images_endpoint(endpoint: str, expected_tail: str) -> None:
    normalized = endpoint.strip().rstrip("/")
    if not normalized:
        raise ValueError("api endpoint must be non-empty")
    unsupported = ("/responses", "/chat/completions", "/completions")
    if any(marker in normalized for marker in unsupported):
        raise ValueError("Use the Images API endpoint, not Responses or Chat Completions")
    if not normalized.endswith(expected_tail):
        print(f"[warning] endpoint does not end with {expected_tail}: {endpoint}")


def sleep_before_retry(label: str, attempt: int, error: Exception, retry_settings: RetrySettings) -> None:
    delay = min(
        retry_settings.initial_delay_seconds * (retry_settings.backoff_multiplier ** max(attempt - 1, 0)),
        retry_settings.max_delay_seconds,
    )
    print(
        f"[retry] {label} failed on attempt {attempt}/{retry_settings.max_attempts}: "
        f"{error}. Retrying in {delay:.1f}s..."
    )
    if delay > 0:
        time.sleep(delay)


def api_request(
    label: str,
    request: urllib.request.Request,
    timeout: float,
    retry_settings: RetrySettings,
    opener: urllib.request.OpenerDirector,
) -> bytes:
    for attempt in range(1, retry_settings.max_attempts + 1):
        try:
            with opener.open(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"{label} failed: HTTP {exc.code}: {error_body}") from exc
            if attempt >= retry_settings.max_attempts:
                raise RuntimeError(f"{label} failed after {attempt} attempts: HTTP {exc.code}: {error_body}") from exc
            sleep_before_retry(label, attempt, exc, retry_settings)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt >= retry_settings.max_attempts:
                raise RuntimeError(f"{label} failed after {attempt} attempts: {exc}") from exc
            sleep_before_retry(label, attempt, exc, retry_settings)
    raise RuntimeError(f"{label} failed without a response")


def decode_json_response(response_body: bytes, label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        snippet = response_body[:500].decode("utf-8", errors="replace")
        raise RuntimeError(f"{label} returned non-JSON response: {snippet}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{label} returned a non-object JSON response")
    return decoded


def api_post_json(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
    retry_settings: RetrySettings,
    opener: urllib.request.OpenerDirector,
) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "*/*",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SOLIconGenerator/1.0",
        },
        method="POST",
    )
    return decode_json_response(api_request("API JSON request", request, timeout, retry_settings, opener), "API JSON request")


def build_multipart_body(fields: dict[str, Any], files: list[UploadFile]) -> tuple[bytes, str]:
    boundary = f"----SOLIcon{uuid.uuid4().hex}"
    body = bytearray()
    for key, value in fields.items():
        if value in (None, ""):
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    for upload in files:
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        disposition = f'Content-Disposition: form-data; name="{upload.field_name}"; filename="{upload.filename}"\r\n'
        body.extend(disposition.encode("utf-8"))
        body.extend(f"Content-Type: {upload.content_type}\r\n\r\n".encode("ascii"))
        body.extend(upload.data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    return bytes(body), boundary


def api_post_multipart(
    endpoint: str,
    api_key: str,
    fields: dict[str, Any],
    files: list[UploadFile],
    timeout: float,
    retry_settings: RetrySettings,
    opener: urllib.request.OpenerDirector,
) -> dict[str, Any]:
    body, boundary = build_multipart_body(fields, files)
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Accept": "*/*",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "SOLIconGenerator/1.0",
        },
        method="POST",
    )
    return decode_json_response(
        api_request("API multipart request", request, timeout, retry_settings, opener),
        "API multipart request",
    )


def download_bytes(
    url: str,
    timeout: float,
    retry_settings: RetrySettings,
    opener: urllib.request.OpenerDirector,
) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "SOLIconGenerator/1.0"})
    return api_request("image download", request, timeout, retry_settings, opener)


def extract_image_bytes(
    response: dict[str, Any],
    timeout: float,
    retry_settings: RetrySettings,
    opener: urllib.request.OpenerDirector,
) -> tuple[bytes, str]:
    data = response.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise RuntimeError("Image API response did not contain data[0]")
    item = data[0]
    revised_prompt = str(item.get("revised_prompt") or "")
    if isinstance(item.get("b64_json"), str):
        encoded = item["b64_json"]
        if encoded.startswith("data:image/") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        try:
            return base64.b64decode(encoded, validate=False), revised_prompt
        except binascii.Error as exc:
            raise RuntimeError("Image API returned invalid b64_json image data") from exc
    if isinstance(item.get("url"), str):
        return download_bytes(item["url"], timeout, retry_settings, opener), revised_prompt
    raise RuntimeError("Image API response did not contain b64_json or url image data")


def build_final_prompt(prompt_config: dict[str, Any], image_config: dict[str, Any], target: IconTarget) -> str:
    subject = str(image_config.get("prompt") or image_config.get("natural_prompt") or "").strip()
    if not subject:
        raise ValueError("image.prompt or image.natural_prompt must be set")
    if not bool(prompt_config.get("enabled", True)):
        return subject

    style_rules = str(prompt_config.get("style_rules") or "").strip()
    composition_rules = str(prompt_config.get("composition_rules") or "").strip()
    negative_prompt = str(image_config.get("negative_prompt") or "").strip()
    parts = [
        "Create a Europa Universalis V UI icon for the Standard of Living mod.",
        f"Subject: {subject}",
        "Use a compact painterly strategy-game icon style with a readable centered silhouette.",
        "It must work as one shared icon for a situation entry, a map mode, and a small location-window button.",
        "Do not include text, letters, numbers, watermarks, logos, UI frames, or a large narrative scene.",
        f"Final DDS target: {target.width}x{target.height}, {target.dds_format}, <= {format_bytes(target.max_file_size_bytes)}.",
    ]
    if target.prompt_requirements:
        parts.append(f"Target requirements: {target.prompt_requirements}")
    if style_rules:
        parts.append(f"Style rules: {style_rules}")
    if composition_rules:
        parts.append(f"Composition rules: {composition_rules}")
    if negative_prompt:
        parts.append(f"Avoid: {negative_prompt}")
    return "\n".join(parts)


def build_generation_payload(image_config: dict[str, Any], final_prompt: str, target: IconTarget) -> dict[str, Any]:
    payload = {
        "model": image_config.get("model", "gpt-image-2"),
        "prompt": final_prompt,
        "size": image_config.get("size", target.image_size),
        "quality": image_config.get("quality", "high"),
        "output_format": image_config.get("output_format", "png"),
        "response_format": image_config.get("response_format", "url"),
        "n": image_config.get("n", 1),
    }
    for key in ("background", "moderation", "user", "output_compression"):
        if key in image_config and image_config[key] not in (None, ""):
            payload[key] = image_config[key]
    if payload["model"] != "gpt-image-2":
        raise ValueError("image.model must be gpt-image-2")
    if payload["n"] != 1:
        raise ValueError("gpt-image-2 only supports image.n = 1")
    if payload["output_format"] != "png":
        raise ValueError("This helper expects image.output_format = png")
    if payload["response_format"] not in {"url", "b64_json"}:
        raise ValueError("image.response_format must be url or b64_json")
    if payload["quality"] not in {"low", "medium", "high", "auto"}:
        raise ValueError("image.quality must be low, medium, high, or auto")
    if payload.get("background") == "transparent":
        raise ValueError("gpt-image-2 relay should use opaque background; transparent is not supported here")
    if str(payload["size"]) != "auto":
        parse_size(str(payload["size"]))
    if "output_compression" in payload:
        compression = int(payload["output_compression"])
        if compression < 0 or compression > 100:
            raise ValueError("image.output_compression must be between 0 and 100")
        payload["output_compression"] = compression
    return payload


def collect_style_references(style_config: dict[str, Any], target: IconTarget, dry_run: bool) -> list[UploadFile]:
    paths = list(target.style_reference_paths)
    if not paths:
        if bool(style_config.get("required", False)):
            raise ValueError("style_reference.required is true, but style_reference.paths is empty")
        return []

    upload_field = str(style_config.get("upload_field_name") or "image")
    if upload_field != "image":
        raise ValueError('Image edits endpoint expects style_reference.upload_field_name = "image"')
    temporary_dir = resolve_repo_path(style_config.get("temporary_png_dir"), DEFAULT_STYLE_REF_DIR)
    if bool(style_config.get("write_converted_pngs", True)) and not dry_run:
        temporary_dir.mkdir(parents=True, exist_ok=True)

    uploads: list[UploadFile] = []
    for index, raw_path in enumerate(paths, start=1):
        path = resolve_repo_path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Missing style reference: {path}")
        png_bytes = encode_png_rgba(read_image_rgba(path))
        png_name = f"{index:02d}_{target.name}_{safe_slug(path.stem)}.png"
        if bool(style_config.get("write_converted_pngs", True)) and not dry_run:
            png_path = temporary_dir / png_name
            png_path.write_bytes(png_bytes)
            print(f"[style] converted {display_path(path)} -> {display_path(png_path)}")
        else:
            print(f"[style] converted {display_path(path)} for upload")
        uploads.append(UploadFile(upload_field, png_name, "image/png", png_bytes))
    return uploads


def call_image_api(
    api_config: dict[str, Any],
    style_config: dict[str, Any],
    payload: dict[str, Any],
    style_uploads: list[UploadFile],
    api_key: str,
    timeout: float,
    retry_settings: RetrySettings,
    opener: urllib.request.OpenerDirector,
) -> dict[str, Any]:
    if style_uploads:
        fields = dict(payload)
        fields["input_fidelity"] = str(style_config.get("input_fidelity") or "high")
        endpoint = str(api_config.get("edits_endpoint") or api_config.get("endpoint") or DEFAULT_EDITS_ENDPOINT)
        validate_images_endpoint(endpoint, "/v1/images/edits")
        print(f"[request] POST {endpoint}")
        print(f"[request] model={fields['model']} size={fields['size']} quality={fields['quality']} refs={len(style_uploads)}")
        return api_post_multipart(endpoint, api_key, fields, style_uploads, timeout, retry_settings, opener)

    endpoint = str(api_config.get("generations_endpoint") or api_config.get("endpoint") or DEFAULT_GENERATIONS_ENDPOINT)
    validate_images_endpoint(endpoint, "/v1/images/generations")
    print(f"[request] POST {endpoint}")
    print(f"[request] model={payload['model']} size={payload['size']} quality={payload['quality']} refs=0")
    return api_post_json(endpoint, api_key, payload, timeout, retry_settings, opener)


def output_artifact_stem(output_config: dict[str, Any], target: IconTarget) -> str:
    template = str(output_config.get("artifact_stem") or "{name}")
    return safe_slug(template.replace("{name}", target.name))


def write_prepared_png(output_config: dict[str, Any], target: IconTarget, image: RgbaImage) -> Path:
    png_dir = resolve_repo_path(output_config.get("png_dir"), DEFAULT_PNG_DIR)
    png_path = png_dir / f"{output_artifact_stem(output_config, target)}.png"
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(encode_png_rgba(image))
    print(f"[png] {display_path(png_path)}")
    return png_path


def iter_unique_output_paths(target: IconTarget) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for path in (target.path, *target.extra_paths):
        key = str(path.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def write_single_dds_path(
    path: Path,
    target: IconTarget,
    prepared: RgbaImage,
    overwrite: bool,
) -> dict[str, Any]:
    if path.exists() and not overwrite:
        size = path.stat().st_size
        print(f"[skip] {display_path(path)} exists; output.overwrite is false")
        return {"path": display_path(path).replace("\\", "/"), "skipped": True, "file_size_bytes": size}

    levels = write_dds(
        prepared,
        path,
        dds_format=target.dds_format,
        overwrite=overwrite,
        opaque_background=target.opaque_background,
        mipmaps=target.mipmaps,
        mipmap_min_dimension=target.mipmap_min_dimension,
    )
    file_size = path.stat().st_size
    if file_size > target.max_file_size_bytes:
        raise RuntimeError(
            f"DDS output is {format_bytes(file_size)}, above the "
            f"{format_bytes(target.max_file_size_bytes)} limit: {path}"
        )
    print(
        f"[dds] {display_path(path)} "
        f"({target.width}x{target.height} {target.dds_format}, levels={levels}, "
        f"{format_bytes(file_size)} <= {format_bytes(target.max_file_size_bytes)})"
    )
    return {
        "path": display_path(path).replace("\\", "/"),
        "width": target.width,
        "height": target.height,
        "dds_format": target.dds_format,
        "dds_levels": levels,
        "file_size_bytes": file_size,
        "max_file_size_bytes": target.max_file_size_bytes,
    }


def write_target(output_config: dict[str, Any], target: IconTarget, source_image: RgbaImage) -> dict[str, Any]:
    overwrite = bool(output_config.get("overwrite", False))
    prepared = prepare_target_image(source_image, target)
    target_results = [
        write_single_dds_path(path, target, prepared, overwrite)
        for path in iter_unique_output_paths(target)
    ]
    wrote_any_dds = any(not result.get("skipped") for result in target_results)
    png_path = write_prepared_png(output_config, target, prepared) if wrote_any_dds and bool(output_config.get("keep_png", True)) else None

    primary = dict(target_results[0])
    result = {
        **primary,
        "path": display_path(target.path).replace("\\", "/"),
        "targets": target_results,
        "skipped": not wrote_any_dds,
        "width": target.width,
        "height": target.height,
        "dds_format": target.dds_format,
        "max_file_size_bytes": target.max_file_size_bytes,
    }
    if png_path:
        result["png"] = display_path(png_path).replace("\\", "/")
        for target_result in target_results:
            if not target_result.get("skipped"):
                target_result["png"] = result["png"]
    return result


def write_metadata(
    output_config: dict[str, Any],
    target: IconTarget,
    payload: dict[str, Any],
    response: dict[str, Any],
    final_prompt: str,
    revised_prompt: str,
    written_target: dict[str, Any],
) -> None:
    if not bool(output_config.get("write_metadata", True)):
        return
    metadata_dir = resolve_repo_path(output_config.get("metadata_dir"), DEFAULT_PNG_DIR)
    metadata_path = metadata_dir / f"{output_artifact_stem(output_config, target)}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "generator": "scripts/generate_sol_icon.py",
        "final_prompt": final_prompt,
        "payload": payload,
        "created": response.get("created"),
        "revised_prompt": revised_prompt,
        "target": written_target,
        "usage_texture": "gfx/interface/icons/sol/sol_living_standard.dds",
        "usage_textures": [
            "gfx/interface/icons/sol/sol_living_standard.dds",
            "gfx/interface/icons/map_modes/sol_living_standard.dds",
            "gfx/interface/icons/situations/global_living_standard.dds",
            "gfx/interface/icons/modifier_types/sol_living_standard.dds",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[metadata] {display_path(metadata_path)}")


def run(args: argparse.Namespace, config: dict[str, Any], target: IconTarget) -> int:
    api_config = require_object(config, "api")
    prompt_config = require_object(config, "prompt_refinement")
    image_config = require_object(config, "image")
    style_config = require_object(config, "style_reference")
    output_config = require_object(config, "output")
    if args.overwrite:
        output_config = {**output_config, "overwrite": True}

    print(f"[target] {target.name}: {target.width}x{target.height}, request_size={target.image_size}")
    print(f"[target] output={display_path(target.path)}")
    for extra_path in target.extra_paths:
        print(f"[target] extra_output={display_path(extra_path)}")

    if args.convert_existing_png:
        source_path = resolve_repo_path(args.convert_existing_png)
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source PNG: {source_path}")
        written = write_target(output_config, target, decode_png_rgba(source_path.read_bytes()))
        print(f"[summary] converted existing PNG to {written['path']}")
        return 0

    final_prompt = build_final_prompt(prompt_config, image_config, target)
    payload = build_generation_payload(image_config, final_prompt, target)
    style_uploads = collect_style_references(style_config, target, bool(args.dry_run))

    print("[prompt] final prompt:")
    print(final_prompt)

    if args.dry_run:
        print("[dry-run] payload:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("[dry-run] skipped API request and output writes")
        return 0

    timeout = float(api_config.get("timeout_seconds", 180))
    retry_settings = load_retry_settings(api_config)
    proxy_url = load_proxy_url(api_config)
    opener = build_url_opener(proxy_url)
    if proxy_url:
        print(f"[network] proxy={proxy_url}")
    api_key = resolve_api_key(api_config)
    response = call_image_api(api_config, style_config, payload, style_uploads, api_key, timeout, retry_settings, opener)
    png_bytes, revised_prompt = extract_image_bytes(response, timeout, retry_settings, opener)
    if not png_bytes.startswith(PNG_SIGNATURE):
        raise RuntimeError("Generated image payload is not a PNG")
    written = write_target(output_config, target, decode_png_rgba(png_bytes))
    write_metadata(output_config, target, payload, response, final_prompt, revised_prompt, written)
    if revised_prompt:
        print(f"[revised_prompt] {revised_prompt}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    config = load_config()
    target = load_target(config)
    return run(args, config, target)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - command-line helper should fail tersely.
        print(f"[error] {exc}", file=sys.stderr)
        if os.environ.get("SOL_ICON_IMAGE_DEBUG"):
            raise
        raise SystemExit(1) from None
