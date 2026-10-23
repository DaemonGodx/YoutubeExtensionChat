let videoId = null;
const API_BASE_URL = "https://youtube-chat-api.onrender.com";


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

    document.getElementById("video").innerText =
        `Video: ${videoId}`;

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

        const response = await fetch(
            `${API_BASE_URL}/api/chat`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    videoId: videoId,
                    question: question
                })
            }
        );

        const data = await response.json();

        removeLastMessage();

        addMessage("AI", data.answer);

    } catch (error) {

        removeLastMessage();

        addMessage(
            "AI",
            "Something went wrong."
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
