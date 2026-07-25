#!/usr/bin/env python3
"""Regenerate the golden parity fixtures from the Python implementation.

Run this ONLY when the conversion algorithm changes on purpose:

    python tests/fixtures/generate_golden.py

Then run both suites. ``pytest`` passing proves Python matches the new goldens;
``node --test tests/`` passing proves the JavaScript port was updated to match.
A failure in only one of them is the drift signal these fixtures exist for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURES_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from patterns import build_image  # noqa: E402, I001
from svg_core import create_svg  # noqa: E402, I001


def main() -> int:
    cases = json.loads((FIXTURES_DIR / "cases.json").read_text(encoding="utf-8"))
    for case in cases:
        img = build_image(case["pattern"], case["width"], case["height"])
        svg = create_svg(
            img,
            conversion_type=case["conversionType"],
            color_levels=case["colorLevels"],
            detail_level=case["detailLevel"],
        )
        target = FIXTURES_DIR / f"{case['name']}.svg"
        target.write_text(svg, encoding="utf-8")
        print(f"wrote {target.relative_to(REPO_ROOT)} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
