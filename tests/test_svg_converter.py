"""Tests for the desktop app's non-UI logic.

Everything here runs headless: importing ``svg_converter`` only imports Tk, it
never instantiates a window. The UI construction itself still needs a display
and stays untested.
"""

from __future__ import annotations

import dataclasses
import re

import pytest
from PIL import Image

pytest.importorskip("tkinter", reason="python3-tk not installed")

import potrace_adapter  # noqa: E402
import svg_converter  # noqa: E402
from svg_converter import ConversionSettings, SVGConverterApp  # noqa: E402


def _settings(**overrides) -> ConversionSettings:
    base = {
        "conversion_type": "color",
        "color_levels": 3,
        "detail_level": 5,
        "output_scale": 1.0,
        "use_potrace": False,
    }
    base.update(overrides)
    return ConversionSettings(**base)


def _image(width=12, height=9):
    img = Image.new("RGB", (width, height))
    img.putdata(
        [((x * 37) % 256, (y * 53) % 256, 128) for y in range(height) for x in range(width)]
    )
    return img


# ---------- rendering ----------


@pytest.mark.parametrize("conversion_type", ["color", "bw", "grayscale"])
def test_render_produces_svg_and_preview(conversion_type):
    svg, preview = SVGConverterApp._render(_image(), _settings(conversion_type=conversion_type))
    assert svg.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert svg.rstrip().endswith("</svg>")
    assert preview.mode == "RGB"


def test_render_applies_output_scale():
    svg, _ = SVGConverterApp._render(_image(12, 9), _settings(output_scale=2.0))
    assert 'viewBox="0 0 24 18"' in svg


def test_render_never_scales_to_zero():
    # A 1px image at 50% must not collapse into an empty (and invalid) image.
    svg, _ = SVGConverterApp._render(Image.new("RGB", (1, 1)), _settings(output_scale=0.5))
    assert 'viewBox="0 0 1 1"' in svg


def test_bw_render_emits_only_black_and_white():
    svg, _ = SVGConverterApp._render(_image(), _settings(conversion_type="bw"))
    fills = set(re.findall(r'fill="(rgb\([^)]+\))"', svg))
    assert fills <= {"rgb(0,0,0)", "rgb(255,255,255)"}


def test_render_falls_back_when_potrace_is_missing():
    # use_potrace=True must not explode when pypotrace is absent.
    settings = _settings(conversion_type="bw", use_potrace=True)
    svg, _ = SVGConverterApp._render(_image(), settings)
    if potrace_adapter.is_available():
        assert "<path" in svg
    else:
        assert "<rect" in svg


def test_render_rejects_invalid_settings():
    with pytest.raises(ValueError):
        SVGConverterApp._render(_image(), _settings(color_levels=99))


# ---------- preview ----------


def test_svg_preview_falls_back_to_the_bitmap_without_cairosvg(monkeypatch):
    monkeypatch.setattr(svg_converter, "_HAS_CAIROSVG", False)
    fallback = _image()
    assert SVGConverterApp._svg_preview("<svg/>", fallback).size == fallback.size


def test_svg_preview_survives_a_broken_rasterizer(monkeypatch):
    class Boom:
        @staticmethod
        def svg2png(**_kwargs):
            raise RuntimeError("cairo exploded")

    monkeypatch.setattr(svg_converter, "_HAS_CAIROSVG", True)
    monkeypatch.setattr(svg_converter, "cairosvg", Boom)
    fallback = _image()
    assert SVGConverterApp._svg_preview("<svg/>", fallback).size == fallback.size


# ---------- decompression bombs ----------


def test_open_image_rejects_oversized_images(tmp_path, monkeypatch):
    path = tmp_path / "big.png"
    _image(40, 40).save(path)
    monkeypatch.setattr(svg_converter, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ValueError, match="كبيرة جداً"):
        SVGConverterApp._open_image_safely(str(path))


def test_open_image_accepts_normal_images(tmp_path):
    path = tmp_path / "ok.png"
    _image(20, 15).save(path)
    image = SVGConverterApp._open_image_safely(str(path))
    assert image.size == (20, 15)


def test_open_image_rejects_a_decompression_bomb(tmp_path, monkeypatch):
    path = tmp_path / "bomb.png"
    _image(40, 40).save(path)
    # Pillow only warns by default; _open_image_safely must promote that to an error.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises((Image.DecompressionBombError, Image.DecompressionBombWarning)):
        SVGConverterApp._open_image_safely(str(path))


# ---------- settings snapshot ----------


def test_settings_are_immutable():
    # The worker thread must not be able to mutate what it was handed.
    settings = _settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.color_levels = 6  # type: ignore[misc]


def test_supported_extensions_include_webp():
    assert "*.webp" in svg_converter.SUPPORTED_EXTENSIONS
