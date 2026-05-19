/**
 * Unit tests for svg-core.js — runs with Node's built-in test runner.
 *   node --test tests/svg-core.test.js
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const SvgCore = require("../svg-core.js");

function makeSolidImageData(w, h, r, g, b) {
    const data = new Uint8ClampedArray(w * h * 4);
    for (let i = 0; i < w * h; i++) {
        data[i * 4] = r;
        data[i * 4 + 1] = g;
        data[i * 4 + 2] = b;
        data[i * 4 + 3] = 255;
    }
    return { data, width: w, height: h };
}

// ---------- structure ----------

test("createSVG starts with XML declaration", () => {
    const img = makeSolidImageData(4, 4, 0, 0, 0);
    const svg = SvgCore.createSVG(img.data, img.width, img.height, 16, 5, "color");
    assert.ok(svg.startsWith('<?xml version="1.0" encoding="UTF-8"?>'));
});

test("createSVG ends with </svg>", () => {
    const img = makeSolidImageData(4, 4, 0, 0, 0);
    const svg = SvgCore.createSVG(img.data, img.width, img.height, 16, 5, "color");
    assert.ok(svg.trimEnd().endsWith("</svg>"));
});

test("createSVG includes viewBox matching dimensions", () => {
    const img = makeSolidImageData(7, 13, 255, 255, 255);
    const svg = SvgCore.createSVG(img.data, img.width, img.height, 16, 5, "color");
    assert.ok(svg.includes('viewBox="0 0 7 13"'));
    assert.ok(svg.includes('width="7"'));
    assert.ok(svg.includes('height="13"'));
});

// ---------- color behavior ----------

test("solid image produces a single color group", () => {
    const img = makeSolidImageData(4, 4, 0, 0, 0);
    const svg = SvgCore.createSVG(img.data, img.width, img.height, 16, 5, "color");
    const groupCount = (svg.match(/<g fill="/g) || []).length;
    assert.equal(groupCount, 1);
    assert.ok(svg.includes('fill="rgb(0,0,0)"'));
});

test("BW mode skips quantization (no levels collapse)", () => {
    // checkerboard: every other pixel pure black / pure white
    const w = 4, h = 4;
    const data = new Uint8ClampedArray(w * h * 4);
    for (let i = 0; i < w * h; i++) {
        const v = (i + Math.floor(i / w)) % 2 === 0 ? 0 : 255;
        data[i * 4] = data[i * 4 + 1] = data[i * 4 + 2] = v;
        data[i * 4 + 3] = 255;
    }
    const svg = SvgCore.createSVG(data, w, h, 16, 10, "bw"); // block=1
    assert.ok(svg.includes('fill="rgb(0,0,0)"'));
    assert.ok(svg.includes('fill="rgb(255,255,255)"'));
});

// ---------- block size ----------

test("higher detail level produces more rectangles", () => {
    // Use a non-uniform image so the merge step can't collapse everything.
    const w = 10, h = 10;
    const data = new Uint8ClampedArray(w * h * 4);
    for (let i = 0; i < w * h; i++) {
        data[i * 4] = (i * 25) % 256;
        data[i * 4 + 1] = 100;
        data[i * 4 + 2] = 150;
        data[i * 4 + 3] = 255;
    }
    const svgFine = SvgCore.createSVG(data.slice(), w, h, 64, 10, "color");
    const svgCoarse = SvgCore.createSVG(data.slice(), w, h, 64, 1, "color");
    const nFine = (svgFine.match(/<rect/g) || []).length;
    const nCoarse = (svgCoarse.match(/<rect/g) || []).length;
    assert.ok(nCoarse < nFine, `expected ${nCoarse} < ${nFine}`);
    assert.equal(nCoarse, 1);
});

// ---------- horizontal merging ----------

test("adjacent same-color rectangles merge horizontally", () => {
    const img = makeSolidImageData(10, 1, 50, 50, 50);
    const svg = SvgCore.createSVG(img.data, img.width, img.height, 16, 10, "color");
    const rects = svg.match(/<rect[^/]+\/>/g) || [];
    assert.equal(rects.length, 1);
    assert.ok(rects[0].includes('width="10"'));
});

// ---------- determinism / regression ----------

test("output is deterministic for same input", () => {
    const a = makeSolidImageData(6, 6, 200, 100, 50);
    const b = makeSolidImageData(6, 6, 200, 100, 50);
    assert.equal(
        SvgCore.createSVG(a.data, a.width, a.height, 16, 5, "color"),
        SvgCore.createSVG(b.data, b.width, b.height, 16, 5, "color")
    );
});

// ---------- applyGrayscaleFilter ----------

test("applyGrayscaleFilter converts BW to extreme values", () => {
    const data = new Uint8ClampedArray([200, 50, 100, 255, 30, 30, 30, 255]);
    SvgCore.applyGrayscaleFilter(data, "bw");
    // Pixel 1: gray = 0.299*200 + 0.587*50 + 0.114*100 ≈ 100.65 -> below 128 -> 0
    assert.equal(data[0], 0);
    assert.equal(data[1], 0);
    assert.equal(data[2], 0);
});

test("applyGrayscaleFilter is no-op for color mode", () => {
    const data = new Uint8ClampedArray([200, 50, 100, 255]);
    const before = Array.from(data);
    SvgCore.applyGrayscaleFilter(data, "color");
    assert.deepEqual(Array.from(data), before);
});

// ---------- edge cases ----------

test("1x1 image emits one rect", () => {
    const img = makeSolidImageData(1, 1, 123, 45, 67);
    const svg = SvgCore.createSVG(img.data, 1, 1, 16, 5, "color");
    const rects = svg.match(/<rect/g) || [];
    assert.equal(rects.length, 1);
});

test("non-divisible dimensions do not overflow bounds", () => {
    const img = makeSolidImageData(7, 5, 255, 255, 255);
    const svg = SvgCore.createSVG(img.data, 7, 5, 16, 8, "color");  // block=3
    const matches = [...svg.matchAll(/<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"\/>/g)];
    assert.ok(matches.length > 0);
    for (const m of matches) {
        const [, x, y, w, h] = m.map(Number);
        assert.ok(x + w <= 7, `rect ${x}+${w} > 7`);
        assert.ok(y + h <= 5, `rect ${y}+${h} > 5`);
    }
});
