const express = require("express");
const cors = require("cors");
const axios = require("axios");
require("dotenv").config();

const app = express();

app.use(cors());
app.use(express.json());


app.get("/", (req, res) => {

    res.json({
        message: "YouTube Chat Node API is running"
    });

});


app.post("/api/chat", async (req, res) => {

    try {

        const { videoId, question } = req.body;

        if (!videoId || !question) {

            return res.status(400).json({
                error: "videoId and question are required"
            });

        }

        const response = await axios.post(
            "http://127.0.0.1:8000/chat",
            {
                video_id: videoId,
                question: question
            }
        );

        res.json({
            answer: response.data.answer
        });

    } catch (error) {

        console.error(error.message);

        res.status(500).json({
            error: "Failed to get answer"
        });

    }

});


app.listen(3000, () => {

    console.log(
        "Node server running on http://localhost:3000"
    );

});