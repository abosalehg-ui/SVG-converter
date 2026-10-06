/**
 * app.js — UI logic for the web converter.
 *
 * Extracted from index.html so it can be linted and diffed like normal code.
 * The conversion algorithm itself lives in svg-core.js (shared with the Web
 * Worker and the test suite); this file only wires it to the DOM.
 */
"use strict";

(function () {
    const THEME_KEY = "svg-converter-theme";

    /**
     * Guard rails against a single image exhausting the tab's memory.
     *
     * Canvases have hard limits (Chrome refuses areas above ~268MP and any
     * dimension above 65535) and `getImageData` allocates width*height*4 bytes
     * on top of the canvas itself. Without a check, a 6000x4000 photo at 200%
     * asked for a 384MB buffer and simply killed the tab.
     */
    const MAX_SOURCE_PIXELS = 40e6; // 40 megapixels
    const MAX_OUTPUT_PIXELS = 40e6;
    const MAX_OUTPUT_DIMENSION = 16384;

    /**
     * Output size follows the number of blocks, not the pixel count, so the
     * pixel limits above cannot stop a 12MP photo at full detail from building
     * a string bigger than V8 allows. svg-core enforces MAX_BLOCKS; this is the
     * message users see when they hit it.
     */
    const TOO_COMPLEX_MESSAGE =
        "❌ هذه الإعدادات تنتج ملفاً معقّداً جداً قد يوقف المتصفح. " +
        "خفّض دقة التفاصيل أو دقة المعالجة.";

    /** How long to wait for the worker to answer a readiness ping. */
    const WORKER_PING_TIMEOUT_MS = 3000;

    const DETAIL_LABELS = [
        "", "منخفض جداً", "منخفض", "منخفض", "متوسط-منخفض", "متوسط",
        "متوسط-عالي", "عالي", "عالي", "عالي جداً", "أقصى دقة",
    ];

    const $ = (id) => document.getElementById(id);

    const uploadArea = $("uploadArea");
    const fileInput = $("fileInput");
    const previewSection = $("previewSection");
    const originalPreview = $("originalPreview");
    const svgPreview = $("svgPreview");
    const svgMeta = $("svgMeta");
    const convertBtn = $("convertBtn");
    const downloadBtn = $("downloadBtn");
    const newImageBtn = $("newImageBtn");
    const cancelBtn = $("cancelBtn");
    const progressContainer = $("progressContainer");
    const progressBar = $("progressBar");
    const progressFill = $("progressFill");
    const progressText = $("progressText");
    const statusMessage = $("statusMessage");
    const fileInfo = $("fileInfo");
    const colorLevelsSlider = $("colorLevels");
    const colorsValue = $("colorsValue");
    const detailLevelSlider = $("detailLevel");
    const detailValue = $("detailValue");
    const colorsSetting = $("colorsSetting");
    const themeToggle = $("themeToggle");
    const themeIcon = $("themeIcon");

    let currentImage = null;
    let currentFileName = null;
    let currentSvg = null;
    let currentSvgSize = 0;
    let currentSvgSettingsKey = null;
    let sourceObjectUrl = null;
    let previewObjectUrl = null;

    // ------------------------------------------------------------- theme --

    function prefersDark() {
        return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    }

    function isDarkActive() {
        const explicit = document.documentElement.getAttribute("data-theme");
        return explicit === "dark" || (!explicit && prefersDark());
    }

    function updateThemeIcon() {
        themeIcon.textContent = isDarkActive() ? "☀️" : "🌙";
    }

    function toggleTheme() {
        const next = isDarkActive() ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        try {
            localStorage.setItem(THEME_KEY, next);
        } catch (err) {
            // Not persisting the choice is survivable; the toggle still works.
        }
        updateThemeIcon();
    }

    themeToggle.addEventListener("click", toggleTheme);
    if (window.matchMedia) {
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", updateThemeIcon);
    }
    updateThemeIcon();

    // ---------------------------------------------------------- messaging --

    /** An error carrying a message that is safe (and useful) to show a user. */
    function userError(message, cause) {
        const err = new Error(message);
        err.userMessage = message;
        err.cause = cause;
        return err;
    }

    /**
     * Never surface a raw exception string: they are English, technical, and
     * meaningless in an Arabic UI ("Failed to execute 'getImageData'...").
     */
    function describeError(error) {
        if (error && error.userMessage) {
            return error.userMessage;
        }
        if (error && error.code === "TOO_COMPLEX") {
            return TOO_COMPLEX_MESSAGE;
        }
        console.error("SVG converter:", error);
        return "تعذّر إكمال التحويل. جرّب صورة أصغر أو دقة معالجة أقل.";
    }

    function showStatus(message, type) {
        statusMessage.textContent = message;
        statusMessage.className = "status-message " + type;
    }

    function hideStatus() {
        statusMessage.textContent = "";
        statusMessage.className = "status-message";
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + " بايت";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " كيلوبايت";
        return (bytes / (1024 * 1024)).toFixed(1) + " ميجابايت";
    }

    // ------------------------------------------------------- object URLs --

    function releaseSourceUrl() {
        if (sourceObjectUrl) {
            URL.revokeObjectURL(sourceObjectUrl);
            sourceObjectUrl = null;
        }
    }

    function releasePreviewUrl() {
        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = null;
        }
    }

    // -------------------------------------------------------- file input --

    uploadArea.addEventListener("click", () => fileInput.click());

    uploadArea.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fileInput.click();
        }
    });

    uploadArea.addEventListener("dragover", (event) => {
        event.preventDefault();
        uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", () => {
        uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", (event) => {
        event.preventDefault();
        uploadArea.classList.remove("dragover");
        if (event.dataTransfer.files.length > 0) {
            handleFile(event.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (event) => {
        if (event.target.files.length > 0) {
            handleFile(event.target.files[0]);
        }
    });

    function handleFile(file) {
        // Swapping the image mid-conversion is how a result for one picture
        // used to end up saved under another picture's name.
        if (activeConversion) return;

        if (file.type === "image/svg+xml") {
            showStatus(
                "❌ هذا الملف بصيغة SVG أصلاً. اختر صورة نقطية (PNG، JPG، WebP، BMP، GIF).",
                "error"
            );
            return;
        }
        if (!file.type.startsWith("image/")) {
            showStatus("❌ يرجى اختيار ملف صورة صالح (PNG، JPG، WebP، BMP، GIF)", "error");
            return;
        }

        hideStatus();

        // Hold the new URL locally and only adopt it once the image decodes.
        // Revoking the previous one up front would blank a preview that is
        // still on screen when the new file turns out to be unreadable.
        const url = URL.createObjectURL(file);
        const img = new Image();

        img.onload = () => {
            if (!img.naturalWidth || !img.naturalHeight) {
                URL.revokeObjectURL(url);
                showStatus("❌ تعذّر تحديد أبعاد هذه الصورة.", "error");
                return;
            }
            // Decoding succeeded but the image may still be too big to process.
            if (img.naturalWidth * img.naturalHeight > MAX_SOURCE_PIXELS) {
                URL.revokeObjectURL(url);
                showStatus(
                    `❌ الصورة كبيرة جداً (${img.naturalWidth}×${img.naturalHeight}). ` +
                    `الحد الأقصى ${Math.round(MAX_SOURCE_PIXELS / 1e6)} ميجابكسل.`,
                    "error"
                );
                return;
            }
            releaseSourceUrl();
            sourceObjectUrl = url;
            currentImage = img;
            currentFileName = file.name;
            showPreview(img, file);
        };

        // Without these the app went silent on a corrupt or mislabelled file:
        // onload never fired and the user just saw a frozen page.
        img.onerror = () => {
            URL.revokeObjectURL(url);
            showStatus("❌ تعذّر قراءة هذه الصورة. قد يكون الملف تالفاً أو بصيغة غير مدعومة.", "error");
        };

        img.alt = "";
        img.src = url;
    }

    function showPreview(img, file) {
        uploadArea.hidden = true;
        previewSection.hidden = false;

        const previewImg = document.createElement("img");
        previewImg.src = img.src;
        // Without an alt, screen readers announced the entire blob/data URL.
        previewImg.alt = "معاينة الصورة الأصلية: " + file.name;
        originalPreview.replaceChildren(previewImg);

        clearResult();

        $("fileName").textContent = file.name;
        $("fileDimensions").textContent = `${img.naturalWidth} × ${img.naturalHeight}`;
        $("fileSize").textContent = formatFileSize(file.size);
        fileInfo.hidden = false;

        convertBtn.disabled = false;
    }

    /** Forget the converted result and put the placeholder back. */
    function clearResult() {
        currentSvg = null;
        currentSvgSize = 0;
        currentSvgSettingsKey = null;
        downloadBtn.disabled = true;
        releasePreviewUrl();
        svgMeta.textContent = "";
        svgPreview.classList.remove("stale");
        const placeholder = document.createElement("div");
        placeholder.className = "preview-placeholder";
        const icon = document.createElement("span");
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "✨";
        const text = document.createElement("p");
        text.textContent = 'اضغط "تحويل" للمعاينة';
        placeholder.append(icon, text);
        svgPreview.replaceChildren(placeholder);
    }

    newImageBtn.addEventListener("click", resetToUpload);

    function resetToUpload() {
        if (activeConversion) return;
        uploadArea.hidden = false;
        previewSection.hidden = true;
        fileInput.value = "";
        currentImage = null;
        currentFileName = null;
        fileInfo.hidden = true;
        // Drop the big bitmaps instead of leaving them parked in the DOM.
        originalPreview.replaceChildren();
        clearResult();
        releaseSourceUrl();
        hideStatus();
        uploadArea.focus();
    }

    // ----------------------------------------------------------- controls --

    function updateColorsLabel() {
        const levels = Number(colorLevelsSlider.value);
        colorsValue.textContent = `${levels} (${levels ** 3} لون)`;
    }

    function updateDetailLabel() {
        const level = Number(detailLevelSlider.value);
        detailValue.textContent = "";
        detailValue.append(DETAIL_LABELS[level] + " ");
        const number = document.createElement("span");
        number.setAttribute("dir", "ltr");
        number.textContent = `(${level})`;
        detailValue.append(number);
    }

    colorLevelsSlider.addEventListener("input", updateColorsLabel);
    detailLevelSlider.addEventListener("input", updateDetailLabel);
    updateColorsLabel();
    updateDetailLabel();

    document.querySelectorAll('input[name="conversionType"]').forEach((radio) => {
        radio.addEventListener("change", (event) => {
            // Colour levels do nothing in black & white mode.
            colorsSetting.hidden = event.target.value === "bw";
        });
    });

    function readSettings() {
        return {
            conversionType: document.querySelector('input[name="conversionType"]:checked').value,
            colorLevels: Number(colorLevelsSlider.value),
            detailLevel: Number(detailLevelSlider.value),
            outputScale: parseFloat(
                document.querySelector('input[name="outputScale"]:checked').value
            ),
        };
    }

    function settingsKey(settings) {
        // Colour levels are ignored in BW mode, so they must not mark it stale.
        const levels = settings.conversionType === "bw" ? 0 : settings.colorLevels;
        return [settings.conversionType, levels, settings.detailLevel, settings.outputScale].join("|");
    }

    /**
     * A preview left over from other settings used to look exactly like a
     * fresh one, so users downloaded a result they had already changed.
     */
    function refreshStaleState() {
        if (!currentSvg) return;
        const stale = settingsKey(readSettings()) !== currentSvgSettingsKey;
        svgPreview.classList.toggle("stale", stale);
        svgMeta.textContent = stale
            ? formatFileSize(currentSvgSize) + " · الإعدادات تغيّرت، أعد التحويل"
            : formatFileSize(currentSvgSize);
        svgMeta.classList.toggle("stale", stale);
        if (stale) hideStatus();
    }

    document.querySelector(".sidebar").addEventListener("input", refreshStaleState);
    document.querySelector(".sidebar").addEventListener("change", refreshStaleState);

    // ------------------------------------------------------------ worker --

    let svgWorker = null;
    let workerReady = null; // Promise<boolean>

    /**
     * Create the worker and wait for it to answer a ping.
     *
     * The old code posted the (transferred) image data straight at a worker it
     * had never heard from. If the worker script 404'd, the error arrived after
     * the buffer had already been detached, so neither retrying nor falling
     * back to the main thread was possible. Probing first keeps the real
     * payload intact until we know the worker is alive.
     */
    function ensureWorker() {
        if (workerReady) {
            return workerReady;
        }

        workerReady = new Promise((resolve) => {
            if (typeof Worker === "undefined") {
                resolve(false);
                return;
            }

            let worker;
            try {
                worker = new Worker("svg-worker.js");
            } catch (err) {
                // Thrown for file:// in Chrome, among others.
                console.warn("Worker unavailable, using the main thread:", err);
                resolve(false);
                return;
            }

            let settled = false;
            const finish = (ok) => {
                if (settled) return;
                settled = true;
                clearTimeout(timer);
                worker.removeEventListener("message", onMessage);
                worker.removeEventListener("error", onError);
                if (ok) {
                    svgWorker = worker;
                } else {
                    worker.terminate();
                }
                resolve(ok);
            };

            const onMessage = (event) => {
                if (event.data && event.data.type === "pong") finish(true);
            };
            const onError = (event) => {
                console.warn("Worker failed to start, using the main thread:", event.message);
                finish(false);
            };
            const timer = setTimeout(() => finish(false), WORKER_PING_TIMEOUT_MS);

            worker.addEventListener("message", onMessage);
            worker.addEventListener("error", onError);
            worker.postMessage({ type: "ping" });
        });

        return workerReady;
    }

    function discardWorker() {
        if (svgWorker) svgWorker.terminate();
        svgWorker = null;
        workerReady = null;
    }

    /**
     * Run one conversion in the worker. Replies are matched on `id`: two
     * conversions used to share listeners, so the first "done" resolved both
     * and the second image was shown (and saved) with the first one's result.
     */
    function runInWorker(conversion, imageData, settings, onProgress) {
        return new Promise((resolve, reject) => {
            const worker = svgWorker;

            const cleanup = () => {
                worker.removeEventListener("message", onMessage);
                worker.removeEventListener("error", onError);
                conversion.abort = null;
            };

            const onMessage = (event) => {
                const msg = event.data || {};
                if (msg.id !== conversion.id) return;
                if (msg.type === "progress") {
                    onProgress(msg.progress);
                } else if (msg.type === "done") {
                    cleanup();
                    resolve(msg.svg);
                } else if (msg.type === "error") {
                    cleanup();
                    reject(userError(describeError({ message: msg.message, code: msg.code })));
                }
            };

            const onError = (event) => {
                cleanup();
                // Force a fresh worker (and a fresh readiness probe) next time.
                discardWorker();
                reject(userError("تعطّل معالج التحويل. أعد المحاولة.", event.message));
            };

            conversion.abort = () => {
                cleanup();
                const err = new Error("cancelled");
                err.cancelled = true;
                reject(err);
            };

            worker.addEventListener("message", onMessage);
            worker.addEventListener("error", onError);
            // Transfer the buffer instead of structured-cloning a copy of it.
            worker.postMessage(
                { type: "convert", id: conversion.id, payload: { imageData, settings } },
                [imageData.data.buffer]
            );
        });
    }

    function runOnMainThread(imageData, settings) {
        return SvgCore.createSVG(
            imageData.data,
            imageData.width,
            imageData.height,
            settings.colorLevels,
            settings.detailLevel,
            settings.conversionType
        );
    }

    // -------------------------------------------------------- conversion --

    /** { id, abort } while a conversion runs, otherwise null. */
    let activeConversion = null;
    let conversionSeq = 0;

    convertBtn.addEventListener("click", convertImage);
    downloadBtn.addEventListener("click", downloadSvg);
    cancelBtn.addEventListener("click", cancelConversion);

    function setProgress(percent, label) {
        progressFill.style.width = percent + "%";
        progressBar.setAttribute("aria-valuenow", String(Math.round(percent)));
        if (label) progressText.textContent = label;
    }

    function setBusy(busy) {
        convertBtn.disabled = busy || !currentImage;
        newImageBtn.disabled = busy;
        downloadBtn.disabled = busy || !currentSvg;
        progressContainer.hidden = !busy;
        if (!busy) cancelBtn.hidden = true;
    }

    function captureImageData(image, settings) {
        const width = Math.max(1, Math.floor(image.naturalWidth * settings.outputScale));
        const height = Math.max(1, Math.floor(image.naturalHeight * settings.outputScale));

        if (width > MAX_OUTPUT_DIMENSION || height > MAX_OUTPUT_DIMENSION ||
            width * height > MAX_OUTPUT_PIXELS) {
            throw userError(
                `❌ الناتج المطلوب كبير جداً (${width}×${height}). ` +
                "اختر دقة معالجة أقل."
            );
        }
        // Checked before allocating anything: the core would refuse anyway,
        // but only after the canvas and pixel buffer had been built.
        if (SvgCore.blockCount(width, height, settings.detailLevel) > SvgCore.MAX_BLOCKS) {
            throw userError(TOO_COMPLEX_MESSAGE);
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        if (!ctx) {
            throw userError("❌ متصفحك لا يدعم Canvas المطلوب للتحويل.");
        }
        // Transparent pixels stay transparent here; svg-core composites them
        // onto white so a logo's background does not come out black.
        ctx.drawImage(image, 0, 0, width, height);

        try {
            return ctx.getImageData(0, 0, width, height);
        } catch (err) {
            throw userError("❌ تعذّر قراءة بيانات الصورة. جرّب دقة معالجة أقل.", err);
        }
    }

    async function convertImage() {
        if (!currentImage || activeConversion) return;

        const conversion = { id: ++conversionSeq, abort: null };
        activeConversion = conversion;
        const isCurrent = () => activeConversion === conversion;
        const settings = readSettings();
        const image = currentImage;

        setBusy(true);
        // A stale "تم التحويل بنجاح" next to a stale preview reads as if the
        // shown result matches the new settings.
        hideStatus();
        setProgress(5, "جاري تجهيز الصورة...");

        await sleep(50); // let the progress bar paint before the heavy work
        if (!isCurrent()) return;

        try {
            const imageData = captureImageData(image, settings);
            const useWorker = await ensureWorker();
            if (!isCurrent()) return;

            let svg;
            setProgress(10, "جاري إنشاء SVG...");
            if (useWorker) {
                // Only the worker can be stopped mid-way; a main-thread run
                // blocks the page, so offering "cancel" there would be a lie.
                cancelBtn.hidden = false;
                svg = await runInWorker(conversion, imageData, settings, (fraction) => {
                    if (isCurrent()) setProgress(10 + fraction * 80, "جاري إنشاء SVG...");
                });
            } else {
                svg = runOnMainThread(imageData, settings);
            }
            if (!isCurrent()) return;

            setProgress(95, "جاري عرض المعاينة...");
            showSvgPreview(svg, settings);
            setProgress(100, "تم!");
            await sleep(300);
            if (!isCurrent()) return;
            activeConversion = null;
            setBusy(false);
            showStatus("✅ تم التحويل بنجاح!", "success");
        } catch (error) {
            if (!isCurrent() || error.cancelled) return;
            activeConversion = null;
            setBusy(false);
            showStatus(describeError(error), "error");
        }
    }

    function cancelConversion() {
        const conversion = activeConversion;
        if (!conversion) return;
        activeConversion = null;
        // Terminating is the only way to stop a busy worker; the next
        // conversion probes a fresh one.
        discardWorker();
        if (conversion.abort) conversion.abort();
        setBusy(false);
        showStatus("تم إلغاء التحويل.", "info");
        convertBtn.focus();
    }

    /**
     * Render the result as an <img> pointing at a blob, not via innerHTML.
     *
     * innerHTML would inject the SVG into the live document, where event
     * handler attributes inside it can execute. As an image the browser
     * renders it inertly — scripts and handlers never run.
     */
    function showSvgPreview(svg, settings) {
        releasePreviewUrl();
        const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
        previewObjectUrl = URL.createObjectURL(blob);

        const img = document.createElement("img");
        img.src = previewObjectUrl;
        img.alt = "معاينة الناتج المتجهي";
        svgPreview.replaceChildren(img);

        currentSvg = svg;
        currentSvgSize = blob.size;
        currentSvgSettingsKey = settingsKey(settings);
        // The output size is the thing users actually need before downloading.
        refreshStaleState();
    }

    function svgFileName() {
        if (!currentFileName) return "converted.svg";
        const base = currentFileName.replace(/\.[^.]+$/, "");
        return (base || "converted") + ".svg";
    }

    function downloadSvg() {
        if (!currentSvg) return;

        const blob = new Blob([currentSvg], { type: "image/svg+xml;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = svgFileName();
        document.body.appendChild(link);
        link.click();
        link.remove();
        // Revoking synchronously can cancel the download in some browsers.
        setTimeout(() => URL.revokeObjectURL(url), 1000);

        showStatus("✅ تم تحميل الملف: " + link.download, "success");
    }

    function sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    // -------------------------------------------------------- shortcuts --

    document.addEventListener("keydown", (event) => {
        if (!(event.ctrlKey || event.metaKey) || event.altKey) return;

        const target = event.target;
        const tag = (target && target.tagName) || "";
        const isTyping =
            (tag === "INPUT" && target.type !== "range" && target.type !== "radio") ||
            tag === "TEXTAREA" ||
            (target && target.isContentEditable);
        if (isTyping) return;

        const key = event.key.toLowerCase();

        if (key === "o") {
            event.preventDefault();
            if (!activeConversion) fileInput.click();
        } else if (event.key === "Enter") {
            if (convertBtn.disabled) return;
            event.preventDefault();
            convertBtn.click();
        } else if (key === "s") {
            // Only hijack the browser's Save when there is actually something
            // of ours to save.
            if (downloadBtn.disabled) return;
            event.preventDefault();
            downloadBtn.click();
        } else if (key === "d") {
            event.preventDefault();
            toggleTheme();
        }
    });
})();
