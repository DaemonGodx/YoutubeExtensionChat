import logging
import os
import re

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import GenericProxyConfig
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError as RequestsHTTPError
from requests.exceptions import ProxyError, Timeout as RequestsTimeout

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
    """A transcript retrieval failure with a safe, non-secret diagnostic."""

    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def create_transcript_api():

    proxy_url = os.getenv("TRANSCRIPT_PROXY_URL")
    if proxy_url:
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=proxy_url,
                https_url=proxy_url,
            )
        )

    return YouTubeTranscriptApi()


def _proxy_authentication_failed(error):

    response = getattr(error, "response", None)
    if getattr(response, "status_code", None) == 407:
        return True

    # requests/urllib3 may expose a 407 only in nested exception text. Inspect it
    # for classification, but never log or return that text (it can contain the URL).
    try:
        message = str(error).lower()
    except Exception:
        return False
    return "407" in message and ("auth" in message or "proxy" in message)


def _raise_transcript_fetch_error(category, message):

    logger.warning("Transcript retrieval failed [%s]: %s", category, message)
    raise TranscriptFetchError(category, message) from None


# -----------------------------
# Get YouTube Transcript
# -----------------------------

def get_transcript(video_id):

    try:
        ytt_api = create_transcript_api()
        transcript_list = ytt_api.fetch(
            video_id,
            languages=["en"]
        )
    except IpBlocked:
        _raise_transcript_fetch_error(
            "youtube_ip_blocked",
            "YouTube blocked the configured outbound IP. The proxy IP may also be blocked."
        )
    except RequestBlocked:
        _raise_transcript_fetch_error(
            "youtube_request_blocked",
            "YouTube blocked the transcript request."
        )
    except RequestsHTTPError as error:
        if _proxy_authentication_failed(error):
            _raise_transcript_fetch_error(
                "proxy_authentication",
                "The configured transcript proxy rejected authentication. Check TRANSCRIPT_PROXY_URL in the service environment."
            )
        _raise_transcript_fetch_error(
            "transcript_http_error",
            "The transcript service returned an HTTP error."
        )
    except ProxyError as error:
        if _proxy_authentication_failed(error):
            _raise_transcript_fetch_error(
                "proxy_authentication",
                "The configured transcript proxy rejected authentication. Check TRANSCRIPT_PROXY_URL in the service environment."
            )
        _raise_transcript_fetch_error(
            "proxy_connection",
            "Could not connect through the configured transcript proxy. Check its URL and availability."
        )
    except (RequestsConnectionError, RequestsTimeout):
        if os.getenv("TRANSCRIPT_PROXY_URL"):
            _raise_transcript_fetch_error(
                "proxy_connection",
                "The transcript network connection failed. Check the configured proxy and network availability."
            )
        _raise_transcript_fetch_error(
            "transcript_connection",
            "The direct transcript network connection failed."
        )
    except TranscriptsDisabled:
        _raise_transcript_fetch_error(
            "captions_disabled",
            "Captions are disabled for this video."
        )
    except NoTranscriptFound:
        _raise_transcript_fetch_error(
            "transcript_missing",
            "No English transcript is available for this video."
        )
    except InvalidVideoId:
        _raise_transcript_fetch_error(
            "invalid_video_id",
            "The supplied YouTube video ID is invalid."
        )
    except VideoUnavailable:
        _raise_transcript_fetch_error(
            "video_unavailable",
            "The YouTube video is unavailable."
        )
    except Exception:
        _raise_transcript_fetch_error(
            "transcript_api_failure",
            "The transcript service returned an unexpected error."
        )

    transcript_list = transcript_list.to_raw_data()

    cleaned_transcript = []

    for chunk in transcript_list:

        text = chunk["text"]

        # Remove zero-width characters
        text = re.sub(
            r"[\u200b\u200c\u200d\ufeff]",
            "",
            text
        )

        # Normalize whitespace
        text = " ".join(text.split())

        cleaned_transcript.append({
            "text": text,
            "start": chunk["start"],
            "duration": chunk["duration"]
        })

    return cleaned_transcript


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
        transcript_list = get_transcript(video_id)
        transcript = " ".join(chunk["text"] for chunk in transcript_list)
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
