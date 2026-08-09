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
import asyncio
import hashlib
import os
import re
import io
import json
import zipfile
from urllib.parse import parse_qs, unquote, urlparse
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Literal, Optional, Union, Any

from dotenv import load_dotenv

load_dotenv()

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from file_processing import (
    FileProcessingError,
    process_file,
)
from virus_scanner import scan_bytes as _virus_scan
from vigzone_ai import (
    DEFAULT_MODEL,
    FAST_MODEL,
    COMPLEX_MODEL,
    MODEL_ROUTING_ENABLED,
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
    estimate_budgeted_request_tokens,
    is_configured,
    stream_chat,
    validate_groq_api_key,
)
from image_generation import generate_image, edit_image, ImageGenError
from web_search import _get_user_timezone_name, image_search
from stream_manager import (
    create_stream_id,
    register_stream,
    cancel_stream,
    is_cancelled,
    unregister_stream,
    pause_stream,
    resume_stream,
    purge_stale_streams,
)
from security import (
    RequestBodyLimitMiddleware,
    SecurityHeadersMiddleware,
    allowed_origins,
    client_ip,
    is_production,
    request_fingerprint,
    validate_production_settings,
)
import auth as authmod
import billing
import mailer
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
    try:
        validate_production_settings()
    except RuntimeError as exc:
        # Managed platforms otherwise tend to show only the downstream symptom
        # ("nothing is listening on PORT"). Log the real preflight failure
        # prominently without printing any configured secret values.
        logger.critical("Production preflight failed; server will not become ready:\n%s", exc)
        raise
    authmod.init_db()
    purge_stale_streams()
    mode = "TESTING (unlimited)" if IS_TESTING else "PRODUCTION (token tracking ON)"
    logger.info("Vigzone AI started — mode: %s", mode)
    yield


app = FastAPI(
    title="Vigzone AI API",
    description="A real conversational AI assistant — powered by Groq.",
    version="5.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not is_production() or os.getenv("ENABLE_API_DOCS", "").lower() in {"1", "true", "yes"} else None,
    redoc_url=None,
    openapi_url="/openapi.json" if not is_production() or os.getenv("ENABLE_API_DOCS", "").lower() in {"1", "true", "yes"} else None,
)

app.add_middleware(
    RequestBodyLimitMiddleware,
    max_bytes=int(os.getenv("MAX_REQUEST_BODY_BYTES", str(32 * 1024 * 1024))),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-Request-ID"],
)
app.add_middleware(SecurityHeadersMiddleware)

# ── Upload config ─────────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE    = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(25 * 1024 * 1024)))
IMAGE_EXTENSIONS   = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


async def _read_upload_limited(file: UploadFile, limit: int) -> bytes:
    """Read an upload in bounded chunks and abort before buffering too much."""

    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(min(1024 * 1024, limit + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise HTTPException(
                    status_code=413,
                    detail=f"Upload exceeds the {limit // (1024 * 1024)} MB limit.",
                )
            chunks.append(chunk)
    finally:
        await file.close()
    return b"".join(chunks)


# ── Pydantic models ───────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, List[dict]] = Field(...)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=100)
    model: str = Field(default=FAST_MODEL, max_length=120)
    ai_mode: Optional[str] = Field(default="general", max_length=40)
    workspace_id: Optional[int] = Field(default=None)
    conversation_id: Optional[str] = Field(default=None, max_length=120)
    # Browser-provided timezone lets Vigzone answer date/time correctly
    # without requiring a Railway USER_TIMEZONE variable.
    client_timezone: Optional[str] = Field(default=None, max_length=80)
    client_now_iso: Optional[str] = Field(default=None, max_length=80)


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
    fast_model: str
    complex_model: str
    vision_model: str
    routing_enabled: bool
    backend: str
    status: str
    mode: str


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=10, max_length=200)
    name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


class EmailRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)


class PasswordResetRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=256)
    new_password: str = Field(..., min_length=10, max_length=256)


class StreamControlRequest(BaseModel):
    stream_id: str = Field(..., min_length=8, max_length=120)


class ImageRequest(BaseModel):
    # Image prompts often need details for accurate composition/text/layout.
    prompt: str = Field(..., min_length=1, max_length=3000)
    size: Optional[str] = Field(default="1024x1024", max_length=30)


class EditImageRequest(BaseModel):
    image_data_uri: str = Field(..., min_length=1, max_length=28_000_000)
    prompt: str = Field(..., min_length=1, max_length=3000)
    size: Optional[str] = Field(default="1024x1024", max_length=30)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str = Field(default="", max_length=600)
    mode: str = Field(default="general", max_length=40)
    shared: bool = False


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
    messages: List[dict] = Field(default_factory=list, max_length=500)
    format: Literal["txt", "html"] = "txt"


class WebsiteExportRequest(BaseModel):
    html: str = Field(..., min_length=1, max_length=500000)
    filename: str = Field(default="vigzone-website.zip", max_length=100)


class DriveImportRequest(BaseModel):
    url: Optional[str] = Field(default="", max_length=2000)
    file_id: Optional[str] = Field(default="", max_length=200)
    access_token: Optional[str] = Field(default="", max_length=4000)
    name: Optional[str] = Field(default="", max_length=240)
    mime_type: Optional[str] = Field(default="", max_length=240)


class BrainCloudSyncRequest(BaseModel):
    data: dict = Field(default_factory=dict)
    client_updated_at: Optional[str] = Field(default=None, max_length=80)
    base_version: Optional[int] = Field(default=None, ge=0)


class FeedbackCreateRequest(BaseModel):
    message_id: Optional[str] = Field(default=None, max_length=120)
    conversation_id: Optional[str] = Field(default=None, max_length=120)
    rating: Literal["up", "down"] = "up"
    reason: Optional[str] = Field(default="", max_length=500)
    message_text: Optional[str] = Field(default="", max_length=6000)
    assistant_text: Optional[str] = Field(default="", max_length=12000)
    context: dict = Field(default_factory=dict)


class ShareChatRequest(BaseModel):
    title: str = Field(default="Vigzone chat", max_length=160)
    messages: List[dict] = Field(default_factory=list, max_length=200)
    public: bool = True
    expires_in_days: int = Field(default=7, ge=1, le=30)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(default="", max_length=256)
    new_password: str = Field(..., min_length=10, max_length=256)


class AccountDeleteRequest(BaseModel):
    confirmation: Literal["DELETE"]
    password: str = Field(default="", max_length=256)


class ConversationSyncRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=120)
    title: str = Field(default="New chat", max_length=160)
    messages: List[dict] = Field(default_factory=list, max_length=500)
    base_revision: Optional[int] = Field(default=None, ge=0)


class TeamProfileRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    persona_name: Optional[str] = Field(default=None, max_length=60)
    persona_instructions: Optional[str] = Field(default=None, max_length=2400)


class TeamInviteRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)


class TeamInviteAcceptRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=256)


class SupportTicketRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=160)
    message: str = Field(..., min_length=10, max_length=6000)


class SupportTicketUpdateRequest(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]
    admin_response: str = Field(default="", max_length=6000)


# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_current_user(
    request: Request,
    vigzone_session: Optional[str] = Cookie(default=None),
) -> Optional[dict]:
    return authmod.get_user_by_session(vigzone_session)


def require_current_user(
    request: Request,
    vigzone_session: Optional[str] = Cookie(default=None),
) -> dict:
    user = authmod.get_user_by_session(vigzone_session)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


# ── Production safety helpers ────────────────────────────────────────────────
_CHAT_RATE_LIMIT_PER_MINUTE = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "20"))


def _enforce_rate_limit(
    request: Request,
    scope: str,
    limit: int,
    *,
    user: Optional[dict] = None,
    window_seconds: int = 60,
) -> None:
    if IS_TESTING or limit <= 0:
        return
    subject = f"user:{user['id']}" if user else f"ip:{client_ip(request)}"
    retry_after = authmod.consume_rate_limit(subject, scope, limit, window_seconds)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


def _check_chat_rate_limit(request: Request, user: dict) -> None:
    _enforce_rate_limit(
        request,
        "chat",
        _CHAT_RATE_LIMIT_PER_MINUTE,
        user=user,
        window_seconds=60,
    )


def require_admin(user: dict = Depends(require_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


# ── Product Suite / Brain Pro storage ─────────────────────────────────────────
APP_VERSION = os.getenv("VIGZONE_VERSION", "5.0.0")
APP_NAME = os.getenv("VIGZONE_APP_NAME", "Vigzone AI")
APP_SHORT_NAME = os.getenv("VIGZONE_SHORT_NAME", APP_NAME)
APP_BUILD_NAME = os.getenv("VIGZONE_BUILD_NAME", "Vigzone AI Production")
GROQ_KEYS_URL = os.getenv("GROQ_KEYS_URL", "https://console.groq.com/keys")
GROQ_DOCS_URL = os.getenv("GROQ_DOCS_URL", "https://console.groq.com/docs/models")
GOOGLE_DRIVE_API_KEY = os.getenv("GOOGLE_DRIVE_API_KEY", os.getenv("GOOGLE_API_KEY", "")).strip()
GOOGLE_DRIVE_CLIENT_ID = os.getenv("GOOGLE_DRIVE_CLIENT_ID", os.getenv("GOOGLE_CLIENT_ID", "")).strip()

# ── Paddle Billing ────────────────────────────────────────────────────────────
PADDLE_VENDOR_ID = os.getenv("PADDLE_VENDOR_ID", "").strip()
PADDLE_CLIENT_TOKEN = os.getenv("PADDLE_CLIENT_TOKEN", "").strip() or PADDLE_VENDOR_ID
_PADDLE_PRO_LEGACY_ID = os.getenv("PADDLE_PRO_PRODUCT_ID", "").strip()
_PADDLE_TEAM_LEGACY_ID = os.getenv("PADDLE_TEAM_PRODUCT_ID", "").strip()
PADDLE_PRO_PRICE_ID = os.getenv("PADDLE_PRO_PRICE_ID", "").strip() or (
    _PADDLE_PRO_LEGACY_ID if _PADDLE_PRO_LEGACY_ID.startswith("pri_") else ""
)
PADDLE_TEAM_PRICE_ID = os.getenv("PADDLE_TEAM_PRICE_ID", "").strip() or (
    _PADDLE_TEAM_LEGACY_ID if _PADDLE_TEAM_LEGACY_ID.startswith("pri_") else ""
)
PADDLE_PRO_PRODUCT_ID = os.getenv("PADDLE_PRO_CATALOG_PRODUCT_ID", "").strip() or (
    _PADDLE_PRO_LEGACY_ID if _PADDLE_PRO_LEGACY_ID.startswith("pro_") else ""
)
PADDLE_TEAM_PRODUCT_ID = os.getenv("PADDLE_TEAM_CATALOG_PRODUCT_ID", "").strip() or (
    _PADDLE_TEAM_LEGACY_ID if _PADDLE_TEAM_LEGACY_ID.startswith("pro_") else ""
)
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "").strip()
PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "").strip()
PADDLE_ENVIRONMENT = os.getenv("PADDLE_ENVIRONMENT", "").strip().lower() or (
    "sandbox" if PADDLE_CLIENT_TOKEN.startswith("test_") else "production"
)

# Customer-facing names must match the IDs actually sent to Groq.  Legacy
# Llama/DeepSeek IDs are migrated in vigzone_ai.py for saved clients, but are
# never advertised as if those retired models were still serving responses.
MODEL_CATALOG = [
    {
        "id": "openai/gpt-oss-20b",
        "name": "GPT-OSS 20B",
        "badge": "Fast",
        "description": "Fast production model for everyday chat and documents",
        "icon": "🚀",
        "plan": "free",
    },
    {
        "id": "openai/gpt-oss-120b",
        "name": "GPT-OSS 120B",
        "badge": "Powerhouse",
        "description": "Quality-first production model for complex reasoning and analysis",
        "icon": "⚡",
        "plan": "pro",
    },
    {
        "id": "qwen/qwen3.6-27b",
        "name": "Qwen 3.6 27B",
        "badge": "Preview · Vision",
        "description": "Preview multimodal model for images, coding, and reasoning",
        "icon": "👁️",
        "plan": "pro",
        "required_feature": "early_access",
    },
]


def _paddle_catalog() -> dict:
    return {
        "pro": {"price_ids": [PADDLE_PRO_PRICE_ID], "product_ids": [PADDLE_PRO_PRODUCT_ID]},
        "team": {"price_ids": [PADDLE_TEAM_PRICE_ID], "product_ids": [PADDLE_TEAM_PRODUCT_ID]},
    }


def _require_feature(user: dict, feature: str, label: str) -> None:
    if not billing.feature_allowed(user, feature):
        required_plan = "Vigzone TEAM" if feature in {
            "team_workspace", "usage_analytics", "custom_ai_persona", "dedicated_support"
        } else "Vigzone PRO and TEAM"
        raise HTTPException(
            status_code=403,
            detail=f"{label} is available on {required_plan}. Upgrade to unlock it.",
        )


def _assert_chat_entitlements(user: dict, chat_request: ChatRequest, *, has_own_key: bool, estimated_tokens: int) -> None:
    if not billing.model_allowed(user, chat_request.model):
        raise HTTPException(
            status_code=403,
            detail="That model is available on Vigzone PRO and TEAM. Free includes GPT-OSS 20B.",
        )
    contains_image = any(
        isinstance(message.content, list)
        and any(isinstance(item, dict) and item.get("type") == "image_url" for item in message.content)
        for message in chat_request.messages
    )
    if contains_image and not billing.feature_allowed(user, "advanced_models"):
        raise HTTPException(
            status_code=403,
            detail="Image understanding uses the Qwen vision model and is available on Vigzone PRO and TEAM.",
        )
    if not billing.chat_mode_allowed(user, chat_request.ai_mode):
        raise HTTPException(
            status_code=403,
            detail="That AI mode is available on Vigzone PRO and TEAM.",
        )
    if billing.effective_plan(user) != "free":
        return
    if authmod.consume_daily_message(user["id"], 50) is None:
        raise HTTPException(
            status_code=429,
            detail="You have used your 50 Free messages for today. Upgrade to PRO or TEAM for unlimited messages.",
        )
    try:
        assert_user_can_chat(
            user["id"],
            has_own_key=has_own_key,
            estimated_request_tokens=estimated_tokens,
        )
    except UsageLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

NEW_CHAT_TOPLINE = os.getenv("VIGZONE_NEW_CHAT_TOPLINE", "Start with a real task")
NEW_CHAT_SUBTITLE = os.getenv(
    "VIGZONE_NEW_CHAT_SUBTITLE",
    "Open a fresh chat for one focused goal. Tell {app_name} what you are trying to finish, attach useful files, or choose a starter below."
)
GROQ_HINT_TEXT = os.getenv(
    "VIGZONE_GROQ_HINT",
    "Groq is fast and generous on the free tier — cheaper than most alternatives for a project like this."
)
GREETING_OPTIONS = [
    x.strip() for x in os.getenv(
        "VIGZONE_GREETING_OPTIONS",
        "Back at it,|Welcome back,|Good to see you,|Hey there,"
    ).split("|") if x.strip()
] or ["Welcome back,"]


def _safe_share_id() -> str:
    return _secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]


def _safe_message_text(value: Any, limit: int = 12000) -> str:
    if isinstance(value, str):
        return value[:limit]
    try:
        return json.dumps(value, ensure_ascii=False)[:limit]
    except Exception:
        return str(value)[:limit]


def _render_share_html(title: str, messages: list[dict]) -> str:
    import html
    safe_title = html.escape(title or "Vigzone chat")
    rows = []
    for m in messages[:200]:
        role_raw = str(m.get("role", "message"))[:40]
        role = html.escape(role_raw)
        text = html.escape(_safe_message_text(m.get("displayText") or m.get("content") or "", 10000))
        cls = "user" if role_raw == "user" else "assistant"
        rows.append(f'<article class="msg {cls}"><div class="role">{role}</div><div class="bubble">{text}</div></article>')
    body = "\n".join(rows) or '<p class="empty">No messages shared.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{safe_title}</title>
<style>
:root{{color-scheme:dark;--bg:#090a0f;--card:#161922;--muted:#8f96a8;--text:#eceef4;--accent:#ff6b4a;--border:#ffffff18}}
body{{margin:0;background:radial-gradient(circle at 50% 0,#ff6b4a22,transparent 42%),var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}
.wrap{{max-width:860px;margin:0 auto;padding:34px 16px 56px}}
h1{{font-size:28px;margin:0 0 6px}} .meta{{color:var(--muted);margin-bottom:24px}}
.msg{{margin:14px 0;display:flex;flex-direction:column;gap:5px}} .role{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:800}}
.bubble{{white-space:pre-wrap;border:1px solid var(--border);border-radius:18px;padding:14px 16px;background:var(--card);box-shadow:0 18px 50px -34px #000}}
.user .bubble{{background:#ff6b4a;color:#160b06;border-color:#ff6b4a;margin-left:auto;max-width:78%}} .assistant .bubble{{max-width:86%}}
.badge{{display:inline-flex;gap:8px;align-items:center;border:1px solid var(--border);border-radius:999px;padding:7px 10px;color:var(--muted);font-size:12px}}
</style>
</head>
<body><main class="wrap"><div class="badge">{html.escape(APP_NAME)} shared chat</div><h1>{safe_title}</h1><div class="meta">Exported public read-only view</div>{body}</main></body></html>"""


@app.get("/api/app/version", tags=["Product"])
async def app_version():
    return JSONResponse({
        "version": APP_VERSION,
        "name": APP_BUILD_NAME,
        "app_name": APP_NAME,
        "features": [
            "Private versioned Brain sync",
            "Per-user chat history",
            "Explicit Learning Center memory",
            "Bounded document and OCR analysis",
            "Voice transcription",
            "Live-source context",
            "Image generation and editing",
            "Website Studio export",
            "TEAM seats and email-bound invitations",
            "Shared TEAM workspaces and notes",
            "TEAM usage analytics and custom persona",
            "Standard, priority, and dedicated support queues",
            "Licensed Openverse image search",
            "Expiring shared chats",
            "Account export and deletion",
        ],
    })


@app.get("/api/public/config", tags=["Product"])
async def public_config():
    """Frontend living config. Keeps branding/text/URLs out of hardcoded HTML."""
    return JSONResponse({
        "app_name": APP_NAME,
        "short_name": APP_SHORT_NAME,
        "build_name": APP_BUILD_NAME,
        "version": APP_VERSION,
        "groq_keys_url": GROQ_KEYS_URL,
        "groq_docs_url": GROQ_DOCS_URL,
        "google_drive_api_key": GOOGLE_DRIVE_API_KEY,
        "google_drive_client_id": GOOGLE_DRIVE_CLIENT_ID,
        "drive_picker_enabled": bool(GOOGLE_DRIVE_API_KEY and GOOGLE_DRIVE_CLIENT_ID),
        "email_delivery_enabled": mailer.is_configured(),
        "supported_uploads": {
            "documents": ["pdf", "docx", "rtf", "xlsx", "xlsm", "csv", "tsv", "pptx"],
            "images": ["png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "ico"],
            "archives": ["zip", "tar", "tgz"],
            "archive_capability": "manifest_only",
            "audio_video_capability": "metadata_only",
        },
        "new_chat_topline": NEW_CHAT_TOPLINE,
        "new_chat_subtitle": NEW_CHAT_SUBTITLE.format(app_name=APP_NAME),
        "groq_hint": GROQ_HINT_TEXT,
        "greetings": GREETING_OPTIONS,
        "available_models": MODEL_CATALOG,
        "default_model": FAST_MODEL,
        "labels": {
            "assistant": APP_NAME,
            "settings_signed_in": f"Signed in to {APP_NAME}",
            "share_badge": f"{APP_NAME} shared chat",
            "api_default": "Groq (default)",
            "api_own": "Groq (your key)",
        },
        # Paddle billing (empty strings if not configured)
        "paddle_client_token": PADDLE_CLIENT_TOKEN or None,
        "paddle_vendor_id": PADDLE_CLIENT_TOKEN or None,
        "paddle_pro_price_id": PADDLE_PRO_PRICE_ID or None,
        "paddle_team_price_id": PADDLE_TEAM_PRICE_ID or None,
    })


@app.get("/api/models/available", tags=["AI"])
async def available_models_endpoint():
    """Return available Groq models and their capabilities."""
    return JSONResponse({
        "models": MODEL_CATALOG,
        "default": FAST_MODEL,
    })


@app.get("/api/brain/cloud", tags=["Brain"])
async def get_brain_cloud(user: dict = Depends(require_current_user)):
    return JSONResponse(authmod.get_brain_snapshot(user["id"]))


@app.post("/api/brain/cloud", tags=["Brain"])
async def save_brain_cloud(req: BrainCloudSyncRequest, user: dict = Depends(require_current_user)):
    try:
        result = authmod.save_brain_snapshot(
            user["id"],
            req.data,
            req.client_updated_at,
            req.base_version,
        )
    except authmod.StateConflictError as exc:
        return JSONResponse(
            {"detail": str(exc), "current": exc.current},
            status_code=409,
        )
    except authmod.AuthError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    return JSONResponse(result)


@app.post("/api/feedback", tags=["Feedback"])
async def save_feedback(req: FeedbackCreateRequest, user: dict = Depends(require_current_user)):
    item = {
        "message_id": req.message_id,
        "conversation_id": req.conversation_id,
        "rating": req.rating,
        "reason": req.reason or "",
        "message_text": req.message_text or "",
        "assistant_text": req.assistant_text or "",
        "context": req.context or {},
    }
    try:
        feedback_id = authmod.save_feedback_record(user["id"], item)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return JSONResponse({"ok": True, "id": feedback_id})


@app.post("/api/share/chat", tags=["Share"])
async def share_chat(req: ShareChatRequest, user: dict = Depends(require_current_user)):
    if not req.public:
        raise HTTPException(status_code=400, detail="Private share links are not supported.")
    share_id = _safe_share_id()
    try:
        payload = authmod.create_shared_chat(
            user["id"],
            share_id,
            req.title,
            req.messages,
            req.public,
            req.expires_in_days,
        )
    except authmod.AuthError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    return JSONResponse({
        "ok": True,
        "share_id": share_id,
        "url": f"/share/{share_id}",
        "expires_at": payload["expires_at"],
    })


@app.get("/api/share/chats", tags=["Share"])
async def my_shared_chats(user: dict = Depends(require_current_user)):
    return JSONResponse({"shares": authmod.list_shared_chats(user["id"])})


@app.delete("/api/share/chat/{share_id}", tags=["Share"])
async def revoke_shared_chat(share_id: str, user: dict = Depends(require_current_user)):
    safe_id = re.sub(r"[^A-Za-z0-9]", "", share_id)[:32]
    if not authmod.revoke_shared_chat(user["id"], safe_id):
        raise HTTPException(status_code=404, detail="Shared chat not found.")
    return JSONResponse({"ok": True, "share_id": safe_id, "revoked": True})


@app.get("/share/{share_id}", response_class=HTMLResponse, tags=["Share"])
async def public_share_page(request: Request, share_id: str):
    _enforce_rate_limit(request, "public_share", 120, window_seconds=60)
    share_id = re.sub(r"[^A-Za-z0-9]", "", share_id)[:32]
    doc = authmod.get_shared_chat(share_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Shared chat not found.")
    return HTMLResponse(
        _render_share_html(doc.get("title") or "Vigzone chat", doc.get("messages") or []),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/admin/analytics", tags=["Admin"])
async def admin_analytics(user: dict = Depends(require_admin)):
    return JSONResponse({**authmod.product_analytics(), "version": APP_VERSION})


@app.get("/api/early-access", tags=["Product"])
async def early_access_catalog(user: dict = Depends(require_current_user)):
    _require_feature(user, "early_access", "Preview model access")
    return JSONResponse({
        "enabled": True,
        "channel": "preview",
        "features": [
            {
                "id": "qwen-vision-preview",
                "name": "Qwen 3.6 vision and reasoning",
                "status": "available",
                "models": ["qwen/qwen3.6-27b"],
            }
        ],
    })


@app.get("/api/search/images", tags=["Search"])
async def search_images(request: Request, q: str = "", limit: int = 8, user: dict = Depends(require_current_user)):
    _require_feature(user, "image_search", "Image search")
    _enforce_rate_limit(request, "image_search", 30, user=user, window_seconds=3600)
    query = (q or "").strip()[:300]
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Enter an image search query.")
    limit = max(1, min(int(limit), 12))
    try:
        results = await asyncio.wait_for(image_search(query, limit), timeout=10.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Image search timed out. Please try again.")
    return JSONResponse({"query": query, "provider": "Openverse", "results": results})


@app.get("/api/support/tickets", tags=["Support"])
async def my_support_tickets(user: dict = Depends(require_current_user)):
    level = (
        "dedicated"
        if billing.feature_allowed(user, "dedicated_support")
        else ("priority" if billing.feature_allowed(user, "priority_support") else "standard")
    )
    return JSONResponse({"support_level": level, "tickets": authmod.list_support_tickets(user["id"])})


@app.post("/api/support/tickets", tags=["Support"])
async def create_support_ticket(
    request: Request,
    req: SupportTicketRequest,
    user: dict = Depends(require_current_user),
):
    _enforce_rate_limit(request, "support_ticket", 5, user=user, window_seconds=86400)
    try:
        ticket = authmod.create_support_ticket(user, req.subject, req.message)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse({"ok": True, "ticket": ticket})


@app.get("/api/admin/support/tickets", tags=["Admin"])
async def admin_support_tickets(status: str = "", user: dict = Depends(require_admin)):
    return JSONResponse({"tickets": authmod.list_admin_support_tickets(status)})


@app.patch("/api/admin/support/tickets/{ticket_id}", tags=["Admin"])
async def admin_update_support_ticket(
    ticket_id: str,
    req: SupportTicketUpdateRequest,
    user: dict = Depends(require_admin),
):
    safe_id = re.sub(r"[^A-Za-z0-9_]", "", ticket_id)[:40]
    try:
        ticket = authmod.update_support_ticket(safe_id, req.status, req.admin_response)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc))
    return JSONResponse({"ok": True, "ticket": ticket})


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
    return os.getenv("VIGZONE_BACKEND_LABEL", "Groq (hosted)")


def _setup_message() -> str:
    return (
        f"{APP_NAME} isn't configured. Add a valid GROQ_API_KEY in your deployment "
        f"environment variables, then redeploy/restart the app. Get a key at {GROQ_KEYS_URL}."
    )


@app.get("/health/live", tags=["System"])
async def health_live():
    """Process liveness only; never depends on an external AI provider."""

    return JSONResponse({"status": "alive", "version": APP_VERSION})


async def _readiness_response() -> JSONResponse:
    configured = await is_configured()
    database_ready = authmod.database_healthcheck()
    ready = bool(configured and database_ready)
    body = HealthCheckResponse(
        status="ready" if ready else "not_ready",
        backend_configured=configured,
        mode="testing" if IS_TESTING else "production",
        backend=_backend_label(),
        setup_message="" if configured else _setup_message(),
    ).model_dump()
    body["database_ready"] = database_ready
    return JSONResponse(body, status_code=200 if ready else 503)


@app.get("/health/ready", tags=["System"])
async def health_ready():
    """Deployment readiness: local database plus configured AI backend."""

    return await _readiness_response()


@app.get("/health", tags=["System"])
async def health_check():
    """Compatibility alias used by the existing frontend."""

    return await _readiness_response()


@app.get("/api/capabilities", response_model=CapabilitiesResponse, tags=["System"])
async def get_capabilities():
    internet_search_enabled = os.getenv("WEB_SEARCH_ENABLED", "true").lower() not in ("false", "0", "no")
    return CapabilitiesResponse(
        internet_search_enabled=internet_search_enabled,
        internet_access_configured=internet_search_enabled,
        current_time_available=True,
        configured_timezone=_get_user_timezone_name(),
        accuracy_note=(
            "Current time/date are deterministic. Live answers use targeted APIs plus keyless web/news search "
            "when the user asks for current, recent, weather, price, currency, sports, roles, or news data. "
            "No system can guarantee 100% truth for every world fact; Vigzone now verifies live when possible and avoids guessing when live sources are unavailable."
        ),
    )


@app.get("/api/model-info", response_model=ModelInfoResponse, tags=["Model"])
async def get_model_info():
    return ModelInfoResponse(
        name="Vigzone AI",
        version=APP_VERSION,
        model=DEFAULT_MODEL,
        fast_model=FAST_MODEL,
        complex_model=COMPLEX_MODEL,
        vision_model=VISION_MODEL,
        routing_enabled=MODEL_ROUTING_ENABLED,
        backend=_backend_label(),
        status="ready" if await is_configured() else "groq_not_configured",
        mode="testing" if IS_TESTING else "production",
    )


@app.get("/api/stats", tags=["System"])
async def get_stats():
    return JSONResponse({
        "name": "Vigzone AI",
        "version": APP_VERSION,
        "mode": "testing" if IS_TESTING else "production",
        "description": "A real conversational AI assistant — powered by Groq",
        "endpoints": {
            "health": "/health",
            "capabilities": "/api/capabilities",
            "model_info": "/api/model-info",
            "realworld_data": "GET /api/realworld-data",
            "realworld_live_context": "GET /api/realworld-data/live-context?query=...",
            "realworld_capabilities": "GET /api/realworld-data/capabilities",
            "upload": "POST /api/upload",
            "drive_import": "POST /api/drive/import",
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
        "docs": "/docs" if app.docs_url else None,
    })


# ── Real-World Data endpoints (weather, prices, etc.) ────────────────────────

try:
    from realworld_data import get_weather, get_price, get_exchange_rate, get_datetime_info
    HAS_REALWORLD_ENDPOINTS = True
except ImportError:
    HAS_REALWORLD_ENDPOINTS = False
    logger.warning("realworld_data module not available; skipping real-world data endpoints")


@app.get("/api/realworld-data/weather", tags=["Real-World Data"])
async def get_weather_endpoint(
    request: Request,
    location: str = None,
    user: dict = Depends(require_current_user),
):
    _enforce_rate_limit(request, "realworld", 30, user=user, window_seconds=60)
    if location is not None:
        location = re.sub(r"[\x00-\x1f\x7f]", "", location).strip()[:100]
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
async def get_price_endpoint(
    request: Request,
    symbol: str,
    asset_type: str = "auto",
    user: dict = Depends(require_current_user),
):
    _enforce_rate_limit(request, "realworld", 30, user=user, window_seconds=60)
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.^=-]{1,15}", symbol):
        raise HTTPException(status_code=400, detail="Invalid asset symbol.")
    if asset_type not in {"auto", "stock", "crypto"}:
        raise HTTPException(status_code=400, detail="asset_type must be auto, stock, or crypto.")
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
async def get_exchange_rate_endpoint(
    request: Request,
    from_currency: str,
    to_currency: str,
    user: dict = Depends(require_current_user),
):
    _enforce_rate_limit(request, "realworld", 30, user=user, window_seconds=60)
    from_currency = from_currency.strip().upper()
    to_currency = to_currency.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", from_currency) or not re.fullmatch(r"[A-Z]{3}", to_currency):
        raise HTTPException(status_code=400, detail="Currencies must be three-letter ISO codes.")
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
async def get_current_time_endpoint(user: dict = Depends(require_current_user)):
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



# ── Deterministic date/time answers ───────────────────────────────────────────
def _message_text_plain(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "\n".join(p for p in parts if p)
    return ""


def _normalize_chat_messages(messages: list[dict]) -> list[dict]:
    """Validate client chat history and retain only the latest image turn."""

    latest_image_index = -1
    for index, message in enumerate(messages):
        content = message.get("content")
        if isinstance(content, list) and any(
            isinstance(part, dict) and part.get("type") == "image_url"
            for part in content
        ):
            latest_image_index = index

    total_text_chars = 0
    total_image_chars = 0
    image_count = 0
    normalized: list[dict] = []
    for index, message in enumerate(messages):
        content = message.get("content")
        if isinstance(content, str):
            total_text_chars += len(content)
            normalized.append({**message, "content": content})
            continue
        if not isinstance(content, list) or len(content) > 12:
            raise HTTPException(status_code=400, detail="Invalid message content.")
        parts: list[dict] = []
        omitted_old_image = False
        for part in content:
            if not isinstance(part, dict):
                raise HTTPException(status_code=400, detail="Invalid message content part.")
            part_type = part.get("type")
            if part_type == "text":
                text = str(part.get("text") or "")
                total_text_chars += len(text)
                parts.append({"type": "text", "text": text})
                continue
            if part_type != "image_url":
                raise HTTPException(status_code=400, detail="Unsupported message content type.")
            if index != latest_image_index:
                omitted_old_image = True
                continue
            image_url = (part.get("image_url") or {}).get("url")
            if not isinstance(image_url, str) or not re.match(
                r"^data:image/(?:png|jpeg|webp);base64,",
                image_url,
                re.IGNORECASE,
            ):
                raise HTTPException(status_code=400, detail="Images must be uploaded through Vigzone.")
            image_count += 1
            total_image_chars += len(image_url)
            if image_count > 5 or len(image_url) > 8_000_000 or total_image_chars > 22_000_000:
                raise HTTPException(status_code=413, detail="Too many or oversized image attachments.")
            parts.append({"type": "image_url", "image_url": {"url": image_url}})
        if omitted_old_image:
            parts.append({
                "type": "text",
                "text": "[An older image attachment was omitted from this request to control size.]",
            })
        normalized.append({**message, "content": parts})

    if total_text_chars > 180_000:
        raise HTTPException(
            status_code=413,
            detail="Conversation context is too large. Start a new chat or shorten attached text.",
        )
    return normalized


def _is_simple_datetime_request(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    q = re.sub(r"[^\w\s]+", " ", raw.lower())
    q = re.sub(r"\s+", " ", q).strip()
    if not q or len(q.split()) > 12:
        return False

    dt_patterns = [
        r"\bwhat\s+time\s+(is\s+it|is\s+it\s+now)\b",
        r"\bwhat\s+(is\s+)?(the\s+)?(current\s+)?(time|date|day)\b",
        r"\bwhat\s+day\s+is\s+it\b",
        r"\bwhat\s+is\s+today\s*s?\s+date\b",
        r"\b(tell|give|show)\s+(me\s+)?(the\s+)?(current\s+)?(time|date|day)\b",
        r"^(current\s+)?(date|time|day|time now|date today)\??$",
        r"^(දිනය|අද\s+දිනය|වේලාව|වෙලාව|දැනට\s+වේලාව)\??$",
        r"^(தேதி|இன்று\s+தேதி|நேரம்|மணி)\??$",
    ]
    return any(re.search(pat, q) for pat in dt_patterns)


def _datetime_info_for_client(client_timezone: Optional[str] = None) -> dict:
    if client_timezone:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(client_timezone)
            now = datetime.now(tz)
            return {
                "full": now.strftime("%d %B %Y, %I:%M %p %Z (%A)"),
                "date": now.strftime("%d %B %Y"),
                "time": now.strftime("%I:%M %p"),
                "timezone": client_timezone,
                "day": now.strftime("%A"),
                "iso": now.isoformat(),
            }
        except Exception:
            pass
    if HAS_REALWORLD_ENDPOINTS:
        try:
            return get_datetime_info()
        except Exception:
            logger.exception("Failed to get realworld datetime info")
    now = datetime.now().astimezone()
    return {
        "full": now.strftime("%d %B %Y, %I:%M %p %Z (%A)"),
        "date": now.strftime("%d %B %Y"),
        "time": now.strftime("%I:%M %p"),
        "timezone": str(now.tzinfo or "local"),
        "day": now.strftime("%A"),
        "iso": now.isoformat(),
    }


def _build_datetime_answer(text: str, client_timezone: Optional[str] = None) -> str:
    info = _datetime_info_for_client(client_timezone)
    q = (text or "").lower()
    wants_date = any(k in q for k in ("date", "today", "calendar", "දිනය", "අද", "தேதி", "இன்று"))
    wants_time = any(k in q for k in ("time", "now", "වේලාව", "වෙලාව", "நேரம்", "மணி"))
    wants_day = any(k in q for k in ("day", "weekday", "දවස", "நாள்"))
    tz = info.get("timezone") or "local timezone"

    if wants_date and wants_time:
        return f"📅 Today is **{info['day']}, {info['date']}**.\n🕒 The current time is **{info['time']}** ({tz})."
    if wants_time and not wants_date:
        return f"🕒 The current time is **{info['time']}** ({tz})."
    if wants_day and not wants_date:
        return f"📅 Today is **{info['day']}**. The date is **{info['date']}**."
    return f"📅 Today is **{info['day']}, {info['date']}**."


async def _stream_direct_answer(stream_id: str, text: str):
    yield f'data: {json.dumps({"stream_id": stream_id})}\n\n'
    yield f'data: {json.dumps({"content": text})}\n\n'
    yield "data: [DONE]\n\n"


# ── Fact Verification & Accuracy endpoints ──────────────────────────────────

try:
    from fact_verification import verify_factual_claim
    HAS_FACT_VERIFICATION = True
except ImportError:
    HAS_FACT_VERIFICATION = False
    logger.warning("fact_verification module not available; skipping accuracy endpoints")


class VerifyClaimRequest(BaseModel):
    claim: str = Field(..., max_length=1000)


@app.post("/api/verify-claim", tags=["Accuracy"])
async def verify_claim_endpoint(
    request: Request,
    req: VerifyClaimRequest,
    user: dict = Depends(require_current_user),
):
    """Retrieve attributable evidence without inventing a confidence score."""

    _enforce_rate_limit(request, "verification", 15, user=user, window_seconds=60)
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
        "effective_plan": billing.effective_plan(user),
        "plan_messages_today": authmod.get_daily_message_count(user["id"]),
        "plan_message_limit": 50 if billing.effective_plan(user) == "free" else None,
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
    api_key: str = Field(..., min_length=20, max_length=300)


@app.post("/api/me/groq-key/validate", tags=["Account"])
async def validate_my_groq_key(
    http_request: Request,
    req: GroqKeyRequest,
    user: dict = Depends(require_current_user),
):
    """Check whether a pasted Groq key actually works, WITHOUT saving it yet."""
    _enforce_rate_limit(http_request, "key_validate", 10, user=user, window_seconds=3600)
    result = await validate_groq_api_key(req.api_key)
    return JSONResponse(result)


@app.post("/api/me/groq-key/activate", tags=["Account"])
async def activate_my_groq_key(
    http_request: Request,
    req: GroqKeyRequest,
    user: dict = Depends(require_current_user),
):
    """
    Validate (again, server-side — never trust the client) and save the
    user's Groq key, then switch their chats over to using it.
    """
    _enforce_rate_limit(http_request, "key_validate", 10, user=user, window_seconds=3600)
    result = await validate_groq_api_key(req.api_key)
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=result.get("message", "That Groq key didn't validate."))
    authmod.set_user_groq_key(user["id"], req.api_key.strip())
    return JSONResponse({"activated": True, "message": "Your Groq key is now powering your chats."})


@app.post("/api/me/groq-key/deactivate", tags=["Account"])
async def deactivate_my_groq_key(user: dict = Depends(require_current_user)):
    """Forget the stored key and switch the user back to Vigzone's default Groq key."""
    authmod.clear_user_groq_key(user["id"])
    return JSONResponse({"activated": False, "message": "Switched back to Vigzone's default Groq plan."})


# ── Auth endpoints ────────────────────────────────────────────────────────────
def _public_base_url(request: Request) -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    return configured or str(request.base_url).rstrip("/")


async def _deliver_verification_email(user: dict, request: Request) -> bool:
    if not mailer.is_configured() or user.get("email_verified"):
        return False
    token, email = authmod.create_email_verification_token(user["id"])
    link = f"{_public_base_url(request)}/verify-email?token={token}"
    text = (
        f"Verify your {APP_NAME} email address:\n\n{link}\n\n"
        "This link expires in 24 hours. If you did not create this account, "
        "you can ignore this message."
    )
    await asyncio.to_thread(
        mailer.send_email,
        email,
        f"Verify your {APP_NAME} email",
        text,
    )
    return True


@app.post("/api/auth/signup", tags=["Auth"])
async def signup(request: Request, req: SignupRequest):
    _enforce_rate_limit(request, "signup", 5, window_seconds=3600)
    try:
        user = authmod.create_user_with_password(req.email, req.password, req.name)
    except authmod.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = authmod.create_session(user["id"], request_fingerprint(request))
    verification_sent = False
    if mailer.is_configured():
        try:
            verification_sent = await _deliver_verification_email(user, request)
        except (authmod.AuthError, mailer.MailError):
            logger.warning("Could not deliver signup verification email")
    response = JSONResponse({
        "user": user,
        "verification_sent": verification_sent,
    })
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/login", tags=["Auth"])
async def login(request: Request, req: LoginRequest):
    _enforce_rate_limit(request, "login", 10, window_seconds=900)
    try:
        user = authmod.verify_password_login(req.email, req.password)
    except authmod.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    token = authmod.create_session(user["id"], request_fingerprint(request))
    response = JSONResponse({"user": user})
    _set_session_cookie(response, token)
    return response


@app.post("/api/auth/verification/request", tags=["Auth"])
async def request_email_verification(
    request: Request,
    user: dict = Depends(require_current_user),
):
    _enforce_rate_limit(request, "verify_email", 3, user=user, window_seconds=3600)
    if not mailer.is_configured():
        raise HTTPException(status_code=503, detail="Email delivery is not configured.")
    try:
        sent = await _deliver_verification_email(user, request)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except mailer.MailError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return JSONResponse({"ok": True, "sent": sent})


@app.get("/verify-email", response_class=HTMLResponse, tags=["Auth"])
async def verify_email_page(token: str = ""):
    import html

    try:
        authmod.verify_email_token(token)
        title = "Email verified"
        message = "Your email is verified. You can return to Vigzone."
    except authmod.AuthError:
        title = "Verification failed"
        message = "This verification link is invalid or expired."
    return HTMLResponse(
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' "
        "content='width=device-width,initial-scale=1'><title>"
        + html.escape(title)
        + "</title><style>body{font:16px system-ui;background:#090a0f;color:#eceef4;"
        "display:grid;place-items:center;min-height:100vh;margin:0}.card{max-width:520px;"
        "padding:28px;border:1px solid #ffffff22;border-radius:22px;background:#161922}"
        "a{color:#ff8064}</style></head><body><main class='card'><h1>"
        + html.escape(title)
        + "</h1><p>"
        + html.escape(message)
        + "</p><a href='/chat'>Open Vigzone</a></main></body></html>",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/auth/password/forgot", tags=["Auth"])
async def forgot_password(request: Request, req: EmailRequest):
    _enforce_rate_limit(request, "forgot_password", 5, window_seconds=3600)
    if not mailer.is_configured():
        raise HTTPException(status_code=503, detail="Email delivery is not configured.")
    item = authmod.create_password_reset_token(req.email)
    if item:
        token, email = item
        link = f"{_public_base_url(request)}/reset-password?token={token}"
        text = (
            f"Reset your {APP_NAME} password:\n\n{link}\n\n"
            "This link expires in 30 minutes. If you did not request it, ignore this message."
        )
        try:
            await asyncio.to_thread(
                mailer.send_email,
                email,
                f"Reset your {APP_NAME} password",
                text,
            )
        except mailer.MailError:
            logger.warning("Password reset email delivery failed")
    return JSONResponse({
        "ok": True,
        "message": "If that account exists, a reset link has been sent.",
    })


@app.post("/api/auth/password/reset", tags=["Auth"])
async def reset_password(request: Request, req: PasswordResetRequest):
    _enforce_rate_limit(request, "reset_password", 10, window_seconds=3600)
    try:
        authmod.reset_password_with_token(req.token, req.new_password)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse({"ok": True, "message": "Password reset. Sign in again."})


@app.get("/reset-password", response_class=HTMLResponse, tags=["Auth"])
async def reset_password_page(token: str = ""):
    import html

    safe_token = html.escape(token[:256], quote=True)
    return HTMLResponse(
        """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><title>Reset password</title>
<style>body{font:16px system-ui;background:#090a0f;color:#eceef4;display:grid;
place-items:center;min-height:100vh;margin:0}.card{width:min(420px,calc(100% - 40px));
padding:28px;border:1px solid #ffffff22;border-radius:22px;background:#161922}
input,button{box-sizing:border-box;width:100%;margin-top:12px;padding:12px;border-radius:12px;
border:1px solid #ffffff22}input{background:#090a0f;color:#fff}button{background:#ff6b4a;
color:white;font-weight:800;cursor:pointer}.status{min-height:24px;margin-top:12px}</style>
</head><body><main class="card"><h1>Reset password</h1><p>Use at least 10 characters.</p>
<form id="form"><input id="password" type="password" minlength="10" maxlength="256"
autocomplete="new-password" required><button>Save new password</button></form>
<div class="status" id="status"></div></main><script>
const token='"""
        + safe_token
        + """';document.getElementById('form').addEventListener('submit',async(e)=>{
e.preventDefault();const status=document.getElementById('status');status.textContent='Saving…';
const response=await fetch('/api/auth/password/reset',{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify({token,
new_password:document.getElementById('password').value})});
const data=await response.json().catch(()=>({}));status.textContent=response.ok
?'Password reset. You can sign in now.':(data.detail||'Reset failed.');});</script></body></html>""",
        headers={"Cache-Control": "no-store"},
    )


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
async def google_login(request: Request):
    _enforce_rate_limit(request, "google_login", 20, window_seconds=900)
    if not authmod.google_is_configured():
        return RedirectResponse(url="/?error=google_not_configured")
    state    = _secrets.token_urlsafe(16)
    auth_url = authmod.google_build_auth_url(state)
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="vigzone_oauth_state", value=state,
        httponly=True,
        secure=is_production(),
        samesite="lax",
        max_age=600,
        path="/",
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
            profile["google_id"],
            profile["email"],
            profile["name"],
            email_verified=profile.get("email_verified", False),
        )
    except authmod.AuthError:
        return RedirectResponse(url="/?error=google_failed")
    token = authmod.create_session(user["id"], request_fingerprint(request))
    response = RedirectResponse(url="/chat")
    _set_session_cookie(response, token)
    response.delete_cookie("vigzone_oauth_state", path="/")
    return response


@app.post("/api/account/password", tags=["Account"])
async def change_account_password(
    req: PasswordChangeRequest,
    user: dict = Depends(require_current_user),
):
    try:
        authmod.change_password(user["id"], req.current_password, req.new_password)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    response = JSONResponse({
        "ok": True,
        "message": "Password changed. Sign in again on this device.",
    })
    response.delete_cookie(authmod.SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/api/account/export", tags=["Account"])
async def export_account_data(user: dict = Depends(require_current_user)):
    payload = authmod.export_user_data(user["id"])
    response = JSONResponse(payload)
    response.headers["Content-Disposition"] = 'attachment; filename="vigzone-account-export.json"'
    response.headers["Cache-Control"] = "no-store"
    return response


@app.delete("/api/account", tags=["Account"])
async def delete_my_account(
    req: AccountDeleteRequest,
    user: dict = Depends(require_current_user),
):
    if authmod.account_has_password(user["id"]) and not authmod.verify_user_password(
        user["id"],
        req.password,
    ):
        raise HTTPException(status_code=403, detail="Password confirmation failed.")
    authmod.delete_account(user["id"])
    response = JSONResponse({"ok": True, "deleted": True})
    response.delete_cookie(authmod.SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/api/conversations", tags=["Conversations"])
async def list_my_conversations(user: dict = Depends(require_current_user)):
    return JSONResponse({"conversations": authmod.list_conversations(user["id"])})


@app.get("/api/conversations/{conversation_id}", tags=["Conversations"])
async def get_my_conversation(
    conversation_id: str,
    user: dict = Depends(require_current_user),
):
    item = authmod.get_conversation(user["id"], conversation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return JSONResponse(item)


@app.put("/api/conversations/{conversation_id}", tags=["Conversations"])
async def sync_my_conversation(
    conversation_id: str,
    req: ConversationSyncRequest,
    user: dict = Depends(require_current_user),
):
    if conversation_id != req.id:
        raise HTTPException(status_code=400, detail="Conversation ID mismatch.")
    try:
        item = authmod.upsert_conversation(
            user["id"],
            req.id,
            req.title,
            req.messages,
            req.base_revision,
        )
    except authmod.StateConflictError as exc:
        return JSONResponse(
            {"detail": str(exc), "current": exc.current},
            status_code=409,
        )
    except authmod.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse(item)


@app.delete("/api/conversations/{conversation_id}", tags=["Conversations"])
async def delete_my_conversation(
    conversation_id: str,
    user: dict = Depends(require_current_user),
):
    if not authmod.delete_conversation(user["id"], conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return JSONResponse({"ok": True, "deleted": True})



# ── TEAM account management ──────────────────────────────────────────────────
@app.get("/api/team", tags=["Team"])
async def get_my_team(user: dict = Depends(require_current_user)):
    _require_feature(user, "team_workspace", "TEAM management")
    try:
        return JSONResponse(authmod.get_team_details(user["id"], user.get("name") or ""))
    except authmod.AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.patch("/api/team", tags=["Team"])
async def update_my_team(req: TeamProfileRequest, user: dict = Depends(require_current_user)):
    _require_feature(user, "custom_ai_persona", "Custom AI persona")
    try:
        team = authmod.update_team_profile(
            user["id"], req.name, req.persona_name, req.persona_instructions
        )
    except authmod.AuthError as exc:
        raise HTTPException(status_code=403 if "owner" in str(exc).lower() else 400, detail=str(exc))
    return JSONResponse({"ok": True, "team": team})


@app.post("/api/team/invitations", tags=["Team"])
async def invite_team_member(
    request: Request,
    req: TeamInviteRequest,
    user: dict = Depends(require_current_user),
):
    _require_feature(user, "team_workspace", "TEAM seats")
    _enforce_rate_limit(request, "team_invite", 20, user=user, window_seconds=86400)
    try:
        invitation = authmod.create_team_invitation(user["id"], req.email)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # Keep the bearer token in the URL fragment so browsers never send it in
    # HTTP request logs or Referrer headers. The chat client stores it only
    # long enough to complete the authenticated acceptance request.
    invite_url = f"{_public_base_url(request)}/chat#team_invite={invitation['token']}"
    email_sent = False
    if mailer.is_configured():
        try:
            details = authmod.get_team_details(user["id"], user.get("name") or "")
            team_name = details["team"]["name"]
            await asyncio.to_thread(
                mailer.send_email,
                invitation["email"],
                f"You're invited to {team_name} on {APP_NAME}",
                (
                    f"{user.get('name') or user.get('email')} invited you to join {team_name}.\n\n"
                    f"Sign in with {invitation['email']} and accept your seat here:\n{invite_url}\n\n"
                    f"This invitation expires {invitation['expires_at']}."
                ),
            )
            email_sent = True
        except (mailer.MailError, authmod.AuthError):
            logger.warning("TEAM invitation email delivery failed", exc_info=True)
    public_invitation = {key: value for key, value in invitation.items() if key != "token"}
    return JSONResponse({
        "ok": True,
        "invitation": public_invitation,
        "invite_url": invite_url,
        "email_sent": email_sent,
    })


@app.post("/api/team/invitations/accept", tags=["Team"])
async def accept_team_invitation(req: TeamInviteAcceptRequest, user: dict = Depends(require_current_user)):
    try:
        membership = authmod.accept_team_invitation(user["id"], req.token)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return JSONResponse({"ok": True, "membership": membership, "reload_required": True})


@app.delete("/api/team/invitations/{invitation_id}", tags=["Team"])
async def revoke_team_invitation(invitation_id: int, user: dict = Depends(require_current_user)):
    _require_feature(user, "team_workspace", "TEAM seats")
    try:
        authmod.revoke_team_invitation(user["id"], invitation_id)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=403 if "owner" in str(exc).lower() else 404, detail=str(exc))
    return JSONResponse({"ok": True})


@app.delete("/api/team/members/{member_user_id}", tags=["Team"])
async def remove_team_member(member_user_id: int, user: dict = Depends(require_current_user)):
    _require_feature(user, "team_workspace", "TEAM seats")
    try:
        authmod.remove_team_member(user["id"], member_user_id)
    except authmod.AuthError as exc:
        raise HTTPException(status_code=403 if "owner" in str(exc).lower() else 404, detail=str(exc))
    return JSONResponse({"ok": True})


@app.post("/api/team/leave", tags=["Team"])
async def leave_team(user: dict = Depends(require_current_user)):
    try:
        authmod.leave_team(user["id"])
    except authmod.AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return JSONResponse({"ok": True, "reload_required": True})


@app.get("/api/team/analytics", tags=["Team"])
async def team_analytics(days: int = 30, user: dict = Depends(require_current_user)):
    _require_feature(user, "usage_analytics", "TEAM usage analytics")
    try:
        return JSONResponse(authmod.get_team_analytics(user["id"], days))
    except authmod.AuthError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


# ── Workspaces / Deep Features v3 ─────────────────────────────────────────────
@app.get("/api/workspaces", tags=["Workspaces"])
async def api_list_workspaces(user: dict = Depends(require_current_user)):
    return JSONResponse({"workspaces": authmod.list_workspaces(user["id"])})


@app.post("/api/workspaces", tags=["Workspaces"])
async def api_create_workspace(req: WorkspaceCreateRequest, user: dict = Depends(require_current_user)):
    if req.shared:
        _require_feature(user, "team_workspace", "Shared workspace")
    if not billing.chat_mode_allowed(user, req.mode):
        raise HTTPException(status_code=403, detail="That workspace mode is available on Vigzone PRO and TEAM.")
    try:
        ws = authmod.create_workspace(user["id"], req.name, req.description, req.mode, req.shared)
        return JSONResponse({"workspace": ws})
    except authmod.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/api/workspaces/{workspace_id}", tags=["Workspaces"])
async def api_update_workspace(workspace_id: int, req: WorkspaceUpdateRequest, user: dict = Depends(require_current_user)):
    if req.mode is not None and not billing.chat_mode_allowed(user, req.mode):
        raise HTTPException(status_code=403, detail="That workspace mode is available on Vigzone PRO and TEAM.")
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
    title = (req.title or f"{APP_NAME} Export").strip()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if req.format == "html":
        import html as html_lib

        safe_title = html_lib.escape(title)
        body = [f"<h1>{safe_title}</h1><p>Exported {now}</p>"]
        for m in req.messages[:500]:
            role = html_lib.escape(str(m.get("role", "message")).title())
            content = str(m.get("displayText") or m.get("content") or "")
            body.append(
                f"<section><h2>{role}</h2><pre>{html_lib.escape(content)}</pre></section>"
            )
        data = (
            "<!doctype html><meta charset='utf-8'><title>"
            + safe_title
            + "</title><body>"
            + "\n".join(body)
            + "</body>"
        )
        media = "text/html"
        filename = "vigzone-chat-export.html"
    else:
        chunks = [title, f"Exported {now}", ""]
        for m in req.messages[:500]:
            role = str(m.get("role", "message")).upper()
            content = str(m.get("displayText") or m.get("content") or "")
            chunks.append(f"[{role}]\n{content}\n")
        data = "\n".join(chunks)
        media = "text/plain"
        filename = "vigzone-chat-export.txt"
    return JSONResponse({"filename": filename, "media_type": media, "content": data})


@app.post("/api/website/export", tags=["Website Studio"])
async def api_export_website(req: WebsiteExportRequest, user: dict = Depends(require_current_user)):
    _require_feature(user, "website_studio", "Website Studio")
    html = req.html.strip()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", html)
        zf.writestr("README.txt", f"Generated by {APP_NAME} Website Studio. Open index.html in a browser or upload it to your hosting provider.\n")
    data = buf.getvalue()
    requested = os.path.basename(req.filename)
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", requested).strip(".-")[:80] or "vigzone-website"
    filename = stem if stem.lower().endswith(".zip") else stem + ".zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Google Drive import ──────────────────────────────────────────────────────
_DRIVE_EXPORT_MIME = {
    "application/vnd.google-apps.document": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}
_DRIVE_CT_EXT = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/markdown": ".md",
    "application/json": ".json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _extract_drive_file_id(value: str) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", value):
        return value
    try:
        parsed = urlparse(value)
        qs = parse_qs(parsed.query)
        if qs.get("id"):
            return qs["id"][0]
        match = re.search(r"/(?:file|document|spreadsheets|presentation|drawings)/d/([A-Za-z0-9_-]+)", parsed.path)
        if match:
            return match.group(1)
        match = re.search(r"/open(?:/|\?|$).*id=([A-Za-z0-9_-]+)", value)
        if match:
            return match.group(1)
    except Exception:
        pass
    match = re.search(r"[-\w]{20,}", value)
    return match.group(0) if match else None


def _drive_name_from_headers(headers: dict, fallback: str, content_type: str = "") -> str:
    cd = headers.get("content-disposition") or headers.get("Content-Disposition") or ""
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.IGNORECASE)
    if match:
        return unquote(match.group(1)).strip() or fallback
    ext = _DRIVE_CT_EXT.get((content_type or "").split(";")[0].lower(), "")
    if ext and not fallback.lower().endswith(ext):
        return fallback + ext
    return fallback


async def _read_http_response_limited(
    response: httpx.Response,
    limit: int = MAX_UPLOAD_SIZE,
) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > limit:
                raise HTTPException(
                    status_code=413,
                    detail=f"Remote file exceeds the {limit // (1024 * 1024)} MB limit.",
                )
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"Remote file exceeds the {limit // (1024 * 1024)} MB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _download_drive_with_token(file_id: str, access_token: str, supplied_name: str = "", supplied_mime: str = "") -> tuple[bytes, str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=8.0, read=45.0, write=8.0, pool=8.0), follow_redirects=True) as client:
        meta_resp = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"fields": "id,name,mimeType,size", "supportsAllDrives": "true"},
            headers=headers,
        )
        if meta_resp.status_code >= 400:
            raise HTTPException(status_code=403, detail="Google Drive rejected access. Reconnect Drive or choose a file you can access.")
        meta = meta_resp.json()
        name = supplied_name or meta.get("name") or f"drive-file-{file_id}"
        mime = supplied_mime or meta.get("mimeType") or ""
        try:
            if meta.get("size") and int(meta["size"]) > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f'"{name}" is larger than the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit.',
                )
        except ValueError:
            pass

        if mime.startswith("application/vnd.google-apps."):
            export_mime, ext = _DRIVE_EXPORT_MIME.get(mime, ("application/pdf", ".pdf"))
            if not name.lower().endswith(ext):
                name += ext
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            params = {"mimeType": export_mime}
            content_type = export_mime
        else:
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            params = {"alt": "media", "supportsAllDrives": "true"}
            content_type = mime

        async with client.stream("GET", url, params=params, headers=headers) as resp:
            if resp.status_code >= 400:
                raise HTTPException(status_code=403, detail="Could not download this Google Drive file.")
            content_type = resp.headers.get("content-type", content_type)
            data = await _read_http_response_limited(resp)
            return data, name, content_type


async def _download_public_drive(file_id: str, source_url: str = "", supplied_name: str = "") -> tuple[bytes, str, str]:
    source = source_url or ""
    candidates: list[tuple[str, str, str]] = []

    # Native Google Docs public export URLs.
    if "/document/" in source:
        candidates.append((f"https://docs.google.com/document/d/{file_id}/export?format=docx", supplied_name or "google-doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        candidates.append((f"https://docs.google.com/document/d/{file_id}/export?format=txt", supplied_name or "google-doc.txt", "text/plain"))
    elif "/spreadsheets/" in source:
        candidates.append((f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx", supplied_name or "google-sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        candidates.append((f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv", supplied_name or "google-sheet.csv", "text/csv"))
    elif "/presentation/" in source:
        candidates.append((f"https://docs.google.com/presentation/d/{file_id}/export/pptx", supplied_name or "google-slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"))
        candidates.append((f"https://docs.google.com/presentation/d/{file_id}/export/pdf", supplied_name or "google-slides.pdf", "application/pdf"))

    # Binary/public Drive files.
    candidates.extend([
        (f"https://drive.google.com/uc?export=download&id={file_id}", supplied_name or f"drive-file-{file_id}", ""),
        (f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t", supplied_name or f"drive-file-{file_id}", ""),
    ])

    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=8.0, read=45.0, write=8.0, pool=8.0), follow_redirects=True) as client:
        for url, fallback_name, fallback_ct in candidates:
            try:
                async with client.stream(
                    "GET",
                    url,
                    headers={"User-Agent": "Mozilla/5.0 VigzoneDriveImport/1.0"},
                ) as resp:
                    ct = resp.headers.get("content-type", fallback_ct)
                    if resp.status_code >= 400:
                        continue
                    body = await _read_http_response_limited(resp)
                    if body and not (
                        b"<!DOCTYPE html" in body[:500].upper()
                        and "text/html" in ct.lower()
                    ):
                        name = _drive_name_from_headers(resp.headers, fallback_name, ct)
                        return body, name, ct or fallback_ct
            except HTTPException:
                raise
            except Exception:
                continue

    raise HTTPException(
        status_code=403,
        detail=(
            "Could not import this Drive file. Make it shared as 'Anyone with the link can view', "
            "or use the Google Drive Picker after configuring GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_API_KEY."
        ),
    )


@app.post("/api/drive/import", tags=["Google Drive"])
async def import_drive_file(
    request: Request,
    req: DriveImportRequest,
    user: dict = Depends(require_current_user),
):
    _enforce_rate_limit(request, "drive_import", 20, user=user, window_seconds=3600)
    file_id = _extract_drive_file_id(req.file_id or req.url or "")
    if not file_id:
        raise HTTPException(status_code=400, detail="Paste a valid Google Drive file link or file ID.")

    if req.access_token:
        contents, filename, content_type = await _download_drive_with_token(file_id, req.access_token, req.name or "", req.mime_type or "")
    else:
        contents, filename, content_type = await _download_public_drive(file_id, req.url or "", req.name or "")

    if not contents:
        raise HTTPException(status_code=422, detail=f'"{filename}" is empty.')
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f'"{filename}" is larger than the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit.')

    scan = await asyncio.to_thread(_virus_scan, contents, filename)
    if not scan.clean:
        threat_label = scan.threat or "unknown threat"
        raise HTTPException(status_code=422, detail=f'"{filename}" was blocked by the virus scanner: {threat_label}.')

    try:
        result = await asyncio.to_thread(process_file, contents, filename)
    except FileProcessingError as e:
        raise HTTPException(status_code=422, detail=f'"{filename}": {e}')

    result["name"] = result.get("name") or filename
    result["drive_file_id"] = file_id
    result["drive_source"] = "google_drive"
    result["scan_clean"] = scan.clean
    result["scanner_available"] = scan.scanner_available
    result["mime"] = result.get("mime") or content_type
    return JSONResponse(result)


# ── Upload endpoint ───────────────────────────────────────────────────────────
@app.post("/api/upload", tags=["Chat"])
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_current_user),
):
    _enforce_rate_limit(request, "upload", 20, user=user, window_seconds=3600)
    filename = os.path.basename((file.filename or "upload").replace("\x00", ""))[:240]
    contents = await _read_upload_limited(file, MAX_UPLOAD_SIZE)

    if not contents:
        raise HTTPException(400, f'"{filename}" is empty.')
    # ── Virus scan (runs before any processing) ────────────────────────────
    scan = await asyncio.to_thread(_virus_scan, contents, filename)
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
        result = await asyncio.to_thread(process_file, contents, filename)
    except FileProcessingError as e:
        raise HTTPException(422, f'"{filename}": {e}')
    except Exception as e:
        logger.error("Unexpected error processing upload %s: %s", filename, e, exc_info=True)
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

    db_path = authmod.DB_PATH
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




@app.get("/api/admin/full-dashboard", tags=["Admin"])
async def admin_full_dashboard(admin: dict = Depends(require_admin)):
    """Professional all-in-one admin dashboard data: usage, users, feedback, shares, Brain, and trends."""
    import sqlite3
    from datetime import timedelta

    db_path = authmod.DB_PATH
    tz_offset_minutes = int(os.getenv("USAGE_TZ_OFFSET_MINUTES", "330"))
    local_tz = timezone(timedelta(minutes=tz_offset_minutes))
    now_local = datetime.now(local_tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ts = int(today_start_local.timestamp())
    week_start_ts = int((today_start_local - timedelta(days=6)).timestamp())

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        active_today = conn.execute(
            "SELECT COUNT(DISTINCT user_id) AS c FROM token_usage WHERE ts >= ?",
            (today_start_ts,),
        ).fetchone()["c"]
        own_key_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE use_own_key = 1 AND own_groq_key_enc IS NOT NULL"
        ).fetchone()["c"]
        totals_today = conn.execute(
            """
            SELECT COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens),0) AS completion_tokens,
                   COALESCE(SUM(total_tokens),0) AS total_tokens,
                   COUNT(*) AS requests,
                   COALESCE(SUM(fallback_used),0) AS fallbacks,
                   COALESCE(AVG(latency_ms),0) AS avg_latency_ms,
                   COALESCE(AVG(time_to_first_token_ms),0) AS avg_ttft_ms,
                   COALESCE(SUM(cached_tokens),0) AS cached_tokens
            FROM token_usage WHERE ts >= ?
            """,
            (today_start_ts,),
        ).fetchone()
        totals_week = conn.execute(
            """
            SELECT COALESCE(SUM(total_tokens),0) AS total_tokens,
                   COUNT(*) AS requests,
                   COUNT(DISTINCT user_id) AS active_users
            FROM token_usage WHERE ts >= ?
            """,
            (week_start_ts,),
        ).fetchone()
        top_rows = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.use_own_key AS using_own_key,
                   COALESCE(SUM(t.total_tokens),0) AS total_tokens,
                   COUNT(t.id) AS requests,
                   MAX(t.ts) AS last_seen
            FROM users u
            LEFT JOIN token_usage t ON t.user_id = u.id AND t.ts >= ?
            GROUP BY u.id
            ORDER BY total_tokens DESC, requests DESC, u.id DESC
            LIMIT 12
            """,
            (week_start_ts,),
        ).fetchall()
        raw_usage_rows = conn.execute(
            """
            SELECT ts, user_id, COALESCE(total_tokens,0) AS total_tokens
            FROM token_usage
            WHERE ts >= ?
            ORDER BY ts ASC
            """,
            (week_start_ts,),
        ).fetchall()
        by_provider = conn.execute(
            """
            SELECT COALESCE(provider, 'groq') AS provider,
                   COALESCE(SUM(total_tokens),0) AS tokens,
                   COUNT(*) AS requests
            FROM token_usage
            WHERE ts >= ?
            GROUP BY provider
            ORDER BY tokens DESC
            """,
            (week_start_ts,),
        ).fetchall()
        route_rows = conn.execute(
            """
            SELECT COALESCE(model, 'unknown') AS model,
                   COALESCE(NULLIF(routed_model, ''), model, 'unknown') AS routed_model,
                   COALESCE(NULLIF(route_reason, ''), 'legacy') AS route_reason,
                   COALESCE(NULLIF(routing_mode, ''), 'general') AS routing_mode,
                   COUNT(*) AS requests,
                   COALESCE(SUM(total_tokens),0) AS tokens,
                   COALESCE(SUM(fallback_used),0) AS fallbacks,
                   COALESCE(SUM(retry_count),0) AS retries,
                   COALESCE(AVG(latency_ms),0) AS avg_latency_ms,
                   COALESCE(AVG(time_to_first_token_ms),0) AS avg_ttft_ms,
                   COALESCE(SUM(cached_tokens),0) AS cached_tokens
            FROM token_usage
            WHERE ts >= ? AND provider = 'groq'
            GROUP BY model, routed_model, route_reason, routing_mode
            ORDER BY requests DESC, tokens DESC
            LIMIT 30
            """,
            (week_start_ts,),
        ).fetchall()
        context_totals = conn.execute(
            """
            SELECT COALESCE(SUM(system_tokens),0) AS system_tokens,
                   COALESCE(SUM(history_tokens),0) AS history_tokens,
                   COALESCE(SUM(summary_tokens),0) AS summary_tokens,
                   COALESCE(SUM(memory_tokens),0) AS memory_tokens,
                   COALESCE(SUM(workspace_tokens),0) AS workspace_tokens,
                   COALESCE(SUM(search_tokens),0) AS search_tokens,
                   COALESCE(SUM(user_tokens),0) AS user_tokens
            FROM token_usage
            WHERE ts >= ? AND provider = 'groq'
            """,
            (week_start_ts,),
        ).fetchone()
        brain_users = conn.execute("SELECT COUNT(*) AS c FROM brain_snapshots").fetchone()["c"]
        share_count = conn.execute("SELECT COUNT(*) AS c FROM shared_chats").fetchone()["c"]
        stored_feedback = conn.execute(
            """
            SELECT f.id, f.created_at, f.reason, f.assistant_text,
                   f.message_text, f.conversation_id, f.context_json,
                   f.rating, u.email
            FROM feedback f
            JOIN users u ON u.id = f.user_id
            ORDER BY f.created_at DESC
            LIMIT 1000
            """
        ).fetchall()

    # Build daily usage in the configured local timezone instead of UTC SQL dates.
    daily_buckets = {}
    for r in raw_usage_rows:
        local_day = datetime.fromtimestamp(int(r["ts"]), local_tz).date().isoformat()
        bucket = daily_buckets.setdefault(local_day, {"tokens": 0, "requests": 0, "users": set()})
        bucket["tokens"] += int(r["total_tokens"] or 0)
        bucket["requests"] += 1
        bucket["users"].add(r["user_id"])

    daily = []
    for i in range(6, -1, -1):
        local_date = today_start_local - timedelta(days=i)
        d = local_date.date().isoformat()
        r = daily_buckets.get(d)
        daily.append({
            "day": d,
            "label": local_date.strftime("%b %d"),
            "tokens": int(r["tokens"]) if r else 0,
            "requests": int(r["requests"]) if r else 0,
            "users": len(r["users"]) if r else 0,
        })

    feedback_rows = []
    for stored in stored_feedback:
        row = dict(stored)
        try:
            row["context"] = json.loads(row.pop("context_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            row["context"] = {}
        feedback_rows.append(row)
    negative_feedback = [row for row in feedback_rows if row.get("rating") == "down"]

    feedback_total = len(feedback_rows)
    feedback_bad = len(negative_feedback)
    feedback_good = max(feedback_total - feedback_bad, 0)
    quality_buckets: dict[tuple[str, str], dict] = {}
    for row in feedback_rows:
        context = row.get("context") or {}
        model = str(context.get("model") or "unknown")
        route_reason = str(context.get("route_reason") or "unknown")
        bucket = quality_buckets.setdefault(
            (model, route_reason),
            {
                "model": model,
                "route_reason": route_reason,
                "positive": 0,
                "negative": 0,
            },
        )
        if row.get("rating") == "down":
            bucket["negative"] += 1
        else:
            bucket["positive"] += 1

    quality_by_route = []
    for bucket in quality_buckets.values():
        total = bucket["positive"] + bucket["negative"]
        quality_by_route.append(
            {
                **bucket,
                "total": total,
                "positive_rate": round(bucket["positive"] * 100 / total, 1)
                if total
                else 0,
            }
        )
    quality_by_route.sort(key=lambda item: item["total"], reverse=True)

    return JSONResponse({
        "admin": {"email": admin.get("email"), "name": admin.get("name")},
        "version": APP_VERSION,
        "app_name": APP_NAME,
        "summary": {
            "total_users": total_users,
            "active_today": active_today,
            "default_plan_users": max(total_users - own_key_users, 0),
            "own_key_users": own_key_users,
            "brain_users": brain_users,
            "share_count": share_count,
            "feedback_total": feedback_total,
            "negative_feedback": feedback_bad,
            "positive_feedback": feedback_good,
            "today_tokens": int(totals_today["total_tokens"]),
            "today_requests": int(totals_today["requests"]),
            "today_fallbacks": int(totals_today["fallbacks"]),
            "average_latency_ms": round(float(totals_today["avg_latency_ms"] or 0)),
            "average_ttft_ms": round(float(totals_today["avg_ttft_ms"] or 0)),
            "today_cached_tokens": int(totals_today["cached_tokens"]),
            "week_tokens": int(totals_week["total_tokens"]),
            "week_requests": int(totals_week["requests"]),
            "week_active_users": int(totals_week["active_users"]),
        },
        "daily": daily,
        "top_users": [
            {
                "id": r["id"],
                "name": r["name"],
                "email": r["email"],
                "using_own_key": bool(r["using_own_key"]),
                "total_tokens": int(r["total_tokens"]),
                "requests": int(r["requests"]),
                "last_seen": r["last_seen"],
            }
            for r in top_rows
        ],
        "provider_usage": [
            {
                "provider": r["provider"],
                "label": "Default Groq / shared key" if str(r["provider"]).lower() == "groq" else str(r["provider"]).replace("_", " ").title(),
                "tokens": int(r["tokens"]),
                "requests": int(r["requests"]),
            }
            for r in by_provider
        ],
        "routing_usage": [
            {
                "model": r["model"],
                "routed_model": r["routed_model"],
                "route_reason": r["route_reason"],
                "routing_mode": r["routing_mode"],
                "requests": int(r["requests"]),
                "tokens": int(r["tokens"]),
                "fallbacks": int(r["fallbacks"]),
                "retries": int(r["retries"]),
                "average_latency_ms": round(float(r["avg_latency_ms"] or 0)),
                "average_ttft_ms": round(float(r["avg_ttft_ms"] or 0)),
                "cached_tokens": int(r["cached_tokens"]),
            }
            for r in route_rows
        ],
        "context_token_mix": [
            {"name": name, "tokens": int(context_totals[name] or 0)}
            for name in (
                "system_tokens",
                "history_tokens",
                "summary_tokens",
                "memory_tokens",
                "workspace_tokens",
                "search_tokens",
                "user_tokens",
            )
        ],
        "quality_by_route": quality_by_route[:30],
        "system_notes": [
            {
                "title": "Timezone",
                "status": "active",
                "value": f"UTC{tz_offset_minutes/60:+g}",
                "note": "Daily charts are grouped using this local timezone, not UTC.",
            },
            {
                "title": "Default API key",
                "status": "configured" if bool(API_KEY) else "missing",
                "value": "Ready" if bool(API_KEY) else "Needs GROQ_API_KEY",
                "note": "Placeholder API keys are ignored so the app will not falsely report configured.",
            },
            {
                "title": "Storage",
                "status": "scoped",
                "value": "Per-user browser storage",
                "note": "Local chats, Brain metadata, mode memory and upload history are separated by signed-in user.",
            },
        ],
        "feedback_mix": [
            {"name": "Positive", "value": feedback_good},
            {"name": "Negative", "value": feedback_bad},
        ],
        "bad_feedback": [
            {
                "id": r.get("id"),
                "email": r.get("email"),
                "created_at": r.get("created_at"),
                "reason": r.get("reason") or "No reason provided",
                "assistant_text": _safe_message_text(r.get("assistant_text") or r.get("message_text") or "", 800),
                "conversation_id": r.get("conversation_id"),
                "context": r.get("context") or {},
            }
            for r in negative_feedback[:30]
        ],
    })


@app.post("/api/admin/users/{user_id}/usage/reset", tags=["Admin"])
async def admin_reset_user_usage(user_id: int, admin: dict = Depends(require_admin)):
    """Delete today's tracked usage rows for a user. Groq-side usage is not reset."""
    import sqlite3

    db_path = authmod.DB_PATH
    start_ts = _admin_today_start_ts()
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("DELETE FROM token_usage WHERE user_id = ? AND ts >= ?", (user_id, start_ts))
        conn.commit()
    return JSONResponse({"ok": True, "deleted_rows": cur.rowcount})


# ── Paddle Billing Webhook ─────────────────────────────────────────────────────
@app.post("/api/billing/paddle/restore", tags=["Billing"])
async def restore_paddle_purchase(
    request: Request,
    user: dict = Depends(require_current_user),
):
    """Reconcile the signed-in account with Paddle by its exact email."""
    _enforce_rate_limit(request, "paddle_restore", 5, user=user, window_seconds=3600)
    if not PADDLE_API_KEY:
        raise HTTPException(status_code=503, detail="Purchase restore is not configured yet.")
    base_url = "https://sandbox-api.paddle.com" if PADDLE_ENVIRONMENT == "sandbox" else "https://api.paddle.com"
    headers = {"Authorization": f"Bearer {PADDLE_API_KEY}", "Accept": "application/json"}
    restored: list[dict] = []
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=15.0) as client:
            customer_response = await client.get("/customers", params={"email": user["email"]})
            customer_response.raise_for_status()
            customers = customer_response.json().get("data") or []
            for customer in customers:
                customer_id = str(customer.get("id") or "")
                if not customer_id:
                    continue
                subscription_response = await client.get("/subscriptions", params={"customer_id": customer_id})
                subscription_response.raise_for_status()
                for subscription in subscription_response.json().get("data") or []:
                    if str(subscription.get("status") or "").lower() not in billing.ACTIVE_SUBSCRIPTION_STATUSES:
                        continue
                    subscription = dict(subscription)
                    custom = dict(subscription.get("custom_data") or {})
                    custom.update({"vigzone_user_id": str(user["id"]), "vigzone_email": user["email"]})
                    subscription["custom_data"] = custom
                    occurred_at = subscription.get("updated_at") or subscription.get("created_at") or datetime.now(timezone.utc).isoformat()
                    identity = f"{subscription.get('id')}:{subscription.get('status')}:{occurred_at}"
                    event = {
                        "event_id": "restore_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32],
                        "event_type": "subscription.updated",
                        "occurred_at": occurred_at,
                        "data": subscription,
                    }
                    result = billing.process_paddle_event(authmod.DB_PATH, event, _paddle_catalog())
                    if result.get("ok") and result.get("action") in {"processed", "duplicate", "stale"}:
                        restored.append(result)
    except httpx.HTTPStatusError as exc:
        logger.warning("Paddle restore API rejected the request: status=%s", exc.response.status_code)
        raise HTTPException(status_code=502, detail="Paddle could not verify this purchase right now.") from exc
    except httpx.HTTPError as exc:
        logger.warning("Paddle restore API unavailable: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Paddle is temporarily unavailable. Try again shortly.") from exc
    if not restored:
        return JSONResponse({"ok": True, "restored": False, "message": "No active PRO or TEAM membership matched this account."})
    restored_plan = billing.recompute_user_plan(authmod.DB_PATH, user["id"])
    return JSONResponse({"ok": True, "restored": True, "memberships": len(restored), "plan": restored_plan})


@app.post("/api/billing/paddle/webhook", tags=["Billing"])
async def paddle_webhook(request: Request):
    """Verify and durably apply a Paddle Billing webhook."""
    raw_body = await request.body()
    signature = request.headers.get("Paddle-Signature", "")
    verified, verification_result = billing.verify_paddle_signature(
        PADDLE_WEBHOOK_SECRET,
        signature,
        raw_body,
    )
    if not verified:
        status = 503 if verification_result == "webhook_not_configured" else 401
        logger.warning("Rejected Paddle webhook: %s", verification_result)
        return JSONResponse({"ok": False, "error": verification_result}, status_code=status)
    try:
        event = json.loads(raw_body)
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    try:
        result = billing.process_paddle_event(authmod.DB_PATH, event, _paddle_catalog())
    except Exception as exc:
        logger.exception("Paddle webhook processing failed")
        return JSONResponse({"ok": False, "error": "processing_failed"}, status_code=500)
    if not result.get("ok"):
        # A missing local account is recoverable: Paddle should retry rather
        # than recording a misleading successful delivery.
        status = 409 if result.get("error") == "user_not_found" else 400
        return JSONResponse(result, status_code=status)
    logger.info(
        "Paddle webhook %s: event=%s user=%s plan=%s",
        result.get("action"), result.get("event_id"), result.get("user_id"), result.get("plan"),
    )
    return JSONResponse(result)


# ── Voice transcription endpoint ──────────────────────────────────────────────
GROQ_TRANSCRIPTION_MODEL = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
GROQ_TRANSCRIPTION_MODELS = [
    item.strip()
    for item in os.getenv(
        "GROQ_TRANSCRIPTION_MODELS",
        os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo") + ",whisper-large-v3",
    ).split(",")
    if item.strip()
]
MAX_VOICE_UPLOAD_SIZE = int(os.getenv("MAX_VOICE_UPLOAD_SIZE_BYTES", str(25 * 1024 * 1024)))
VOICE_TRANSCRIPTION_LANG_PRIORITY = [
    item.strip().lower()
    for item in os.getenv("VOICE_TRANSCRIPTION_LANG_PRIORITY", "auto,si,ta,en,hi").split(",")
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
    """Build a short ordered list of language hints for Whisper.

    Important: always try auto-detect first. Trying many explicit languages
    first burns Groq rate limit and can make short voice messages fail before
    auto-detect gets a chance. For Sinhala/Tamil, retry explicit hints only
    when needed.
    """
    candidates: list[Optional[str]] = []

    # Auto-detect first. This is usually the most reliable for multilingual audio.
    candidates.append(None)

    explicit = _normalize_transcription_language(explicit_language)
    if explicit:
        candidates.append(explicit)

    hint = (browser_hint or "")[:120]
    if re.search(r"[\u0D80-\u0DFF]", hint):
        candidates.append("si")
    if re.search(r"[\u0B80-\u0BFF]", hint):
        candidates.append("ta")
    if re.search(r"[\u0900-\u097F]", hint):
        # Browser may mishear Sinhala as Hindi. Keep hi as a late fallback.
        candidates.append("hi")

    # Browser/device language can still help for English/Tamil/Sinhala.
    raw_langs = ",".join([browser_language or "", browser_languages or ""])
    for part in re.split(r"[,;\s]+", raw_langs.lower()):
        lang = _normalize_transcription_language(part)
        if lang:
            candidates.append(lang)

    # Admin-configured priority, usually auto,si,ta,en,hi.
    for item in VOICE_TRANSCRIPTION_LANG_PRIORITY:
        lang = None if item in ("auto", "detect", "default") else _normalize_transcription_language(item)
        candidates.append(lang)

    # Keep unique valid items. Hard cap avoids burning Groq limits.
    out: list[Optional[str]] = []
    seen: set[str] = set()
    for item in candidates:
        key = item or "auto"
        if item is not None and not re.fullmatch(r"[a-z]{2,3}", item):
            continue
        if key not in seen:
            out.append(item)
            seen.add(key)

    return out[:4]  # auto + at most 3 retries


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
    model: str,
) -> tuple[str, dict]:
    data = {"model": model, "response_format": "json"}
    if lang:
        data["language"] = lang
    resp = await client.post(
        transcribe_url,
        headers={"Authorization": f"Bearer {api_key}"},
        data=data,
        files={"file": (filename or "voice.webm", audio, content_type)},
    )
    if resp.status_code != 200:
        return "", {"status_code": resp.status_code, "body": resp.text[:500], "language": lang, "model": model}
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
    _require_feature(user, "voice", "Voice transcription")
    _enforce_rate_limit(request, "voice", 10, user=user, window_seconds=60)

    provider_override, _ = _resolve_provider_for_user(user)
    if provider_override is None and not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=f"{APP_NAME} isn't configured — set GROQ_API_KEY before using voice transcription.",
        )

    content_type = (file.content_type or "audio/webm").split(";", 1)[0]
    filename = os.path.basename((file.filename or "voice.webm").replace("\x00", ""))[:240]
    audio = await _read_upload_limited(file, MAX_VOICE_UPLOAD_SIZE)
    if not audio:
        raise HTTPException(status_code=400, detail="Voice recording was empty.")

    if not content_type.startswith("audio/") and content_type not in {"video/webm", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Unsupported voice recording format.")
    scan = await asyncio.to_thread(_virus_scan, audio, filename)
    if not scan.clean:
        raise HTTPException(status_code=422, detail="The voice upload was blocked by the virus scanner.")

    using_override = provider_override is not None
    api_url = provider_override["api_url"] if using_override else f"{OLLAMA_BASE_URL}/chat/completions"
    api_key = provider_override["api_key"] if using_override else API_KEY
    transcribe_url = _groq_audio_transcriptions_url(api_url)

    candidates = _voice_candidate_languages(language, browser_language, browser_languages, browser_hint)
    attempts: list[dict] = []
    best_text = ""
    best_lang: Optional[str] = None
    best_model = GROQ_TRANSCRIPTION_MODELS[0] if GROQ_TRANSCRIPTION_MODELS else GROQ_TRANSCRIPTION_MODEL
    best_score = -1_000_000.0
    last_error: Optional[dict] = None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=8.0, read=90.0, write=30.0, pool=5.0)) as client:
            for model in GROQ_TRANSCRIPTION_MODELS:
                for idx_lang, lang in enumerate(candidates):
                    text, payload = await _groq_transcribe_once(
                        client,
                        transcribe_url,
                        api_key,
                        audio,
                        filename,
                        content_type,
                        lang,
                        model,
                    )
                    if not text:
                        last_error = payload
                        status = payload.get("status_code")
                        # Invalid language/model hints should not kill the whole request.
                        if status in (400, 404, 422):
                            continue
                        # Do not burn more attempts if the key/account is blocked.
                        if status in (401, 429):
                            break
                        continue

                    score = _score_transcription_candidate(text, lang, browser_hint or "")
                    attempts.append({
                        "model": model,
                        "language": lang or "auto",
                        "text": text[:80],
                        "score": round(score, 2),
                    })
                    if score > best_score:
                        best_score = score
                        best_text = text
                        best_lang = lang
                        best_model = model

                    counts = _voice_script_counts(text)

                    # For normal auto-detected Sinhala/Tamil/English text, accept quickly.
                    # If auto returns Devanagari/Hindi, try a Sinhala/Tamil hint before accepting.
                    if lang is None and counts["hi"] and ("si" in candidates or "ta" in candidates):
                        continue
                    if counts["si"] >= 2 or counts["ta"] >= 2:
                        break
                    if idx_lang == 0 and text and not counts["hi"]:
                        break

                if best_text:
                    break
                if last_error and last_error.get("status_code") in (401, 429):
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
            track_token_usage(
                user["id"],
                prompt_tokens=0,
                completion_tokens=_estimate_tokens(text),
                provider="groq_audio",
                estimated=True,
                model=best_model,
            )
    except Exception:
        logger.debug("Voice transcription usage tracking failed", exc_info=True)

    return JSONResponse({"text": text, "provider": "groq", "model": best_model, "language": best_lang or "auto", "attempts": attempts[:3]})


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
    paid_model_access = billing.effective_plan(user) != "free"
    if not paid_model_access:
        override_model = FAST_MODEL
    _check_chat_rate_limit(request, user)
    messages = _normalize_chat_messages([
        {"role": message.role, "content": message.content}
        for message in chat_request.messages
    ])

    # Real backend quota guard: do not start a Groq call when this user's
    # Vigzone daily plan is exhausted or too close to exhausted.
    key_status = authmod.get_user_key_status(user["id"])
    estimated_request_tokens = estimate_budgeted_request_tokens(messages)
    _assert_chat_entitlements(
        user,
        chat_request,
        has_own_key=key_status["active"],
        estimated_tokens=estimated_request_tokens,
    )

    if provider_override is None and not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                f"{APP_NAME} isn't configured — set GROQ_API_KEY in .env "
                f"or in your deployment Variables (get a free key at {GROQ_KEYS_URL})."
            ),
        )

    last_user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_query = _message_text_plain(m.get("content")) or ""
            break

    if _is_simple_datetime_request(last_user_query):
        stream_id = create_stream_id()
        register_stream(stream_id, user["id"])
        direct_answer = _build_datetime_answer(last_user_query, chat_request.client_timezone)
        async def direct_event_stream():
            try:
                async for item in _stream_direct_answer(stream_id, direct_answer):
                    yield item
            finally:
                unregister_stream(stream_id)
        return StreamingResponse(
            direct_event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    context_parts = {
        "workspace": authmod.get_workspace_context(
            user["id"], chat_request.workspace_id, last_user_query
        ),
        "memory": authmod.get_learning_context(user["id"], last_user_query),
        "persona": authmod.get_team_persona_context(user["id"]),
    }
    feature_policy = billing.entitlement_snapshot(user)["features"]
    stream_id = create_stream_id()
    register_stream(stream_id, user["id"])

    async def event_stream():
        response_meta: dict = {}
        try:
            yield f"data: {json.dumps({'stream_id': stream_id})}\n\n"

            reply_accum    = ""

            try:
                async for chunk in stream_chat(
                    messages,
                    model=override_model or chat_request.model,
                    stream_id=stream_id,
                    user_id=user["id"],
                    user_name=user.get("name") or "",
                    provider_override=provider_override,
                    context_parts=context_parts,
                    feature_policy=feature_policy,
                    routing_mode=chat_request.ai_mode or "general",
                    conversation_id=chat_request.conversation_id or "",
                    metadata_callback=response_meta.update,
                    allowed_models=None if paid_model_access else {FAST_MODEL},
                ):
                    if is_cancelled(stream_id):
                        break
                    reply_accum += chunk
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

                if response_meta:
                    yield f"data: {json.dumps({'meta': response_meta}, ensure_ascii=False)}\n\n"
                if not is_cancelled(stream_id):
                    yield "data: [DONE]\n\n"
                else:
                    yield "data: [CANCELLED]\n\n"

            except VigzoneAIError as e:
                logger.error("Chat stream failed: %s", e)
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            except Exception:
                # Safety net: any *unexpected* exception (e.g. a malformed
                # streaming API chunk) used to propagate out of this generator
                # uncaught, which silently kills the SSE stream with zero
                # content and zero error - the frontend then just shows a
                # generic "No response received." with no clue why. Surface
                # it as a real error instead so it's actually debuggable.
                logger.exception("Unexpected error in chat stream")
                request_id = getattr(request.state, "request_id", None)
                message = "Unexpected server error."
                if request_id:
                    message += f" Reference: {request_id}"
                yield f"data: {json.dumps({'error': message}, ensure_ascii=False)}\n\n"
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
    paid_model_access = billing.effective_plan(user) != "free"
    if not paid_model_access:
        override_model = FAST_MODEL
    _check_chat_rate_limit(request, user)
    messages = _normalize_chat_messages([
        {"role": message.role, "content": message.content}
        for message in chat_request.messages
    ])

    key_status = authmod.get_user_key_status(user["id"])
    estimated_request_tokens = estimate_budgeted_request_tokens(messages)
    _assert_chat_entitlements(
        user,
        chat_request,
        has_own_key=key_status["active"],
        estimated_tokens=estimated_request_tokens,
    )

    if provider_override is None and not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                f"{APP_NAME} isn't configured — set GROQ_API_KEY in .env "
                f"or in your deployment Variables (get a free key at {GROQ_KEYS_URL})."
            ),
        )
    last_user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_query = _message_text_plain(m.get("content")) or ""
            break

    if _is_simple_datetime_request(last_user_query):
        return JSONResponse({"role": "assistant", "content": _build_datetime_answer(last_user_query, chat_request.client_timezone)})

    context_parts = {
        "workspace": authmod.get_workspace_context(
            user["id"], chat_request.workspace_id, last_user_query
        ),
        "memory": authmod.get_learning_context(user["id"], last_user_query),
        "persona": authmod.get_team_persona_context(user["id"]),
    }
    feature_policy = billing.entitlement_snapshot(user)["features"]
    response_meta: dict = {}
    try:
        reply = await chat_once(
            messages,
            model=override_model or chat_request.model,
            user_id=user["id"],
            user_name=user.get("name") or "",
            provider_override=provider_override,
            context_parts=context_parts,
            feature_policy=feature_policy,
            routing_mode=chat_request.ai_mode or "general",
            conversation_id=chat_request.conversation_id or "",
            metadata_callback=response_meta.update,
            allowed_models=None if paid_model_access else {FAST_MODEL},
        )
    except VigzoneAIError as e:
        logger.error("Chat failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    return JSONResponse({"role": "assistant", "content": reply, "meta": response_meta})


# ── Stream control ────────────────────────────────────────────────────────────
@app.post("/api/cancel-stream", tags=["Chat"])
async def cancel_stream_endpoint(
    req: StreamControlRequest,
    user: dict = Depends(require_current_user),
):
    if cancel_stream(req.stream_id, user["id"]):
        return JSONResponse({"status": "cancelled", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


@app.post("/api/pause-stream", tags=["Chat"])
async def pause_stream_endpoint(
    req: StreamControlRequest,
    user: dict = Depends(require_current_user),
):
    if pause_stream(req.stream_id, user["id"]):
        return JSONResponse({"status": "paused", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


@app.post("/api/resume-stream", tags=["Chat"])
async def resume_stream_endpoint(
    req: StreamControlRequest,
    user: dict = Depends(require_current_user),
):
    if resume_stream(req.stream_id, user["id"]):
        return JSONResponse({"status": "resumed", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


# ── Image generation ──────────────────────────────────────────────────────────
@app.post("/api/generate-image", tags=["Image"])
async def api_generate_image(
    request: Request,
    req: ImageRequest,
    user: dict = Depends(require_current_user),
):
    _require_feature(user, "image_generation", "Image generation")
    _enforce_rate_limit(request, "image_generate", 10, user=user, window_seconds=3600)
    try:
        result = await generate_image(req.prompt, size=req.size or "1024x1024")
    except ImageGenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in image generation")
        raise HTTPException(status_code=500, detail="Image generation failed")
    if not IS_TESTING:
        from vigzone_ai import track_token_usage

        track_token_usage(
            user["id"],
            0,
            0,
            provider=f"{result.get('provider', 'image')}_image",
            estimated=False,
            model=str(result.get("model") or ""),
        )
    return JSONResponse(result)


@app.post("/api/edit-image", tags=["Image"])
async def api_edit_image(
    request: Request,
    req: EditImageRequest,
    user: dict = Depends(require_current_user),
):
    _require_feature(user, "image_generation", "Image editing")
    _enforce_rate_limit(request, "image_edit", 10, user=user, window_seconds=3600)
    try:
        result = await edit_image(req.image_data_uri, req.prompt, size=req.size or "1024x1024")
    except ImageGenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in image editing")
        raise HTTPException(status_code=500, detail="Image editing failed")
    if not IS_TESTING:
        from vigzone_ai import track_token_usage

        track_token_usage(
            user["id"],
            0,
            0,
            provider=f"{result.get('provider', 'image')}_image",
            estimated=False,
            model=str(result.get("model") or ""),
        )
    return JSONResponse(result)





@app.get("/manifest.json", tags=["Web"])
async def manifest_json():
    """Dynamic PWA manifest so app name/description are not frozen in static JSON."""
    return JSONResponse({
        "name": APP_NAME,
        "short_name": APP_SHORT_NAME,
        "description": os.getenv("VIGZONE_APP_DESCRIPTION", f"{APP_NAME} assistant"),
        "start_url": "/chat",
        "scope": "/",
        "display": "standalone",
        "background_color": os.getenv("VIGZONE_PWA_BACKGROUND", "#0b0f1a"),
        "theme_color": os.getenv("VIGZONE_PWA_THEME", "#ff6f4d"),
        "id": "/chat",
        "icons": [
            {"src": "/static/icons/vigzone-icon-64.png", "sizes": "64x64", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/vigzone-icon-128.png", "sizes": "128x128", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/vigzone-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/vigzone-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/vigzone-icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/static/icons/vigzone-icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Open Chat", "short_name": "Chat", "url": "/chat", "icons": [{"src": "/static/icons/vigzone-icon-192.png", "sizes": "192x192"}]}
        ],
    })


@app.get("/service-worker.js", tags=["Web"])
async def service_worker():
    """Serve the service worker from the root so it can control /chat and /static."""
    return FileResponse(
        "static/service-worker.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Service-Worker-Allowed": "/",
        },
    )


@app.get("/offline", tags=["Web"])
async def offline_page():
    return FileResponse("static/offline.html", media_type="text/html")


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
    logger.info(
        "http_exception request_id=%s status=%s path=%s",
        getattr(request.state, "request_id", ""),
        exc.status_code,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers or {},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    request_id = getattr(request.state, "request_id", "")
    logger.error(
        "unexpected_error request_id=%s path=%s",
        request_id,
        request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "request_id": request_id or None,
        },
    )


# ── Static files ──────────────────────────────────────────────────────────────
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port   = int(os.getenv("PORT", "8000"))
    reload = not is_production() and os.getenv("ENV", "development") == "development"
    logger.info("Starting Vigzone AI server on port %d…", port)
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=reload, log_level="info")
