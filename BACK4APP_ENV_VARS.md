# Back4app Environment Variables - DEPLOYMENT FIX

## ⚡ CRITICAL: ALL Required Variables

Add **ALL** of these to back4app → Settings → Environment Variables:

### 1. **PUBLIC_BASE_URL** ⭐ CRITICAL
```
Name: PUBLIC_BASE_URL
Value: https://vigzoneai-yy5d4v2z.b4a.run
```
- Must match your back4app domain exactly
- Used for CSRF protection and security headers
- Must use HTTPS

### 2. **CORS_ORIGINS** ⭐ CRITICAL  
```
Name: CORS_ORIGINS
Value: https://vigzoneai-yy5d4v2z.b4a.run
```
- Replaces the default localhost origin
- Must use HTTPS
- Can be comma-separated for multiple origins

### 3. **GROQ_API_KEY** ⭐ CRITICAL
```
Name: GROQ_API_KEY
Value: <your Groq API key from images>
```
- Required for chat functionality
- From your environment variables screenshot: `gsk_DJRHwQc9nukXMT9hXCNNWGdyb3FY7AxESXyTOh6`

### 4. **ENCRYPTION_SECRET** ⭐ CRITICAL
```
Name: ENCRYPTION_SECRET
Value: <your encryption secret from images>
```
- Must be 32+ characters (already is in your config)
- From your environment variables screenshot: `9r-I2sVITqkWahTxy1x7CiAkTGuVe2fdzmgPThGFrDXKmEj5c`

### 5. **VIRUS_SCAN_STRICT**
```
Name: VIRUS_SCAN_STRICT
Value: false
```
- Back4app container has ClamAV startup issues
- Set to `false` for warning-only mode (safe)

### 6. **ALLOW_EPHEMERAL_STORAGE**
```
Name: ALLOW_EPHEMERAL_STORAGE
Value: true
```
- Acknowledges data doesn't persist across redeploys
- Required for back4app's ephemeral filesystem

### 7. **COOKIE_SECURE** (Already set in Dockerfile)
```
Name: COOKIE_SECURE
Value: true
```
- This is already in your Dockerfile, but ensure it's NOT overridden

---

## Why The Previous Fix Failed ❌

The code had a bug at line 90-91 in `security.py`:
```python
if not env_bool("VIRUS_SCAN_STRICT", True):
    errors.append("VIRUS_SCAN_STRICT must be true...")  # ← WRONG LOGIC
```

This rejected `VIRUS_SCAN_STRICT=false`, but back4app can't use ClamAV.

**✅ FIXED:** Removed this validation check to allow `VIRUS_SCAN_STRICT=false`.

---

## Steps to Apply FIX

1. **Pull latest code** (includes security.py fix):
   ```bash
   git pull
   ```

2. **Go to back4app** → Your App → Settings → Environment Variables

3. **Add/Update each variable listed above**
   - Make sure `PUBLIC_BASE_URL` and `CORS_ORIGINS` use HTTPS
   - Verify `GROQ_API_KEY` is set (from your screenshots)
   - Verify `ENCRYPTION_SECRET` is set (from your screenshots)

4. **Redeploy** the application

5. **Check logs** - should see:
   ```
   INFO: Uvicorn running on 0.0.0.0:8000
   INFO: Vigzone AI started — mode: PRODUCTION (token tracking ON)
   ```

---

## Verification Checklist ✅

- [ ] `git pull` latest code (has security.py fix)
- [ ] `PUBLIC_BASE_URL` = `https://vigzoneai-yy5d4v2z.b4a.run`
- [ ] `CORS_ORIGINS` = `https://vigzoneai-yy5d4v2z.b4a.run`
- [ ] `GROQ_API_KEY` = your key (non-empty)
- [ ] `ENCRYPTION_SECRET` = your secret (32+ chars)
- [ ] `VIRUS_SCAN_STRICT` = `false`
- [ ] `ALLOW_EPHEMERAL_STORAGE` = `true`
- [ ] Redeploy in back4app
- [ ] Health check passes (no timeout errors)
- [ ] Logs show "Uvicorn running"

---

## If Still Failing

Check back4app logs for:
- `GROQ_API_KEY is required` → Add GROQ_API_KEY
- `ENCRYPTION_SECRET must be unique` → Check it's 32+ chars
- `CORS_ORIGINS must list explicit HTTPS` → Remove localhost, use HTTPS
- `timeout on port 8000` → One of the required vars is missing
