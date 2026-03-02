import importlib

import pytest


def test_format_stream_error_returns_sse_error_payload(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")
    error = main.ProviderClientError(status_code=400, message="bad request")
    event = main._format_stream_error(error, alias="agent", provider="openai")

    assert event.startswith("data: ")
    assert '"code": 400' in event
    assert 'provider=openai alias=agent' in event


def test_chat_completions_forwards_valid_structured_output(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")

    class StubClient:
        def __init__(self) -> None:
            self.called_payload = None

        async def chat_completions(self, payload):
            self.called_payload = payload
            return {"id": "ok", "object": "chat.completion", "choices": []}

    stub_client = StubClient()
    alias_config = main.AliasConfig(
        alias="agent",
        provider="openai",
        upstream_model="gpt-5-mini",
        mode="chat",
        defaults={},
    )
    monkeypatch.setattr(main.registry, "resolve", lambda alias: (alias_config, stub_client))

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "agent",
            "messages": [{"role": "user", "content": "hello"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "answer",
                    "schema": {
                        "type": "object",
                        "properties": {"answer": {"type": "string"}},
                        "required": ["answer"],
                    },
                },
            },
        },
    )

    assert response.status_code == 200
    assert stub_client.called_payload is not None
    assert stub_client.called_payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "answer",
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        },
    }


@pytest.mark.parametrize(
    "response_format, expected_detail",
    [
        ("not-an-object", "response_format must be an object"),
        ({"type": "json_object"}, "response_format.type must be 'json_schema'"),
        ({"type": "json_schema", "json_schema": []}, "response_format.json_schema must be a non-empty object"),
    ],
)
def test_chat_completions_rejects_malformed_structured_output(monkeypatch, response_format, expected_detail) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")
    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "agent",
            "messages": [{"role": "user", "content": "hello"}],
            "response_format": response_format,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail
