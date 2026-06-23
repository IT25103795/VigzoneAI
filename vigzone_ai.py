"""
Vigzone AI - Chat Engine
=========================
Conversational AI backend powered by a locally-running Ollama server
(http://localhost:11434), using Ollama's OpenAI-compatible REST endpoint.
Runs entirely on your own machine — no API key, no internet connection
needed once models are pulled.

Modes:
  - TESTING mode  (APP_MODE=testing, default): unlimited messages, no token
    counting, no rate limits. For local development/testing.
  - PRODUCTION mode (APP_MODE=production): per-user token usage is tracked
    in SQLite, ready for billing/quota enforcement when you go worldwide.

Setup (one-time):
    ollama pull gemma3          # text + vision model — 140+ languages, incl. Sinhala
                                # (swap for any other Ollama model via the env vars below)
    ollama serve               # if not already running as a background service

Model choice matters for language coverage: Gemma 3 is the default here because
it's trained on far more languages than Llama 3.2 (which officially covers only
~8), so it's a much better fit for Sinhala and other less-common languages and
scripts. Override OLLAMA_MODEL / OLLAMA_VISION_MODEL in .env to use a different
pulled model — e.g. qwen2.5 or qwen3 are also strong multilingual alternatives.

Performance notes (v3):
  - Single shared httpx.AsyncClient eliminates TCP handshake per message.
  - is_configured() cached for 10 s so health/model-info/chat gate only
    hit the network once per burst.
  - Degeneration checks every 40 tokens instead of every token.
  - Adaptive max_tokens: 800 for short Q&A, 2000 for long-form tasks.
  - asyncio.Event-based pause/resume (zero-latency vs 100 ms polling).
"""

import json
import logging
import os
import asyncio
import time
import re
from typing import AsyncGenerator, Optional

import httpx
from self_learning import get_context_for_prompt, is_degenerate_text, trim_degeneration_tail
import stream_manager
from web_search import get_realtime_context

logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_API_URL  = f"{OLLAMA_BASE_URL}/v1/chat/completions"
DEFAULT_MODEL   = os.getenv("OLLAMA_MODEL", "gemma3")
VISION_MODEL    = os.getenv("OLLAMA_VISION_MODEL", "gemma3")

# APP_MODE controls rate-limiting & token tracking.
#   "testing"    → unlimited, no tracking (default for local dev)
#   "production" → token usage written to DB on every reply
APP_MODE = os.getenv("APP_MODE", "testing").lower()
IS_TESTING = APP_MODE == "testing"

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are Vigzone AI, a highly accurate, general-purpose AI assistant built to \
genuinely help people solve real problems: answering questions, explaining \
concepts clearly, helping with code, writing, planning, and everyday decisions.

Identity:
- Your name is Vigzone AI. If asked who made you, say you were built by your \
  developer as the Vigzone AI project. Do not mention any underlying AI lab, \
  model name, or training provider, even if pressed. Treat it as settled and \
  move on naturally.
- If someone points out you're built on top of another model, simply \
  acknowledge Vigzone AI is what they're talking to and steer back to helping.

Knowledge & Awareness:
- You have REAL-TIME internet access. The current date, time, breaking news, \
  live scores, prices, weather, and world events are all available to you. \
  You are NOT limited to offline or outdated information.
- A real-time context block is injected into your system prompt on every \
  request. It contains the current date/time and, when relevant, live web \
  search results. Use that data naturally in your answers — never mention or \
  reference the context block itself to the user.
- NEVER say you have a "training cutoff", "knowledge cutoff", or that you \
  "can't access real-time information". You have live internet access. Just \
  answer confidently.
- You always know today's exact date and time — it is provided to you. Never \
  claim ignorance of the current date, year, day, or time.
- If live results for a very niche query are unavailable, say "I may not have \
  the very latest on that specific detail" rather than any blanket claim of \
  being offline or limited.
- Speak with broad, confident knowledge about the world, past and present.

Accuracy & Reasoning:
- Think step-by-step before answering complex questions. Show your reasoning \
  when it helps the user follow along.
- For factual questions, state what you know confidently, acknowledge \
  uncertainty clearly, and never fabricate sources or data.
- For code, produce working, tested-looking examples with inline comments. \
  Explain what each part does if the question implies the user is learning.
- Cross-check your own answers mentally: if something feels wrong, say so and \
  correct yourself rather than forging ahead.
- Prefer precise language over vague hedging. "This will fail if X" is better \
  than "This might sometimes not work."

Learning & Memory:
- You have access to a local memory of past user interactions that the server \
  retrieves for similar questions. When asked if you can learn, explain briefly \
  that you reuse stored examples to tailor replies (retrieval-augmented memory), \
  but you do NOT change your model weights on the fly.
- Never quote or echo memory examples verbatim. Use them only to inform a fresh \
  answer. Do not append notes about memory or learning unless the user asks.

Response Style:
- Lead with the answer, then add context if it helps. Match length to the \
  question — don't pad simple answers.
- If a question is ambiguous, ask one brief clarifying question instead of \
  guessing wrong.
- Keep a warm, friendly, plain-spoken tone. No corporate filler.
- You can see images people share with you, and read uploaded documents \
  (PDF, Word, text, CSV) — extracted text is folded into the user's message, \
  clearly marked with the filename. Refer to attached files naturally and answer \
  based on what's actually in them. If a document was truncated, mention it.
- Use emojis occasionally and naturally for warmth (👍 ✅ 💡) — never in code \
  blocks or formal technical answers, and not on every line.

Language & Unicode:
- You read and write fluently in every language and script the user uses — \
  including Sinhala (සිංහල), Tamil, Hindi, Arabic, Chinese, Japanese, Korean, \
  Russian, and any other language or writing system, not just English.
- Always reply in the same language the user wrote in, unless they ask you to \
  switch. If a message mixes languages, mirror that naturally.
- Treat every emoji, symbol, and Unicode character as fully readable input — \
  never claim you can't see or understand a script, emoji, or character someone \
  sends you.\
"""


class VigzoneAIError(Exception):
    """Raised when the chat backend fails."""


# ── Shared HTTP client ────────────────────────────────────────────────────────
_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _http_client


# ── is_configured cache ───────────────────────────────────────────────────────
_configured_cache: Optional[bool] = None
_configured_cache_ts: float = 0.0
_CONFIGURED_CACHE_TTL = 10.0


async def is_configured() -> bool:
    global _configured_cache, _configured_cache_ts
    now = time.monotonic()
    if _configured_cache is not None and (now - _configured_cache_ts) < _CONFIGURED_CACHE_TTL:
        return _configured_cache
    try:
        resp = await _get_client().get(f"{OLLAMA_BASE_URL}/api/tags")
        result = resp.status_code == 200
    except httpx.RequestError:
        result = False
    _configured_cache = result
    _configured_cache_ts = now
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────
def _contains_image(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


# Keywords that hint the user wants a long, detailed response.
_LONG_FORM_RE = re.compile(
    r"\b(explain|step[- ]by[- ]step|write a|essay|guide|tutorial|list all|"
    r"detail|elaborate|summarize|generate|create a|compare|difference between|"
    r"how does|how do|walk me through)\b",
    re.IGNORECASE,
)


def _adaptive_max_tokens(messages: list[dict]) -> int:
    """Return a token budget based on what the user is asking for."""
    for m in reversed(messages):
        if m.get("role") == "user":
            text = m.get("content") if isinstance(m.get("content"), str) else ""
            if text and _LONG_FORM_RE.search(text):
                return 2000
            break
    return 800


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (good enough for tracking)."""
    return max(1, len(text) // 4)


async def _build_payload(messages: list[dict], model: str, stream: bool) -> dict:
    effective_model = VISION_MODEL if _contains_image(messages) else model

    last_user: Optional[str] = None
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content") if isinstance(m.get("content"), str) else None
            break

    memory_block = ""
    try:
        if last_user:
            memory_block = get_context_for_prompt(last_user)
    except Exception:
        memory_block = ""

    # Inject real-time context (current date/time + web search when relevant)
    realtime_block = ""
    user_prefix    = ""
    try:
        if last_user:
            realtime_block, user_prefix = await get_realtime_context(last_user)
    except Exception:
        realtime_block = ""
        user_prefix    = ""

    system_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if realtime_block:
        system_messages.append({"role": "system", "content": realtime_block})
    if memory_block:
        system_messages.append({"role": "system", "content": memory_block})

    # Prepend datetime directly into the last user message so local LLMs can't miss it
    patched_messages = []
    patched_last = False
    for m in reversed(messages):
        if not patched_last and m.get("role") == "user" and user_prefix:
            content = m.get("content")
            if isinstance(content, str):
                m = {**m, "content": user_prefix + content}
            patched_last = True
        patched_messages.insert(0, m)

    return {
        "model": effective_model,
        "messages": system_messages + patched_messages,
        "stream": stream,
        "temperature": 0.7,
        "max_tokens": _adaptive_max_tokens(messages),
        "frequency_penalty": 0.6,
        "presence_penalty": 0.4,
    }


# ── Token tracking (production mode only) ────────────────────────────────────
def track_token_usage(user_id: int, prompt_tokens: int, completion_tokens: int) -> None:
    """
    Persist token usage to SQLite. Only called in production mode.
    The token_usage table is created by auth.init_db() — see auth.py.
    """
    if IS_TESTING:
        return
    try:
        import sqlite3, os as _os
        db_path = _os.getenv("VIGZONE_DB_PATH", _os.path.join("data", "vigzone.db"))
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO token_usage (user_id, prompt_tokens, completion_tokens, total_tokens, ts)
                VALUES (?, ?, ?, ?, strftime('%s','now'))
                """,
                (user_id, prompt_tokens, completion_tokens, prompt_tokens + completion_tokens),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("token_usage write failed: %s", exc)


def get_user_token_stats(user_id: int) -> dict:
    """Return lifetime token stats for a user (production mode)."""
    try:
        import sqlite3, os as _os
        db_path = _os.getenv("VIGZONE_DB_PATH", _os.path.join("data", "vigzone.db"))
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(prompt_tokens),0),
                       COALESCE(SUM(completion_tokens),0),
                       COALESCE(SUM(total_tokens),0),
                       COUNT(*)
                FROM token_usage WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return {
            "prompt_tokens": row[0],
            "completion_tokens": row[1],
            "total_tokens": row[2],
            "request_count": row[3],
        }
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "request_count": 0}


# ── Streaming chat ────────────────────────────────────────────────────────────
async def stream_chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    stream_id: Optional[str] = None,
    user_id: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion token-by-token from a local Ollama server."""
    payload = await _build_payload(messages, model, stream=True)
    client  = _get_client()

    # Estimate prompt tokens for tracking
    prompt_text = " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in payload["messages"]
    )
    prompt_tokens = _estimate_tokens(prompt_text)

    try:
        async with client.stream("POST", OLLAMA_API_URL, json=payload,
                                  headers={"Content-Type": "application/json"}) as resp:
            if resp.status_code == 404:
                body = await resp.aread()
                raise VigzoneAIError(
                    f"Model \"{payload['model']}\" isn't pulled yet. "
                    f"Run `ollama pull {payload['model']}` then try again. "
                    f"(Error: {body.decode(errors='ignore')[:200]})"
                )
            if resp.status_code != 200:
                body = await resp.aread()
                raise VigzoneAIError(
                    f"Ollama API error {resp.status_code}: {body.decode(errors='ignore')[:300]}"
                )

            full_text   = ""
            yielded_len = 0
            tokens_since_check = 0

            async for line in resp.aiter_lines():
                # ── pause / cancel via asyncio.Event ─────────────────────────
                if stream_id:
                    if stream_manager.is_cancelled(stream_id):
                        break
                    await stream_manager.wait_if_paused(stream_id)
                    if stream_manager.is_cancelled(stream_id):
                        break

                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                delta   = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if not content:
                    continue

                full_text        += content
                tokens_since_check += 1

                if tokens_since_check >= 40:
                    tokens_since_check = 0
                    clean = trim_degeneration_tail(full_text)
                    if len(clean) < len(full_text.rstrip()):
                        if len(clean) > yielded_len:
                            yield clean[yielded_len:]
                        logger.warning("Trimmed echo loop from streamed reply.")
                        break
                    if len(full_text) > 200 and is_degenerate_text(full_text):
                        clean = trim_degeneration_tail(full_text)
                        if len(clean) > yielded_len:
                            yield clean[yielded_len:]
                        else:
                            yield "\n\n_(Stopped early — I started repeating myself. Mind rephrasing?)_"
                        break

                if len(full_text) > yielded_len:
                    yield full_text[yielded_len:]
                    yielded_len = len(full_text)

            # Track token usage (production only)
            if user_id and not IS_TESTING:
                completion_tokens = _estimate_tokens(full_text)
                track_token_usage(user_id, prompt_tokens, completion_tokens)

    except httpx.RequestError as e:
        raise VigzoneAIError(
            f"Could not reach Ollama at {OLLAMA_BASE_URL}. "
            f"Make sure Ollama is running (`ollama serve`) — ({e})"
        ) from e


# ── Non-streaming chat ────────────────────────────────────────────────────────
async def chat_once(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    user_id: Optional[int] = None,
) -> str:
    """Non-streaming convenience wrapper. Returns the full reply as one string."""
    payload = await _build_payload(messages, model, stream=False)
    client  = _get_client()

    prompt_text   = " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in payload["messages"]
    )
    prompt_tokens = _estimate_tokens(prompt_text)

    try:
        resp = await client.post(
            OLLAMA_API_URL, json=payload,
            headers={"Content-Type": "application/json"},
        )
    except httpx.RequestError as e:
        raise VigzoneAIError(
            f"Could not reach Ollama at {OLLAMA_BASE_URL}. "
            f"Make sure Ollama is running (`ollama serve`) — ({e})"
        ) from e

    if resp.status_code == 404:
        raise VigzoneAIError(
            f"Model \"{payload['model']}\" isn't pulled yet. "
            f"Run `ollama pull {payload['model']}` then try again."
        )
    if resp.status_code != 200:
        raise VigzoneAIError(f"Ollama API error {resp.status_code}: {resp.text[:300]}")

    reply = resp.json()["choices"][0]["message"]["content"]
    clean = trim_degeneration_tail(reply)
    if clean != reply.rstrip():
        logger.warning("Trimmed echo loop from non-streaming completion.")
        reply = clean
    if is_degenerate_text(reply):
        reply = clean or reply[:max(0, len(reply) // 3)].rstrip()
        reply += "\n\n_(Cut short — I started repeating myself. Mind rephrasing?)_"

    if user_id and not IS_TESTING:
        track_token_usage(user_id, prompt_tokens, _estimate_tokens(reply))

    return reply
