"""Authentication, privacy-isolation, and durable-state regression tests."""

from __future__ import annotations

import re

import pytest


PASSWORD = "correct horse battery staple"


def _create_two_users(auth):
    first = auth.create_user_with_password("first@example.com", PASSWORD, "First")
    second = auth.create_user_with_password("second@example.com", PASSWORD, "Second")
    return first, second


def test_sessions_are_hashed_and_revocable(auth_db):
    user = auth_db.create_user_with_password("person@example.com", PASSWORD, "Person")
    token = auth_db.create_session(user["id"], "test-fingerprint")

    with auth_db._connect() as conn:
        stored = conn.execute("SELECT token FROM sessions").fetchone()["token"]

    assert stored != token
    assert re.fullmatch(r"[0-9a-f]{64}", stored)
    assert auth_db.get_user_by_session(token)["id"] == user["id"]

    auth_db.delete_session(token)
    assert auth_db.get_user_by_session(token) is None


def test_learning_brain_and_conversations_are_isolated(auth_db):
    first, second = _create_two_users(auth_db)

    auth_db.add_learning_memory(first["id"], "I prefer concise technical answers.", "style")
    assert "concise technical" in auth_db.get_learning_context(first["id"], "technical")
    assert auth_db.list_learning_memories(second["id"]) == []
    assert auth_db.get_learning_context(second["id"], "technical") == ""

    saved = auth_db.save_brain_snapshot(
        first["id"],
        {"conversations": [{"id": "private-chat"}]},
        "2026-08-01T00:00:00Z",
        0,
    )
    assert saved["version"] == 1
    assert auth_db.get_brain_snapshot(second["id"])["payload"] == {}
    with pytest.raises(auth_db.StateConflictError) as stale:
        auth_db.save_brain_snapshot(first["id"], {"stale": True}, None, 0)
    assert stale.value.current["version"] == 1

    first_chat = auth_db.upsert_conversation(
        first["id"],
        "same-client-id",
        "First private chat",
        [{"role": "user", "content": "first secret"}],
        0,
    )
    second_chat = auth_db.upsert_conversation(
        second["id"],
        "same-client-id",
        "Second private chat",
        [{"role": "user", "content": "second secret"}],
        0,
    )
    assert first_chat["messages"][0]["content"] == "first secret"
    assert second_chat["messages"][0]["content"] == "second secret"
    with pytest.raises(auth_db.StateConflictError):
        auth_db.upsert_conversation(first["id"], "same-client-id", "Stale", [], 0)


def test_admin_allowlist_requires_verified_ownership(auth_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    user = auth_db.create_user_with_password("admin@example.com", PASSWORD, "Admin Claim")

    auth_db.init_db()
    assert auth_db.verify_password_login("admin@example.com", PASSWORD)["is_admin"] is False

    verification_token, _ = auth_db.create_email_verification_token(user["id"])
    verified = auth_db.verify_email_token(verification_token)
    assert verified["email_verified"] is True
    assert verified["is_admin"] is True


def test_share_revocation_and_account_export_cascade(auth_db):
    first, second = _create_two_users(auth_db)
    session = auth_db.create_session(first["id"])
    auth_db.add_learning_memory(first["id"], "Keep this private to the first account.")
    auth_db.save_feedback_record(
        first["id"],
        {
            "rating": "down",
            "reason": "Needs a source",
            "message_text": "What changed?",
            "assistant_text": "An unsupported answer",
            "context": {"model": "test"},
        },
    )
    auth_db.create_shared_chat(
        first["id"],
        "shareABC123",
        "Temporary share",
        [{"role": "user", "content": "hello"}],
        True,
        7,
    )

    assert auth_db.get_shared_chat("shareABC123") is not None
    assert auth_db.revoke_shared_chat(second["id"], "shareABC123") is False
    assert auth_db.revoke_shared_chat(first["id"], "shareABC123") is True
    assert auth_db.get_shared_chat("shareABC123") is None

    exported = auth_db.export_user_data(first["id"])
    assert exported["account"]["email"] == "first@example.com"
    assert exported["feedback"][0]["message_text"] == "What changed?"
    assert exported["learning_memories"][0]["memory_text"].startswith("Keep this private")

    auth_db.delete_account(first["id"])
    assert auth_db.get_user_by_session(session) is None
    with auth_db._connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM learning_memories WHERE user_id = ?",
            (first["id"],),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE user_id = ?",
            (first["id"],),
        ).fetchone()[0] == 0


def test_per_account_storage_quotas_are_enforced(auth_db, monkeypatch):
    user = auth_db.create_user_with_password("quota@example.com", PASSWORD, "Quota")
    monkeypatch.setattr(auth_db, "MAX_LEARNING_MEMORIES_PER_USER", 1)
    auth_db.add_learning_memory(user["id"], "First approved memory")
    with pytest.raises(auth_db.AuthError, match="limited to 1"):
        auth_db.add_learning_memory(user["id"], "Second approved memory")

    monkeypatch.setattr(auth_db, "MAX_CONVERSATIONS_PER_USER", 1)
    auth_db.upsert_conversation(user["id"], "first", "First", [], 0)
    with pytest.raises(auth_db.AuthError, match="limit reached"):
        auth_db.upsert_conversation(user["id"], "second", "Second", [], 0)
