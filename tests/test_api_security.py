"""End-to-end API checks for cookies, origin policy, account controls, and limits."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from security import RequestBodyLimitMiddleware


def _signup(client, email="api@example.com", password="a strong test password"):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "name": "API Person"},
    )


def test_cookie_auth_security_headers_and_origin_rejection(client, auth_db):
    response = _signup(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "api@example.com"

    rejected = client.post(
        "/api/feedback",
        headers={"Origin": "https://evil.example"},
        json={"rating": "up"},
    )
    assert rejected.status_code == 403
    assert rejected.headers["x-frame-options"] == "DENY"
    assert rejected.headers["x-content-type-options"] == "nosniff"
    assert rejected.headers.get("content-security-policy")
    assert rejected.headers.get("x-request-id")

    with auth_db._connect() as conn:
        stored = conn.execute("SELECT token FROM sessions").fetchone()["token"]
    assert len(stored) == 64
    assert stored not in response.headers["set-cookie"]


def test_feedback_export_password_change_and_account_deletion(client):
    old_password = "old password for api test"
    new_password = "new password for api test"
    assert _signup(client, "controls@example.com", old_password).status_code == 200

    feedback = client.post(
        "/api/feedback",
        json={
            "rating": "down",
            "reason": "Needs attribution",
            "message_text": "Question",
            "assistant_text": "Answer",
            "context": {"surface": "chat"},
        },
    )
    assert feedback.status_code == 200

    export = client.get("/api/account/export")
    assert export.status_code == 200
    assert export.headers["cache-control"] == "no-store"
    assert "attachment" in export.headers["content-disposition"]
    assert export.json()["feedback"][0]["assistant_text"] == "Answer"

    chat_export = client.post(
        "/api/export/chat",
        json={
            "format": "html",
            "title": "<script>alert(1)</script>",
            "messages": [{"role": "<img src=x onerror=alert(1)>", "content": "<b>unsafe</b>"}],
        },
    )
    assert chat_export.status_code == 200
    exported_html = chat_export.json()["content"]
    assert "<script>alert(1)</script>" not in exported_html
    assert "<img src=x onerror=alert(1)>" not in exported_html
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in exported_html

    shared = client.post(
        "/api/share/chat",
        json={
            "title": "Revocable API share",
            "messages": [{"role": "user", "content": "Public test"}],
            "public": True,
            "expires_in_days": 7,
        },
    )
    assert shared.status_code == 200
    share_id = shared.json()["share_id"]
    public_share = client.get(f"/share/{share_id}")
    assert public_share.status_code == 200
    assert public_share.headers["cache-control"] == "no-store"
    assert client.get("/api/share/chats").json()["shares"][0]["id"] == share_id
    assert client.delete(f"/api/share/chat/{share_id}").status_code == 200
    assert client.get(f"/share/{share_id}").status_code == 404

    changed = client.post(
        "/api/account/password",
        json={"current_password": old_password, "new_password": new_password},
    )
    assert changed.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "controls@example.com", "password": old_password},
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "controls@example.com", "password": new_password},
    ).status_code == 200

    invalid = client.request(
        "DELETE",
        "/api/account",
        json={"confirmation": "delete", "password": new_password},
    )
    assert invalid.status_code == 422
    deleted = client.request(
        "DELETE",
        "/api/account",
        json={"confirmation": "DELETE", "password": new_password},
    )
    assert deleted.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_public_config_and_liveness_do_not_expose_secrets(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("ENCRYPTION_SECRET", "also-secret-and-should-never-be-returned")

    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["version"] == "5.0.0"

    config = client.get("/api/public/config")
    assert config.status_code == 200
    encoded = config.text
    assert "gsk_test" not in encoded
    assert "also-secret-and-should-never-be-returned" not in encoded


def test_durable_feature_endpoints_and_real_upload_processing(client):
    assert _signup(client, "features@example.com").status_code == 200

    memory = client.post(
        "/api/learning/memories",
        json={"memory_text": "Use production-safe examples.", "tags": "style"},
    )
    assert memory.status_code == 200
    memory_id = memory.json()["memory"]["id"]
    assert client.patch(
        f"/api/learning/memories/{memory_id}",
        json={"is_active": False},
    ).json()["memory"]["is_active"] is False

    workspace = client.post(
        "/api/workspaces",
        json={"name": "Release", "description": "Production launch", "mode": "general"},
    )
    assert workspace.status_code == 200
    workspace_id = workspace.json()["workspace"]["id"]
    note = client.post(
        f"/api/workspaces/{workspace_id}/notes",
        json={"title": "Goal", "content": "Ship the tested release.", "kind": "note"},
    )
    assert note.status_code == 200
    assert client.get(f"/api/workspaces/{workspace_id}/notes").json()["notes"][0]["title"] == "Goal"

    brain = client.post(
        "/api/brain/cloud",
        json={"data": {"focus": "release"}, "base_version": 0},
    )
    assert brain.status_code == 200
    assert brain.json()["version"] == 1
    assert client.get("/api/brain/cloud").json()["payload"] == {"focus": "release"}

    conversation = client.put(
        "/api/conversations/release-chat",
        json={
            "id": "release-chat",
            "title": "Release chat",
            "messages": [{"role": "user", "content": "Ship it"}],
            "base_revision": 0,
        },
    )
    assert conversation.status_code == 200
    assert conversation.json()["revision"] == 1
    assert client.get("/api/conversations/release-chat").json()["title"] == "Release chat"

    upload = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"real extracted upload text", "text/plain")},
    )
    assert upload.status_code == 200
    assert upload.json()["text"] == "real extracted upload text"
    assert upload.json()["kind"] == "document"


def test_request_body_limit_rejects_declared_oversize():
    tiny = FastAPI()
    tiny.add_middleware(RequestBodyLimitMiddleware, max_bytes=8)

    @tiny.post("/echo")
    async def echo(request: Request):
        return {"size": len(await request.body())}

    with TestClient(tiny) as tiny_client:
        assert tiny_client.post("/echo", content=b"12345678").status_code == 200
        oversized = tiny_client.post("/echo", content=b"123456789")
    assert oversized.status_code == 413
    assert oversized.json()["detail"] == "Request body is too large."


def test_safe_production_configuration_is_accepted(monkeypatch):
    import security
    import virus_scanner

    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("ENCRYPTION_SECRET", "a-unique-production-secret-with-more-than-32-characters")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("VIRUS_SCAN_STRICT", "true")
    monkeypatch.setenv("CORS_ORIGINS", "https://vigzone.example")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://vigzone.example")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("WORKERS", "1")
    monkeypatch.setenv("VIGZONE_DATA_DIR", "/srv/vigzone/data")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://vigzone:database-test-password@db.example.com/vigzone?sslmode=require",
    )
    monkeypatch.setattr(virus_scanner, "scanner_healthcheck", lambda: True)

    security.validate_production_settings()


def test_production_preflight_rejects_inverted_token_quotas(monkeypatch):
    import security

    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("ENCRYPTION_SECRET", "a-unique-production-secret-with-more-than-32-characters")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("VIRUS_SCAN_STRICT", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://vigzone.example")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://vigzone.example")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("WORKERS", "1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://vigzone:database-test-password@db.example.com/vigzone?sslmode=require",
    )
    monkeypatch.setenv("FREE_DAILY_TOKEN_LIMIT", "50000")
    monkeypatch.setenv("PRO_DAILY_TOKEN_LIMIT", "40000")
    monkeypatch.setenv("TEAM_DAILY_TOKEN_LIMIT", "1000000")

    with pytest.raises(RuntimeError, match="Daily token quotas must satisfy"):
        security.validate_production_settings()


def test_production_preflight_rejects_mixed_paddle_environments(monkeypatch):
    import security

    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("ENCRYPTION_SECRET", "a-unique-production-secret-with-more-than-32-characters")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("VIRUS_SCAN_STRICT", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://vigzone.example")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://vigzone.example")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("WORKERS", "1")
    monkeypatch.setenv("VIGZONE_DATA_DIR", "/srv/vigzone/data")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://vigzone:database-test-password@db.example.com/vigzone?sslmode=require",
    )
    monkeypatch.setenv("PADDLE_ENVIRONMENT", "production")
    monkeypatch.setenv("PADDLE_CLIENT_TOKEN", "live_123456789012345678901234567")
    monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_pro")
    monkeypatch.setenv("PADDLE_TEAM_PRICE_ID", "pri_team")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "ntfset_live")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_" + "sdbx_apikey_legacy_test_value")

    with pytest.raises(RuntimeError, match="Paddle live API key"):
        security.validate_production_settings()


def test_production_preflight_requires_durable_database(monkeypatch):
    import security

    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("ENCRYPTION_SECRET", "a-unique-production-secret-with-more-than-32-characters")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("VIRUS_SCAN_STRICT", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://vigzone.example")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://vigzone.example")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("WORKERS", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ALLOW_SQLITE_PRODUCTION", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        security.validate_production_settings()


def test_production_preflight_rejects_masked_or_insecure_database_url(monkeypatch):
    import security

    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("ENCRYPTION_SECRET", "a-unique-production-secret-with-more-than-32-characters")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("VIRUS_SCAN_STRICT", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://vigzone.example")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://vigzone.example")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("WORKERS", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://vigzone:********@db.example.com/vigzone")

    with pytest.raises(RuntimeError, match="real database password"):
        security.validate_production_settings()
