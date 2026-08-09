# Security

## Production guarantees

- Session cookies are `HttpOnly`, `SameSite=Lax`, and must be `Secure` in production.
- Only SHA-256 session-token digests are stored. Passwords use salted PBKDF2-HMAC-SHA256 with 600,000 iterations.
- User-supplied Groq keys are encrypted with Fernet using the deployment's stable `ENCRYPTION_SECRET`.
- Admin authorization is a durable verified role, not a client flag or an unverified email match.
- State-changing browser requests must be same-origin. CORS credentials never use a wildcard.
- Request bodies, uploads, provider responses, images, archive expansion, and persisted JSON have explicit limits.
- Production uploads fail closed unless ClamAV can complete a scan with a readable signature database.
- Rate-limit counters are durable in PostgreSQL. Chat, auth, sharing, uploads, voice, images, and global writes are bounded.
- Responses receive request IDs, HSTS, anti-framing, MIME-sniffing protection, a permissions policy, and a restrictive content security policy.
- Generated Website Studio previews run in an opaque-origin sandbox without account cookies, form submission, popups, downloads, or parent-page navigation.
- The service worker caches only fixed app-shell navigations; verification, password-reset, and public-share URLs stay network-only.

## Required operations

- Put the application behind TLS and set the exact public URL in `CORS_ORIGINS` and `PUBLIC_BASE_URL`.
- Store `.env` only in the deployment's secret manager. Never commit it.
- Store production data in a TLS-protected PostgreSQL service with tested backups.
- Keep `ENCRYPTION_SECRET` stable. Rotating it without a key migration makes saved user Groq keys unreadable.
- Rebuild the Docker image regularly so ClamAV signatures and system packages are refreshed.
- Keep `WORKERS=1` and one application replica until stream control is moved to shared infrastructure.
- Remove the bootstrap admin password after first startup.
- Review request-ID-correlated logs and alert on repeated 401, 403, 413, 429, and 500 responses.

## Known architectural boundary

The trusted frontend remains a single inline HTML application, so the CSP currently permits inline script/style. It still blocks framing, plugins, unexpected base URLs, and undeclared network destinations. Moving scripts/styles into hashed static bundles would allow a stricter nonce/hash-only CSP.

PostgreSQL provides durable shared account, billing, TEAM, and rate-limit state.
Horizontal scaling still requires shared stream state and external object
storage for any future persisted binary artifacts.

## Incident response

1. Revoke exposed Groq/OpenAI/Google/SMTP credentials at the provider.
2. Rotate session access by deleting session rows or restarting after a session purge.
3. Preserve database and request-ID logs for investigation.
4. If `ENCRYPTION_SECRET` was exposed, rotate it and require users to re-enter personal Groq keys.
5. Restore from a known-good backup if database integrity is uncertain.

Do not send vulnerability details or secrets through a public issue.
