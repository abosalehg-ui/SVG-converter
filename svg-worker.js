/**
 * svg-worker.js
 *
 * Web Worker that runs SVG conversion off the main thread so large images
 * don't freeze the browser UI.
 *
 * Protocol (postMessage):
 *   IN  -> { type: 'ping' }
 *   OUT -> { type: 'pong' }
 *   IN  -> { type: 'convert', payload: { imageData, settings } }
 *          settings = { conversionType, colorLevels, detailLevel }
 *   OUT -> { type: 'progress', progress: 0..100, label: string }
 *   OUT -> { type: 'done', svg: string }
 *   OUT -> { type: 'error', message: string }
 *
 * The caller pings first and only transfers `imageData.data.buffer` once this
 * worker has answered — a transferred buffer is detached, so discovering a dead
 * worker afterwards would leave nothing to retry or fall back with.
 */

importScripts("svg-core.js");

self.addEventListener("message", function (event) {
    const msg = event.data || {};

    if (msg.type === "ping") {
        self.postMessage({ type: "pong" });
        return;
    }

    if (msg.type !== "convert") {
        return;
    }

    try {
        const { imageData, settings } = msg.payload;
        const { conversionType, colorLevels, detailLevel } = settings;

        self.postMessage({ type: "progress", progress: 30, label: "جاري معالجة الألوان..." });
        self.SvgCore.applyGrayscaleFilter(imageData.data, conversionType);

        self.postMessage({ type: "progress", progress: 50, label: "جاري إنشاء SVG..." });
        const svg = self.SvgCore.createSVG(
            imageData.data,
            imageData.width,
            imageData.height,
            colorLevels,
            detailLevel,
            conversionType
        );

        self.postMessage({ type: "progress", progress: 90, label: "تم!" });
        self.postMessage({ type: "done", svg: svg });
    } catch (err) {
        self.postMessage({ type: "error", message: (err && err.message) || String(err) });
    }
});
