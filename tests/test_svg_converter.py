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
import svg_core  # noqa: E402
from svg_converter import ConversionSettings, RenderResult, SVGConverterApp  # noqa: E402


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
    result = SVGConverterApp._render(_image(), _settings(conversion_type=conversion_type))
    assert isinstance(result, RenderResult)
    assert result.svg.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert result.svg.rstrip().endswith("</svg>")
    assert result.preview.mode == "RGB"
    assert result.exact_preview


def test_render_applies_output_scale():
    result = SVGConverterApp._render(_image(12, 9), _settings(output_scale=2.0))
    assert 'viewBox="0 0 24 18"' in result.svg


def test_render_never_scales_to_zero():
    # A 1px image at 50% must not collapse into an empty (and invalid) image.
    result = SVGConverterApp._render(Image.new("RGB", (1, 1)), _settings(output_scale=0.5))
    assert 'viewBox="0 0 1 1"' in result.svg


def test_bw_render_emits_only_black_and_white():
    result = SVGConverterApp._render(_image(), _settings(conversion_type="bw"))
    fills = set(re.findall(r'fill="(rgb\([^)]+\))"', result.svg))
    assert fills <= {"rgb(0,0,0)", "rgb(255,255,255)"}


def test_render_keeps_a_transparent_logo_visible():
    # Regression: the logo vanished into a solid black square in BW mode.
    logo = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    logo.paste((0, 0, 0, 255), (3, 3, 7, 7))
    result = SVGConverterApp._render(logo, _settings(conversion_type="bw", detail_level=10))
    assert 'fill="rgb(255,255,255)"' in result.svg
    assert result.preview.getpixel((0, 0)) == (255, 255, 255)
    assert result.preview.getpixel((5, 5)) == (0, 0, 0)


def test_render_preview_matches_the_svg_blocks():
    img = _image(23, 17)
    settings = _settings(color_levels=4, detail_level=7)
    result = SVGConverterApp._render(img, settings)
    expected = svg_core.preview_image(img, "color", color_levels=4, detail_level=7)
    assert result.preview.tobytes() == expected.tobytes()


def test_render_falls_back_when_potrace_is_missing():
    # use_potrace=True must not explode when pypotrace is absent.
    settings = _settings(conversion_type="bw", use_potrace=True)
    result = SVGConverterApp._render(_image(), settings)
    if potrace_adapter.is_available():
        assert "<path" in result.svg
    else:
        assert "<rect" in result.svg


def test_render_refuses_oversized_output_before_resizing(monkeypatch):
    monkeypatch.setattr(svg_converter, "MAX_OUTPUT_PIXELS", 100)
    with pytest.raises(svg_converter.ConversionLimitError, match="كبير جداً"):
        SVGConverterApp._render(_image(10, 10), _settings(output_scale=2.0))


def test_render_refuses_too_many_blocks(monkeypatch):
    monkeypatch.setattr(svg_converter, "MAX_BLOCKS", 10)
    with pytest.raises(svg_converter.ConversionLimitError):
        SVGConverterApp._render(_image(10, 10), _settings(detail_level=10))


def test_render_rejects_invalid_settings():
    with pytest.raises(ValueError):
        SVGConverterApp._render(_image(), _settings(color_levels=99))


# ---------- preview ----------


def test_svg_preview_falls_back_to_the_bitmap_without_cairosvg(monkeypatch):
    monkeypatch.setattr(svg_converter, "_HAS_CAIROSVG", False)
    fallback = _image()
    preview, exact = SVGConverterApp._svg_preview("<svg/>", fallback)
    assert preview.size == fallback.size
    assert not exact


def test_svg_preview_survives_a_broken_rasterizer(monkeypatch):
    class Boom:
        @staticmethod
        def svg2png(**_kwargs):
            raise RuntimeError("cairo exploded")

    monkeypatch.setattr(svg_converter, "_HAS_CAIROSVG", True)
    monkeypatch.setattr(svg_converter, "cairosvg", Boom)
    fallback = _image()
    preview, exact = SVGConverterApp._svg_preview("<svg/>", fallback)
    assert preview.size == fallback.size
    assert not exact


# ---------- decompression bombs ----------


def test_open_image_rejects_oversized_images(tmp_path, monkeypatch):
    path = tmp_path / "big.png"
    _image(40, 40).save(path)
    monkeypatch.setattr(svg_converter, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ValueError, match="كبيرة جداً"):
        SVGConverterApp._open_image_safely(str(path))


def test_open_image_checks_size_before_decoding(tmp_path, monkeypatch):
    path = tmp_path / "big.png"
    _image(40, 40).save(path)
    monkeypatch.setattr(svg_converter, "MAX_IMAGE_PIXELS", 100)

    def fail_load(self):
        raise AssertionError("decoded an image that was already known to be too big")

    monkeypatch.setattr(Image.Image, "load", fail_load)
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


# ---------- user-facing messages ----------


def test_load_errors_are_described_in_arabic(tmp_path):
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"not an image at all")
    with pytest.raises(Exception) as caught:
        SVGConverterApp._open_image_safely(str(junk))
    message = svg_converter.describe_load_error(caught.value)
    assert "تالفاً" in message
    assert "cannot identify" not in message


def test_conversion_errors_are_described_in_arabic():
    too_complex = svg_core.OutputTooComplexError(10**9)
    assert svg_converter.describe_conversion_error(too_complex) == svg_converter.TOO_COMPLEX_MESSAGE
    assert "تعذّر" in svg_converter.describe_conversion_error(RuntimeError("boom"))


# ---------- settings snapshot ----------


def test_settings_are_immutable():
    # The worker thread must not be able to mutate what it was handed.
    settings = _settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.color_levels = 6  # type: ignore[misc]


def test_supported_extensions_include_webp():
    assert "*.webp" in svg_converter.SUPPORTED_EXTENSIONS


# ---------- superseded conversions ----------


def test_a_superseded_result_is_discarded():
    # Regression: a slow conversion finishing after a new image was loaded
    # replaced that image's preview and was saved under its name. A stale job
    # id must return before touching any widget (the stub has none).
    from types import SimpleNamespace

    app = SimpleNamespace(_job_id=2)
    result = RenderResult("<svg/>", _image(), True)
    assert SVGConverterApp._conversion_done(app, result, 1) is None
    assert SVGConverterApp._conversion_error(app, "boom", 1) is None
