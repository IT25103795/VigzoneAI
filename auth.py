"""
Vigzone AI - Authentication
============================
Email/password accounts + Google OAuth, backed by a local SQLite database.
No external auth dependencies — everything here is stdlib + httpx (already
a project dependency), so there's nothing extra to `pip install`.

Sessions are opaque random tokens stored server-side (so logout actually
revokes access immediately) and handed to the browser as an HttpOnly cookie.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("vigzone.auth")

DATA_DIR = os.getenv("VIGZONE_DATA_DIR", "data")
DB_PATH = os.getenv("VIGZONE_DB_PATH", os.path.join(DATA_DIR, "vigzone.db"))
SESSION_COOKIE_NAME = "vigzone_session"
SESSION_TTL_DAYS = max(1, min(int(os.getenv("SESSION_TTL_DAYS", "30")), 90))
SESSION_TOUCH_SECONDS = 15 * 60
PASSWORD_ITERATIONS = 600_000
MAX_LEARNING_MEMORIES_PER_USER = max(1, int(os.getenv("MAX_LEARNING_MEMORIES_PER_USER", "200")))
MAX_WORKSPACES_PER_USER = max(1, int(os.getenv("MAX_WORKSPACES_PER_USER", "50")))
MAX_WORKSPACE_NOTES_PER_WORKSPACE = max(1, int(os.getenv("MAX_WORKSPACE_NOTES_PER_WORKSPACE", "500")))
MAX_FEEDBACK_PER_USER = max(1, int(os.getenv("MAX_FEEDBACK_PER_USER", "5000")))
MAX_ACTIVE_SHARES_PER_USER = max(1, int(os.getenv("MAX_ACTIVE_SHARES_PER_USER", "100")))
MAX_CONVERSATIONS_PER_USER = max(
    1,
    min(int(os.getenv("MAX_CONVERSATIONS_PER_USER", "200")), 200),
)

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


class StateConflictError(AuthError):
    """Raised when an optimistic-concurrency revision is stale."""

    def __init__(self, message: str, current: Optional[dict] = None):
        super().__init__(message)
        self.current = current or {}


def google_is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


# ==========================================
# DATABASE
# ==========================================
@contextmanager
def _connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def database_healthcheck() -> bool:
    try:
        with _connect() as conn:
            return conn.execute("SELECT 1").fetchone()[0] == 1
    except Exception:
        logger.exception("Database health check failed")
        return False


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
                role TEXT NOT NULL DEFAULT 'user',
                email_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT,
                revoked_at TEXT,
                client_fingerprint TEXT
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
                ts                INTEGER NOT NULL,
                routed_model      TEXT,
                route_reason      TEXT,
                routing_mode      TEXT,
                fallback_used     INTEGER NOT NULL DEFAULT 0,
                retry_count       INTEGER NOT NULL DEFAULT 0,
                latency_ms        INTEGER NOT NULL DEFAULT 0,
                time_to_first_token_ms INTEGER NOT NULL DEFAULT 0,
                cached_tokens     INTEGER NOT NULL DEFAULT 0,
                system_tokens     INTEGER NOT NULL DEFAULT 0,
                history_tokens    INTEGER NOT NULL DEFAULT 0,
                summary_tokens    INTEGER NOT NULL DEFAULT 0,
                memory_tokens     INTEGER NOT NULL DEFAULT 0,
                workspace_tokens  INTEGER NOT NULL DEFAULT 0,
                search_tokens     INTEGER NOT NULL DEFAULT 0,
                user_tokens       INTEGER NOT NULL DEFAULT 0,
                conversation_id   TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_token_usage_user ON token_usage(user_id)"
        )
        # ---- Migrations for per-user "bring your own Groq key" feature ----
        # SQLite has no "ADD COLUMN IF NOT EXISTS", so we probe first.
        existing_user_cols = _columns(conn, "users")
        if "own_groq_key_enc" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN own_groq_key_enc TEXT")
        if "use_own_key" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN use_own_key INTEGER NOT NULL DEFAULT 0")
        if "learning_enabled" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN learning_enabled INTEGER NOT NULL DEFAULT 1")
        if "role" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        if "email_verified" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE users SET email_verified = 1 WHERE google_id IS NOT NULL")
        if "updated_at" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN updated_at TEXT")
            conn.execute("UPDATE users SET updated_at = COALESCE(created_at, ?)", (_utc_now(),))

        existing_session_cols = _columns(conn, "sessions")
        if "last_seen_at" not in existing_session_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN last_seen_at TEXT")
        if "revoked_at" not in existing_session_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN revoked_at TEXT")
        if "client_fingerprint" not in existing_session_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN client_fingerprint TEXT")

        # Per-user Learning Center memories. These are private to each account
        # and only enter that user's chat context when learning_enabled = 1.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                memory_text TEXT NOT NULL,
                tags TEXT DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_learning_memories_user ON learning_memories(user_id, is_active)"
        )
        existing_usage_cols = _columns(conn, "token_usage")
        if "provider" not in existing_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN provider TEXT NOT NULL DEFAULT 'groq'")
        if "estimated" not in existing_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN estimated INTEGER NOT NULL DEFAULT 1")
        if "model" not in existing_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN model TEXT")
        if "provider_request_id" not in existing_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN provider_request_id TEXT")
        usage_migrations = {
            "routed_model": "TEXT",
            "route_reason": "TEXT",
            "routing_mode": "TEXT",
            "fallback_used": "INTEGER NOT NULL DEFAULT 0",
            "retry_count": "INTEGER NOT NULL DEFAULT 0",
            "latency_ms": "INTEGER NOT NULL DEFAULT 0",
            "time_to_first_token_ms": "INTEGER NOT NULL DEFAULT 0",
            "cached_tokens": "INTEGER NOT NULL DEFAULT 0",
            "system_tokens": "INTEGER NOT NULL DEFAULT 0",
            "history_tokens": "INTEGER NOT NULL DEFAULT 0",
            "summary_tokens": "INTEGER NOT NULL DEFAULT 0",
            "memory_tokens": "INTEGER NOT NULL DEFAULT 0",
            "workspace_tokens": "INTEGER NOT NULL DEFAULT 0",
            "search_tokens": "INTEGER NOT NULL DEFAULT 0",
            "user_tokens": "INTEGER NOT NULL DEFAULT 0",
            "conversation_id": "TEXT",
        }
        for column, definition in usage_migrations.items():
            if column not in existing_usage_cols:
                conn.execute(
                    f"ALTER TABLE token_usage ADD COLUMN {column} {definition}"
                )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_token_usage_route "
            "ON token_usage(route_reason, model, ts)"
        )


        # Deep Features v3: private per-user workspaces and lightweight workspace notes/assets.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                mode TEXT DEFAULT 'general',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workspaces_user ON workspaces(user_id, updated_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                kind TEXT DEFAULT 'note',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workspace_notes_ws ON workspace_notes(workspace_id, user_id, created_at DESC)"
        )

        # Durable product state replaces per-user and global loose JSON files.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS brain_snapshots (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                payload_json TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                client_updated_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message_id TEXT,
                conversation_id TEXT,
                rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
                reason TEXT NOT NULL DEFAULT '',
                message_text TEXT NOT NULL DEFAULT '',
                assistant_text TEXT NOT NULL DEFAULT '',
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_user_created ON feedback(user_id, created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shared_chats (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                messages_json TEXT NOT NULL,
                is_public INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_shared_chats_owner ON shared_chats(user_id, created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rate_limits (
                subject TEXT NOT NULL,
                scope TEXT NOT NULL,
                window_start INTEGER NOT NULL,
                hits INTEGER NOT NULL,
                PRIMARY KEY (subject, scope)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start)"
        )
        conn.execute(
            "DELETE FROM rate_limits WHERE window_start < ?",
            (int(time.time()) - 7 * 24 * 60 * 60,),
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL DEFAULT 'New chat',
                messages_json TEXT NOT NULL DEFAULT '[]',
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT,
                PRIMARY KEY (id, user_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_tokens_user ON account_tokens(user_id, purpose)"
        )

        # Session tokens are stored as SHA-256 digests.  Older builds stored
        # plaintext; values that are not already 64 hex characters are migrated
        # once so existing cookies remain valid after the upgrade.
        raw_sessions = conn.execute("SELECT token FROM sessions").fetchall()
        for session_row in raw_sessions:
            stored = str(session_row["token"])
            if not re.fullmatch(r"[0-9a-f]{64}", stored):
                conn.execute(
                    "UPDATE sessions SET token = ? WHERE token = ?",
                    (_token_hash(stored), stored),
                )

        purge_expired_sessions(conn=conn)
        _bootstrap_admin(conn)


# ==========================================
# PER-USER GROQ API KEY (encrypted at rest)
# ==========================================
# Each user can optionally bring their own Groq API key instead of using the
# app's default Groq key. The key is encrypted before it
# touches disk using a key derived from ENCRYPTION_SECRET (set this in your
# environment — if it's ever missing we fall back to a random one generated
# at startup, which works fine but means previously-saved keys become
# unreadable after a restart, so users would need to re-enter them).
_EPHEMERAL_ENCRYPTION_SECRET = secrets.token_urlsafe(48)


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
        secret = _EPHEMERAL_ENCRYPTION_SECRET
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
# PER-USER LEARNING CENTER / PRIVATE MEMORY
# ==========================================
def get_learning_status(user_id: int) -> dict:
    """Return whether private Learning Center memories are used for this user."""
    with _connect() as conn:
        row = conn.execute("SELECT learning_enabled FROM users WHERE id = ?", (user_id,)).fetchone()
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM learning_memories WHERE user_id = ?",
            (user_id,),
        ).fetchone()["c"]
        active_count = conn.execute(
            "SELECT COUNT(*) AS c FROM learning_memories WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()["c"]
    return {
        "enabled": True if row is None else bool(row["learning_enabled"]),
        "count": int(count or 0),
        "active_count": int(active_count or 0),
    }


def set_learning_enabled(user_id: int, enabled: bool) -> dict:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET learning_enabled = ? WHERE id = ?",
            (1 if enabled else 0, user_id),
        )
    return get_learning_status(user_id)


def _memory_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "memory_text": row["memory_text"],
        "tags": row["tags"] or "",
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_learning_memories(user_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, memory_text, tags, is_active, created_at, updated_at
            FROM learning_memories
            WHERE user_id = ?
            ORDER BY is_active DESC, updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [_memory_row_to_dict(row) for row in rows]


def add_learning_memory(user_id: int, memory_text: str, tags: str = "") -> dict:
    memory_text = (memory_text or "").strip()
    tags = (tags or "").strip()[:200]
    if len(memory_text) < 3:
        raise AuthError("Memory is too short.")
    if len(memory_text) > 1200:
        raise AuthError("Memory is too long. Keep it under 1,200 characters.")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) FROM learning_memories WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if int(count) >= MAX_LEARNING_MEMORIES_PER_USER:
            raise AuthError(
                f"Learning Center is limited to {MAX_LEARNING_MEMORIES_PER_USER} memories per account."
            )
        cur = conn.execute(
            """
            INSERT INTO learning_memories (user_id, memory_text, tags, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (user_id, memory_text, tags, now, now),
        )
        row = conn.execute(
            "SELECT id, memory_text, tags, is_active, created_at, updated_at FROM learning_memories WHERE id = ? AND user_id = ?",
            (cur.lastrowid, user_id),
        ).fetchone()
    return _memory_row_to_dict(row)


def update_learning_memory(user_id: int, memory_id: int, memory_text: Optional[str] = None, tags: Optional[str] = None, is_active: Optional[bool] = None) -> dict:
    updates = []
    values = []
    if memory_text is not None:
        memory_text = memory_text.strip()
        if len(memory_text) < 3:
            raise AuthError("Memory is too short.")
        if len(memory_text) > 1200:
            raise AuthError("Memory is too long. Keep it under 1,200 characters.")
        updates.append("memory_text = ?")
        values.append(memory_text)
    if tags is not None:
        updates.append("tags = ?")
        values.append(tags.strip()[:200])
    if is_active is not None:
        updates.append("is_active = ?")
        values.append(1 if is_active else 0)
    if not updates:
        with _connect() as conn:
            row = conn.execute(
                "SELECT id, memory_text, tags, is_active, created_at, updated_at FROM learning_memories WHERE id = ? AND user_id = ?",
                (memory_id, user_id),
            ).fetchone()
        if not row:
            raise AuthError("Memory not found.")
        return _memory_row_to_dict(row)

    updates.append("updated_at = ?")
    values.append(datetime.now(timezone.utc).isoformat())
    values.extend([memory_id, user_id])
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE learning_memories SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        if cur.rowcount == 0:
            raise AuthError("Memory not found.")
        row = conn.execute(
            "SELECT id, memory_text, tags, is_active, created_at, updated_at FROM learning_memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        ).fetchone()
    return _memory_row_to_dict(row)


def delete_learning_memory(user_id: int, memory_id: int) -> None:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM learning_memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        if cur.rowcount == 0:
            raise AuthError("Memory not found.")


def _simple_terms(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_]{3,}", text or "")}


def get_learning_context(user_id: int, query: str = "", limit: int = 10) -> str:
    """Return a compact system-context block of active, user-approved memories.

    This is private per user. We include newest memories and lightly prioritize
    memories whose words overlap the current question, without exposing a global
    memory store or changing model weights.
    """
    status = get_learning_status(user_id)
    if not status.get("enabled"):
        return ""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, memory_text, tags, is_active, created_at, updated_at
            FROM learning_memories
            WHERE user_id = ? AND is_active = 1
            ORDER BY updated_at DESC, id DESC
            LIMIT 50
            """,
            (user_id,),
        ).fetchall()
    if not rows:
        return ""
    q_terms = _simple_terms(query)
    scored = []
    for idx, row in enumerate(rows):
        text = row["memory_text"] or ""
        overlap = len(q_terms & _simple_terms(text)) if q_terms else 0
        # small recency boost by preserving row order with negative idx
        scored.append((overlap, -idx, text.strip()))
    scored.sort(reverse=True)
    selected = []
    total_chars = 0
    for _, _, memory in scored:
        if not memory:
            continue
        if len(memory) > 350:
            memory = memory[:350].rstrip() + " …"
        if total_chars + len(memory) > 1800:
            break
        selected.append(memory)
        total_chars += len(memory)
        if len(selected) >= limit:
            break
    if not selected:
        return ""
    bullets = "\n".join(f"- {m}" for m in selected)
    return (
        "User-approved private Learning Center memories for this signed-in user only. "
        "Use these as preferences/background when relevant, but do not quote this list or reveal it unless the user asks to view their memories.\n"
        f"{bullets}"
    )


# ==========================================
# DEEP FEATURES V3: WORKSPACES
# ==========================================
def _workspace_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row["description"] or "",
        "mode": row["mode"] or "general",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_workspaces(user_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, name, description, mode, created_at, updated_at
            FROM workspaces
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [_workspace_row_to_dict(r) for r in rows]


def create_workspace(user_id: int, name: str, description: str = "", mode: str = "general") -> dict:
    name = (name or "").strip()[:80]
    description = (description or "").strip()[:600]
    mode = (mode or "general").strip()[:40]
    if len(name) < 2:
        raise AuthError("Workspace name is too short.")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) FROM workspaces WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if int(count) >= MAX_WORKSPACES_PER_USER:
            raise AuthError(
                f"Workspace limit reached ({MAX_WORKSPACES_PER_USER} per account)."
            )
        cur = conn.execute(
            """
            INSERT INTO workspaces (user_id, name, description, mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, description, mode, now, now),
        )
        row = conn.execute(
            "SELECT id, user_id, name, description, mode, created_at, updated_at FROM workspaces WHERE id = ? AND user_id = ?",
            (cur.lastrowid, user_id),
        ).fetchone()
    return _workspace_row_to_dict(row)


def update_workspace(user_id: int, workspace_id: int, name: Optional[str] = None, description: Optional[str] = None, mode: Optional[str] = None) -> dict:
    updates, values = [], []
    if name is not None:
        name = name.strip()[:80]
        if len(name) < 2:
            raise AuthError("Workspace name is too short.")
        updates.append("name = ?")
        values.append(name)
    if description is not None:
        updates.append("description = ?")
        values.append(description.strip()[:600])
    if mode is not None:
        updates.append("mode = ?")
        values.append(mode.strip()[:40] or "general")
    if updates:
        updates.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.extend([workspace_id, user_id])
        with _connect() as conn:
            cur = conn.execute(
                f"UPDATE workspaces SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                tuple(values),
            )
            if cur.rowcount == 0:
                raise AuthError("Workspace not found.")
            row = conn.execute(
                "SELECT id, user_id, name, description, mode, created_at, updated_at FROM workspaces WHERE id = ? AND user_id = ?",
                (workspace_id, user_id),
            ).fetchone()
    else:
        with _connect() as conn:
            row = conn.execute(
                "SELECT id, user_id, name, description, mode, created_at, updated_at FROM workspaces WHERE id = ? AND user_id = ?",
                (workspace_id, user_id),
            ).fetchone()
    if not row:
        raise AuthError("Workspace not found.")
    return _workspace_row_to_dict(row)


def delete_workspace(user_id: int, workspace_id: int) -> None:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM workspaces WHERE id = ? AND user_id = ?", (workspace_id, user_id))
        if cur.rowcount == 0:
            raise AuthError("Workspace not found.")


def add_workspace_note(user_id: int, workspace_id: int, title: str, content: str, kind: str = "note") -> dict:
    title = (title or "Note").strip()[:120]
    content = (content or "").strip()
    kind = (kind or "note").strip()[:30]
    if len(content) < 2:
        raise AuthError("Workspace note is too short.")
    if len(content) > 5000:
        content = content[:5000].rstrip() + " …"
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ws = conn.execute("SELECT id FROM workspaces WHERE id = ? AND user_id = ?", (workspace_id, user_id)).fetchone()
        if not ws:
            raise AuthError("Workspace not found.")
        count = conn.execute(
            "SELECT COUNT(*) FROM workspace_notes WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id),
        ).fetchone()[0]
        if int(count) >= MAX_WORKSPACE_NOTES_PER_WORKSPACE:
            raise AuthError(
                f"Workspace note limit reached ({MAX_WORKSPACE_NOTES_PER_WORKSPACE} per workspace)."
            )
        cur = conn.execute(
            """
            INSERT INTO workspace_notes (workspace_id, user_id, title, content, kind, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, user_id, title, content, kind, now),
        )
        conn.execute("UPDATE workspaces SET updated_at = ? WHERE id = ? AND user_id = ?", (now, workspace_id, user_id))
        row = conn.execute(
            "SELECT id, workspace_id, user_id, title, content, kind, created_at FROM workspace_notes WHERE id = ? AND user_id = ?",
            (cur.lastrowid, user_id),
        ).fetchone()
    return dict(row)


def list_workspace_notes(user_id: int, workspace_id: int, limit: int = 30) -> list[dict]:
    with _connect() as conn:
        ws = conn.execute("SELECT id FROM workspaces WHERE id = ? AND user_id = ?", (workspace_id, user_id)).fetchone()
        if not ws:
            raise AuthError("Workspace not found.")
        rows = conn.execute(
            """
            SELECT id, workspace_id, user_id, title, content, kind, created_at
            FROM workspace_notes
            WHERE workspace_id = ? AND user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (workspace_id, user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_workspace_context(user_id: int, workspace_id: Optional[int], query: str = "", limit: int = 8) -> str:
    if not workspace_id:
        return ""
    try:
        workspace_id = int(workspace_id)
    except Exception:
        return ""
    with _connect() as conn:
        ws = conn.execute(
            "SELECT id, name, description, mode FROM workspaces WHERE id = ? AND user_id = ?",
            (workspace_id, user_id),
        ).fetchone()
        if not ws:
            return ""
        rows = conn.execute(
            """
            SELECT title, content, kind, created_at
            FROM workspace_notes
            WHERE workspace_id = ? AND user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (workspace_id, user_id, limit),
        ).fetchall()
    lines = [f"Active workspace: {ws['name']} (mode: {ws['mode'] or 'general'})."]
    if ws["description"]:
        lines.append(f"Workspace description: {ws['description']}")
    if rows:
        lines.append("Relevant private workspace notes/assets:")
        for r in rows:
            content = (r["content"] or "").strip().replace("\n", " ")
            if len(content) > 420:
                content = content[:420].rstrip() + " …"
            lines.append(f"- [{r['kind']}] {r['title']}: {content}")
    return "\n".join(lines)


# ==========================================
# DURABLE PRODUCT STATE
# ==========================================
def consume_rate_limit(
    subject: str,
    scope: str,
    limit: int,
    window_seconds: int = 60,
) -> int:
    """Consume one request and return ``0`` or seconds until retry.

    The fixed-window counter is durable and shared by every process that points
    at this database.  Vigzone still deploys with one worker because stream
    pause state is in-process, but the limiter no longer resets on every
    request or module reload.
    """

    if limit <= 0:
        return 0
    now = int(time.time())
    subject = str(subject)[:180]
    scope = str(scope)[:80]
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if secrets.randbelow(256) == 0:
            conn.execute(
                "DELETE FROM rate_limits WHERE window_start < ?",
                (now - 7 * 24 * 60 * 60,),
            )
        row = conn.execute(
            "SELECT window_start, hits FROM rate_limits WHERE subject = ? AND scope = ?",
            (subject, scope),
        ).fetchone()
        if not row or now - int(row["window_start"]) >= window_seconds:
            conn.execute(
                """
                INSERT INTO rate_limits(subject, scope, window_start, hits)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(subject, scope)
                DO UPDATE SET window_start = excluded.window_start, hits = 1
                """,
                (subject, scope, now),
            )
            return 0
        if int(row["hits"]) >= limit:
            return max(1, window_seconds - (now - int(row["window_start"])))
        conn.execute(
            "UPDATE rate_limits SET hits = hits + 1 WHERE subject = ? AND scope = ?",
            (subject, scope),
        )
        return 0


def get_brain_snapshot(user_id: int) -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT payload_json, version, client_updated_at, updated_at
            FROM brain_snapshots WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return {
            "version": 0,
            "updated_at": None,
            "client_updated_at": None,
            "payload": {},
        }
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {
        "version": int(row["version"]),
        "updated_at": row["updated_at"],
        "client_updated_at": row["client_updated_at"],
        "payload": payload if isinstance(payload, dict) else {},
    }


def save_brain_snapshot(
    user_id: int,
    payload: dict,
    client_updated_at: Optional[str],
    base_version: Optional[int],
) -> dict:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    max_bytes = max(64_000, int(os.getenv("BRAIN_CLOUD_MAX_BYTES", "2000000")))
    if len(encoded.encode("utf-8")) > max_bytes:
        raise AuthError(f"Brain sync payload exceeds the {max_bytes // 1000} KB limit.")
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT payload_json, version, client_updated_at, updated_at
            FROM brain_snapshots WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        current_version = int(row["version"]) if row else 0
        if base_version is not None and base_version != current_version:
            try:
                current_payload = json.loads(row["payload_json"]) if row else {}
            except (TypeError, json.JSONDecodeError):
                current_payload = {}
            raise StateConflictError(
                "Brain data changed on another device. Refresh before saving.",
                current={
                    "version": current_version,
                    "updated_at": row["updated_at"] if row else None,
                    "client_updated_at": row["client_updated_at"] if row else None,
                    "payload": current_payload,
                },
            )
        next_version = current_version + 1
        conn.execute(
            """
            INSERT INTO brain_snapshots(
                user_id, payload_json, version, client_updated_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                version = excluded.version,
                client_updated_at = excluded.client_updated_at,
                updated_at = excluded.updated_at
            """,
            (user_id, encoded, next_version, client_updated_at, now),
        )
    return {
        "ok": True,
        "version": next_version,
        "updated_at": now,
        "client_updated_at": client_updated_at,
    }


def save_feedback_record(user_id: int, item: dict) -> str:
    feedback_id = secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:18]
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if int(count) >= MAX_FEEDBACK_PER_USER:
            raise AuthError(
                f"Feedback storage limit reached ({MAX_FEEDBACK_PER_USER} records per account)."
            )
        conn.execute(
            """
            INSERT INTO feedback(
                id, user_id, message_id, conversation_id, rating, reason,
                message_text, assistant_text, context_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                user_id,
                str(item.get("message_id") or "")[:120],
                str(item.get("conversation_id") or "")[:120],
                str(item.get("rating") or "up"),
                str(item.get("reason") or "")[:500],
                str(item.get("message_text") or "")[:6000],
                str(item.get("assistant_text") or "")[:12000],
                json.dumps(item.get("context") or {}, ensure_ascii=False)[:20_000],
                _utc_now(),
            ),
        )
    return feedback_id


def create_shared_chat(
    user_id: int,
    share_id: str,
    title: str,
    messages: list[dict],
    is_public: bool,
    expires_in_days: int,
) -> dict:
    clean_messages = messages[:200]
    encoded = json.dumps(clean_messages, ensure_ascii=False, separators=(",", ":"))
    max_bytes = int(os.getenv("SHARE_MAX_BYTES", "1000000"))
    if len(encoded.encode("utf-8")) > max_bytes:
        raise AuthError("This chat is too large to share. Export it instead.")
    now = datetime.now(timezone.utc)
    days = max(1, min(int(expires_in_days), 30))
    expires = now + timedelta(days=days)
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Inactive share bodies no longer serve content. Retain the newest 500
        conn.execute(
            """
            DELETE FROM shared_chats
            WHERE user_id = ?
              AND (revoked_at IS NOT NULL OR expires_at <= ?)
              AND id NOT IN (
                  SELECT id FROM shared_chats
                  WHERE user_id = ? AND (revoked_at IS NOT NULL OR expires_at <= ?)
                  ORDER BY created_at DESC LIMIT 500
              )
            """,
            (user_id, now.isoformat(), user_id, now.isoformat()),
        )
        active_count = conn.execute(
            """
            SELECT COUNT(*) FROM shared_chats
            WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?
            """,
            (user_id, now.isoformat()),
        ).fetchone()[0]
        if int(active_count) >= MAX_ACTIVE_SHARES_PER_USER:
            raise AuthError(
                f"Active share limit reached ({MAX_ACTIVE_SHARES_PER_USER} per account). Revoke an existing link first."
            )
        conn.execute(
            """
            INSERT INTO shared_chats(
                id, user_id, title, messages_json, is_public,
                created_at, expires_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                share_id,
                user_id,
                title[:160],
                encoded,
                1 if is_public else 0,
                now.isoformat(),
                expires.isoformat(),
            ),
        )
    return {
        "id": share_id,
        "title": title[:160],
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "public": bool(is_public),
    }


def get_shared_chat(share_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM shared_chats
            WHERE id = ? AND is_public = 1 AND revoked_at IS NULL AND expires_at > ?
            """,
            (share_id, _utc_now()),
        ).fetchone()
    if not row:
        return None
    try:
        messages = json.loads(row["messages_json"])
    except (TypeError, json.JSONDecodeError):
        messages = []
    return {
        "id": row["id"],
        "user_id": int(row["user_id"]),
        "title": row["title"],
        "messages": messages if isinstance(messages, list) else [],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "public": bool(row["is_public"]),
    }


def list_shared_chats(user_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, is_public, created_at, expires_at, revoked_at
            FROM shared_chats WHERE user_id = ? ORDER BY created_at DESC LIMIT 100
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "public": bool(row["is_public"]),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "revoked": bool(row["revoked_at"]),
        }
        for row in rows
    ]


def revoke_shared_chat(user_id: int, share_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE shared_chats SET revoked_at = ?
            WHERE id = ? AND user_id = ? AND revoked_at IS NULL
            """,
            (_utc_now(), share_id, user_id),
        )
        return bool(cur.rowcount)


def product_analytics() -> dict:
    with _connect() as conn:
        brain_users = conn.execute("SELECT COUNT(*) FROM brain_snapshots").fetchone()[0]
        feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        negative = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating = 'down'"
        ).fetchone()[0]
        shares = conn.execute("SELECT COUNT(*) FROM shared_chats").fetchone()[0]
    return {
        "brain_users": int(brain_users),
        "feedback_count": int(feedback_count),
        "negative_feedback": int(negative),
        "share_count": int(shares),
    }


def list_conversations(user_id: int, limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, revision, created_at, updated_at
            FROM conversations
            WHERE user_id = ? AND deleted_at IS NULL
            ORDER BY updated_at DESC LIMIT ?
            """,
            (user_id, max(1, min(limit, 200))),
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation(user_id: int, conversation_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM conversations
            WHERE id = ? AND user_id = ? AND deleted_at IS NULL
            """,
            (conversation_id, user_id),
        ).fetchone()
    if not row:
        return None
    try:
        messages = json.loads(row["messages_json"])
    except (TypeError, json.JSONDecodeError):
        messages = []
    return {
        "id": row["id"],
        "title": row["title"],
        "messages": messages if isinstance(messages, list) else [],
        "revision": int(row["revision"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def upsert_conversation(
    user_id: int,
    conversation_id: str,
    title: str,
    messages: list[dict],
    base_revision: Optional[int],
) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", conversation_id):
        raise AuthError("Invalid conversation ID.")
    encoded = json.dumps(messages[:500], ensure_ascii=False, separators=(",", ":"))
    max_bytes = int(os.getenv("CONVERSATION_MAX_BYTES", "2000000"))
    if len(encoded.encode("utf-8")) > max_bytes:
        raise AuthError("Conversation is too large to sync.")
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM conversations WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()
        if row is None or row["deleted_at"] is not None:
            active_count = conn.execute(
                """
                SELECT COUNT(*) FROM conversations
                WHERE user_id = ? AND deleted_at IS NULL
                """,
                (user_id,),
            ).fetchone()[0]
            if int(active_count) >= MAX_CONVERSATIONS_PER_USER:
                raise AuthError(
                    f"Conversation sync limit reached ({MAX_CONVERSATIONS_PER_USER} per account). Delete an older synced conversation first."
                )
        current_revision = int(row["revision"]) if row else 0
        if base_revision is not None and base_revision != current_revision:
            try:
                current_messages = json.loads(row["messages_json"]) if row else []
            except (TypeError, json.JSONDecodeError):
                current_messages = []
            raise StateConflictError(
                "Conversation changed on another device.",
                current={
                    "id": row["id"],
                    "title": row["title"],
                    "messages": current_messages,
                    "revision": current_revision,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                } if row else {},
            )
        revision = current_revision + 1
        conn.execute(
            """
            INSERT INTO conversations(
                id, user_id, title, messages_json, revision, created_at,
                updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id, user_id) DO UPDATE SET
                title = excluded.title,
                messages_json = excluded.messages_json,
                revision = excluded.revision,
                updated_at = excluded.updated_at,
                deleted_at = NULL
            """,
            (
                conversation_id,
                user_id,
                title[:160] or "New chat",
                encoded,
                revision,
                now,
                now,
            ),
        )
    return get_conversation(user_id, conversation_id) or {}


def delete_conversation(user_id: int, conversation_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE conversations SET deleted_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND deleted_at IS NULL
            """,
            (_utc_now(), _utc_now(), conversation_id, user_id),
        )
        return bool(cur.rowcount)


def export_user_data(user_id: int) -> dict:
    with _connect() as conn:
        user = conn.execute(
            """
            SELECT id, email, name, auth_provider, role, email_verified,
                   created_at, updated_at
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        memories = [dict(row) for row in conn.execute(
            """
            SELECT id, memory_text, tags, is_active, created_at, updated_at
            FROM learning_memories WHERE user_id = ? ORDER BY created_at
            """,
            (user_id,),
        ).fetchall()]
        workspaces = [dict(row) for row in conn.execute(
            "SELECT * FROM workspaces WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()]
        notes = [dict(row) for row in conn.execute(
            "SELECT * FROM workspace_notes WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()]
        usage = [dict(row) for row in conn.execute(
            """
            SELECT prompt_tokens, completion_tokens, total_tokens, ts, provider,
                   estimated, model, provider_request_id, routed_model,
                   route_reason, routing_mode, fallback_used, retry_count,
                   latency_ms, time_to_first_token_ms, cached_tokens,
                   system_tokens, history_tokens, summary_tokens, memory_tokens,
                   workspace_tokens, search_tokens, user_tokens, conversation_id
            FROM token_usage WHERE user_id = ? ORDER BY ts
            """,
            (user_id,),
        ).fetchall()]
        feedback = [dict(row) for row in conn.execute(
            """
            SELECT id, message_id, conversation_id, rating, reason,
                   message_text, assistant_text, context_json, created_at
            FROM feedback WHERE user_id = ? ORDER BY created_at
            """,
            (user_id,),
        ).fetchall()]
    return {
        "exported_at": _utc_now(),
        "account": dict(user) if user else {},
        "learning_memories": memories,
        "workspaces": workspaces,
        "workspace_notes": notes,
        "brain": get_brain_snapshot(user_id),
        "conversations": [
            get_conversation(user_id, item["id"])
            for item in list_conversations(user_id, limit=200)
        ],
        "shared_chats": list_shared_chats(user_id),
        "usage": usage,
        "feedback": feedback,
    }


# ==========================================
# PASSWORD HASHING / ROLES
# ==========================================
def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, iterations_raw, salt_hex, digest_hex = stored.split("$", 3)
            iterations = int(iterations_raw)
        else:
            # Legacy Vigzone format: ``salt:digest`` at 200k iterations.
            salt_hex, digest_hex = stored.split(":", 1)
            iterations = 200_000
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def _password_needs_rehash(stored: str) -> bool:
    if not stored.startswith("pbkdf2_sha256$"):
        return True
    try:
        return int(stored.split("$", 3)[1]) < PASSWORD_ITERATIONS
    except (ValueError, IndexError):
        return True


def _configured_admin_emails() -> set[str]:
    return {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }


def is_admin_email(email: str) -> bool:
    """Return whether an email is on the configured, verified admin allow-list.

    This helper is retained for configuration displays.  Authorization uses the
    durable ``users.role`` value returned in the authenticated session.
    """

    return (email or "").strip().lower() in _configured_admin_emails()


def _row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def _public_user(row: sqlite3.Row) -> dict:
    role = str(_row_value(row, "role", "user") or "user")
    return {
        "id": int(row["id"]),
        "email": str(row["email"]),
        "name": str(row["name"]),
        "auth_provider": str(row["auth_provider"]),
        "role": role,
        "email_verified": bool(_row_value(row, "email_verified", 0)),
        "is_admin": role == "admin",
    }


def _bootstrap_admin(conn: sqlite3.Connection) -> None:
    """Safely assign admin roles.

    ``ADMIN_EMAILS`` only promotes already verified addresses (normally Google
    OAuth users).  A local first admin can be created with both
    ``ADMIN_BOOTSTRAP_EMAIL`` and ``ADMIN_BOOTSTRAP_PASSWORD``.  An attacker
    cannot pre-register the address and gain admin because an existing local
    account must prove the same bootstrap password before promotion.
    """

    for email in _configured_admin_emails():
        conn.execute(
            """
            UPDATE users SET role = 'admin', updated_at = ?
            WHERE email = ? AND email_verified = 1
            """,
            (_utc_now(), email),
        )

    bootstrap_email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "").strip().lower()
    bootstrap_password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    if not bootstrap_email and not bootstrap_password:
        return
    if not EMAIL_RE.match(bootstrap_email) or len(bootstrap_password) < 12:
        raise RuntimeError(
            "ADMIN_BOOTSTRAP_EMAIL and a password of at least 12 characters "
            "must both be set for local admin bootstrap"
        )
    row = conn.execute("SELECT * FROM users WHERE email = ?", (bootstrap_email,)).fetchone()
    now = _utc_now()
    if row:
        if _row_value(row, "role", "user") == "admin":
            return
        verified_google = bool(_row_value(row, "email_verified", 0)) and bool(
            _row_value(row, "google_id")
        )
        password_matches = bool(row["password_hash"]) and _verify_password(
            bootstrap_password,
            row["password_hash"],
        )
        if not (verified_google or password_matches):
            raise RuntimeError(
                "ADMIN_BOOTSTRAP_EMAIL already exists but ownership could not be verified"
            )
        conn.execute(
            "UPDATE users SET role = 'admin', email_verified = 1, updated_at = ? WHERE id = ?",
            (now, row["id"]),
        )
        return

    conn.execute(
        """
        INSERT INTO users (
            email, name, password_hash, auth_provider, role,
            email_verified, created_at, updated_at
        ) VALUES (?, ?, ?, 'email', 'admin', 1, ?, ?)
        """,
        (
            bootstrap_email,
            os.getenv("ADMIN_BOOTSTRAP_NAME", "Vigzone Admin").strip() or "Vigzone Admin",
            _hash_password(bootstrap_password),
            now,
            now,
        ),
    )


# ==========================================
# ACCOUNT MANAGEMENT
# ==========================================
def create_user_with_password(email: str, password: str, name: str) -> dict:
    email = email.strip().lower()
    name = name.strip() or email.split("@")[0]

    if not EMAIL_RE.match(email):
        raise AuthError("That doesn't look like a valid email address.")
    if len(password) < 10:
        raise AuthError("Password must be at least 10 characters.")
    if len(password.encode("utf-8")) > 256:
        raise AuthError("Password is too long.")

    with _connect() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise AuthError("An account with that email already exists. Try signing in instead.")

        now = _utc_now()
        cur = conn.execute(
            """
            INSERT INTO users (
                email, name, password_hash, auth_provider, role,
                email_verified, created_at, updated_at
            ) VALUES (?, ?, ?, 'email', 'user', 0, ?, ?)
            """,
            (email, name, _hash_password(password), now, now),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _public_user(row)


def verify_password_login(email: str, password: str) -> dict:
    email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not row["password_hash"] or not _verify_password(password, row["password_hash"]):
            raise AuthError("No account found with that email and password.")
        if _password_needs_rehash(row["password_hash"]):
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (_hash_password(password), _utc_now(), row["id"]),
            )
        return _public_user(row)


def get_or_create_google_user(
    google_id: str,
    email: str,
    name: str,
    email_verified: bool = False,
) -> dict:
    email = email.strip().lower()
    if not google_id or not EMAIL_RE.match(email) or not email_verified:
        raise AuthError("Google did not verify this email address.")
    with _connect() as conn:
        now = _utc_now()
        row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            _bootstrap_admin(conn)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            return _public_user(row)

        # Linking by email is safe because Google explicitly verified ownership.
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            provider = "email+google" if row["password_hash"] else "google"
            conn.execute(
                """
                UPDATE users
                SET google_id = ?, auth_provider = ?, email_verified = 1, updated_at = ?
                WHERE id = ?
                """,
                (google_id, provider, now, row["id"]),
            )
            _bootstrap_admin(conn)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            return _public_user(row)

        cur = conn.execute(
            """
            INSERT INTO users (
                email, name, password_hash, auth_provider, google_id, role,
                email_verified, created_at, updated_at
            ) VALUES (?, ?, NULL, 'google', ?, 'user', 1, ?, ?)
            """,
            (email, name or email.split("@")[0], google_id, now, now),
        )
        _bootstrap_admin(conn)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _public_user(row)


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    if len(new_password) < 10:
        raise AuthError("New password must be at least 10 characters.")
    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash, google_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            raise AuthError("Account not found.")
        if row["password_hash"] and not _verify_password(current_password, row["password_hash"]):
            raise AuthError("Current password is incorrect.")
        conn.execute(
            "UPDATE users SET password_hash = ?, auth_provider = ?, updated_at = ? WHERE id = ?",
            (
                _hash_password(new_password),
                "email+google" if row["google_id"] else "email",
                _utc_now(),
                user_id,
            ),
        )
        conn.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ?", (_utc_now(), user_id))


def account_has_password(user_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return bool(row and row["password_hash"])


def verify_user_password(user_id: int, password: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return bool(row and row["password_hash"] and _verify_password(password, row["password_hash"]))


def _create_account_token(user_id: int, purpose: str, ttl_minutes: int) -> str:
    if purpose not in {"verify_email", "reset_password"}:
        raise ValueError("Unsupported account token purpose.")
    raw = secrets.token_urlsafe(40)
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        conn.execute(
            "DELETE FROM account_tokens WHERE user_id = ? AND purpose = ?",
            (user_id, purpose),
        )
        conn.execute(
            """
            INSERT INTO account_tokens(
                token_hash, user_id, purpose, expires_at, used_at, created_at
            ) VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (
                _token_hash(raw),
                user_id,
                purpose,
                (now + timedelta(minutes=ttl_minutes)).isoformat(),
                now.isoformat(),
            ),
        )
    return raw


def create_email_verification_token(user_id: int) -> tuple[str, str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT email, email_verified FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        raise AuthError("Account not found.")
    if row["email_verified"]:
        raise AuthError("Email is already verified.")
    return _create_account_token(user_id, "verify_email", 24 * 60), row["email"]


def verify_email_token(token: str) -> dict:
    digest = _token_hash((token or "")[:256])
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT a.user_id
            FROM account_tokens a
            WHERE a.token_hash = ? AND a.purpose = 'verify_email'
              AND a.used_at IS NULL AND a.expires_at > ?
            """,
            (digest, now),
        ).fetchone()
        if not row:
            raise AuthError("Verification link is invalid or expired.")
        conn.execute(
            "UPDATE account_tokens SET used_at = ? WHERE token_hash = ?",
            (now, digest),
        )
        conn.execute(
            "UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
            (now, row["user_id"]),
        )
        _bootstrap_admin(conn)
        user = conn.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()
        return _public_user(user)


def create_password_reset_token(email: str) -> Optional[tuple[str, str]]:
    normalized = (email or "").strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, email FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()
    if not row:
        return None
    return _create_account_token(row["id"], "reset_password", 30), row["email"]


def reset_password_with_token(token: str, new_password: str) -> None:
    if len(new_password) < 10 or len(new_password.encode("utf-8")) > 256:
        raise AuthError("New password must be 10 to 256 bytes.")
    digest = _token_hash((token or "")[:256])
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT user_id FROM account_tokens
            WHERE token_hash = ? AND purpose = 'reset_password'
              AND used_at IS NULL AND expires_at > ?
            """,
            (digest, now),
        ).fetchone()
        if not row:
            raise AuthError("Password reset link is invalid or expired.")
        user = conn.execute(
            "SELECT google_id FROM users WHERE id = ?",
            (row["user_id"],),
        ).fetchone()
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, auth_provider = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                _hash_password(new_password),
                "email+google" if user and user["google_id"] else "email",
                now,
                row["user_id"],
            ),
        )
        conn.execute(
            "UPDATE account_tokens SET used_at = ? WHERE token_hash = ?",
            (now, digest),
        )
        conn.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ?", (now, row["user_id"]))


def delete_account(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ==========================================
# SESSIONS
# ==========================================
def purge_expired_sessions(*, conn: sqlite3.Connection | None = None) -> int:
    own_connection = conn is None
    if own_connection:
        ctx = _connect()
        conn = ctx.__enter__()
    assert conn is not None
    try:
        cur = conn.execute(
            "DELETE FROM sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL",
            (_utc_now(),),
        )
        return int(cur.rowcount or 0)
    finally:
        if own_connection:
            ctx.__exit__(None, None, None)


def create_session(user_id: int, client_fingerprint: str = "") -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                token, user_id, created_at, expires_at, last_seen_at,
                revoked_at, client_fingerprint
            ) VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                _token_hash(token),
                user_id,
                now.isoformat(),
                (now + timedelta(days=SESSION_TTL_DAYS)).isoformat(),
                now.isoformat(),
                client_fingerprint[:128],
            ),
        )
        # Cap active sessions per account to limit forgotten devices.
        rows = conn.execute(
            """
            SELECT token FROM sessions
            WHERE user_id = ? AND revoked_at IS NULL
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        for old in rows[10:]:
            conn.execute("DELETE FROM sessions WHERE token = ?", (old["token"],))
    return token


def get_user_by_session(token: Optional[str]) -> Optional[dict]:
    if not token or len(token) > 256:
        return None
    now = _utc_now()
    digest = _token_hash(token)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.*, s.last_seen_at AS session_last_seen
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ? AND s.revoked_at IS NULL
            """,
            (digest, now),
        ).fetchone()
        if not row:
            return None
        last_seen = row["session_last_seen"]
        try:
            due = (
                not last_seen
                or datetime.fromisoformat(last_seen) + timedelta(seconds=SESSION_TOUCH_SECONDS)
                < datetime.now(timezone.utc)
            )
        except ValueError:
            due = True
        if due:
            conn.execute("UPDATE sessions SET last_seen_at = ? WHERE token = ?", (now, digest))
        return _public_user(row)


def delete_session(token: Optional[str]) -> None:
    if not token:
        return
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE token = ?",
            (_utc_now(), _token_hash(token)),
        )


def delete_all_sessions(user_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE user_id = ?",
            (_utc_now(), user_id),
        )


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
        "email_verified": bool(profile.get("email_verified")),
    }
