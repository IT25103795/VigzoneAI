"""
Stream manager — pauseable / cancellable AI response streams.

Upgrade from v2: pause/resume now uses asyncio.Event instead of
polling with asyncio.sleep(0.1). This gives zero-latency resume
(no 100 ms delay) and zero CPU spin while paused.
"""
import asyncio
import uuid
from typing import Dict


class _StreamState:
    __slots__ = ("cancelled", "_pause_event")

    def __init__(self) -> None:
        self.cancelled   = False
        # Event starts set (not paused). Cleared = paused, set = running.
        self._pause_event = asyncio.Event()
        self._pause_event.set()

    def pause(self)  -> None: self._pause_event.clear()
    def resume(self) -> None: self._pause_event.set()
    def is_paused(self) -> bool: return not self._pause_event.is_set()

    async def wait_if_paused(self) -> None:
        """Await until the stream is running (no-op if already running)."""
        await self._pause_event.wait()


_active_streams: Dict[str, _StreamState] = {}


def create_stream_id() -> str:
    return str(uuid.uuid4())


def register_stream(stream_id: str) -> None:
    _active_streams[stream_id] = _StreamState()


def cancel_stream(stream_id: str) -> bool:
    s = _active_streams.get(stream_id)
    if s:
        s.cancelled = True
        s.resume()   # unblock any waiting coroutine so it can exit
        return True
    return False


def is_cancelled(stream_id: str) -> bool:
    s = _active_streams.get(stream_id)
    return s.cancelled if s else False


def pause_stream(stream_id: str) -> bool:
    s = _active_streams.get(stream_id)
    if s and not s.cancelled:
        s.pause()
        return True
    return False


def resume_stream(stream_id: str) -> bool:
    s = _active_streams.get(stream_id)
    if s:
        s.resume()
        return True
    return False


def is_paused(stream_id: str) -> bool:
    s = _active_streams.get(stream_id)
    return s.is_paused() if s else False


async def wait_if_paused(stream_id: str) -> None:
    """Used by vigzone_ai.py — awaits until resume() is called."""
    s = _active_streams.get(stream_id)
    if s:
        await s.wait_if_paused()


def unregister_stream(stream_id: str) -> None:
    _active_streams.pop(stream_id, None)
