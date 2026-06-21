"""
Stream manager for handling pauseable/cancellable AI responses.

Tracks active streaming requests and allows cancellation and pausing.
"""
import uuid
from typing import Dict

# Global registry of active streams (stream_id -> {"cancelled": bool, "paused": bool})
_active_streams: Dict[str, Dict] = {}


def create_stream_id() -> str:
    """Generate a unique stream ID."""
    return str(uuid.uuid4())


def register_stream(stream_id: str) -> None:
    """Register a new active stream."""
    _active_streams[stream_id] = {"cancelled": False, "paused": False}


def cancel_stream(stream_id: str) -> bool:
    """Mark a stream as cancelled. Returns True if the stream was found and cancelled."""
    if stream_id in _active_streams:
        _active_streams[stream_id]["cancelled"] = True
        return True
    return False


def is_cancelled(stream_id: str) -> bool:
    """Check if a stream has been cancelled."""
    return _active_streams.get(stream_id, {}).get("cancelled", False)


def pause_stream(stream_id: str) -> bool:
    """Mark a stream as paused. Returns True if the stream was found and paused."""
    if stream_id in _active_streams:
        _active_streams[stream_id]["paused"] = True
        return True
    return False


def resume_stream(stream_id: str) -> bool:
    """Mark a stream as resumed. Returns True if the stream was found and resumed."""
    if stream_id in _active_streams:
        _active_streams[stream_id]["paused"] = False
        return True
    return False


def is_paused(stream_id: str) -> bool:
    """Check if a stream has been paused."""
    return _active_streams.get(stream_id, {}).get("paused", False)


def unregister_stream(stream_id: str) -> None:
    """Remove a stream from the registry (call when done)."""
    _active_streams.pop(stream_id, None)