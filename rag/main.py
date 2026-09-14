import re

from youtube_transcript_api import YouTubeTranscriptApi

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_groq import ChatGroq

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import (
    RunnableParallel,
    RunnableLambda,
    RunnablePassthrough
)
from langchain_core.output_parsers import StrOutputParser


# -----------------------------
# Models
# -----------------------------

embedding = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2"
)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.5
)


# -----------------------------
# Cache
# -----------------------------

vector_store_cache = {}


# -----------------------------
# Get YouTube Transcript
# -----------------------------

def get_transcript(video_id):

    ytt_api = YouTubeTranscriptApi()

    transcript_list = ytt_api.fetch(
        video_id,
        languages=["en"]
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

def create_vector_store(video_id):

    # Check cache first
    if video_id in vector_store_cache:

        print(f"Using cached vector store for {video_id}")

        return vector_store_cache[video_id]


    print(f"Creating vector store for {video_id}")

    # Get transcript
    transcript_list = get_transcript(video_id)

    transcript = " ".join(
        chunk["text"]
        for chunk in transcript_list
    )


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
    vector_store_cache[video_id] = vector_store

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

def ask_question(video_id, question):

    vector_store = create_vector_store(
        video_id
    )

    chain = create_chain(
        vector_store
    )

    answer = chain.invoke(
        question
    )

    return answer