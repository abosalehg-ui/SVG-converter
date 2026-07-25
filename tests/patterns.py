"""Deterministic pixel patterns shared by the parity fixtures.

Mirrored exactly in ``tests/parity.test.js``. See ``tests/fixtures/README.md``
for the formulas and why they exist.
"""

from __future__ import annotations

from PIL import Image


def pixel(pattern: str, x: int, y: int) -> tuple[int, int, int]:
    """Return the RGB value of one pixel for a named pattern."""
    if pattern == "gradient":
        return ((x * 37 + y * 17) % 256, (x * 11 + y * 53) % 256, (x * 91 + y * 7) % 256)
    if pattern == "checker":
        value = 255 if (x + y) % 2 == 0 else 0
        return (value, value, value)
    if pattern == "gray":
        value = (x * 29 + y * 13) % 256
        return (value, value, value)
    if pattern == "bands":
        return ((y // 3) * 60 % 256, (x // 4) * 80 % 256, 128)
    raise ValueError(f"unknown pattern: {pattern!r}")


def build_image(pattern: str, width: int, height: int) -> Image.Image:
    """Build an RGB PIL image from a named pattern."""
    img = Image.new("RGB", (width, height))
    img.putdata([pixel(pattern, x, y) for y in range(height) for x in range(width)])
    return img
