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
    assert "provider=openai alias=agent" in event


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


def test_internal_native_chat_endpoint_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")

    class StubClient:
        async def native_chat(self, request):
            assert request.structured_output is not None
            return main.NativeChatResponse(
                id="chat_123",
                model=request.model,
                message=main.AssistantMessage(
                    content=[
                        main.ToolCallBlock(id="call_1", name="lookup", arguments={"id": "42"}),
                        main.TextBlock(text="done"),
                    ]
                ),
                finish_reason="tool_use",
                usage=main.Usage(input_tokens=3, output_tokens=7, total_tokens=10),
            )

    alias_config = main.AliasConfig(
        alias="agent",
        provider="openai",
        upstream_model="gpt-5-mini",
        mode="chat",
        defaults={},
    )
    monkeypatch.setattr(main.registry, "resolve", lambda alias: (alias_config, StubClient()))

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.post(
        "/v1/internal/chat/messages",
        json={
            "model": "agent",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
            "tools": [
                {
                    "type": "function",
                    "name": "lookup",
                    "description": "Lookup",
                    "parameters": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    },
                }
            ],
            "tool_choice": {"type": "tool", "name": "lookup"},
            "structured_output": {
                "name": "answer",
                "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
                "strict": True,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "agent"
    assert body["message"]["content"][0]["type"] == "tool_call"
    assert body["usage"]["total_tokens"] == 10


def test_chat_completions_shim_projects_tool_calls(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")

    class StubClient:
        async def native_chat(self, request):
            return main.NativeChatResponse(
                id="chat_123",
                model=request.model,
                message=main.AssistantMessage(
                    content=[
                        main.TextBlock(text="hello"),
                        main.ToolCallBlock(id="call_1", name="lookup", arguments={"id": "42"}),
                    ]
                ),
                finish_reason="tool_use",
                usage=main.Usage(input_tokens=5, output_tokens=6, total_tokens=11),
            )

    alias_config = main.AliasConfig(
        alias="agent",
        provider="anthropic",
        upstream_model="claude-sonnet-4-6",
        mode="chat",
        defaults={},
    )
    monkeypatch.setattr(main.registry, "resolve", lambda alias: (alias_config, StubClient()))

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.post(
        "/v1/chat/completions",
        json={"model": "agent", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "agent"
    assert body["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "lookup"
    assert body["usage"]["total_tokens"] == 11


@pytest.mark.asyncio
async def test_architect_rate_limiter_sleeps_when_budget_exceeded(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")

    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)

    limiter = main.ArchitectTokenRateLimiter(max_tokens_per_minute=1000)
    await limiter.throttle_for_payload("architect", {"text": "x" * 1600})
    await limiter.throttle_for_payload("architect", {"text": "x" * 3200})

    assert slept
    assert slept[0] > 0


@pytest.mark.asyncio
async def test_architect_rate_limiter_ignores_non_architect_alias(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")

    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)

    limiter = main.ArchitectTokenRateLimiter(max_tokens_per_minute=1)
    await limiter.throttle_for_payload("agent", {"text": "x" * 10000})

    assert slept == []


def test_internal_native_chat_endpoint_unwraps_json_schema_tool_parameters(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    main = importlib.import_module("app.main")

    class StubClient:
        async def native_chat(self, request):
            parameters = request.tools[0].parameters
            assert parameters == {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            }
            return main.NativeChatResponse(
                id="chat_123",
                model=request.model,
                message=main.AssistantMessage(content=[main.TextBlock(text="done")]),
                finish_reason="stop",
                usage=main.Usage(input_tokens=3, output_tokens=7, total_tokens=10),
            )

    alias_config = main.AliasConfig(
        alias="agent",
        provider="openai",
        upstream_model="gpt-5-mini",
        mode="chat",
        defaults={},
    )
    monkeypatch.setattr(main.registry, "resolve", lambda alias: (alias_config, StubClient()))

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "agent",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "parameters": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "LookupInput",
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "string"}},
                                    "required": ["id"],
                                },
                            },
                        },
                    },
                }
            ],
        },
    )

    assert response.status_code == 200


def test_chat_completions_rejects_invalid_tool_parameter_schema_payload(monkeypatch) -> None:
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
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "parameters": {
                            "type": "json_schema",
                            "json_schema": {"name": "LookupInput"},
                        },
                    },
                }
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "tools[].function.parameters.json_schema.schema must be an object"
