"""
Vigzone AI - Authentication
============================
Email/password accounts + Google OAuth, backed by a local SQLite database.
No external auth dependencies — everything here is stdlib + httpx (already
a project dependency), so there's nothing extra to `pip install`.

Sessions are opaque random tokens stored server-side (so logout actually
revokes access immediately) and handed to the browser as an HttpOnly cookie.
"""

import os
import re
import secrets
import sqlite3
import hashlib
import hmac
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

DB_PATH = os.getenv("VIGZONE_DB_PATH", os.path.join("data", "vigzone.db"))
SESSION_COOKIE_NAME = "vigzone_session"
SESSION_TTL_DAYS = 30

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"


class AuthError(Exception):
    """Raised for any user-facing auth failure (bad credentials, duplicate
    email, Google not configured, etc.)."""


def google_is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


# ==========================================
# DATABASE
# ==========================================
@contextmanager
def _connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT,
                auth_provider TEXT NOT NULL DEFAULT 'email',
                google_id TEXT UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        # Token usage table — populated only in production mode.
        # In testing mode rows are never inserted so this stays empty.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS token_usage (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                prompt_tokens     INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens      INTEGER NOT NULL DEFAULT 0,
                ts                INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_token_usage_user ON token_usage(user_id)"
        )


# ==========================================
# PASSWORD HASHING (stdlib PBKDF2, no extra deps)
# ==========================================
def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return f"{salt}:{digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, hex_digest = stored.split(":", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return hmac.compare_digest(digest.hex(), hex_digest)


def _public_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "auth_provider": row["auth_provider"],
    }


# ==========================================
# ACCOUNT MANAGEMENT
# ==========================================
def create_user_with_password(email: str, password: str, name: str) -> dict:
    email = email.strip().lower()
    name = name.strip() or email.split("@")[0]

    if not EMAIL_RE.match(email):
        raise AuthError("That doesn't look like a valid email address.")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")

    with _connect() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise AuthError("An account with that email already exists. Try signing in instead.")

        cur = conn.execute(
            "INSERT INTO users (email, name, password_hash, auth_provider, created_at) VALUES (?, ?, ?, 'email', ?)",
            (email, name, _hash_password(password), datetime.now(timezone.utc).isoformat()),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _public_user(row)


def verify_password_login(email: str, password: str) -> dict:
    email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not row or row["auth_provider"] != "email" or not row["password_hash"]:
        raise AuthError("No account found with that email and password.")
    if not _verify_password(password, row["password_hash"]):
        raise AuthError("No account found with that email and password.")
    return _public_user(row)


def get_or_create_google_user(google_id: str, email: str, name: str) -> dict:
    email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        if row:
            return _public_user(row)

        # If an email/password account already exists with this email, link
        # Google sign-in to it rather than creating a duplicate account.
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET google_id = ?, auth_provider = ? WHERE id = ?",
                (google_id, row["auth_provider"] if row["auth_provider"] == "email" else "google", row["id"]),
            )
            # auth_provider stays as-is if it was already an email account that's
            # just adding Google as an alternate sign-in method.
            row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            return _public_user(row)

        cur = conn.execute(
            "INSERT INTO users (email, name, password_hash, auth_provider, google_id, created_at) "
            "VALUES (?, ?, NULL, 'google', ?, ?)",
            (email, name or email.split("@")[0], google_id, datetime.now(timezone.utc).isoformat()),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _public_user(row)


# ==========================================
# SESSIONS
# ==========================================
def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), (now + timedelta(days=SESSION_TTL_DAYS)).isoformat()),
        )
    return token


def get_user_by_session(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    return _public_user(row) if row else None


def delete_session(token: Optional[str]) -> None:
    if not token:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ==========================================
# GOOGLE OAUTH
# ==========================================
def google_build_auth_url(state: str) -> str:
    if not google_is_configured():
        raise AuthError("Google sign-in isn't configured on this server yet.")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{httpx.QueryParams(params)}"


async def google_exchange_code(code: str) -> dict:
    """Exchange an auth code for tokens, then fetch the user's profile.
    Returns dict with google_id, email, name."""
    if not google_is_configured():
        raise AuthError("Google sign-in isn't configured on this server yet.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise AuthError("Google rejected the sign-in request. Please try again.")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise AuthError("Google didn't return an access token.")

        profile_resp = await client.get(
            GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code != 200:
            raise AuthError("Couldn't fetch your Google profile.")
        profile = profile_resp.json()

    return {
        "google_id": profile.get("sub"),
        "email": profile.get("email", ""),
        "name": profile.get("name") or profile.get("given_name") or "",
    }
