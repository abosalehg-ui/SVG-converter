/**
 * svg-worker.js
 *
 * Web Worker that runs SVG conversion off the main thread so large images
 * don't freeze the browser UI.
 *
 * Protocol (postMessage):
 *   IN  -> { type: 'ping' }
 *   OUT -> { type: 'pong' }
 *   IN  -> { type: 'convert', id, payload: { imageData, settings } }
 *          settings = { conversionType, colorLevels, detailLevel }
 *   OUT -> { type: 'progress', id, progress: 0..1 }
 *   OUT -> { type: 'done', id, svg: string }
 *   OUT -> { type: 'error', id, message: string, code?: string }
 *
 * Every reply echoes the request `id`, so the page can drop a reply that
 * belongs to a conversion it has since abandoned instead of mistaking it for
 * the current one.
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

    const id = msg.id;
    try {
        const { imageData, settings } = msg.payload;
        const svg = self.SvgCore.createSVG(
            imageData.data,
            imageData.width,
            imageData.height,
            settings.colorLevels,
            settings.detailLevel,
            settings.conversionType,
            {
                onProgress: function (fraction) {
                    self.postMessage({ type: "progress", id: id, progress: fraction });
                },
            }
        );
        self.postMessage({ type: "done", id: id, svg: svg });
    } catch (err) {
        self.postMessage({
            type: "error",
            id: id,
            message: (err && err.message) || String(err),
            code: err && err.code,
        });
    }
});
