#!/usr/bin/env python
"""Verify pause feature integration."""
import sys

def test_imports():
    """Test that all modules import cleanly."""
    try:
        print("Testing imports...")
        import stream_manager
        print("  ✓ stream_manager imported")

        import app
        print("  ✓ app imported")

        print("\n✅ All imports successful!")
        return True
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        return False

def test_stream_manager_api():
    """Test stream manager API."""
    try:
        print("\nTesting stream manager API...")
        from stream_manager import (
            create_stream_id, register_stream, cancel_stream,
            is_cancelled, unregister_stream, pause_stream, resume_stream, is_paused
        )

        # Create and test a stream
        sid = create_stream_id()
        register_stream(sid)
        assert not is_cancelled(sid), "Stream should not be cancelled initially"
        assert not is_paused(sid), "Stream should not be paused initially"
        
        pause_stream(sid)
        assert is_paused(sid), "Stream should be paused after pause_stream"
        
        resume_stream(sid)
        assert not is_paused(sid), "Stream should not be paused after resume_stream"

        cancel_stream(sid)
        assert is_cancelled(sid), "Stream should be cancelled after cancel_stream"
        
        unregister_stream(sid)

        print("  ✓ Stream manager API works correctly")
        return True
    except Exception as e:
        print(f"  ❌ Stream manager API test failed: {e}")
        return False

def test_app_endpoints():
    """Test that app has the cancel-stream endpoint defined."""
    try:
        print("\nTesting app endpoints...")
        import app

        # Check that the cancel-stream endpoint exists
        routes = [route.path for route in app.app.routes]
        assert '/api/cancel-stream' in routes, "Missing /api/cancel-stream endpoint"
        assert '/api/pause-stream' in routes, "Missing /api/pause-stream endpoint"
        assert '/api/resume-stream' in routes, "Missing /api/resume-stream endpoint"

        print("  ✓ /api/cancel-stream endpoint defined")
        print("  ✓ /api/pause-stream endpoint defined")
        print("  ✓ /api/resume-stream endpoint defined")
        print("  ✓ All required endpoints present")
        return True
    except Exception as e:
        print(f"  ❌ Endpoint test failed: {e}")
        return False

def main():
    print("=" * 50)
    print("PAUSE FEATURE VERIFICATION")
    print("=" * 50)

    results = [
        test_imports(),
        test_stream_manager_api(),
        test_app_endpoints(),
    ]

    print("\n" + "=" * 50)
    if all(results):
        print("✅ VERIFICATION COMPLETE - All tests passed!")
        print("=" * 50)
        return 0
    else:
        print("❌ VERIFICATION FAILED - Some tests did not pass")
        print("=" * 50)
        return 1

if __name__ == '__main__':
    sys.exit(main())