(function (root) {
    "use strict";

    // Chrome does not load .env files. Select local or demo here, then reload
    // the unpacked extension from chrome://extensions.
    const config = Object.freeze({
        mode: "local",
        apiBaseUrls: Object.freeze({
            local: "http://localhost:3000",
            demo: "https://youtube-chat-api-siqa.onrender.com"
        })
    });

    function resolveApiBaseUrl(selectedConfig = config) {
        const mode = typeof selectedConfig.mode === "string"
            ? selectedConfig.mode.trim().toLowerCase()
            : "";

        if (mode !== "local" && mode !== "demo") {
            throw new Error(
                `Invalid YouTube Chat mode "${selectedConfig.mode}". Set extension/config.js mode to "local" or "demo".`
            );
        }

        const baseUrl = selectedConfig.apiBaseUrls?.[mode];
        if (typeof baseUrl !== "string" || !baseUrl.trim()) {
            throw new Error(
                `Missing API base URL for YouTube Chat mode "${mode}" in extension/config.js.`
            );
        }

        let parsedUrl;
        try {
            parsedUrl = new URL(baseUrl);
        } catch {
            throw new Error(`Invalid API base URL for YouTube Chat mode "${mode}".`);
        }

        if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
            throw new Error(`API base URL for mode "${mode}" must use HTTP or HTTPS.`);
        }

        return baseUrl.trim().replace(/\/$/, "");
    }

    const publicConfig = Object.freeze({ resolveApiBaseUrl });
    root.YouTubeChatConfig = publicConfig;

    if (typeof module !== "undefined" && module.exports) {
        module.exports = { config, resolveApiBaseUrl };
    }
})(globalThis);
