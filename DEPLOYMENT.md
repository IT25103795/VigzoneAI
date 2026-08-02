# Deployment runbook

## 1. Prerequisites

- HTTPS reverse proxy or managed platform TLS.
- One application replica with a persistent volume mounted at `/app/data`.
- Groq API key, stable encryption secret, public URL, and exact CORS origin.
- Working outbound HTTPS to configured AI/data providers and SMTP if enabled.

## 2. Configure

Copy `.env.example` to `.env` and set production values. The application refuses to start when:

- the encryption secret is missing, known-placeholder, or shorter than 32 characters;
- cookies or malware scanning are not strict;
- CORS uses `*`, a non-HTTPS non-loopback origin, or no explicit origin;
- `PUBLIC_BASE_URL` is missing or insecure;
- workers are not exactly one;
- the data directory is under `/tmp`;
- the default Groq key is missing;
- ClamAV cannot complete a real scan.

Set `TRUSTED_PROXY_IPS` only to the direct reverse-proxy IPs whose forwarding headers should be trusted.

## 3. Build and run

```bash
docker compose build --pull
docker compose up -d
docker compose ps
```

The image runs as UID/GID `10001`, uses Python 3.13, installs OCR/MIME/malware tooling, and downloads ClamAV signatures at build time.

### Back4App Containers

Deploy the repository root with its `Dockerfile`; no custom start command is
needed. Vigzone reads Back4App's `PORT` variable and listens on `0.0.0.0`.
Configure these variables before deploying:

| Variable | Production value |
| --- | --- |
| `APP_MODE` | `production` |
| `ENV` | `production` |
| `PORT` | `8000` |
| `WORKERS` | `1` |
| `GROQ_API_KEY` | A real `gsk_...` Groq key |
| `ENCRYPTION_SECRET` | A stable random value of at least 32 characters |
| `COOKIE_SECURE` | `true` |
| `VIRUS_SCAN_STRICT` | `true` |
| `VIGZONE_DATA_DIR` | `/app/data` |
| `CORS_ORIGINS` | The exact Back4App HTTPS URL, without a trailing slash |
| `PUBLIC_BASE_URL` | The same exact Back4App HTTPS URL |
| `ENABLE_API_DOCS` | `false` |

Generate the encryption secret locally and store it only in Back4App's secret
variables:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Mount persistent storage at `/app/data` before serving real accounts. A
Back4App temporary URL can change or expire; whenever its hostname changes,
update both URL variables and any Google OAuth origin/redirect configuration.
A permanent URL is strongly recommended.

If deployment reports that nothing is listening on port 8000, inspect the first
`Production preflight failed` application log above the platform health-check
messages. The listed variable or scanner failure is the cause; the port message
is only the consequence. Do not disable secure cookies or strict malware
scanning to bypass preflight.

## 4. Verify

```bash
curl -fsS https://ai.example.com/health/live
curl -fsS https://ai.example.com/health/ready
```

Then use a staging account to verify signup/login, one chat stream, cancel/pause/resume, file upload, voice transcription, image generation, Brain sync, export, and logout. Optional features should be tested only after their provider credentials are configured.

## 5. Backups

Back up the persistent volume while coordinating with SQLite:

```bash
sqlite3 /path/to/data/vigzone.db ".backup '/safe/location/vigzone-backup.db'"
```

Test restores regularly. Keep backup access narrower than application access and define a retention/deletion policy.

## 6. Updates

1. Back up the database.
2. Build a fresh image so OS packages and ClamAV signatures update.
3. Deploy one replacement instance.
4. Check readiness and the staging smoke flow.
5. Keep the previous image available for rollback. Database schema additions are automatic and backward rollback should be tested before production.

## Scaling

Do not increase workers or replicas. For horizontal scaling, migrate SQLite to PostgreSQL, rate/stream state to Redis, and generated/uploaded artifacts to object storage before changing `WORKERS`.
