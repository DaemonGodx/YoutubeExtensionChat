let videoId = null;
let activeTabId = null;
let transcriptPromise = null;
const API_BASE_URL = "https://youtube-chat-api-siqa.onrender.com";


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
                    const playerResponse = window.ytInitialPlayerResponse;
                    if (!playerResponse) {
                        return { error: "YouTube has not loaded the video details yet. Refresh the video page and try again." };
                    }

                    const tracks =
                        playerResponse
                            ?.captions
                            ?.playerCaptionsTracklistRenderer
                            ?.captionTracks;

                    if (!tracks?.length) {
                        return { error: "This video does not expose captions. Check that captions are available in YouTube, then retry." };
                    }

                    const track =
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

                    return { body: await response.text() };
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
            throw new Error(result?.result?.error || "Could not read captions from this video.");
        }

        let lines = [];
        try {
            const captions = JSON.parse(body);
            lines = (captions.events || [])
                .flatMap((event) => event.segs || [])
                .map((segment) => segment.utf8?.trim())
                .filter(Boolean);
        } catch {
            const doc = new DOMParser().parseFromString(body, "text/xml");
            lines = Array.from(doc.querySelectorAll("text, p"))
                .map((element) => element.textContent?.trim())
                .filter(Boolean);
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


async function askQuestion() {

    const input =
        document.getElementById("question");

    const question = input.value.trim();

    if (!question || !videoId) {
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

getCurrentVideo();
