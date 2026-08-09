"""Role-aware token quotas, durable reservations, and shared TEAM accounting."""

from __future__ import annotations

import pytest

import billing


PASSWORD = "a strong quota test password"


def _clear_quota_env(monkeypatch):
    for name in billing.TOKEN_LIMIT_ENV_VARS.values():
        monkeypatch.delenv(name, raising=False)


def test_default_role_quota_matrix_and_entitlements(monkeypatch):
    _clear_quota_env(monkeypatch)
    free = {"id": 1, "plan": "free", "role": "user"}
    pro = {"id": 2, "plan": "pro", "role": "user"}
    team_owner = {"id": 3, "plan": "team", "role": "user"}
    team_member = {
        "id": 4,
        "plan": "free",
        "role": "user",
        "team_active": True,
        "team_owner_id": 3,
    }
    admin = {"id": 5, "plan": "free", "role": "admin", "is_admin": True}

    assert billing.token_quota(free)["daily_limit"] == 50_000
    assert billing.token_quota(pro)["daily_limit"] == 250_000
    assert billing.token_quota(team_owner) == {
        "plan": "team",
        "display_name": "TEAM",
        "daily_limit": 1_000_000,
        "scope": "team",
        "subject_id": 3,
        "shared": True,
    }
    assert billing.token_quota(team_member)["subject_id"] == 3
    assert billing.token_quota(admin)["daily_limit"] == 0
    assert billing.entitlement_snapshot(pro)["limits"]["tokens_per_day"] == 250_000
    assert billing.entitlement_snapshot(admin)["limits"]["tokens_per_day"] is None


def test_quota_reservation_is_reconciled_to_exact_usage(auth_db, monkeypatch):
    import vigzone_ai

    user = auth_db.create_user_with_password("quota@example.com", PASSWORD, "Quota")
    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    monkeypatch.setattr(vigzone_ai, "USAGE_RESERVE_TOKENS", 100)
    monkeypatch.setenv("FREE_DAILY_TOKEN_LIMIT", "1000")

    reservation = vigzone_ai.assert_user_can_chat(
        user,
        has_own_key=False,
        estimated_request_tokens=200,
    )
    pending = vigzone_ai.get_user_daily_usage(user, has_own_key=False)
    assert pending["used_today"] == 0
    assert pending["reserved_today"] == 300
    assert pending["remaining_today"] == 700

    usage_id = vigzone_ai.track_token_usage(
        user["id"],
        120,
        80,
        estimated=False,
        quota_reservation=reservation,
    )
    assert usage_id
    assert reservation["finalized"] is True

    usage = vigzone_ai.get_user_daily_usage(user, has_own_key=False)
    assert usage["used_today"] == 200
    assert usage["reserved_today"] == 0
    assert usage["remaining_today"] == 800
    assert usage["tracking_error"] is False
    with auth_db._connect() as conn:
        stored = conn.execute(
            "SELECT status, actual_tokens FROM token_quota_reservations WHERE reservation_id = ?",
            (reservation["reservation_id"],),
        ).fetchone()
    assert stored["status"] == "finalized"
    assert stored["actual_tokens"] == 200


def test_failed_request_releases_reserved_tokens(auth_db, monkeypatch):
    import vigzone_ai

    user = auth_db.create_user_with_password("release@example.com", PASSWORD, "Release")
    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    monkeypatch.setattr(vigzone_ai, "USAGE_RESERVE_TOKENS", 100)
    monkeypatch.setenv("FREE_DAILY_TOKEN_LIMIT", "500")

    reservation = vigzone_ai.assert_user_can_chat(user, False, 200)
    assert vigzone_ai.get_user_daily_usage(user, False)["reserved_today"] == 300
    vigzone_ai.release_token_reservation(reservation)
    usage = vigzone_ai.get_user_daily_usage(user, False)
    assert usage["used_today"] == 0
    assert usage["reserved_today"] == 0
    assert usage["remaining_today"] == 500


def test_accepted_but_interrupted_request_is_estimated_not_forgotten(auth_db, monkeypatch):
    import vigzone_ai

    user = auth_db.create_user_with_password("interrupted@example.com", PASSWORD, "Interrupted")
    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    monkeypatch.setattr(vigzone_ai, "USAGE_RESERVE_TOKENS", 100)
    monkeypatch.setenv("FREE_DAILY_TOKEN_LIMIT", "1000")

    reservation = vigzone_ai.assert_user_can_chat(user, False, 200)
    reservation["provider_accepted"] = True
    vigzone_ai.release_token_reservation(reservation)

    usage = vigzone_ai.get_user_daily_usage(user, False)
    assert usage["used_today"] == 300
    assert usage["reserved_today"] == 0
    assert usage["estimated_request_count_today"] == 1
    assert reservation["finalized"] is True


def test_atomic_reservations_enforce_the_daily_cap(auth_db, monkeypatch):
    import vigzone_ai

    user = auth_db.create_user_with_password("limited-tokens@example.com", PASSWORD, "Limited")
    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    monkeypatch.setattr(vigzone_ai, "USAGE_RESERVE_TOKENS", 100)
    monkeypatch.setenv("FREE_DAILY_TOKEN_LIMIT", "500")

    first = vigzone_ai.assert_user_can_chat(user, False, 300)
    with pytest.raises(vigzone_ai.UsageLimitError, match="FREE daily token quota"):
        vigzone_ai.assert_user_can_chat(user, False, 1)
    vigzone_ai.release_token_reservation(first)


def test_team_seats_share_one_owner_quota(auth_db, monkeypatch):
    import vigzone_ai

    owner = auth_db.create_user_with_password("owner@example.com", PASSWORD, "Owner")
    member = auth_db.create_user_with_password("member@example.com", PASSWORD, "Member")
    with auth_db._connect() as conn:
        conn.execute("UPDATE users SET plan = 'team' WHERE id = ?", (owner["id"],))
    team = auth_db.ensure_team_for_owner(owner["id"], "Owner")
    with auth_db._connect() as conn:
        conn.execute(
            "INSERT INTO team_members(team_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
            (team["id"], member["id"], "2026-08-09T00:00:00+00:00"),
        )
    owner = auth_db.get_user_by_id(owner["id"])
    member = auth_db.get_user_by_id(member["id"])

    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    monkeypatch.setenv("TEAM_DAILY_TOKEN_LIMIT", "1000")
    vigzone_ai.track_token_usage(owner["id"], 100, 50, estimated=False)
    vigzone_ai.track_token_usage(member["id"], 200, 50, estimated=False)

    owner_usage = vigzone_ai.get_user_daily_usage(owner, False)
    member_usage = vigzone_ai.get_user_daily_usage(member, False)
    assert owner_usage["used_today"] == 400
    assert member_usage["used_today"] == 400
    assert owner_usage["quota_shared"] is True
    assert member_usage["quota_scope"] == "team"
    assert owner_usage["remaining_today"] == 600
    assert member_usage["remaining_today"] == 600


def test_admin_is_unlimited_but_usage_is_recorded(auth_db, monkeypatch):
    import vigzone_ai

    admin = auth_db.create_user_with_password(
        "bhashithanavod808@gmail.com", PASSWORD, "Founder"
    )
    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    reservation = vigzone_ai.assert_user_can_chat(admin, False, 10_000_000)
    assert reservation["active"] is False
    assert reservation["daily_limit"] == 0

    vigzone_ai.track_token_usage(admin["id"], 500, 100, estimated=False)
    usage = vigzone_ai.get_user_daily_usage(admin, False)
    assert usage["display_plan"] == "admin"
    assert usage["quota_unlimited"] is True
    assert usage["used_today"] == 600
    assert usage["remaining_today"] is None
    assert usage["is_limited"] is False


def test_usage_api_exposes_the_same_authoritative_plan_fields(client, auth_db, monkeypatch):
    import app
    import vigzone_ai

    response = client.post(
        "/api/auth/signup",
        json={"email": "api-quota@example.com", "password": PASSWORD, "name": "API Quota"},
    )
    assert response.status_code == 200
    user_id = response.json()["user"]["id"]
    with auth_db._connect() as conn:
        conn.execute("UPDATE users SET plan = 'pro' WHERE id = ?", (user_id,))

    monkeypatch.setattr(app, "IS_TESTING", False)
    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    monkeypatch.setenv("PRO_DAILY_TOKEN_LIMIT", "250000")
    usage = client.get("/api/me/usage")
    assert usage.status_code == 200
    body = usage.json()
    assert body["effective_plan"] == "pro"
    assert body["display_plan"] == "pro"
    assert body["quota_label"] == "PRO daily account quota"
    assert body["daily_limit"] == 250_000
    assert body["quota_shared"] is False
    assert body["plan_message_limit"] is None
    assert body["tracking_error"] is False
