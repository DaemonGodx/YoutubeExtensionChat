const express = require("express");
const cors = require("cors");
const axios = require("axios");
require("dotenv").config();

const app = express();
const ragHostport = process.env.RAG_API_HOSTPORT || "127.0.0.1:8000";
const ragApiUrl = process.env.RAG_API_URL || `http://${ragHostport}/chat`;

app.use(cors());
app.use(express.json({ limit: "5mb" }));


app.get("/", (req, res) => {

    res.json({
        message: "YouTube Chat Node API is running"
    });

});


app.post("/api/chat", async (req, res) => {

    try {

        const { videoId, question, transcript } = req.body;

        if (!videoId || !question) {

            return res.status(400).json({
                error: "videoId and question are required"
            });

        }

        const ragRequest = {
            video_id: videoId,
            question: question
        };
        if (typeof transcript === "string" && transcript.trim()) {
            ragRequest.transcript = transcript;
        }

        const response = await axios.post(
            ragApiUrl,
            ragRequest
        );

        res.json({
            answer: response.data.answer
        });

    } catch (error) {

        console.error("RAG request failed:", error.response?.data || error.message);

        res.status(500).json({
            error: error.response?.data?.detail || "Failed to get answer"
        });

    }

});


const port = process.env.PORT || 3000;

app.listen(port, "0.0.0.0", () => {

    console.log(
        `Node server running on port ${port}`
    );

});
