"""
Vigzone AI - Web Server
========================
FastAPI backend serving the Vigzone AI chat interface and a streaming
chat API backed by Groq's LLM API (see vigzone_ai.py).
"""

import logging
import os
from typing import List, Literal, Optional, Union

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
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
    VigzoneAIError,
    chat_once,
    is_configured,
    stream_chat,
)
from self_learning import add_interaction, prune_kb, sanitize_assistant_for_memory
from image_generation import generate_image, edit_image, ImageGenError
from stream_manager import (
    create_stream_id,
    register_stream,
    cancel_stream,
    is_cancelled,
    unregister_stream,
    pause_stream,
    resume_stream,
)

# ==========================================
# LOGGING SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ==========================================
# FASTAPI APP INITIALIZATION
# ==========================================
app = FastAPI(
    title="Vigzone AI API",
    description="A real conversational AI assistant — ask it anything.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _cleanup_knowledge_base() -> None:
    removed = prune_kb()
    if removed:
        logger.info("Pruned %d corrupted knowledge-base entries on startup", removed)

# ==========================================
# UPLOAD CONFIG
# ==========================================
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


# ==========================================
# PYDANTIC MODELS
# ==========================================
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    # Plain text for normal messages, or a list of OpenAI-style content
    # parts (text + image_url) when an image is attached.
    content: Union[str, List[dict]] = Field(...)


class ChatRequest(BaseModel):
    """The client sends the full conversation each time (stateless server)."""
    messages: List[ChatMessage] = Field(..., min_length=1)
    model: str = Field(default=DEFAULT_MODEL)


class HealthCheckResponse(BaseModel):
    status: str
    backend_configured: bool


class ModelInfoResponse(BaseModel):
    name: str
    version: str
    model: str
    vision_model: str
    backend: str
    status: str


# ==========================================
# API ENDPOINTS
# ==========================================
@app.get("/health", response_model=HealthCheckResponse, tags=["System"])
async def health_check():
    configured = await is_configured()
    return HealthCheckResponse(
        status="healthy" if configured else "needs_setup",
        backend_configured=configured,
    )


@app.get("/api/model-info", response_model=ModelInfoResponse, tags=["Model"])
async def get_model_info():
    return ModelInfoResponse(
        name="Vigzone AI",
        version="2.0.0",
        model=DEFAULT_MODEL,
        vision_model=VISION_MODEL,
        backend="Ollama (local)",
        status="ready" if await is_configured() else "ollama_unreachable",
    )


@app.post("/api/upload", tags=["Chat"])
async def upload_file(file: UploadFile = File(...)):
    """
    Accept one image or document, return it ready to attach to a chat message.

    - Images: resized/compressed and returned as a base64 data URI, for the
      vision model to look at directly.
    - Documents (PDF, DOCX, TXT/MD/CSV): text is extracted server-side and
      returned as plain text, to fold into the user's message.
    """
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    content_type = (file.content_type or "").lower()

    contents = await file.read()
    if not contents:
        raise HTTPException(400, f"\"{filename}\" is empty.")
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"\"{filename}\" is larger than the 10 MB limit.")

    is_image = content_type in IMAGE_CONTENT_TYPES or ext in IMAGE_EXTENSIONS

    try:
        if is_image:
            data_uri, mime = process_image(contents)
            return JSONResponse({
                "kind": "image",
                "name": filename,
                "mime": mime,
                "data_uri": data_uri,
            })

        if ext == ".pdf":
            text, truncated = extract_pdf_text(contents)
        elif ext == ".docx":
            text, truncated = extract_docx_text(contents)
        elif ext in {".txt", ".md", ".csv"}:
            text, truncated = extract_plain_text(contents)
        else:
            raise HTTPException(
                400,
                f"Unsupported file type \"{ext or content_type or 'unknown'}\". "
                "Supported: images (PNG/JPG/WEBP/GIF), PDF, DOCX, TXT, MD, CSV.",
            )
    except FileProcessingError as e:
        raise HTTPException(422, f"\"{filename}\": {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing upload {filename}: {e}", exc_info=True)
        raise HTTPException(500, f"Couldn't process \"{filename}\".")

    return JSONResponse({
        "kind": "document",
        "name": filename,
        "text": text,
        "truncated": truncated,
    })


@app.post("/api/chat", tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Stream a chat response as Server-Sent Events.

    The client sends the *entire* conversation history (including the
    latest user message) on every call; the server is stateless and adds
    only the system prompt. Each SSE event is `data: {"content": "..."}`,
    terminated by `data: [DONE]`.
    
    The first event includes a stream_id that the client can use to cancel
    the stream by calling POST /api/cancel-stream with the stream_id.
    """
    if not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=f"Can't reach Ollama at {OLLAMA_BASE_URL}. Make sure Ollama is "
                   "installed and running (`ollama serve`), and that you've pulled a "
                   "model (`ollama pull llama3.2`).",
        )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    stream_id = create_stream_id()
    register_stream(stream_id)

    async def event_stream():
        try:
            # Send stream_id to client so it can cancel this stream if needed
            yield f'data: {{"stream_id": "{stream_id}"}}\n\n'
            
            # accumulate the full reply so we can store the interaction in the
            # local knowledge base after the stream completes.
            reply_accum = ""
            # find the last user text (if present) to store with the assistant reply
            last_user_text = None
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user_text = m.get("content") if isinstance(m.get("content"), str) else None
                    break
            
            try:
                async for chunk in stream_chat(messages, model=request.model, stream_id=stream_id):
                    # Check if this stream was cancelled
                    if is_cancelled(stream_id):
                        logger.info(f"Stream {stream_id} was cancelled")
                        break
                    
                    reply_accum += chunk
                    payload = chunk.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
                    yield f'data: {{"content": "{payload}"}}\n\n'
                
                # store the interaction (best-effort). This is local, lightweight
                # retrieval memory — not model fine-tuning.
                if not is_cancelled(stream_id):
                    try:
                        if last_user_text and reply_accum:
                            safe_reply = sanitize_assistant_for_memory(reply_accum)
                            if safe_reply:
                                add_interaction(last_user_text, safe_reply)
                    except Exception:
                        logger.exception("Failed to save interaction to KB")

                # Only send DONE if not cancelled (cancelled streams end abruptly)
                if not is_cancelled(stream_id):
                    yield "data: [DONE]\n\n"
                else:
                    yield "data: [CANCELLED]\n\n"
            except VigzoneAIError as e:
                logger.error(f"Chat stream failed: {e}")
                err = str(e).replace('"', "'")
                yield f'data: {{"error": "{err}"}}\n\n'
        finally:
            unregister_stream(stream_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/sync", tags=["Chat"])
async def chat_sync(request: ChatRequest):
    """Non-streaming variant — returns the full reply in one JSON response."""
    if not await is_configured():
        raise HTTPException(
            status_code=503,
            detail=f"Can't reach Ollama at {OLLAMA_BASE_URL}. Make sure Ollama is "
                   "installed and running (`ollama serve`), and that you've pulled a "
                   "model (`ollama pull llama3.2`).",
        )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        reply = await chat_once(messages, model=request.model)
    except VigzoneAIError as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    # Best-effort: store the user/assistant pair in the local KB so the
    # assistant can learn from future similar queries.
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


class ImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=800)
    size: Optional[str] = Field(default="1024x1024")


class EditImageRequest(BaseModel):
    image_data_uri: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1, max_length=800)
    size: Optional[str] = Field(default="1024x1024")


@app.post("/api/generate-image", tags=["Image"])
async def api_generate_image(req: ImageRequest):
    """Generate an image from a text prompt using the configured provider.

    Defaults to the free, keyless Pollinations provider (no setup required).
    Set IMAGE_API_PROVIDER=openai (plus OPENAI_API_KEY) in .env to switch to
    OpenAI's Images API instead.

    The endpoint returns JSON with either `data_uri` (base64) or `url`.
    """
    try:
        result = await generate_image(req.prompt, size=req.size or "1024x1024")
    except ImageGenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in image generation")
        raise HTTPException(status_code=500, detail="Image generation failed")

    return JSONResponse(result)


@app.post("/api/edit-image", tags=["Image"])
async def api_edit_image(req: EditImageRequest):
    """Apply a described change to an uploaded photo.

    Requires OPENAI_API_KEY to be set (no free/keyless provider can edit a
    specific input photo) — returns a clear 503 with setup instructions if
    it isn't configured, rather than silently generating an unrelated image.

    The endpoint returns JSON with either `data_uri` (base64) or `url`.
    """
    try:
        result = await edit_image(req.image_data_uri, req.prompt, size=req.size or "1024x1024")
    except ImageGenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in image editing")
        raise HTTPException(status_code=500, detail="Image editing failed")

    return JSONResponse(result)


class StreamControlRequest(BaseModel):
    stream_id: str = Field(...)


@app.post("/api/cancel-stream", tags=["Chat"])
async def cancel_stream_endpoint(req: StreamControlRequest):
    """Cancel an active streaming chat response."""
    if cancel_stream(req.stream_id):
        return JSONResponse({"status": "cancelled", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


@app.post("/api/pause-stream", tags=["Chat"])
async def pause_stream_endpoint(req: StreamControlRequest):
    """Pause an active streaming chat response."""
    if pause_stream(req.stream_id):
        return JSONResponse({"status": "paused", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


@app.post("/api/resume-stream", tags=["Chat"])
async def resume_stream_endpoint(req: StreamControlRequest):
    """Resume a paused streaming chat response."""
    if resume_stream(req.stream_id):
        return JSONResponse({"status": "resumed", "stream_id": req.stream_id})
    return JSONResponse({"status": "not_found", "stream_id": req.stream_id}, status_code=404)


@app.get("/", tags=["Web"])
async def root():
    """Serve the main chat interface"""
    return FileResponse("static/index.html", media_type="text/html")


@app.get("/api/stats", tags=["System"])
async def get_stats():
    return JSONResponse({
        "name": "Vigzone AI",
        "version": "2.0.0",
        "description": "A real conversational AI assistant",
        "endpoints": {
            "health": "/health",
            "model_info": "/api/model-info",
            "upload": "POST /api/upload",
            "chat_stream": "POST /api/chat",
            "cancel_stream": "POST /api/cancel-stream",
            "pause_stream": "POST /api/pause-stream",
            "resume_stream": "POST /api/resume-stream",
            "chat_sync": "POST /api/chat/sync",
            "generate_image": "POST /api/generate-image",
            "edit_image": "POST /api/edit-image",
            "stats": "/api/stats",
        },
        "docs": "/docs",
        "redoc": "/redoc",
    })


# ==========================================
# ERROR HANDLERS
# ==========================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ==========================================
# STATIC FILES
# ==========================================
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENV", "development") == "development"

    logger.info(f"Starting Vigzone AI server on port {port}...")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info",
    )