# 🎥 YouTube RAG Chat

An AI-powered Chrome Extension that lets you **chat with YouTube videos** using Retrieval-Augmented Generation (RAG).

Ask questions about a video's transcript and get context-aware answers. The extension also supports normal conversations and can handle different transcript languages.

---

## ✨ Features

- 🎥 Chat with YouTube videos
- 🤖 AI-powered answers using RAG
- 🔎 Semantic search over video transcripts
- 🧠 Context-aware question answering
- 💬 General conversation support
- 🌐 Support for transcripts in multiple languages
- ⚡ Vector store caching for repeated questions
- 🧩 Chrome Extension interface
- 🔌 Node.js API gateway
- 🐍 Python/FastAPI RAG backend
- 📝 Markdown-formatted AI responses

---

## 🏗️ Architecture

```text
┌──────────────────────────────┐
│      Chrome Extension        │
│                              │
│  Popup UI + User Questions   │
└──────────────┬───────────────┘
               │ HTTP
               ▼
┌──────────────────────────────┐
│       Node.js / Express      │
│                              │
│       API Gateway            │
└──────────────┬───────────────┘
               │ HTTP
               ▼
┌──────────────────────────────┐
│       Python / FastAPI       │
│                              │
│          RAG System          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      YouTube Transcript      │
│                              │
│   Cleaning → Chunking        │
│          ↓                   │
│       Embeddings             │
│          ↓                   │
│         Chroma               │
│          ↓                   │
│       Retrieval              │
│          ↓                   │
│       Groq LLM               │
└──────────────────────────────┘
```

---

## 📂 Project Structure

```text
YoutubeChat/
│
├── rag/
│   ├── __init__.py
│   ├── app.py
│   └── main.py
│
├── node/
│   ├── server.js
│   
│   
│ 
│
├── extension/
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
│
├── .gitignore
└── README.md
```

> `.env`, virtual environments, `node_modules`, caches, and generated vector databases should not be committed to Git.

---

# 🧠 How RAG Works

When you ask a question about a YouTube video, the system follows these steps:

### 1. Get YouTube Transcript

The Python backend retrieves the transcript using `youtube-transcript-api`.

```text
YouTube Video
      ↓
Transcript
```

### 2. Clean the Transcript

Unnecessary Unicode characters and whitespace are cleaned.

```text
Raw Transcript
      ↓
Clean Transcript
```

### 3. Split Into Chunks

The transcript is divided into smaller chunks using:

```text
RecursiveCharacterTextSplitter
```

Current configuration:

```python
chunk_size = 1000
chunk_overlap = 200
```

### 4. Generate Embeddings

Each chunk is converted into a vector representation using a sentence-transformer embedding model.

```text
Transcript Chunks
      ↓
Embeddings
```

### 5. Store in Chroma

The embeddings are stored in a Chroma vector store.

```text
Embeddings
      ↓
Chroma Vector Store
```

### 6. Retrieve Relevant Context

When the user asks a question, the system searches for the most relevant transcript chunks.

```text
User Question
      ↓
Similarity Search
      ↓
Top 3 Relevant Chunks
```

### 7. Generate the Answer

The retrieved context is passed to the LLM together with the user's question.

```text
Question + Retrieved Context
            ↓
         Groq LLM
            ↓
       AI Response
```

---

# 🔀 Question Routing

The system can distinguish between **video-related questions** and **general conversation**.

```text
                User Question
                      │
                      ▼
                LLM Router
                 /       \
                /         \
           VIDEO           GENERAL
             │                │
             ▼                ▼
       RAG Pipeline       General LLM
             │                │
             └───────┬────────┘
                     ▼
                  Answer
```

### Video Question

Example:

```text
What are the main points discussed in this video?
```

The system retrieves relevant transcript context before generating the answer.

### General Question

Example:

```text
Hello
```

The question is handled directly by the general conversation chain without querying the transcript.

---

# 🛠️ Tech Stack

## Frontend

- HTML
- CSS
- JavaScript
- Chrome Extension Manifest V3

## Backend

- Node.js
- Express.js
- Axios
- CORS

## RAG Backend

- Python
- FastAPI
- LangChain
- Chroma
- Hugging Face Embeddings
- Groq
- YouTube Transcript API

---

# ⚙️ Installation

## Prerequisites

Make sure you have installed:

- Node.js
- Python 3.10+
- Git
- Google Chrome

---

## 1. Clone the Repository

```bash
git clone https://github.com/DaemonGodx/YoutubeExtensionChat.git
cd YoutubeExtensionChat
```

---

# 🐍 2. Setup Python Backend

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

---

# 🔐 3. Configure Environment Variables

Create:

```text
node/.env
```

Add your API credentials:

```env
GROQ_API_KEY=your_groq_api_key
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token
```

Never commit your `.env` file.

You can provide a safe example file such as:

```text
node/.env.example
```

```env
GROQ_API_KEY=
HUGGINGFACEHUB_API_TOKEN=
```

---

# 🚀 4. Start the Python RAG Server

From the project root:

```bash
uvicorn rag.app:app --reload --port 8000
```

The FastAPI server will run at:

```text
http://localhost:8000
```

You can test the API documentation at:

```text
http://localhost:8000/docs
```

---

# 🟢 5. Start the Node.js Server

Open another terminal:

```bash
cd node
```

Install dependencies:

```bash
npm install
```

Start the server:

```bash
node server.js
```

The Node.js API will run at:

```text
http://localhost:3000
```

---

# 🧩 6. Load the Chrome Extension

1. Open Google Chrome.
2. Go to:

```text
chrome://extensions
```

3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select the project's:

```text
extension/
```

folder.

The extension should now appear in your Chrome extensions list.

---

# 🔌 API

## POST `/api/chat`

The Chrome extension sends questions to the Node.js backend.

### Request

```json
{
  "videoId": "VIDEO_ID",
  "question": "What is this video about?"
}
```

### Node.js → Python

The Node.js server forwards the request to:

```text
POST http://localhost:8000/chat
```

using:

```json
{
  "video_id": "VIDEO_ID",
  "question": "What is this video about?"
}
```

### Response

```json
{
  "answer": "The video discusses..."
}
```

---

# 🎯 Example

Open a YouTube video and click the extension.

Ask:

```text
What are the main points of this video?
```

The system:

```text
YouTube Video
      ↓
Transcript
      ↓
Text Chunks
      ↓
Embeddings
      ↓
Chroma
      ↓
Relevant Context
      ↓
Groq LLM
      ↓
Answer
```

---

# 🌐 Multilingual Support

The system can work with transcripts available in languages supported by YouTube's transcript system.

For example:

```text
Hindi Video
     ↓
Hindi Transcript
     ↓
Embeddings
     ↓
Vector Search
     ↓
LLM
     ↓
Answer
```

Multilingual embedding models can be used to improve retrieval quality across languages.

---

# 🔒 Security

API keys should be stored in environment variables.

Never commit:

```text
.env
```

to GitHub.

The `.gitignore` should include:

```gitignore
.env
node_modules/
.venv/
__pycache__/
chroma_db/
```

---

# 🚧 Future Improvements

- [ ] Full-screen chat interface
- [ ] Conversation history
- [ ] Persistent vector database
- [ ] Better multilingual embeddings
- [ ] Support for video timestamps
- [ ] Clickable transcript references
- [ ] Streaming AI responses
- [ ] Loading/typing animations
- [ ] Better Markdown rendering
- [ ] Dark/light themes
- [ ] Chat export
- [ ] Improved transcript language detection

---

# 📌 Current Status

The project currently supports:

- ✅ YouTube video detection
- ✅ Transcript retrieval
- ✅ Transcript cleaning
- ✅ Text chunking
- ✅ Embedding generation
- ✅ Chroma vector search
- ✅ RAG-based question answering
- ✅ General conversation
- ✅ LLM-based question routing
- ✅ Node.js API gateway
- ✅ FastAPI backend
- ✅ Chrome Extension UI

---

# 👨‍💻 Author

**Pritam Shaw**

GitHub:  
https://github.com/DaemonGodx

---

## ⭐ If you found this project interesting

Feel free to star the repository and explore the code!
