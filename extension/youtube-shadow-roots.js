(() => {
    const originalAttachShadow = Element.prototype.attachShadow;
    if (window.__youtubeChatHookInstalled || originalAttachShadow.__youtubeChatCapture) return;

    const capturedRoots = window.__youtubeChatCapturedRoots || [];
    window.__youtubeChatCapturedRoots = capturedRoots;

    const captureAttachShadow = function (init) {
        const root = originalAttachShadow.call(this, init);
        if (init?.mode === "closed" && capturedRoots.length < 500) {
            capturedRoots.push(root);
        }
        return root;
    };

    Object.defineProperty(captureAttachShadow, "__youtubeChatCapture", { value: true });
    Element.prototype.attachShadow = captureAttachShadow;
    window.__youtubeChatHookInstalled = true;
})();
