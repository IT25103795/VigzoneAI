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

## Prompt and context efficiency

The efficiency engine is enabled by default and needs no new variable. Ordinary
turns use a stable compact core prompt; code, website, live-data, study, file,
business, and voice instructions are loaded only when relevant. Recent history
is selected by token budget, older relevant context is compacted, and duplicate
memory/workspace/search units are removed before the Groq request.

These optional Render variables tune the conservative defaults:

```env
CONTEXT_MAX_RECENT_MESSAGES=10
CONTEXT_HISTORY_TOKEN_BUDGET=2400
CONTEXT_SUMMARY_TOKEN_BUDGET=600
CONTEXT_MEMORY_TOKEN_BUDGET=450
CONTEXT_WORKSPACE_TOKEN_BUDGET=650
CONTEXT_LIVE_TOKEN_BUDGET=1800
CONTEXT_IMAGE_SEARCH_TOKEN_BUDGET=1200
ROUTING_ANALYTICS_ENABLED=true
```

Each production usage row records the selected route, final model, fallback and
retry state, latency, cached tokens when reported by Groq, and an estimated
system/history/summary/memory/workspace/search/user token breakdown. Existing
SQLite databases are migrated automatically during startup.
