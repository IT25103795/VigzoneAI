"""
Simple local self-learning module.

Provides a tiny persistent knowledge base (JSON file) of past user/assistant
exchanges and a lightweight fuzzy matcher to retrieve relevant memories and
fold them into the model prompt. Intentionally small and dependency-free.

Performance notes (v2):
- The KB is loaded once into an in-process cache and refreshed only when the
  file changes on disk (mtime check). This means repeated calls within a
  session don't pay repeated JSON parse + file I/O costs.
- find_similar() uses fast word-intersection scoring as a pre-filter before
  falling back to SequenceMatcher, skipping most entries entirely.
- is_degenerate_text() now only runs on the *tail* of the stream (every 40
  tokens instead of every token) to avoid mid-stream overhead.
"""
from __future__ import annotations

import json
import os
import re
import time
from difflib import SequenceMatcher
from typing import List, Dict, Optional

KB_DIR = os.path.join(os.path.dirname(__file__), "data")
KB_PATH = os.path.join(KB_DIR, "knowledge.json")

MAX_ASSISTANT_CHARS = 4000
MAX_MEMORY_ASSISTANT_CHARS = 500

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
    cut = len(text)
    for marker in _DEGENERATION_MARKERS:
        idx = lower.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    semi_idx = lower.find("by the way;")
    if semi_idx != -1:
        cut = min(cut, semi_idx)
    semi_here = lower.find("i'm here;")
    if semi_here != -1 and lower.count("i'm here") >= 2:
        cut = min(cut, semi_here)
    return text[:cut].rstrip()


_trim_degeneration_tail = trim_degeneration_tail


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _has_repeated_line_blocks(lines: List[str], max_repeat: int = 5) -> bool:
    if len(lines) < max_repeat * 2:
        return False
    for n in range(1, min(4, len(lines) // max_repeat + 1)):
        block = lines[-n:]
        count = 1
        i = len(lines) - n
        while i - n >= 0 and lines[i - n : i] == block:
            count += 1
            i -= n
        if count >= max_repeat:
            return True
    return False


def _has_repeated_segments(text: str, separator: str, max_repeat: int = 5) -> bool:
    parts = [p.strip() for p in text.split(separator) if p.strip()]
    if len(parts) < max_repeat * 2:
        return False
    for n in (1, 2):
        block = parts[-n:]
        count = 1
        i = len(parts) - n
        while i - n >= 0 and parts[i - n : i] == block:
            count += 1
            i -= n
        if count >= max_repeat:
            return True
    return False


def is_degenerate_text(text: str, max_repeat: int = 6, tail_chars: int = 2500) -> bool:
    if not text:
        return False
    lower = text.lower()
    if any(marker in lower for marker in _DEGENERATION_MARKERS):
        return True
    stripped = text.rstrip()
    tail = stripped[-tail_chars:]
    norm_tail = _normalize_ws(tail)
    for needle, limit in (
        ("step 1:", 4),
        ("to verify", 6),
        ("i'm here", 5),
        ("that's", 12),
    ):
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
        count = 1
        i = len(words) - n
        while i - n >= 0 and tuple(w.lower() for w in words[i - n : i]) == phrase:
            count += 1
            i -= n
        if count >= max_repeat:
            return True
    if len(words) >= 60:
        unique_ratio = len(set(w.lower() for w in words)) / len(words)
        if unique_ratio < 0.2:
            return True
    return False


def sanitize_assistant_for_memory(text: str) -> str:
    cleaned = trim_degeneration_tail(text).strip()
    if not cleaned:
        return ""
    if is_degenerate_text(cleaned):
        return ""
    return cleaned[:MAX_MEMORY_ASSISTANT_CHARS]


# ── In-process KB cache ─────────────────────────────────────────────────────
# Avoids re-reading and re-parsing knowledge.json on every single message.
# The cache is invalidated only when the file's mtime changes on disk.
_kb_cache: List[Dict] = []
_kb_mtime: float = 0.0


def _ensure_kb() -> None:
    os.makedirs(KB_DIR, exist_ok=True)
    if not os.path.exists(KB_PATH):
        with open(KB_PATH, "w", encoding="utf-8") as fh:
            json.dump([], fh)


def _load_kb() -> List[Dict]:
    global _kb_cache, _kb_mtime
    _ensure_kb()
    try:
        mtime = os.path.getmtime(KB_PATH)
        if mtime != _kb_mtime:
            with open(KB_PATH, "r", encoding="utf-8") as fh:
                _kb_cache = json.load(fh)
            _kb_mtime = mtime
    except Exception:
        _kb_cache = []
    return _kb_cache


def _invalidate_cache() -> None:
    global _kb_mtime
    _kb_mtime = 0.0


def _save_kb(kb: List[Dict]) -> None:
    _ensure_kb()
    tmp = KB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(kb, fh, ensure_ascii=False, indent=2)
    try:
        os.replace(tmp, KB_PATH)
    except Exception:
        with open(KB_PATH, "w", encoding="utf-8") as fh:
            json.dump(kb, fh, ensure_ascii=False, indent=2)
    _invalidate_cache()


def prune_kb() -> int:
    kb = _load_kb()
    kept = []
    removed = 0
    changed = False
    for entry in kb:
        assistant = entry.get("assistant", "")
        safe = sanitize_assistant_for_memory(assistant)
        if not safe:
            removed += 1
            changed = True
            continue
        if safe != assistant:
            entry = dict(entry)
            entry["assistant"] = safe
            changed = True
        kept.append(entry)
    if changed:
        _save_kb(kept)
    return removed


def add_interaction(user_text: str, assistant_text: str, feedback: Optional[str] = None) -> None:
    if not isinstance(user_text, str) or not isinstance(assistant_text, str):
        return
    if not user_text.strip() or not assistant_text.strip():
        return
    safe_assistant = sanitize_assistant_for_memory(assistant_text)
    if not safe_assistant:
        return
    entry = {
        "user": user_text,
        "assistant": safe_assistant[:MAX_ASSISTANT_CHARS],
        "feedback": feedback,
        "ts": int(time.time()),
    }
    kb = _load_kb()
    kb.append(entry)
    MAX_ENTRIES = 2000
    if len(kb) > MAX_ENTRIES:
        kb = kb[-MAX_ENTRIES:]
    _save_kb(kb)


# Pre-compiled stopwords to ignore during word-intersection scoring.
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would could should may might shall can i you he she it we they "
    "me him her us them my your his her its our their this that these those "
    "and but or nor so yet for of in on at to from with by about into ".split()
)


def _word_set(text: str) -> frozenset:
    """Return meaningful lowercase words from text (stopwords excluded)."""
    return frozenset(
        w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOPWORDS
    )


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_similar(query: str, top_k: int = 3) -> List[Dict]:
    """Return up to top_k KB entries most similar to query.

    Uses fast word-intersection as a pre-filter so SequenceMatcher only runs
    on the small subset of entries that share at least one meaningful word
    with the query — skips the expensive comparison for unrelated entries.
    """
    if not query:
        return []
    kb = _load_kb()
    if not kb:
        return []

    query_words = _word_set(query)
    scored = []
    for e in kb:
        user_text = e.get("user", "")
        # Fast pre-filter: skip entries with no word overlap at all.
        if query_words and not query_words.intersection(_word_set(user_text)):
            continue
        assistant = sanitize_assistant_for_memory(e.get("assistant", ""))
        if not assistant:
            continue
        score = _similarity(query, user_text)
        if score > 0.2:
            scored.append((score, e))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [dict(e, _score=s) for s, e in scored[:top_k]]


def get_context_for_prompt(query: str, max_chars: int = 1500, top_k: int = 3) -> str:
    hits = find_similar(query, top_k=top_k)
    if not hits:
        return ""
    parts: List[str] = []
    for h in hits:
        user = h.get("user", "").strip()
        assistant = sanitize_assistant_for_memory(h.get("assistant", ""))
        if not user or not assistant:
            continue
        parts.append(f"Q: {user}\nA: {assistant}\n")
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
