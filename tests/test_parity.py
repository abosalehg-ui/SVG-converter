"""Golden-fixture parity tests for the Python implementation.

`tests/parity.test.js` asserts the JavaScript port against the very same golden
files. If the two implementations ever drift again, one suite goes red while the
other stays green — which is the signal that was missing when
`int(64 ** (1/3)) == 3` silently disagreed with `Math.cbrt(64) === 4`.

See `tests/fixtures/README.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import svg_core
from svg_core import create_svg
from tests.patterns import build_image

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
CASES = json.loads((FIXTURES_DIR / "cases.json").read_text(encoding="utf-8"))


def _render(case: dict) -> str:
    img = build_image(case["pattern"], case["width"], case["height"])
    return create_svg(
        img,
        conversion_type=case["conversionType"],
        color_levels=case["colorLevels"],
        detail_level=case["detailLevel"],
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_matches_golden_fixture(case):
    golden = (FIXTURES_DIR / f"{case['name']}.svg").read_text(encoding="utf-8")
    assert _render(case) == golden, (
        f"{case['name']} drifted from its golden fixture. If the change is "
        f"intentional, run: python tests/fixtures/generate_golden.py"
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_pure_python_path_matches_numpy_path(case, monkeypatch):
    """The NumPy fast path must be an optimization only, never a behaviour change."""
    fast = _render(case)
    monkeypatch.setattr(svg_core, "_HAS_NUMPY", False)
    slow = _render(case)
    assert fast == slow


def test_fixtures_cover_every_conversion_type():
    covered = {case["conversionType"] for case in CASES}
    assert covered == set(svg_core.VALID_CONVERSION_TYPES)


def test_fixtures_cover_the_color_level_range():
    levels = {case["colorLevels"] for case in CASES}
    assert svg_core.MIN_COLOR_LEVELS in levels
    assert svg_core.MAX_COLOR_LEVELS in levels


def test_fixtures_cover_the_detail_level_range():
    details = {case["detailLevel"] for case in CASES}
    assert svg_core.MIN_DETAIL_LEVEL in details
    assert svg_core.MAX_DETAIL_LEVEL in details
