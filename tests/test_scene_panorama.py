from io import BytesIO

from PIL import Image

from civsim.services.scene_panorama import (
    build_expansion_mask,
    build_panorama_seed,
    crop_normalized,
    load_png,
    paste_cover,
    png_bytes,
)


def _rgb_image(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", size, color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_crop_normalized_quadrants():
    img = load_png(_rgb_image((900, 600), (120, 80, 40)))
    left = crop_normalized(img, {"x": 0, "y": 0, "w": 0.333, "h": 0.55})
    assert left.size == (299, 330)


def test_paste_cover_composites_exit():
    base = load_png(_rgb_image((900, 600), (30, 30, 30)))
    overlay = load_png(_rgb_image((400, 300), (200, 180, 120)))
    rect = {"x": 0.333, "y": 0, "w": 0.334, "h": 0.55}
    merged = paste_cover(base, overlay, rect)
    out = png_bytes(merged)
    assert len(out) > 100
    assert merged.size == (900, 600)


def test_build_panorama_seed_places_floor_and_exit():
    exit_img = load_png(_rgb_image((512, 512), (200, 180, 120)))
    floor_img = load_png(_rgb_image((256, 256), (160, 140, 110)))
    exit_rect = {"x": 0.4725, "y": 0.16, "w": 0.055, "h": 0.12}
    floor_rect = {"x": 0, "y": 0.66, "w": 1, "h": 0.34}
    seed = build_panorama_seed(
        exit_img, (1024, 1024), exit_rect, floor_img=floor_img, floor_rect=floor_rect
    )
    assert seed.size == (1024, 1024)
    assert seed.getpixel((512, 800))[0] > 100
    assert seed.getpixel((512, 240))[0] > 100


def test_build_expansion_mask_preserves_opening():
    rect = {"x": 0.4725, "y": 0.16, "w": 0.055, "h": 0.12}
    mask = build_expansion_mask((1024, 1024), rect)
    assert mask.getpixel((512, 280))[3] == 255
    assert mask.getpixel((50, 50))[3] == 0


def test_build_expansion_mask_preserves_floor_strip():
    exit_rect = {"x": 0.4725, "y": 0.16, "w": 0.055, "h": 0.12}
    floor_rect = {"x": 0, "y": 0.66, "w": 1, "h": 0.34}
    mask = build_expansion_mask((1024, 1024), [exit_rect, floor_rect])
    assert mask.getpixel((512, 240))[3] == 255
    assert mask.getpixel((512, 800))[3] == 255
    assert mask.getpixel((512, 400))[3] == 0


def test_mask_png_bytes_keeps_alpha():
    from civsim.services.scene_panorama import mask_png_bytes

    rect = {"x": 0.4725, "y": 0.16, "w": 0.055, "h": 0.12}
    mask = build_expansion_mask((1024, 1024), rect)
    data = mask_png_bytes(mask)
    loaded = load_png(data)
    assert loaded.mode == "RGBA"
    assert loaded.getpixel((50, 50))[3] == 0
    assert loaded.getpixel((512, 280))[3] == 255
