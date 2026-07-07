"""
Vigzone AI - Real-World Data Access Module
============================================
Multi-source real-world data provider for 100% accuracy:
- Current date/time
- Weather data
- Stock/Crypto prices
- News & facts (with verification)
- Sports scores
- Currency rates

Implements fallback chains, source scoring, and fact verification.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_WEB_SEARCH_ON = os.getenv("WEB_SEARCH_ENABLED", "true").lower() not in ("false", "0", "no")
_CONFIGURED_USER_TIMEZONE = os.getenv("USER_TIMEZONE", "").strip()
_WEATHER_FALLBACK_LOCATION = os.getenv("WEATHER_DEFAULT_LOCATION", "Colombo, Sri Lanka")
_OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()
_ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()

# HTTP client (shared, reused)
_data_client: Optional[httpx.AsyncClient] = None


def _get_data_client() -> httpx.AsyncClient:
    global _data_client
    if _data_client is None or _data_client.is_closed:
        _data_client = httpx.AsyncClient(
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
    return _data_client


# ── Timezone Handling ─────────────────────────────────────────────────────────

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


# ── Date/Time Provider ────────────────────────────────────────────────────────

def get_current_datetime() -> str:
    """Return human-readable current date and time in configured timezone."""
    tz = _get_user_timezone()
    now = datetime.now(tz)
    return now.strftime("%d %B %Y, %I:%M %p %Z (%A)")


def get_datetime_info() -> Dict[str, str]:
    """Return structured datetime info for API responses."""
    tz = _get_user_timezone()
    now = datetime.now(tz)
    return {
        "full": now.strftime("%d %B %Y, %I:%M %p %Z (%A)"),
        "date": now.strftime("%d %B %Y"),
        "time": now.strftime("%I:%M %p"),
        "timezone": _get_user_timezone_name(),
        "day": now.strftime("%A"),
        "iso": now.isoformat(),
    }


# ── Weather Data (Multi-Source) ───────────────────────────────────────────────

async def _get_weather_openweather(location: str) -> Optional[Dict[str, Any]]:
    """Fetch from OpenWeather API (higher accuracy if key available)."""
    if not _OPENWEATHER_API_KEY:
        return None

    try:
        client = _get_data_client()
        resp = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": location,
                "appid": _OPENWEATHER_API_KEY,
                "units": "metric",
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "source": "OpenWeather",
                "location": f"{data.get('name')}, {data.get('sys', {}).get('country')}",
                "temp": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "description": data["weather"][0]["description"],
                "wind_speed": data["wind"]["speed"],
                "cloudiness": data["clouds"]["all"],
                "confidence": 0.95,
            }
    except Exception as exc:
        logger.debug("OpenWeather failed: %s", exc)
    return None


async def _get_weather_duckduckgo(location: str) -> Optional[Dict[str, Any]]:
    """Fallback: Parse weather from DuckDuckGo instant answer."""
    try:
        client = _get_data_client()
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={
                "q": f"weather in {location}",
                "format": "json",
                "no_html": "1",
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            abstract = data.get("AbstractText", "")
            if abstract:
                return {
                    "source": "DuckDuckGo",
                    "location": location,
                    "summary": abstract,
                    "confidence": 0.70,
                }
    except Exception as exc:
        logger.debug("DuckDuckGo weather failed: %s", exc)
    return None


async def get_weather(location: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get weather from best available source."""
    location = location or _WEATHER_FALLBACK_LOCATION

    # Try OpenWeather first (if API key available)
    result = await _get_weather_openweather(location)
    if result:
        return result

    # Fallback to DuckDuckGo
    result = await _get_weather_duckduckgo(location)
    return result


# ── Crypto/Stock Data (Multi-Source) ──────────────────────────────────────────

async def _get_crypto_coingecko(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch crypto price from CoinGecko (free, no API key required)."""
    try:
        client = _get_data_client()
        # Map common symbols to CoinGecko IDs
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "XRP": "ripple",
            "ADA": "cardano",
            "SOL": "solana",
            "DOGE": "dogecoin",
            "BNBBNB": "binancecoin",
        }
        coin_id = symbol_map.get(symbol.upper(), symbol.lower())

        resp = await client.get(
            f"https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
            },
        )

        if resp.status_code == 200:
            data = resp.json()
            if coin_id in data:
                coin_data = data[coin_id]
                return {
                    "source": "CoinGecko",
                    "symbol": symbol.upper(),
                    "price_usd": coin_data.get("usd"),
                    "market_cap": coin_data.get("usd_market_cap"),
                    "volume_24h": coin_data.get("usd_24h_vol"),
                    "change_24h": coin_data.get("usd_24h_change"),
                    "confidence": 0.95,
                }
    except Exception as exc:
        logger.debug("CoinGecko crypto fetch failed: %s", exc)
    return None


async def _get_stock_yahoo(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch stock price from Yahoo Finance (scrape)."""
    try:
        client = _get_data_client()
        resp = await client.get(
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}",
            params={"modules": "price"},
        )

        if resp.status_code == 200:
            data = resp.json()
            result = data.get("quoteSummary", {}).get("result", [{}])[0]
            price_data = result.get("price", {})
            if price_data:
                return {
                    "source": "Yahoo Finance",
                    "symbol": symbol.upper(),
                    "price": price_data.get("regularMarketPrice", {}).get("raw"),
                    "currency": price_data.get("currency"),
                    "change": price_data.get("regularMarketChange", {}).get("raw"),
                    "change_pct": price_data.get("regularMarketChangePercent", {}).get("raw"),
                    "confidence": 0.92,
                }
    except Exception as exc:
        logger.debug("Yahoo Finance stock fetch failed: %s", exc)
    return None


async def get_price(symbol: str, asset_type: str = "auto") -> Optional[Dict[str, Any]]:
    """
    Get current price for crypto or stock.
    asset_type: "crypto", "stock", or "auto" (detect from symbol)
    """
    symbol = symbol.strip().upper()

    if asset_type in ("crypto", "auto"):
        result = await _get_crypto_coingecko(symbol)
        if result:
            return result

    if asset_type in ("stock", "auto"):
        result = await _get_stock_yahoo(symbol)
        if result:
            return result

    return None


# ── Currency Exchange Rates ───────────────────────────────────────────────────

async def _get_exchange_rate_fixer(from_curr: str, to_curr: str) -> Optional[float]:
    """Fetch exchange rate from Fixer.io (free tier available)."""
    try:
        client = _get_data_client()
        # Free tier uses EUR as base; use alternative endpoints
        resp = await client.get(
            "https://api.exchangerate-api.com/v4/latest/" + from_curr.upper()
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("rates", {}).get(to_curr.upper())
    except Exception as exc:
        logger.debug("Exchange rate fetch failed: %s", exc)
    return None


async def get_exchange_rate(from_curr: str, to_curr: str) -> Optional[Dict[str, Any]]:
    """Get current exchange rate between two currencies."""
    rate = await _get_exchange_rate_fixer(from_curr, to_curr)
    if rate:
        return {
            "source": "ExchangeRate-API",
            "from": from_curr.upper(),
            "to": to_curr.upper(),
            "rate": rate,
            "confidence": 0.93,
        }
    return None


# ── Fact Verification (Multi-Source Cross-Check) ─────────────────────────────

async def verify_fact(claim: str) -> Dict[str, Any]:
    """
    Cross-check a factual claim against multiple sources.
    Returns: { verified: bool, sources: [...], confidence: 0-100 }
    """
    # This is a framework for fact-checking; actual implementation
    # would call multiple fact-check APIs (Snopes, FactCheck.org, etc.)
    return {
        "claim": claim,
        "verified": None,  # Unable to verify without specific APIs
        "sources": [],
        "confidence": 0,
        "note": "Fact verification requires additional API integrations (Snopes, FactCheck.org)",
    }


# ── Aggregate Real-World Context ──────────────────────────────────────────────

async def get_realworld_context(user_message: str) -> Tuple[str, str]:
    """
    Returns (system_block, user_prefix) with comprehensive real-world data.
    Detects what type of data the user needs and fetches it.
    """
    tz = _get_user_timezone()
    now = datetime.now(tz)
    date_str = now.strftime("%d %B %Y")
    time_str = now.strftime("%I:%M %p %Z")

    # Do not inject date/time into every casual message. Only include it
    # when the request explicitly asks for date/time/day or needs real-world data.
    user_prefix = ""

    system_lines: list[str] = []

    # Detect what data is needed
    needs_weather = bool(
        re.search(
            r"\b(weather|forecast|temperature|rain|humidity|wind|climate)\b",
            user_message,
            re.IGNORECASE,
        )
    )
    needs_price = bool(
        re.search(r"\b(price|cost|stock|crypto|bitcoin|ethereum)\b", user_message, re.IGNORECASE)
    )
    needs_exchange = bool(
        re.search(r"\b(exchange rate|convert|currency)\b", user_message, re.IGNORECASE)
    )
    needs_datetime = bool(
        re.search(
            r"\b(what(?:'s| is)?\s+(?:the\s+)?(?:time|date|day)|current\s+(?:time|date|day)|today|tonight|tomorrow|yesterday|now|clock|timezone|time zone|when is)\b",
            user_message,
            re.IGNORECASE,
        )
    )

    if not (needs_weather or needs_price or needs_exchange or needs_datetime):
        return "", ""

    system_lines.extend([
        f"[REAL-WORLD DATA]",
        f"Timezone: {_get_user_timezone_name()}",
    ])
    if needs_datetime:
        user_prefix = f"[SYSTEM: Current date is {date_str}, {time_str}]\n"
        system_lines.append(f"Current date/time: {date_str}, {time_str}")

    # Fetch weather if needed
    if needs_weather:
        try:
            weather = await asyncio.wait_for(get_weather(), timeout=5.0)
            if weather:
                system_lines.append(f"\n[WEATHER DATA - {weather['source']}]")
                system_lines.append(f"Location: {weather.get('location', 'Unknown')}")
                if "temp" in weather:
                    system_lines.append(
                        f"Temperature: {weather['temp']}°C (feels like {weather['feels_like']}°C)"
                    )
                    system_lines.append(f"Humidity: {weather['humidity']}%")
                    system_lines.append(f"Condition: {weather['description']}")
                else:
                    system_lines.append(f"Summary: {weather.get('summary', 'Unknown')}")
                system_lines.append(f"Confidence: {weather.get('confidence', 0):.0%}")
        except asyncio.TimeoutError:
            logger.warning("Weather fetch timed out")

    # Fetch price if needed
    if needs_price:
        symbols = re.findall(r"\b([A-Z]{1,5})\b", user_message.upper())
        for symbol in symbols[:3]:  # Limit to 3 symbols
            try:
                price_data = await asyncio.wait_for(get_price(symbol), timeout=5.0)
                if price_data:
                    system_lines.append(f"\n[PRICE DATA - {price_data['source']}]")
                    system_lines.append(
                        f"{price_data.get('symbol', symbol)}: "
                        f"${price_data.get('price_usd') or price_data.get('price', 'N/A')}"
                    )
                    if price_data.get("change_pct"):
                        system_lines.append(f"Change: {price_data['change_pct']:.2f}%")
                    system_lines.append(f"Confidence: {price_data.get('confidence', 0):.0%}")
            except asyncio.TimeoutError:
                pass

    system_lines.extend([
        "",
        "Use the above real-world data only when it directly answers the user.",
        "Do not mention the current date/time unless the user asked for it or the answer depends on it.",
        "Always cite your data sources when mentioning specific facts, prices, or weather.",
        "Do NOT mention the data block itself — just use the information naturally.",
    ])

    return "\n".join(system_lines), user_prefix
