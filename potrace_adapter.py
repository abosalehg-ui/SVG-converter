#!/usr/bin/env python3
"""potrace_adapter - High-quality bitmap tracing via pypotrace (optional).

Provides :func:`is_available` and :func:`trace_bw` for the Tkinter app.
If ``pypotrace`` is not installed, ``is_available()`` returns ``False`` and
callers should fall back to :func:`svg_core.create_svg`.

Why an adapter:
    Potrace produces Bezier curves following object contours — dramatically
    better than the axis-aligned rectangles produced by the default algorithm.
    But pypotrace is a C extension that may fail to install, so it must be
    optional.

Note:
    This module is only exercised when pypotrace is installed, which CI does
    not do (building the C extension needs system libpotrace + libagg). Treat
    the tracing path as covered by its type checks and the availability tests
    only.
"""

from __future__ import annotations

from collections.abc import Iterable

from svg_core import BW_THRESHOLD, DEFAULT_HEADER_COMMENTS

try:
    import numpy as np
    import potrace  # type: ignore[import-not-found]

    _AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    np = None  # type: ignore[assignment]
    potrace = None  # type: ignore[assignment]
    _AVAILABLE = False


#: Same attribution as the default renderer, with the mode called out.
POTRACE_HEADER_COMMENTS: tuple[str, ...] = (
    DEFAULT_HEADER_COMMENTS[0] + " (Potrace mode)",
    *DEFAULT_HEADER_COMMENTS[1:],
)


def is_available() -> bool:
    """Whether pypotrace + numpy are importable in this environment."""
    return _AVAILABLE


def trace_bw(
    img,
    threshold: int = BW_THRESHOLD,
    turdsize: int = 2,
    alphamax: float = 1.0,
    header_comments: Iterable[str] = POTRACE_HEADER_COMMENTS,
) -> str:
    """Trace a (PIL) image as black-on-white via Potrace and return SVG.

    Args:
        img: A PIL ``Image`` instance. Will be converted to grayscale internally.
        threshold: Pixels with grayscale >= ``threshold`` are treated as white.
        turdsize: Suppress speckles smaller than this many pixels.
        alphamax: Curve smoothness (0=polygons, ~1.34=very smooth).
        header_comments: Comments injected at the top of the SVG.

    Returns:
        SVG document as a UTF-8 string.

    Raises:
        RuntimeError: if Potrace is not available. Check :func:`is_available`
            first and fall back to :func:`svg_core.create_svg` otherwise.
    """
    if not _AVAILABLE:
        raise RuntimeError("pypotrace not available; install with: pip install pypotrace")

    gray = img.convert("L")
    width, height = gray.size

    arr = np.asarray(gray, dtype=np.uint8)
    bitmap_data = arr < threshold  # True = filled (black)

    bmp = potrace.Bitmap(bitmap_data)
    path = bmp.trace(turdsize=turdsize, alphamax=alphamax)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        ),
    ]
    for comment in header_comments:
        lines.append(f"  <!-- {comment} -->")

    lines.append('  <g fill="rgb(0,0,0)" fill-rule="evenodd">')
    for curve in path:
        d_parts = []
        start_x, start_y = curve.start_point
        d_parts.append(f"M{start_x:.2f} {start_y:.2f}")
        for segment in curve:
            end_x, end_y = segment.end_point
            if segment.is_corner:
                cx, cy = segment.c
                d_parts.append(f"L{cx:.2f} {cy:.2f}L{end_x:.2f} {end_y:.2f}")
            else:
                c1x, c1y = segment.c1
                c2x, c2y = segment.c2
                d_parts.append(f"C{c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} {end_x:.2f} {end_y:.2f}")
        d_parts.append("Z")
        lines.append(f'    <path d="{"".join(d_parts)}"/>')
    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)
