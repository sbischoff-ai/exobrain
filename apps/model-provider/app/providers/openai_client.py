from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable, ClassVar

from openai import APIError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.contracts.native_chat import (
    AssistantMessage,
    CompletionFrame,
    FunctionToolDefinition,
    NativeChatRequest,
    NativeChatResponse,
    StreamFrame,
    StructuredOutputIntent,
    TextBlock,
    TextDeltaFrame,
    ToolCallBlock,
    ToolCallFrame,
    ToolChoicePolicy,
    Usage,
    UsageFrame,
)
from app.providers.base import ProviderClient, ProviderClientError


class OpenAIProviderClient(ProviderClient):
    _shared_clients: ClassVar[dict[tuple[str, float, int], AsyncOpenAI]] = {}
    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 8,
        max_concurrent_requests: int = 2,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or self._get_shared_client(api_key, timeout_seconds, max_retries)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent_requests))


    @classmethod
    def _get_shared_client(cls, api_key: str, timeout_seconds: float, max_retries: int) -> AsyncOpenAI:
        key = (api_key, timeout_seconds, max_retries)
        shared = cls._shared_clients.get(key)
        if shared is not None:
            return shared
        client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)
        cls._shared_clients[key] = client
        return client

    async def _with_rate_limit_retry(self, operation: Callable[[], Awaitable[Any]]) -> Any:
        async with self._semaphore:
            delay = 1.0
            for attempt in range(5):
                try:
                    return await operation()
                except RateLimitError:
                    if attempt == 4:
                        raise
                    await asyncio.sleep(delay + random.uniform(0, 0.25))
                    delay = min(delay * 2.0, 8.0)

    def _normalize_chat_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        max_tokens = normalized.pop("max_tokens", None)
        if max_tokens is not None and "max_completion_tokens" not in normalized:
            normalized["max_completion_tokens"] = max_tokens
        return normalized

    def _native_to_openai_messages(self, request: NativeChatRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            role = message.role
            for block in message.content:
                if role == "system" and block.type == "text":
                    messages.append({"role": "system", "content": block.text})
                elif role == "user" and block.type == "text":
                    messages.append({"role": "user", "content": block.text})
                elif role == "user" and block.type == "tool_result":
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": block.tool_call_id,
                            "content": block.content if isinstance(block.content, str) else json.dumps(block.content),
                        }
                    )
                elif role == "assistant" and block.type == "text":
                    messages.append({"role": "assistant", "content": block.text})
                elif role == "assistant" and block.type == "tool_call":
                    messages.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": block.id,
                                    "type": "function",
                                    "function": {
                                        "name": block.name,
                                        "arguments": json.dumps(block.arguments),
                                    },
                                }
                            ],
                        }
                    )
        return messages

    def _native_tool_choice(self, tool_choice: ToolChoicePolicy | None) -> Any:
        if tool_choice is None:
            return None
        if tool_choice.type in {"auto", "none"}:
            return tool_choice.type
        if tool_choice.type == "required":
            return "required"
        return {"type": "function", "function": {"name": tool_choice.name}}

    def _native_response_format(self, intent: StructuredOutputIntent | None) -> dict[str, Any] | None:
        if intent is None:
            return None
        payload: dict[str, Any] = {"schema": intent.json_schema}
        if intent.name:
            payload["name"] = intent.name
        if intent.strict:
            payload["strict"] = True
        return {"type": "json_schema", "json_schema": payload}

    def _native_tools(self, tools: list[FunctionToolDefinition]) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _to_native_payload(self, request: NativeChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": self._native_to_openai_messages(request),
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        tools = self._native_tools(request.tools)
        if tools:
            payload["tools"] = tools
        tool_choice = self._native_tool_choice(request.tool_choice)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        response_format = self._native_response_format(request.structured_output)
        if response_format is not None:
            payload["response_format"] = response_format
        return payload

    def _openai_to_native_response(self, request: NativeChatRequest, payload: dict[str, Any]) -> NativeChatResponse:
        choice = payload.get("choices", [{}])[0]
        message = choice.get("message", {})
        content_blocks: list[TextBlock | ToolCallBlock] = []
        content = message.get("content")
        if isinstance(content, str) and content:
            content_blocks.append(TextBlock(text=content))
        for tool_call in message.get("tool_calls", []) or []:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function", {})
            arguments = function.get("arguments", "{}")
            parsed_arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            content_blocks.append(
                ToolCallBlock(
                    id=tool_call.get("id", f"call_{uuid.uuid4().hex}"),
                    name=function.get("name", "tool"),
                    arguments=parsed_arguments if isinstance(parsed_arguments, dict) else {"value": parsed_arguments},
                )
            )

        usage_payload = payload.get("usage", {})
        usage = Usage(
            input_tokens=usage_payload.get("prompt_tokens", 0),
            output_tokens=usage_payload.get("completion_tokens", 0),
            total_tokens=usage_payload.get("total_tokens", 0),
        )
        return NativeChatResponse(
            id=payload.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            model=request.model,
            message=AssistantMessage(content=content_blocks),
            finish_reason=choice.get("finish_reason"),
            usage=usage,
        )

    async def native_chat(self, request: NativeChatRequest) -> NativeChatResponse:
        payload = self._to_native_payload(request)
        try:
            response = await self._with_rate_limit_retry(
                lambda: self._client.chat.completions.create(**self._normalize_chat_payload(payload))
            )
            return self._openai_to_native_response(request, response.model_dump(mode="json"))
        except (APITimeoutError,) as exc:
            raise ProviderClientError(status_code=504, message=str(exc)) from exc
        except (RateLimitError,) as exc:
            raise ProviderClientError(status_code=429, message=str(exc)) from exc
        except (APIStatusError,) as exc:
            status = exc.status_code
            mapped_status = 502 if status and status >= 500 else (status or 502)
            raise ProviderClientError(status_code=mapped_status, message=str(exc)) from exc
        except APIError as exc:
            raise ProviderClientError(status_code=502, message=str(exc)) from exc

    async def native_chat_stream(self, request: NativeChatRequest) -> AsyncIterator[StreamFrame]:
        payload = self._to_native_payload(request)
        payload["stream"] = True
        pending_tool_calls: dict[int, dict[str, Any]] = {}
        try:
            stream = await self._with_rate_limit_retry(
                lambda: self._client.chat.completions.create(**self._normalize_chat_payload(payload))
            )
            async for chunk in stream:
                data = chunk.model_dump(mode="json")
                for choice in data.get("choices", []):
                    delta = choice.get("delta", {})
                    if delta.get("content"):
                        yield TextDeltaFrame(text=delta["content"])
                    for tool_call in delta.get("tool_calls", []) or []:
                        if not isinstance(tool_call, dict):
                            continue
                        index = tool_call.get("index", 0)
                        fn = tool_call.get("function", {}) if isinstance(tool_call.get("function"), dict) else {}
                        call_state = pending_tool_calls.setdefault(
                            index,
                            {
                                "id": tool_call.get("id"),
                                "name": fn.get("name"),
                                "index": int(index) if isinstance(index, int) else 0,
                                "arguments": "",
                            },
                        )

                        if tool_call.get("id"):
                            call_state["id"] = tool_call["id"]
                        if fn.get("name"):
                            call_state["name"] = fn["name"]
                        if isinstance(fn.get("arguments"), str):
                            call_state["arguments"] += fn["arguments"]

                    if choice.get("finish_reason"):
                        for _, item in sorted(pending_tool_calls.items(), key=lambda pair: pair[0]):
                            yield ToolCallFrame(
                                id=str(item.get("id") or f"call_{uuid.uuid4().hex}"),
                                name=str(item.get("name") or "tool"),
                                index=int(item.get("index") or 0),
                                arguments=self._coerce_tool_arguments(item.get("arguments")),
                            )
                        pending_tool_calls.clear()
                        yield CompletionFrame(finish_reason=choice["finish_reason"])
                usage_payload = data.get("usage")
                if isinstance(usage_payload, dict):
                    yield UsageFrame(
                        usage=Usage(
                            input_tokens=usage_payload.get("prompt_tokens", 0),
                            output_tokens=usage_payload.get("completion_tokens", 0),
                            total_tokens=usage_payload.get("total_tokens", 0),
                        )
                    )
        except (APITimeoutError,) as exc:
            raise ProviderClientError(status_code=504, message=str(exc)) from exc
        except (RateLimitError,) as exc:
            raise ProviderClientError(status_code=429, message=str(exc)) from exc
        except (APIStatusError,) as exc:
            status = exc.status_code
            mapped_status = 502 if status and status >= 500 else (status or 502)
            raise ProviderClientError(status_code=mapped_status, message=str(exc)) from exc
        except APIError as exc:
            raise ProviderClientError(status_code=502, message=str(exc)) from exc

    def _coerce_tool_arguments(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
                if isinstance(parsed, dict):
                    return parsed
                return {"value": parsed}
            except json.JSONDecodeError:
                return {"raw": arguments}
        return {"value": arguments}

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._with_rate_limit_retry(
                lambda: self._client.chat.completions.create(**self._normalize_chat_payload(payload))
            )
            return response.model_dump(mode="json")
        except (APITimeoutError,) as exc:
            raise ProviderClientError(status_code=504, message=str(exc)) from exc
        except (RateLimitError,) as exc:
            raise ProviderClientError(status_code=429, message=str(exc)) from exc
        except (APIStatusError,) as exc:
            status = exc.status_code
            mapped_status = 502 if status and status >= 500 else (status or 502)
            raise ProviderClientError(status_code=mapped_status, message=str(exc)) from exc
        except APIError as exc:
            raise ProviderClientError(status_code=502, message=str(exc)) from exc

    async def chat_completions_stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        try:
            stream = await self._with_rate_limit_retry(
                lambda: self._client.chat.completions.create(**self._normalize_chat_payload(payload))
            )
            async for chunk in stream:
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
        except (APITimeoutError,) as exc:
            raise ProviderClientError(status_code=504, message=str(exc)) from exc
        except (RateLimitError,) as exc:
            raise ProviderClientError(status_code=429, message=str(exc)) from exc
        except (APIStatusError,) as exc:
            status = exc.status_code
            mapped_status = 502 if status and status >= 500 else (status or 502)
            raise ProviderClientError(status_code=mapped_status, message=str(exc)) from exc
        except APIError as exc:
            raise ProviderClientError(status_code=502, message=str(exc)) from exc

    async def embeddings(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._with_rate_limit_retry(lambda: self._client.embeddings.create(**payload))
            return response.model_dump(mode="json")
        except (APITimeoutError,) as exc:
            raise ProviderClientError(status_code=504, message=str(exc)) from exc
        except (RateLimitError,) as exc:
            raise ProviderClientError(status_code=429, message=str(exc)) from exc
        except (APIStatusError,) as exc:
            status = exc.status_code
            mapped_status = 502 if status and status >= 500 else (status or 502)
            raise ProviderClientError(status_code=mapped_status, message=str(exc)) from exc
        except APIError as exc:
            raise ProviderClientError(status_code=502, message=str(exc)) from exc
