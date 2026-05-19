/**
 * svg-worker.js
 *
 * Web Worker that runs SVG conversion off the main thread so large images
 * don't freeze the browser UI.
 *
 * Protocol (postMessage):
 *   IN  -> { type: 'convert', payload: { imageData: ImageData, numColors, detailLevel, conversionType } }
 *   OUT -> { type: 'progress', progress: 0..100, label: string }
 *   OUT -> { type: 'done', svg: string }
 *   OUT -> { type: 'error', message: string }
 *
 * The `imageData.data` buffer is transferred (zero-copy) when supported.
 */

importScripts("svg-core.js");

self.addEventListener("message", function (event) {
    const msg = event.data || {};
    if (msg.type !== "convert") {
        return;
    }

    try {
        const { imageData, numColors, detailLevel, conversionType } = msg.payload;
        const data = imageData.data;
        const width = imageData.width;
        const height = imageData.height;

        post({ type: "progress", progress: 30, label: "جاري معالجة الألوان..." });
        self.SvgCore.applyGrayscaleFilter(data, conversionType);

        post({ type: "progress", progress: 50, label: "جاري إنشاء SVG..." });
        const svg = self.SvgCore.createSVG(
            data,
            width,
            height,
            numColors,
            detailLevel,
            conversionType
        );

        post({ type: "progress", progress: 100, label: "تم!" });
        post({ type: "done", svg: svg });
    } catch (err) {
        post({ type: "error", message: (err && err.message) || String(err) });
    }
});

function post(message) {
    self.postMessage(message);
}
