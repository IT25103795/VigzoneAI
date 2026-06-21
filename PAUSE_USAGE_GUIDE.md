# Pause Button - Setup & Usage Guide

## Quick Start

The pause feature is automatically available once you start the server. No additional setup is required.

### Starting the Server

```powershell
# From the VigzoneAI directory
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Using the Pause Button

1. **Send a message** - Type your prompt and click send
2. **Wait for response** - AI starts responding
3. **Pause button appears** - A red ⏸ button shows up next to the send button
4. **Click to stop** - Click the pause button to cancel the response
5. **See partial result** - The response stops and shows what was generated so far

## What Happens When You Pause

### User Perspective
- Red pause button appears while AI is responding
- Click the button to stop the response
- Partial response is displayed
- The pause button disappears
- You can send another message

### Behind the Scenes
1. Previous response is discarded (not saved to knowledge base)
2. Backend stops processing chunks
3. Stream is cleaned up from memory
4. Frontend clears its stream tracking

## Features

✅ **Graceful Cancellation** - Stops mid-stream cleanly
✅ **Visual Feedback** - Red button appears/disappears
✅ **No Data Loss** - Partial responses shown
✅ **No Memory Leaks** - Streams properly cleaned up
✅ **Lightweight** - Uses simple in-memory tracking

## Troubleshooting

### Pause button doesn't appear
- Make sure you have a Groq API key configured (check `/health`)
- Try a longer prompt that takes more time to respond
- Check browser console for errors (F12 → Console)

### Pause button doesn't work
- Try with a different message
- Refresh the page and try again
- Check server logs for errors

### Response shows "[CANCELLED]" ending
- This is expected behavior when you click pause
- The partial response shown is what was generated before pause
- Subsequent messages will work normally

## Technical Details for Developers

### How Stream IDs Work

Each chat request gets a unique UUID:
```
stream_id = "550e8400-e29b-41d4-a716-446655440000"
```

This ID is:
- Generated server-side
- Sent to client in first SSE event
- Stored in client's `currentStreamId` variable
- Sent to `/api/cancel-stream` endpoint when paused
- Cleaned up after response completes

### Stream States

```
CREATED → REGISTERED → ACTIVE → [CANCELLED/COMPLETED] → UNREGISTERED
```

### Code Flow

**Backend:**
```python
# In /api/chat:
stream_id = create_stream_id()         # Create unique ID
register_stream(stream_id)             # Track it
yield {"stream_id": stream_id}         # Send to client

# In streaming loop:
for chunk in stream_chat(...):
    if is_cancelled(stream_id):        # Check if paused
        break
    yield {"content": chunk}           # Send chunk

# In finally block:
unregister_stream(stream_id)           # Clean up
```

**Frontend:**
```javascript
// When stream starts:
currentStreamId = parsed.stream_id;    // Capture ID
pauseBtn.classList.add('active');      // Show button

// When user clicks pause:
fetch('/api/cancel-stream', {
  body: JSON.stringify({ stream_id: currentStreamId })
});

// When stream ends:
currentStreamId = null;                // Clear ID
pauseBtn.classList.remove('active');   // Hide button
```

## Testing

Run all tests:
```powershell
# Unit tests
python test_stream_manager.py

# Integration tests  
python verify_pause_feature.py

# Simulation test
python test_pause_simulation.py
```

All should show ✅ PASSED.

## Files Overview

| File | Purpose |
|------|---------|
| `stream_manager.py` | Stream lifecycle management |
| `app.py` | FastAPI endpoints, stream handling |
| `static/index.html` | UI components (pause button), JavaScript logic |
| `test_stream_manager.py` | Unit tests |
| `verify_pause_feature.py` | Integration verification |
| `test_pause_simulation.py` | End-to-end simulation |

## Performance Impact

- **Memory**: ~200 bytes per active stream (minimal)
- **CPU**: Negligible overhead (one dict lookup per chunk)
- **Network**: One extra SSE event at start (stream_id)
- **Latency**: No added latency

## Security Considerations

- Stream IDs are UUIDs (cryptographically random)
- Cannot be guessed or brute-forced in practice
- Only valid during active stream (cleaned up after)
- No persistent storage of stream history

## Future Enhancement Ideas

- [ ] History of paused responses
- [ ] Pause duration tracking (analytics)
- [ ] Resume from pause point
- [ ] Custom pause timeout (auto-pause after N seconds)
- [ ] Pause all active streams for multi-stream apps
- [ ] Pause statistics dashboard

---

For more details, see:
- `PAUSE_FEATURE.md` - Architecture documentation
- `PAUSE_FEATURE_SUMMARY.md` - Implementation summary

