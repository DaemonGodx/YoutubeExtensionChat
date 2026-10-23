let videoId = null;
let activeTabId = null;
let transcriptPromise = null;
const API_BASE_URL = "https://youtube-chat-api-siqa.onrender.com";
const YOUTUBE_ORIGIN = "https://www.youtube.com/*";
const TRANSCRIPT_SCRIPT_ID = "youtube-chat-transcript-capture";


async function ensureTranscriptAccess(permissionStatus) {
    const granted = await permissionStatus;
    if (!granted) {
        throw new Error("Allow YouTube site access to read this video's transcript, then try again.");
    }

    const registered = await chrome.scripting.getRegisteredContentScripts({
        ids: [TRANSCRIPT_SCRIPT_ID]
    });
    if (!registered.length) {
        await chrome.scripting.registerContentScripts([{
            id: TRANSCRIPT_SCRIPT_ID,
            matches: ["https://www.youtube.com/*"],
            js: ["youtube-shadow-roots.js"],
            runAt: "document_start",
            world: "MAIN",
            persistAcrossSessions: false
        }]);
    }

    const [hookState] = await chrome.scripting.executeScript({
        target: { tabId: activeTabId },
        world: "MAIN",
        func: () => window.__youtubeChatHookInstalled === true
    });

    // The hook must run before YouTube creates its closed transcript roots.
    return hookState?.result === true;
}


function getVideoId(url) {

    const urlObject = new URL(url);

    return urlObject.searchParams.get("v");

}


async function getCurrentVideo() {

    const tabs = await chrome.tabs.query({
        active: true,
        currentWindow: true
    });

    const url = tabs[0].url;

    if (!url || !url.includes("youtube.com/watch")) {

        document.getElementById("video").innerText =
            "Open a YouTube video first.";

        return;

    }

    videoId = getVideoId(url);
    activeTabId = tabs[0].id;

    document.getElementById("video").innerText =
        `Video: ${videoId}`;

}


async function getTranscript() {

    if (transcriptPromise) {
        return transcriptPromise;
    }

    transcriptPromise = (async () => {
        const [result] = await chrome.scripting.executeScript({
            target: { tabId: activeTabId },
            world: "MAIN",
            func: async () => {
                try {
                    const getOpenRoots = (start = document) => {
                        const roots = [start];
                        if (start === document && Array.isArray(window.__youtubeChatCapturedRoots)) {
                            roots.push(...window.__youtubeChatCapturedRoots);
                        }
                        for (let index = 0; index < roots.length; index += 1) {
                            const root = roots[index];
                            const documentForRoot = root.nodeType === Node.DOCUMENT_NODE
                                ? root
                                : root.ownerDocument;
                            const walker = documentForRoot.createTreeWalker(
                                root,
                                NodeFilter.SHOW_ELEMENT
                            );
                            let element = walker.nextNode();
                            while (element) {
                                if (element.shadowRoot) roots.push(element.shadowRoot);
                                element = walker.nextNode();
                            }
                        }
                        return roots;
                    };

                    const readTranscriptPanel = () => {
                        const roots = getOpenRoots();
                        const segmentHosts = roots.flatMap((root) =>
                            Array.from(root.querySelectorAll("ytd-transcript-segment-renderer"))
                        );

                        if (segmentHosts.length) {
                            return segmentHosts
                                .map((host) => {
                                    const segmentRoots = getOpenRoots(host);
                                    const textElement = segmentRoots
                                        .flatMap((root) => Array.from(root.querySelectorAll(".segment-text")))[0];
                                    return textElement?.innerText?.trim() || textElement?.textContent?.trim();
                                })
                                .filter(Boolean);
                        }

                        return roots
                            .flatMap((root) => Array.from(root.querySelectorAll(".segment-text")))
                            .map((element) => element.innerText?.trim() || element.textContent?.trim())
                            .filter(Boolean);
                    };

                    // Prefer the transcript YouTube has already rendered. This also works
                    // when the player response currently belongs to a pre-roll ad.
                    let lines = readTranscriptPanel();
                    if (!lines.length) {
                        const transcriptButton = getOpenRoots()
                            .flatMap((root) => Array.from(root.querySelectorAll("button")))
                            .find((button) => /show transcript/i.test(button.innerText || button.getAttribute("aria-label") || ""));
                        transcriptButton?.click();

                        // YouTube loads transcript segments asynchronously after opening the panel.
                        const deadline = Date.now() + 8000;
                        while (!lines.length && Date.now() < deadline) {
                            await new Promise((resolve) => setTimeout(resolve, 200));
                            lines = readTranscriptPanel();
                        }
                    }

                    if (lines.length) {
                        return { body: lines.join(" ") };
                    }

                    const player = document.getElementById("movie_player");
                    const playerResponse = player?.getPlayerResponse?.() || window.ytInitialPlayerResponse;

                    const tracks =
                        playerResponse
                            ?.captions
                            ?.playerCaptionsTracklistRenderer
                            ?.captionTracks;

                    if (!tracks?.length) {
                        return { error: "No captions were available from YouTube. Open the video's Transcript panel and try again." };
                    }

                    const track =
                        tracks.find((item) => item.languageCode === "en" && item.kind === "asr") ||
                        tracks.find((item) => item.languageCode === "en") ||
                        tracks[0];
                    const captionsUrl = new URL(track.baseUrl);
                    captionsUrl.searchParams.set("fmt", "json3");

                    const response = await fetch(captionsUrl.toString(), {
                        credentials: "include"
                    });

                    if (!response.ok) {
                        return { error: `YouTube captions returned HTTP ${response.status}.` };
                    }

                    const captionBody = await response.text();
                    if (!captionBody) {
                        return {
                            error: "YouTube returned an empty caption track. Open the video's Transcript panel and try again."
                        };
                    }
                    return { body: captionBody };
                } catch (error) {
                    return { error: error?.message || "YouTube caption extraction failed." };
                }
            }
        });

        if (result?.result?.error) {
            throw new Error(result.result.error);
        }

        const body = result?.result?.body;
        if (typeof body !== "string" || !body) {
            throw new Error(
                result?.result?.error ||
                "YouTube returned an empty caption response. Try reopening the video and transcript, then retry."
            );
        }

        let lines = [];
        try {
            const captions = JSON.parse(body);
            lines = (captions.events || [])
                .flatMap((event) => event.segs || [])
                .map((segment) => segment.utf8?.trim())
                .filter(Boolean);
        } catch {
            // A rendered YouTube transcript is already plain text; otherwise parse
            // the XML caption response in the extension context (Trusted Types safe).
            if (!body.includes("<")) {
                lines = [body.trim()];
            } else {
                const doc = new DOMParser().parseFromString(body, "text/xml");
                lines = Array.from(doc.querySelectorAll("text, p"))
                    .map((element) => element.textContent?.trim())
                    .filter(Boolean);
            }
        }

        if (!lines.length) {
            throw new Error("YouTube returned an empty caption track for this video.");
        }

        return lines.join(" ");
    })().catch((error) => {
        transcriptPromise = null;
        throw error;
    });

    return transcriptPromise;
}


async function askQuestion({ automaticRetry = false } = {}) {

    const input =
        document.getElementById("question");

    const question = input.value.trim();

    if (!question || !videoId) {
        return;
    }

    try {
        // Start the permission request synchronously in the user click handler.
        // A retry after the one-time reload only checks the saved permission.
        const permissionStatus = automaticRetry
            ? chrome.permissions.contains({ origins: [YOUTUBE_ORIGIN] })
            : chrome.permissions.request({ origins: [YOUTUBE_ORIGIN] });
        const ready = await ensureTranscriptAccess(permissionStatus);
        if (!ready) {
            localStorage.setItem("youtube-chat-pending-question", question);
            addMessage("AI", "YouTube access is enabled. The video is reloading so I can read its transcript. Reopen the extension and I’ll retry your question.");
            window.setTimeout(() => chrome.tabs.reload(activeTabId), 700);
            return;
        }
    } catch (error) {
        addMessage("AI", error.message || "Could not enable YouTube transcript access.");
        return;
    }

    addMessage("You", question);

    input.value = "";

    addMessage("AI", "Thinking...");

    try {

        const transcript = await getTranscript();

        const response = await fetch(
            `${API_BASE_URL}/api/chat`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    videoId: videoId,
                    question: question,
                    transcript: transcript
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `Request failed (${response.status}).`);
        }

        removeLastMessage();
        addMessage("AI", data.answer);

    } catch (error) {

        removeLastMessage();

        addMessage(
            "AI",
            error.message || "Something went wrong."
        );

        console.error(error);

    }

}


function addMessage(sender, message) {

    const chat =
        document.getElementById("chat");

    const div =
        document.createElement("div");

    div.className = "message";

    div.innerHTML = `
        <strong>${sender}:</strong>
        <p>${message}</p>
    `;

    chat.appendChild(div);

    chat.scrollTop = chat.scrollHeight;

}


function removeLastMessage() {

    const chat =
        document.getElementById("chat");

    chat.removeChild(chat.lastElementChild);

}


document
    .getElementById("send")
    .addEventListener(
        "click",
        askQuestion
    );


document
    .getElementById("question")
    .addEventListener(
        "keydown",
        (event) => {

            if (event.key === "Enter") {
                askQuestion();
            }

        }
    );
document.querySelectorAll(".suggestion").forEach(button => {
    button.addEventListener("click", () => {
        document.getElementById("question").value =
            button.innerText;

        document.getElementById("question").focus();
    });
});

getCurrentVideo().then(() => {
    const pendingQuestion = localStorage.getItem("youtube-chat-pending-question");
    if (pendingQuestion) {
        localStorage.removeItem("youtube-chat-pending-question");
        document.getElementById("question").value = pendingQuestion;
        askQuestion({ automaticRetry: true });
    }
});
