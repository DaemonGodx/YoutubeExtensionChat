# 🎥 YouTube RAG Chat

An AI-powered Chrome Extension that lets you **ask questions about YouTube videos** using Retrieval-Augmented Generation (RAG).

The Python backend retrieves the video's transcript from TranscriptAPI.com, then uses Gemini embeddings (`models/gemini-embedding-001`), Chroma retrieval, and Groq (`openai/gpt-oss-120b`) to answer questions based on that transcript.

---

## ✨ Features

- 🎥 Chat with YouTube videos
- 🤖 AI-powered answers using RAG
- 🔎 Semantic search over video transcripts
- 🧠 Context-aware question answering
- 📝 Transcript retrieval through TranscriptAPI.com
- 🌐 Uses the language selected by TranscriptAPI's default behavior
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
│ Video ID + Popup Question   │
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
│ TranscriptAPI → Chunk        │
│ Gemini → Chroma → Groq       │
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
├── server/
│   └── server.js
│
├── extension/
│   ├── config.js
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
│
├── tests/
│   ├── environment_config.test.js
│   └── test_transcript_api.py
├── package.json
├── package-lock.json
├── render.yaml
├── requirements.txt
├── .gitignore
├── .env.example
└── README.md
```

> `.env`, virtual environments, `node_modules`, caches, and generated vector databases should not be committed to Git.

---

# 🧠 How RAG Works

When you ask a question about a YouTube video, the system follows these steps:

### 1. Get YouTube Transcript

The Python backend retrieves the transcript from TranscriptAPI.com using the video ID sent by the extension.

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

Each chunk is converted into a vector representation using Google Gemini embeddings (`models/gemini-embedding-001`).

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

# 🔀 Video Question Flow

The current pipeline answers questions using the selected video's transcript. It does not have a separate general-conversation route.

```text
User Question
      ↓
Transcript and vector store (fetched or cached)
      ↓
Gemini Embeddings → Chroma Retrieval
      ↓
Groq Answer
```

### Video Question

Example:

```text
What are the main points discussed in this video?
```

The system retrieves relevant transcript context before generating the answer.

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
- Google Gemini Embeddings (`models/gemini-embedding-001`)
- Groq
- TranscriptAPI.com

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

# 🔐 3. Configure Local Environment Variables

Use `.env.example` as a template for `.env` in the repository root. If you already have `.env`, keep it and add or update the listed settings instead of replacing it:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Set `GOOGLE_API_KEY`, `GROQ_API_KEY`, and `TRANSCRIPT_API_KEY` in `.env`. The example also sets `PORT=3000` and `RAG_API_URL=http://localhost:8000/chat`, so the local Node service forwards to the local Python service. Both services load the root `.env`. Never commit `.env`; it is ignored by Git.

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

From the project root, start the server:

```bash
npm ci
npm start
```

The Node.js API will run at:

```text
http://localhost:3000
```

---

# ☁️ Deploy to Render

The repository includes a Render Blueprint (`render.yaml`) that creates two web services:

- `youtube-chat-rag` runs the FastAPI and RAG backend.
- `youtube-chat-api` runs the public Node.js API and calls the RAG service's public URL.

To deploy:

1. Push this repository, including `render.yaml`, to a Git provider connected to Render.
2. In the Render Dashboard, choose **New → Blueprint**, connect the repository, and apply the Blueprint.
3. Enter `GROQ_API_KEY`, `GOOGLE_API_KEY`, and `TRANSCRIPT_API_KEY` in the RAG service's environment settings. Add `TRANSCRIPT_API_KEY` to the Python RAG service only; keep it out of the Node service and extension.
4. Wait for both services to finish deploying. This repository's current extension demo URL is `https://youtube-chat-api-siqa.onrender.com`; the Node service forwards to `https://youtube-chat-rag.onrender.com/chat` through `render.yaml`.
5. Set `mode` to `"demo"` in `extension/config.js`, then reload the unpacked extension in Chrome. If Render changes the Node service hostname, update `demo` in that config and the matching host permission in `extension/manifest.json`.

The Blueprint uses Render's free service plan. Free services can spin down when idle, so the first request after inactivity may take longer.

Transcript retrieval is handled by TranscriptAPI.com rather than a direct YouTube request from Render. Provider errors, missing captions, rate limits, or exhausted credits can still prevent a transcript from being returned.

## Local and Demo Modes

The extension is Manifest V3 and has no build step, so Chrome does not read `.env` for the extension. Its mode is selected in `extension/config.js`:

```js
mode: "local", // or "demo"
```

### Local usage

1. Copy `.env.example` to `.env` and set your Google, Groq, and TranscriptAPI keys.
2. In `extension/config.js`, leave `mode` set to `"local"`.
3. Start FastAPI from the repository root: `uvicorn rag.app:app --reload --port 8000`.
4. In a second terminal at the repository root, start Node: `npm start`.
5. Reload the unpacked extension from `chrome://extensions` and open a YouTube video.

The extension calls `http://localhost:3000`; Node reads `RAG_API_URL=http://localhost:8000/chat` from `.env` and forwards the request to FastAPI. No chat request is sent to Render in local mode.

The Python service sends a server-side request to TranscriptAPI.com with `TRANSCRIPT_API_KEY` as a Bearer token. It normalizes the provider's transcript segments or text into a plain string before chunking. Keep the key in the root `.env` locally and in the Python RAG service environment on Render. It is never sent to the extension or Node API.

### Demo usage and switching

Set `mode` to `"demo"` in `extension/config.js`. The extension then calls the existing Render Node API at `https://youtube-chat-api-siqa.onrender.com`. The deployed Node service retains its `RAG_API_URL` setting for `https://youtube-chat-rag.onrender.com/chat`.

After changing the mode or either URL, save `extension/config.js` and reload the unpacked extension in `chrome://extensions`. No build is needed. Changing the local `.env` requires restarting the affected local service. Switching extension modes does not require a source edit to `popup.js` or a Render redeploy.

---

# 🧩 6. Download and Use the Chrome Extension

| Download and install | Use the extension |
| --- | --- |
| Open the [GitHub repository](https://github.com/DaemonGodx/YoutubeExtensionChat), select **Code → Download ZIP**, and extract it. In Chrome, open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select the extracted `extension/` folder. | The checked-in mode is `demo`. To use local services, change `mode` to `"local"` in `extension/config.js` and start the Python and Node services. Open a YouTube video, click the extension, and ask a question. After changing the mode, save the file and click the extension’s refresh icon at `chrome://extensions`. |

The extension uses the active YouTube tab to get the video ID. It sends the question to the Node API selected in `extension/config.js`; it does not read captions from the page.

---

# 🔌 API

## POST `/api/chat`

The Chrome extension sends questions to the Node.js backend selected by `extension/config.js`.

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
POST `/chat` on the RAG backend
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

# 🌐 Transcript Languages

The extension does not currently provide a language selector. Because the backend does not send a `language` parameter, TranscriptAPI uses its default language selection for each video.

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
- ✅ TranscriptAPI.com integration
- ✅ Transcript cleaning
- ✅ Text chunking
- ✅ Embedding generation
- ✅ Google Gemini embeddings
- ✅ Chroma vector search
- ✅ RAG-based question answering
- ✅ Groq answer generation
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
