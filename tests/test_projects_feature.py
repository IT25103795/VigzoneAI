"""Projects are real, private, local-folder-aware, and quota metered."""

from __future__ import annotations

import json
from pathlib import Path

import billing


PASSWORD = "A strong project test password"


def _cookie(auth, user_id: int) -> dict[str, str]:
    return {auth.SESSION_COOKIE_NAME: auth.create_session(user_id)}


def test_projects_entitlement_is_enabled_for_every_role():
    users = [
        {"id": 1, "plan": "free", "role": "user"},
        {"id": 2, "plan": "pro", "role": "user"},
        {"id": 3, "plan": "team", "role": "user"},
        {"id": 4, "plan": "free", "role": "admin", "is_admin": True},
    ]
    assert all(
        billing.entitlement_snapshot(user)["features"]["projects"] is True
        for user in users
    )


def test_personal_project_creation_works_for_free_pro_team_and_admin(client, auth_db):
    accounts = [
        ("projects-free@example.com", "free"),
        ("projects-pro@example.com", "pro"),
        ("projects-team@example.com", "team"),
        ("bhashithanavod808@gmail.com", "admin"),
    ]
    for index, (email, role) in enumerate(accounts):
        user = auth_db.create_user_with_password(email, PASSWORD, role.title())
        if role in {"pro", "team"}:
            with auth_db._connect() as conn:
                conn.execute("UPDATE users SET plan = ? WHERE id = ?", (role, user["id"]))
        response = client.post(
            "/api/projects",
            cookies=_cookie(auth_db, user["id"]),
            json={"name": f"{role.title()} Project {index}", "mode": "general"},
        )
        assert response.status_code == 200, (role, response.text)


def test_project_crud_is_available_to_free_users_and_remains_private(client, auth_db):
    owner = auth_db.create_user_with_password(
        "project-owner@example.com", PASSWORD, "Project Owner"
    )
    outsider = auth_db.create_user_with_password(
        "project-outsider@example.com", PASSWORD, "Project Outsider"
    )
    owner_cookie = _cookie(auth_db, owner["id"])
    outsider_cookie = _cookie(auth_db, outsider["id"])

    created = client.post(
        "/api/projects",
        cookies=owner_cookie,
        json={
            "name": "Local App",
            "description": "Analyze and improve a local application",
            "mode": "general",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["workspace"]["id"]

    owner_projects = client.get("/api/projects", cookies=owner_cookie)
    assert owner_projects.status_code == 200
    assert owner_projects.json()["projects"][0]["id"] == project_id
    assert client.get("/api/projects", cookies=outsider_cookie).json()["projects"] == []
    assert client.get(
        f"/api/projects/{project_id}/notes", cookies=outsider_cookie
    ).status_code == 404


def test_project_ai_uses_durable_plan_quota_and_filters_unsafe_changes(
    client, auth_db, monkeypatch
):
    import app
    import vigzone_ai

    user = auth_db.create_user_with_password(
        "project-ai@example.com", PASSWORD, "Project AI"
    )
    cookie = _cookie(auth_db, user["id"])
    created = client.post(
        "/api/projects",
        cookies=cookie,
        json={"name": "Quota Project", "description": "Meter every AI action"},
    )
    project_id = created.json()["workspace"]["id"]

    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    monkeypatch.setattr(vigzone_ai, "USAGE_RESERVE_TOKENS", 100)
    monkeypatch.setenv("FREE_DAILY_TOKEN_LIMIT", "10000")

    async def configured():
        return True

    calls = []

    async def fake_chat_once(messages, **kwargs):
        calls.append({"messages": messages, "kwargs": kwargs})
        assert kwargs["quota_reservation"]["active"] is True
        assert kwargs["conversation_id"] == f"project:{project_id}:thread-123"
        usage_id = vigzone_ai.track_token_usage(
            kwargs["user_id"],
            120,
            80,
            provider="groq",
            estimated=False,
            model="openai/gpt-oss-20b",
            quota_reservation=kwargs["quota_reservation"],
        )
        assert usage_id
        return json.dumps(
            {
                "summary": "Found and fixed the selected bug.",
                "changes": [
                    {
                        "path": "src/app.py",
                        "content": "print('fixed')\n",
                        "reason": "Correct the behavior",
                    },
                    {
                        "path": "../outside.txt",
                        "content": "must never escape",
                        "reason": "Unsafe",
                    },
                ],
            }
        )

    monkeypatch.setattr(app, "is_configured", configured)
    monkeypatch.setattr(app, "chat_once", fake_chat_once)

    response = client.post(
        "/api/projects/assist",
        cookies=cookie,
        json={
            "project_id": project_id,
            "action": "edit",
            "instruction": "Fix the selected bug safely.",
            "model": "openai/gpt-oss-20b",
            "conversation_id": "thread-123",
            "history": [
                {"role": "user", "content": "The bug happens after saving."},
                {"role": "assistant", "content": "I will inspect the save flow."},
            ],
            "tree": ["src/app.py", "../outside.txt"],
            "files": [{"path": "src/app.py", "content": "print('broken')\n"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["changes"] == [
        {
            "path": "src/app.py",
            "content": "print('fixed')\n",
            "reason": "Correct the behavior",
        }
    ]
    assert len(calls) == 1
    assert "print('broken')" in calls[0]["messages"][0]["content"]
    assert "The bug happens after saving." in calls[0]["messages"][0]["content"]

    usage = vigzone_ai.get_user_daily_usage(user, has_own_key=False)
    assert usage["used_today"] == 200
    assert usage["reserved_today"] == 0
    assert usage["remaining_today"] == 9800
    assert auth_db.get_daily_message_count(user["id"]) == 1

    monkeypatch.setenv("FREE_DAILY_TOKEN_LIMIT", "200")
    exhausted = client.post(
        "/api/projects/assist",
        cookies=cookie,
        json={
            "project_id": project_id,
            "action": "analyze",
            "model": "openai/gpt-oss-20b",
            "tree": ["src/app.py"],
            "files": [{"path": "src/app.py", "content": "print('fixed')\n"}],
        },
    )
    assert exhausted.status_code == 429
    assert "FREE daily token quota" in exhausted.json()["detail"]
    assert len(calls) == 1


def test_project_ai_rejects_cross_account_and_oversized_context(client, auth_db):
    owner = auth_db.create_user_with_password(
        "project-secure-owner@example.com", PASSWORD, "Secure Owner"
    )
    outsider = auth_db.create_user_with_password(
        "project-secure-outsider@example.com", PASSWORD, "Secure Outsider"
    )
    project = auth_db.create_workspace(owner["id"], "Private Project", "Private")

    not_found = client.post(
        "/api/projects/assist",
        cookies=_cookie(auth_db, outsider["id"]),
        json={
            "project_id": project["id"],
            "action": "analyze",
            "files": [{"path": "README.md", "content": "private"}],
        },
    )
    assert not_found.status_code == 404

    oversized = client.post(
        "/api/projects/assist",
        cookies=_cookie(auth_db, owner["id"]),
        json={
            "project_id": project["id"],
            "action": "analyze",
            "files": [
                {"path": "one.txt", "content": "a" * 60000},
                {"path": "two.txt", "content": "b" * 60000},
                {"path": "three.txt", "content": "c"},
            ],
        },
    )
    assert oversized.status_code == 413


def test_projects_ui_uses_explicit_folder_permission_and_reviewed_writes():
    index = Path("static/index.html").read_text(encoding="utf-8")
    script = Path("static/js/projects.js").read_text(encoding="utf-8")
    service_worker = Path("static/service-worker.js").read_text(encoding="utf-8")

    assert 'id="sidebarProjectsList"' in index
    assert 'id="projectChatBar"' in index
    assert 'id="projectChatNewBtn"' in index
    assert 'id="workspaceSidebarBtn"' in index
    assert "showDirectoryPicker({mode: 'readwrite'})" in script
    assert "createWritable()" in script
    assert "Review full replacement" in script
    assert "window.confirm('Write '" in script
    assert "fetch('/api/projects/assist'" in script
    assert "conversation_id" in script
    assert "recent_conversation" in Path("app.py").read_text(encoding="utf-8")
    assert "renderMessageResult" in script
    assert "openProjectConversation" in Path("static/js/app.js").read_text(encoding="utf-8")
    assert "projectThreadTitle" in Path("static/js/app.js").read_text(encoding="utf-8")
    assert "isSensitivePath" in script
    assert "name === '.env'" in script
    assert "node_modules" in script
    assert "Do not claim to run commands or tests" in Path("app.py").read_text(encoding="utf-8")
    assert "/static/js/projects.js?v=vigi-desktop-r1" in index
    assert "/static/js/projects.js?v=${UI_ASSET_REVISION}" in service_worker
