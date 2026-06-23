# Vigzone AI — Conversational Assistant

Vigzone AI is a real chat assistant: ask it to explain something, debug code,
draft a message, or think through a decision, and it actually reasons about
the conversation instead of free-associating words.

This is a redesign of the original Vigzone AI project. The previous version
trained a tiny attention-LSTM on a 59-line dataset and produced
word-association text, not real answers. This version keeps the same
FastAPI + web-UI architecture but swaps the brain for a real LLM running
locally via [Ollama](https://ollama.com) (OpenAI-compatible API), so it can
actually hold a conversation and solve real problems — entirely on your own
machine, with no API key and no internet connection required once models
are pulled.

## ⚡ Features

- **Real conversations**: powered by a local Ollama model (Llama 3.2 by default, or any model you've pulled)
- **Runs fully offline**: no API key, no cloud dependency, no per-message cost
- **Image & document analysis**: attach a screenshot, photo, PDF, Word doc, or
  text/CSV file and ask about it — images go to a vision model, documents are
  text-extracted server-side and folded into the conversation
- **Streaming responses**: tokens appear live, like ChatGPT/Claude
- **Modern chat UI**: dark theme, markdown-lite rendering, mobile responsive,
  drag-and-drop / paste-to-attach files
- **Stateless REST API**: `POST /api/chat` (streaming) and `/api/chat/sync`
- **Production ready**: Docker support, health checks, CORS, logging
- **Free to run**: no GPU, no training, no paid API required

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running locally

### Local Installation

1. **Navigate to the project**
   ```bash
   cd VigzoneAI
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Pull the model** (one-time)
   ```bash
   ollama pull gemma3   # text + vision in one model, 140+ languages (incl. Sinhala)
   ```

   `.env` is already set up to use this by default — copy `.env.example`
   to `.env` if you don't have one yet, and adjust `OLLAMA_MODEL` /
   `OLLAMA_VISION_MODEL` if you'd rather use different models (e.g. the
   smaller/faster `llama3.2` + `llava` pair, which has more limited language
   coverage, or `qwen2.5`/`qwen3` for another strong multilingual option).

4. **Run the server**
   ```bash
   python app.py
   ```

5. **Open the chat UI**

   Visit `http://localhost:8000`

### Using Docker

```bash
docker-compose up -d
# or
docker build -t vigzone-ai .
docker run -p 8000:8000 --env-file .env vigzone-ai
```

## 📖 API Reference

### Interactive Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Chat (streaming)
```
POST /api/chat
Content-Type: application/json

{
  "messages": [
    { "role": "user", "content": "Explain recursion with an example." }
  ]
}
```
Returns a `text/event-stream` of `data: {"content": "..."}` chunks, ending
with `data: [DONE]`. The client is expected to send the **entire**
conversation history each call — the server is stateless and only adds the
system prompt.

### Chat (non-streaming)
```
POST /api/chat/sync
```
Same request body, returns `{"role": "assistant", "content": "..."}` in one
JSON response.

### Upload an attachment
```
POST /api/upload
Content-Type: multipart/form-data

file: <binary>
```
Returns one of:
```json
{ "kind": "image", "name": "photo.jpg", "mime": "image/jpeg", "data_uri": "data:image/jpeg;base64,..." }
```
```json
{ "kind": "document", "name": "report.pdf", "text": "...", "truncated": false }
```
The frontend calls this when you attach a file, then folds the result into
the next chat message: images become an `image_url` content part (handled
by the vision-capable Ollama model, gemma3 by default), and document text
gets inlined into the message with the filename noted. Supported types:
PNG/JPG/WEBP/GIF images, PDF, DOCX, TXT, MD, CSV. Max 10 MB per file, up to
5 files at once.

### Other endpoints
- `GET /health` — backend status and whether an API key is configured
- `GET /api/model-info` — current text + vision model names
- `GET /api/stats` — endpoint listing

## 🧠 Why Ollama

Ollama's API is OpenAI-schema compatible, runs fully on your own hardware
with no API key or per-message cost, and serves full-size
open models (Llama 3.3 70B and others) at very low latency — a good fit for
a student project that needs a genuinely capable model without a billing
setup. Swapping providers later (OpenAI, Anthropic, local Ollama) only
requires changing `vigzone_ai.py` — the API contract (`/api/chat`) and the
UI don't need to change.

## 📂 Project Structure

```
VigzoneAI/
├── app.py                # FastAPI server & API routes
├── vigzone_ai.py          # Chat engine (Ollama API client, streaming, vision routing)
├── file_processing.py     # Image resizing + PDF/DOCX/text extraction for uploads
├── static/index.html      # Chat UI (single file: HTML/CSS/JS)
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── Procfile                # for Heroku-style deploys
└── launcher.py              # dev/prod launch helper
```

## 🔧 Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Where your local Ollama server is running |
| `OLLAMA_MODEL` | No | `gemma3` | Which pulled Ollama model to use for text |
| `OLLAMA_VISION_MODEL` | No | `gemma3` | Model used automatically whenever an image is attached (must be pulled separately) |
| `PORT` | No | `8000` | Server port |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
