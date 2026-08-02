"""Security and production configuration helpers for Vigzone AI.

The application intentionally remains a single-process deployment because it
uses in-process stream state and SQLite.  This is a supported production shape
for a small deployment when the data directory is mounted on persistent
storage.  Startup validation refuses unsafe production combinations instead
of silently running with weak defaults.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
import secrets
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("vigzone.security")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,100}$")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_production() -> bool:
    return os.getenv("APP_MODE", os.getenv("ENV", "development")).strip().lower() == "production"


def allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    # If CORS_ORIGINS is empty, we're on back4app with temp URL
    # Allow requests from the same origin (auto-detected per request in middleware)
    if not raw.strip():
        return ["http://localhost:8000"]  # Default for development
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def _is_loopback_origin(origin: str) -> bool:
    try:
        parsed = urlparse(origin)
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    except Exception:
        return False


def _is_ephemeral_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    text = str(resolved)
    return text == "/tmp" or text.startswith("/tmp/")


def validate_production_settings() -> None:
    """Raise RuntimeError when a production deployment is unsafe.

    Development stays frictionless.  Production must supply explicit secrets,
    an HTTPS cookie policy, a concrete CORS allow-list, one worker, and a
    non-temporary data path.
    """

    if not is_production():
        return

    errors: list[str] = []
    encryption_secret = os.getenv("ENCRYPTION_SECRET", "").strip()
    weak_secrets = {
        "",
        "change_this_to_a_long_random_secret",
        "vigzone-ephemeral-fallback-secret",
        "changeme",
    }
    if encryption_secret in weak_secrets or len(encryption_secret) < 32:
        errors.append("ENCRYPTION_SECRET must be a unique random value of at least 32 characters")

    if not env_bool("COOKIE_SECURE", True):
        errors.append("COOKIE_SECURE must be true")

    origins = allowed_origins()
    # Allow empty CORS_ORIGINS for back4app temporary URLs that change every 60min
    # The CORS middleware will fall back to localhost for development/testing
    if origins and "*" in origins:
        errors.append("CORS_ORIGINS must list explicit HTTPS origins; wildcard origins are forbidden")
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme != "https" and not _is_loopback_origin(origin):
            errors.append(f"CORS origin must use HTTPS: {origin}")

    workers = int(os.getenv("WORKERS", "1") or "1")
    if workers != 1:
        errors.append("WORKERS must be 1 while using SQLite and in-process streaming")

    data_dir = Path(os.getenv("VIGZONE_DATA_DIR", "data"))
    if _is_ephemeral_path(data_dir):
        errors.append("VIGZONE_DATA_DIR cannot point inside /tmp in production")
    if not env_bool("ALLOW_EPHEMERAL_STORAGE", False) and data_dir == Path("data"):
        logger.warning(
            "VIGZONE_DATA_DIR uses the default relative path. Mount /app/data "
            "as a persistent volume before serving real users."
        )

    if not os.getenv("GROQ_API_KEY", "").strip():
        errors.append("GROQ_API_KEY is required for the default chat plan")

    public_base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    # Allow empty PUBLIC_BASE_URL for back4app temporary URLs that change every 60min
    # The app will auto-detect the URL from incoming requests in that case
    if public_base:
        parsed_base = urlparse(public_base)
        if parsed_base.scheme != "https" and not _is_loopback_origin(public_base):
            errors.append("PUBLIC_BASE_URL must use HTTPS outside local development")

    if env_bool("VIRUS_SCAN_STRICT", True):
        from virus_scanner import scanner_healthcheck

        if not scanner_healthcheck():
            errors.append(
                "ClamAV and a readable signature database are required when VIRUS_SCAN_STRICT=true"
            )

    if errors:
        joined = "\n - ".join(errors)
        raise RuntimeError(f"Unsafe Vigzone production configuration:\n - {joined}")


def request_fingerprint(request: Request) -> str:
    """Return a privacy-preserving fingerprint for audit/session metadata."""

    user_agent = request.headers.get("user-agent", "")[:512]
    ip = client_ip(request)
    secret = os.getenv("ENCRYPTION_SECRET", "development-only")
    return hashlib.sha256(f"{secret}|{ip}|{user_agent}".encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str:
    """Resolve the client IP without blindly trusting spoofable proxy headers."""

    direct = request.client.host if request.client else "unknown"
    trusted = {
        item.strip()
        for item in os.getenv("TRUSTED_PROXY_IPS", "").split(",")
        if item.strip()
    }
    if direct not in trusted:
        return direct

    forwarded = request.headers.get("x-forwarded-for", "")
    candidate = forwarded.split(",", 1)[0].strip() if forwarded else direct
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return direct


def enforce_same_origin(request: Request, origins: Iterable[str] | None = None) -> None:
    """Reject cross-origin cookie-authenticated state-changing requests."""

    if request.method.upper() not in UNSAFE_METHODS:
        return
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        # Non-browser clients often omit Origin. Cookie-backed browser requests
        # include it; SameSite cookies provide the additional browser boundary.
        return
    permitted = set(origins or allowed_origins())
    host_origin = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
    permitted.add(host_origin)
    if origin not in permitted:
        raise HTTPException(status_code=403, detail="Cross-origin request rejected.")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add request IDs and browser security headers to every response."""

    @staticmethod
    def _apply_headers(response: Response, request_id: str) -> Response:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), payment=(), usb=(); "
            "microphone=(self)"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if is_production():
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # The existing trusted frontend is intentionally inline. A nonce-based
        # CSP is a later modularisation step; this policy still blocks framing,
        # plugins, base-URI rewriting, and unexpected network destinations.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "frame-src 'self' https://accounts.google.com https://drive.google.com "
            "https://docs.google.com; "
            "form-action 'self' https://accounts.google.com; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com "
            "https://apis.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "img-src 'self' data: blob: https:; media-src 'self' data: blob:; "
            "connect-src 'self' https://api.groq.com https://api.openai.com "
            "https://*.googleapis.com https://text.pollinations.ai "
            "https://image.pollinations.ai"
        )
        return response

    async def dispatch(self, request: Request, call_next) -> Response:
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if REQUEST_ID_RE.match(supplied) else secrets.token_urlsafe(16)
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            enforce_same_origin(request)
        except HTTPException as exc:
            return self._apply_headers(
                JSONResponse({"detail": exc.detail}, status_code=exc.status_code),
                request_id,
            )
        if is_production() and request.method.upper() in UNSAFE_METHODS:
            import auth as authmod

            retry_after = authmod.consume_rate_limit(
                f"ip:{client_ip(request)}",
                "unsafe_requests",
                int(os.getenv("GLOBAL_WRITE_RATE_LIMIT_PER_MINUTE", "180")),
                60,
            )
            if retry_after:
                return self._apply_headers(
                    JSONResponse(
                        {"detail": "Too many requests. Please slow down."},
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                    ),
                    request_id,
                )
        response = await call_next(request)

        self._apply_headers(response, request_id)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class RequestBodyLimitMiddleware:
    """ASGI body limiter that also covers chunked requests."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = int(max_bytes)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        try:
            declared = int(headers.get("content-length", "0") or "0")
        except ValueError:
            declared = 0
        if declared > self.max_bytes:
            await self._reject(send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await self._reject(send)

    async def _reject(self, send) -> None:
        import json

        body = json.dumps({"detail": "Request body is too large."}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class _RequestBodyTooLarge(Exception):
    pass
