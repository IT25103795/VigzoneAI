<p align="center">
  <img src="branding/vigzone-logo.svg" alt="Vigzone AI logo" width="144">
</p>

# Vigzone AI 5.0

Vigzone AI is a private, multi-user AI workspace built with FastAPI and a responsive browser client. Chat, vision, and transcription use Groq by default; text chat can optionally fail over to Gemini after all server-side Groq candidates are rate-limited. Image generation uses OpenAI when configured and otherwise uses a clearly labelled Pollinations fallback.

Vigzone's versioned assistant runtime is **Zoner v0**. Zoner v0 combines Vigzone prompt policy, private-context retrieval, bounded tool context, routing, and offline evaluations over replaceable third-party foundation models. It does not claim custom-trained weights. Its current development status and production gates are recorded in [Zoner release readiness](zoner/RELEASE_READINESS.md).

This release removes demo-only product behavior. Features either call a real backend/provider, work locally and say so, or report that required configuration is missing.

## Included

- Streaming Groq chat with server-side model allowlists and exact usage capture when the provider reports it.
- Zoner v0 component versioning, public runtime manifest, durable version telemetry, and a free offline evaluation corpus.
- Adaptive backup-model request shaping with bounded replies, deterministic context compaction, and one safe retry after provider TPM/payload overflow.
- Per-user accounts, hash-at-rest sessions, password reset/verification email, Google sign-in, account export, and account deletion.
- Durable admin roles with a secure bootstrap path. An unverified signup cannot claim admin access by using an allowlisted email.
- Private Learning Center memory. Only memories explicitly saved by the signed-in user enter that user's prompts.
- Versioned Brain cloud sync with conflict detection, per-user browser storage, workspaces, feedback, conversations, and expiring/revocable public shares.
- Bounded uploads, MIME checks, archive/Office bomb checks, ClamAV scanning, PDF text extraction, scanned-PDF OCR, and truthful format limitations.
- Groq Whisper voice transcription, image understanding, live-data tools, sourced web evidence, image generation/editing, and Website Studio ZIP export.
- Request IDs, origin checks, security headers, durable rate limits, bounded bodies, encrypted user API keys, health probes, Docker packaging, and automated tests.

Vigzone does not claim perfect factual accuracy. Live facts include sources when available; unsupported verification returns an explicit unknown result instead of a fabricated confidence score.

## Supported uploads

| Category | Formats | Behavior |
|---|---|---|
| Documents | PDF, DOCX, RTF | Bounded text extraction; scanned PDFs use bounded OCR |
| Spreadsheets | XLSX, XLSM, CSV, TSV | Bounded sheets, rows, and cells converted to text |
| Presentations | PPTX | Bounded slide text extraction |
| Images | PNG, JPEG, WebP, GIF, BMP, TIFF, ICO | Validated and resized; animated GIFs use the first frame only |
| Data/code/text | JSON/JSONL, XML, YAML, TOML, common source/text files | Bounded plain-text context |
| Archives | ZIP, TAR, TGZ | Manifest only; contents are not analyzed |
| Audio/video attachments | Common formats | Metadata only; use the microphone flow for transcription |

Legacy DOC/XLS/PPT, ODT/ODS, SVG, RAR, and 7z are rejected with conversion guidance.

## Local development

Python 3.11–3.14 is supported. Python 3.13 is used in the container.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Add `GROQ_API_KEY` to `.env`, then run:

```bash
python launcher.py dev
```

Open `http://localhost:8000`. API documentation is available at `/docs` in development.

OCR requires Tesseract and MIME detection requires libmagic. ClamAV is optional in local testing; the Docker image includes all three.

## Production

Production startup intentionally fails if a critical setting is unsafe. At minimum configure:

```env
APP_MODE=production
ENV=production
GROQ_API_KEY=...
ENCRYPTION_SECRET=<unique random value, at least 32 characters>
COOKIE_SECURE=true
VIRUS_SCAN_STRICT=true
WORKERS=1
DATABASE_URL=postgresql://.../vigzone?sslmode=require
CORS_ORIGINS=https://ai.example.com
PUBLIC_BASE_URL=https://ai.example.com
```

Generate the encryption secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For a first admin account, set a unique email and a password of at least 12 characters:

```env
ADMIN_BOOTSTRAP_EMAIL=admin@example.com
ADMIN_BOOTSTRAP_NAME=Vigzone Admin
ADMIN_BOOTSTRAP_PASSWORD=<unique admin password>
```

Remove `ADMIN_BOOTSTRAP_PASSWORD` from the deployment environment after the admin has been created. `ADMIN_EMAILS` can promote only an already verified account.

Build and start behind an HTTPS reverse proxy:

```bash
cp .env.example .env
# Fill all required production values in .env
docker compose up --build -d
```

Use a managed PostgreSQL database and its tested backup/restore facilities.
SQLite remains available only for local development or an explicitly approved
persistent-volume deployment. Use one process and one replica because
pause/resume stream state is still process-local.

See [DEPLOYMENT.md](DEPLOYMENT.md), [SECURITY.md](SECURITY.md), and [PRIVACY.md](PRIVACY.md).

## Optional providers

- `GEMINI_API_KEY`: server-only Gemini text fallback after all configured server Groq candidates return rate limits. `GEMINI_FALLBACK_MODEL` defaults to `gemini-3.6-flash`; personal Groq keys and image chats do not use this shared fallback.
- `OPENAI_API_KEY`: OpenAI image generation/editing (`gpt-image-2` by default).
- SMTP settings: verification and password-reset email. Without SMTP, those delivery flows report that email is not configured.
- Google OAuth settings: Google sign-in.
- Google Drive API/client IDs: Drive Picker. Shared-link import still requires the file to be downloadable.
- Weather/market API keys: richer current-data coverage. Keyless sources remain best-effort and attributable.

Users may validate and activate their own Groq key. It is encrypted at rest with `ENCRYPTION_SECRET`.

## Validation

```bash
python -m compileall -q .
python -m zoner.evaluation validate
python -m zoner.baseline plan --limit 3
ruff check .
pytest
```

CI runs the same syntax, lint, and test gates. Provider calls are mocked in tests; deploy-time smoke checks should use real staging credentials.

The browser bundle vendors JSZip 3.10.1 for CSP-compatible ZIP downloads. Its MIT license is included at `static/vendor/JSZIP-LICENSE.md`.

## Health

- `GET /health/live`: process liveness only.
- `GET /health/ready`: database and required Groq configuration readiness.
- `GET /health`: compatibility alias for readiness.

Production API docs are disabled unless `ENABLE_API_DOCS=true`.
