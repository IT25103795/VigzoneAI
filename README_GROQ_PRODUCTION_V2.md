# Vigzone AI Groq Production v2 — Quick Deploy

Set these variables:

```env
AI_PROVIDER=groq
APP_MODE=production
GROQ_API_KEY=your_new_groq_key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo
DAILY_TOKEN_LIMIT=100000
BYOK_DAILY_TOKEN_LIMIT=100000
ENFORCE_DEFAULT_DAILY_LIMIT=true
ENFORCE_BYOK_DAILY_LIMIT=true
USAGE_TZ_OFFSET_MINUTES=330
ENCRYPTION_SECRET=make_a_long_random_secret
COOKIE_SECURE=true
ADMIN_EMAILS=your-admin-email@example.com
CHAT_RATE_LIMIT_PER_MINUTE=20
```

Deploy, sign in with the admin email, and open the new Admin row in the sidebar.

Old local-model variables are not needed for this build.

Voice messages now use a reliable Groq Whisper fallback at `/api/transcribe` when the browser recognizer falsely says `no-speech`. The same default/user Groq key flow is used for voice transcription.
