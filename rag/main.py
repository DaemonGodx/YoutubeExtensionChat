import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import requests

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import (
    RunnableParallel,
    RunnableLambda,
    RunnablePassthrough
)
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import GoogleGenerativeAIEmbeddings

embedding = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
)


# -----------------------------
# Models
# -----------------------------

# embedding = HuggingFaceEndpointEmbeddings(
#     model="hotchpotch/bekko-static-embedding-v1"
# )

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.5
)
# llm=ChatGoogleGenerativeAI( 
#     model="gemini-3.8-flash",
#     temperature=1.0, )


# -----------------------------
# Cache
# -----------------------------

vector_store_cache = {}
logger = logging.getLogger(__name__)


class TranscriptFetchError(RuntimeError):
    """A transcript provider failure with a safe, user-facing diagnostic."""

    def __init__(self, category, message, status_code=502):
        super().__init__(message)
        self.category = category
        self.status_code = status_code


TRANSCRIPT_API_URL = "https://transcriptapi.com/api/v2/youtube/transcript"
TRANSCRIPT_API_TIMEOUT_SECONDS = 30


def _raise_transcript_fetch_error(category, message, status_code=502):
    # Only log the safe category; never include provider response bodies or headers.
    logger.warning("Transcript retrieval failed [%s]", category)
    raise TranscriptFetchError(category, message, status_code) from None


def _normalize_transcript(response_data):
    if not isinstance(response_data, dict):
        _raise_transcript_fetch_error(
            "transcript_invalid_response",
            "TranscriptAPI returned an invalid response. Please try again later.",
        )

    transcript = response_data.get("transcript")
    if isinstance(transcript, str):
        transcript_text = transcript
    elif isinstance(transcript, list):
        segments = []
        for segment in transcript:
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                _raise_transcript_fetch_error(
                    "transcript_invalid_response",
                    "TranscriptAPI returned malformed transcript segments.",
                )
            segments.append(segment["text"])
        transcript_text = " ".join(segments)
    else:
        _raise_transcript_fetch_error(
            "transcript_invalid_response",
            "TranscriptAPI did not return transcript text in a supported format.",
        )

    transcript_text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", transcript_text)
    transcript_text = " ".join(transcript_text.split())
    if not transcript_text:
        _raise_transcript_fetch_error(
            "transcript_empty",
            "The provider returned an empty transcript for this video.",
        )

    return transcript_text


# -----------------------------
# Get YouTube Transcript
# -----------------------------

def get_transcript(video_id):
    api_key = os.getenv("TRANSCRIPT_API_KEY", "").strip()
    if not api_key:
        _raise_transcript_fetch_error(
            "transcript_api_not_configured",
            "Transcript retrieval is not configured. Set TRANSCRIPT_API_KEY in the Python service environment.",
            status_code=500,
        )

    try:
        response = requests.get(
            TRANSCRIPT_API_URL,
            params={"video_url": video_id, "format": "json"},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TRANSCRIPT_API_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        _raise_transcript_fetch_error(
            "transcript_provider_timeout",
            "TranscriptAPI took too long to respond. Please retry in a few seconds.",
        )
    except requests.ConnectionError:
        _raise_transcript_fetch_error(
            "transcript_provider_connection",
            "Could not connect to TranscriptAPI. Please try again later.",
        )
    except requests.RequestException:
        _raise_transcript_fetch_error(
            "transcript_provider_request",
            "The transcript provider request failed. Please try again later.",
        )

    status_errors = {
        401: ("transcript_api_auth", "TranscriptAPI rejected the API key. Check TRANSCRIPT_API_KEY."),
        402: ("transcript_api_credits", "TranscriptAPI requires payment or has no credits remaining."),
        404: ("transcript_unavailable", "No transcript is available for this video."),
        422: ("transcript_invalid_video", "TranscriptAPI rejected the supplied YouTube video ID or URL."),
        500: ("transcript_provider_failure", "TranscriptAPI encountered an error. Please try again later."),
    }
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "5")
        if not retry_after.isdigit():
            retry_after = "5"
        _raise_transcript_fetch_error(
            "transcript_api_rate_limited",
            f"TranscriptAPI is rate limiting requests. Please retry in {retry_after} seconds.",
        )
    if response.status_code == 408:
        _raise_transcript_fetch_error(
            "transcript_provider_timeout",
            "TranscriptAPI temporarily timed out. Please retry in a few seconds.",
        )
    if response.status_code != 200:
        category, message = status_errors.get(
            response.status_code,
            ("transcript_provider_failure", "TranscriptAPI returned an unexpected error. Please try again later."),
        )
        _raise_transcript_fetch_error(category, message)

    try:
        response_data = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        _raise_transcript_fetch_error(
            "transcript_invalid_json",
            "TranscriptAPI returned an invalid response. Please try again later.",
        )

    return _normalize_transcript(response_data)


# -----------------------------
# Create Vector Store
# -----------------------------

def create_vector_store(video_id, transcript_text=None):

    cache_key = f"{video_id}:{hash(transcript_text)}" if transcript_text is not None else video_id
    if cache_key in vector_store_cache:

        print(f"Using cached vector store for {video_id}")

        return vector_store_cache[cache_key]


    print(f"Creating vector store for {video_id}")

    if transcript_text is None:
        transcript = get_transcript(video_id)
    else:
        transcript = transcript_text


    # Split transcript
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.create_documents(
        [transcript]
    )


    # Create vector store
    vector_store = Chroma.from_documents(
        chunks,
        embedding
    )


    # Save to cache
    vector_store_cache[cache_key] = vector_store

    print(f"Vector store cached for {video_id}")

    return vector_store


# -----------------------------
# Create RAG Chain
# -----------------------------

def create_chain(vector_store):

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 3
        }
    )


    def format_docs(retrieved_docs):

        return "\n\n".join(
            doc.page_content
            for doc in retrieved_docs
        )


    parallel_chain = RunnableParallel({

        "context":
            retriever
            | RunnableLambda(format_docs),

        "question":
            RunnablePassthrough()

    })


    prompt = PromptTemplate(

        template="""
You are a helpful AI assistant inside a YouTube chat extension.

Answer the user's question using the provided transcript context.

IMPORTANT RULES:

1. For video-related questions, use only information supported by the transcript.
2. Do not invent facts that are not present in the transcript.
3. If the transcript does not contain enough information, say:
   "I don't know based on the transcript."
4. For questions asking for an opinion about the video, give an opinion based only on what can be inferred from the transcript.
5. Never claim that you personally watched the video.
6. Keep answers clear, natural, and easy to read.

FORMATTING:

- Use Markdown.
- Use a short heading when appropriate.
- Use bullet points for multiple pieces of information.
- Use **bold** to highlight important names, features, numbers, or conclusions.
- Use emojis sparingly when they improve readability.
- Avoid unnecessarily long paragraphs.
- Don't repeat the user's question.
- Don't add a "Conclusion" section unless it is useful.
- For simple questions, give a short direct answer instead of forcing a long format.

Transcript context:
{context}

User question:
{question}

Answer:
""",
        input_variables=[
            "context",
            "question"
        ]
    )


    chain = (
        parallel_chain
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain


# -----------------------------
# Ask Question
# -----------------------------

def ask_question(video_id, question, transcript_text=None):

    vector_store = create_vector_store(
        video_id,
        transcript_text
    )

    chain = create_chain(
        vector_store
    )

    answer = chain.invoke(
        question
    )

    return answer
