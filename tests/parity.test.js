/**
 * Golden-fixture parity tests for the JavaScript implementation.
 *
 * `tests/test_parity.py` asserts the Python implementation against the very
 * same golden files. If the two ports ever drift again, one suite goes red
 * while the other stays green — the signal that was missing when
 * `Math.cbrt(64) === 4` silently disagreed with `int(64 ** (1/3)) == 3`.
 *
 * See `tests/fixtures/README.md`.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const SvgCore = require("../svg-core.js");

const FIXTURES_DIR = path.join(__dirname, "fixtures");
const CASES = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, "cases.json"), "utf8"));

/**
 * Mirrors `tests/patterns.py` exactly. See `tests/fixtures/README.md`.
 */
function pixel(pattern, x, y) {
    if (pattern === "gradient") {
        return [(x * 37 + y * 17) % 256, (x * 11 + y * 53) % 256, (x * 91 + y * 7) % 256];
    }
    if (pattern === "checker") {
        const value = (x + y) % 2 === 0 ? 255 : 0;
        return [value, value, value];
    }
    if (pattern === "gray") {
        const value = (x * 29 + y * 13) % 256;
        return [value, value, value];
    }
    if (pattern === "bands") {
        return [(Math.floor(y / 3) * 60) % 256, (Math.floor(x / 4) * 80) % 256, 128];
    }
    throw new Error("unknown pattern: " + pattern);
}

function buildImageData(pattern, width, height) {
    const data = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const [r, g, b] = pixel(pattern, x, y);
            const idx = (y * width + x) * 4;
            data[idx] = r;
            data[idx + 1] = g;
            data[idx + 2] = b;
            data[idx + 3] = 255;
        }
    }
    return data;
}

function render(testCase) {
    const data = buildImageData(testCase.pattern, testCase.width, testCase.height);
    return SvgCore.createSVG(
        data,
        testCase.width,
        testCase.height,
        testCase.colorLevels,
        testCase.detailLevel,
        testCase.conversionType
    );
}

for (const testCase of CASES) {
    test(`matches golden fixture: ${testCase.name}`, () => {
        const golden = fs.readFileSync(
            path.join(FIXTURES_DIR, `${testCase.name}.svg`),
            "utf8"
        );
        assert.equal(
            render(testCase),
            golden,
            `${testCase.name} drifted from its golden fixture. The Python port ` +
            `owns the algorithm — reconcile svg-core.js with svg_core.py.`
        );
    });
}

test("fixtures cover every conversion type", () => {
    const covered = new Set(CASES.map((c) => c.conversionType));
    assert.deepEqual([...covered].sort(), [...SvgCore.VALID_CONVERSION_TYPES].sort());
});

test("fixtures cover the color level range", () => {
    const levels = new Set(CASES.map((c) => c.colorLevels));
    assert.ok(levels.has(SvgCore.MIN_COLOR_LEVELS));
    assert.ok(levels.has(SvgCore.MAX_COLOR_LEVELS));
});

test("fixtures cover the detail level range", () => {
    const details = new Set(CASES.map((c) => c.detailLevel));
    assert.ok(details.has(SvgCore.MIN_DETAIL_LEVEL));
    assert.ok(details.has(SvgCore.MAX_DETAIL_LEVEL));
});
