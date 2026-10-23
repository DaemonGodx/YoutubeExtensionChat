const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const extensionConfig = require("../extension/config.js");
const { createApp, resolveRagApiUrl } = require("../server/server.js");

test("local extension mode resolves to the configured local Node API", () => {
    assert.equal(
        extensionConfig.resolveApiBaseUrl({
            mode: "local",
            apiBaseUrls: { local: "http://localhost:3000" }
        }),
        "http://localhost:3000"
    );
});

test("demo extension mode resolves to the existing Render Node API", () => {
    assert.equal(
        extensionConfig.resolveApiBaseUrl({
            mode: "demo",
            apiBaseUrls: { demo: "https://youtube-chat-api-siqa.onrender.com" }
        }),
        "https://youtube-chat-api-siqa.onrender.com"
    );
});

test("unsupported extension mode gives a clear configuration error", () => {
    assert.throws(
        () => extensionConfig.resolveApiBaseUrl({ mode: "staging", apiBaseUrls: {} }),
        /Invalid YouTube Chat mode.*local.*demo/
    );
});

test("missing selected API URL gives a clear configuration error", () => {
    assert.throws(
        () => extensionConfig.resolveApiBaseUrl({ mode: "local", apiBaseUrls: {} }),
        /Missing API base URL.*local/
    );
});

test("Node API forwards the existing chat schema to the configured local RAG URL", async (t) => {
    let forwardedRequest;
    const app = createApp({
        env: { RAG_API_URL: "http://localhost:8000/chat" },
        axiosClient: {
            async post(url, body) {
                forwardedRequest = { url, body };
                return { data: { answer: "A local answer" } };
            }
        }
    });
    const server = app.listen(0, "127.0.0.1");
    t.after(() => new Promise((resolve, reject) => {
        server.close((error) => error ? reject(error) : resolve());
    }));
    await new Promise((resolve) => server.once("listening", resolve));

    const response = await fetch(`http://127.0.0.1:${server.address().port}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ videoId: "video-123", question: "Summarize this" })
    });

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { answer: "A local answer" });
    assert.deepEqual(forwardedRequest, {
        url: "http://localhost:8000/chat",
        body: { video_id: "video-123", question: "Summarize this" }
    });
});

test("demo Render configuration retains its deployed RAG routing", () => {
    const renderConfig = fs.readFileSync(path.join(__dirname, "../render.yaml"), "utf8");
    assert.match(renderConfig, /value:\s*https:\/\/youtube-chat-rag\.onrender\.com\/chat/);
    assert.equal(
        resolveRagApiUrl({ RAG_API_URL: "https://youtube-chat-rag.onrender.com/chat" }),
        "https://youtube-chat-rag.onrender.com/chat"
    );
});

test("popup loads one central config and contains no duplicated backend URL", () => {
    const popupHtml = fs.readFileSync(path.join(__dirname, "../extension/popup.html"), "utf8");
    const popupJs = fs.readFileSync(path.join(__dirname, "../extension/popup.js"), "utf8");
    assert.match(popupHtml, /<script src="config\.js"><\/script>\s*<script src="popup\.js"><\/script>/);
    assert.match(popupJs, /YouTubeChatConfig\.resolveApiBaseUrl\(\)/);
    assert.doesNotMatch(popupJs, /youtube-chat-api-siqa\.onrender\.com|localhost:3000/);
});
