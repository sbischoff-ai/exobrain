from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage

from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format


@pytest.mark.asyncio
async def test_model_provider_chat_model_posts_to_internal_chat_messages_path() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat_1",
                "model": "architect",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
                "finish_reason": "stop",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="architect", base_url="http://test/v1", async_http_client=client)

    response = await model.ainvoke([HumanMessage(content="hello")])

    assert response.content == "ok"
    assert captured["path"] == "/v1/internal/chat/messages"


@pytest.mark.asyncio
async def test_model_provider_chat_model_serializes_langchain_any_tool_choice_as_required() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat_2",
                "model": "architect",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
                "finish_reason": "stop",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="architect", base_url="http://test/v1", async_http_client=client)

    configured = model.bind_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup things",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        tool_choice="any",
    )

    reply = await configured.ainvoke([HumanMessage(content="hello")])

    assert reply.content == "done"
    assert captured["tool_choice"] == {"type": "required"}


def test_model_provider_chat_model_serializes_dict_any_tool_choice_as_required() -> None:
    model = ModelProviderChatModel(model="architect", base_url="http://test/v1")

    payload = model._build_payload(
        [HumanMessage(content="hello")],
        stop=None,
        model_provider_tools=[],
        model_provider_tool_choice={"type": "any"},
    )

    assert payload["tool_choice"] == {"type": "required"}


@pytest.mark.asyncio
async def test_model_provider_chat_model_unwraps_openai_response_format_envelope() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat_3",
                "model": "worker",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
                "finish_reason": "stop",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="worker", base_url="http://test/v1", async_http_client=client)

    configured = model.with_structured_output(
        {
            "type": "json_schema",
            "json_schema": {
                "name": "comparison",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"decision": {"type": "string"}},
                    "required": ["decision"],
                },
            },
        }
    )

    response = await configured.ainvoke([HumanMessage(content="compare")])

    assert response.content == "ok"
    assert captured["structured_output"]["name"] == "structured_output"
    assert captured["structured_output"]["schema"] == {
        "type": "object",
        "additionalProperties": False,
        "properties": {"decision": {"type": "string"}},
        "required": ["decision"],
    }


@pytest.mark.asyncio
async def test_model_provider_chat_model_respects_strict_json_schema_response_format() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat_4",
                "model": "worker",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
                "finish_reason": "stop",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="worker", base_url="http://test/v1", async_http_client=client)

    configured = model.with_structured_output(
        build_strict_response_format(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"decision": {"type": "string"}},
                "required": ["decision"],
            }
        )
    )

    response = await configured.ainvoke([HumanMessage(content="compare")])

    assert response.content == "ok"
    assert captured["structured_output"]["strict"] is True


@pytest.mark.asyncio
async def test_model_provider_chat_model_retries_without_temperature_when_provider_rejects_it() -> None:
    captured: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append(payload)
        if len(captured) == 1:
            return httpx.Response(
                400,
                json={
                    "detail": "Unsupported value: 'temperature' does not support 0.0 with this model. Only the default (1) value is supported."
                },
            )

        return httpx.Response(
            200,
            json={
                "id": "chat_5",
                "model": "worker",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
                "finish_reason": "stop",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="worker", base_url="http://test/v1", temperature=0.0, async_http_client=client)

    response = await model.ainvoke([HumanMessage(content="hello")])

    assert response.content == "ok"
    assert len(captured) == 2
    assert captured[0]["temperature"] == 0.0
    assert "temperature" not in captured[1]


@pytest.mark.asyncio
async def test_model_provider_chat_model_does_not_retry_temperature_for_other_400_errors() -> None:
    captured: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(400, json={"detail": "Provider error: another bad request"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="worker", base_url="http://test/v1", async_http_client=client)

    with pytest.raises(httpx.HTTPStatusError):
        await model.ainvoke([HumanMessage(content="hello")])

    assert len(captured) == 1
