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
        console.error("SVG converter:", error);
        return "تعذّر إكمال التحويل. جرّب صورة أصغر أو مقياس إخراج أقل.";
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
            // Decoding succeeded but the image may still be too big to process.
            if (img.width * img.height > MAX_SOURCE_PIXELS) {
                URL.revokeObjectURL(url);
                showStatus(
                    `❌ الصورة كبيرة جداً (${img.width}×${img.height}). ` +
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

        resetSvgPreview();

        $("fileName").textContent = file.name;
        $("fileDimensions").textContent = `${img.width} × ${img.height}`;
        $("fileSize").textContent = formatFileSize(file.size);
        fileInfo.hidden = false;

        convertBtn.disabled = false;
        downloadBtn.disabled = true;
        currentSvg = null;
    }

    function resetSvgPreview() {
        releasePreviewUrl();
        svgMeta.textContent = "";
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
        uploadArea.hidden = false;
        previewSection.hidden = true;
        fileInput.value = "";
        currentImage = null;
        currentFileName = null;
        currentSvg = null;
        fileInfo.hidden = true;
        // Drop the big bitmaps instead of leaving them parked in the DOM.
        originalPreview.replaceChildren();
        resetSvgPreview();
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

    function selectedConversionType() {
        return document.querySelector('input[name="conversionType"]:checked').value;
    }

    function selectedOutputScale() {
        return parseFloat(document.querySelector('input[name="outputScale"]:checked').value);
    }

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

    function runInWorker(imageData, settings, onProgress) {
        return new Promise((resolve, reject) => {
            const worker = svgWorker;

            const cleanup = () => {
                worker.removeEventListener("message", onMessage);
                worker.removeEventListener("error", onError);
            };

            const onMessage = (event) => {
                const msg = event.data || {};
                if (msg.type === "progress") {
                    onProgress(msg.progress, msg.label);
                } else if (msg.type === "done") {
                    cleanup();
                    resolve(msg.svg);
                } else if (msg.type === "error") {
                    cleanup();
                    reject(userError(describeError({ message: msg.message })));
                }
            };

            const onError = (event) => {
                cleanup();
                // Force a fresh worker (and a fresh readiness probe) next time.
                svgWorker = null;
                workerReady = null;
                reject(userError("تعطّل معالج التحويل. أعد المحاولة.", event.message));
            };

            worker.addEventListener("message", onMessage);
            worker.addEventListener("error", onError);
            // Transfer the buffer instead of structured-cloning a copy of it.
            worker.postMessage(
                { type: "convert", payload: { imageData, settings } },
                [imageData.data.buffer]
            );
        });
    }

    function runOnMainThread(imageData, settings, onProgress) {
        onProgress(30, "جاري معالجة الألوان...");
        SvgCore.applyGrayscaleFilter(imageData.data, settings.conversionType);
        onProgress(50, "جاري إنشاء SVG...");
        const svg = SvgCore.createSVG(
            imageData.data,
            imageData.width,
            imageData.height,
            settings.colorLevels,
            settings.detailLevel,
            settings.conversionType
        );
        onProgress(100, "تم!");
        return svg;
    }

    // -------------------------------------------------------- conversion --

    convertBtn.addEventListener("click", convertImage);
    downloadBtn.addEventListener("click", downloadSvg);

    function setProgress(progress, label) {
        progressFill.style.width = progress + "%";
        progressBar.setAttribute("aria-valuenow", String(Math.round(progress)));
        if (label) progressText.textContent = label;
    }

    function captureImageData(settings) {
        const width = Math.max(1, Math.floor(currentImage.width * settings.outputScale));
        const height = Math.max(1, Math.floor(currentImage.height * settings.outputScale));

        if (width > MAX_OUTPUT_DIMENSION || height > MAX_OUTPUT_DIMENSION ||
            width * height > MAX_OUTPUT_PIXELS) {
            throw userError(
                `❌ الناتج المطلوب كبير جداً (${width}×${height}). ` +
                "اختر مقياس إخراج أصغر."
            );
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        if (!ctx) {
            throw userError("❌ متصفحك لا يدعم Canvas المطلوب للتحويل.");
        }
        ctx.drawImage(currentImage, 0, 0, width, height);

        try {
            return ctx.getImageData(0, 0, width, height);
        } catch (err) {
            throw userError("❌ تعذّر قراءة بيانات الصورة. جرّب مقياس إخراج أصغر.", err);
        }
    }

    async function convertImage() {
        if (!currentImage) return;

        const settings = {
            conversionType: selectedConversionType(),
            colorLevels: Number(colorLevelsSlider.value),
            detailLevel: Number(detailLevelSlider.value),
            outputScale: selectedOutputScale(),
        };

        convertBtn.disabled = true;
        downloadBtn.disabled = true;
        // A stale "تم التحويل بنجاح" next to a stale preview reads as if the
        // shown result matches the new settings.
        hideStatus();
        progressContainer.hidden = false;
        setProgress(10, "جاري تجهيز الصورة...");

        await sleep(50);

        try {
            const imageData = captureImageData(settings);

            const svg = (await ensureWorker())
                ? await runInWorker(imageData, settings, setProgress)
                : runOnMainThread(imageData, settings, setProgress);

            setProgress(95, "جاري عرض المعاينة...");
            currentSvg = svg;
            showSvgPreview(svg);

            setProgress(100, "تم!");
            await sleep(300);
            progressContainer.hidden = true;
            convertBtn.disabled = false;
            downloadBtn.disabled = false;
            showStatus("✅ تم التحويل بنجاح!", "success");
        } catch (error) {
            progressContainer.hidden = true;
            convertBtn.disabled = false;
            showStatus(describeError(error), "error");
        }
    }

    /**
     * Render the result as an <img> pointing at a blob, not via innerHTML.
     *
     * innerHTML would inject the SVG into the live document, where event
     * handler attributes inside it can execute. As an image the browser
     * renders it inertly — scripts and handlers never run.
     */
    function showSvgPreview(svg) {
        releasePreviewUrl();
        const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
        previewObjectUrl = URL.createObjectURL(blob);

        const img = document.createElement("img");
        img.src = previewObjectUrl;
        img.alt = "معاينة الناتج المتجهي";
        svgPreview.replaceChildren(img);

        // The output size is the thing users actually need before downloading.
        svgMeta.textContent = formatFileSize(blob.size);
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
            fileInput.click();
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
