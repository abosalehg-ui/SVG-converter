"""Unit tests for svg_core.create_svg."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from svg_core import create_svg


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


# ---------- color quantization ----------

def test_solid_black_image_produces_single_group():
    img = _solid_image((4, 4), (0, 0, 0))
    root = _parse(create_svg(img, "color"))
    groups = root.findall("g")
    assert len(groups) == 1
    assert groups[0].get("fill") == "rgb(0,0,0)"


def test_bw_mode_skips_quantization():
    # Pre-filtered BW: 50% black, 50% white pixels.
    pixels = [(0, 0, 0) if (x + y) % 2 == 0 else (255, 255, 255)
              for y in range(4) for x in range(4)]
    img = _make_image(pixels, (4, 4))
    root = _parse(create_svg(img, "bw", detail_level=10))  # block_size=1
    fills = {g.get("fill") for g in root.findall("g")}
    assert fills == {"rgb(0,0,0)", "rgb(255,255,255)"}


def test_num_colors_affects_palette_size():
    # Gradient: each row has different shades of red.
    pixels = [(r, 0, 0) for r in range(0, 64) for _ in range(4)]
    img = _make_image(pixels, (4, 64))
    # Few palette levels -> few unique fills.
    svg_few = create_svg(img, "color", num_colors=8, detail_level=10)
    svg_many = create_svg(img, "color", num_colors=64, detail_level=10)
    fills_few = set(re.findall(r'fill="(rgb\([^)]+\))"', svg_few))
    fills_many = set(re.findall(r'fill="(rgb\([^)]+\))"', svg_many))
    assert len(fills_few) <= len(fills_many)


# ---------- block size / detail level ----------

def test_detail_level_controls_block_size():
    img = _solid_image((10, 10), (100, 100, 100))
    # detail_level=10 -> block_size=1 -> 100 source rects (then merged)
    svg_fine = create_svg(img, "color", detail_level=10)
    # detail_level=1 -> block_size=10 -> 1 rect total
    svg_coarse = create_svg(img, "color", detail_level=1)
    n_fine = svg_fine.count("<rect")
    n_coarse = svg_coarse.count("<rect")
    assert n_coarse < n_fine
    assert n_coarse == 1  # 10x10 image fits in one block of size 10


# ---------- horizontal merging ----------

def test_horizontal_merge_combines_adjacent_rects():
    img = _solid_image((10, 1), (50, 50, 50))
    svg = create_svg(img, "color", detail_level=10)  # block_size=1
    # All 10 same-colored pixels in one row should merge into one wide rect.
    rects = re.findall(r'<rect[^/]+/>', svg)
    assert len(rects) == 1
    assert 'width="10"' in rects[0]


# ---------- regression / golden ----------

def test_deterministic_output():
    img = _solid_image((6, 6), (200, 100, 50))
    assert create_svg(img, "color") == create_svg(img, "color")


# ---------- edge cases ----------

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
    # Sum of rect widths/heights should cover the full image without gaps.
    # We verify at least that no rect extends beyond the bounds.
    for rect in root.iter("rect"):
        x = int(rect.get("x"))
        y = int(rect.get("y"))
        w = int(rect.get("width"))
        h = int(rect.get("height"))
        assert x + w <= 7
        assert y + h <= 5
