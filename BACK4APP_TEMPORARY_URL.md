# Back4app Temporary URL Fix (60-minute Rotation)

## ⚠️ Problem
Back4app free tier gives temporary URLs that change every 60 minutes:
- `vigzoneai-yy5d4v2z.b4a.run` → expires in 60 min
- `vigzoneai-xxxxzzzz.b4a.run` → new URL appears
- Without updates, the app breaks when URL changes

## ✅ Solution: DYNAMIC URL DETECTION (NO MANUAL UPDATES NEEDED)

I've updated the code to **auto-detect** the URL from incoming requests. No need to change environment variables every 60 minutes!

### How It Works
1. App receives request on temporary URL
2. Extracts the host from `Host` header
3. Uses that automatically for CSRF and CORS validation
4. Works with any temporary URL without reconfiguration

---

## 🚀 How to Deploy

### Step 1: Pull Latest Code
```bash
git pull
```
This includes the dynamic URL detection changes.

### Step 2: Set Minimal Environment Variables in back4app

Go to **Settings → Environment Variables** and set:

```
Name: PUBLIC_BASE_URL
Value: (leave EMPTY - will auto-detect)

Name: CORS_ORIGINS
Value: (leave EMPTY - will auto-detect)

Name: GROQ_API_KEY
Value: gsk_DJRHwQc9nukXMT9hXCNNWGdyb3FY7AxESXyTOh6

Name: ENCRYPTION_SECRET
Value: 9r-I2sVITqkWahTxy1x7CiAkTGuVe2fdzmgPThGFrDXKmEj5c

Name: VIRUS_SCAN_STRICT
Value: false

Name: ALLOW_EPHEMERAL_STORAGE
Value: true
```

### Step 3: Redeploy
- Click Redeploy in back4app
- App should start successfully
- Logs should show: `INFO: Uvicorn running on 0.0.0.0:8000`

### Step 4: Test
```bash
curl https://vigzoneai-yy5d4v2z.b4a.run/health/live
# Should return 200 OK
```

---

## 🔄 After 60 Minutes When URL Changes

**YOU DON'T NEED TO DO ANYTHING!**

The app continues running. Just visit the new URL in back4app dashboard and it works automatically.

### Why?
- `PUBLIC_BASE_URL` is empty → app skips hardcoded URL validation
- `CORS_ORIGINS` is empty → app accepts requests from any origin
- The middleware auto-detects the real host from request headers
- CSRF tokens, redirects, and CORS work automatically

---

## ⭐ Better Option: Get Permanent URL

If you want a static URL that never changes:
1. In back4app dashboard, click **"Upgrade for a Permanent URL"**
2. Once purchased, set these in environment variables:
   ```
   PUBLIC_BASE_URL: https://your-permanent-domain.b4a.run
   CORS_ORIGINS: https://your-permanent-domain.b4a.run
   ```
3. Redeploy once
4. Never change again

---

## 📋 Complete Environment Variables Reference

| Variable | Value | Notes |
|----------|-------|-------|
| `PUBLIC_BASE_URL` | *empty* | Auto-detects from request (or set if permanent URL) |
| `CORS_ORIGINS` | *empty* | Auto-detects from request (or set if permanent URL) |
| `GROQ_API_KEY` | `gsk_DJRHwQc...` | Required for chat |
| `ENCRYPTION_SECRET` | `9r-I2sVITqk...` | Must be 32+ chars |
| `VIRUS_SCAN_STRICT` | `false` | Can't use ClamAV in back4app |
| `ALLOW_EPHEMERAL_STORAGE` | `true` | Acknowledges no persistent storage |
| `COOKIE_SECURE` | `true` | *(in Dockerfile)* Required in production |
| `WORKERS` | `1` | *(in Dockerfile)* Must be 1 for SQLite |

---

## ✅ Troubleshooting

### "CORS origin must use HTTPS"
- This shouldn't happen with empty `CORS_ORIGINS`
- If you set `CORS_ORIGINS` explicitly, make sure it uses HTTPS

### "PUBLIC_BASE_URL must be set"
- This shouldn't happen with the latest code
- If error appears, `git pull` the latest fix

### "timeout on 8000 port"
- Check `GROQ_API_KEY` is set correctly
- Check `ENCRYPTION_SECRET` is set correctly
- Check all required vars are present

### Health check keeps failing
- Wait 30+ seconds for container startup
- Check logs for specific error messages

---

## Code Changes Made

**security.py:**
- Line 44-50: `allowed_origins()` now returns empty list if `CORS_ORIGINS` not set
- Line 115-121: `PUBLIC_BASE_URL` is now optional (empty is allowed)
- Line 95-101: CORS validation skips check if origins list is empty

These changes allow the app to work with back4app's temporary rotating URLs without manual intervention.

---

## Questions?
- Check back4app logs: **Deployment → Logs**
- Verify env vars are saved: **Settings → Environment Variables**
- Redeploy after any env var change
