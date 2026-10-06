"""Unit tests for svg_core.create_svg."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

import svg_core
from svg_core import (
    MAX_COLOR_LEVELS,
    MAX_DETAIL_LEVEL,
    MIN_COLOR_LEVELS,
    MIN_DETAIL_LEVEL,
    create_svg,
    quantize_channel,
)


def _make_image(pixels, size):
    img = Image.new("RGB", size)
    img.putdata(pixels)
    return img


def _solid_image(size, color=(0, 0, 0)):
    return _make_image([color] * (size[0] * size[1]), size)


def _parse(svg: str):
    # ET is strict about default namespaces; strip them for easier asserts.
    return ET.fromstring(re.sub(r' xmlns="[^"]+"', "", svg, count=1))


# ---------- structure ----------


def test_create_svg_starts_with_xml_decl():
    img = _solid_image((4, 4))
    assert create_svg(img, "color").startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_create_svg_ends_with_closing_tag():
    img = _solid_image((4, 4))
    assert create_svg(img, "color").rstrip().endswith("</svg>")


def test_create_svg_is_valid_xml():
    img = _solid_image((4, 4))
    root = _parse(create_svg(img, "color"))
    assert root.tag == "svg"
    assert root.get("width") == "4"
    assert root.get("height") == "4"
    assert root.get("viewBox") == "0 0 4 4"


def test_create_svg_sets_crisp_edges():
    # Adjacent rectangles otherwise show hairline seams at some zoom levels.
    img = _solid_image((4, 4))
    assert _parse(create_svg(img, "color")).get("shape-rendering") == "crispEdges"


# ---------- quantization ----------


def test_quantize_channel_preserves_black_and_white():
    # Regression: the old `min(255, (v // step) * step)` turned pure white into
    # mid-gray, darkening every converted image.
    for levels in range(MIN_COLOR_LEVELS, MAX_COLOR_LEVELS + 1):
        assert quantize_channel(0, levels) == 0
        assert quantize_channel(255, levels) == 255


def test_quantize_channel_is_monotonic():
    for levels in range(MIN_COLOR_LEVELS, MAX_COLOR_LEVELS + 1):
        values = [quantize_channel(v, levels) for v in range(256)]
        assert values == sorted(values)


def test_quantize_channel_emits_exactly_color_levels_values():
    for levels in range(MIN_COLOR_LEVELS, MAX_COLOR_LEVELS + 1):
        assert len({quantize_channel(v, levels) for v in range(256)}) == levels


def test_white_image_stays_white():
    img = _solid_image((4, 4), (255, 255, 255))
    assert 'fill="rgb(255,255,255)"' in create_svg(img, "color", color_levels=3)


def test_solid_black_image_produces_single_group():
    img = _solid_image((4, 4), (0, 0, 0))
    root = _parse(create_svg(img, "color"))
    groups = root.findall("g")
    assert len(groups) == 1
    assert groups[0].get("fill") == "rgb(0,0,0)"


def test_bw_mode_skips_quantization():
    # Pre-filtered BW: 50% black, 50% white pixels.
    pixels = [
        (0, 0, 0) if (x + y) % 2 == 0 else (255, 255, 255) for y in range(4) for x in range(4)
    ]
    img = _make_image(pixels, (4, 4))
    root = _parse(create_svg(img, "bw", detail_level=10))  # block_size=1
    fills = {g.get("fill") for g in root.findall("g")}
    assert fills == {"rgb(0,0,0)", "rgb(255,255,255)"}


def test_bw_stays_binary_when_blocks_average_mixed_pixels():
    # Regression: with block_size > 1 a checkerboard averaged to mid-gray, so
    # "أبيض وأسود" quietly produced dozens of gray shades.
    pixels = [
        (255, 255, 255) if (x + y) % 2 == 0 else (0, 0, 0) for y in range(12) for x in range(12)
    ]
    img = _make_image(pixels, (12, 12))
    for detail in range(MIN_DETAIL_LEVEL, MAX_DETAIL_LEVEL + 1):
        svg = create_svg(img, "bw", detail_level=detail)
        fills = set(re.findall(r'fill="(rgb\([^)]+\))"', svg))
        assert fills <= {"rgb(0,0,0)", "rgb(255,255,255)"}, f"detail={detail}: {fills}"


def test_every_color_level_is_distinguishable():
    # Regression: the old cbrt(num_colors) mapping collapsed the whole 2-64
    # slider onto two effective palettes, so most of its range did nothing.
    pixels = [(v, v, v) for v in range(0, 256, 4) for _ in range(2)]
    img = _make_image(pixels, (2, 64))
    palette_sizes = []
    for levels in range(MIN_COLOR_LEVELS, MAX_COLOR_LEVELS + 1):
        svg = create_svg(img, "color", color_levels=levels, detail_level=10)
        palette_sizes.append(len(set(re.findall(r'fill="(rgb\([^)]+\))"', svg))))
    assert palette_sizes == sorted(palette_sizes)
    assert len(set(palette_sizes)) == len(palette_sizes), palette_sizes


# ---------- block size / detail level ----------


def test_detail_level_controls_block_size():
    # A non-uniform image so the merge step can't collapse everything.
    pixels = [((x * 40) % 256, (y * 40) % 256, 128) for y in range(10) for x in range(10)]
    img = _make_image(pixels, (10, 10))
    svg_fine = create_svg(img, "color", detail_level=10)  # block_size=1
    svg_coarse = create_svg(img, "color", detail_level=1)  # block_size=10
    n_fine = svg_fine.count("<rect")
    n_coarse = svg_coarse.count("<rect")
    assert n_coarse < n_fine
    assert n_coarse == 1  # 10x10 image fits in one block of size 10


# ---------- rectangle merging ----------


def test_horizontal_merge_combines_adjacent_rects():
    img = _solid_image((10, 1), (50, 50, 50))
    svg = create_svg(img, "color", detail_level=10)  # block_size=1
    rects = re.findall(r"<rect[^/]+/>", svg)
    assert len(rects) == 1
    assert 'width="10"' in rects[0]


def test_vertical_merge_combines_stacked_rects():
    # Regression: merging used to be horizontal only, so a solid 8x8 area
    # emitted 8 stacked rectangles instead of 1.
    img = _solid_image((8, 8), (50, 50, 50))
    svg = create_svg(img, "color", detail_level=10)  # block_size=1
    rects = re.findall(r"<rect[^/]+/>", svg)
    assert len(rects) == 1
    assert 'width="8"' in rects[0]
    assert 'height="8"' in rects[0]


def test_vertical_merge_respects_color_boundaries():
    # Top half black, bottom half white -> exactly two rectangles.
    pixels = [(0, 0, 0)] * 16 + [(255, 255, 255)] * 16
    img = _make_image(pixels, (4, 8))
    svg = create_svg(img, "bw", detail_level=10)
    rects = re.findall(r"<rect[^/]+/>", svg)
    assert len(rects) == 2


def test_merged_rects_cover_the_image_exactly():
    pixels = [((x * 60) % 256, (y * 90) % 256, 64) for y in range(11) for x in range(13)]
    img = _make_image(pixels, (13, 11))
    root = _parse(create_svg(img, "color", detail_level=10))
    covered = 0
    seen = set()
    for rect in root.iter("rect"):
        x, y = int(rect.get("x")), int(rect.get("y"))
        w, h = int(rect.get("width")), int(rect.get("height"))
        covered += w * h
        for py in range(y, y + h):
            for px in range(x, x + w):
                assert (px, py) not in seen, "rectangles overlap"
                seen.add((px, py))
    assert covered == 13 * 11  # no gaps, no overlaps


# ---------- validation ----------


def test_rejects_unknown_conversion_type():
    with pytest.raises(ValueError, match="conversion_type"):
        create_svg(_solid_image((2, 2)), "sepia")


@pytest.mark.parametrize("levels", [MIN_COLOR_LEVELS - 1, MAX_COLOR_LEVELS + 1, 0, -3])
def test_rejects_out_of_range_color_levels(levels):
    with pytest.raises(ValueError, match="color_levels"):
        create_svg(_solid_image((2, 2)), "color", color_levels=levels)


@pytest.mark.parametrize("detail", [0, 11, -1, 1000])
def test_rejects_out_of_range_detail_level(detail):
    with pytest.raises(ValueError, match="detail_level"):
        create_svg(_solid_image((2, 2)), "color", detail_level=detail)


def test_rejects_empty_image():
    with pytest.raises(ValueError, match="empty"):
        create_svg(Image.new("RGB", (0, 0)), "color")


def test_accepts_non_rgb_modes():
    # Regression: a mode "L" image used to raise TypeError on pixel[0].
    for mode in ("L", "RGBA", "P"):
        img = Image.new(mode, (4, 4))
        assert create_svg(img, "color").startswith("<?xml")


# ---------- regression / edge cases ----------


def test_deterministic_output():
    img = _solid_image((6, 6), (200, 100, 50))
    assert create_svg(img, "color") == create_svg(img, "color")


def test_one_pixel_image():
    img = _solid_image((1, 1), (123, 45, 67))
    svg = create_svg(img, "color")
    assert "<rect" in svg
    assert _parse(svg).get("width") == "1"


def test_non_divisible_dimensions():
    # 7x5 with block_size 3 (detail_level=8) -> partial blocks at edges.
    img = _solid_image((7, 5), (255, 255, 255))
    svg = create_svg(img, "color", detail_level=8)
    root = _parse(svg)
    for rect in root.iter("rect"):
        x, y = int(rect.get("x")), int(rect.get("y"))
        w, h = int(rect.get("width")), int(rect.get("height"))
        assert x + w <= 7
        assert y + h <= 5


def test_custom_header_comments_are_emitted():
    svg = create_svg(_solid_image((2, 2)), "color", header_comments=("hello",))
    assert "  <!-- hello -->" in svg
    assert "Generated by" not in svg


def test_default_header_names_the_tool_only():
    # The file belongs to the user: no rights notice, no personal e-mail.
    svg = create_svg(_solid_image((2, 2)), "color")
    assert "<!-- Generated by محول SVG -->" in svg
    assert "All Rights Reserved" not in svg
    assert "@" not in svg


# ---------- step 0: transparency and luma ----------


def _logo(mode="RGBA"):
    """A black square on a fully transparent 8x8 background."""
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    img.paste((0, 0, 0, 255), (2, 2, 6, 6))
    return img.convert(mode) if mode != "RGBA" else img


@pytest.mark.parametrize("conversion_type", ["bw", "grayscale", "color"])
def test_transparent_background_becomes_white_not_black(conversion_type):
    # Regression: alpha was dropped, so a logo on a transparent PNG became a
    # solid black square in BW mode.
    svg = create_svg(_logo(), conversion_type, detail_level=10)
    fills = set(re.findall(r'fill="(rgb\([^)]+\))"', svg))
    assert fills == {"rgb(0,0,0)", "rgb(255,255,255)"}


def test_palette_transparency_is_flattened_too():
    img = _logo().convert("P")
    img.info["transparency"] = img.getpixel((0, 0))
    fills = set(re.findall(r'fill="(rgb\([^)]+\))"', create_svg(img, "bw", detail_level=10)))
    assert "rgb(255,255,255)" in fills


def test_gray_value_and_flatten_channel():
    assert svg_core.gray_value(200, 50, 100) == 101
    assert svg_core.gray_value(255, 255, 255) == 255
    assert svg_core.flatten_channel(0, 0) == 255
    assert svg_core.flatten_channel(17, 255) == 17
    assert svg_core.flatten_channel(0, 128) == 127


def test_bw_and_grayscale_filter_colour_input_themselves():
    img = _solid_image((4, 4), (200, 50, 100))  # luma 101
    assert 'fill="rgb(0,0,0)"' in create_svg(img, "bw", detail_level=10)
    r, g, b = re.search(r'fill="rgb\((\d+),(\d+),(\d+)\)"', create_svg(img, "grayscale")).groups()
    assert r == g == b


def test_prepare_image_python_path_matches_numpy_path(monkeypatch):
    from tests.patterns import build_image

    img = build_image("alpha", 9, 7)
    for mode in ("color", "bw", "grayscale"):
        fast = svg_core.prepare_image(img, mode).tobytes()
        monkeypatch.setattr(svg_core, "_HAS_NUMPY", False)
        slow = svg_core.prepare_image(img, mode).tobytes()
        monkeypatch.setattr(svg_core, "_HAS_NUMPY", svg_core.numpy_available())
        assert fast == slow, mode


# ---------- limits ----------


def test_block_count_matches_the_grid():
    assert svg_core.block_count(10, 10, 10) == 100
    assert svg_core.block_count(11, 10, 1) == 2  # 10px blocks


def test_rejects_output_above_max_blocks(monkeypatch):
    monkeypatch.setattr(svg_core, "MAX_BLOCKS", 10)
    with pytest.raises(svg_core.OutputTooComplexError):
        create_svg(_solid_image((4, 4)), "color", detail_level=10)
    assert create_svg(_solid_image((3, 3)), "color", detail_level=10)


# ---------- preview ----------


def _rects(svg):
    pattern = r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"/>'
    out = []
    for group in re.finditer(r'<g fill="rgb\((\d+),(\d+),(\d+)\)">(.*?)</g>', svg, re.S):
        color = tuple(int(v) for v in group.groups()[:3])
        out += [(color, *map(int, m)) for m in re.findall(pattern, group.group(4))]
    return out


@pytest.mark.parametrize("conversion_type", ["color", "bw", "grayscale"])
def test_preview_image_paints_exactly_what_the_svg_draws(conversion_type):
    from tests.patterns import build_image

    img = build_image("alpha", 17, 11)
    svg = create_svg(img, conversion_type, color_levels=4, detail_level=8)
    preview = svg_core.preview_image(img, conversion_type, color_levels=4, detail_level=8)
    assert preview.size == img.size
    for color, x, y, w, h in _rects(svg):
        for py in range(y, y + h):
            for px in range(x, x + w):
                assert preview.getpixel((px, py)) == color


def test_preview_image_is_downscaled_for_huge_images():
    img = _solid_image((400, 300), (10, 200, 30))
    preview = svg_core.preview_image(img, "color", detail_level=10, max_pixels=12_000)
    assert preview.width * preview.height <= 12_000 * 1.05
    assert abs(preview.width / preview.height - 4 / 3) < 0.05


def test_numpy_availability_flag_is_boolean():
    assert isinstance(svg_core.numpy_available(), bool)
