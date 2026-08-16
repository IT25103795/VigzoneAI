"""Regression checks for the server Groq -> Gemini fallback."""

from __future__ import annotations
import asyncio
import json
import httpx


class PostResponse:
    headers = httpx.Headers()

    def __init__(self, status_code, text="", body=None):
        self.status_code, self.text, self.body = status_code, text, body

    def json(self):
        return self.body


class StreamResponse:
    headers = httpx.Headers()

    def __init__(self, status_code, body="", lines=None):
        self.status_code, self.body, self.lines = status_code, body.encode(), lines or []

    async def aread(self):
        return self.body

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class StreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *_args):
        return False


def built(model, stream):
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "Zoner policy and private context"},
            {"role": "user", "content": "Explain RAM simply"},
        ],
        "stream": stream,
        "_vigzone_meta": {"prompt_modules": ["core"]},
    }


def test_gemini_payload_keeps_built_zoner_context(monkeypatch):
    import vigzone_ai

    monkeypatch.setattr(vigzone_ai, "GEMINI_FALLBACK_KEY", "test-key")
    payload = vigzone_ai._gemini_request_payload(built("x", False)["messages"])
    assert payload["systemInstruction"]["parts"][0]["text"] == "Zoner policy and private context"
    assert payload["contents"][-1]["parts"][0]["text"] == "Explain RAM simply"
    assert payload["generationConfig"] == {"maxOutputTokens": 2048}


def test_chat_once_final_429_returns_gemini(monkeypatch):
    import vigzone_ai

    calls = []

    async def build(_m, model, stream, **_k):
        return built(model, stream)

    class Client:
        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if "api.groq.com" in url:
                return PostResponse(429, json.dumps({"error": {"message": "rate limited; try again in 5s"}}))
            return PostResponse(
                200, body={"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]}
            )

    client = Client()
    metadata = []
    monkeypatch.setattr(vigzone_ai, "GEMINI_FALLBACK_KEY", "test-key")
    monkeypatch.setattr(vigzone_ai, "GEMINI_FALLBACK_MODEL", "gemini-3.6-flash")
    monkeypatch.setattr(vigzone_ai, "_build_payload", build)
    monkeypatch.setattr(vigzone_ai, "_model_candidates", lambda *_a, **_k: ["primary"])
    monkeypatch.setattr(vigzone_ai, "_get_client", lambda: client)
    reply = asyncio.run(
        vigzone_ai.chat_once(
            [{"role": "user", "content": "Explain RAM simply"}], metadata_callback=metadata.append
        )
    )
    assert reply == "Gemini answer" and len(calls) == 2
    url, kwargs = calls[1]
    assert "gemini-3.6-flash:generateContent" in url and "key=" not in url
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    assert kwargs["json"]["systemInstruction"]["parts"][0]["text"] == "Zoner policy and private context"
    assert metadata[-1]["provider"] == "gemini" and metadata[-1]["fallback_used"] is True


def test_stream_final_429_streams_gemini(monkeypatch):
    import vigzone_ai

    calls = []

    async def build(_m, model, stream, **_k):
        return built(model, stream)

    class Client:
        def stream(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if "api.groq.com" in url:
                return StreamContext(
                    StreamResponse(
                        429, body=json.dumps({"error": {"message": "rate limited; try again in 5s"}})
                    )
                )
            return StreamContext(
                StreamResponse(
                    200,
                    lines=[
                        'data: {"candidates":[{"content":{"parts":[{"text":"Gemini "}]}}]}',
                        'data: {"candidates":[{"content":{"parts":[{"text":"stream"}]}}]}',
                    ],
                )
            )

    client = Client()
    metadata = []
    monkeypatch.setattr(vigzone_ai, "GEMINI_FALLBACK_KEY", "test-key")
    monkeypatch.setattr(vigzone_ai, "GEMINI_FALLBACK_MODEL", "gemini-3.6-flash")
    monkeypatch.setattr(vigzone_ai, "_build_payload", build)
    monkeypatch.setattr(vigzone_ai, "_model_candidates", lambda *_a, **_k: ["primary"])
    monkeypatch.setattr(vigzone_ai, "_get_client", lambda: client)

    async def collect():
        return "".join(
            [
                c
                async for c in vigzone_ai.stream_chat(
                    [{"role": "user", "content": "Explain RAM simply"}], metadata_callback=metadata.append
                )
            ]
        )

    assert asyncio.run(collect()) == "Gemini stream" and len(calls) == 2
    _, url, kwargs = calls[1]
    assert "gemini-3.6-flash:streamGenerateContent?alt=sse" in url and "key=" not in url
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    assert metadata[-1]["provider"] == "gemini"


def test_shared_fallback_excludes_byok_and_images(monkeypatch):
    import vigzone_ai

    monkeypatch.setattr(vigzone_ai, "GEMINI_FALLBACK_KEY", "test-key")
    err = vigzone_ai.VigzoneAIError("limited", code="provider_rate_limit")
    assert not vigzone_ai._should_use_gemini_fallback(err, using_override=True, contains_image=False)
    assert not vigzone_ai._should_use_gemini_fallback(err, using_override=False, contains_image=True)
