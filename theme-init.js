/**
 * theme-init.js
 *
 * Applies the stored theme before first paint so the page never flashes the
 * wrong colours. Kept in its own synchronous file rather than an inline
 * <script> so the page can ship a `script-src 'self'` CSP without
 * 'unsafe-inline'.
 *
 * Everything else theme-related lives in app.js.
 */
(function initTheme() {
    "use strict";
    try {
        const stored = localStorage.getItem("svg-converter-theme");
        if (stored === "dark" || stored === "light") {
            document.documentElement.setAttribute("data-theme", stored);
        }
    } catch (err) {
        // localStorage can throw in private mode or with cookies blocked;
        // falling through just means "follow the OS preference".
    }
})();
