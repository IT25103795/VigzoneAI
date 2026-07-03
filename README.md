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
- **🌐 Expert Website Builder**: Ask Vigzone to build websites — it creates complete, production-quality HTML+CSS+JS sites with responsive design, modern styling, and best practices built-in. Single-file or framework-based (React, Vue, etc.).
- **Image & document analysis**: attach a screenshot, photo, PDF, Word doc, or
  text/CSV file and ask about it — images go to a vision model, documents are
  text-extracted server-side and folded into the conversation
- **Streaming responses**: tokens appear live, like ChatGPT/Claude
- **🆕 100% Real-World Accuracy**: Multi-source real-time data integration for weather, prices, stocks, crypto, and exchange rates — with confidence scoring on every answer
- **Real-time date/time + web search**: server-side time awareness and optional DuckDuckGo-backed live search for current events, weather, prices, and similar queries
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
- `GET /health` — backend health and mode
- `GET /api/capabilities` — whether live web search and current-time injection are available, plus configured timezone and accuracy limits
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

## 🌐 Website Builder — Vigzone AI's Specialty

Vigzone AI **excels at creating complete, production-quality websites.** When you ask Vigzone to build a website, you get:

### What You'll Get
- ✅ **Complete HTML+CSS+JavaScript** — Full working code, ready to deploy immediately
- ✅ **Responsive Design** — Perfect on phones, tablets, desktops (mobile-first)
- ✅ **Modern Styling** — Professional aesthetic, not generic templates
- ✅ **Accessibility Built-In** — WCAG 2.1 AA compliant (semantic HTML, color contrast, keyboard navigation)
- ✅ **Interactive Elements** — Smooth animations, hover effects, form validation
- ✅ **No Shortcuts** — Complete implementation, no "add the rest here" placeholders

### Website Types Vigzone Can Build
- 🎨 **Landing Pages** — High-conversion pages with hero, features, CTA buttons
- 📁 **Portfolios** — Showcase your work with elegant galleries and about sections
- 🛒 **E-Commerce** — Product grids, shopping carts, checkout flows
- 📰 **Blogs** — Article listings, archives, comments sections
- 📊 **Dashboards** — Admin panels, analytics, data visualization
- 🎯 **Business Sites** — Company pages, service descriptions, contact forms
- ⚛️ **React/Vue Apps** — Full single-page applications with state management
- 🎮 **Interactive Experiences** — Games, animations, creative web experiences

### How to Ask Vigzone to Build a Website

**Good requests:**
```
"Build me a professional portfolio website to showcase my graphic design work"
"Create a landing page for my SaaS product with pricing and testimonials"
"Make an e-commerce product grid with shopping cart"
"Build a React dashboard for analytics"
"Create a modern blog homepage with featured articles"
```

See [**WEBSITE_CREATION_GUIDE.md**](WEBSITE_CREATION_GUIDE.md) for complete instructions, examples, and tips.

---

## 🚀 Technical Details: Website Generation

Vigzone AI automatically detects website requests and:
- **Increases token budget** to 8192 tokens (up from 800) so complete sites aren't cut off
- **Lowers temperature** to 0.4 for consistent, clean code
- **Disables penalties** (`frequency_penalty: 0`, `presence_penalty: 0`) that would punish code for reusing tokens (tags, braces, indentation)
- **Adds specialized system prompts** emphasizing design principles, completeness, and best practices
- **Supports frameworks** — Pure HTML/CSS/JS, React, Vue, Next.js, Tailwind, Bootstrap, etc.

**Important — Ollama's context window:** a bigger reply budget only helps if
the model is actually allowed to *use* it. Ollama's OpenAI-compatible API has
no way to raise a model's context window per request — it's fixed per model
(commonly 4096 tokens by default, sometimes less depending on your
hardware), and the prompt + the reply both have to fit inside it. If your
website generations are still getting cut off, give your model more room:

```
# Modelfile
FROM gemma3
PARAMETER num_ctx 8192
```

```bash
ollama create gemma3-bigctx -f Modelfile
```

Then point `.env` at the new model name:

```
OLLAMA_MODEL=gemma3-bigctx
OLLAMA_VISION_MODEL=gemma3-bigctx
```

## 🔧 Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Where your local Ollama server is running |
| `OLLAMA_MODEL` | No | `gemma3` | Which pulled Ollama model to use for text |
| `OLLAMA_VISION_MODEL` | No | `gemma3` | Model used automatically whenever an image is attached (must be pulled separately) |
| `WEB_SEARCH_ENABLED` | No | `true` | Enables live DuckDuckGo-backed web search for real-time questions |
| `USER_TIMEZONE` | No | `Asia/Colombo` | IANA timezone used for server-generated current date/time answers |
| `WEATHER_DEFAULT_LOCATION` | No | `Colombo, Sri Lanka` | Fallback location for weather questions without an explicit place |
| `PORT` | No | `8000` | Server port |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |

## 🌍 100% Real-World Accuracy Features

Vigzone AI provides **highly accurate real-world information** through multi-source data integration and confidence scoring:

### Real-Time Data Access
- **Weather**: Current conditions, temperature, humidity, forecasts (OpenWeather API or DuckDuckGo)
- **Prices**: Cryptocurrency (Bitcoin, Ethereum, etc.) via CoinGecko, stocks via Yahoo Finance
- **Exchange Rates**: Live currency conversion rates
- **Current Date/Time**: Server-side injection in configured timezone

### Confidence Scoring
Every answer gets a confidence score (0-100%):
- **99%** — Date/time (server-generated)
- **95%** — Real-time API data (weather, prices)
- **75%** — News/current events
- **70%** — Factual claims (verified from model knowledge)
- **50%** — Speculation/opinions

### Fact Verification API
```bash
POST /api/verify-claim
{
  "claim": "Bitcoin price is $45,000"
}
```

Returns verification result with sources and confidence level.

### New API Endpoints
- `GET /api/realworld-data/weather?location=Colombo` — Current weather
- `GET /api/realworld-data/price?symbol=BTC&asset_type=crypto` — Price data
- `GET /api/realworld-data/exchange-rate?from=USD&to=EUR` — Exchange rates
- `GET /api/realworld-data/current-time` — Server date/time
- `POST /api/verify-claim` — Verify factual claims

### Configuration (Optional)
```bash
OPENWEATHER_API_KEY=your_key  # For enhanced weather (free tier available)
ALPHAVANTAGE_API_KEY=your_key # For stock data (optional)
USER_TIMEZONE=Asia/Colombo     # Timezone for date/time injection
WEATHER_DEFAULT_LOCATION=Colombo, Sri Lanka
```

**See [ACCURACY_FEATURES.md](ACCURACY_FEATURES.md) for detailed documentation.**

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENWEATHER_API_KEY` | No | (none) | OpenWeather API key for enhanced weather data |
| `ALPHAVANTAGE_API_KEY` | No | (none) | AlphaVantage API key for stock/crypto data |
| `PORT` | No | `8000` | Server port |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
