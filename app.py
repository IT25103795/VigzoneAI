"""
Vigzone AI - Web Server
========================
FastAPI backend serving the Vigzone AI chat interface.
Chat backend: Groq's hosted API (https://api.groq.com). This build is Groq-only; local-model mode is disabled.

Modes (set APP_MODE in .env):
  testing    → unlimited messages, no rate limits (default)
  production → token usage tracked per user in SQLite
"""

import logging
import os
import time
import io
import json
import zipfile
from datetime import datetime, timezone
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import List, Literal, Optional, Union, Any

from dotenv import load_dotenv

load_dotenv()

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from file_processing import (
    FileProcessingError,
    process_file,
    # Legacy single-type helpers kept for any internal callers
    extract_pdf_text,
    extract_plain_text,
    process_image,
)
from virus_scanner import scan_bytes as _virus_scan
from vigzone_ai import (
    AI_PROVIDER,
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    GROQ_BYOK_API_URL,
    GROQ_BYOK_MODEL,
    API_KEY,
    VISION_MODEL,
    IS_TESTING,
    VigzoneAIError,
    UsageLimitError,
    chat_once,
    get_user_token_stats,
    get_user_daily_usage,
    assert_user_can_chat,
    estimate_messages_tokens,
    is_configured,
    stream_chat,
    validate_groq_api_key,
)
from self_learning import add_interaction, prune_kb, sanitize_assistant_for_memory
from image_generation import generate_image, edit_image, ImageGenError
from web_search import _get_user_timezone_name
from stream_manager import (
    create_stream_id,
    register_stream,
    cancel_stream,
    is_cancelled,
    unregister_stream,
    pause_stream,
    resume_stream,
)
import auth as authmod
import secrets as _secrets
import httpx

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    removed = prune_kb()
    if removed:
        logger.info("Pruned %d corrupted knowledge-base entries on startup", removed)
    authmod.init_db()
    mode = "TESTING (unlimited)" if IS_TESTING else "PRODUCTION (token tracking ON)"
    logger.info("Vigzone AI started — mode: %s", mode)
    yield
    # Shutdown (nothing to clean up currently)


app = FastAPI(
    title="Vigzone AI API",
    description="A real conversational AI assistant — powered by Groq.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Upload config ─────────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE    = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(25 * 1024 * 1024)))
IMAGE_EXTENSIONS   = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


# ── Pydantic models ───────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, List[dict]] = Field(...)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    model: str = Field(default=DEFAULT_MODEL)
    ai_mode: Optional[str] = Field(default="general", max_length=40)
    workspace_id: Optional[int] = Field(default=None)


class HealthCheckResponse(BaseModel):
    status: str
    backend_configured: bool
    mode: str
    backend: str
    setup_message: str


class CapabilitiesResponse(BaseModel):
    internet_search_enabled: bool
    internet_access_configured: bool
    current_time_available: bool
    configured_timezone: str
    accuracy_note: str


class ModelInfoResponse(BaseModel):
    name: str
    version: str
    model: str
    vision_model: str
    backend: str
    status: str
    mode: str


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


class StreamControlRequest(BaseModel):
    stream_id: str = Field(...)


class ImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=800)
    size: Optional[str] = Field(default="1024x1024")


class EditImageRequest(BaseModel):
    image_data_uri: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1, max_length=800)
    size: Optional[str] = Field(default="1024x1024")


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str = Field(default="", max_length=600)
    mode: str = Field(default="general", max_length=40)


class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=600)
    mode: Optional[str] = Field(default=None, max_length=40)


class WorkspaceNoteRequest(BaseModel):
    title: str = Field(default="Note", max_length=120)
    content: str = Field(..., min_length=2, max_length=5000)
    kind: str = Field(default="note", max_length=30)


class FileIntelRequest(BaseModel):
    name: str = Field(default="file", max_length=180)
    kind: str = Field(default="document", max_length=30)
    text: str = Field(default="", max_length=60000)


class ExportRequest(BaseModel):
    title: str = Field(default="Vigzone Export", max_length=120)
    messages: List[dict] = Field(default_factory=list)
    format: Literal["txt", "html"] = "txt"


class WebsiteExportRequest(BaseModel):
    html: str = Field(..., min_length=1, max_length=500000)
    filename: str = Field(default="vigzone-website.zip", max_length=100)


# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_current_user(
    request: Request,
    vigzone_session: Optional[str] = Cookie(default=None),
) -> Optional[dict]:
    token = vigzone_session
    if not token:
        header = request.headers.get("authorization") or request.headers.get("Authorization")
        if header and header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip() or None
    return authmod.get_user_by_session(token)


def require_current_user(
    request: Request,
    vigzone_session: Optional[str] = Cookie(default=None),
) -> dict:
    # Cookie-based session is the canonical auth path, but the JS client
    # also stores the same token in localStorage (`vigzone_token`) and sends
    # it as `Authorization: Bearer <token>`. The frontend's Web Speech flow
    # only ships the bearer token, so without this fallback the voice→chat
    # request 401s and the user sees "trouble processing your voice message".
    token = vigzone_session
    if not token:
        header = request.headers.get("authorization") or request.headers.get("Authorization")
        if header and header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip() or None
    user = authmod.get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


# ── Production safety helpers ────────────────────────────────────────────────
_CHAT_RATE_LIMIT_PER_MINUTE = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "20"))
_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _check_chat_rate_limit(request: Request, user: dict) -> None:
    """Simple in-memory guard against spam. Works per process/deployment."""
    if IS_TESTING or _CHAT_RATE_LIMIT_PER_MINUTE <= 0:
        return
    now = time.monotonic()
    key = f"user:{user.get('id')}|ip:{_client_ip(request)}"
    bucket = _rate_windows[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= _CHAT_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many messages too quickly. Please wait a minute and try again.")
    bucket.append(now)


def require_admin(user: dict = Depends(require_current_user)) -> dict:
    if not authmod.is_admin_email(user.get("email", "")):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


AI_MODE_PROMPTS = {
    "general": "Mode: General Chat. Be helpful, direct, and accurate.",
    "website": "Mode: Website Studio. Prioritize modern responsive UI, complete runnable HTML/CSS/JS, strong visual hierarchy, mobile-first layout, CTAs, SEO basics, accessibility, and downloadable file structure when useful.",
    "code": "Mode: Code Fixer. Diagnose issues, explain the exact cause briefly, and provide complete corrected files or patches. Prefer runnable, production-safe code.",
    "study": "Mode: Study Helper. Teach clearly with exam-focused summaries, examples, quick revision, and practice questions where useful.",
    "file": "Mode: File Analyzer. Extract key facts, summarize, compare, find risks/errors, and give action items based only on the provided file content.",
    "business": "Mode: Business Writer. Write polished, persuasive, practical business content with clear structure and professional tone.",
    "voice": "Mode: Voice Assistant. Keep replies conversational, concise, and easy to listen to aloud.",
}


def _mode_context(mode: Optional[str]) -> str:
    key = (mode or "general").strip().lower()
    return AI_MODE_PROMPTS.get(key, AI_MODE_PROMPTS["general"])


def _combine_context(*parts: str) -> str:
    clean = [p.strip() for p in parts if p and p.strip()]
    return "\n\n".join(clean)


def _simple_file_intel(name: str, kind: str, text: str) -> dict:
    text = (text or "").strip()
    words = re.findall(r"[A-Za-z0-9_'-]+", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    preview = " ".join(lines[:10])[:900]
    # crude keyword extraction without extra dependencies
    stop = {"the","and","for","with","that","this","from","are","was","were","have","has","not","you","your","but","all","can","will","into","about","there","their","they","them","our","his","her","its","to","of","in","a","an","is","on","as","by","or","be","it"}
    freq = {}
    for w in words:
        lw = w.lower()
        if len(lw) >= 4 and lw not in stop:
            freq[lw] = freq.get(lw, 0) + 1
    keywords = [k for k,_ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]
    risks = []
    low = text.lower()
    for needle,label in [("error","Possible error references"),("failed","Failure references"),("todo","TODO items"),("password","Sensitive password/key mention"),("api_key","Sensitive API key mention"),("secret","Sensitive secret mention"),("deadline","Deadline mentioned")]:
        if needle in low:
            risks.append(label)
    if not text:
        summary = "No readable text was extracted from this file. Try asking Vigzone about the file directly, or upload a clearer text/PDF/DOCX/CSV file."
    else:
        summary = f"{name} contains about {len(words):,} words across {len(lines):,} non-empty lines. Main visible topics: {', '.join(keywords[:6]) or 'general content'}."
    return {
        "name": name,
        "kind": kind,
        "word_count": len(words),
        "line_count": len(lines),
        "keywords": keywords,
        "summary": summary,
        "preview": preview,
        "risks": risks,
        "suggested_prompts": [
            f"Summarize {name} in exam-ready bullet points.",
            f"Find mistakes, risks, and missing parts in {name}.",
            f"Create an action plan based on {name}.",
        ],
    }


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    cookie_secure = os.getenv("COOKIE_SECURE", "true" if os.getenv("APP_MODE", "testing").lower() == "production" else "false").lower() in ("1", "true", "yes", "on")
    response.set_cookie(
        key=authmod.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=authmod.SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


# ── System endpoints ──────────────────────────────────────────────────────────
def _backend_label() -> str:
    return "Groq (hosted)"


def _setup_message() -> str:
    return (
        "Groq isn't configured. Add a valid GROQ_API_KEY in your deployment "
        "environment variables, then redeploy/restart the app."
    )


@app.get("/health", response_model=HealthCheckResponse, tags=["System"])
async def health_check():
    configured = await is_configured()
    return HealthCheckResponse(
        status="healthy" if configured else "needs_setup",
        backend_configured=configured,
        mode="testing" if IS_TESTING else "production",
        backend=_backend_label(),
        setup_message="" if configured else _setup_message(),
    )


@app.get("/api/capabilities", response_model=CapabilitiesResponse, tags=["System"])
async def get_capabilities():
    internet_search_enabled = os.getenv("WEB_SEARCH_ENABLED", "true").lower() not in ("false", "0", "no")
    return CapabilitiesResponse(
        internet_search_enabled=internet_search_enabled,
        internet_access_configured=internet_search_enabled,
        current_time_available=True,
        configured_timezone=_get_user_timezone_name(),
        accuracy_note=(
            "Current time is generated by the server in the configured timezone. "
            "Live internet answers depend on actual network availability and source freshness, so 100% accuracy cannot be guaranteed."
        ),
    )


@app.get("/api/model-info", response_model=ModelInfoResponse, tags=["Model"])
async def get_model_info():
    return ModelInfoResponse(
        name="Vigzone AI",
        version="3.0.0",
        model=DEFAULT_MODEL,
        vision_model=VISION_MODEL,
        backend=_backend_label(),
        status="ready" if await is_configured() else "groq_not_configured",
        mode="testing" if IS_TESTING else "production",
    )


@app.get("/api/stats", tags=["System"])
async def get_stats():
    return JSONResponse({
        "name": "Vigzone AI",
        "version": "3.0.0",
        "mode": "testing" if IS_TESTING else "production",
        "description": "A real conversational AI assistant — powered by Groq",
        "endpoints": {
            "health": "/health",
            "capabilities": "/api/capabilities",
            "model_info": "/api/model-info",
            "realworld_data": "GET /api/realworld-data",
            "upload": "POST /api/upload",
            "chat_stream": "POST /api/chat",
            "cancel_stream": "POST /api/cancel-stream",
            "pause_stream": "POST /api/pause-stream",
            "resume_stream": "POST /api/resume-stream",
            "chat_sync": "POST /api/chat/sync",
            "generate_image": "POST /api/generate-image",
            "edit_image": "POST /api/edit-image",
            "token_usage": "GET /api/me/tokens",
            "usage_today": "GET /api/me/usage",
            "learning_status": "GET /api/learning/status",
            "learning_memories": "GET/POST /api/learning/memories",
            "groq_key_validate": "POST /api/me/groq-key/validate",
            "groq_key_activate": "POST /api/me/groq-key/activate",
            "groq_key_deactivate": "POST /api/me/groq-key/deactivate",
        },
        "docs": "/docs",
    })


# ── Real-World Data endpoints (weather, prices, etc.) ────────────────────────

try:
    from realworld_data import get_weather, get_price, get_exchange_rate, get_datetime_info
    HAS_REALWORLD_ENDPOINTS = True
except ImportError:
    HAS_REALWORLD_ENDPOINTS = False
    logger.warning("realworld_data module not available; skipping real-world data endpoints")


@app.get("/api/realworld-data/weather", tags=["Real-World Data"])
async def get_weather_endpoint(location: str = None):
    """
    Get current weather for a location.
    
    Query parameters:
      - location: City name or coordinates (optional, uses default if not provided)
    
    Returns weather data from OpenWeather API or DuckDuckGo.
    """
    if not HAS_REALWORLD_ENDPOINTS:
        raise HTTPException(
            status_code=503,
            detail="Real-world data module is not available. Install realworld_data.py"
        )
    
    try:
        weather = await get_weather(location)
        if not weather:
            return JSONResponse(
                status_code=404,
                content={"error": "Weather data not found for the given location"}
            )
        return JSONResponse(weather)
    except Exception as e:
        logger.error("Weather endpoint error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch weather data")


@app.get("/api/realworld-data/price", tags=["Real-World Data"])
async def get_price_endpoint(symbol: str, asset_type: str = "auto"):
    """
    Get current price for crypto or stock.
    
    Query parameters:
      - symbol: Asset symbol (BTC, ETH, AAPL, etc.)
      - asset_type: "crypto", "stock", or "auto" (default)
    
    Returns price data from CoinGecko or Yahoo Finance.
    """
    if not HAS_REALWORLD_ENDPOINTS:
        raise HTTPException(
            status_code=503,
            detail="Real-world data module is not available"
        )
    
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    
    try:
        price = await get_price(symbol, asset_type)
        if not price:
            return JSONResponse(
                status_code=404,
                content={"error": f"Price data not found for {symbol}"}
            )
        return JSONResponse(price)
    except Exception as e:
        logger.error("Price endpoint error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch price data")


@app.get("/api/realworld-data/exchange-rate", tags=["Real-World Data"])
async def get_exchange_rate_endpoint(from_currency: str, to_currency: str):
    """
    Get exchange rate between two currencies.
    
    Query parameters:
      - from_currency: Source currency code (USD, EUR, etc.)
      - to_currency: Target currency code (USD, EUR, etc.)
    
    Returns exchange rate from ExchangeRate-API.
    """
    if not HAS_REALWORLD_ENDPOINTS:
        raise HTTPException(
            status_code=503,
            detail="Real-world data module is not available"
        )
    
    if not from_currency or not to_currency or len(from_currency) > 3 or len(to_currency) > 3:
        raise HTTPException(status_code=400, detail="Invalid currency codes")
    
    try:
        rate = await get_exchange_rate(from_currency, to_currency)
        if not rate:
            return JSONResponse(
                status_code=404,
                content={"error": f"Exchange rate not found for {from_currency}/{to_currency}"}
            )
        return JSONResponse(rate)
    except Exception as e:
        logger.error("Exchange rate endpoint error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch exchange rate")


@app.get("/api/realworld-data/current-time", tags=["Real-World Data"])
async def get_current_time_endpoint():
    """
    Get current date and time in the configured timezone.
    
    Returns structured datetime information.
    """
    if not HAS_REALWORLD_ENDPOINTS:
        raise HTTPException(
            status_code=503,
            detail="Real-world data module is not available"
        )
    
    return JSONResponse(get_datetime_info())


# ── Fact Verification & Accuracy endpoints ──────────────────────────────────

try:
    from fact_verification import (
        verify_factual_claim,
        score_response_accuracy,
        ClaimClassifier,
        AccuracyMetadata,
    )
    HAS_FACT_VERIFICATION = True
except ImportError:
    HAS_FACT_VERIFICATION = False
    logger.warning("fact_verification module not available; skipping accuracy endpoints")


class VerifyClaimRequest(BaseModel):
    claim: str = Field(..., max_length=1000)


@app.post("/api/verify-claim", tags=["Accuracy"])
async def verify_claim_endpoint(req: VerifyClaimRequest):
    """
    Verify a factual claim and get confidence scoring.
    
    Returns:
      - verified: true/false/null (if unable to verify)
      - confidence: 0-100% confidence in the claim
      - sources: List of sources used for verification
      - reasoning: Explanation of verification result
    """
    if not HAS_FACT_VERIFICATION:
        raise HTTPException(
            status_code=503,
            detail="Fact verification module is not available"
        )
    
    try:
        result = await verify_factual_claim(req.claim)
        return JSONResponse(result.to_dict())
    except Exception as e:
        logger.error("Fact verification error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to verify claim")


# ── Token usage endpoint (production) ─────────────────────────────────────────
@app.get("/api/me/tokens", tags=["Account"])
async def my_token_usage(user: dict = Depends(require_current_user)):
    """
    Returns the signed-in user's lifetime token usage.
    In testing mode, always returns zeros (no tracking).
    In production mode, returns real accumulated totals.
    """
    if IS_TESTING:
        return JSONResponse({
            "mode": "testing",
            "note": "Token tracking is disabled in testing mode.",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "request_count": 0,
        })
    stats = get_user_token_stats(user["id"])
    return JSONResponse({"mode": "production", **stats})


@app.get("/api/me/usage", tags=["Account"])
async def my_usage_today(user: dict = Depends(require_current_user)):
    """
    Returns today's usage for the SIGNED-IN user only.
    No free local mode: users without their own key use the deployment's
    default Groq key, and users with an activated key use their own Groq quota.
    """
    key_status = authmod.get_user_key_status(user["id"])
    if IS_TESTING:
        return JSONResponse({
            "mode": "testing",
            "note": "Usage tracking is disabled in testing mode.",
            "has_own_key": key_status["has_key"],
            "using_own_key": key_status["active"],
        })
    usage = get_user_daily_usage(user["id"], has_own_key=key_status["active"])
    return JSONResponse({
        "has_own_key": key_status["has_key"],
        "using_own_key": key_status["active"],
        **usage,
    })


class LearningMemoryCreateRequest(BaseModel):
    memory_text: str = Field(..., min_length=3, max_length=1200)
    tags: str = Field(default="", max_length=200)


class LearningMemoryUpdateRequest(BaseModel):
    memory_text: Optional[str] = Field(default=None, min_length=3, max_length=1200)
    tags: Optional[str] = Field(default=None, max_length=200)
    is_active: Optional[bool] = Field(default=None)


class LearningToggleRequest(BaseModel):
    enabled: bool


@app.get("/api/learning/status", tags=["Learning"])
async def learning_status(user: dict = Depends(require_current_user)):
    """Return whether Learning Center memories are enabled for this account."""
    return JSONResponse(authmod.get_learning_status(user["id"]))


@app.post("/api/learning/toggle", tags=["Learning"])
async def learning_toggle(req: LearningToggleRequest, user: dict = Depends(require_current_user)):
    """Turn use of saved memories on/off for this account."""
    return JSONResponse(authmod.set_learning_enabled(user["id"], req.enabled))


@app.get("/api/learning/memories", tags=["Learning"])
async def learning_list_memories(user: dict = Depends(require_current_user)):
    """List this account's private memories."""
    return JSONResponse({
        "status": authmod.get_learning_status(user["id"]),
        "memories": authmod.list_learning_memories(user["id"]),
    })


@app.post("/api/learning/memories", tags=["Learning"])
async def learning_add_memory(req: LearningMemoryCreateRequest, user: dict = Depends(require_current_user)):
    """Add a new user-approved private memory."""
    try:
        memory = authmod.add_learning_memory(user["id"], req.memory_text, req.tags)
    except authmod.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"ok": True, "memory": memory})


@app.patch("/api/learning/memories/{memory_id}", tags=["Learning"])
async def learning_update_memory(memory_id: int, req: LearningMemoryUpdateRequest, user: dict = Depends(require_current_user)):
    """Edit, activate, or pause one private memory."""
    try:
        memory = authmod.update_learning_memory(
            user["id"],
            memory_id,
            memory_text=req.memory_text,
            tags=req.tags,
            is_active=req.is_active,
        )
    except authmod.AuthError as e:
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 400, detail=str(e))
    return JSONResponse({"ok": True, "memory": memory})


@app.delete("/api/learning/memories/{memory_id}", tags=["Learning"])
async def learning_delete_memory(memory_id: int, user: dict = Depends(require_current_user)):
    """Delete one private memory forever."""
    try:
        authmod.delete_learning_memory(user["id"], memory_id)
    except authmod.AuthError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return JSONResponse({"ok": True})


class GroqKeyRequest(BaseModel):
    api_key: str


@app.post("/api/me/groq-key/validate", tags=["Account"])
async def validate_my_groq_key(request: GroqKeyRequest, user: dict = Depends(require_current_user)):
    """Check whether a pasted Groq key actually works, WITHOUT saving it yet."""
    result = await validate_groq_api_key(request.api_key)
    return JSONResponse(result)


@app.post("/api/me/groq-key/activate", tags=["Account"])
async def activate_my_groq_key(request: GroqKeyRequest, user: dict = Depends(require_current_user)):
    """
    Validate (again, server-side — never trust the client) and save the
    user's Groq key, then switch their chats over to using it.
    """
    result = await validate_groq_api_key(request.api_key)
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=result.get("message", "That Groq key didn't validate."))
    authmod.set_user_groq_key(user["id"], request.api_key.strip())
    return JSONResponse({"activated": True, "message": "Your Groq key is now powering your chats."})


@app.post("/api/me/groq-key/deactivate", tags=["Account"])
async def deactivate_my_groq_key(user: dict = Depends(require_current_user)):
    """Forget the stored key and switch the user back to Vigzone's default Groq key."""
    authmod.clear_user_groq_key(user["id"])
    return JSONResponse({"activated": False, "message": "Switched back to Vigzone's default Groq plan."})


# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/api/auth/signup", tags=["Auth"])
async def signup(req: SignupRequest):
    try:
        user = authmod.create_user_with_password(req.email, req.password, req.name)
    except authmod.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token    = authmod.create_session(user["id"])
    response = JSONResponse({"user": user})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/login", tags=["Auth"])
async def login(req: LoginRequest):
    try:
        user = authmod.verify_password_login(req.email, req.password)
    except authmod.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    token    = authmod.create_session(user["id"])
    response = JSONResponse({"user": user})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/logout", tags=["Auth"])
async def logout(vigzone_session: Optional[str] = Cookie(default=None)):
    authmod.delete_session(vigzone_session)
    response = JSONResponse({"status": "signed_out"})
    response.delete_cookie(authmod.SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/api/auth/me", tags=["Auth"])
async def me(user: Optional[dict] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return JSONResponse({"user": user})


@app.get("/api/auth/google/login", tags=["Auth"])
async def google_login():
    if not authmod.google_is_configured():
        return RedirectResponse(url="/?error=google_not_configured")
    state    = _secrets.token_urlsafe(16)
    auth_url = authmod.google_build_auth_url(state)
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="vigzone_oauth_state", value=state,
        httponly=True, samesite="lax", max_age=600, path="/",
    )
    return response


@app.get("/api/auth/google/callback", tags=["Auth"])
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    vigzone_oauth_state: Optional[str] = Cookie(default=None),
):
    if error:
        return RedirectResponse(url="/?error=google_cancelled")
    if not code or not state or not vigzone_oauth_state or state != vigzone_oauth_state:
        return RedirectResponse(url="/?error=google_failed")
    try:
        profile = await authmod.google_exchange_code(code)
        if not profile.get("google_id") or not profile.get("email"):
            return RedirectResponse(url="/?error=google_failed")
        user = authmod.get_or_create_google_user(
            profile["google_id"], profile["email"], profile["name"]
        )
    except authmod.AuthError:
        return RedirectResponse(url="/?error=google_failed")
    token    = authmod.create_session(user["id"])
    response = RedirectResponse(url="/chat")
    _set_session_cookie(response, token)
    response.delete_cookie("vigzone_oauth_state", path="/")
    return response



# ── Workspaces / Deep Features v3 ─────────────────────────────────────────────
@app.get("/api/workspaces", tags=["Workspaces"])
async def api_list_workspaces(user: dict = Depends(require_current_user)):
    return JSONResponse({"workspaces": authmod.list_workspaces(user["id"])})


@app.post("/api/workspaces", tags=["Workspaces"])
async def api_create_workspace(req: WorkspaceCreateRequest, user: dict = Depends(require_current_user)):
    try:
        ws = authmod.create_workspace(user["id"], req.name, req.description, req.mode)
        return JSONResponse({"workspace": ws})
    except authmod.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/api/workspaces/{workspace_id}", tags=["Workspaces"])
async def api_update_workspace(workspace_id: int, req: WorkspaceUpdateRequest, user: dict = Depends(require_current_user)):
    try:
        ws = authmod.update_workspace(user["id"], workspace_id, req.name, req.description, req.mode)
        return JSONResponse({"workspace": ws})
    except authmod.AuthError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/workspaces/{workspace_id}", tags=["Workspaces"])
async def api_delete_workspace(workspace_id: int, user: dict = Depends(require_current_user)):
    try:
        authmod.delete_workspace(user["id"], workspace_id)
        return JSONResponse({"ok": True})
    except authmod.AuthError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/workspaces/{workspace_id}/notes", tags=["Workspaces"])
async def api_workspace_notes(workspace_id: int, user: dict = Depends(require_current_user)):
    try:
        return JSONResponse({"notes": authmod.list_workspace_notes(user["id"], workspace_id)})
    except authmod.AuthError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/workspaces/{workspace_id}/notes", tags=["Workspaces"])
async def api_add_workspace_note(workspace_id: int, req: WorkspaceNoteRequest, user: dict = Depends(require_current_user)):
    try:
        note = authmod.add_workspace_note(user["id"], workspace_id, req.title, req.content, req.kind)
        return JSONResponse({"note": note})
    except authmod.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/file-intel/analyze", tags=["File Intelligence"])
async def api_file_intel(req: FileIntelRequest, user: dict = Depends(require_current_user)):
    return JSONResponse(_simple_file_intel(req.name, req.kind, req.text))


@app.post("/api/export/chat", tags=["Export"])
async def api_export_chat(req: ExportRequest, user: dict = Depends(require_current_user)):
    title = (req.title or "Vigzone Export").strip()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if req.format == "html":
        body = [f"<h1>{title}</h1><p>Exported {now}</p>"]
        for m in req.messages:
            role = str(m.get("role", "message")).title()
            content = str(m.get("displayText") or m.get("content") or "")
            body.append(f"<section><h2>{role}</h2><pre>{content.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')}</pre></section>")
        data = "<!doctype html><meta charset='utf-8'><title>" + title + "</title><body>" + "\n".join(body) + "</body>"
        media = "text/html"
        filename = "vigzone-chat-export.html"
    else:
        chunks = [title, f"Exported {now}", ""]
        for m in req.messages:
            role = str(m.get("role", "message")).upper()
            content = str(m.get("displayText") or m.get("content") or "")
            chunks.append(f"[{role}]\n{content}\n")
        data = "\n".join(chunks)
        media = "text/plain"
        filename = "vigzone-chat-export.txt"
    return JSONResponse({"filename": filename, "media_type": media, "content": data})


@app.post("/api/website/export", tags=["Website Studio"])
async def api_export_website(req: WebsiteExportRequest, user: dict = Depends(require_current_user)):
    html = req.html.strip()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", html)
        zf.writestr("README.txt", "Generated by Vigzone AI Website Studio. Open index.html in a browser or upload it to your hosting provider.\n")
    data = buf.getvalue()
    filename = req.filename if req.filename.endswith(".zip") else req.filename + ".zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

# ── Upload endpoint ───────────────────────────────────────────────────────────
@app.post("/api/upload", tags=["Chat"])
async def upload_file(file: UploadFile = File(...), user: dict = Depends(require_current_user)):
    filename = file.filename or "upload"
    contents = await file.read()

    if not contents:
        raise HTTPException(400, f'"{filename}" is empty.')
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f'"{filename}" is larger than the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit.')

    # ── Virus scan (runs before any processing) ────────────────────────────
    scan = _virus_scan(contents, filename)
    if not scan.clean:
        threat_label = scan.threat or "unknown threat"
        logger.warning("Blocked upload '%s' — virus scan: %s", filename, threat_label)
        raise HTTPException(
            422,
            f'"{filename}" was blocked by the virus scanner: {threat_label}. '
            "Please ensure your file is safe before uploading.",
        )

    # ── Universal file processing ──────────────────────────────────────────
    try:
        result = process_file(contents, filename)
    except FileProcessingError as e:
        # UX rule for PDFs: never turn the PDF chip red only because extraction
        # failed. Many real user PDFs are scanned/image-only, protected, or
        # generated design PDFs. Accept the attachment with a clear note so the
        # user can still include it in the conversation.
        if filename.lower().endswith(".pdf"):
            logger.warning("Accepted PDF with fallback note after processing error for %s: %s", filename, e)
            result = {
                "name": filename,
                "kind": "document",
                "text": (
                    f"[PDF attached: {filename}]\n"
                    "Vigzone accepted this PDF, but the server could not extract readable text from it. "
                    "It may be scanned/image-based, protected, corrupted, or a design PDF. "
                    "If you need visual analysis, upload screenshots/images of the PDF pages too."
                ),
                "truncated": False,
                "pdf_fallback": True,
                "processing_warning": str(e),
            }
        else:
            raise HTTPException(422, f'"{filename}": {e}')
    except Exception as e:
        logger.error("Unexpected error processing upload %s: %s", filename, e, exc_info=True)
        if filename.lower().endswith(".pdf"):
            result = {
                "name": filename,
                "kind": "document",
                "text": (
                    f"[PDF attached: {filename}]\n"
                    "Vigzone accepted this PDF, but the server could not process it. "
                    "If you need visual analysis, upload screenshots/images of the PDF pages too."
                ),
                "truncated": False,
                "pdf_fallback": True,
                "processing_warning": str(e),
            }
        else:
            raise HTTPException(500, f'Couldn\'t process "{filename}".')

    # Attach scan metadata so the frontend can show a "scanned ✓" badge
    result["scan_clean"] = scan.clean
    result["scanner_available"] = scan.scanner_available

    return JSONResponse(result)


# ── Admin endpoints ───────────────────────────────────────────────────────────
def _admin_today_start_ts() -> int:
    from datetime import datetime, timezone, timedelta

    tz_offset_minutes = int(os.getenv("USAGE_TZ_OFFSET_MINUTES", "330"))
    local_tz = timezone(timedelta(minutes=tz_offset_minutes))
    now_local = datetime.now(local_tz)
    return int(now_local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


@app.get("/api/admin/overview", tags=["Admin"])
async def admin_overview(admin: dict = Depends(require_admin)):
    """Small production dashboard: users, today's tokens, top users."""
    import sqlite3

    db_path = os.getenv("VIGZONE_DB_PATH", os.path.join("data", "vigzone.db"))
    start_ts = _admin_today_start_ts()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        active_today = conn.execute(
            "SELECT COUNT(DISTINCT user_id) AS c FROM token_usage WHERE ts >= ?",
            (start_ts,),
        ).fetchone()["c"]
        totals = conn.execute(
            """
            SELECT COALESCE(SUM(prompt_tokens),0) AS prompt,
                   COALESCE(SUM(completion_tokens),0) AS completion,
                   COALESCE(SUM(total_tokens),0) AS total,
                   COUNT(*) AS requests
            FROM token_usage WHERE ts >= ?
            """,
            (start_ts,),
        ).fetchone()
        own_key_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE use_own_key = 1 AND own_groq_key_enc IS NOT NULL"
        ).fetchone()["c"]
        top_rows = conn.execute(
            """
            SELECT u.id, u.name, u.email,
                   COALESCE(SUM(t.total_tokens),0) AS total_tokens,
                   COUNT(t.id) AS requests,
                   u.use_own_key AS using_own_key
            FROM users u
            LEFT JOIN token_usage t ON t.user_id = u.id AND t.ts >= ?
            GROUP BY u.id
            ORDER BY total_tokens DESC, requests DESC
            LIMIT 10
            """,
            (start_ts,),
        ).fetchall()

    return JSONResponse({
        "total_users": total_users,
        "active_today": active_today,
        "own_key_users": own_key_users,
        "default_plan_users": max(total_users - own_key_users, 0),
        "today": {
            "prompt_tokens": totals["prompt"],
            "completion_tokens": totals["completion"],
            "total_tokens": totals["total"],
            "requests": totals["requests"],
        },
        "top_users": [
            {
                "id": r["id"],
                "name": r["name"],
                "email": r["email"],
                "total_tokens": r["total_tokens"],
                "requests": r["requests"],
                "using_own_key": bool(r["using_own_key"]),
            }
            for r in top_rows
        ],
    })


@app.post("/api/admin/users/{user_id}/usage/reset", tags=["Admin"])
async def admin_reset_user_usage(user_id: int, admin: dict = Depends(require_admin)):
    """Delete today's tracked usage rows for a user. Groq-side usage is not reset."""
    import sqlite3

    db_path = os.getenv("VIGZONE_DB_PATH", os.path.join("data", "vigzone.db"))
    start_ts = _admin_today_start_ts()
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("DELETE FROM token_usage WHERE user_id = ? AND ts >= ?", (user_id, start_ts))
        conn.commit()
    return JSONResponse({"ok": True, "deleted_rows": cur.rowcount})


# ── Voice transcription endpoint ──────────────────────────────────────────────
GROQ_TRANSCRIPTION_MODEL = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
MAX_VOICE_UPLOAD_SIZE = int(os.getenv("MAX_VOICE_UPLOAD_SIZE_BYTES", str(25 * 1024 * 1024)))
VOICE_TRANSCRIPTION_LANG_PRIORITY = [
    item.strip().lower()
    for item in os.getenv("VOICE_TRANSCRIPTION_LANG_PRIORITY", "si,ta,en,hi").split(",")
    if item.strip()
]


def _groq_audio_transcriptions_url(api_url: str) -> str:
    """Build Groq's OpenAI-compatible audio transcription URL from the chat URL."""
    base = (api_url or "https://api.groq.com/openai/v1/chat/completions").rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return f"{base}/audio/transcriptions"


def _normalize_transcription_language(language: Optional[str]) -> Optional[str]:
    """Convert browser BCP-47 values like en-US/si-LK to Whisper's en/si."""
    import re as _re

    raw = (language or "").strip().lower()
    if not raw or raw in ("auto", "default", "detect"):
        return None
    primary = raw.split("-", 1)[0].split("_", 1)[0].strip()
    return primary if _re.fullmatch(r"[a-z]{2,3}", primary) else None


def _voice_candidate_languages(
    explicit_language: Optional[str],
    browser_language: Optional[str] = None,
    browser_languages: Optional[str] = None,
    browser_hint: Optional[str] = None,
) -> list[Optional[str]]:
    """Build a small ordered list of language hints to try for Whisper.

    For Sri Lankan users, Whisper/browser auto-detect may confuse Sinhala with
    Hindi. We therefore try Sinhala and Tamil explicitly before falling back to
    English/Hindi/auto. Admin can change order with VOICE_TRANSCRIPTION_LANG_PRIORITY.
    """
    candidates: list[Optional[str]] = []
    explicit = _normalize_transcription_language(explicit_language)
    if explicit:
        candidates.append(explicit)

    # Scripts from any quick browser hint. This uses the first one/two words
    # when available, but never trusts it fully because Web Speech can be wrong.
    hint = (browser_hint or "")[:80]
    if re.search(r"[\u0D80-\u0DFF]", hint):
        candidates.append("si")
    if re.search(r"[\u0B80-\u0BFF]", hint):
        candidates.append("ta")
    if re.search(r"[\u0900-\u097F]", hint):
        candidates.append("hi")

    # Browser languages can still help for English/Tamil/Sinhala users.
    raw_langs = ",".join([browser_language or "", browser_languages or ""])
    for part in re.split(r"[,;\s]+", raw_langs.lower()):
        lang = _normalize_transcription_language(part)
        if lang:
            candidates.append(lang)

    candidates.extend(VOICE_TRANSCRIPTION_LANG_PRIORITY)
    # Auto detect as final fallback.
    candidates.append(None)

    # Keep valid unique items, preserving order.
    out: list[Optional[str]] = []
    seen: set[str] = set()
    for item in candidates:
        key = item or "auto"
        if item is not None and not re.fullmatch(r"[a-z]{2,3}", item):
            continue
        if key not in seen:
            out.append(item)
            seen.add(key)
    return out[:6]


def _voice_script_counts(text: str) -> dict[str, int]:
    return {
        "si": len(re.findall(r"[\u0D80-\u0DFF]", text or "")),
        "ta": len(re.findall(r"[\u0B80-\u0BFF]", text or "")),
        "hi": len(re.findall(r"[\u0900-\u097F]", text or "")),
        "latin": len(re.findall(r"[A-Za-z]", text or "")),
        "digits": len(re.findall(r"\d", text or "")),
    }


def _score_transcription_candidate(text: str, lang: Optional[str], browser_hint: str = "") -> float:
    """Heuristic scorer for multiple Whisper attempts.

    The first spoken words often expose the writing system. We prefer Sinhala
    when Sinhala letters are present, Tamil for Tamil letters, and penalize
    Devanagari/Hindi when Sinhala/Tamil candidates exist because Sinhala speech
    is commonly misdetected as Hindi in browser/auto transcription.
    """
    clean = (text or "").strip()
    if not clean:
        return -1_000_000

    counts = _voice_script_counts(clean)
    words = re.findall(r"\S+", clean)
    score = min(len(clean), 240) * 0.45 + min(len(words), 30) * 2.0

    # Strong script/language agreement bonuses.
    if lang == "si":
        score += counts["si"] * 14
        score -= counts["hi"] * 10
    elif lang == "ta":
        score += counts["ta"] * 14
        score -= counts["hi"] * 5
    elif lang == "hi":
        score += counts["hi"] * 6
        # If Hindi is only slightly better than Sinhala, don't let it win for SL users.
        score -= 18
    elif lang == "en":
        score += counts["latin"] * 1.2

    # Script present even when auto language was used.
    score += counts["si"] * 12
    score += counts["ta"] * 11
    score += counts["latin"] * 0.25
    score -= counts["hi"] * 2.5

    # Extremely short outputs are often mis-detections.
    if len(words) <= 1:
        score -= 15

    # Browser hint can nudge but not decide.
    hint_counts = _voice_script_counts(browser_hint or "")
    if hint_counts["si"] and counts["si"]:
        score += 20
    if hint_counts["ta"] and counts["ta"]:
        score += 20
    if hint_counts["hi"] and counts["hi"]:
        score += 3

    # Penalize obvious junk repetition.
    if len(set(words)) <= 2 and len(words) >= 6:
        score -= 25

    return score


async def _groq_transcribe_once(
    client: httpx.AsyncClient,
    transcribe_url: str,
    api_key: str,
    audio: bytes,
    filename: str,
    content_type: str,
    lang: Optional[str],
) -> tuple[str, dict]:
    data = {"model": GROQ_TRANSCRIPTION_MODEL, "response_format": "json"}
    if lang:
        data["language"] = lang
    resp = await client.post(
        transcribe_url,
        headers={"Authorization": f"Bearer {api_key}"},
        data=data,
        files={"file": (filename or "voice.webm", audio, content_type)},
    )
    if resp.status_code != 200:
        return "", {"status_code": resp.status_code, "body": resp.text[:500], "language": lang}
    try:
        payload = resp.json()
    except Exception:
        payload = {}
    return (payload.get("text") or "").strip(), payload


@app.post("/api/transcribe", tags=["Voice"])
async def transcribe_voice(
    request: Request,
    file: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
    browser_language: Optional[str] = Form(default=None),
    browser_languages: Optional[str] = Form(default=None),
    browser_hint: Optional[str] = Form(default=None),
    user: dict = Depends(require_current_user),
):
    """Transcribe a recorded voice message with Groq Whisper.

    The frontend first tries the browser's built-in SpeechRecognition for instant
    captions. If that gives a false `no-speech` result, this endpoint becomes the
    reliable server fallback, using either the user's activated Groq key or the
    deployment default key.
    """
    _check_chat_rate_limit(request, user)

    provider_override, _ = _resolve_provider_for_user(user)
    if provider_override is None and not await is_configured():
        raise HTTPException(
            status_code=503,
            detail="Groq isn't configured — set GROQ_API_KEY before using voice transcription.",
        )

    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Voice recording was empty.")
    if len(audio) > MAX_VOICE_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Voice recording is too large. Try a shorter message.")

    content_type = file.content_type or "audio/webm"
    if not content_type.startswith("audio/") and content_type not in {"video/webm", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Unsupported voice recording format.")

    using_override = provider_override is not None
    api_url = provider_override["api_url"] if using_override else f"{OLLAMA_BASE_URL}/chat/completions"
    api_key = provider_override["api_key"] if using_override else API_KEY
    transcribe_url = _groq_audio_transcriptions_url(api_url)

    candidates = _voice_candidate_languages(language, browser_language, browser_languages, browser_hint)
    attempts: list[dict] = []
    best_text = ""
    best_lang: Optional[str] = None
    best_score = -1_000_000.0
    last_error: Optional[dict] = None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=5.0)) as client:
            for lang in candidates:
                text, payload = await _groq_transcribe_once(
                    client,
                    transcribe_url,
                    api_key,
                    audio,
                    file.filename or "voice.webm",
                    content_type,
                    lang,
                )
                if not text:
                    last_error = payload
                    # Do not burn more attempts if the key is invalid/rate-limited.
                    if payload.get("status_code") in (401, 429):
                        break
                    continue
                score = _score_transcription_candidate(text, lang, browser_hint or "")
                attempts.append({"language": lang or "auto", "text": text[:80], "score": round(score, 2)})
                if score > best_score:
                    best_score = score
                    best_text = text
                    best_lang = lang

                # Early accept: Sinhala/Tamil script is very strong evidence.
                counts = _voice_script_counts(text)
                if (lang == "si" and counts["si"] >= 2) or (lang == "ta" and counts["ta"] >= 2):
                    break
    except httpx.RequestError as e:
        logger.warning("Groq transcription request failed: %s", e)
        raise HTTPException(status_code=502, detail="Couldn't reach Groq to transcribe the voice message.")

    if last_error and last_error.get("status_code") == 401 and not best_text:
        raise HTTPException(
            status_code=401,
            detail=(
                "Groq rejected this API key for voice transcription. "
                + ("Check the key you entered." if using_override else "Check GROQ_API_KEY in your deployment variables.")
            ),
        )
    if last_error and last_error.get("status_code") == 429 and not best_text:
        raise HTTPException(status_code=429, detail="Groq voice transcription is rate-limited right now. Please try again soon.")
    if last_error and last_error.get("status_code") and last_error.get("status_code") != 200 and not best_text:
        logger.warning("Groq transcription error %s: %s", last_error.get("status_code"), last_error.get("body"))
        raise HTTPException(status_code=502, detail=f"Groq couldn't transcribe that voice message (status {last_error.get('status_code')}).")

    text = best_text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="I couldn't detect speech in that recording.")

    # Count a small estimated amount against Vigzone's usage table so voice
    # users do not get invisible/free backend activity. This is an estimate;
    # Groq's rate-limit response is still the final source of truth.
    try:
        from vigzone_ai import track_token_usage, _estimate_tokens

        if not IS_TESTING:
            track_token_usage(user["id"], prompt_tokens=0, completion_tokens=_estimate_tokens(text), provider="groq")
    except Exception:
        logger.debug("Voice transcription usage tracking failed", exc_info=True)

    return JSONResponse({"text": text, "provider": "groq", "model": GROQ_TRANSCRIPTION_MODEL, "language": best_lang or "auto"})


# ── Chat endpoints ────────────────────────────────────────────────────────────
def _resolve_provider_for_user(user: dict) -> tuple[Optional[dict], Optional[str]]:
    """
    Decide which AI backend a given user's message should use.
    Returns (provider_override, override_model):
      - (None, None)               → use the deployment default Groq key
      - ({"api_url":..,"api_key":..}, GROQ_BYOK_MODEL) → this user has
        activated their own personal Groq key, so their chats bypass the
        shared default entirely and run on their own quota.
    """
    key_status = authmod.get_user_key_status(user["id"])
    if key_status["active"]:
        own_key = authmod.get_user_groq_key(user["id"])
        if own_key:
            return {"api_url": GROQ_BYOK_API_URL, "api_key": own_key}, GROQ_BYOK_MODEL
    return None, None


@app.post("/api/chat", tags=["Chat"])
async def chat(request: Request, chat_request: ChatRequest, user: dict = Depends(require_current_user)):
    """
    Stream a chat response as Server-Sent Events.
    No message limits in testing mode. Token usage tracked in production mode.
    Users with their own activated Groq key bypass the deployment default
    entirely and run on their own personal quota.
    """
    provider_override, override_model = _resolve_provider_for_user(user)
    _check_chat_rate_limit(request, user)

    # Real backend quota guard: do not start a Groq call when this user's
    # Vigzone daily plan is exhausted or too close to exhausted.
    key_status = authmod.get_user_key_status(user["id"])
    estimated_request_tokens = estimate_messages_tokens([{"role": m.role, "content": m.content} for m in chat_request.messages])
    try:
        assert_user_can_chat(user["id"], has_own_key=key_status["active"], estimated_request_tokens=estimated_request_tokens)
    except UsageLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))

    if provider_override is None and not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Groq isn't configured — set GROQ_API_KEY in .env "
                "or in your deployment Variables (get a free key at https://console.groq.com/keys)."
            ),
        )

    messages  = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    last_user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            last_user_query = m.get("content") or ""
            break
    user_learning_context = _combine_context(
        _mode_context(chat_request.ai_mode),
        authmod.get_workspace_context(user["id"], chat_request.workspace_id, last_user_query),
        authmod.get_learning_context(user["id"], last_user_query),
    )
    stream_id = create_stream_id()
    register_stream(stream_id)

    async def event_stream():
        try:
            yield f'data: {{"stream_id": "{stream_id}"}}\n\n'

            reply_accum    = ""
            last_user_text = None
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user_text = m.get("content") if isinstance(m.get("content"), str) else None
                    break

            try:
                async for chunk in stream_chat(
                    messages,
                    model=override_model or chat_request.model,
                    stream_id=stream_id,
                    user_id=user["id"],
                    user_name=user.get("name") or "",
                    provider_override=provider_override,
                    user_learning_context=user_learning_context,
                ):
                    if is_cancelled(stream_id):
                        break
                    reply_accum += chunk
                    payload = chunk.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
                    yield f'data: {{"content": "{payload}"}}\n\n'

                if not is_cancelled(stream_id):
                    try:
                        if last_user_text and reply_accum:
                            safe = sanitize_assistant_for_memory(reply_accum)
                            if safe:
                                add_interaction(last_user_text, safe)
                    except Exception:
                        logger.exception("Failed to save interaction to KB")
                    yield "data: [DONE]\n\n"
                else:
                    yield "data: [CANCELLED]\n\n"

            except VigzoneAIError as e:
                logger.error("Chat stream failed: %s", e)
                err = str(e).replace('"', "'")
                yield f'data: {{"error": "{err}"}}\n\n'
            except Exception as e:
                # Safety net: any *unexpected* exception (e.g. a malformed
                # streaming API chunk) used to propagate out of this generator
                # uncaught, which silently kills the SSE stream with zero
                # content and zero error - the frontend then just shows a
                # generic "No response received." with no clue why. Surface
                # it as a real error instead so it's actually debuggable.
                logger.exception("Unexpected error in chat stream")
                err = str(e).replace('"', "'") or e.__class__.__name__
                yield f'data: {{"error": "Unexpected server error: {err}"}}\n\n'
        finally:
            unregister_stream(stream_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/sync", tags=["Chat"])
async def chat_sync(request: Request, chat_request: ChatRequest, user: dict = Depends(require_current_user)):
    """Non-streaming variant — returns the full reply in one JSON response."""
    provider_override, override_model = _resolve_provider_for_user(user)
    _check_chat_rate_limit(request, user)

    key_status = authmod.get_user_key_status(user["id"])
    estimated_request_tokens = estimate_messages_tokens([{"role": m.role, "content": m.content} for m in chat_request.messages])
    try:
        assert_user_can_chat(user["id"], has_own_key=key_status["active"], estimated_request_tokens=estimated_request_tokens)
    except UsageLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))

    if provider_override is None and not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Groq isn't configured — set GROQ_API_KEY in .env "
                "or in your deployment Variables (get a free key at https://console.groq.com/keys)."
            ),
        )
    messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    last_user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            last_user_query = m.get("content") or ""
            break
    user_learning_context = _combine_context(
        _mode_context(chat_request.ai_mode),
        authmod.get_workspace_context(user["id"], chat_request.workspace_id, last_user_query),
        authmod.get_learning_context(user["id"], last_user_query),
    )
    try:
        reply = await chat_once(
            messages,
            model=override_model or chat_request.model,
            user_id=user["id"],
            user_name=user.get("name") or "",
            provider_override=provider_override,
            user_learning_context=user_learning_context,
        )
    except VigzoneAIError as e:
        logger.error("Chat failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    try:
        last_user_text = None
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_text = m.get("content") if isinstance(m.get("content"), str) else None
                break
        if last_user_text and reply:
            add_interaction(last_user_text, reply)
    except Exception:
        logger.exception("Failed to save interaction to KB")

    return JSONResponse({"role": "assistant", "content": reply})


# ── Stream control ────────────────────────────────────────────────────────────
@app.post("/api/cancel-stream", tags=["Chat"])
async def cancel_stream_endpoint(req: StreamControlRequest):
    if cancel_stream(req.stream_id):
        return JSONResponse({"status": "cancelled", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


@app.post("/api/pause-stream", tags=["Chat"])
async def pause_stream_endpoint(req: StreamControlRequest):
    if pause_stream(req.stream_id):
        return JSONResponse({"status": "paused", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


@app.post("/api/resume-stream", tags=["Chat"])
async def resume_stream_endpoint(req: StreamControlRequest):
    if resume_stream(req.stream_id):
        return JSONResponse({"status": "resumed", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


# ── Image generation ──────────────────────────────────────────────────────────
@app.post("/api/generate-image", tags=["Image"])
async def api_generate_image(req: ImageRequest, user: dict = Depends(require_current_user)):
    try:
        result = await generate_image(req.prompt, size=req.size or "1024x1024")
    except ImageGenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in image generation")
        raise HTTPException(status_code=500, detail="Image generation failed")
    return JSONResponse(result)


@app.post("/api/edit-image", tags=["Image"])
async def api_edit_image(req: EditImageRequest, user: dict = Depends(require_current_user)):
    try:
        result = await edit_image(req.image_data_uri, req.prompt, size=req.size or "1024x1024")
    except ImageGenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in image editing")
        raise HTTPException(status_code=500, detail="Image editing failed")
    return JSONResponse(result)


# ── Page routes ───────────────────────────────────────────────────────────────
@app.get("/", tags=["Web"])
async def root():
    return FileResponse("static/landing.html", media_type="text/html")


@app.get("/chat", tags=["Web"])
async def chat_page(vigzone_session: Optional[str] = Cookie(default=None)):
    if not authmod.get_user_by_session(vigzone_session):
        return RedirectResponse(url="/")
    return FileResponse("static/index.html", media_type="text/html")


# ── Error handlers ────────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error("HTTP Exception: %s - %s", exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Unexpected error: %s", str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ── Static files ──────────────────────────────────────────────────────────────
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port   = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENV", "development") == "development"
    logger.info("Starting Vigzone AI server on port %d…", port)
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=reload, log_level="info")
