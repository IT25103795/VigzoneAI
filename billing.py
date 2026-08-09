"""Vigzone plans, entitlements, and durable Paddle subscription processing."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Iterable


VALID_PLANS = ("free", "pro", "team")
PLAN_RANK = {"free": 0, "pro": 1, "team": 2}
ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing", "past_due"}
PREMIUM_CHAT_MODES = {"website", "code", "business", "voice"}
FREE_MODEL_IDS = {
    "openai/gpt-oss-20b",
}

_FEATURES = {
    "free": {
        "advanced_models": False,
        "web_search": True,
        "image_search": False,
        "file_studio": True,
        "website_studio": False,
        "image_generation": False,
        "voice": False,
        "premium_modes": False,
        "priority_support": False,
        "dedicated_support": False,
        "early_access": False,
        "team_workspace": False,
        "usage_analytics": False,
        "custom_ai_persona": False,
    },
    "pro": {
        "advanced_models": True,
        "web_search": True,
        "image_search": True,
        "file_studio": True,
        "website_studio": True,
        "image_generation": True,
        "voice": True,
        "premium_modes": True,
        "priority_support": True,
        "dedicated_support": False,
        "early_access": True,
        "team_workspace": False,
        "usage_analytics": False,
        "custom_ai_persona": False,
    },
    "team": {
        "advanced_models": True,
        "web_search": True,
        "image_search": True,
        "file_studio": True,
        "website_studio": True,
        "image_generation": True,
        "voice": True,
        "premium_modes": True,
        "priority_support": True,
        "dedicated_support": True,
        "early_access": True,
        "team_workspace": True,
        "usage_analytics": True,
        "custom_ai_persona": True,
    },
}


def normalize_plan(value: Any) -> str:
    plan = str(value or "free").strip().lower()
    return plan if plan in VALID_PLANS else "free"


def effective_plan(user: dict) -> str:
    if bool(user.get("is_admin")) or user.get("role") == "admin":
        return "team"
    # A seat in an active TEAM subscription grants the same product access as
    # the owner.  Authentication attaches this server-verified marker only
    # when the owning account still has TEAM (or admin) access.
    if bool(user.get("team_active")):
        return "team"
    return normalize_plan(user.get("plan"))


def entitlement_snapshot(user: dict) -> dict:
    billed_plan = normalize_plan(user.get("plan"))
    plan = effective_plan(user)
    is_admin = bool(user.get("is_admin")) or user.get("role") == "admin"
    return {
        "billing_plan": billed_plan,
        "effective_plan": plan,
        "display_plan": "admin" if is_admin else plan,
        "badge": "ADMIN" if is_admin else (plan.upper() if plan != "free" else ""),
        "is_admin": is_admin,
        "can_upgrade": not is_admin and plan != "team",
        "features": dict(_FEATURES[plan]),
        "limits": {
            "messages_per_day": 50 if plan == "free" else None,
            "team_seats": 5 if plan == "team" else 1,
        },
        "team": {
            "id": user.get("team_id"),
            "name": user.get("team_name") or "",
            "role": user.get("team_role") or "",
            "owner_id": user.get("team_owner_id"),
            "active": bool(user.get("team_active")),
        },
    }


def feature_allowed(user: dict, feature: str) -> bool:
    return bool(entitlement_snapshot(user)["features"].get(feature, False))


def model_allowed(user: dict, model: str) -> bool:
    if effective_plan(user) != "free":
        return True
    return str(model or "").strip().lower() in FREE_MODEL_IDS


def chat_mode_allowed(user: dict, mode: str | None) -> bool:
    selected = str(mode or "general").strip().lower()
    return selected not in PREMIUM_CHAT_MODES or feature_allowed(user, "premium_modes")


def verify_paddle_signature(
    secret: str,
    signature_header: str,
    raw_body: bytes,
    *,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> tuple[bool, str]:
    """Verify a Paddle Billing signature against the untouched request body."""
    if not secret:
        return False, "webhook_not_configured"
    values: dict[str, list[str]] = {}
    for part in str(signature_header or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        values.setdefault(key, []).append(value)
    timestamp = (values.get("ts") or [""])[0]
    signatures = values.get("h1") or []
    if not timestamp or not signatures:
        return False, "missing_signature"
    try:
        signed_at = int(timestamp)
    except (TypeError, ValueError):
        return False, "invalid_signature_timestamp"
    current = int(time.time()) if now is None else int(now)
    if tolerance_seconds > 0 and abs(current - signed_at) > tolerance_seconds:
        return False, "expired_signature"
    expected = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b":" + raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        return False, "signature_mismatch"
    return True, "ok"


def _iso_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _iter_line_items(data: dict) -> Iterable[dict]:
    for item in data.get("items") or []:
        if isinstance(item, dict):
            yield item
    details = _dict(data.get("details"))
    for item in details.get("line_items") or []:
        if isinstance(item, dict):
            yield item
    for item in data.get("line_items") or []:
        if isinstance(item, dict):
            yield item


def parse_paddle_event(event: dict) -> dict:
    data = _dict(event.get("data")) or _dict(event)
    event_type = str(event.get("event_type") or event.get("alert_name") or "").strip().lower().replace("_", ".")
    custom = _dict(data.get("custom_data"))
    customer = _dict(data.get("customer"))
    prices: set[str] = set()
    products: set[str] = set()
    for item in _iter_line_items(data):
        price = _dict(item.get("price"))
        price_id = item.get("price_id") or price.get("id")
        product_id = (
            item.get("product_id")
            or _dict(item.get("product")).get("id")
            or price.get("product_id")
            or _dict(price.get("product")).get("id")
        )
        if price_id:
            prices.add(str(price_id))
        if product_id:
            products.add(str(product_id))
    if data.get("price_id"):
        prices.add(str(data["price_id"]))
    if data.get("product_id"):
        products.add(str(data["product_id"]))

    user_id = custom.get("vigzone_user_id") or custom.get("user_id")
    try:
        user_id = int(user_id) if user_id not in (None, "") else None
    except (TypeError, ValueError):
        user_id = None
    email = (
        custom.get("vigzone_email")
        or custom.get("email")
        or customer.get("email")
        or data.get("email")
        or ""
    )
    event_id = str(event.get("event_id") or event.get("notification_id") or data.get("id") or "").strip()
    subscription_id = data.get("subscription_id")
    if event_type.startswith("subscription."):
        subscription_id = data.get("id") or subscription_id
    transaction_id = data.get("id") if event_type.startswith("transaction.") else data.get("transaction_id")
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": _iso_timestamp(event.get("occurred_at") or data.get("updated_at") or data.get("created_at")),
        "data": data,
        "user_id": user_id,
        "email": str(email).strip().lower(),
        "customer_id": str(data.get("customer_id") or customer.get("id") or "").strip(),
        "subscription_id": str(subscription_id or "").strip(),
        "transaction_id": str(transaction_id or "").strip(),
        "status": str(data.get("status") or "").strip().lower(),
        "price_ids": prices,
        "product_ids": products,
        "current_period_end": str(data.get("current_billing_period", {}).get("ends_at") or data.get("next_billed_at") or ""),
    }


def _catalog_values(catalog: dict, plan: str, kind: str) -> set[str]:
    configured = _dict(catalog.get(plan)).get(kind) or []
    if isinstance(configured, str):
        configured = [configured]
    return {str(value).strip() for value in configured if str(value).strip()}


def resolve_catalog_plan(parsed: dict, catalog: dict) -> str | None:
    matches: list[str] = []
    for plan in ("pro", "team"):
        if parsed["price_ids"] & _catalog_values(catalog, plan, "price_ids"):
            matches.append(plan)
        elif parsed["product_ids"] & _catalog_values(catalog, plan, "product_ids"):
            matches.append(plan)
    return max(matches, key=lambda item: PLAN_RANK[item]) if matches else None


def _event_subscription_status(parsed: dict) -> str:
    event_type = parsed["event_type"]
    if event_type == "subscription.canceled":
        return "canceled"
    if event_type == "subscription.paused":
        return "paused"
    if event_type in {"subscription.activated", "subscription.resumed"}:
        return "active"
    if event_type == "transaction.completed":
        return "active"
    return parsed["status"] or ("active" if event_type in {"subscription.created", "subscription.updated"} else "")


def _recompute_user_plan(conn: sqlite3.Connection, user_id: int) -> str:
    active = conn.execute(
        "SELECT plan FROM billing_subscriptions WHERE user_id = ? AND status IN ('active', 'trialing', 'past_due')",
        (user_id,),
    ).fetchall()
    plan = max(
        (normalize_plan(row["plan"]) for row in active),
        key=lambda value: PLAN_RANK[value],
        default="free",
    )
    conn.execute(
        "UPDATE users SET plan = ?, updated_at = ? WHERE id = ?",
        (plan, _iso_timestamp(None), user_id),
    )
    return plan


def recompute_user_plan(db_path: str, user_id: int) -> str:
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        plan = _recompute_user_plan(conn, int(user_id))
        conn.commit()
        return plan
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_paddle_event(db_path: str, event: dict, catalog: dict) -> dict:
    """Apply one Paddle event transactionally and recompute the user's best plan."""
    parsed = parse_paddle_event(event)
    if not parsed["event_id"]:
        return {"ok": False, "error": "missing_event_id"}
    supported = {
        "subscription.created", "subscription.updated", "subscription.activated",
        "subscription.resumed", "subscription.paused", "subscription.canceled",
        "transaction.completed",
    }
    if parsed["event_type"] not in supported:
        return {"ok": True, "action": "ignored", "event_type": parsed["event_type"]}

    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        prior_event = conn.execute(
            "SELECT processing_status FROM billing_webhook_events WHERE event_id = ?",
            (parsed["event_id"],),
        ).fetchone()
        if prior_event and prior_event["processing_status"] not in {"unlinked", "failed"}:
            conn.rollback()
            return {"ok": True, "action": "duplicate", "event_id": parsed["event_id"]}

        if not prior_event:
            conn.execute(
                """INSERT INTO billing_webhook_events
                   (event_id, event_type, occurred_at, processing_status, payload_json, processed_at)
                   VALUES (?, ?, ?, 'received', ?, ?)""",
                (parsed["event_id"], parsed["event_type"], parsed["occurred_at"], json.dumps(event), _iso_timestamp(None)),
            )

        existing_sub = None
        if parsed["subscription_id"]:
            existing_sub = conn.execute(
                "SELECT * FROM billing_subscriptions WHERE subscription_id = ?",
                (parsed["subscription_id"],),
            ).fetchone()

        user = None
        if parsed["user_id"] is not None:
            user = conn.execute("SELECT id, email FROM users WHERE id = ?", (parsed["user_id"],)).fetchone()
        if not user and existing_sub:
            user = conn.execute("SELECT id, email FROM users WHERE id = ?", (existing_sub["user_id"],)).fetchone()
        if not user and parsed["customer_id"]:
            user = conn.execute(
                """SELECT u.id, u.email FROM billing_subscriptions b
                   JOIN users u ON u.id = b.user_id
                   WHERE b.customer_id = ? ORDER BY b.updated_at DESC LIMIT 1""",
                (parsed["customer_id"],),
            ).fetchone()
        if not user and parsed["email"]:
            user = conn.execute("SELECT id, email FROM users WHERE lower(email) = ?", (parsed["email"],)).fetchone()
        if not user:
            conn.execute(
                "UPDATE billing_webhook_events SET processing_status = 'unlinked', error = 'user_not_found' WHERE event_id = ?",
                (parsed["event_id"],),
            )
            conn.commit()
            return {"ok": False, "error": "user_not_found", "event_id": parsed["event_id"]}

        plan = resolve_catalog_plan(parsed, catalog)
        if not plan and existing_sub:
            plan = normalize_plan(existing_sub["plan"])
        if not plan:
            conn.execute(
                "UPDATE billing_webhook_events SET user_id = ?, processing_status = 'failed', error = 'unrecognized_catalog_item' WHERE event_id = ?",
                (user["id"], parsed["event_id"]),
            )
            conn.commit()
            return {"ok": False, "error": "unrecognized_catalog_item", "event_id": parsed["event_id"]}

        # A transaction without a subscription is a one-time purchase and must
        # never create permanent recurring membership access.
        subscription_id = parsed["subscription_id"]
        if not subscription_id:
            conn.execute(
                "UPDATE billing_webhook_events SET user_id = ?, processing_status = 'ignored', error = 'missing_subscription_id' WHERE event_id = ?",
                (user["id"], parsed["event_id"]),
            )
            conn.commit()
            return {"ok": True, "action": "ignored", "reason": "missing_subscription_id"}

        if existing_sub and str(existing_sub["last_event_at"]) > parsed["occurred_at"]:
            conn.execute(
                "UPDATE billing_webhook_events SET user_id = ?, processing_status = 'stale' WHERE event_id = ?",
                (user["id"], parsed["event_id"]),
            )
            conn.commit()
            return {"ok": True, "action": "stale", "plan": normalize_plan(existing_sub["plan"])}

        status = _event_subscription_status(parsed)
        if not status:
            status = str(existing_sub["status"] if existing_sub else "inactive")
        first_price = sorted(parsed["price_ids"])[0] if parsed["price_ids"] else (existing_sub["price_id"] if existing_sub else "")
        first_product = sorted(parsed["product_ids"])[0] if parsed["product_ids"] else (existing_sub["product_id"] if existing_sub else "")
        conn.execute(
            """INSERT INTO billing_subscriptions
               (subscription_id, user_id, customer_id, plan, status, price_id, product_id,
                current_period_end, last_event_id, last_event_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(subscription_id) DO UPDATE SET
                 user_id=excluded.user_id, customer_id=COALESCE(NULLIF(excluded.customer_id, ''), billing_subscriptions.customer_id),
                 plan=excluded.plan, status=excluded.status,
                 price_id=COALESCE(NULLIF(excluded.price_id, ''), billing_subscriptions.price_id),
                 product_id=COALESCE(NULLIF(excluded.product_id, ''), billing_subscriptions.product_id),
                 current_period_end=COALESCE(NULLIF(excluded.current_period_end, ''), billing_subscriptions.current_period_end),
                 last_event_id=excluded.last_event_id, last_event_at=excluded.last_event_at, updated_at=excluded.updated_at""",
            (
                subscription_id, user["id"], parsed["customer_id"], plan, status,
                first_price, first_product, parsed["current_period_end"], parsed["event_id"],
                parsed["occurred_at"], _iso_timestamp(None),
            ),
        )
        effective_billing_plan = _recompute_user_plan(conn, int(user["id"]))
        now_iso = _iso_timestamp(None)
        conn.execute(
            "UPDATE billing_webhook_events SET user_id = ?, subscription_id = ?, processing_status = 'processed', processed_at = ?, error = NULL WHERE event_id = ?",
            (user["id"], subscription_id, now_iso, parsed["event_id"]),
        )
        conn.commit()
        return {
            "ok": True,
            "action": "processed",
            "event_id": parsed["event_id"],
            "user_id": int(user["id"]),
            "plan": effective_billing_plan,
            "subscription_status": status,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
