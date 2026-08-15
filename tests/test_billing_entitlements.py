from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time

import billing


PASSWORD = "StrongPassword!123"


def _event(
    event_id: str,
    event_type: str,
    *,
    user_id: int,
    email: str,
    subscription_id: str = "sub_vigzone_1",
    price_id: str | None = "pri_pro",
    status: str = "active",
    occurred_at: str = "2026-08-09T04:33:00Z",
) -> dict:
    data = {
        "id": subscription_id,
        "customer_id": "ctm_vigzone_1",
        "status": status,
        "custom_data": {
            "vigzone_user_id": str(user_id),
            "vigzone_email": email,
        },
    }
    if price_id:
        data["items"] = [{"price": {"id": price_id, "product_id": "pro_catalog"}}]
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "data": data,
    }


def _catalog() -> dict:
    return {
        "pro": {"price_ids": ["pri_pro"], "product_ids": ["pro_catalog"]},
        "team": {"price_ids": ["pri_team"], "product_ids": ["team_catalog"]},
    }


def _signed(raw: bytes, secret: str) -> str:
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode(), timestamp.encode() + b":" + raw, hashlib.sha256).hexdigest()
    return f"ts={timestamp};h1={digest}"


def test_plan_matrix_and_founder_admin_access(auth_db):
    free = {"plan": "free", "role": "user", "is_admin": False}
    pro = {"plan": "pro", "role": "user", "is_admin": False}
    team = {"plan": "team", "role": "user", "is_admin": False}
    assert billing.entitlement_snapshot(free)["limits"]["messages_per_day"] == 50
    assert not billing.model_allowed(free, "llama-3.3-70b-versatile")
    assert billing.model_allowed(free, "openai/gpt-oss-20b")
    assert billing.feature_allowed(pro, "website_studio")
    assert billing.model_allowed(pro, "qwen/qwen3.6-27b")
    assert billing.feature_allowed(team, "custom_ai_persona")
    assert billing.entitlement_snapshot(team)["limits"]["team_seats"] == 5

    founder = auth_db.create_user_with_password(
        "bhashithanavod808@gmail.com", PASSWORD, "Founder"
    )
    assert founder["is_admin"] is True
    token = auth_db.create_session(founder["id"])
    refreshed = auth_db.get_user_by_session(token)
    assert refreshed["is_admin"] is True
    assert refreshed["entitlements"]["display_plan"] == "admin"
    assert refreshed["entitlements"]["effective_plan"] == "team"
    assert refreshed["entitlements"]["can_upgrade"] is False
    assert all(refreshed["entitlements"]["features"].values())


def test_free_message_limit_is_atomic_and_exact(auth_db):
    user = auth_db.create_user_with_password("limited@example.com", PASSWORD, "Limited")
    for remaining in range(49, -1, -1):
        assert auth_db.consume_daily_message(user["id"], 50) == remaining
    assert auth_db.consume_daily_message(user["id"], 50) is None
    assert auth_db.get_daily_message_count(user["id"]) == 50


def test_paddle_events_are_durable_idempotent_and_ordered(auth_db):
    user = auth_db.create_user_with_password("buyer@example.com", PASSWORD, "Buyer")
    created = _event("evt_created", "subscription.created", user_id=user["id"], email=user["email"])
    result = billing.process_paddle_event(auth_db.DB_PATH, created, _catalog())
    assert result["plan"] == "pro"
    assert billing.process_paddle_event(auth_db.DB_PATH, created, _catalog())["action"] == "duplicate"

    team = _event(
        "evt_team", "subscription.updated", user_id=user["id"], email=user["email"],
        price_id="pri_team", occurred_at="2026-08-09T05:00:00Z",
    )
    assert billing.process_paddle_event(auth_db.DB_PATH, team, _catalog())["plan"] == "team"

    stale_cancel = _event(
        "evt_stale", "subscription.canceled", user_id=user["id"], email=user["email"],
        price_id=None, status="canceled", occurred_at="2026-08-09T04:40:00Z",
    )
    stale_result = billing.process_paddle_event(auth_db.DB_PATH, stale_cancel, _catalog())
    assert stale_result["action"] == "stale"

    with sqlite3.connect(auth_db.DB_PATH) as conn:
        assert conn.execute("SELECT plan FROM users WHERE id = ?", (user["id"],)).fetchone()[0] == "team"
        assert conn.execute("SELECT COUNT(*) FROM billing_webhook_events").fetchone()[0] == 3


def test_canceling_one_subscription_keeps_another_active_plan(auth_db):
    user = auth_db.create_user_with_password("multi@example.com", PASSWORD, "Multi")
    first = _event("evt_pro", "subscription.created", user_id=user["id"], email=user["email"], subscription_id="sub_pro")
    second = _event(
        "evt_team", "subscription.created", user_id=user["id"], email=user["email"],
        subscription_id="sub_team", price_id="pri_team", occurred_at="2026-08-09T04:34:00Z",
    )
    billing.process_paddle_event(auth_db.DB_PATH, first, _catalog())
    assert billing.process_paddle_event(auth_db.DB_PATH, second, _catalog())["plan"] == "team"
    cancel_team = _event(
        "evt_cancel_team", "subscription.canceled", user_id=user["id"], email=user["email"],
        subscription_id="sub_team", price_id=None, status="canceled", occurred_at="2026-08-09T05:00:00Z",
    )
    assert billing.process_paddle_event(auth_db.DB_PATH, cancel_team, _catalog())["plan"] == "pro"


def test_one_time_transaction_does_not_grant_recurring_membership(auth_db):
    user = auth_db.create_user_with_password("one-time@example.com", PASSWORD, "One Time")
    event = _event(
        "evt_one_time", "transaction.completed", user_id=user["id"], email=user["email"]
    )
    event["data"]["id"] = "txn_one_time"
    event["data"].pop("subscription_id", None)
    result = billing.process_paddle_event(auth_db.DB_PATH, event, _catalog())
    assert result["action"] == "ignored"
    session = auth_db.create_session(user["id"])
    assert auth_db.get_user_by_session(session)["plan"] == "free"


def test_free_model_fallbacks_never_escape_fast_model_allowlist():
    import vigzone_ai

    assert vigzone_ai._model_candidates(
        vigzone_ai.FAST_MODEL,
        allowed_models={vigzone_ai.FAST_MODEL},
    ) == [vigzone_ai.FAST_MODEL]


def test_webhook_rejects_bad_signatures_and_activates_exact_price(client, auth_db, monkeypatch):
    import app

    user = auth_db.create_user_with_password("api-buyer@example.com", PASSWORD, "API Buyer")
    secret = "unit-test-webhook-signing-secret"
    monkeypatch.setattr(app, "PADDLE_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(app, "PADDLE_PRO_PRICE_ID", "pri_pro")
    monkeypatch.setattr(app, "PADDLE_TEAM_PRICE_ID", "pri_team")
    monkeypatch.setattr(app, "PADDLE_PRO_PRODUCT_ID", "pro_catalog")
    monkeypatch.setattr(app, "PADDLE_TEAM_PRODUCT_ID", "team_catalog")
    raw = json.dumps(
        _event("evt_api", "subscription.created", user_id=user["id"], email=user["email"]),
        separators=(",", ":"),
    ).encode()

    rejected = client.post(
        "/api/billing/paddle/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "Paddle-Signature": "ts=1;h1=bad"},
    )
    assert rejected.status_code == 401

    accepted = client.post(
        "/api/billing/paddle/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "Paddle-Signature": _signed(raw, secret)},
    )
    assert accepted.status_code == 200
    assert accepted.json()["plan"] == "pro"
    session = auth_db.create_session(user["id"])
    me = client.get("/api/auth/me", cookies={auth_db.SESSION_COOKIE_NAME: session})
    assert me.json()["user"]["entitlements"]["effective_plan"] == "pro"


def test_unrecognized_paid_item_fails_loudly_instead_of_granting_pro(client, auth_db, monkeypatch):
    import app

    user = auth_db.create_user_with_password("wrong-price@example.com", PASSWORD, "Wrong Price")
    secret = "unit-test-webhook-signing-secret"
    monkeypatch.setattr(app, "PADDLE_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(app, "PADDLE_PRO_PRICE_ID", "pri_pro")
    monkeypatch.setattr(app, "PADDLE_TEAM_PRICE_ID", "pri_team")
    raw = json.dumps(
        _event("evt_wrong", "subscription.created", user_id=user["id"], email=user["email"], price_id="pri_unknown"),
        separators=(",", ":"),
    ).encode()
    response = client.post(
        "/api/billing/paddle/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "Paddle-Signature": _signed(raw, secret)},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "unrecognized_catalog_item"
    session = auth_db.create_session(user["id"])
    me = client.get("/api/auth/me", cookies={auth_db.SESSION_COOKIE_NAME: session})
    assert me.json()["user"]["plan"] == "free"
