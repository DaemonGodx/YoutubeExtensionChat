from fastapi import FastAPI
from pydantic import BaseModel

from .main import ask_question


app = FastAPI()


class ChatRequest(BaseModel):

    video_id: str
    question: str
    transcript: str | None = None


@app.get("/")
def root():

    return {
        "message": "YouTube RAG API is running"
    }


@app.post("/chat")
def chat(request: ChatRequest):

    answer = ask_question(
        request.video_id,
        request.question,
        request.transcript
    )

    return {
        "answer": answer
    }
