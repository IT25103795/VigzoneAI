"""
Simple local self-learning module.

This provides a tiny persistent knowledge base (JSON file) of past
user/assistant exchanges and a lightweight fuzzy matcher to retrieve
relevant memories and fold them into the model prompt. It's intentionally
small and dependency-free so it works in the existing project without
adding new packages.

Notes:
- This is not online fine-tuning; it simply records interactions and
  provides relevant examples to the LLM as extra context (retrieval
  augmentation). It's private, stored locally under `data/knowledge.json`.
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

# Cap how much of a single reply we persist — an unbounded value means one
# runaway generation could dominate every future "memory" lookup.
MAX_ASSISTANT_CHARS = 4000
# Memory context only needs the useful opening of a past reply — long tails
# are where runaway repetition usually starts.
MAX_MEMORY_ASSISTANT_CHARS = 500

# Phrases that mark the start of a known repetition / echo loop. The model
# often begins parroting system-prompt or memory text before falling into
# "Step 1: To verify" / "I'm here" loops.
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
    """Return only the clean prefix before a known loop/echo marker."""
    if not text:
        return ""
    lower = text.lower()
    cut = len(text)
    for marker in _DEGENERATION_MARKERS:
        idx = lower.find(marker)
        if idx != -1:
            cut = min(cut, idx)

    # Semicolon-chained "By the way;" blocks echo system/memory text. Natural
    # asides use a comma ("By the way, I think...") and are left alone.
    semi_idx = lower.find("by the way;")
    if semi_idx != -1:
        cut = min(cut, semi_idx)

    # Semicolon-chained "I'm here;" fragments are the loop, not "I'm here to help".
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
    """Heuristic check for a degenerate/looping LLM output.

    LLMs occasionally fall into a failure mode where they get stuck
    repeating the same short word or phrase over and over (e.g. "Global \\n\\n
    Global \\n\\n Global \\n\\n ..." sometimes trailing off into bare blank
    lines). This catches that pattern so callers can avoid both (a) showing
    it to the user forever and (b) saving it into the knowledge base, where
    it would otherwise get retrieved as a "memory" example for similar
    future questions and keep reproducing the same loop.
    """
    if not text:
        return False

    lower = text.lower()
    if any(marker in lower for marker in _DEGENERATION_MARKERS):
        return True

    # Strip trailing whitespace-only padding first — a runaway reply often
    # trails off into nothing but blank lines, which would otherwise eat up
    # the whole tail window without showing us any of the actual repeated
    # words just before it.
    stripped = text.rstrip()
    tail = stripped[-tail_chars:]
    norm_tail = _normalize_ws(tail)

    # High-frequency short phrases common in Vigzone's echo loops.
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

    # Same short phrase (1-4 words) repeating back-to-back many times.
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

    # Very low lexical diversity — lots of words, few distinct ones.
    if len(words) >= 60:
        unique_ratio = len(set(w.lower() for w in words)) / len(words)
        if unique_ratio < 0.2:
            return True

    return False


def sanitize_assistant_for_memory(text: str) -> str:
    """Keep only a safe prefix of an assistant reply for storage/retrieval."""
    cleaned = trim_degeneration_tail(text).strip()
    if not cleaned:
        return ""
    if is_degenerate_text(cleaned):
        return ""
    return cleaned[:MAX_MEMORY_ASSISTANT_CHARS]


def _ensure_kb() -> None:
    os.makedirs(KB_DIR, exist_ok=True)
    if not os.path.exists(KB_PATH):
        with open(KB_PATH, "w", encoding="utf-8") as fh:
            json.dump([], fh)


def _load_kb() -> List[Dict]:
    _ensure_kb()
    try:
        with open(KB_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def _save_kb(kb: List[Dict]) -> None:
    _ensure_kb()
    tmp = KB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(kb, fh, ensure_ascii=False, indent=2)
    try:
        os.replace(tmp, KB_PATH)
    except Exception:
        # best-effort fallback
        with open(KB_PATH, "w", encoding="utf-8") as fh:
            json.dump(kb, fh, ensure_ascii=False, indent=2)


def prune_kb() -> int:
    """Remove or trim corrupted KB entries. Returns how many entries were removed."""
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
    """Append a new interaction to the persistent knowledge base.

    Keeps a simple timestamp and optional free-form feedback.
    """
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
    # keep KB bounded (avoid unbounded growth)
    MAX_ENTRIES = 2000
    if len(kb) > MAX_ENTRIES:
        kb = kb[-MAX_ENTRIES:]
    _save_kb(kb)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_similar(query: str, top_k: int = 3) -> List[Dict]:
    """Return up to top_k KB entries similar to query (sorted by score).

    Similarity is a simple sequence matcher on the user text. This is
    intentionally lightweight; replace with embeddings later if desired.
    """
    if not query:
        return []
    kb = _load_kb()
    scored = []
    for e in kb:
        assistant = sanitize_assistant_for_memory(e.get("assistant", ""))
        if not assistant:
            continue
        score = _similarity(query, e.get("user", ""))
        if score > 0.2:
            scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [dict(e, _score=s) for s, e in scored[:top_k]]


def get_context_for_prompt(query: str, max_chars: int = 1500, top_k: int = 3) -> str:
    """Build a short textual 'long-term memory' block to include in the
    system prompt. Returns an empty string when no useful memories are found.
    """
    hits = find_similar(query, top_k=top_k)
    if not hits:
        return ""
    parts: List[str] = []
    for h in hits:
        user = h.get("user", "").strip()
        assistant = sanitize_assistant_for_memory(h.get("assistant", ""))
        if not user or not assistant:
            continue
        part = f"Q: {user}\nA: {assistant}\n"
        parts.append(part)
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

