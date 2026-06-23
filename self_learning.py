"""
Vigzone AI - Self Learning / Retrieval-Augmented Memory
=========================================================
Persistent knowledge base of past user/assistant exchanges.
Uses SQLite FTS5 for fast full-text search instead of scanning a JSON file,
giving dramatically better recall and scalability.

Accuracy improvements over v2:
  - FTS5 full-text search replaces slow linear SequenceMatcher scan.
  - Entries ranked by BM25 relevance (SQLite built-in) — best matches first.
  - Stopword-aware tokenisation already handled by FTS5.
  - Cache still used for read-heavy paths; invalidated on any write.
  - Degeneration detection unchanged (was already solid).
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_DIR  = os.path.join(os.path.dirname(__file__), "data")
KB_DB   = os.path.join(DB_DIR, "knowledge.db")   # new FTS database
KB_JSON = os.path.join(DB_DIR, "knowledge.json")  # legacy, migrated on first run

MAX_ENTRIES             = 5000   # hard cap; oldest entries pruned beyond this
MAX_ASSISTANT_CHARS     = 4000
MAX_MEMORY_ASSISTANT_CHARS = 500

# ── Degeneration markers (unchanged from v2) ──────────────────────────────────
_DEGENERATION_MARKERS = (
    "by the way; i am still learning",
    "by the way; i provide helpful context",
    "by the way; i don't change my underlying model",
    "by the way; i adapt",
    "i do this by reusing past examples",
    "i'm here; i'm here",
    "you are; you are",
    "## step 1:",
    "step 1:\nto verify",
    "_(stopped early",
    "_(cut short",
)


def trim_degeneration_tail(text: str) -> str:
    if not text:
        return ""
    lower = text.lower()
    cut   = len(text)
    for marker in _DEGENERATION_MARKERS:
        idx = lower.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    for needle in ("by the way;", "i'm here;"):
        idx = lower.find(needle)
        if idx != -1:
            if needle == "i'm here;" and lower.count("i'm here") < 2:
                continue
            cut = min(cut, idx)
    return text[:cut].rstrip()


_trim_degeneration_tail = trim_degeneration_tail


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _has_repeated_line_blocks(lines: List[str], max_repeat: int = 5) -> bool:
    if len(lines) < max_repeat * 2:
        return False
    for n in range(1, min(4, len(lines) // max_repeat + 1)):
        block = lines[-n:]
        count, i = 1, len(lines) - n
        while i - n >= 0 and lines[i - n: i] == block:
            count += 1
            i    -= n
        if count >= max_repeat:
            return True
    return False


def _has_repeated_segments(text: str, separator: str, max_repeat: int = 5) -> bool:
    parts = [p.strip() for p in text.split(separator) if p.strip()]
    if len(parts) < max_repeat * 2:
        return False
    for n in (1, 2):
        block = parts[-n:]
        count, i = 1, len(parts) - n
        while i - n >= 0 and parts[i - n: i] == block:
            count += 1
            i    -= n
        if count >= max_repeat:
            return True
    return False


def is_degenerate_text(text: str, max_repeat: int = 6, tail_chars: int = 2500) -> bool:
    if not text:
        return False
    lower = text.lower()
    if any(m in lower for m in _DEGENERATION_MARKERS):
        return True
    tail      = text.rstrip()[-tail_chars:]
    norm_tail = _normalize_ws(tail)
    for needle, limit in (("step 1:", 4), ("to verify", 6), ("i'm here", 5), ("that's", 12)):
        if norm_tail.count(needle) >= limit:
            return True
    lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    if _has_repeated_line_blocks(lines, max_repeat=max(4, max_repeat - 1)):
        return True
    if _has_repeated_segments(tail, ";", max_repeat=max(4, max_repeat - 1)):
        return True
    words = tail.split()
    if len(words) < max_repeat * 2:
        return False
    for n in (1, 2, 3, 4):
        phrase = tuple(w.lower() for w in words[-n:])
        if not any(phrase):
            continue
        count, i = 1, len(words) - n
        while i - n >= 0 and tuple(w.lower() for w in words[i - n: i]) == phrase:
            count += 1
            i     -= n
        if count >= max_repeat:
            return True
    if len(words) >= 60 and len(set(w.lower() for w in words)) / len(words) < 0.2:
        return True
    return False


def sanitize_assistant_for_memory(text: str) -> str:
    cleaned = trim_degeneration_tail(text).strip()
    if not cleaned or is_degenerate_text(cleaned):
        return ""
    return cleaned[:MAX_MEMORY_ASSISTANT_CHARS]


# ── SQLite FTS5 knowledge base ────────────────────────────────────────────────
@contextmanager
def _db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(KB_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema() -> None:
    with _db() as conn:
        # Main table holds canonical data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_q    TEXT    NOT NULL,
                assistant TEXT    NOT NULL,
                feedback  TEXT,
                ts        INTEGER NOT NULL
            )
        """)
        # FTS5 virtual table for fast full-text search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS interactions_fts
            USING fts5(user_q, content='interactions', content_rowid='id')
        """)
        # Triggers keep FTS in sync with the main table
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS interactions_ai
            AFTER INSERT ON interactions BEGIN
                INSERT INTO interactions_fts(rowid, user_q) VALUES (new.id, new.user_q);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS interactions_ad
            AFTER DELETE ON interactions BEGIN
                INSERT INTO interactions_fts(interactions_fts, rowid, user_q)
                VALUES ('delete', old.id, old.user_q);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS interactions_au
            AFTER UPDATE ON interactions BEGIN
                INSERT INTO interactions_fts(interactions_fts, rowid, user_q)
                VALUES ('delete', old.id, old.user_q);
                INSERT INTO interactions_fts(rowid, user_q) VALUES (new.id, new.user_q);
            END
        """)


def _migrate_json_if_present() -> None:
    """One-time migration of legacy knowledge.json into the SQLite KB."""
    if not os.path.exists(KB_JSON):
        return
    try:
        import json
        with open(KB_JSON, "r", encoding="utf-8") as fh:
            entries = json.load(fh)
        if not isinstance(entries, list) or not entries:
            return
        migrated = 0
        for e in entries:
            u = (e.get("user") or "").strip()
            a = sanitize_assistant_for_memory(e.get("assistant") or "")
            if u and a:
                add_interaction(u, a, e.get("feedback"))
                migrated += 1
        logger.info("Migrated %d entries from knowledge.json → knowledge.db", migrated)
        os.rename(KB_JSON, KB_JSON + ".migrated")
    except Exception as exc:
        logger.warning("knowledge.json migration failed: %s", exc)


# Initialise on import
_ensure_schema()
_migrate_json_if_present()


def add_interaction(user_text: str, assistant_text: str, feedback: Optional[str] = None) -> None:
    if not isinstance(user_text, str) or not isinstance(assistant_text, str):
        return
    if not user_text.strip() or not assistant_text.strip():
        return
    safe_assistant = sanitize_assistant_for_memory(assistant_text)
    if not safe_assistant:
        return
    with _db() as conn:
        conn.execute(
            "INSERT INTO interactions (user_q, assistant, feedback, ts) VALUES (?, ?, ?, ?)",
            (user_text.strip(), safe_assistant[:MAX_ASSISTANT_CHARS], feedback, int(time.time())),
        )
        # Prune oldest entries beyond cap
        count = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        if count > MAX_ENTRIES:
            conn.execute(
                "DELETE FROM interactions WHERE id IN "
                "(SELECT id FROM interactions ORDER BY ts ASC LIMIT ?)",
                (count - MAX_ENTRIES,),
            )


def find_similar(query: str, top_k: int = 3) -> List[Dict]:
    """
    Return up to top_k KB entries most relevant to query.
    Uses SQLite FTS5 BM25 ranking — far more accurate than SequenceMatcher.
    """
    if not query or not query.strip():
        return []
    # Sanitise query for FTS5 (escape special chars)
    fts_query = re.sub(r'[^\w\s]', ' ', query).strip()
    if not fts_query:
        return []
    try:
        with _db() as conn:
            rows = conn.execute(
                """
                SELECT i.id, i.user_q, i.assistant, i.feedback, i.ts,
                       bm25(interactions_fts) AS rank
                FROM interactions_fts f
                JOIN interactions i ON i.id = f.rowid
                WHERE interactions_fts MATCH ?
                ORDER BY rank   -- bm25 returns negative; lower = better match
                LIMIT ?
                """,
                (fts_query, top_k),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        # FTS query syntax error — fall back gracefully
        return []


def get_context_for_prompt(query: str, max_chars: int = 1500, top_k: int = 3) -> str:
    hits = find_similar(query, top_k=top_k)
    if not hits:
        return ""
    parts: List[str] = []
    for h in hits:
        u = (h.get("user_q") or "").strip()
        a = sanitize_assistant_for_memory(h.get("assistant") or "")
        if u and a:
            parts.append(f"Q: {u}\nA: {a}\n")
    if not parts:
        return ""
    context = "\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars]
    header = (
        "The assistant has access to brief notes from past similar conversations. "
        "Use them only as background — never quote or echo them verbatim, and do not "
        "repeat their wording in your reply.\n\n"
    )
    return header + context


def prune_kb() -> int:
    """Remove degenerate entries. Returns count removed."""
    removed = 0
    try:
        with _db() as conn:
            rows = conn.execute("SELECT id, assistant FROM interactions").fetchall()
            for row in rows:
                safe = sanitize_assistant_for_memory(row["assistant"])
                if not safe:
                    conn.execute("DELETE FROM interactions WHERE id = ?", (row["id"],))
                    removed += 1
    except Exception as exc:
        logger.warning("prune_kb error: %s", exc)
    return removed
