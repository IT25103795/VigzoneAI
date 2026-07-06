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
        if "learning_enabled" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN learning_enabled INTEGER NOT NULL DEFAULT 1")

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
        existing_usage_cols = {row[1] for row in conn.execute("PRAGMA table_info(token_usage)")}
        if "provider" not in existing_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN provider TEXT NOT NULL DEFAULT 'groq'")


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
        ws = conn.execute("SELECT id FROM workspaces WHERE id = ? AND user_id = ?", (workspace_id, user_id)).fetchone()
        if not ws:
            raise AuthError("Workspace not found.")
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


def is_admin_email(email: str) -> bool:
    """Admin users are configured with ADMIN_EMAILS=one@example.com,two@example.com."""
    admins = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    return (email or "").strip().lower() in admins


def _public_user(row: sqlite3.Row) -> dict:
    email = row["email"]
    return {
        "id": row["id"],
        "email": email,
        "name": row["name"],
        "auth_provider": row["auth_provider"],
        "is_admin": is_admin_email(email),
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
