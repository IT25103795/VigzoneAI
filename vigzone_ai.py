"""
Vigzone AI - Chat Engine
=========================
Conversational AI backend powered by Groq's hosted, OpenAI-compatible chat
completions API (https://api.groq.com/openai/v1). Runs from any server with
internet access — no local GPU, no Ollama install, no model to pull.

Modes:
  - TESTING mode  (APP_MODE=testing, default): unlimited messages, no token
    counting, no rate limits. For local development/testing.
  - PRODUCTION mode (APP_MODE=production): per-user token usage is tracked
    in SQLite, ready for billing/quota enforcement when you go worldwide.

Setup (one-time):
    1. Get a free API key at https://console.groq.com/keys
    2. Set GROQ_API_KEY in .env
    3. (Optional) override GROQ_MODEL / GROQ_VISION_MODEL — see
       https://console.groq.com/docs/models for the current list.

This build is Groq-only for hosted deployment. Ollama/free-local mode has
been removed so every chat uses either the default GROQ_API_KEY or the user's
own activated Groq API key.

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
from web_search import get_realtime_context, get_image_search_context
try:
    from realworld_data import get_realworld_context as get_realworld_data_context
    HAS_REALWORLD_DATA = True
except ImportError:
    HAS_REALWORLD_DATA = False

try:
    from website_builder import WebsiteRequest, WebsiteSystemPrompt, get_website_specific_params
    HAS_WEBSITE_BUILDER = True
except ImportError:
    HAS_WEBSITE_BUILDER = False

logger = logging.getLogger(__name__)


def _friendly_groq_error(status_code: int, body_text: str) -> str:
    """Turn a raw Groq error body into a short, user-facing message.

    Groq's error bodies are raw JSON meant for developers (e.g. the full
    429 rate-limit payload with org IDs and tier upsell links). Dumping that
    straight into the chat is confusing for end users, so we parse out just
    the useful bits: which limit was hit and how long until it resets.
    """
    try:
        parsed = json.loads(body_text)
        inner_message = parsed.get("error", {}).get("message", "")
    except (json.JSONDecodeError, AttributeError):
        inner_message = body_text

    if status_code == 429:
        # Groq's message includes a "Please try again in 17m22.848s" segment.
        wait_match = re.search(r"try again in ([\d.]+m[\d.]+s|[\d.]+s)", inner_message)
        wait_str = wait_match.group(1) if wait_match else None
        if "tokens per day" in inner_message.lower() or "TPD" in inner_message:
            base = "Vigzone AI has hit Groq's daily free-tier token limit for this model."
        elif "tokens per minute" in inner_message.lower() or "TPM" in inner_message:
            base = "Vigzone AI is sending messages a bit too fast for Groq's free tier."
        else:
            base = "Vigzone AI has hit Groq's rate limit."
        if wait_str:
            return f"{base} Please try again in about {wait_str}."
        return f"{base} Please wait a bit and try again."

    return f"Groq API error {status_code}: {inner_message[:300] or body_text[:300]}"


async def validate_groq_api_key(api_key: str) -> dict:
    """
    Lightweight check that a user-supplied Groq API key actually works.
    Hits Groq's /models list endpoint (cheap, no tokens consumed) rather
    than running a real chat completion.
    Returns {"valid": bool, "message": str}.
    """
    api_key = (api_key or "").strip()
    if not api_key:
        return {"valid": False, "message": "Please paste a Groq API key first."}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except httpx.RequestError as e:
        return {"valid": False, "message": f"Couldn't reach Groq to check the key ({e})."}

    if resp.status_code == 200:
        return {"valid": True, "message": "This Groq key works."}
    if resp.status_code == 401:
        return {"valid": False, "message": "Groq says this key is invalid or revoked."}
    if resp.status_code == 429:
        # The key itself is real (Groq authenticated it) — it's just already
        # rate-limited right now, which is still a "valid" key for our purposes.
        return {"valid": True, "message": "This Groq key works (it's currently rate-limited, but that's fine)."}
    return {"valid": False, "message": f"Groq returned an unexpected error (status {resp.status_code})."}


# ── Config ───────────────────────────────────────────────────────────────────
# Groq-only hosted backend.
#
# IMPORTANT: This build intentionally ignores any old AI_PROVIDER=ollama or
# OLLAMA_* variables that may still exist in your host's Variables panel. The
# default chat backend is always Groq, using the deployment's GROQ_API_KEY.
# A signed-in user can optionally activate their own Groq key to use their own
# quota instead of the deployment default.
_REQUESTED_AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").strip().lower()
if _REQUESTED_AI_PROVIDER != "groq":
    logger.warning("Ignoring AI_PROVIDER=%r; this build is Groq-only.", _REQUESTED_AI_PROVIDER)
AI_PROVIDER = "groq"

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Variable names are kept for backward compatibility with the rest of the code,
# but these now point to Groq's OpenAI-compatible endpoint, not Ollama.
OLLAMA_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
OLLAMA_API_URL  = f"{OLLAMA_BASE_URL}/chat/completions"
DEFAULT_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
VISION_MODEL    = os.getenv("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")
API_KEY         = _GROQ_API_KEY

_AUTH_HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

# Constants for the "bring your own Groq key" feature — these are used
# whenever a user has activated their own personal Groq key, REGARDLESS of
# what AI_PROVIDER the deployment defaults to for everyone else.
GROQ_BYOK_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_BYOK_API_URL  = f"{GROQ_BYOK_BASE_URL}/chat/completions"
GROQ_BYOK_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# The Groq (or other hosted) API key is SHARED across every user of this
# deployment — it is not a per-user quota. DAILY_TOKEN_LIMIT should match
# whatever your provider's daily token cap actually is (Groq's free tier is
# 100,000 tokens/day per model as of writing; check console.groq.com/settings/limits
# for your current plan) so the usage table can show remaining headroom.
DAILY_TOKEN_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", "100000"))

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
- For any substantial code answer (roughly 25+ lines, a full class/module, or \
  multiple files) — even outside website building — end with a brief 1-3 \
  sentence summary of what you implemented (the key pieces/functions and what \
  they do). Skip this for small snippets and one-liners; don't pad trivial \
  answers with a summary nobody asked for.
- When a code answer spans more than one file, put each file in its own \
  fenced code block and label it clearly right before the block (e.g. \
  "**main.py**" or "`UserService.java`") so each block maps to one \
  identifiable file — this lets the file be offered as a separate download \
  rather than one undifferentiated blob.

Building Websites & Web Apps — YOUR SIGNATURE STRENGTH:
- Website building is what you are best known for and best at. Treat every \
  request to build, design, or code a website, landing page, portfolio, web \
  app, or front-end UI as a real design brief — not a template to reskin.
- HARD RULE: never write `<link rel="stylesheet" href="...">` or `<script \
  src="...">` pointing at a separate file (styles.css, script.js, etc.) \
  unless you also print that file's complete content in the same response. \
  If you're not writing it out as a separate labeled file, put ALL CSS in \
  one `<style>` block in `<head>` and all JS in one `<script>` block before \
  `</body>`. A page that links a stylesheet you never wrote loads completely \
  unstyled — this is a common, avoidable failure.
- HARD RULE: if a page uses more than one inline SVG icon, every icon needs \
  a different shape/path. Never copy-paste the same icon for two different \
  features or list items — pick a shape that matches what each one means.
- Ground the design in the actual subject: what it's for, who it's for, and \
  the one job the page needs to do. If the request is vague, make a \
  concrete, sensible choice yourself and run with it rather than defaulting \
  to a generic "business website" look.
- Actively avoid the overused AI-generated design ruts: (1) warm cream \
  background with a serif headline and a terracotta accent, (2) near-black \
  background with one neon-green or vermilion accent and a card grid, (3) \
  broadsheet/newspaper layout with hairline rules and zero border-radius, \
  (4) purple-to-pink gradient hero with a generic "three feature cards" \
  layout. Use one of these ONLY if the user's own brief specifically calls \
  for it. Otherwise choose a palette, type pairing, and layout concept that \
  actually fits the subject, and give the page one deliberate, memorable \
  signature element instead of scattering effects everywhere.
- Always deliver complete, working, production-quality code in full — never \
  partial snippets, placeholder comments like "// add the rest here" or "// \
  repeat for other sections", or "the rest follows the same pattern" \
  shortcuts. Finish what you start, even if the answer runs long.
- Write real, specific copy for the subject — never "Lorem ipsum" or "Your \
  Company Name Here" placeholders.
- IMAGES: check first for a system message titled "[REAL IMAGES AVAILABLE — \
  USE THESE EXACT URLS]" — if present, it lists real, working photo URLs \
  found for this subject via live search; use those EXACT URLs verbatim in \
  `<img>` tags, copied character-for-character, matched to the closest \
  relevant section. If that block is absent (search disabled, offline, or no \
  matches), never invent an image URL or a local file path that doesn't \
  exist (e.g. "car1.jpg", "images/photo.png", or a made-up link) — it will \
  render as a broken image icon, since nothing actually lives at that path. \
  Instead use inline SVG placeholders as `<img>` sources, since they always \
  render with zero network calls. Example pattern to follow exactly — note \
  every tag is properly closed (`rect` self-closes with `/%3E`, `text` \
  closes with `%3C/text%3E`, and the whole thing ends with `%3C/svg%3E`), \
  only changing the width/height/label/colors to fit the design: \
  `<img src="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 \
  width=%27400%27 height=%27300%27%3E%3Crect width=%27100%25%27 height=%27100%25%27 \
  fill=%27%23ddd%27/%3E%3Ctext x=%2750%25%27 y=%2750%25%27 font-size=%2720%27 \
  text-anchor=%27middle%27 fill=%27%23888%27 dy=%27.3em%27%3ECar 1%3C/text%3E%3C/svg%3E" \
  alt="Car 1">`. Mention in your after-code summary whether images are real \
  photos or placeholders.
- Make it responsive by default — mobile-first layout, flexbox/CSS grid, and \
  media queries — so it looks right on phones, tablets, and desktops without \
  being asked.
- Use semantic HTML5 (header, nav, main, section, article, footer) and \
  accessible markup by default — alt text on images, sufficient color \
  contrast, visible focus states, and a logical heading order — not only when \
  the user explicitly asks for accessibility.
- Unless the user names a framework (React, Vue, Tailwind, etc.), default to \
  a single self-contained HTML file with embedded <style> and <script> tags \
  so it runs immediately in any browser with no build step or dependencies. \
  If they do name a stack, follow it exactly and don't substitute your own.
- Re-check the code in your head before sending it: every tag closed and \
  matched, valid CSS syntax, no undefined JS variables or functions, no \
  missing braces or semicolons where they matter. Accuracy matters more than \
  speed here — code that doesn't run is worse than no answer.
- After the code, give a short summary naming the signature design choice and \
  why it fits this subject, then suggest a couple of concrete next steps \
  (e.g. "want a dark mode toggle, a contact form, or a different color \
  scheme?") instead of a generic "let me know if you need anything else."
- For multi-page or multi-file builds, clearly label each file (e.g. \
  "index.html", "styles.css", "script.js") so the user can tell them apart \
  and knows exactly where each block of code goes.

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

    # Groq has no unauthenticated health endpoint to ping cheaply, so just
    # confirm an API key is present. The actual chat call will surface any
    # auth/network problem with a clear user-facing error.
    result = bool(API_KEY)

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

# Keywords that hint the user wants a website / web app / UI built — these
# need a much bigger token budget than ordinary long-form text, since a
# complete, professional single-file HTML+CSS+JS build easily runs well past
# 2000 tokens once it has real structure, styling, and interactivity.
# Includes casual, non-technical phrasing ("a site for my bakery", "online
# store", "menu page") so Vigzone catches website requests even when the
# user doesn't use web-dev jargon.
_WEBSITE_RE = re.compile(
    r"\b(web ?site|web ?page|web ?app|webapp|landing page|portfolio (?:site|page)|"
    r"home ?page|login page|signup page|dashboard ui|single[- ]page app|\bspa\b|"
    r"html5?|css3?|tailwind|bootstrap|front[- ]?end|web design|ui/?ux|"
    r"react (?:app|component|site)|vue (?:app|component)|"
    r"online store|web ?store|web ?shop|menu page|coming soon page|"
    r"(?:site|page) for my \w+|"
    r"\.html\b|index\.html)\b",
    re.IGNORECASE,
)

# Keywords that hint the user wants general code (not necessarily a website) —
# also benefits from a larger budget and different sampling settings than a
# normal chat answer, see _is_code_request().
_CODE_RE = re.compile(
    r"\b(function|class \w|script|program|algorithm|snippet|api endpoint|"
    r"refactor|debug|code for|code (?:to|that)|write (?:a|the) code|"
    r"python|javascript|typescript|java\b|c\+\+|c#|sql query|regex)\b",
    re.IGNORECASE,
)


# Short follow-ups like "continue" carry no topic keywords of their own, so
# on their own they'd fall through to the default 800-token budget even when
# they're asking the model to keep writing a long code/website reply that got
# cut off. Detect these and fall back to inspecting the last assistant reply
# (and the user message before that) instead of the literal "continue" text.
_CONTINUATION_RE = re.compile(
    r"^\s*(continue|keep going|go on|more|next|and then|carry on|"
    r"finish (?:it|that|this)|what('?s| is) next)[\s.!?]*$",
    re.IGNORECASE,
)


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            text = m.get("content")
            return text if isinstance(text, str) else ""
    return ""


def _effective_context_text(messages: list[dict]) -> str:
    """
    Text used to decide topic (website/code/long-form) for regex matching.
    Normally this is just the last user message. But a bare "continue" has
    no keywords of its own — so for those, pull in the prior assistant
    reply and the user message before it, which is where the real topic
    (e.g. a Java class, a website build) actually lives.
    """
    last_user = _last_user_text(messages)
    if not _CONTINUATION_RE.match(last_user or ""):
        return last_user

    # Walk backwards, skip the trailing "continue" message itself, then
    # grab the assistant reply it's continuing plus the user message that
    # originally prompted it.
    skipped_last_user = False
    extra = []
    for m in reversed(messages):
        role = m.get("role")
        content = m.get("content")
        content = content if isinstance(content, str) else ""
        if role == "user" and not skipped_last_user:
            skipped_last_user = True
            continue
        if role in ("assistant", "user"):
            extra.append(content)
        if role == "user" and skipped_last_user and len(extra) >= 2:
            break
    return (last_user + " " + " ".join(extra)).strip()


def _is_website_request(messages: list[dict]) -> bool:
    return bool(_WEBSITE_RE.search(_effective_context_text(messages)))


def _is_code_request(messages: list[dict]) -> bool:
    text = _effective_context_text(messages)
    return bool(_WEBSITE_RE.search(text) or _CODE_RE.search(text))


def _adaptive_max_tokens(messages: list[dict]) -> int:
    """Return a token budget based on what the user is asking for."""
    text = _effective_context_text(messages)
    if not text:
        return 800
    if _WEBSITE_RE.search(text):
        # Full website builds (HTML structure + CSS + JS) need substantial headroom
        # so complete, professional pages don't get cut off mid-tag or mid-script.
        # This budget supports full single-page apps with rich interactivity.
        return 8192
    if _CODE_RE.search(text):
        return 3000
    if _LONG_FORM_RE.search(text):
        return 2000
    return 800


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (good enough for tracking)."""
    return max(1, len(text) // 4)


async def _build_payload(messages: list[dict], model: str, stream: bool, user_name: Optional[str] = None) -> dict:
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
            # Try to use enhanced realworld_data module first, fall back to basic web_search
            if HAS_REALWORLD_DATA:
                realtime_block, user_prefix = await get_realworld_data_context(last_user)
            else:
                realtime_block, user_prefix = await get_realtime_context(last_user)
    except Exception as exc:
        logger.debug("Real-time context injection failed: %s", exc)
        realtime_block = ""
        user_prefix    = ""

    system_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject verified user identity from the authenticated account so the AI
    # always knows the user's real name without them having to say it.
    if user_name and user_name.strip():
        name_block = (
            f"The user's name is \"{user_name.strip()}\". "
            f"When they ask what their name is, reply directly — e.g. \"Your name is {user_name.strip()}.\" "
            f"Never say things like \"you told me earlier\", \"you verified your identity\", "
            f"\"according to your account\", or any similar phrasing. "
            f"Just state the name naturally and move on."
        )
        system_messages.append({"role": "system", "content": name_block})

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

    code_request = _is_code_request(messages)

    # Add website-specific system prompt if applicable, plus a real-time
    # image search so the model can use actual working photo URLs instead
    # of inventing paths or hand-encoding SVG data URIs (both are common
    # failure points for small local models).
    if HAS_WEBSITE_BUILDER and _is_website_request(messages):
        website_request = WebsiteRequest(_last_user_text(messages))
        if website_request.is_website_request:
            website_prompt = WebsiteSystemPrompt.generate_website_prompt(website_request)
            system_messages.append({"role": "system", "content": website_prompt})

            try:
                image_block = await get_image_search_context(_last_user_text(messages))
                if image_block:
                    system_messages.append({"role": "system", "content": image_block})
            except Exception as exc:
                logger.debug("Image search context injection failed: %s", exc)

    payload = {
        "model": effective_model,
        "messages": system_messages + patched_messages,
        "stream": stream,
        # Code/website requests get a lower, more deterministic temperature
        # (accuracy matters more than variety) and frequency/presence
        # penalties near zero — those penalties are great for prose but they
        # actively damage code, since code legitimately reuses the same
        # tokens over and over (closing tags, braces, indentation, repeated
        # class names) and a penalty pushes the model to avoid that, which is
        # how you end up with mismatched tags or broken syntax.
        "temperature": 0.4 if code_request else 0.7,
        "max_tokens": _adaptive_max_tokens(messages),
        "frequency_penalty": 0.0 if code_request else 0.6,
        "presence_penalty": 0.0 if code_request else 0.4,
    }

    return payload


# ── Token tracking (production mode only) ────────────────────────────────────
def track_token_usage(user_id: int, prompt_tokens: int, completion_tokens: int, provider: str = "groq") -> None:
    """
    Persist token usage to SQLite. Only called in production mode.
    The token_usage table is created by auth.init_db() — see auth.py.
    `provider` is 'groq' for both the default deployment key and a user's
    own activated Groq key.
    """
    if IS_TESTING:
        return
    try:
        import sqlite3, os as _os
        db_path = _os.getenv("VIGZONE_DB_PATH", _os.path.join("data", "vigzone.db"))
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO token_usage (user_id, prompt_tokens, completion_tokens, total_tokens, ts, provider)
                VALUES (?, ?, ?, ?, strftime('%s','now'), ?)
                """,
                (user_id, prompt_tokens, completion_tokens, prompt_tokens + completion_tokens, provider),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("token_usage write failed: %s", exc)


def get_user_daily_usage(user_id: int, has_own_key: bool) -> dict:
    """
    Return today's Groq usage for ONE signed-in user.

    No Ollama/free-local mode in this build. If the user has not activated
    their own key, chats use the deployment's default GROQ_API_KEY. If they
    have activated a key, chats use their own Groq quota. The usage numbers are
    Vigzone's estimates from messages it sends; Groq's own rate-limit response
    is still the final authority.

    "Today" resets at Sri Lanka local midnight (UTC+5:30) by default — set
    the USAGE_TZ_OFFSET_MINUTES env var to change this.
    """
    try:
        import sqlite3, os as _os
        from datetime import datetime, timezone, timedelta

        db_path = _os.getenv("VIGZONE_DB_PATH", _os.path.join("data", "vigzone.db"))
        tz_offset_minutes = int(_os.getenv("USAGE_TZ_OFFSET_MINUTES", "330"))
        local_tz = timezone(timedelta(minutes=tz_offset_minutes))
        now_local = datetime.now(local_tz)
        day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = int(day_start_local.timestamp())
        seconds_until_reset = int((day_start_local + timedelta(days=1)).timestamp()) - int(now_local.timestamp())

        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0)
                FROM token_usage
                WHERE user_id = ? AND provider = 'groq' AND ts >= ?
                """,
                (user_id, day_start),
            ).fetchone()

        used_today = row[0] if row else 0
        limit = DAILY_TOKEN_LIMIT
        return {
            "mode": "own_key" if has_own_key else "default_groq",
            "provider": "groq",
            "using_own_key": bool(has_own_key),
            "used_today": used_today,
            "daily_limit": limit,
            "remaining_today": max(limit - used_today, 0),
            "seconds_until_reset": max(seconds_until_reset, 0),
            "disclaimer": (
                "This is Vigzone's own estimate based on your messages, not a live reading "
                "from Groq's servers. A rate-limit error from Groq is always the real, final "
                "word on what's left, even if this shows plenty of room."
            ),
        }
    except Exception as exc:
        logger.warning("get_user_daily_usage failed: %s", exc)
        return {
            "mode": "own_key" if has_own_key else "default_groq",
            "provider": "groq",
            "using_own_key": bool(has_own_key),
            "used_today": 0,
            "daily_limit": DAILY_TOKEN_LIMIT,
            "remaining_today": DAILY_TOKEN_LIMIT,
            "seconds_until_reset": 0,
            "disclaimer": "",
        }


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
    user_name: Optional[str] = None,
    provider_override: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion token-by-token.

    `provider_override`, when given, is {"api_url": ..., "api_key": ...} for
    a user's own personal Groq key — used INSTEAD of the deployment's
    default AI_PROVIDER/API_KEY for this one call. This is how per-user
    "bring your own key" mode overrides the shared default without needing
    a server restart or affecting any other user's requests.
    """
    using_override = provider_override is not None
    effective_api_url = provider_override["api_url"] if using_override else OLLAMA_API_URL
    effective_headers = (
        {"Authorization": f"Bearer {provider_override['api_key']}"} if using_override else _AUTH_HEADERS
    )
    effective_provider_label = "groq"
    is_ollama_call = False

    payload = await _build_payload(messages, model, stream=True, user_name=user_name)
    client  = _get_client()

    # Estimate prompt tokens for tracking
    prompt_text = " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in payload["messages"]
    )
    prompt_tokens = _estimate_tokens(prompt_text)

    try:
        async with client.stream("POST", effective_api_url, json=payload,
                                  headers={"Content-Type": "application/json", **effective_headers}) as resp:
            if resp.status_code == 404:
                body = await resp.aread()
                if is_ollama_call:
                    raise VigzoneAIError(
                        f"Model \"{payload['model']}\" isn't pulled yet. "
                        f"Run `ollama pull {payload['model']}` then try again. "
                        f"(Error: {body.decode(errors='ignore')[:200]})"
                    )
                raise VigzoneAIError(
                    f"Model \"{payload['model']}\" not found on Groq. "
                    f"Check GROQ_MODEL against https://console.groq.com/docs/models. "
                    f"(Error: {body.decode(errors='ignore')[:200]})"
                )
            if resp.status_code == 401:
                body = await resp.aread()
                raise VigzoneAIError(
                    "Groq rejected this API key. "
                    + ("Check the key you entered in Settings." if using_override else "Check GROQ_API_KEY in .env.")
                    + f" (Error: {body.decode(errors='ignore')[:200]})"
                )
            if resp.status_code != 200:
                body = await resp.aread()
                raise VigzoneAIError(
                    _friendly_groq_error(resp.status_code, body.decode(errors="ignore"))
                    if not is_ollama_call else
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

                # NOTE: .get("choices", [{}]) only supplies the default when
                # the key is *missing*. Ollama sometimes streams a valid SSE
                # chunk where "choices" is present but an EMPTY list (e.g. a
                # trailing chunk right before [DONE]). In that case .get()
                # returns [] as-is, and [][0] raises an uncaught IndexError
                # that silently kills the whole stream with zero content and
                # no error shown - this is the actual cause of the frontend's
                # generic "No response received." error, independent of
                # message length or context size.
                choices = chunk.get("choices") or [{}]
                delta   = choices[0].get("delta", {})
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
                track_token_usage(user_id, prompt_tokens, completion_tokens, provider=effective_provider_label)

    except httpx.RequestError as e:
        if is_ollama_call:
            raise VigzoneAIError(
                f"Could not reach Ollama at {OLLAMA_BASE_URL}. "
                f"Make sure Ollama is running (`ollama serve`) — ({e})"
            ) from e
        raise VigzoneAIError(
            f"Could not reach Groq. Check the server's internet connection "
            + ("and the API key you entered in Settings" if using_override else "and GROQ_API_KEY")
            + f" — ({e})"
        ) from e


# ── Non-streaming chat ────────────────────────────────────────────────────────
async def chat_once(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    provider_override: Optional[dict] = None,
) -> str:
    """Non-streaming convenience wrapper. Returns the full reply as one string.
    See stream_chat's docstring for what `provider_override` does."""
    using_override = provider_override is not None
    effective_api_url = provider_override["api_url"] if using_override else OLLAMA_API_URL
    effective_headers = (
        {"Authorization": f"Bearer {provider_override['api_key']}"} if using_override else _AUTH_HEADERS
    )
    effective_provider_label = "groq"
    is_ollama_call = False

    payload = await _build_payload(messages, model, stream=False, user_name=user_name)
    client  = _get_client()

    prompt_text   = " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in payload["messages"]
    )
    prompt_tokens = _estimate_tokens(prompt_text)

    try:
        resp = await client.post(
            effective_api_url, json=payload,
            headers={"Content-Type": "application/json", **effective_headers},
        )
    except httpx.RequestError as e:
        if is_ollama_call:
            raise VigzoneAIError(
                f"Could not reach Ollama at {OLLAMA_BASE_URL}. "
                f"Make sure Ollama is running (`ollama serve`) — ({e})"
            ) from e
        raise VigzoneAIError(
            f"Could not reach Groq. Check the server's internet connection "
            + ("and the API key you entered in Settings" if using_override else "and GROQ_API_KEY")
            + f" — ({e})"
        ) from e

    if resp.status_code == 404:
        if is_ollama_call:
            raise VigzoneAIError(
                f"Model \"{payload['model']}\" isn't pulled yet. "
                f"Run `ollama pull {payload['model']}` then try again."
            )
        raise VigzoneAIError(
            f"Model \"{payload['model']}\" not found on Groq. "
            f"Check GROQ_MODEL against https://console.groq.com/docs/models."
        )
    if resp.status_code == 401:
        raise VigzoneAIError(
            "Groq rejected this API key. "
            + ("Check the key you entered in Settings." if using_override else "Check GROQ_API_KEY in .env.")
        )
    if resp.status_code != 200:
        raise VigzoneAIError(
            _friendly_groq_error(resp.status_code, resp.text)
            if not is_ollama_call else
            f"Ollama API error {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise VigzoneAIError("Groq returned no choices in its response (empty completion).")
    reply = choices[0]["message"]["content"]
    clean = trim_degeneration_tail(reply)
    if clean != reply.rstrip():
        logger.warning("Trimmed echo loop from non-streaming completion.")
        reply = clean
    if is_degenerate_text(reply):
        reply = clean or reply[:max(0, len(reply) // 3)].rstrip()
        reply += "\n\n_(Cut short — I started repeating myself. Mind rephrasing?)_"

    if user_id and not IS_TESTING:
        track_token_usage(user_id, prompt_tokens, _estimate_tokens(reply), provider=effective_provider_label)

    return reply