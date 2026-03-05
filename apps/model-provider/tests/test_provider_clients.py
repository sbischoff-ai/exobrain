from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.contracts.native_chat import (
    NativeChatRequest,
    StructuredOutputIntent,
    TextBlock,
    ToolChoiceAny,
)
from app.providers.anthropic_client import AnthropicProviderClient
from app.providers.base import ProviderClientError
from app.providers.openai_client import OpenAIProviderClient


class FakeDumpable:
    def __init__(self, payload: dict):
        self.payload = payload

    def model_dump(self, mode: str = "json") -> dict:
        return self.payload

    def model_dump_json(self) -> str:
        import json

        return json.dumps(self.payload)


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))
        self.embeddings = SimpleNamespace(create=self._emb_create)
        self.called_with: dict | None = None
        self.stream_called_with: dict | None = None

    async def _chat_create(self, **kwargs):
        if kwargs.get("stream"):
            self.stream_called_with = kwargs

            async def _gen():
                yield FakeDumpable(
                    {
                        "id": "chunk1",
                        "choices": [{"delta": {"content": "he"}, "finish_reason": None}],
                    }
                )
                yield FakeDumpable(
                    {
                        "id": "chunk2",
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_1",
                                            "function": {"name": "lookup", "arguments": '{"id"'},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                )
                yield FakeDumpable(
                    {
                        "id": "chunk3",
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "function": {"arguments": ': "42"}'},
                                        }
                                    ]
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                    }
                )

            return _gen()
        self.called_with = kwargs
        return FakeDumpable(
            {
                "id": "resp1",
                "object": "chat.completion",
                "choices": [
                    {
                        "message": {
                            "content": "hello",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {"name": "lookup", "arguments": '{"id": "42"}'},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }
        )

    async def _emb_create(self, **kwargs):
        self.called_with = kwargs
        return FakeDumpable({"object": "list", "data": [{"embedding": [0.1, 0.2]}]})


@pytest.mark.asyncio
async def test_openai_provider_native_and_compat_chat_round_trip() -> None:
    fake = FakeOpenAIClient()
    client = OpenAIProviderClient(api_key="x", client=fake)

    request = NativeChatRequest(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        tools=[{"type": "function", "name": "lookup", "parameters": {"type": "object"}}],
        tool_choice=ToolChoiceAny(),
        structured_output=StructuredOutputIntent(name="answer", schema={"type": "object"}),
    )

    native = await client.native_chat(request)
    assert native.message.content[0].type == "text"
    assert native.message.content[1].type == "tool_call"
    assert fake.called_with is not None
    assert fake.called_with["tool_choice"] == "required"

    frames = []
    async for frame in client.native_chat_stream(request):
        frames.append(frame)
    assert any(frame.type == "text_delta" for frame in frames)
    tool_frames = [frame for frame in frames if frame.type == "tool_call"]
    assert tool_frames
    assert tool_frames[0].arguments == {"id": "42"}
    assert any(frame.type == "completion" for frame in frames)


class FakeAnthropicMessages:
    async def create(self, **kwargs):
        self.last_create = kwargs
        return SimpleNamespace(
            id="msg_1",
            content=[
                SimpleNamespace(type="tool_use", id="call_1", name="lookup", input={"id": "42"}),
                SimpleNamespace(type="text", text="hello"),
            ],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        )


@pytest.mark.asyncio
async def test_anthropic_provider_native_preserves_tool_use_content() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    request = NativeChatRequest(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        tools=[{"type": "function", "name": "lookup", "parameters": {"type": "object"}}],
        structured_output=StructuredOutputIntent(name="answer", schema={"type": "object"}),
    )
    response = await client.native_chat(request)

    assert response.message.content[0].type == "tool_call"
    assert response.message.content[1].type == "text"
    assert "type" not in messages.last_create["tools"][0]
    assert messages.last_create["tools"][0]["name"] == "lookup"
    assert messages.last_create["output_config"]["format"]["type"] == "json_schema"

    projected = await client.chat_completions(
        {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "lookup", "parameters": {"type": "object"}},
                }
            ],
        }
    )
    assert projected["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "lookup"


@pytest.mark.asyncio
async def test_anthropic_provider_rejects_invalid_response_format_schema() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "answer"},
        },
    }

    with pytest.raises(ProviderClientError) as exc_info:
        await client.chat_completions(payload)

    assert exc_info.value.status_code == 400
