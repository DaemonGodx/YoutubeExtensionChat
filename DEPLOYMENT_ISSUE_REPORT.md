# YouTube Chat Deployment Issue Report

**Prepared:** October 23, 2026  
**Repository:** `DaemonGodx/YoutubeExtensionChat`  
**Current commit:** `15d7fea` — `Restore backend transcript fetching`

## Executive summary

The deployed chat request reaches the Node API and the RAG service, but the RAG request returns HTTP 500 while trying to fetch the video's transcript. Render's RAG logs show the precise exception: `youtube_transcript_api._errors.IpBlocked`. YouTube is rejecting the request because it originates from a cloud-provider IP used by Render.

This explains the difference reported between the local “scholarship” environment and Render: the local request comes from a different network, while the deployed request is made from Render. The current failure occurs before the RAG service creates embeddings or calls the language model. The confirmed cause is therefore transcript retrieval from Render, not the earlier extension `DOMParser` error.

No application code was changed as part of the investigation that identified this cause. The current code is at `15d7fea`, which was pushed to `main`.

## Current request flow

The extension currently sends a video ID and question to the Node API. Node forwards them to the Python RAG service. Since the request has no transcript, the RAG service fetches it itself:

```text
Chrome extension
  → Node API on Render
    → Python RAG API on Render
      → youtube-transcript-api fetches from YouTube
        → YouTube blocks Render's cloud IP (IpBlocked)
```

The relevant implementation is in:

- `extension/popup.js`: sends the video ID and question.
- `server/server.js`: forwards the request to the configured RAG URL and returns an HTTP 500 if that request fails.
- `rag/app.py`: handles `/chat` and calls `ask_question`.
- `rag/main.py`: calls `get_transcript(video_id)` when no transcript text was supplied, then proceeds to chunking and embeddings.

## Evidence from Render

The Node service log reported:

```text
Node server running on port 10000
RAG request failed: Internal Server Error
```

That message only establishes that Node received an HTTP error from the RAG service. The RAG service log supplied the root cause. Its traceback went through `youtube_transcript_api`'s `_fetch_html` path and ended with:

```text
youtube_transcript_api._errors.IpBlocked
YouTube is blocking requests from your IP.
```

The library's explanation explicitly identifies cloud-provider IPs as commonly blocked. The same RAG log view also showed successful `GET /` health requests, so the RAG process was running even though its `/chat` request failed.

## What fails, and what does not

### Confirmed failing step

`get_transcript(video_id)` tries to fetch English captions from YouTube. The request is rejected before a transcript is returned. The exception propagates out of the FastAPI `/chat` handler, producing the 500 that Node reports.

### Not reached for this request

After a successful fetch, the code would split the transcript, call `Chroma.from_documents(...)` to create embeddings, retrieve relevant chunks, and call the Groq language model. Because the transcript fetch raises first, those later steps are not the cause of this particular 500.

### Separate earlier extension error

During the earlier browser-side extraction attempts, Chrome reported:

```text
Failed to execute 'parseFromString' on 'DOMParser':
This document requires 'TrustedHTML' assignment.
```

That was a separate browser-side problem from a previous transcript-capture approach. It is not the exception in the current Render request. The current error occurs on the Python service while talking to YouTube.

## Change history and how it led here

| Commit | Change | Relevance |
|---|---|---|
| `8df9942` | Initial working application | The original design used the Python transcript API. The user reports it worked in the local scholarship environment. |
| `1e55c58` | Changed embeddings from Hugging Face to Google Gemini | Adds a separate dependency on `GOOGLE_API_KEY`. It could cause a later embedding error if missing or invalid, but it is not reached during the currently observed failure. |
| `870ca71` | Deployment changes | Began adapting service setup for Render. |
| `3da9d2e` | Changed the extension endpoint for the Render hostname | Pointed the extension at the deployed Node service. |
| `3699307` | Deployment fixes | Moved transcript responsibility to the extension: Node required a non-empty `transcript` and forwarded it to RAG. This made browser-side caption extraction a required part of the chat flow. |
| `5279982` | Added caption-extraction diagnostics | Continued the browser-side extraction approach. |
| `cfdbb9e` | Parsed YouTube captions in extension context | Continued attempts to obtain captions in the browser. |
| `4c76aea` | Read from YouTube's transcript panel | Tried extracting transcript text from the page UI. |
| `39d776c` | Fixed transcript-capture permissions | Added more extension permission and reload handling around browser extraction. |
| `15d7fea` | Restored backend transcript fetching | Removed the client-side extraction requirement and made backend fetching optional again. The extension now sends only video ID and question, so Render's RAG service attempts the YouTube fetch and encounters `IpBlocked`. |

The central deployment constraint was not visible in local testing: the original backend fetch depends on YouTube accepting requests from the backend's network. Render's cloud IP is blocked, even though the same library can work from a local network.

## Other configuration to verify after transcript retrieval works

`rag/main.py` currently initializes `GoogleGenerativeAIEmbeddings` with model `models/gemini-embedding-001`. `render.yaml` declares `GOOGLE_API_KEY` as a secret that must be supplied in Render. If that key is absent, invalid, or unavailable to the service, the first request that gets past transcript retrieval could fail at embedding creation. The current `IpBlocked` traceback does not establish whether the Google key is correct; that is a separate follow-up check.

The project also uses `GROQ_API_KEY` for the answer-generation step, which would be reached after transcript retrieval and embeddings succeed.

## Recovery options

### Option A: Keep transcript fetching on the backend and use a proxy

Configure `youtube-transcript-api` to route requests through a rotating residential proxy. The library documents proxy configuration for `IpBlocked`/`RequestBlocked` failures and warns that static proxy addresses may themselves get blocked. For its Webshare-specific configuration, the library supports `WebshareProxyConfig`; other compatible proxy services can use the generic proxy configuration. See the [library's IP-ban guidance](https://github.com/jdepoix/youtube-transcript-api#working-around-ip-bans-requestblocked-or-ipblocked-exception).

This is the closest fit to the current backend-fetch architecture, but it requires choosing a provider, may cost money, and cannot guarantee every request will succeed. Proxy credentials should be kept in Render environment variables and must never be embedded in the Chrome extension or committed to Git.

### Option B: Fetch the transcript in the user's browser

Have the extension obtain transcript text from the YouTube page/browser session and send that text to the backend. This avoids making the transcript request from Render's blocked IP and avoids a paid proxy service. However, the previous browser extraction attempts were not working reliably and encountered the separate `TrustedHTML`/caption extraction issues described above. This path needs a reliable extension-side implementation and a test on the target video before it can replace backend fetching.

### Option C: Use a hosted transcript provider

A hosted transcript API could perform retrieval outside Render and return transcript text to the RAG service. This reduces the work of operating a proxy but introduces another service dependency, credentials, potential usage costs, and provider-specific limits.

## Recommended next diagnostic step

Before changing code, decide whether the project should keep backend retrieval through a rotating residential proxy or retry browser-side retrieval. If choosing the proxy route, first confirm the selected provider supports rotating residential egress and understand its pricing/usage limits. Then configure the RAG client and Render secrets, test one known video, and inspect the RAG logs. Only after the log shows transcript retrieval succeeded should the embedding and LLM steps be investigated.

If choosing browser-side retrieval, first test that the extension can obtain a non-empty transcript for `RE3_PGwDwhw` in the browser, then confirm the request carries that transcript to Node and RAG. Do not treat a successful Node health check as proof that transcript fetching works; the failing operation is the RAG `/chat` request.

## Current status

- Current pushed commit: `15d7fea`.
- Node service starts and reports port `10000` in its logs.
- RAG service is running and responds to health requests.
- RAG chat requests fail when transcript retrieval is attempted from Render.
- Exact observed failure: `youtube_transcript_api._errors.IpBlocked` for video `RE3_PGwDwhw`.
- A browser-side transcript implementation is now present in the local working tree. It is not committed, pushed, or deployed, and still needs a live browser test against YouTube.
- Automated tests currently cover mocked caption retrieval, Node forwarding/validation, FastAPI validation, and the regression that supplied text bypasses `get_transcript`.
- After deployment, the RAG logs should show `Using supplied transcript for <video ID>` for the production flow and should not show an `IpBlocked` traceback.
