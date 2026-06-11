from __future__ import annotations

import io
from typing import Any

from PIL import Image


def crop_normalized(img: Image.Image, rect: dict[str, float]) -> Image.Image:
    w, h = img.size
    x0 = max(0, min(w, int(rect["x"] * w)))
    y0 = max(0, min(h, int(rect["y"] * h)))
    x1 = max(0, min(w, int((rect["x"] + rect["w"]) * w)))
    y1 = max(0, min(h, int((rect["y"] + rect["h"]) * h)))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Invalid crop rectangle")
    return img.crop((x0, y0, x1, y1))


def paste_cover(base: Image.Image, overlay: Image.Image, rect: dict[str, float]) -> Image.Image:
    result = base.convert("RGBA")
    w, h = result.size
    tw = max(1, int(rect["w"] * w))
    th = max(1, int(rect["h"] * h))
    tx = int(rect["x"] * w)
    ty = int(rect["y"] * h)
    layer = overlay.convert("RGBA")
    scale = max(tw / layer.width, th / layer.height)
    nw = max(1, int(layer.width * scale))
    nh = max(1, int(layer.height * scale))
    layer = layer.resize((nw, nh), Image.Resampling.LANCZOS)
    left = tx + (tw - nw) // 2
    top = ty + (th - nh) // 2
    result.paste(layer, (left, top), layer)
    return result


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def mask_png_bytes(img: Image.Image) -> bytes:
    """PNG with alpha channel preserved (required by OpenAI images.edit)."""
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    return buf.getvalue()


def build_expansion_mask(
    size: tuple[int, int], preserve_rects: dict[str, float] | list[dict[str, float]]
) -> Image.Image:
    """Mask for images.edit: transparent = expand, opaque = keep seed pixels."""
    rects = (
        [preserve_rects]
        if isinstance(preserve_rects, dict)
        else list(preserve_rects)
    )
    w, h = size
    mask = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for rect in rects:
        x0 = int(rect["x"] * w)
        y0 = int(rect["y"] * h)
        x1 = int((rect["x"] + rect["w"]) * w)
        y1 = int((rect["y"] + rect["h"]) * h)
        opaque = Image.new(
            "RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (255, 255, 255, 255)
        )
        mask.paste(opaque, (x0, y0))
    return mask


def build_panorama_seed(
    exit_img: Image.Image,
    size: tuple[int, int],
    exit_rect: dict[str, float],
    *,
    floor_img: Image.Image | None = None,
    floor_rect: dict[str, float] | None = None,
    base_color: tuple[int, int, int] = (42, 36, 30),
) -> Image.Image:
    """Place floor strip and exit opening on canvas; AI expands walls around them."""
    seed = Image.new("RGBA", size, (*base_color, 255))
    if floor_img is not None and floor_rect is not None:
        seed = paste_cover(seed, floor_img, floor_rect)
    return paste_cover(seed, exit_img, exit_rect)


def load_png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")

