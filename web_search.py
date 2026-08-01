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
import html as _html
from urllib.parse import parse_qs, unquote, urlparse
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

# Set WEB_SEARCH_ENABLED=false in .env to disable (default: enabled)
_WEB_SEARCH_ON = os.getenv("WEB_SEARCH_ENABLED", "true").lower() not in ("false", "0", "no")
_CONFIGURED_USER_TIMEZONE = os.getenv("USER_TIMEZONE", "").strip()
_WEATHER_FALLBACK_LOCATION = os.getenv("WEATHER_DEFAULT_LOCATION", "Colombo, Sri Lanka")

logger = logging.getLogger(__name__)

# ── Vigzone Real-Time Search v2 helpers ──────────────────────────────────────
# Keyless sources:
# - DuckDuckGo Instant Answer + HTML search
# - GDELT article search for latest/news/current events
# - Wikipedia summary for stable entities
# Optional future providers can be added without changing the chat layer.

def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = _html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _clean_ddg_url(value: str) -> str:
    value = _html.unescape(value or "").strip()
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    # DuckDuckGo redirect links often contain ?uddg=<real_url>
    try:
        parsed = urlparse(value)
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    except Exception:
        pass
    return value


def _is_news_like_query(query: str) -> bool:
    return bool(re.search(
        r"\b(latest|recent|today|now|breaking|news|headlines|update|happening|happened|announced|released|launched|"
        r"election|war|conflict|earthquake|flood|accident|score|result|match|game|sports|ipl|cricket|fifa|world cup|"
        r"president|prime minister|ceo|minister|current|new)\b",
        query or "",
        re.IGNORECASE,
    ))


def _is_stable_encyclopedic_query(query: str) -> bool:
    if _is_news_like_query(query):
        return False
    return bool(re.search(r"\b(who is|what is|explain|meaning of|definition of|history of)\b", query or "", re.IGNORECASE))


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

def _get_user_timezone_name() -> str:
    if _CONFIGURED_USER_TIMEZONE:
        return _CONFIGURED_USER_TIMEZONE
    local_tz = datetime.now().astimezone().tzinfo
    if isinstance(local_tz, ZoneInfo) and getattr(local_tz, "key", None):
        return local_tz.key
    return "UTC"



def _get_user_timezone() -> timezone | ZoneInfo:
    tz_name = _get_user_timezone_name()
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown USER_TIMEZONE %r; falling back to system local timezone", tz_name)
        local_tz = datetime.now().astimezone().tzinfo
        return local_tz if local_tz is not None else timezone.utc


def get_current_datetime() -> str:
    """Return a human-readable current date and time string in the configured timezone."""
    tz = _get_user_timezone()
    now = datetime.now(tz)
    return now.strftime("%d %B %Y, %I:%M %p %Z (%A)")


def get_datetime_injection(user_message: str) -> str:
    """
    Returns a strong date/time prefix to prepend directly to the user's message.
    This forces the local LLM to see the date IMMEDIATELY before the question,
    making it impossible to ignore (local models often ignore system prompts).
    """
    tz = _get_user_timezone()
    now = datetime.now(tz)
    date_str = now.strftime("%d %B %Y")
    time_str = now.strftime("%I:%M %p %Z")
    weekday = now.strftime("%A")
    year = now.strftime("%Y")
    month = now.strftime("%B")

    date_q = re.search(
        r"\b(date|time|day|year|month|today|what.s today|current date|"
        r"what year|what day|right now|currently|clock|timezone)\b",
        user_message,
        re.IGNORECASE,
    )

    if date_q:
        return (
            f"[SYSTEM DATETIME INJECTION — ANSWER THIS FIRST]\n"
            f"TODAY IS: {weekday}, {date_str}\n"
            f"CURRENT TIME: {time_str}\n"
            f"CURRENT YEAR: {year}\n"
            f"CURRENT MONTH: {month}\n"
            f"TIME ZONE: {_get_user_timezone_name()}\n"
            f"You MUST use this exact date and time in your answer. Do NOT say you don't know the date or time.\n"
            f"[END DATETIME INJECTION]\n\n"
        )
    return ""


# ── Search trigger detection ──────────────────────────────────────────────────

_REALTIME_PATTERNS = re.compile(
    r"("
    r"what.?s (the )?(current |today.?s )?(date|time|day|year|month)|"
    r"what (is |are )?(the )?(date|time|day|year|today)|"
    r"what (year|day|date|time) is it|"
    r"(current|today.?s) (date|time|day|year)|"
    r"tell me the (date|time|day|year)|"
    r"(date|time) (today|now|currently)|"
    r"\b(today|tonight|yesterday|right now|currently|current|latest|recent|now)\b|"
    r"this (week|month|year|morning|evening|afternoon|night)|"
    r"just (happened|announced|released|launched)|"
    r"\b(news|breaking|update|headlines)\b|"
    r"what.?s happening|what happened|who won|latest happenings|recent happenings|"
    r"\b(score|result|match|game)\b|"
    r"\b(price|stock|crypto|bitcoin|ethereum)\b|"
    r"exchange rate|how much (is|does|costs?)|"
    r"\b(weather|forecast|temperature|rain|humidity|wind|climate)\b|"
    r"who is (the )?(current |new )?(president|prime minister|ceo|head|minister)|"
    r"is .+ still (alive|ceo|president)|"
    r"\b(ipl|t20|cricket|fifa|nba|nfl|nhl|mlb|epl|olympics|ufc|formula 1|f1)\b|"
    r"world cup|premier league|formula 1|"
    r"\b(standings|ranking|leaderboard)\b|"
    r"\blkr\b|"
    r"(sri lanka|colombo).*(price|rate|news|today|weather|forecast)|"
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
    """
    Returns True if the user's query likely needs real-time web data.
    Keeps false-positive rate low by also checking no-search patterns.
    """
    if _NO_SEARCH_PATTERNS.search(query) and not re.search(r"\b(weather|forecast|date|time|today|now)\b", query, re.IGNORECASE):
        return False
    return bool(_REALTIME_PATTERNS.search(query))


def _is_weather_query(query: str) -> bool:
    return bool(re.search(r"\b(weather|forecast|temperature|rain|humidity|wind|climate)\b", query, re.IGNORECASE))


def _has_explicit_location(query: str) -> bool:
    location_hints = [
        r"\bin\s+[A-Z][a-z]+",
        r"\bfor\s+[A-Z][a-z]+",
        r"\bat\s+[A-Z][a-z]+",
        r"\b(sri lanka|colombo|kandy|galle|jaffna|london|new york|tokyo|delhi)\b",
    ]
    return any(re.search(pattern, query) for pattern in location_hints)


def _normalize_search_query(query: str) -> str:
    query = query.strip()
    if _is_weather_query(query) and not _has_explicit_location(query):
        return f"{query} in {_WEATHER_FALLBACK_LOCATION}"
    return query


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
    Robust enough for current DDG HTML variants.
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
        results: list[dict] = []

        # Preferred block parser.
        blocks = re.findall(r'<div class="result(?: results_links)?[\s\S]*?</div>\s*</div>', html, re.IGNORECASE)
        for block in blocks:
            title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block, re.IGNORECASE)
            if not title_match:
                continue
            url = _clean_ddg_url(title_match.group(1))
            title = _clean_html(title_match.group(2))
            snippet_match = re.search(r'class="result__snippet"[^>]*>([\s\S]*?)</a>', block, re.IGNORECASE)
            snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""
            if title and url:
                results.append({"title": title, "snippet": snippet, "url": url})
            if len(results) >= max_results:
                break

        # Fallback old parser.
        if not results:
            title_pattern = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.DOTALL | re.IGNORECASE)
            snippet_pattern = re.compile(r'class="result__snippet"[^>]*>([\s\S]*?)</a>', re.DOTALL | re.IGNORECASE)
            titles = title_pattern.findall(html)
            snippets = snippet_pattern.findall(html)
            for i, (url, title_html) in enumerate(titles[:max_results]):
                title = _clean_html(title_html)
                snippet = _clean_html(snippets[i] if i < len(snippets) else "")
                url = _clean_ddg_url(url)
                if title:
                    results.append({"title": title, "snippet": snippet, "url": url})

        # Deduplicate domains/URLs.
        deduped = []
        seen = set()
        for r in results:
            key = r.get("url") or r.get("title")
            if key and key not in seen:
                deduped.append(r)
                seen.add(key)
        return deduped[:max_results]

    except Exception as exc:
        logger.debug("DDG HTML search failed: %s", exc)
        return []


async def _gdelt_article_search(query: str, max_results: int = 5) -> list[dict]:
    """Keyless current-news search using GDELT Doc API."""
    if not _is_news_like_query(query):
        return []
    try:
        client = _get_search_client()
        resp = await client.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": query,
                "mode": "ArtList",
                "format": "json",
                "maxrecords": max_results,
                "sort": "HybridRel",
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        rows = []
        for item in (data.get("articles") or [])[:max_results]:
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            source = (item.get("sourceCommonName") or item.get("domain") or "").strip()
            seen_date = (item.get("seendate") or "").strip()
            if title and url:
                rows.append({
                    "title": title,
                    "snippet": f"{source} · {seen_date}".strip(" ·"),
                    "url": url,
                })
        return rows
    except Exception as exc:
        logger.debug("GDELT search failed: %s", exc)
        return []


async def _wikipedia_summary(query: str) -> Optional[str]:
    """Keyless encyclopedia fallback for stable 'who/what is' questions."""
    if not _is_stable_encyclopedic_query(query):
        return None
    try:
        topic = re.sub(r"^\s*(who|what)\s+is\s+", "", query, flags=re.IGNORECASE)
        topic = re.sub(r"\?.*$", "", topic).strip()
        if not topic or len(topic) > 80:
            return None
        client = _get_search_client()
        resp = await client.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + topic.replace(" ", "_"),
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        extract = (data.get("extract") or "").strip()
        page = (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", "")
        if extract:
            return f"{extract}\nSource: {page}"
    except Exception as exc:
        logger.debug("Wikipedia summary failed: %s", exc)
    return None


async def web_search(query: str, max_results: int = 5) -> str:
    """
    Main search entry point.
    Uses multiple keyless live sources:
    - DuckDuckGo instant answer
    - DuckDuckGo HTML results
    - GDELT article search for current news
    - Wikipedia summary for stable entities
    Returns a formatted context block for the model.
    """
    normalized_query = _normalize_search_query(query)

    tasks = [
        asyncio.create_task(_ddg_instant_answer(normalized_query)),
        asyncio.create_task(_ddg_html_search(normalized_query, max_results)),
        asyncio.create_task(_gdelt_article_search(normalized_query, max_results)),
        asyncio.create_task(_wikipedia_summary(normalized_query)),
    ]
    instant, html_results, gdelt_results, wiki = await asyncio.gather(*tasks, return_exceptions=True)

    if isinstance(instant, Exception):
        instant = None
    if isinstance(html_results, Exception):
        html_results = []
    if isinstance(gdelt_results, Exception):
        gdelt_results = []
    if isinstance(wiki, Exception):
        wiki = None

    parts = []

    if instant:
        parts.append(f"📌 Direct/summary result:\n{instant}")

    if wiki:
        parts.append(f"📚 Encyclopedia context:\n{wiki}")

    # Merge news and web results, preserving fresh GDELT first for current queries.
    merged = []
    seen = set()
    for source_rows, label in ((gdelt_results or [], "Current/news result"), (html_results or [], "Web result")):
        for r in source_rows:
            key = r.get("url") or r.get("title")
            if key and key not in seen:
                merged.append((label, r))
                seen.add(key)

    if merged:
        lines = [f"🔍 Live web results for \"{normalized_query}\" (use these as current context, not as guaranteed truth):"]
        for i, (label, r) in enumerate(merged[:max_results], 1):
            lines.append(f"{i}. **{r['title']}**")
            if r.get("snippet"):
                lines.append(f"   {r['snippet']}")
            if r.get("url"):
                lines.append(f"   Source: {r['url']}")
        parts.append("\n".join(lines))

    if not parts:
        return ""

    return "\n\n".join(parts)


async def search_evidence(query: str, max_results: int = 6) -> list[dict]:
    """Return structured, attributable search evidence for API/UI use.

    Search snippets are leads, not proof.  This function deliberately does not
    fabricate a confidence percentage or a true/false verdict.
    """

    normalized_query = _normalize_search_query(query)[:500]
    html_task = asyncio.create_task(_ddg_html_search(normalized_query, max_results))
    news_task = asyncio.create_task(_gdelt_article_search(normalized_query, max_results))
    html_results, news_results = await asyncio.gather(
        html_task,
        news_task,
        return_exceptions=True,
    )
    if isinstance(html_results, Exception):
        html_results = []
    if isinstance(news_results, Exception):
        news_results = []

    from urllib.parse import urlparse

    evidence: list[dict] = []
    seen: set[str] = set()
    for source_kind, rows in (
        ("news", news_results or []),
        ("web", html_results or []),
    ):
        for row in rows:
            url = str(row.get("url") or "").strip()
            try:
                parsed = urlparse(url)
            except ValueError:
                continue
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if url in seen:
                continue
            seen.add(url)
            evidence.append({
                "title": _clean_html(str(row.get("title") or ""))[:300],
                "snippet": _clean_html(str(row.get("snippet") or ""))[:1000],
                "url": url[:2000],
                "source": parsed.netloc.lower(),
                "kind": source_kind,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            })
            if len(evidence) >= max_results:
                return evidence
    return evidence


# ── High-level helper for vigzone_ai.py ──────────────────────────────────────

async def get_realtime_context(user_message: str) -> tuple[str, str]:
    """
    Returns (system_block, user_prefix).

    system_block  → injected as a system message (general context)
    user_prefix   → prepended DIRECTLY to the user's message text so the
                    local LLM sees it immediately before the question and
                    cannot ignore it (local models often skip system prompts)
    """
    now_str = get_current_datetime()
    needs_datetime = bool(
        re.search(
            r"\b(what(?:'s| is)?\s+(?:the\s+)?(?:time|date|day)|current\s+(?:time|date|day)|today|tonight|tomorrow|yesterday|now|clock|timezone|time zone|when is)\b",
            user_message,
            re.IGNORECASE,
        )
    )
    user_prefix = get_datetime_injection(user_message) if needs_datetime else ""
    normalized_query = _normalize_search_query(user_message)

    system_lines = [
        f"[REAL-TIME CONTEXT]\n"
        f"Configured user time zone: {_get_user_timezone_name()}\n"
        f"Current date/time is available but must only be mentioned when the user asks for it or the answer depends on it. "
        f"Real-time web access is available only when WEB_SEARCH_ENABLED is true and the server has internet connectivity."
    ]
    if needs_datetime:
        system_lines.append(f"Current date and time: {now_str}")

    if _WEB_SEARCH_ON and should_search(user_message):
        logger.info("Web search triggered for: %s", normalized_query[:80])
        try:
            results = await asyncio.wait_for(web_search(normalized_query), timeout=8.0)
            if results:
                system_lines.append(results)
        except asyncio.TimeoutError:
            logger.warning("Web search timed out for query: %s", normalized_query[:80])
        except Exception as exc:
            logger.warning("Web search error: %s", exc)

    system_lines.append(
        "Use the above real-time information only when it directly answers the user. "
        "Do not mention the current date/time unless asked. "
        "Do not mention or reference this context block to the user — just answer naturally."
    )

    return "\n\n".join(system_lines), user_prefix


# ── Real image search (for website builds) ──────────────────────────────────
# Uses the Openverse API — a free, keyless search over openly-licensed images
# (openverse.org, run by WordPress/Creative Commons). No account needed for
# light personal use. This exists specifically so Vigzone can hand the model
# REAL, working image URLs for a website request instead of asking the model
# to invent a path or hand-encode an SVG data URI — both of which are common
# failure points for small local models (fabricated "car1.jpg" paths, or
# malformed percent-encoded SVG markup that breaks the <img> tag).
#
# Optional: set OPENVERSE_CLIENT_ID / OPENVERSE_CLIENT_SECRET in .env for a
# free registered API key (higher rate limits at https://openverse.org/api).
# Works fine without one for occasional/personal use.

_OPENVERSE_URL = "https://api.openverse.org/v1/images/"
_OPENVERSE_TOKEN_URL = "https://api.openverse.org/v1/auth_tokens/token/"
_OPENVERSE_CLIENT_ID = os.getenv("OPENVERSE_CLIENT_ID", "").strip()
_OPENVERSE_CLIENT_SECRET = os.getenv("OPENVERSE_CLIENT_SECRET", "").strip()

_openverse_token: Optional[str] = None

# Generic filler words stripped out so the image query stays on-subject
# ("build me a website for my bakery" → "bakery").
_IMAGE_QUERY_STOPWORDS = re.compile(
    r"\b(build|make|create|design|generate|write|code|develop|need|want|"
    r"can you|please|i want|i need|a|an|the|for|my|me|to|of|with|using|"
    r"website|webpage|web page|site|homepage|home page|landing page|"
    r"page|app|application|system|platform|project|please build|about)\b",
    re.IGNORECASE,
)


def _extract_image_query(user_message: str) -> str:
    """Strip website-building filler words down to the core subject."""
    cleaned = _IMAGE_QUERY_STOPWORDS.sub(" ", user_message)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?")
    return cleaned if cleaned else user_message.strip()


async def _get_openverse_token() -> Optional[str]:
    """Fetch and cache an OAuth token if credentials are configured; else None (anonymous use)."""
    global _openverse_token
    if not (_OPENVERSE_CLIENT_ID and _OPENVERSE_CLIENT_SECRET):
        return None
    if _openverse_token:
        return _openverse_token
    try:
        client = _get_search_client()
        resp = await client.post(
            _OPENVERSE_TOKEN_URL,
            data={
                "client_id": _OPENVERSE_CLIENT_ID,
                "client_secret": _OPENVERSE_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
        )
        if resp.status_code == 200:
            _openverse_token = resp.json().get("access_token")
            return _openverse_token
    except Exception as exc:
        logger.debug("Openverse token fetch failed: %s", exc)
    return None


async def image_search(query: str, max_results: int = 6) -> list[dict]:
    """
    Search Openverse for real, openly-licensed photographs matching `query`.
    Returns a list of {url, title, creator, license} dicts — `url` is a
    direct, hotlinkable image URL safe to drop straight into an <img> tag.
    Returns [] on any failure (network down, rate-limited, no results) so
    callers can gracefully fall back to placeholders.
    """
    try:
        client = _get_search_client()
        headers = {}
        token = await _get_openverse_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = await client.get(
            _OPENVERSE_URL,
            params={
                "q": query,
                "page_size": max_results,
                "category": "photograph",
                "license_type": "commercial,modification",
            },
            headers=headers,
        )
        if resp.status_code != 200:
            logger.debug("Openverse search returned %s for %r", resp.status_code, query)
            return []

        data = resp.json()
        out = []
        for item in data.get("results", [])[:max_results]:
            url = item.get("url")
            if not url:
                continue
            out.append({
                "url": url,
                "title": (item.get("title") or query).strip()[:60],
                "creator": item.get("creator", ""),
                "license": item.get("license", ""),
            })
        return out
    except Exception as exc:
        logger.debug("Openverse image search failed: %s", exc)
        return []


async def get_image_search_context(user_message: str, max_results: int = 6) -> str:
    """
    High-level helper for vigzone_ai.py: given the user's website request,
    search for real matching images and return a formatted system-prompt
    block listing exact URLs the model should use verbatim. Returns "" if
    search is disabled, fails, or finds nothing (caller falls back to the
    inline-SVG-placeholder instructions already in the website prompt).
    """
    if not _WEB_SEARCH_ON:
        return ""

    query = _extract_image_query(user_message)
    try:
        results = await asyncio.wait_for(image_search(query, max_results), timeout=8.0)
    except asyncio.TimeoutError:
        logger.warning("Image search timed out for query: %s", query[:80])
        return ""
    except Exception as exc:
        logger.warning("Image search error: %s", exc)
        return ""

    if not results:
        return ""

    lines = [
        "[REAL IMAGES AVAILABLE — USE THESE EXACT URLS]",
        f"Real, openly-licensed photos matching \"{query}\" were found. Use these ",
        "EXACT URLs verbatim in <img src=\"...\"> tags (or CSS background-image) ",
        "wherever a photo fits the design — copy them character-for-character, ",
        "do not modify, shorten, or re-encode them. Match each image to the most ",
        "relevant section/product/item by its title. If you need more images than ",
        "are listed, reuse the closest-matching one rather than inventing a new ",
        "path or hand-writing an SVG data URI.",
        "",
    ]
    for i, r in enumerate(results, 1):
        credit = f" (by {r['creator']})" if r.get("creator") else ""
        lines.append(f"{i}. \"{r['title']}\"{credit} — {r['url']}")
    lines.append("")
    lines.append(
        "Only fall back to an inline SVG placeholder (see IMAGES rules above) "
        "for anything none of these photos reasonably fit."
    )

    return "\n".join(lines)
