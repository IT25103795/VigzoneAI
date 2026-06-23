"""
Vigzone AI - Web Server
========================
FastAPI backend serving the Vigzone AI chat interface.
Chat backend: local Ollama (http://localhost:11434).

Modes (set APP_MODE in .env):
  testing    → unlimited messages, no rate limits (default)
  production → token usage tracked per user in SQLite
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import List, Literal, Optional, Union

from dotenv import load_dotenv

load_dotenv()

from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from file_processing import (
    FileProcessingError,
    extract_docx_text,
    extract_pdf_text,
    extract_plain_text,
    process_image,
)
from vigzone_ai import (
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    VISION_MODEL,
    IS_TESTING,
    VigzoneAIError,
    chat_once,
    get_user_token_stats,
    is_configured,
    stream_chat,
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
    description="A real conversational AI assistant — powered by Ollama.",
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
MAX_UPLOAD_SIZE    = 10 * 1024 * 1024
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


class HealthCheckResponse(BaseModel):
    status: str
    backend_configured: bool
    mode: str


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


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=authmod.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=authmod.SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


# ── System endpoints ──────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthCheckResponse, tags=["System"])
async def health_check():
    configured = await is_configured()
    return HealthCheckResponse(
        status="healthy" if configured else "needs_setup",
        backend_configured=configured,
        mode="testing" if IS_TESTING else "production",
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
        backend="Ollama (local)",
        status="ready" if await is_configured() else "ollama_unreachable",
        mode="testing" if IS_TESTING else "production",
    )


@app.get("/api/stats", tags=["System"])
async def get_stats():
    return JSONResponse({
        "name": "Vigzone AI",
        "version": "3.0.0",
        "mode": "testing" if IS_TESTING else "production",
        "description": "A real conversational AI assistant — powered by Ollama",
        "endpoints": {
            "health": "/health",
            "capabilities": "/api/capabilities",
            "model_info": "/api/model-info",
            "upload": "POST /api/upload",
            "chat_stream": "POST /api/chat",
            "cancel_stream": "POST /api/cancel-stream",
            "pause_stream": "POST /api/pause-stream",
            "resume_stream": "POST /api/resume-stream",
            "chat_sync": "POST /api/chat/sync",
            "generate_image": "POST /api/generate-image",
            "edit_image": "POST /api/edit-image",
            "token_usage": "GET /api/me/tokens",
        },
        "docs": "/docs",
    })


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


# ── Upload endpoint ───────────────────────────────────────────────────────────
@app.post("/api/upload", tags=["Chat"])
async def upload_file(file: UploadFile = File(...), user: dict = Depends(require_current_user)):
    filename     = file.filename or "upload"
    ext          = os.path.splitext(filename)[1].lower()
    content_type = (file.content_type or "").lower()
    contents     = await file.read()

    if not contents:
        raise HTTPException(400, f'"{filename}" is empty.')
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f'"{filename}" is larger than the 10 MB limit.')

    is_image = content_type in IMAGE_CONTENT_TYPES or ext in IMAGE_EXTENSIONS

    try:
        if is_image:
            data_uri, mime = process_image(contents)
            return JSONResponse({"kind": "image", "name": filename, "mime": mime, "data_uri": data_uri})

        if ext == ".pdf":
            text, truncated = extract_pdf_text(contents)
        elif ext == ".docx":
            text, truncated = extract_docx_text(contents)
        elif ext in {".txt", ".md", ".csv"}:
            text, truncated = extract_plain_text(contents)
        else:
            raise HTTPException(
                400,
                f'Unsupported file type "{ext or content_type or "unknown"}". '
                "Supported: images (PNG/JPG/WEBP/GIF), PDF, DOCX, TXT, MD, CSV.",
            )
    except FileProcessingError as e:
        raise HTTPException(422, f'"{filename}": {e}')
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error processing upload %s: %s", filename, e, exc_info=True)
        raise HTTPException(500, f'Couldn\'t process "{filename}".')

    return JSONResponse({"kind": "document", "name": filename, "text": text, "truncated": truncated})


# ── Chat endpoints ────────────────────────────────────────────────────────────
@app.post("/api/chat", tags=["Chat"])
async def chat(request: ChatRequest, user: dict = Depends(require_current_user)):
    """
    Stream a chat response as Server-Sent Events.
    No message limits in testing mode. Token usage tracked in production mode.
    """
    if not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Can't reach Ollama at {OLLAMA_BASE_URL}. "
                "Make sure Ollama is installed and running (`ollama serve`), "
                "and that you've pulled a model (`ollama pull gemma3`)."
            ),
        )

    messages  = [{"role": m.role, "content": m.content} for m in request.messages]
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
                    model=request.model,
                    stream_id=stream_id,
                    user_id=user["id"],
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
        finally:
            unregister_stream(stream_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/sync", tags=["Chat"])
async def chat_sync(request: ChatRequest, user: dict = Depends(require_current_user)):
    """Non-streaming variant — returns the full reply in one JSON response."""
    if not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Can't reach Ollama at {OLLAMA_BASE_URL}. "
                "Make sure Ollama is running (`ollama serve`)."
            ),
        )
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        reply = await chat_once(messages, model=request.model, user_id=user["id"])
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
