## Stream Pause/Cancel Feature

### Overview
Added a **pause button** to allow users to stop (cancel) the AI response mid-stream. This is useful when:
- A response is taking too long
- The AI is generating unwanted content
- The user changes their mind about the request

### How It Works

#### Backend Components

1. **`stream_manager.py`** (new module)
   - Manages active streaming requests
   - Functions:
     - `create_stream_id()` - Generates unique stream ID
     - `register_stream(stream_id)` - Mark stream as active
     - `is_cancelled(stream_id)` - Check if stream was cancelled
     - `cancel_stream(stream_id)` - Mark stream as cancelled
     - `unregister_stream(stream_id)` - Clean up when done

2. **`app.py` modifications**
   - `/api/chat` endpoint:
     - Generates a unique `stream_id` for each request
     - Sends `stream_id` in the first SSE event
     - Checks `is_cancelled(stream_id)` in the streaming loop
     - Yields `[CANCELLED]` event when cancelled (instead of `[DONE]`)
     - Cleans up with `unregister_stream(stream_id)` in finally block
   
   - New `/api/cancel-stream` endpoint:
     - Accepts: `{ "stream_id": "..." }`
     - Returns: `{ "status": "cancelled", "stream_id": "..." }`
     - Returns 404 if stream not found

3. **Import in app.py**
   ```python
   from stream_manager import create_stream_id, register_stream, cancel_stream, is_cancelled, unregister_stream
   ```

#### Frontend Components

1. **UI Updates** (`static/index.html`)
   - Added pause button (red, with pause icon `||`)
   - Shows only when streaming is active
   - Positioned next to send button in composer
   - CSS class `.pause-btn` with `.active` state

2. **JavaScript Logic**
   - `currentStreamId` variable tracks active stream ID
   - `pauseStream()` function sends cancel request to backend
   - Modified SSE parsing to:
     - Capture `stream_id` from first event
     - Handle `[CANCELLED]` event
   - Updated `updateSendButtonState()` to show/hide pause button

### API Endpoints

#### Streaming Chat (Existing)
```
POST /api/chat
Body: { "messages": [...], "model": "..." }

Response (SSE):
data: {"stream_id": "uuid"}       ← First event
data: {"content": "Hello"}        ← Content chunks
data: {"content": " world"}
...
data: [DONE]                      ← Completion
  OR
data: [CANCELLED]                 ← If user paused
```

#### Cancel Stream (New)
```
POST /api/cancel-stream
Body: { "stream_id": "uuid" }

Response:
{ "status": "cancelled", "stream_id": "uuid" }       ← If found
{ "status": "not_found", "stream_id": "uuid" }       ← 404 if not found
```

### Usage Flow

1. User clicks compose and sends a message
2. Server generates `stream_id` and sends it in first SSE event
3. JavaScript captures `stream_id` and stores in `currentStreamId`
4. Pause button becomes visible (red) while response streams
5. If user clicks pause:
   - Frontend calls `POST /api/cancel-stream` with `stream_id`
   - Backend marks stream as cancelled
   - Streaming loop exits
   - SSE sends `[CANCELLED]` instead of `[DONE]`
6. When streaming completes (cancel or naturally), `currentStreamId` is cleared
7. Pause button hides automatically

### Files Changed/Added

**New Files:**
- `stream_manager.py` - Stream lifecycle management
- `test_stream_manager.py` - Unit tests for stream manager

**Modified Files:**
- `app.py` - Added stream management and cancel endpoint
- `static/index.html` - Added pause button UI and JavaScript logic

### Testing

Run the stream manager tests:
```bash
python test_stream_manager.py
```

Expected output:
```
✓ Created stream ID: xxx-xxx
✓ Stream registered and not cancelled
✓ Stream cancelled successfully
✓ Stream unregistered
✓ Cannot cancel non-existent stream
✅ All tests passed!
```

### Limitations & Notes

- Stream cancellation stops the generator but doesn't interrupt the API call mid-response
- The partial response accumulated so far is displayed with `[CANCELLED]` marker
- If the user cancels, that interaction may not be saved to the knowledge base (interrupts the save)
- The pause button only works during the streaming phase; once complete, it disappears

### Future Enhancements

1. Add visual indicator that response was cancelled (e.g., small "paused" badge)
2. Option to "resume" or "retry" after pause
3. More granular cancellation (per-chunk instead of per-stream)
4. Ability to customize pause button styling/position
5. Analytics: track how often users pause responses

