#!/usr/bin/env python
"""Quick test of stream_manager module."""
from stream_manager import create_stream_id, register_stream, cancel_stream, is_cancelled, unregister_stream

def test_stream_manager():
    print("Testing stream_manager...")

    # Test 1: Create a stream ID
    sid = create_stream_id()
    print(f"✓ Created stream ID: {sid}")

    # Test 2: Register and check initial state
    register_stream(sid)
    assert not is_cancelled(sid), "Stream should not be cancelled initially"
    print("✓ Stream registered and not cancelled")

    # Test 3: Cancel the stream
    result = cancel_stream(sid)
    assert result == True, "Cancel should return True"
    assert is_cancelled(sid), "Stream should be cancelled"
    print("✓ Stream cancelled successfully")

    # Test 4: Unregister
    unregister_stream(sid)
    assert not is_cancelled(sid), "Stream should not be found after unregister"
    print("✓ Stream unregistered")

    # Test 5: Try to cancel non-existent stream
    result = cancel_stream("non-existent")
    assert result == False, "Cancelling non-existent stream should return False"
    print("✓ Cannot cancel non-existent stream")

    print("\n✅ All tests passed!")

if __name__ == '__main__':
    test_stream_manager()

