/**
 * potrace-adapter.js
 *
 * Optional integration with a Potrace JavaScript library for high-quality
 * black-and-white tracing (Bezier curves instead of axis-aligned rectangles).
 *
 * Usage:
 *   Include a Potrace JS library before this file (e.g., kilobtye/potrace),
 *   which should expose a global `Potrace`. This adapter then exposes:
 *
 *     PotraceAdapter.isAvailable() -> boolean
 *     PotraceAdapter.traceBW(imageData, options) -> Promise<string>
 *
 *   If no Potrace global is found, isAvailable() returns false and callers
 *   should fall back to SvgCore.createSVG.
 *
 * To install Potrace:
 *   - Vendor `https://cdn.jsdelivr.net/npm/potrace@2.1.8/index.js` into ./vendor/
 *   - Or add: <script src="vendor/potrace.js"></script> before this file
 */
(function (root) {
    "use strict";

    function isAvailable() {
        return typeof root.Potrace !== "undefined" && typeof root.Potrace.trace === "function";
    }

    function traceBW(imageData, options) {
        if (!isAvailable()) {
            return Promise.reject(new Error("POTRACE_NOT_AVAILABLE"));
        }
        const opts = Object.assign(
            {
                threshold: 128,
                turdSize: 2,
                alphaMax: 1.0,
                color: "rgb(0,0,0)",
                background: "transparent",
            },
            options || {}
        );

        return new Promise((resolve, reject) => {
            try {
                // potrace.js callback API: trace(buffer, opts, cb(err, svg))
                root.Potrace.trace(imageData, opts, function (err, svg) {
                    if (err) reject(err);
                    else resolve(svg);
                });
            } catch (err) {
                reject(err);
            }
        });
    }

    root.PotraceAdapter = {
        isAvailable: isAvailable,
        traceBW: traceBW,
    };
})(typeof self !== "undefined" ? self : globalThis);
