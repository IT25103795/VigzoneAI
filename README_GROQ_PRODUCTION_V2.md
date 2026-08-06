# Vigzone AI Groq Production — Quick Deploy

Use these values on Render or another production host:

```env
AI_PROVIDER=groq
APP_MODE=production
GROQ_API_KEY=your_groq_key
MODEL_ROUTING_ENABLED=true
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FAST_MODEL=openai/gpt-oss-20b
GROQ_COMPLEX_MODEL=openai/gpt-oss-120b
GROQ_BYOK_MODEL=openai/gpt-oss-120b
GROQ_BACKUP_MODELS=openai/gpt-oss-120b,openai/gpt-oss-20b
GROQ_ALLOWED_MODELS=openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.6-27b
GROQ_VISION_MODEL=qwen/qwen3.6-27b
GROQ_ALLOWED_VISION_MODELS=qwen/qwen3.6-27b
GROQ_VISION_FALLBACK_MODELS=qwen/qwen3.6-27b
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo
DAILY_TOKEN_LIMIT=100000
BYOK_DAILY_TOKEN_LIMIT=100000
ENFORCE_DEFAULT_DAILY_LIMIT=true
ENFORCE_BYOK_DAILY_LIMIT=true
USAGE_TZ_OFFSET_MINUTES=330
ENCRYPTION_SECRET=make_a_unique_long_random_secret
COOKIE_SECURE=true
ADMIN_EMAILS=your-admin-email@example.com
CHAT_RATE_LIMIT_PER_MINUTE=20
```

The router sends only clearly simple, low-risk prompts to GPT-OSS 20B. Coding,
website, study, file, business, live/current, multilingual, high-stakes,
context-heavy, image, and ambiguous follow-up requests stay on the stronger
GPT-OSS 120B or Qwen vision path. No extra model call is spent on routing.

Deprecated Llama model values are migrated in code as a safety net, but the
deployment variables should still be updated to the current values above.

Voice messages use Groq Whisper at `/api/transcribe`. A signed-in user can
activate a personal Groq API key, and the same routing policy applies to it.
