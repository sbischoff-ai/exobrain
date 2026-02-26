from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers.anthropic_client import AnthropicProviderClient
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
                yield FakeDumpable({"id": "chunk1", "choices": []})

            return _gen()
        self.called_with = kwargs
        return FakeDumpable({"id": "resp1", "object": "chat.completion"})

    async def _emb_create(self, **kwargs):
        self.called_with = kwargs
        return FakeDumpable({"object": "list", "data": [{"embedding": [0.1, 0.2]}]})


@pytest.mark.asyncio
async def test_openai_provider_uses_sdk_methods_for_chat_embeddings_and_stream() -> None:
    fake = FakeOpenAIClient()
    client = OpenAIProviderClient(api_key="x", client=fake)

    chat_payload = {"model": "gpt-5-mini", "messages": [{"role": "user", "content": "hi"}]}
    response = await client.chat_completions(chat_payload)
    assert response["id"] == "resp1"
    assert fake.called_with == chat_payload

    emb_payload = {"model": "text-embedding-3-large", "input": ["hi"]}
    emb_response = await client.embeddings(emb_payload)
    assert emb_response["object"] == "list"
    assert fake.called_with == emb_payload

    chunks = []
    async for chunk in client.chat_completions_stream({**chat_payload, "stream": True}):
        chunks.append(chunk)
    assert chunks[-1] == "data: [DONE]\n\n"
    assert fake.stream_called_with is not None


class FakeAnthropicMessages:
    async def create(self, **kwargs):
        self.last_create = kwargs
        return SimpleNamespace(
            id="msg_1",
            content=[SimpleNamespace(type="text", text="hello")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        )


@pytest.mark.asyncio
async def test_anthropic_provider_translates_to_openai_shape() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "hi"}]}
    response = await client.chat_completions(payload)

    assert response["object"] == "chat.completion"
    assert response["choices"][0]["message"]["content"] == "hello"
    assert messages.last_create["model"] == "claude-sonnet-4-6"
