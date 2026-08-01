"""Response-quality guards used by the Vigzone chat engine.

Older Vigzone builds placed every user's conversations into one global
``knowledge.db`` and injected matches into later chats.  That design leaked
context across accounts and has deliberately been removed.  Private memory now
lives in ``auth.learning_memories`` and is only populated by explicit
Learning Center actions from the owning user.

The module name remains for import compatibility, but it contains no persistence
or automatic learning.
"""

from __future__ import annotations

import re
from typing import List

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
    lowered = text.lower()
    cut = len(text)
    for marker in _DEGENERATION_MARKERS:
        index = lowered.find(marker)
        if index != -1:
            cut = min(cut, index)
    for needle in ("by the way;", "i'm here;"):
        index = lowered.find(needle)
        if index == -1:
            continue
        if needle == "i'm here;" and lowered.count("i'm here") < 2:
            continue
        cut = min(cut, index)
    return text[:cut].rstrip()


_trim_degeneration_tail = trim_degeneration_tail


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _has_repeated_line_blocks(lines: List[str], max_repeat: int = 5) -> bool:
    if len(lines) < max_repeat * 2:
        return False
    for size in range(1, min(4, len(lines) // max_repeat + 1)):
        block = lines[-size:]
        count = 1
        cursor = len(lines) - size
        while cursor - size >= 0 and lines[cursor - size:cursor] == block:
            count += 1
            cursor -= size
        if count >= max_repeat:
            return True
    return False


def _has_repeated_segments(text: str, separator: str, max_repeat: int = 5) -> bool:
    parts = [part.strip() for part in text.split(separator) if part.strip()]
    if len(parts) < max_repeat * 2:
        return False
    for size in (1, 2):
        block = parts[-size:]
        count = 1
        cursor = len(parts) - size
        while cursor - size >= 0 and parts[cursor - size:cursor] == block:
            count += 1
            cursor -= size
        if count >= max_repeat:
            return True
    return False


def is_degenerate_text(text: str, max_repeat: int = 6, tail_chars: int = 2500) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _DEGENERATION_MARKERS):
        return True
    tail = text.rstrip()[-tail_chars:]
    normalized = _normalize_ws(tail)
    for needle, limit in (
        ("step 1:", 4),
        ("to verify", 6),
        ("i'm here", 5),
        ("that's", 12),
    ):
        if normalized.count(needle) >= limit:
            return True
    lines = [line.strip() for line in tail.splitlines() if line.strip()]
    if _has_repeated_line_blocks(lines, max_repeat=max(4, max_repeat - 1)):
        return True
    if _has_repeated_segments(tail, ";", max_repeat=max(4, max_repeat - 1)):
        return True
    words = tail.split()
    if len(words) < max_repeat * 2:
        return False
    for size in (1, 2, 3, 4):
        phrase = tuple(word.lower() for word in words[-size:])
        count = 1
        cursor = len(words) - size
        while (
            cursor - size >= 0
            and tuple(word.lower() for word in words[cursor - size:cursor]) == phrase
        ):
            count += 1
            cursor -= size
        if count >= max_repeat:
            return True
    return len(words) >= 60 and len({word.lower() for word in words}) / len(words) < 0.2


def sanitize_assistant_for_memory(text: str) -> str:
    """Sanitize text for explicit, user-approved memory creation."""

    cleaned = trim_degeneration_tail(text).strip()
    if not cleaned or is_degenerate_text(cleaned):
        return ""
    return cleaned[:MAX_MEMORY_ASSISTANT_CHARS]
