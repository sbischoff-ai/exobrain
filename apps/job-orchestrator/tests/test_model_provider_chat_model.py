from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage

from app.services.model_provider_chat_model import ModelProviderChatModel


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
async def test_model_provider_chat_model_surfaces_error_body_on_http_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            400,
            json={"error": {"message": "invalid_request_error: too many tokens"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="architect", base_url="http://test/v1", async_http_client=client)

    with pytest.raises(RuntimeError) as exc_info:
        await model.ainvoke([HumanMessage(content="hello")])

    message = str(exc_info.value)
    assert "status 400" in message
    assert "too many tokens" in message
