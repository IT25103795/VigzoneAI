"""End-to-end TEAM seats, sharing, persona, analytics, and support tests."""

from __future__ import annotations

import asyncio
import time

import pytest


PASSWORD = "StrongPassword!123"


def _set_plan(auth, user_id: int, plan: str) -> None:
    with auth._connect() as conn:
        conn.execute("UPDATE users SET plan = ?, updated_at = ? WHERE id = ?", (plan, auth._utc_now(), user_id))


def _cookie(auth, user_id: int) -> dict[str, str]:
    return {auth.SESSION_COOKIE_NAME: auth.create_session(user_id)}


def test_team_invitation_grants_active_seat_and_downgrade_revokes_it(auth_db):
    owner = auth_db.create_user_with_password("owner@example.com", PASSWORD, "Owner")
    member = auth_db.create_user_with_password("member@example.com", PASSWORD, "Member")
    outsider = auth_db.create_user_with_password("outsider@example.com", PASSWORD, "Outsider")
    _set_plan(auth_db, owner["id"], "team")

    team = auth_db.ensure_team_for_owner(owner["id"], owner["name"])
    invitation = auth_db.create_team_invitation(owner["id"], member["email"])
    joined = auth_db.accept_team_invitation(member["id"], invitation["token"])
    assert joined["team_id"] == team["id"]

    refreshed_member = auth_db.get_user_by_session(auth_db.create_session(member["id"]))
    assert refreshed_member["team_active"] is True
    assert refreshed_member["entitlements"]["effective_plan"] == "team"
    assert refreshed_member["entitlements"]["badge"] == "TEAM"

    shared = auth_db.create_workspace(owner["id"], "Launch", "Shared launch plan", shared=True)
    auth_db.add_workspace_note(member["id"], shared["id"], "Owner", "Member-authored shared context")
    assert "Member-authored shared context" in auth_db.get_workspace_context(owner["id"], shared["id"])
    assert auth_db.list_workspace_notes(member["id"], shared["id"])[0]["user_id"] == member["id"]
    with pytest.raises(auth_db.AuthError):
        auth_db.list_workspace_notes(outsider["id"], shared["id"])

    # Paddle downgrade is reflected on the very next authenticated request.
    _set_plan(auth_db, owner["id"], "free")
    downgraded_member = auth_db.get_user_by_session(auth_db.create_session(member["id"]))
    assert downgraded_member.get("team_active") is not True
    assert downgraded_member["entitlements"]["effective_plan"] == "free"
    assert shared["id"] not in {row["id"] for row in auth_db.list_workspaces(member["id"])}

    # An inactive membership must not trap the account or prevent accepting a
    # future seat on a different active team.
    auth_db.leave_team(member["id"])
    next_owner = auth_db.create_user_with_password("next-owner@example.com", PASSWORD, "Next Owner")
    _set_plan(auth_db, next_owner["id"], "team")
    auth_db.ensure_team_for_owner(next_owner["id"])
    next_invitation = auth_db.create_team_invitation(next_owner["id"], member["email"])
    next_membership = auth_db.accept_team_invitation(member["id"], next_invitation["token"])
    assert next_membership["team_name"] == "Next Owner's Team"


def test_team_seat_limit_email_binding_and_owner_controls(auth_db):
    owner = auth_db.create_user_with_password("seat-owner@example.com", PASSWORD, "Seat Owner")
    _set_plan(auth_db, owner["id"], "team")
    auth_db.ensure_team_for_owner(owner["id"])

    wrong = auth_db.create_user_with_password("wrong@example.com", PASSWORD, "Wrong")
    invite = auth_db.create_team_invitation(owner["id"], "intended@example.com")
    with pytest.raises(auth_db.AuthError, match="email address that was invited"):
        auth_db.accept_team_invitation(wrong["id"], invite["token"])
    # The still-pending invitation correctly reserves a seat; revoke it before
    # filling all four member seats below.
    auth_db.revoke_team_invitation(owner["id"], invite["id"])

    invited_users = []
    for index in range(4):
        user = auth_db.create_user_with_password(f"seat{index}@example.com", PASSWORD, f"Seat {index}")
        invited_users.append(user)
        created = auth_db.create_team_invitation(owner["id"], user["email"])
        auth_db.accept_team_invitation(user["id"], created["token"])
    assert auth_db.get_team_details(owner["id"])["team"]["seats_used"] == 5
    with pytest.raises(auth_db.AuthError, match="5 TEAM seats"):
        auth_db.create_team_invitation(owner["id"], "sixth@example.com")

    with pytest.raises(auth_db.AuthError, match="owner cannot be removed"):
        auth_db.remove_team_member(owner["id"], owner["id"])
    auth_db.remove_team_member(owner["id"], invited_users[-1]["id"])
    assert auth_db.get_team_details(owner["id"])["team"]["seats_used"] == 4


def test_team_persona_and_analytics_are_real(auth_db):
    owner = auth_db.create_user_with_password("persona-owner@example.com", PASSWORD, "Persona Owner")
    member = auth_db.create_user_with_password("persona-member@example.com", PASSWORD, "Persona Member")
    _set_plan(auth_db, owner["id"], "team")
    auth_db.ensure_team_for_owner(owner["id"])
    invitation = auth_db.create_team_invitation(owner["id"], member["email"])
    auth_db.accept_team_invitation(member["id"], invitation["token"])

    auth_db.update_team_profile(
        owner["id"],
        "Vigzone Launch Team",
        "Nova",
        "Be concise, use our launch terminology, and finish with owners and next actions.",
    )
    context = auth_db.get_team_persona_context(member["id"])
    assert "Persona name: Nova" in context
    assert "owners and next actions" in context
    with pytest.raises(auth_db.AuthError, match="Only the team owner"):
        auth_db.update_team_profile(member["id"], "Hijack", None, None)

    with auth_db._connect() as conn:
        conn.execute(
            """INSERT INTO token_usage
               (user_id, prompt_tokens, completion_tokens, total_tokens, ts, model, latency_ms)
               VALUES (?, 10, 20, 30, ?, 'openai/gpt-oss-120b', 250)""",
            (member["id"], int(time.time())),
        )
    analytics = auth_db.get_team_analytics(owner["id"])
    assert analytics["totals"]["request_count"] == 1
    assert analytics["totals"]["total_tokens"] == 30
    assert next(row for row in analytics["members"] if row["id"] == member["id"])["average_latency_ms"] == 250


def test_support_levels_and_admin_response_flow(auth_db):
    free = auth_db.create_user_with_password("support-free@example.com", PASSWORD, "Free")
    pro = auth_db.create_user_with_password("support-pro@example.com", PASSWORD, "Pro")
    team = auth_db.create_user_with_password("support-team@example.com", PASSWORD, "Team")
    _set_plan(auth_db, pro["id"], "pro")
    _set_plan(auth_db, team["id"], "team")

    free_ticket = auth_db.create_support_ticket({**free, "plan": "free"}, "Free question", "Please help with this standard issue.")
    pro_ticket = auth_db.create_support_ticket({**pro, "plan": "pro"}, "Pro question", "Please help with this priority issue.")
    team_ticket = auth_db.create_support_ticket({**team, "plan": "team"}, "Team question", "Please help with this dedicated issue.")
    assert [free_ticket["support_level"], pro_ticket["support_level"], team_ticket["support_level"]] == ["standard", "priority", "dedicated"]
    queue = auth_db.list_admin_support_tickets()
    assert queue[0]["id"] == team_ticket["id"]
    updated = auth_db.update_support_ticket(team_ticket["id"], "resolved", "Resolved by the Vigzone team.")
    assert updated["status"] == "resolved"
    assert auth_db.list_support_tickets(team["id"])[0]["admin_response"].startswith("Resolved")


def test_team_api_gates_and_image_attachment_gate(client, auth_db, monkeypatch):
    free = auth_db.create_user_with_password("api-free@example.com", PASSWORD, "API Free")
    team = auth_db.create_user_with_password("api-team@example.com", PASSWORD, "API Team")
    _set_plan(auth_db, team["id"], "team")
    free_cookie = _cookie(auth_db, free["id"])
    team_cookie = _cookie(auth_db, team["id"])

    assert client.get("/api/team", cookies=free_cookie).status_code == 403
    assert client.post(
        "/api/workspaces",
        cookies=free_cookie,
        json={"name": "Bypass", "description": "Must not unlock code mode", "mode": "code"},
    ).status_code == 403
    assert client.get("/api/team", cookies=team_cookie).status_code == 200
    assert client.get("/api/team/analytics", cookies=team_cookie).status_code == 200
    invite_response = client.post(
        "/api/team/invitations",
        cookies=team_cookie,
        json={"email": "api-invitee@example.com"},
    )
    assert invite_response.status_code == 200
    assert "/chat#team_invite=" in invite_response.json()["invite_url"]
    with auth_db._connect() as conn:
        stored_hash = conn.execute(
            "SELECT token_hash FROM team_invitations WHERE email = 'api-invitee@example.com'"
        ).fetchone()["token_hash"]
    assert stored_hash not in invite_response.json()["invite_url"]
    assert client.get("/api/early-access", cookies=free_cookie).status_code == 403
    assert client.get("/api/early-access", cookies=team_cookie).json()["enabled"] is True

    response = client.post(
        "/api/chat/sync",
        cookies=free_cookie,
        json={
            "model": "openai/gpt-oss-20b",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                ],
            }],
        },
    )
    assert response.status_code == 403
    assert "Qwen vision" in response.json()["detail"]

    # No provider request is made when a FREE user hits the paid image-search API.
    async def should_not_run(*args, **kwargs):
        raise AssertionError("image provider should not run for FREE")

    import app

    monkeypatch.setattr(app, "image_search", should_not_run)
    assert client.get("/api/search/images?q=hotel", cookies=free_cookie).status_code == 403


def test_payload_feature_policy_blocks_free_website_and_image_search(monkeypatch):
    import vigzone_ai

    calls = {"images": 0}

    async def fake_realtime(_query):
        return "", ""

    async def fake_images(_query):
        calls["images"] += 1
        return "https://example.com/photo.jpg"

    monkeypatch.setattr(vigzone_ai, "get_realtime_context", fake_realtime)
    monkeypatch.setattr(vigzone_ai, "get_image_search_context", fake_images)
    messages = [{"role": "user", "content": "Build a hotel website with real photos"}]

    free_payload = asyncio.run(vigzone_ai._build_payload(
        messages,
        "openai/gpt-oss-20b",
        False,
        feature_policy={"website_studio": False, "image_search": False, "premium_modes": False},
    ))
    free_sources = [item.get("_vigzone_component") for item in free_payload["messages"]]
    assert "image_search" not in free_sources
    assert "website" not in free_payload["_vigzone_meta"]["prompt_modules"]
    assert "code" not in free_payload["_vigzone_meta"]["prompt_modules"]
    assert calls["images"] == 0

    paid_payload = asyncio.run(vigzone_ai._build_payload(
        messages,
        "openai/gpt-oss-120b",
        False,
        feature_policy={"website_studio": True, "image_search": True, "premium_modes": True},
    ))
    paid_sources = [item.get("_vigzone_component") for item in paid_payload["messages"]]
    assert "image_search" in paid_sources
    assert calls["images"] == 1
