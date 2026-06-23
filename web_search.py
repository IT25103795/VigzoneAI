"""
Vigzone AI - Real-Time Web Search
===================================
Gives Vigzone access to the live internet using DuckDuckGo's Instant Answer
API and HTML scraping — no API key or account required.

Also provides:
  - get_current_datetime()  →  current date, time, timezone string
  - should_search(query)    →  True if the query needs live/real-time info
  - search_and_format(query)→  formatted context block to inject into prompt
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional
import httpx

# Set WEB_SEARCH_ENABLED=false in .env to disable (default: enabled)
_WEB_SEARCH_ON = os.getenv("WEB_SEARCH_ENABLED", "true").lower() not in ("false", "0", "no")

logger = logging.getLogger(__name__)

# ── HTTP client (shared, reused) ──────────────────────────────────────────────
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
    """Return a human-readable current date and time string (UTC)."""
    now = datetime.now(timezone.utc)
    return now.strftime("%-d %B %Y, %H:%M UTC (%A)")


def get_datetime_injection(user_message: str) -> str:
    """
    Returns a strong date/time prefix to prepend directly to the user's message.
    This forces the local LLM to see the date IMMEDIATELY before the question,
    making it impossible to ignore (local models often ignore system prompts).
    """
    now = datetime.now(timezone.utc)
    date_str   = now.strftime("%-d %B %Y")
    time_str   = now.strftime("%H:%M UTC")
    weekday    = now.strftime("%A")
    year       = now.strftime("%Y")
    month      = now.strftime("%B")

    # Detect if this is a date/time question to give extra emphasis
    date_q = re.search(
        r"\b(date|time|day|year|month|today|what.s today|current date|"
        r"what year|what day|right now|currently)\b",
        user_message, re.IGNORECASE
    )

    if date_q:
        return (
            f"[SYSTEM DATETIME INJECTION — ANSWER THIS FIRST]\n"
            f"TODAY IS: {weekday}, {date_str}\n"
            f"CURRENT TIME: {time_str}\n"
            f"CURRENT YEAR: {year}\n"
            f"CURRENT MONTH: {month}\n"
            f"You MUST use this exact date in your answer. Do NOT say you don't know the date.\n"
            f"[END DATETIME INJECTION]\n\n"
        )
    else:
        return f"[Current date: {weekday}, {date_str} | Time: {time_str}]\n\n"


# ── Search trigger detection ──────────────────────────────────────────────────

# Patterns that strongly suggest the user wants live/current information.
_REALTIME_PATTERNS = re.compile(
    r"("
    # Date / time questions — very broad to catch all phrasings
    r"what.?s (the )?(current |today.?s )?(date|time|day|year|month)|"
    r"what (is |are )?(the )?(date|time|day|year|today)|"
    r"what (year|day|date|time) is it|"
    r"(current|today.?s) (date|time|day|year)|"
    r"tell me the (date|time|day|year)|"
    r"(date|time) (today|now|currently)|"
    r"\b(today|tonight|yesterday|right now|currently|current|latest|recent)\b|"
    r"this (week|month|year|morning|evening|afternoon|night)|"
    r"just (happened|announced|released|launched)|"
    # News / events
    r"\b(news|breaking|update|headlines)\b|"
    r"what.?s happening|what happened|who won|"
    r"\b(score|result|match|game)\b|"
    # Prices / markets
    r"\b(price|stock|crypto|bitcoin|ethereum)\b|"
    r"exchange rate|how much (is|does|costs?)|"
    # Weather
    r"\b(weather|forecast)\b|"
    # People / positions
    r"who is (the )?(current |new )?(president|prime minister|ceo|head|minister)|"
    r"is .+ still (alive|ceo|president)|"
    # Sports
    r"\b(ipl|t20|cricket|fifa|nba|nfl)\b|"
    r"world cup|premier league|formula 1|"
    r"\b(standings|ranking|leaderboard)\b|"
    # Sri Lanka specific
    r"\blkr\b|"
    r"(sri lanka|colombo).*(price|rate|news|today)|"
    # General live data
    r"(election|vote|poll) result"
    r")",
    re.IGNORECASE,
)

# Patterns that are definitely NOT searches (pure knowledge/creative tasks)
# NOTE: "current" removed so "current date" isn't blocked
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
    """
    Returns True if the user's query likely needs real-time web data.
    Keeps false-positive rate low by also checking no-search patterns.
    """
    if _NO_SEARCH_PATTERNS.search(query):
        return False
    return bool(_REALTIME_PATTERNS.search(query))


# ── DuckDuckGo Search ─────────────────────────────────────────────────────────

async def _ddg_instant_answer(query: str) -> Optional[str]:
    """
    Try DuckDuckGo Instant Answer API first — returns a clean abstract if
    DDG has a direct answer (Wikipedia summaries, calculations, etc.).
    """
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
        # Related topics (top 3)
        for t in data.get("RelatedTopics", [])[:3]:
            if isinstance(t, dict) and t.get("Text"):
                parts.append(t["Text"])
        return "\n".join(parts) if parts else None
    except Exception as exc:
        logger.debug("DDG instant answer failed: %s", exc)
        return None


async def _ddg_html_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Scrape DuckDuckGo HTML results page to get title + snippet + URL.
    Returns a list of {title, snippet, url} dicts.
    """
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
        results = []

        # Extract result blocks using regex (avoids heavy HTML parser dependency)
        # DDG HTML structure: <div class="result__body"> ... </div>
        # Title: <a class="result__a" href="...">Title</a>
        # Snippet: <a class="result__snippet">snippet</a>

        title_pattern = re.compile(
            r'class="result__a"[^>]*>([^<]+)</a>', re.DOTALL
        )
        snippet_pattern = re.compile(
            r'class="result__snippet"[^>]*>(.+?)</a>', re.DOTALL
        )
        url_pattern = re.compile(
            r'class="result__url"[^>]*>([^<]+)<', re.DOTALL
        )

        titles = title_pattern.findall(html)
        snippets = snippet_pattern.findall(html)
        urls = url_pattern.findall(html)

        for i in range(min(max_results, len(titles))):
            title = re.sub(r"<[^>]+>", "", titles[i]).strip()
            snippet = re.sub(r"<[^>]+>", "", snippets[i] if i < len(snippets) else "").strip()
            url = urls[i].strip() if i < len(urls) else ""
            if title:
                results.append({"title": title, "snippet": snippet, "url": url})

        return results

    except Exception as exc:
        logger.debug("DDG HTML search failed: %s", exc)
        return []


async def web_search(query: str, max_results: int = 5) -> str:
    """
    Main search entry point. Tries DuckDuckGo Instant Answer first,
    then falls back to HTML search results. Returns a formatted string
    ready for injection into the LLM context.
    """
    # Run both in parallel for speed
    instant_task = asyncio.create_task(_ddg_instant_answer(query))
    html_task    = asyncio.create_task(_ddg_html_search(query, max_results))

    instant, html_results = await asyncio.gather(instant_task, html_task, return_exceptions=True)

    if isinstance(instant, Exception):
        instant = None
    if isinstance(html_results, Exception):
        html_results = []

    parts = []

    if instant:
        parts.append(f"📌 Summary:\n{instant}")

    if html_results:
        lines = [f"🔍 Web results for \"{query}\":"]
        for i, r in enumerate(html_results, 1):
            lines.append(f"{i}. **{r['title']}**")
            if r["snippet"]:
                lines.append(f"   {r['snippet']}")
            if r["url"]:
                lines.append(f"   {r['url']}")
        parts.append("\n".join(lines))

    if not parts:
        return ""

    return "\n\n".join(parts)


# ── High-level helper for vigzone_ai.py ──────────────────────────────────────

async def get_realtime_context(user_message: str) -> tuple[str, str]:
    """
    Returns (system_block, user_prefix).

    system_block  → injected as a system message (general context)
    user_prefix   → prepended DIRECTLY to the user's message text so the
                    local LLM sees it immediately before the question and
                    cannot ignore it (local models often skip system prompts)
    """
    now_str    = get_current_datetime()
    user_prefix = get_datetime_injection(user_message)

    system_lines = [
        f"[REAL-TIME CONTEXT]\n"
        f"Current date and time: {now_str}\n"
        f"You HAVE real-time internet access. You KNOW the current date and time. "
        f"NEVER say you don't know what date or time it is."
    ]

    if _WEB_SEARCH_ON and should_search(user_message):
        logger.info("Web search triggered for: %s", user_message[:80])
        try:
            results = await asyncio.wait_for(web_search(user_message), timeout=8.0)
            if results:
                system_lines.append(results)
        except asyncio.TimeoutError:
            logger.warning("Web search timed out for query: %s", user_message[:80])
        except Exception as exc:
            logger.warning("Web search error: %s", exc)

    system_lines.append(
        "Use the above real-time information to give accurate, current answers. "
        "Do not mention or reference this context block to the user — just answer naturally."
    )

    return "\n\n".join(system_lines), user_prefix
