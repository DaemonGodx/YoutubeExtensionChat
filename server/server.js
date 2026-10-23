const express = require("express");
const cors = require("cors");
const axios = require("axios");
const path = require("path");
require("dotenv").config({ path: path.resolve(__dirname, "../.env") });

function resolveRagApiUrl(env = process.env) {
    const configuredUrl = env.RAG_API_URL?.trim();
    if (configuredUrl) return configuredUrl;

    const ragHostport = env.RAG_API_HOSTPORT || "127.0.0.1:8000";
    return `http://${ragHostport}/chat`;
}

function createApp({ axiosClient = axios, env = process.env } = {}) {
    const app = express();
    const ragApiUrl = resolveRagApiUrl(env);

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

            const response = await axiosClient.post(
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


    return app;
}


const port = process.env.PORT || 3000;

if (require.main === module) {
    createApp().listen(port, "0.0.0.0", () => {

        console.log(
            `Node server running on port ${port}`
        );

    });
}

module.exports = { createApp, resolveRagApiUrl };
