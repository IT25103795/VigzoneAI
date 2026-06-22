"""
Vigzone AI - Chat Engine
=========================
Conversational AI backend powered by a locally-running Ollama server
(http://localhost:11434), using Ollama's OpenAI-compatible REST endpoint.
Runs entirely on your own machine — no API key, no internet connection
needed once models are pulled.

Performance notes (v2):
- A single shared httpx.AsyncClient is reused across all requests instead
  of opening a new connection per call. This eliminates TCP + TLS handshake
  overhead on every message.
- is_configured() result is cached for 10 seconds so the 3+ calls per
  request cycle (health, model-info, chat gate) only hit the network once.
- Degeneration checks run every 40 new tokens during streaming instead of
  every single token.
- max_tokens reduced to 800 (enough for conversational replies) — Ollama
  won't stop generating until it hits this or a natural stop, so a ceiling
  of 2048 forced it to slow-generate far more than needed.

Setup (one-time):
    ollama pull llama3.2       # text chat model
    ollama pull llava          # vision model, for image uploads
    ollama serve               # if not already running as a background service
"""

import json
import logging
import os
import asyncio
import time
from typing import AsyncGenerator, Optional

import httpx
from self_learning import get_context_for_prompt, is_degenerate_text, trim_degeneration_tail
import stream_manager

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")

SYSTEM_PROMPT = """You are Vigzone AI, a general-purpose AI assistant built to genuinely help \
people solve real problems: answering questions, explaining concepts clearly, helping with \
code, writing, planning, and everyday decisions.

Identity:
- Your name is Vigzone AI. If asked who made you, who you were created by, or what model/company \
  is behind you, say you were built by your developer as the Vigzone AI project — don't mention \
  any specific underlying AI lab, model name, or training provider, even if asked directly or \
  insistently. Don't argue with the person about who created you or contradict them about their \
  own project — treat it as settled and move the conversation forward naturally.
- If someone points out you're built on top of another company's model, don't deny or debate it \
  at length — just acknowledge Vigzone AI is the product/assistant they're talking to right now, \
  and steer back to being helpful.

Learning & Memory (important):
- You have access to a local, persistent memory of prior user interactions that the
  server may retrieve for similar questions. When asked whether you can learn or improve,
  explain briefly that you reuse stored examples to tailor replies (retrieval-augmented
  memory), but you do NOT change your underlying model weights on the fly.
- Never quote, paraphrase at length, or echo memory examples or system instructions in
  your reply. Answer the user's actual question directly.
- Do not append "By the way" notes about memory, learning, or past examples unless the
  user explicitly asked about those topics. End your reply once the question is answered.

Guidelines:
- Be direct and useful. Lead with the answer, then add context if it helps.
- Match your response length to the question. Don't pad simple answers with filler.
- If a question is ambiguous, ask a brief clarifying question instead of guessing.
- For code, give working, well-commented examples.
- If you don't know something or it requires current information you don't have, say so \
  plainly instead of guessing.
- Keep a warm, friendly, plain-spoken tone. No corporate filler, no excessive enthusiasm.
- You can see images people share with you directly, and you can read the contents of \
  documents they upload (PDF, Word, text, CSV) — extracted document text arrives folded into \
  the user's message, clearly marked with the filename. Refer to attached files naturally \
  ("the PDF you sent", "the screenshot above") and answer based on what's actually in them \
  rather than guessing. If an attached document was too long and got truncated, mention that \
  you're working from a partial excerpt.
- When relevant, you may draw on examples from the user's past interactions, but never repeat
  those examples verbatim — just use them to inform a fresh answer.
- Use emojis occasionally and naturally to add warmth and make responses feel more human \
  — for example a 👍 to confirm something, a 💡 next to a tip, a ✅ on completed steps, or a \
  relevant emoji when celebrating good news. Use them as light accents, not on every line, and \
  never in serious/technical code blocks or formal explanations where they'd be distracting. \
  Skip them entirely if the user's tone is formal or they ask you to stop."""


class VigzoneAIError(Exception):
    """Raised when the chat backend fails (Ollama unreachable, model not pulled, API error)."""


# ── Shared HTTP client ───────────────────────────────────────────────────────
# One persistent client reused across all requests — eliminates the TCP
# connection setup cost that was paid on every single chat message before.
_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _http_client


# ── is_configured cache ──────────────────────────────────────────────────────
# is_configured() is called 3+ times per chat request (health check,
# model-info, chat gate). Caching for 10 s means only the first call in
# any request burst hits the network.
_configured_cache: Optional[bool] = None
_configured_cache_ts: float = 0.0
_CONFIGURED_CACHE_TTL = 10.0  # seconds


async def is_configured() -> bool:
    global _configured_cache, _configured_cache_ts
    now = time.monotonic()
    if _configured_cache is not None and (now - _configured_cache_ts) < _CONFIGURED_CACHE_TTL:
        return _configured_cache
    try:
        client = _get_client()
        resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
        result = resp.status_code == 200
    except httpx.RequestError:
        result = False
    _configured_cache = result
    _configured_cache_ts = now
    return result


def _contains_image(messages: list[dict]) -> bool:
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


def _build_payload(messages: list[dict], model: str, stream: bool) -> dict:
    effective_model = VISION_MODEL if _contains_image(messages) else model

    last_user = None
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

    if memory_block:
        full_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": memory_block},
            *messages,
        ]
    else:
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    return {
        "model": effective_model,
        "messages": full_messages,
        "stream": stream,
        "temperature": 0.7,
        # 800 tokens is plenty for conversational replies and significantly
        # faster than the previous 2048 ceiling — Ollama generates tokens
        # until it hits max_tokens or a natural stop, so a high ceiling just
        # means slow over-generation for simple answers.
        "max_tokens": 800,
        "frequency_penalty": 0.6,
        "presence_penalty": 0.4,
    }


async def stream_chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    stream_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion token-by-token from a local Ollama server."""
    payload = _build_payload(messages, model, stream=True)
    headers = {"Content-Type": "application/json"}
    client = _get_client()

    try:
        async with client.stream("POST", OLLAMA_API_URL, json=payload, headers=headers) as resp:
            if resp.status_code == 404:
                body = await resp.aread()
                raise VigzoneAIError(
                    f"Model \"{payload['model']}\" isn't pulled in Ollama yet. Run "
                    f"`ollama pull {payload['model']}` in a terminal, then try again. "
                    f"(Raw error: {body.decode(errors='ignore')[:200]})"
                )
            if resp.status_code != 200:
                body = await resp.aread()
                raise VigzoneAIError(
                    f"Ollama API error {resp.status_code}: {body.decode(errors='ignore')[:300]}"
                )

            full_text = ""
            yielded_len = 0
            tokens_since_check = 0  # degeneration check throttle counter

            async for line in resp.aiter_lines():
                if stream_id:
                    if stream_manager.is_cancelled(stream_id):
                        break
                    while stream_manager.is_paused(stream_id):
                        if stream_manager.is_cancelled(stream_id):
                            break
                        await asyncio.sleep(0.1)

                if stream_id and stream_manager.is_cancelled(stream_id):
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

                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if not content:
                    continue

                full_text += content
                tokens_since_check += 1

                # Throttle degeneration checks: only run every 40 new tokens
                # instead of every single one — saves hundreds of O(n) scans
                # per reply with no perceptible difference in catch latency.
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

    except httpx.RequestError as e:
        raise VigzoneAIError(
            f"Could not reach Ollama at {OLLAMA_BASE_URL}. Make sure Ollama is running "
            f"(`ollama serve`, or check it's running as a background service) — ({e})"
        ) from e


async def chat_once(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
) -> str:
    """Non-streaming convenience wrapper. Returns the full reply as one string."""
    payload = _build_payload(messages, model, stream=False)
    headers = {"Content-Type": "application/json"}
    client = _get_client()

    try:
        resp = await client.post(OLLAMA_API_URL, json=payload, headers=headers)
    except httpx.RequestError as e:
        raise VigzoneAIError(
            f"Could not reach Ollama at {OLLAMA_BASE_URL}. Make sure Ollama is running "
            f"(`ollama serve`, or check it's running as a background service) — ({e})"
        ) from e

    if resp.status_code == 404:
        raise VigzoneAIError(
            f"Model \"{payload['model']}\" isn't pulled in Ollama yet. Run "
            f"`ollama pull {payload['model']}` in a terminal, then try again."
        )
    if resp.status_code != 200:
        raise VigzoneAIError(f"Ollama API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    reply = data["choices"][0]["message"]["content"]
    clean = trim_degeneration_tail(reply)
    if clean != reply.rstrip():
        logger.warning("Trimmed echo loop from non-streaming completion.")
        return clean
    if is_degenerate_text(reply):
        reply = clean or reply[: max(0, len(reply) // 3)].rstrip()
        reply += "\n\n_(Cut short — I started repeating myself. Mind rephrasing the question?)_"
    return reply
