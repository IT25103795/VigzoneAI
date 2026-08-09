# Deployment runbook

## 1. Prerequisites

- HTTPS reverse proxy or managed platform TLS.
- One application replica connected to a durable TLS-protected PostgreSQL database.
- Groq API key, stable encryption secret, public URL, and exact CORS origin.
- Working outbound HTTPS to configured AI/data providers and SMTP if enabled.

## 2. Configure

Copy `.env.example` to `.env` and set production values. The application refuses to start when:

- the encryption secret is missing, known-placeholder, or shorter than 32 characters;
- cookies or malware scanning are not strict;
- CORS uses `*`, a non-HTTPS non-loopback origin, or no explicit origin;
- `PUBLIC_BASE_URL` is missing or insecure;
- workers are not exactly one;
- `DATABASE_URL` is absent or is not a complete TLS-protected PostgreSQL URL;
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
| `DATABASE_URL` | Complete pooled PostgreSQL URL with `sslmode=require` or stronger |
| `GROQ_API_KEY` | A real `gsk_...` Groq key |
| `ENCRYPTION_SECRET` | A stable random value of at least 32 characters |
| `COOKIE_SECURE` | `true` |
| `VIRUS_SCAN_STRICT` | `true` |
| `CORS_ORIGINS` | The exact Back4App HTTPS URL, without a trailing slash |
| `PUBLIC_BASE_URL` | The same exact Back4App HTTPS URL |
| `ENABLE_API_DOCS` | `false` |
| `PADDLE_CLIENT_TOKEN` | Paddle Billing live client-side token (`live_...`) |
| `PADDLE_PRO_PRICE_ID` | Exact recurring PRO price (`pri_...`) |
| `PADDLE_TEAM_PRICE_ID` | Exact recurring TEAM price (`pri_...`) |
| `PADDLE_WEBHOOK_SECRET` | Secret for `/api/billing/paddle/webhook` |
| `PADDLE_API_KEY` | Server API key for purchase restoration |
| `PADDLE_ENVIRONMENT` | `production` (`sandbox` only for test catalog IDs) |

### Render Free + Neon PostgreSQL

Render's free filesystem is ephemeral, so production accounts and Paddle state
must not use the local SQLite fallback. Create a Neon project, enable its pooled
connection, and store the complete secret URL only in Render as `DATABASE_URL`.
Use **Save only** until a PostgreSQL-capable Vigzone build is ready, then deploy.
The hostname should contain `-pooler` and the query string must contain
`sslmode=require` (or a stronger verification mode). Vigzone creates its schema
at startup and reports `"database_backend": "postgresql"` from `/health/ready`.

Never set `VIGZONE_DB_PATH` to a PostgreSQL URL. `VIGZONE_DATA_DIR` and
`ALLOW_SQLITE_PRODUCTION=true` are only for an explicitly verified persistent
SQLite volume, not Render Free.

### Paddle Sandbox → Live cutover

Paddle sandbox and live are separate workspaces. Do not reuse sandbox API
keys, client-side tokens, products, prices, customers, or webhook secrets in
Live. Before changing `PADDLE_ENVIRONMENT`, create the Live catalog and set all
six variables in the same Render deployment update:

1. `PADDLE_CLIENT_TOKEN=live_...`
2. `PADDLE_API_KEY=pdl_live_apikey_...` (server secret; never expose it in HTML)
3. `PADDLE_PRO_PRICE_ID=pri_...` from the Live recurring PRO price
4. `PADDLE_TEAM_PRICE_ID=pri_...` from the Live recurring TEAM price
5. `PADDLE_WEBHOOK_SECRET=ntfset_...` from the Live notification destination
6. `PADDLE_ENVIRONMENT=production`

Configure the Live webhook destination as
`https://<your-domain>/api/billing/paddle/webhook` and subscribe at minimum to
`subscription.created`, `subscription.updated`, `subscription.activated`,
`subscription.resumed`, `subscription.paused`, `subscription.canceled`, and
`transaction.completed`. Approve the production domain in Paddle Checkout
settings and configure its default payment link before opening Live checkout.

After deployment, make one real controlled PRO purchase and one real controlled
TEAM purchase. Confirm that Paddle reports the webhook as delivered, the header
badge changes immediately after refresh, TEAM Hub creates five available seats,
and cancellation/downgrade removes paid access on the next authenticated request.
Then refund/cancel the controlled transactions as appropriate. Rotate the
server API key before its configured expiry date.

Generate the encryption secret locally and store it only in Back4App's secret
variables:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use managed PostgreSQL before serving real accounts. A Back4App temporary URL
can change or expire; whenever its hostname changes,
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

Use the PostgreSQL provider's automated backups/restore points and test a
restore regularly. Keep database credentials narrower than owner credentials,
rotate them periodically, and define a retention/deletion policy.

## 6. Updates

1. Back up the database.
2. Build a fresh image so OS packages and ClamAV signatures update.
3. Deploy one replacement instance.
4. Check readiness and the staging smoke flow.
5. Keep the previous image available for rollback. Database schema additions are automatic and backward rollback should be tested before production.

## Scaling

Do not increase workers or replicas yet. PostgreSQL and durable rate limits are
shared, but pause/resume stream state is still process-local. Move stream state
to a shared service before changing `WORKERS`.
