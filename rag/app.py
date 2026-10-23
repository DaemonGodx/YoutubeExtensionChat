from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .main import TranscriptFetchError, ask_question


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

    try:
        answer = ask_question(
            request.video_id,
            request.question,
            request.transcript
        )
    except TranscriptFetchError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from None

    return {
        "answer": answer
    }
