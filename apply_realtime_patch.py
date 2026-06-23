"""
Vigzone AI — Real-Time Patch Installer
=======================================
Run this script from INSIDE your "Vigzone AI" project folder:

    cd "Vigzone AI"
    python apply_realtime_patch.py

It will:
  1. Write  web_search.py      (real-time web search + datetime injection)
  2. Patch  vigzone_ai.py      (inject datetime into every user message)
  3. Verify syntax of both files
  4. Print a confirmation

No pip installs needed — only uses httpx which is already in requirements.txt.
"""

import os, sys, ast, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

# ──────────────────────────────────────────────────────────────────────────────
WEB_SEARCH_PY = r'''"""
Vigzone AI - Real-Time Web Search
===================================
Gives Vigzone access to the live internet using DuckDuckGo — no API key needed.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional
import httpx

_WEB_SEARCH_ON = os.getenv("WEB_SEARCH_ENABLED", "true").lower() not in ("false", "0", "no")
logger = logging.getLogger(__name__)

_search_client: Optional[httpx.AsyncClient] = None

def _get_search_client() -> httpx.AsyncClient:
    global _search_client
    if _search_client is None or _search_client.is_closed:
        _search_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
    return _search_client


# ── Date / Time ───────────────────────────────────────────────────────────────

def get_current_datetime() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%d %B %Y, %H:%M UTC (%A)")


def get_datetime_injection(user_message: str) -> str:
    """
    Returns a strong prefix prepended DIRECTLY into the user message.
    Local LLMs (Ollama/gemma3) often ignore system prompts — putting the
    date inside the user turn forces them to read and use it.
    """
    now     = datetime.now(timezone.utc)
    date_s  = now.strftime("%d %B %Y")
    time_s  = now.strftime("%H:%M UTC")
    weekday = now.strftime("%A")
    year    = now.strftime("%Y")
    month   = now.strftime("%B")

    date_q = re.search(
        r"\b(date|time|day|year|month|today|what.?s today|current date|"
        r"what year|what day|right now|currently|the time|the date)\b",
        user_message, re.IGNORECASE
    )

    if date_q:
        return (
            f"<<<REALTIME_DATETIME>>>\n"
            f"TODAY IS: {weekday}, {date_s}\n"
            f"TIME NOW: {time_s}\n"
            f"YEAR: {year}  |  MONTH: {month}\n"
            f"INSTRUCTION: You MUST state this exact date/time in your reply. "
            f"Do NOT write [insert date] or say you don't know.\n"
            f"<<<END_REALTIME_DATETIME>>>\n\n"
        )
    else:
        return f"[Realtime: {weekday} {date_s}, {time_s}]\n\n"


# ── Search trigger patterns ───────────────────────────────────────────────────

_REALTIME_PATTERNS = re.compile(
    r"("
    r"what.?s (the )?(current |today.?s )?(date|time|day|year|month)|"
    r"what (is |are )?(the )?(date|time|day|year|today)|"
    r"what (year|day|date|time) is it|"
    r"(the |current |what.?s the )(time|date)|"
    r"tell me the (date|time|day|year)|"
    r"\b(today|tonight|yesterday|right now|currently|latest|recent)\b|"
    r"this (week|month|year|morning|evening|afternoon|night)|"
    r"just (happened|announced|released|launched)|"
    r"\b(news|breaking|update|headlines)\b|"
    r"what.?s happening|what happened|who won|"
    r"\b(score|result|match|game)\b|"
    r"\b(price|stock|crypto|bitcoin|ethereum)\b|"
    r"exchange rate|how much (is|does|costs?)|"
    r"\b(weather|forecast)\b|"
    r"who is (the )?(current |new )?(president|prime minister|ceo|head|minister)|"
    r"is .+ still (alive|ceo|president)|"
    r"\b(ipl|t20|cricket|fifa|nba|nfl)\b|"
    r"world cup|premier league|formula 1|"
    r"\b(standings|ranking|leaderboard)\b|"
    r"\blkr\b|"
    r"(sri lanka|colombo).*(price|rate|news|today)|"
    r"(election|vote|poll) result"
    r")",
    re.IGNORECASE,
)

_NO_SEARCH_PATTERNS = re.compile(
    r"\b("
    r"explain|how does .+ work|what is the (theory|concept|definition|meaning|formula)|"
    r"write (a|an|me)|draft|generate (a|an|some)|help me (write|code|fix)|"
    r"translate|code|program|calculate|solve|history of|who invented|who discovered|"
    r"summarize|review my|fix (this|my)|"
    r"what are (the )?(pros|cons|benefits|advantages|steps|types)|"
    r"how to (make|do|use|build|install|setup|configure|fix|learn)"
    r")\b",
    re.IGNORECASE,
)


def should_search(query: str) -> bool:
    if _NO_SEARCH_PATTERNS.search(query):
        return False
    return bool(_REALTIME_PATTERNS.search(query))


# ── DuckDuckGo Search ─────────────────────────────────────────────────────────

async def _ddg_instant_answer(query: str) -> Optional[str]:
    try:
        client = _get_search_client()
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        parts = []
        abstract = data.get("AbstractText", "").strip()
        if abstract:
            parts.append(abstract)
        answer = data.get("Answer", "").strip()
        if answer:
            parts.append(f"Direct answer: {answer}")
        for t in data.get("RelatedTopics", [])[:3]:
            if isinstance(t, dict) and t.get("Text"):
                parts.append(t["Text"])
        return "\n".join(parts) if parts else None
    except Exception as exc:
        logger.debug("DDG instant answer failed: %s", exc)
        return None


async def _ddg_html_search(query: str, max_results: int = 5) -> list:
    try:
        client = _get_search_client()
        resp = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "us-en"},
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        if resp.status_code != 200:
            return []
        html = resp.text
        title_pat   = re.compile(r'class="result__a"[^>]*>([^<]+)</a>', re.DOTALL)
        snippet_pat = re.compile(r'class="result__snippet"[^>]*>(.+?)</a>', re.DOTALL)
        url_pat     = re.compile(r'class="result__url"[^>]*>([^<]+)<', re.DOTALL)
        titles   = title_pat.findall(html)
        snippets = snippet_pat.findall(html)
        urls     = url_pat.findall(html)
        results  = []
        for i in range(min(max_results, len(titles))):
            title   = re.sub(r"<[^>]+>", "", titles[i]).strip()
            snippet = re.sub(r"<[^>]+>", "", snippets[i] if i < len(snippets) else "").strip()
            url     = urls[i].strip() if i < len(urls) else ""
            if title:
                results.append({"title": title, "snippet": snippet, "url": url})
        return results
    except Exception as exc:
        logger.debug("DDG HTML search failed: %s", exc)
        return []


async def web_search(query: str, max_results: int = 5) -> str:
    instant_task = asyncio.create_task(_ddg_instant_answer(query))
    html_task    = asyncio.create_task(_ddg_html_search(query, max_results))
    instant, html_results = await asyncio.gather(instant_task, html_task, return_exceptions=True)
    if isinstance(instant, Exception):
        instant = None
    if isinstance(html_results, Exception):
        html_results = []
    parts = []
    if instant:
        parts.append(f"Summary:\n{instant}")
    if html_results:
        lines = [f'Web results for "{query}":']
        for i, r in enumerate(html_results, 1):
            lines.append(f"{i}. {r['title']}")
            if r["snippet"]:
                lines.append(f"   {r['snippet']}")
            if r["url"]:
                lines.append(f"   {r['url']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


# ── Main entry point ──────────────────────────────────────────────────────────

async def get_realtime_context(user_message: str) -> tuple:
    """Returns (system_block, user_prefix)."""
    now_str     = get_current_datetime()
    user_prefix = get_datetime_injection(user_message)

    system_lines = [
        f"REAL-TIME CONTEXT\n"
        f"Current date and time: {now_str}\n"
        f"You have real-time internet access. You KNOW the current date and time. "
        f"NEVER say you don't know the date or time."
    ]

    if _WEB_SEARCH_ON and should_search(user_message):
        logger.info("Web search triggered for: %s", user_message[:80])
        try:
            results = await asyncio.wait_for(web_search(user_message), timeout=8.0)
            if results:
                system_lines.append(results)
        except asyncio.TimeoutError:
            logger.warning("Web search timed out")
        except Exception as exc:
            logger.warning("Web search error: %s", exc)

    system_lines.append(
        "Use the above real-time information naturally. "
        "Do NOT mention this context block to the user."
    )
    return "\n\n".join(system_lines), user_prefix
'''

# ──────────────────────────────────────────────────────────────────────────────
# Patch for vigzone_ai.py
# We find the _build_payload function and replace it entirely.
# ──────────────────────────────────────────────────────────────────────────────

OLD_IMPORT_BLOCK = "import stream_manager"

NEW_IMPORT_BLOCK = """import stream_manager
from web_search import get_realtime_context"""

OLD_BUILD_PAYLOAD = '''def _build_payload(messages: list[dict], model: str, stream: bool) -> dict:
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

    system_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memory_block:
        system_messages.append({"role": "system", "content": memory_block})

    return {
        "model": effective_model,
        "messages": system_messages + messages,
        "stream": stream,
        "temperature": 0.7,
        "max_tokens": _adaptive_max_tokens(messages),
        "frequency_penalty": 0.6,
        "presence_penalty": 0.4,
    }'''

NEW_BUILD_PAYLOAD = '''async def _build_payload(messages: list[dict], model: str, stream: bool) -> dict:
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

    # Real-time: get system block + user message prefix (date/time + web search)
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

    # Inject date/time DIRECTLY into the last user message so local LLMs can\'t skip it
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
    }'''

OLD_STREAM_CALL = "    payload = _build_payload(messages, model, stream=True)"
NEW_STREAM_CALL = "    payload = await _build_payload(messages, model, stream=True)"

OLD_ONCE_CALL   = "    payload = _build_payload(messages, model, stream=False)"
NEW_ONCE_CALL   = "    payload = await _build_payload(messages, model, stream=False)"


# ──────────────────────────────────────────────────────────────────────────────
def apply():
    ws_path  = os.path.join(HERE, "web_search.py")
    vai_path = os.path.join(HERE, "vigzone_ai.py")

    if not os.path.exists(vai_path):
        print("❌  vigzone_ai.py not found. Run this script from inside your 'Vigzone AI' folder.")
        sys.exit(1)

    # ── 1. Write web_search.py ────────────────────────────────────────────────
    with open(ws_path, "w", encoding="utf-8") as f:
        f.write(WEB_SEARCH_PY)
    print("✅  web_search.py  written")

    # ── 2. Patch vigzone_ai.py ────────────────────────────────────────────────
    with open(vai_path, "r", encoding="utf-8") as f:
        src = f.read()

    # Backup
    bak = vai_path + ".bak"
    shutil.copy2(vai_path, bak)

    changed = False

    # a) Add import if not already there
    if "from web_search import get_realtime_context" not in src:
        if OLD_IMPORT_BLOCK in src:
            src = src.replace(OLD_IMPORT_BLOCK, NEW_IMPORT_BLOCK, 1)
            changed = True
            print("✅  Import added to vigzone_ai.py")
        else:
            print("⚠️   Could not find import anchor in vigzone_ai.py — import may already exist or file differs")

    # b) Replace _build_payload (sync → async with realtime injection)
    if "async def _build_payload" not in src:
        if OLD_BUILD_PAYLOAD in src:
            src = src.replace(OLD_BUILD_PAYLOAD, NEW_BUILD_PAYLOAD, 1)
            changed = True
            print("✅  _build_payload patched to async with realtime injection")
        else:
            print("⚠️   _build_payload not found verbatim — it may already be patched, or your file differs.")
            print("     Check vigzone_ai.py manually and ensure _build_payload is async and calls get_realtime_context.")

    # c) Await the two callers
    if OLD_STREAM_CALL in src:
        src = src.replace(OLD_STREAM_CALL, NEW_STREAM_CALL, 1)
        changed = True
        print("✅  stream_chat caller updated to await _build_payload")

    if OLD_ONCE_CALL in src:
        src = src.replace(OLD_ONCE_CALL, NEW_ONCE_CALL, 1)
        changed = True
        print("✅  chat_once caller updated to await _build_payload")

    if changed:
        with open(vai_path, "w", encoding="utf-8") as f:
            f.write(src)

    # ── 3. Syntax check ───────────────────────────────────────────────────────
    print()
    all_ok = True
    for path in [ws_path, vai_path]:
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                ast.parse(f.read())
            print(f"✅  {name} — syntax OK")
        except SyntaxError as e:
            print(f"❌  {name} — SYNTAX ERROR: {e}")
            all_ok = False

    print()
    if all_ok:
        print("🎉  Patch applied successfully!")
        print("    Restart your Vigzone AI server: python app.py")
        print(f"    (Backup saved to {os.path.basename(bak)})")
    else:
        print("❌  Syntax errors detected. Restoring backup...")
        shutil.copy2(bak, vai_path)
        print(f"    vigzone_ai.py restored from {os.path.basename(bak)}")


if __name__ == "__main__":
    apply()
