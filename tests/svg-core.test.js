/**
 * Unit tests for svg-core.js — runs with Node's built-in test runner.
 *   node --test tests/svg-core.test.js
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const SvgCore = require("../svg-core.js");

const {
    MIN_COLOR_LEVELS,
    MAX_COLOR_LEVELS,
    MIN_DETAIL_LEVEL,
    MAX_DETAIL_LEVEL,
    DEFAULT_COLOR_LEVELS,
} = SvgCore;

function makeImageData(w, h, colorAt) {
    const data = new Uint8ClampedArray(w * h * 4);
    for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
            const [r, g, b] = colorAt(x, y);
            const idx = (y * w + x) * 4;
            data[idx] = r;
            data[idx + 1] = g;
            data[idx + 2] = b;
            data[idx + 3] = 255;
        }
    }
    return { data, width: w, height: h };
}

function makeSolidImageData(w, h, r, g, b) {
    return makeImageData(w, h, () => [r, g, b]);
}

function render(img, colorLevels, detailLevel, conversionType) {
    return SvgCore.createSVG(
        img.data, img.width, img.height, colorLevels, detailLevel, conversionType
    );
}

// ---------- structure ----------

test("createSVG starts with XML declaration", () => {
    const img = makeSolidImageData(4, 4, 0, 0, 0);
    assert.ok(render(img, 3, 5, "color").startsWith('<?xml version="1.0" encoding="UTF-8"?>'));
});

test("createSVG ends with </svg>", () => {
    const img = makeSolidImageData(4, 4, 0, 0, 0);
    assert.ok(render(img, 3, 5, "color").trimEnd().endsWith("</svg>"));
});

test("createSVG includes viewBox matching dimensions", () => {
    const img = makeSolidImageData(7, 13, 255, 255, 255);
    const svg = render(img, 3, 5, "color");
    assert.ok(svg.includes('viewBox="0 0 7 13"'));
    assert.ok(svg.includes('width="7"'));
    assert.ok(svg.includes('height="13"'));
});

test("createSVG sets shape-rendering to avoid hairline seams", () => {
    const img = makeSolidImageData(4, 4, 0, 0, 0);
    assert.ok(render(img, 3, 5, "color").includes('shape-rendering="crispEdges"'));
});

// ---------- quantization ----------

test("quantizeChannel preserves black and white at every level count", () => {
    // Regression: the old `min(255, (v / step | 0) * step)` turned pure white
    // into mid-gray, darkening every converted image.
    for (let levels = MIN_COLOR_LEVELS; levels <= MAX_COLOR_LEVELS; levels++) {
        assert.equal(SvgCore.quantizeChannel(0, levels), 0, `levels=${levels}`);
        assert.equal(SvgCore.quantizeChannel(255, levels), 255, `levels=${levels}`);
    }
});

test("quantizeChannel is monotonic", () => {
    for (let levels = MIN_COLOR_LEVELS; levels <= MAX_COLOR_LEVELS; levels++) {
        let previous = -1;
        for (let v = 0; v <= 255; v++) {
            const q = SvgCore.quantizeChannel(v, levels);
            assert.ok(q >= previous, `levels=${levels} v=${v}`);
            previous = q;
        }
    }
});

test("quantizeChannel emits exactly colorLevels distinct values", () => {
    for (let levels = MIN_COLOR_LEVELS; levels <= MAX_COLOR_LEVELS; levels++) {
        const seen = new Set();
        for (let v = 0; v <= 255; v++) {
            seen.add(SvgCore.quantizeChannel(v, levels));
        }
        assert.equal(seen.size, levels);
    }
});

test("white image stays white", () => {
    const img = makeSolidImageData(4, 4, 255, 255, 255);
    assert.ok(render(img, 3, 5, "color").includes('fill="rgb(255,255,255)"'));
});

test("solid image produces a single color group", () => {
    const img = makeSolidImageData(4, 4, 0, 0, 0);
    const svg = render(img, 3, 5, "color");
    assert.equal((svg.match(/<g fill="/g) || []).length, 1);
    assert.ok(svg.includes('fill="rgb(0,0,0)"'));
});

test("BW mode skips quantization", () => {
    const img = makeImageData(4, 4, (x, y) => {
        const v = (x + y) % 2 === 0 ? 0 : 255;
        return [v, v, v];
    });
    const svg = render(img, 3, 10, "bw");
    assert.ok(svg.includes('fill="rgb(0,0,0)"'));
    assert.ok(svg.includes('fill="rgb(255,255,255)"'));
});

test("BW stays binary when blocks average mixed pixels", () => {
    // Regression: with blockSize > 1 a checkerboard averaged to mid-gray, so
    // "أبيض وأسود" quietly produced dozens of gray shades.
    const img = makeImageData(12, 12, (x, y) => {
        const v = (x + y) % 2 === 0 ? 255 : 0;
        return [v, v, v];
    });
    for (let detail = MIN_DETAIL_LEVEL; detail <= MAX_DETAIL_LEVEL; detail++) {
        const fills = new Set(render(img, 3, detail, "bw").match(/fill="rgb\([^)]+\)"/g) || []);
        for (const fill of fills) {
            assert.ok(
                fill === 'fill="rgb(0,0,0)"' || fill === 'fill="rgb(255,255,255)"',
                `detail=${detail} produced ${fill}`
            );
        }
    }
});

test("every colorLevels value yields a distinct palette size", () => {
    // Regression: the old cbrt(numColors) mapping collapsed the whole 2-64
    // slider onto a couple of effective palettes.
    const img = makeImageData(2, 64, (x, y) => {
        const v = (y * 4) % 256;
        return [v, v, v];
    });
    const sizes = [];
    for (let levels = MIN_COLOR_LEVELS; levels <= MAX_COLOR_LEVELS; levels++) {
        const svg = render(img, levels, 10, "color");
        sizes.push(new Set(svg.match(/fill="rgb\([^)]+\)"/g) || []).size);
    }
    assert.deepEqual([...sizes].sort((a, b) => a - b), sizes);
    assert.equal(new Set(sizes).size, sizes.length, `palette sizes: ${sizes}`);
});

// ---------- block size ----------

test("higher detail level produces more rectangles", () => {
    const img = makeImageData(10, 10, (x, y) => [(x * 40) % 256, (y * 40) % 256, 128]);
    const nFine = (render(img, 6, 10, "color").match(/<rect/g) || []).length;
    const nCoarse = (render(img, 6, 1, "color").match(/<rect/g) || []).length;
    assert.ok(nCoarse < nFine, `expected ${nCoarse} < ${nFine}`);
    assert.equal(nCoarse, 1);
});

// ---------- rectangle merging ----------

test("adjacent same-color rectangles merge horizontally", () => {
    const img = makeSolidImageData(10, 1, 50, 50, 50);
    const rects = render(img, 3, 10, "color").match(/<rect[^/]+\/>/g) || [];
    assert.equal(rects.length, 1);
    assert.ok(rects[0].includes('width="10"'));
});

test("stacked same-color rectangles merge vertically", () => {
    // Regression: merging used to be horizontal only, so a solid 8x8 area
    // emitted 8 stacked rectangles instead of 1.
    const img = makeSolidImageData(8, 8, 50, 50, 50);
    const rects = render(img, 3, 10, "color").match(/<rect[^/]+\/>/g) || [];
    assert.equal(rects.length, 1);
    assert.ok(rects[0].includes('width="8"'));
    assert.ok(rects[0].includes('height="8"'));
});

test("vertical merging respects color boundaries", () => {
    const img = makeImageData(4, 8, (x, y) => (y < 4 ? [0, 0, 0] : [255, 255, 255]));
    const rects = render(img, 3, 10, "bw").match(/<rect[^/]+\/>/g) || [];
    assert.equal(rects.length, 2);
});

test("merged rectangles cover the image with no gaps or overlaps", () => {
    const w = 13, h = 11;
    const img = makeImageData(w, h, (x, y) => [(x * 60) % 256, (y * 90) % 256, 64]);
    const svg = render(img, 3, 10, "color");
    const seen = new Set();
    let covered = 0;
    for (const m of svg.matchAll(
        /<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"\/>/g
    )) {
        const [, x, y, rw, rh] = m.map(Number);
        covered += rw * rh;
        for (let py = y; py < y + rh; py++) {
            for (let px = x; px < x + rw; px++) {
                assert.ok(!seen.has(`${px},${py}`), "rectangles overlap");
                seen.add(`${px},${py}`);
            }
        }
    }
    assert.equal(covered, w * h);
});

// ---------- validation ----------

test("createSVG rejects an unknown conversion type", () => {
    const img = makeSolidImageData(2, 2, 0, 0, 0);
    assert.throws(() => render(img, 3, 5, "sepia"), RangeError);
});

test("createSVG rejects out-of-range colorLevels", () => {
    const img = makeSolidImageData(2, 2, 0, 0, 0);
    for (const levels of [MIN_COLOR_LEVELS - 1, MAX_COLOR_LEVELS + 1, 0, -3, NaN]) {
        assert.throws(() => render(img, levels, 5, "color"), RangeError, `levels=${levels}`);
    }
});

test("createSVG rejects out-of-range detailLevel", () => {
    const img = makeSolidImageData(2, 2, 0, 0, 0);
    for (const detail of [MIN_DETAIL_LEVEL - 1, MAX_DETAIL_LEVEL + 1, 1000, NaN]) {
        assert.throws(() => render(img, 3, detail, "color"), RangeError, `detail=${detail}`);
    }
});

test("createSVG rejects an empty image", () => {
    assert.throws(
        () => SvgCore.createSVG(new Uint8ClampedArray(0), 0, 0, 3, 5, "color"),
        RangeError
    );
});

// ---------- step 0: transparency and luma ----------

test("grayValue uses integer BT.601 weights with half-up rounding", () => {
    assert.equal(SvgCore.grayValue(0, 0, 0), 0);
    assert.equal(SvgCore.grayValue(255, 255, 255), 255);
    // 0.299*200 + 0.587*50 + 0.114*100 = 100.55 -> 101
    assert.equal(SvgCore.grayValue(200, 50, 100), 101);
});

test("flattenChannel composites onto white", () => {
    assert.equal(SvgCore.flattenChannel(0, 0), 255, "fully transparent is white");
    assert.equal(SvgCore.flattenChannel(17, 255), 17, "opaque is untouched");
    assert.equal(SvgCore.flattenChannel(0, 128), 127);
});

test("transparent background becomes white, not black", () => {
    // Regression: a black logo on a transparent PNG came out as a solid
    // black square in BW mode because alpha was ignored.
    const img = makeImageData(8, 8, () => [0, 0, 0]);
    for (let y = 0; y < 8; y++) {
        for (let x = 0; x < 8; x++) {
            const inside = x >= 2 && x < 6 && y >= 2 && y < 6;
            img.data[(y * 8 + x) * 4 + 3] = inside ? 255 : 0;
        }
    }
    for (const mode of ["bw", "grayscale", "color"]) {
        const fills = new Set([...render(img, 3, 10, mode).matchAll(/fill="([^"]+)"/g)].map((m) => m[1]));
        assert.deepEqual([...fills].sort(), ["rgb(0,0,0)", "rgb(255,255,255)"], mode);
    }
});

test("bw and grayscale filter colour input themselves", () => {
    const img = makeSolidImageData(4, 4, 200, 50, 100); // luma 101
    assert.ok(render(img, 6, 10, "bw").includes('fill="rgb(0,0,0)"'));
    const gray = render(img, 6, 10, "grayscale").match(/fill="rgb\((\d+),(\d+),(\d+)\)"/);
    assert.equal(gray[1], gray[2]);
    assert.equal(gray[2], gray[3]);
});

test("createSVG never modifies the caller's pixels", () => {
    const img = makeSolidImageData(3, 3, 200, 50, 100);
    img.data[3] = 10;
    const before = Array.from(img.data);
    render(img, 3, 10, "bw");
    assert.deepEqual(Array.from(img.data), before);
});

// ---------- limits / progress ----------

test("blockCount matches the block grid", () => {
    assert.equal(SvgCore.blockCount(10, 10, 10), 100);
    assert.equal(SvgCore.blockCount(11, 10, 1), 2); // 10px blocks
});

test("createSVG refuses output above MAX_BLOCKS before touching pixels", () => {
    const side = Math.ceil(Math.sqrt(SvgCore.MAX_BLOCKS)) + 1;
    assert.throws(
        () => SvgCore.createSVG(new Uint8ClampedArray(4), side, side, 3, 10, "color"),
        (err) => err instanceof RangeError && err.code === "TOO_COMPLEX"
    );
});

test("onProgress reports monotonic fractions ending at 1", () => {
    const img = makeSolidImageData(30, 120, 10, 20, 30);
    const seen = [];
    SvgCore.createSVG(img.data, 30, 120, 3, 10, "color", {
        onProgress: (fraction) => seen.push(fraction),
    });
    assert.ok(seen.length > 2);
    assert.deepEqual(seen, [...seen].sort((x, y) => x - y));
    assert.equal(seen[0], 0);
    assert.equal(seen[seen.length - 1], 1);
});

// ---------- determinism / edge cases ----------

test("output is deterministic for same input", () => {
    const a = makeSolidImageData(6, 6, 200, 100, 50);
    const b = makeSolidImageData(6, 6, 200, 100, 50);
    assert.equal(render(a, DEFAULT_COLOR_LEVELS, 5, "color"),
                 render(b, DEFAULT_COLOR_LEVELS, 5, "color"));
});

test("1x1 image emits one rect", () => {
    const img = makeSolidImageData(1, 1, 123, 45, 67);
    assert.equal((render(img, 3, 5, "color").match(/<rect/g) || []).length, 1);
});

test("non-divisible dimensions do not overflow bounds", () => {
    const img = makeSolidImageData(7, 5, 255, 255, 255);
    const svg = render(img, 3, 8, "color"); // block=3
    const matches = [
        ...svg.matchAll(/<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"\/>/g),
    ];
    assert.ok(matches.length > 0);
    for (const m of matches) {
        const [, x, y, w, h] = m.map(Number);
        assert.ok(x + w <= 7, `rect ${x}+${w} > 7`);
        assert.ok(y + h <= 5, `rect ${y}+${h} > 5`);
    }
});

test("custom header comments replace the defaults", () => {
    const img = makeSolidImageData(2, 2, 0, 0, 0);
    const svg = SvgCore.createSVG(img.data, 2, 2, 3, 5, "color", {
        headerComments: ["hello"],
    });
    assert.ok(svg.includes("  <!-- hello -->"));
    assert.ok(!svg.includes("Generated by"));
});

test("default header names the tool only — the file belongs to the user", () => {
    const svg = render(makeSolidImageData(2, 2, 0, 0, 0), 3, 5, "color");
    assert.ok(svg.includes("<!-- Generated by محول SVG -->"));
    assert.ok(!svg.includes("All Rights Reserved"));
    assert.ok(!svg.includes("@"));
});
