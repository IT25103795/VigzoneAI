#!/usr/bin/env python
"""Quick test of stream_manager module."""
from stream_manager import create_stream_id, register_stream, cancel_stream, is_cancelled, unregister_stream

def test_stream_manager():
    print("Testing stream_manager...")

    # Test 1: Create a stream ID
    sid = create_stream_id()
    print(f"[OK] Created stream ID: {sid}")

    # Test 2: Register and check initial state
    register_stream(sid, 1)
    assert not is_cancelled(sid), "Stream should not be cancelled initially"
    print("[OK] Stream registered and not cancelled")

    # Test 3: Cancel the stream
    result = cancel_stream(sid, 1)
    assert result == True, "Cancel should return True"
    assert is_cancelled(sid), "Stream should be cancelled"
    print("[OK] Stream cancelled successfully")

    # Test 4: Unregister
    unregister_stream(sid)
    assert not is_cancelled(sid), "Stream should not be found after unregister"
    print("[OK] Stream unregistered")

    # Test 5: Try to cancel non-existent stream
    result = cancel_stream("non-existent", 1)
    assert result == False, "Cancelling non-existent stream should return False"
    print("[OK] Cannot cancel non-existent stream")

    print("\n[SUCCESS] All tests passed!")

if __name__ == '__main__':
    test_stream_manager()

