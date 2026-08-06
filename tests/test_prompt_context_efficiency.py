"""Prompt efficiency, context budgeting, routing telemetry, and quality gates."""

from __future__ import annotations

import asyncio
import sqlite3

import httpx
import pytest


FAST_CASES = [
    "Hi",
    "Hello there",
    "Hey bro",
    "Thanks",
    "Good morning",
    "What is RAM?",
    "Define CPU",
    "What does URL mean?",
    "Who wrote Hamlet?",
    "What is photosynthesis?",
    "Name the largest ocean",
    "Convert 5 km to meters",
    "What color is the sky?",
    "Give me a synonym for quick",
    "What is 2 plus 2?",
    "Spell accommodation",
    "What is an adjective?",
    "Name three primary colors",
    "What is a byte?",
    "What does HTTP stand for?",
    "Tell me a short joke",
    "Say welcome",
    "Is water wet?",
    "What is the capital of Japan?",
]


COMPLEX_GENERAL_CASES = [
    "Explain SQL joins step by step",
    "Debug this Python authentication function",
    "Write a Java class for student records",
    "Refactor this JavaScript API endpoint",
    "Create a responsive landing page",
    "Build a portfolio website for a photographer",
    "Design a database schema for a hotel",
    "Review this regex and fix its edge cases",
    "Write C++ code for Dijkstra's algorithm",
    "Explain how this TypeScript class works",
    "Research the trade-offs between Redis and SQLite",
    "Evaluate this production deployment plan",
    "Recommend a secure authentication architecture",
    "Calculate the probability and show each step",
    "Solve this matrix equation",
    "Prove why this algorithm is correct",
    "Compare REST and GraphQL in detail",
    "Write an essay about renewable energy",
    "Summarize this chapter with revision questions",
    "Walk me through how a compiler works",
    "What is the latest exchange rate?",
    "What is today's weather forecast?",
    "Show current football standings",
    "Who is the current prime minister?",
    "What is the newest software release?",
    "What medicine dosage is safe?",
    "Could these symptoms need emergency treatment?",
    "Review this legal contract",
    "Should I make this investment?",
    "How can I secure a mortgage?",
    "Investigate this cybersecurity vulnerability",
    "මේක පැහැදිලි කරන්න",
    "මෙම ප්‍රශ්නය විසඳන්න",
    "இதை விளக்கவும்",
    "இந்த கேள்வியை தீர்க்கவும்",
    "यह कैसे काम करता है?",
    "اشرح هذا المفهوم",
    "解释这个算法",
    "このコードを説明して",
    "What is RAM? How is it different from storage?",
    "Name the risks? What should I do next?",
    "Plan a scalable multi-user application",
    "Optimize this slow production query",
    "Analyze the evidence and identify contradictions",
    "Create a complete tutorial for Docker networking",
    "Generate a detailed business strategy",
    "Explain the difference between TCP and UDP",
    "How does public key cryptography work?",
]


SPECIALIST_MODE_CASES = [
    ("Make it cleaner", "website"),
    ("Please fix this", "code"),
    ("Help me revise", "study"),
    ("Find the key points", "file"),
    ("Polish this", "business"),
]


FOLLOWUP_CASES = ["yes", "no", "do it", "fix it", "same", "again", "why", "how", "continue", "next"]


@pytest.fixture
def routed_models(monkeypatch):
    import vigzone_ai

    fast = "test/fast"
    complex_model = "test/complex"
    vision = "test/vision"
    monkeypatch.setattr(vigzone_ai, "MODEL_ROUTING_ENABLED", True)
    monkeypatch.setattr(vigzone_ai, "FAST_MODEL", fast)
    monkeypatch.setattr(vigzone_ai, "COMPLEX_MODEL", complex_model)
    monkeypatch.setattr(vigzone_ai, "VISION_MODEL", vision)
    monkeypatch.setattr(vigzone_ai, "ALLOWED_CHAT_MODELS", {fast, complex_model, vision})
    return fast, complex_model, vision


@pytest.mark.parametrize("prompt", FAST_CASES)
def test_quality_benchmark_routes_clear_low_risk_prompts_fast(prompt, routed_models):
    import vigzone_ai

    fast, _complex, _vision = routed_models
    model, reason = vigzone_ai.select_chat_model([{"role": "user", "content": prompt}])
    assert model == fast
    assert reason == "simple_request"


@pytest.mark.parametrize("prompt", COMPLEX_GENERAL_CASES)
def test_quality_benchmark_keeps_complex_prompts_on_strong_model(prompt, routed_models):
    import vigzone_ai

    _fast, complex_model, _vision = routed_models
    model, _reason = vigzone_ai.select_chat_model([{"role": "user", "content": prompt}])
    assert model == complex_model


@pytest.mark.parametrize(("prompt", "mode"), SPECIALIST_MODE_CASES)
def test_quality_benchmark_keeps_specialist_modes_strong(prompt, mode, routed_models):
    import vigzone_ai

    _fast, complex_model, _vision = routed_models
    model, reason = vigzone_ai.select_chat_model(
        [{"role": "user", "content": prompt}],
        ai_mode=mode,
    )
    assert model == complex_model
    assert reason == f"specialist_mode:{mode}"


@pytest.mark.parametrize("followup", FOLLOWUP_CASES)
def test_quality_benchmark_keeps_ambiguous_followups_strong(followup, routed_models):
    import vigzone_ai

    _fast, complex_model, _vision = routed_models
    messages = [
        {"role": "user", "content": "Design a secure Python API"},
        {"role": "assistant", "content": "Here is the initial design."},
        {"role": "user", "content": followup},
    ]
    model, reason = vigzone_ai.select_chat_model(messages)
    assert model == complex_model
    assert reason == "contextual_followup"


def test_quality_benchmark_keeps_images_on_vision_model(routed_models):
    import vigzone_ai

    _fast, _complex, vision = routed_models
    assert vigzone_ai.select_chat_model(
        [{"role": "user", "content": "Read this image"}],
        contains_image=True,
    ) == (vision, "vision")


def test_compact_core_prompt_and_task_modules(monkeypatch):
    import vigzone_ai

    async def no_realtime(_text):
        return "", ""

    monkeypatch.setattr(vigzone_ai, "HAS_REALWORLD_DATA", True)
    monkeypatch.setattr(vigzone_ai, "get_realworld_data_context", no_realtime)

    simple = asyncio.run(
        vigzone_ai._build_payload(
            [{"role": "user", "content": "Hi bro"}],
            vigzone_ai.FAST_MODEL,
            False,
        )
    )
    code = asyncio.run(
        vigzone_ai._build_payload(
            [{"role": "user", "content": "Debug this Python function"}],
            vigzone_ai.COMPLEX_MODEL,
            False,
        )
    )
    simple_tokens = vigzone_ai._estimate_payload_prompt_tokens(simple["messages"])
    assert vigzone_ai._estimate_tokens(vigzone_ai.SYSTEM_PROMPT) <= 1000
    assert simple_tokens <= 1000
    assert simple["_vigzone_meta"]["prompt_modules"] == []
    assert code["_vigzone_meta"]["prompt_modules"] == ["code"]
    assert vigzone_ai._estimate_payload_prompt_tokens(code["messages"]) > simple_tokens


def test_history_is_token_budgeted_relevant_and_deduplicated(monkeypatch):
    import vigzone_ai

    monkeypatch.setattr(vigzone_ai, "CONTEXT_MAX_RECENT_MESSAGES", 6)
    monkeypatch.setattr(vigzone_ai, "CONTEXT_HISTORY_TOKEN_BUDGET", 400)
    monkeypatch.setattr(vigzone_ai, "CONTEXT_SUMMARY_TOKEN_BUDGET", 180)
    messages = [
        {"role": "user", "content": "My project uses PostgreSQL for booking data."},
        {"role": "assistant", "content": "Noted the PostgreSQL booking requirement."},
        {"role": "user", "content": "Unrelated discussion about breakfast."},
        {"role": "assistant", "content": "Breakfast can be simple."},
    ]
    for index in range(8):
        messages.extend(
            [
                {"role": "user", "content": f"Recent booking question {index}"},
                {"role": "assistant", "content": f"Recent booking answer {index}"},
            ]
        )
    messages.append({"role": "user", "content": "How should PostgreSQL booking data be indexed?"})
    messages.insert(-1, {"role": "assistant", "content": "Recent booking answer 7"})

    recent, summary, stats = vigzone_ai._select_history_for_model(messages)
    assert len(recent) <= 6
    assert recent[-1]["content"].startswith("How should PostgreSQL")
    assert stats["duplicates_removed"] == 1
    assert "PostgreSQL" in summary
    assert "breakfast" not in summary.lower()
    assert vigzone_ai._estimate_tokens(summary) <= 190


def test_context_blocks_are_separately_bounded_deduplicated_and_fenced(monkeypatch):
    import vigzone_ai

    async def live(_text):
        return "Source A: Current value 42.\n\n- Shared preference", ""

    monkeypatch.setattr(vigzone_ai, "HAS_REALWORLD_DATA", True)
    monkeypatch.setattr(vigzone_ai, "get_realworld_data_context", live)
    monkeypatch.setattr(vigzone_ai, "CONTEXT_LIVE_TOKEN_BUDGET", 80)
    monkeypatch.setattr(vigzone_ai, "CONTEXT_WORKSPACE_TOKEN_BUDGET", 80)
    monkeypatch.setattr(vigzone_ai, "CONTEXT_MEMORY_TOKEN_BUDGET", 80)
    payload = asyncio.run(
        vigzone_ai._build_payload(
            [{"role": "user", "content": "What is the current value?"}],
            vigzone_ai.COMPLEX_MODEL,
            False,
            context_parts={
                "workspace": "Workspace goal\n\n- Shared preference",
                "memory": "- Shared preference\n\nUse concise replies",
            },
        )
    )
    system_text = "\n".join(
        str(message.get("content") or "")
        for message in payload["messages"]
        if message.get("role") == "system"
    )
    assert system_text.count("Shared preference") == 1
    assert "[BEGIN UNTRUSTED LIVE SOURCE DATA]" in system_text
    assert "[BEGIN UNTRUSTED PRIVATE WORKSPACE DATA]" in system_text
    assert "[BEGIN UNTRUSTED PRIVATE USER CONTEXT DATA]" in system_text
    assert payload["_vigzone_meta"]["context_duplicates_removed"] >= 1


def test_provider_payload_removes_internal_analytics_tags(monkeypatch):
    import vigzone_ai

    async def no_realtime(_text):
        return "", ""

    monkeypatch.setattr(vigzone_ai, "HAS_REALWORLD_DATA", True)
    monkeypatch.setattr(vigzone_ai, "get_realworld_data_context", no_realtime)
    payload = asyncio.run(
        vigzone_ai._build_payload(
            [{"role": "user", "content": "Hello"}],
            vigzone_ai.FAST_MODEL,
            False,
        )
    )
    provider_payload = vigzone_ai._provider_payload(payload)
    assert "_vigzone_meta" not in provider_payload
    assert all(
        "_vigzone_component" not in message
        for message in provider_payload["messages"]
    )


def test_usage_telemetry_migration_and_record(auth_db, monkeypatch):
    import vigzone_ai

    user = auth_db.create_user_with_password(
        "telemetry@example.com",
        "a strong telemetry password",
        "Telemetry",
    )
    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    usage_id = vigzone_ai.track_token_usage(
        user["id"],
        700,
        80,
        model="test/fast",
        routed_model="test/fast",
        route_reason="simple_request",
        routing_mode="general",
        fallback_used=False,
        latency_ms=220,
        time_to_first_token_ms=70,
        cached_tokens=500,
        component_tokens={"system_tokens": 650, "user_tokens": 12},
        conversation_id="quality-chat",
    )
    with auth_db._connect() as conn:
        row = conn.execute(
            "SELECT * FROM token_usage WHERE id = ?",
            (usage_id,),
        ).fetchone()
    assert row["route_reason"] == "simple_request"
    assert row["routed_model"] == "test/fast"
    assert row["latency_ms"] == 220
    assert row["cached_tokens"] == 500
    assert row["system_tokens"] == 650
    assert row["conversation_id"] == "quality-chat"


def test_usage_telemetry_migrates_an_existing_database(tmp_path, monkeypatch):
    import auth

    legacy_db = tmp_path / "vigzone-legacy.db"
    with sqlite3.connect(legacy_db) as conn:
        conn.execute(
            """
            CREATE TABLE token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                ts INTEGER NOT NULL
            )
            """
        )

    monkeypatch.setattr(auth, "DB_PATH", str(legacy_db))
    auth.init_db()
    with auth._connect() as conn:
        columns = auth._columns(conn, "token_usage")

    assert {
        "routed_model",
        "route_reason",
        "routing_mode",
        "fallback_used",
        "retry_count",
        "latency_ms",
        "time_to_first_token_ms",
        "cached_tokens",
        "system_tokens",
        "history_tokens",
        "summary_tokens",
        "memory_tokens",
        "workspace_tokens",
        "search_tokens",
        "user_tokens",
        "conversation_id",
    } <= columns


def test_admin_dashboard_groups_routes_context_and_feedback(client, auth_db, monkeypatch):
    import vigzone_ai

    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "routing-admin@example.com",
            "password": "a strong routing admin password",
            "name": "Routing Admin",
        },
    )
    assert signup.status_code == 200
    user_id = signup.json()["user"]["id"]
    with auth_db._connect() as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))

    monkeypatch.setattr(vigzone_ai, "IS_TESTING", False)
    usage_id = vigzone_ai.track_token_usage(
        user_id,
        620,
        70,
        model="test/fast",
        routed_model="test/fast",
        route_reason="simple_request",
        latency_ms=180,
        time_to_first_token_ms=55,
        component_tokens={"system_tokens": 580, "user_tokens": 14},
    )
    feedback = client.post(
        "/api/feedback",
        json={
            "rating": "up",
            "assistant_text": "Useful answer",
            "context": {
                "usage_id": usage_id,
                "model": "test/fast",
                "route_reason": "simple_request",
            },
        },
    )
    assert feedback.status_code == 200

    dashboard = client.get("/api/admin/full-dashboard")
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert data["routing_usage"][0]["route_reason"] == "simple_request"
    assert data["routing_usage"][0]["average_latency_ms"] == 180
    assert any(
        row["name"] == "system_tokens" and row["tokens"] == 580
        for row in data["context_token_mix"]
    )
    assert data["quality_by_route"][0]["positive_rate"] == 100.0


def test_non_streaming_metadata_reports_fallback_and_usage(monkeypatch):
    import vigzone_ai

    async def payload(_messages, model, stream, **_kwargs):
        return {
            "model": model,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": stream,
            "max_completion_tokens": 100,
        }

    class Response:
        headers = httpx.Headers()
        text = ""

        def __init__(self, status_code, body):
            self.status_code = status_code
            self.body = body

        def json(self):
            return self.body

    class Client:
        def __init__(self):
            self.calls = 0

        async def post(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return Response(429, {})
            return Response(
                200,
                {
                    "choices": [{"message": {"content": "backup answer"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                },
            )

    metadata = {}
    monkeypatch.setattr(vigzone_ai, "_build_payload", payload)
    monkeypatch.setattr(vigzone_ai, "_model_candidates", lambda *_a, **_k: ["primary", "backup"])
    monkeypatch.setattr(vigzone_ai, "_get_client", lambda: Client())
    reply = asyncio.run(
        vigzone_ai.chat_once(
            [{"role": "user", "content": "hello"}],
            metadata_callback=metadata.update,
        )
    )
    assert reply == "backup answer"
    assert metadata["model"] == "backup"
    assert metadata["fallback_used"] is True
    assert metadata["retry_count"] == 1
    assert metadata["total_tokens"] == 13
