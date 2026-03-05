from __future__ import annotations

from types import SimpleNamespace

import pytest

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

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "answer",
            "schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        },
    }
    chat_payload = {"model": "gpt-5-mini", "messages": [{"role": "user", "content": "hi"}]}
    response = await client.chat_completions(
        {**chat_payload, "max_tokens": 123, "response_format": response_format}
    )
    assert response["id"] == "resp1"
    assert fake.called_with["model"] == chat_payload["model"]
    assert "max_tokens" not in fake.called_with
    assert fake.called_with["max_completion_tokens"] == 123
    assert fake.called_with["response_format"] == response_format

    emb_payload = {"model": "text-embedding-3-large", "input": ["hi"]}
    emb_response = await client.embeddings(emb_payload)
    assert emb_response["object"] == "list"
    assert fake.called_with == emb_payload

    chunks = []
    async for chunk in client.chat_completions_stream(
        {**chat_payload, "stream": True, "response_format": response_format}
    ):
        chunks.append(chunk)
    assert chunks[-1] == "data: [DONE]\n\n"
    assert fake.stream_called_with is not None
    assert "max_tokens" not in fake.stream_called_with
    assert fake.stream_called_with["response_format"] == response_format


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


@pytest.mark.asyncio
async def test_anthropic_provider_translates_openai_response_format_to_output_config() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "answer",
                "schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            },
        },
    }

    await client.chat_completions(payload)

    assert "response_format" not in messages.last_create
    assert messages.last_create["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_choice", "expected"),
    [
        ("auto", {"type": "auto"}),
        ("none", {"type": "none"}),
        ("required", {"type": "any"}),
    ],
)
async def test_anthropic_provider_translates_string_tool_choice(
    tool_choice: str,
    expected: dict[str, str],
) -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tool_choice": tool_choice,
    }

    await client.chat_completions(payload)

    assert messages.last_create["tool_choice"] == expected


@pytest.mark.asyncio
async def test_anthropic_provider_maps_openai_tools_to_anthropic_tools() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup records",
                    "parameters": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    },
                },
            }
        ],
    }

    await client.chat_completions(payload)

    assert messages.last_create["tools"] == [
        {
            "type": "custom",
            "name": "lookup",
            "description": "Lookup records",
            "input_schema": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        }
    ]


@pytest.mark.asyncio
async def test_anthropic_provider_adds_default_object_schema_for_tool_parameters() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup records",
                    "parameters": {"properties": {"id": {"type": "string"}}},
                },
            }
        ],
    }

    await client.chat_completions(payload)

    assert messages.last_create["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {"id": {"type": "string"}},
    }


@pytest.mark.asyncio
async def test_anthropic_provider_wraps_non_object_tool_parameters() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup records",
                    "parameters": {"type": "string"},
                },
            }
        ],
    }

    await client.chat_completions(payload)

    assert messages.last_create["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {"input": {"type": "string"}},
        "required": ["input"],
    }


@pytest.mark.asyncio
async def test_anthropic_provider_translates_openai_function_tool_choice() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tool_choice": {"type": "function", "function": {"name": "lookup"}},
    }

    await client.chat_completions(payload)

    assert messages.last_create["tool_choice"] == {"type": "tool", "name": "lookup"}


@pytest.mark.asyncio
async def test_anthropic_provider_accepts_direct_response_format_schema() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        },
    }

    await client.chat_completions(payload)

    assert messages.last_create["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        }
    }


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
    assert exc_info.value.message == "response_format.json_schema must contain a non-empty object schema for Anthropic"


@pytest.mark.asyncio
async def test_anthropic_provider_unwraps_langchain_json_schema_tool_parameters() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "parameters": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "response_format_bce2",
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
    }

    await client.chat_completions(payload)

    assert messages.last_create["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
    }


@pytest.mark.asyncio
async def test_anthropic_provider_normalizes_tool_schema_keywords_defs_and_refs() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "parameters": {
                        "definitions": {"city": {"type": "string", "example": "Paris"}},
                        "properties": {"city": {"$ref": "#/definitions/city", "nullable": True}},
                        "required": ["city"],
                    },
                },
            }
        ],
    }

    await client.chat_completions(payload)

    input_schema = messages.last_create["tools"][0]["input_schema"]
    assert input_schema["type"] == "object"
    assert "$defs" in input_schema
    assert "definitions" not in input_schema
    assert "example" not in input_schema["$defs"]["city"]
    assert input_schema["properties"]["city"] == {"type": "string"}


@pytest.mark.asyncio
async def test_anthropic_provider_rejects_invalid_tool_shape() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"type": "weird"}],
    }

    with pytest.raises(ProviderClientError) as exc_info:
        await client.chat_completions(payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == "Anthropic tools must be OpenAI function tools or Anthropic custom tools"


@pytest.mark.asyncio
async def test_anthropic_provider_rejects_external_ref_tool_schema() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"$ref": "https://example.com/schema.json"}},
                    },
                },
            }
        ],
    }

    with pytest.raises(ProviderClientError) as exc_info:
        await client.chat_completions(payload)

    assert exc_info.value.status_code == 400
    assert 'Invalid tool schema for tool "lookup"' in exc_info.value.message


@pytest.mark.asyncio
async def test_anthropic_provider_passes_through_anthropic_custom_tools() -> None:
    messages = FakeAnthropicMessages()
    fake_client = SimpleNamespace(messages=messages)
    client = AnthropicProviderClient(api_key="x", client=fake_client)

    payload = {
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "custom",
                "name": "lookup",
                "description": "Lookup records",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
    }

    await client.chat_completions(payload)

    assert messages.last_create["tools"] == payload["tools"]
