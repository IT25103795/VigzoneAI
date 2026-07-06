# Vigzone AI — Groq Production v2

Vigzone AI is a FastAPI + HTML/JS chat app powered by Groq's hosted OpenAI-compatible API. This production build is Groq-only: users either use the deployment's default Groq key with an individual Vigzone daily limit, or they paste their own Groq API key and use their own quota.

## What changed in v2

- Groq-only chat path; no local/server model dependency.
- Per-user daily usage table with used tokens, remaining tokens, reset countdown, request count, and plan label.
- Real backend daily limit enforcement, not just a UI progress bar.
- Optional BYOK Groq key flow: Check → Use this key.
- Admin dashboard for total users, active users, today’s tokens, top users, and per-user usage reset.
- Model fallback through `GROQ_BACKUP_MODELS`.
- Token-saving history compaction for long conversations.
- Basic chat rate limiting and secure-cookie option.
- API keys saved encrypted at rest with `ENCRYPTION_SECRET`.

## Required production variables

```env
AI_PROVIDER=groq
APP_MODE=production
GROQ_API_KEY=your_new_groq_key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview
DAILY_TOKEN_LIMIT=100000
BYOK_DAILY_TOKEN_LIMIT=100000
USAGE_TZ_OFFSET_MINUTES=330
ENCRYPTION_SECRET=make_a_long_random_secret
COOKIE_SECURE=true
```

Optional but recommended:

```env
GROQ_BACKUP_MODELS=
CHAT_RATE_LIMIT_PER_MINUTE=20
ADMIN_EMAILS=your-admin-email@example.com
MAX_HISTORY_MESSAGES=14
MAX_COMPACTED_TURNS=18
USAGE_RESERVE_TOKENS=800
```

## User plans

### Vigzone default Groq plan

Users without a saved key use the deployment’s `GROQ_API_KEY`. Vigzone tracks each signed-in user separately and blocks new chats after the configured daily limit is reached.

### Personal Groq key plan

Users can paste a Groq key in the sidebar. Vigzone validates it against Groq, then stores it encrypted and uses it for that user’s chats. Usage is still estimated by Vigzone so the UI can show a countdown and remaining tokens.

## Admin dashboard

Set `ADMIN_EMAILS` to one or more comma-separated account emails. Those users will see an Admin button in the sidebar.

Admin dashboard shows:

- total users
- active users today
- total tokens and requests today
- default-plan vs own-key users
- top users by tokens today
- reset today’s tracked usage for a user

The reset only clears Vigzone’s own database rows. It does not reset Groq-side quota.

## Daily limits

Default settings:

```env
DAILY_TOKEN_LIMIT=100000
BYOK_DAILY_TOKEN_LIMIT=100000
ENFORCE_DEFAULT_DAILY_LIMIT=true
ENFORCE_BYOK_DAILY_LIMIT=true
```

Set `ENFORCE_BYOK_DAILY_LIMIT=false` if users with their own Groq key should only be tracked, not blocked by Vigzone.

## Model fallback

Set backup models as a comma-separated list:

```env
GROQ_BACKUP_MODELS=model-one,model-two
```

Vigzone tries backups when the main model returns a model/rate/server failure. It does not fallback on invalid API keys.

## Local run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows
# cp .env.example .env  # macOS/Linux
python start.py
```

Open `http://localhost:8000`.

## Groq API key tutorial for users

1. Go to Groq Console → API Keys.
2. Create a new API key.
3. Copy it immediately; Groq will not show it again.
4. Paste it in Vigzone’s sidebar.
5. Click Check, then Use this key.

## Security notes

- Revoke any key that was ever shared in screenshots.
- Use a strong, stable `ENCRYPTION_SECRET`; changing it makes saved user keys unreadable.
- Keep `COOKIE_SECURE=true` in HTTPS production.
- Do not rely only on UI limits; this build enforces limits in the backend before chat requests.


## Voice message reliability

Voice messages first try the browser's instant speech recognizer. If the browser returns a false no-speech result, Vigzone falls back to Groq Whisper through `/api/transcribe`, using the deployment Groq key or the user's activated Groq key. Configure with `GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo`.

## Learning Center (private per-user memory)

This build includes a real Learning Center from the sidebar. Each signed-in user can add, edit, pause, delete, and toggle their own approved memories. Memories are private to that account and are injected into only that user's chat context when Learning is ON. They do not change the model weights and are not shared with other users.

API endpoints:

- `GET /api/learning/status`
- `POST /api/learning/toggle`
- `GET /api/learning/memories`
- `POST /api/learning/memories`
- `PATCH /api/learning/memories/{id}`
- `DELETE /api/learning/memories/{id}`

