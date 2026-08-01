"""Shared isolated fixtures for the Vigzone production regression suite."""

from __future__ import annotations

import os

import pytest


# These values must exist before application modules are imported because a few
# mode/config constants are intentionally resolved once at process startup.
os.environ.setdefault("APP_MODE", "testing")
os.environ.setdefault("ENV", "testing")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("VIRUS_SCAN_STRICT", "false")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:8000")
os.environ.setdefault("ENCRYPTION_SECRET", "vigzone-test-encryption-secret-at-least-32-characters")


@pytest.fixture
def auth_db(tmp_path, monkeypatch):
    """Give every test a fresh SQLite database and neutral role config."""

    import auth

    monkeypatch.setattr(auth, "DB_PATH", str(tmp_path / "vigzone-test.db"))
    monkeypatch.setenv(
        "ENCRYPTION_SECRET",
        "vigzone-test-encryption-secret-at-least-32-characters",
    )
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_NAME", raising=False)
    auth.init_db()
    return auth


@pytest.fixture
def client(auth_db):
    """Run the real FastAPI app against the isolated database."""

    from starlette.testclient import TestClient

    import app

    with TestClient(app.app) as test_client:
        yield test_client
