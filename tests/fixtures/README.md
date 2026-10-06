# Cross-language parity fixtures

`svg_core.py` and `svg-core.js` implement the same algorithm twice. They drifted
once before (`int(64 ** (1/3))` is `3` in Python but `Math.cbrt(64)` is `4` in
JavaScript), producing different SVGs for identical inputs with nothing to catch
it. These fixtures exist so that can't happen again.

## How it works

`cases.json` describes each test case: image size, a named pixel pattern, and
the conversion settings. Both test suites build the pixels from the same
formulas — `tests/test_parity.py` (pytest) and `tests/parity.test.js`
(`node --test`) — run their own implementation, and assert the result equals the
golden `<name>.svg` in this directory **byte for byte**.

If either implementation changes behaviour, its suite fails. If only one of them
changes, only that one fails — which is exactly the drift signal that was
missing.

## Pixel patterns

Defined identically in both languages; all arithmetic stays well inside the
integer-safe range so there is nothing to round differently:

| Pattern   | Formula                                                                    |
|-----------|----------------------------------------------------------------------------|
| `gradient`| `r = (x*37 + y*17) % 256`, `g = (x*11 + y*53) % 256`, `b = (x*91 + y*7) % 256` |
| `checker` | `v = 255 if (x + y) % 2 == 0 else 0`, `r = g = b = v`                        |
| `gray`    | `v = (x*29 + y*13) % 256`, `r = g = b = v`                                   |
| `bands`   | `v = (y // 3) * 60 % 256`, `r = v`, `g = (x // 4) * 80 % 256`, `b = 128`     |
| `alpha`   | `r = (x*37) % 256`, `g = (y*53) % 256`, `b = (x*y*7) % 256`, **`a = ((x + y)*41) % 256`** |

`alpha` is the only RGBA pattern; it covers fully transparent, partly
transparent and opaque pixels.

Step 0 of the algorithm — compositing transparency onto white and the integer
luma filter for `bw` / `grayscale` — lives inside both cores, so the fixtures
cover it too: there are `bw` and `grayscale` cases fed with colour (`gradient`)
and transparent (`alpha`) pixels, and a test in each suite fails if those cases
are ever removed. What the fixtures do **not** cover is resizing: at a
processing scale other than 100% the browser's canvas and Pillow's LANCZOS
resample differently, so the two apps can differ there.

## Regenerating

Only when the algorithm changes **on purpose**:

```bash
python tests/fixtures/generate_golden.py
```

Then run both suites. If `node --test tests/parity.test.js` still passes, the two ports agree.
If it fails, the JavaScript port has not been updated to match.
