from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator

from anthropic import (
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)

from app.providers.base import ProviderClient, ProviderClientError


class AnthropicProviderClient(ProviderClient):
    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 60.0,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self._client = client or AsyncAnthropic(api_key=api_key, timeout=timeout_seconds)

    def _to_messages_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        mapped = dict(payload)
        mapped["max_tokens"] = mapped.get("max_tokens", 1024)

        tools = mapped.get("tools")
        if isinstance(tools, list):
            anthropic_tools: list[dict[str, Any]] = []
            for tool in tools:
                if (
                    isinstance(tool, dict)
                    and tool.get("type") == "function"
                    and isinstance(tool.get("function"), dict)
                ):
                    function = tool["function"]
                    input_schema = function.get("parameters")
                    if not isinstance(input_schema, dict):
                        input_schema = {"type": "object", "properties": {}}
                    elif "type" not in input_schema:
                        input_schema = {"type": "object", **input_schema}
                    elif input_schema.get("type") != "object":
                        input_schema = {
                            "type": "object",
                            "properties": {"input": input_schema},
                            "required": ["input"],
                        }

                    anthropic_tools.append(
                        {
                            "type": "custom",
                            "name": function.get("name"),
                            "description": function.get("description") or "",
                            "input_schema": input_schema,
                        }
                    )
                elif isinstance(tool, dict):
                    anthropic_tools.append(tool)
            mapped["tools"] = anthropic_tools

        tool_choice = mapped.get("tool_choice")
        if isinstance(tool_choice, str):
            if tool_choice == "auto":
                mapped["tool_choice"] = {"type": "auto"}
            elif tool_choice == "none":
                mapped["tool_choice"] = {"type": "none"}
            elif tool_choice == "required":
                mapped["tool_choice"] = {"type": "any"}
        elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
            function = tool_choice.get("function")
            if isinstance(function, dict) and function.get("name"):
                mapped["tool_choice"] = {"type": "tool", "name": function["name"]}

        response_format = mapped.pop("response_format", None)
        if response_format is not None:
            json_schema = response_format.get("json_schema") if isinstance(response_format, dict) else None
            schema = json_schema.get("schema") if isinstance(json_schema, dict) else None
            if not isinstance(schema, dict) or not schema:
                raise ProviderClientError(
                    status_code=400,
                    message="response_format.json_schema.schema must be a non-empty object for Anthropic",
                )
            mapped["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        return mapped

    def _to_openai_response(self, payload: dict[str, Any], response: Any) -> dict[str, Any]:
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        input_tokens = getattr(response.usage, "input_tokens", 0) if response.usage else 0
        output_tokens = getattr(response.usage, "output_tokens", 0) if response.usage else 0
        return {
            "id": getattr(response, "id", f"chatcmpl-{uuid.uuid4().hex}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": getattr(response, "stop_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.messages.create(**self._to_messages_payload(payload))
            return self._to_openai_response(payload, response)
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
        message_id = f"chatcmpl-{uuid.uuid4().hex}"
        try:
            async with self._client.messages.stream(**self._to_messages_payload(payload)) as stream:
                async for text in stream.text_stream:
                    if not text:
                        continue
                    chunk = {
                        "id": message_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": payload["model"],
                        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
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
        raise ProviderClientError(status_code=400, message="Anthropic embeddings are not configured")
