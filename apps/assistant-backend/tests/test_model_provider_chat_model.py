from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage

from app.agents.model_provider_chat_model import ModelProviderChatModel


def test_plain_chat_round_trip() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "id": "chat_1",
                "model": "agent",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hello from provider"}],
                },
                "finish_reason": "stop",
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="agent", base_url="http://test/v1", http_client=client)

    response = model.invoke([HumanMessage(content="hi")])

    assert response.content == "hello from provider"
    assert captured["messages"][0]["role"] == "user"
    assert captured["messages"][0]["content"][0]["text"] == "hi"
    assert captured["path"] == "/v1/internal/chat/messages"


def test_tool_call_request_and_response() -> None:
    captured: dict[str, object] = {}

    def lookup_tool(identifier: str) -> str:
        return identifier

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "id": "chat_2",
                "model": "agent",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_call",
                            "id": "call_1",
                            "name": "lookup_tool",
                            "arguments": {"identifier": "42"},
                        }
                    ],
                },
                "finish_reason": "tool_use",
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="agent", base_url="http://test/v1", http_client=client)

    response = model.bind_tools([lookup_tool], tool_choice="required").invoke([HumanMessage(content="lookup")])

    assert captured["tool_choice"] == {"type": "required"}
    assert captured["tools"][0]["name"] == "lookup_tool"
    assert response.tool_calls[0]["name"] == "lookup_tool"
    assert response.tool_calls[0]["args"] == {"identifier": "42"}
    assert captured["path"] == "/v1/internal/chat/messages"


def test_structured_output_payload() -> None:
    captured: dict[str, object] = {}

    class AnswerSchema(dict):
        pass

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "id": "chat_3",
                "model": "agent",
                "message": {"role": "assistant", "content": [{"type": "text", "text": '{"ok":true}'}]},
                "finish_reason": "stop",
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="agent", base_url="http://test/v1", http_client=client)

    model.with_structured_output(
        {
            "title": "answer",
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        }
    ).invoke([HumanMessage(content="return json")])

    assert captured["structured_output"]["name"] == "answer"
    assert captured["structured_output"]["schema"]["type"] == "object"
    assert captured["path"] == "/v1/internal/chat/messages"


@pytest.mark.asyncio
async def test_streaming_chunk_assembly() -> None:
    captured_path: str | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_path
        captured_path = request.url.path
        body = "".join(
            [
                'data: {"type":"text_delta","text":"hello "}\n\n',
                'data: {"type":"tool_call","id":"call_1","name":"lookup","arguments":{"id":"42"}}\n\n',
                'data: {"type":"text_delta","text":"world"}\n\n',
                'data: {"type":"completion","finish_reason":"stop"}\n\n',
                'data: [DONE]\n\n',
            ]
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="agent", base_url="http://test/v1", async_http_client=async_client)

    chunks = [chunk async for chunk in model.astream([HumanMessage(content="hi")])]

    text = "".join(chunk.content for chunk in chunks if chunk.content)
    tool_chunks = [
        item
        for chunk in chunks
        for item in getattr(chunk, "tool_call_chunks", [])
    ]

    assert text == "hello world"
    assert tool_chunks[0]["name"] == "lookup"
    assert captured_path == "/v1/internal/chat/messages"
