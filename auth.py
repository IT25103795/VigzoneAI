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
        # ---- Migrations for per-user "bring your own Groq key" feature ----
        # SQLite has no "ADD COLUMN IF NOT EXISTS", so we probe first.
        existing_user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "own_groq_key_enc" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN own_groq_key_enc TEXT")
        if "use_own_key" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN use_own_key INTEGER NOT NULL DEFAULT 0")
        existing_usage_cols = {row[1] for row in conn.execute("PRAGMA table_info(token_usage)")}
        if "provider" not in existing_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN provider TEXT NOT NULL DEFAULT 'groq'")


# ==========================================
# PER-USER GROQ API KEY (encrypted at rest)
# ==========================================
# Each user can optionally bring their own Groq API key instead of using the
# app's default Groq key. The key is encrypted before it
# touches disk using a key derived from ENCRYPTION_SECRET (set this in your
# environment — if it's ever missing we fall back to a random one generated
# at startup, which works fine but means previously-saved keys become
# unreadable after a restart, so users would need to re-enter them).
def _get_fernet():
    from cryptography.fernet import Fernet
    import base64

    secret = os.getenv("ENCRYPTION_SECRET", "")
    if not secret:
        # No persistent secret configured — derive a process-local one so
        # the app still works, but warn since it won't survive a restart.
        import logging
        logging.getLogger("vigzone.auth").warning(
            "ENCRYPTION_SECRET is not set — saved API keys will not survive "
            "a restart. Set ENCRYPTION_SECRET to a fixed random string in "
            "your environment to fix this."
        )
        secret = "vigzone-ephemeral-fallback-secret"
    key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def set_user_groq_key(user_id: int, api_key: str) -> None:
    """Encrypt and store a user's own Groq API key, and mark it active."""
    token = _get_fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET own_groq_key_enc = ?, use_own_key = 1 WHERE id = ?",
            (token, user_id),
        )


def get_user_groq_key(user_id: int) -> Optional[str]:
    """Return the user's decrypted Groq key, or None if they don't have one."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT own_groq_key_enc FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not row or not row["own_groq_key_enc"]:
        return None
    try:
        return _get_fernet().decrypt(row["own_groq_key_enc"].encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def get_user_key_status(user_id: int) -> dict:
    """Return whether this user has a saved key and whether it's active."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT own_groq_key_enc, use_own_key FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not row:
        return {"has_key": False, "active": False}
    return {
        "has_key": bool(row["own_groq_key_enc"]),
        "active": bool(row["use_own_key"]),
    }


def set_use_own_key(user_id: int, enabled: bool) -> None:
    """Toggle whether the user's stored key is actually used for their chats."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET use_own_key = ? WHERE id = ?",
            (1 if enabled else 0, user_id),
        )


def clear_user_groq_key(user_id: int) -> None:
    """Forget the user's stored key entirely and revert them to the default Groq key."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET own_groq_key_enc = NULL, use_own_key = 0 WHERE id = ?",
            (user_id,),
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
