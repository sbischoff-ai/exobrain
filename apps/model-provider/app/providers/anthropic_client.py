from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from typing import Any, AsyncIterator

import jsonref
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

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
                    tool_name = function.get("name")
                    if not isinstance(tool_name, str) or not tool_name:
                        raise ProviderClientError(
                            status_code=400,
                            message="Anthropic tool conversion requires function.name",
                        )

                    input_schema = self.normalize_tool_schema(function.get("parameters"), tool_name=tool_name)

                    anthropic_tools.append(
                        {
                            "type": "custom",
                            "name": tool_name,
                            "description": function.get("description") or "",
                            "input_schema": input_schema,
                        }
                    )
                elif isinstance(tool, dict) and isinstance(tool.get("name"), str) and isinstance(
                    tool.get("input_schema"), dict
                ):
                    anthropic_tools.append(tool)
                else:
                    raise ProviderClientError(
                        status_code=400,
                        message="Anthropic tools must be OpenAI function tools or Anthropic custom tools",
                    )
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
            schema = None
            if isinstance(json_schema, dict):
                nested_schema = json_schema.get("schema")
                if isinstance(nested_schema, dict) and nested_schema:
                    schema = nested_schema
                elif self._looks_like_json_schema_object(json_schema):
                    schema = json_schema
            if not isinstance(schema, dict) or not schema:
                raise ProviderClientError(
                    status_code=400,
                    message="response_format.json_schema must contain a non-empty object schema for Anthropic",
                )
            mapped["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        return mapped

    def normalize_tool_schema(self, parameters: Any, *, tool_name: str) -> dict[str, Any]:
        if not isinstance(parameters, dict):
            schema: dict[str, Any] = {"type": "object", "properties": {}}
        else:
            schema = deepcopy(parameters)

        schema = self._unwrap_json_schema_envelope(schema)

        self._remove_openapi_keywords(schema)

        if "definitions" in schema and "$defs" not in schema:
            schema["$defs"] = schema.pop("definitions")

        self._rewrite_definition_refs(schema)

        if "type" not in schema:
            schema["type"] = "object"
        elif schema.get("type") != "object":
            schema = {
                "type": "object",
                "properties": {"input": schema},
                "required": ["input"],
            }

        if self._schema_has_ref(schema):
            try:
                schema = jsonref.replace_refs(schema, loader=self._jsonref_loader, proxies=False, lazy_load=False)
            except Exception as exc:  # pragma: no cover - jsonref throws varying exceptions
                raise ProviderClientError(
                    status_code=400,
                    message=f'Invalid tool schema for tool "{tool_name}": {exc}',
                ) from exc

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ProviderClientError(
                status_code=400,
                message=f'Invalid tool schema for tool "{tool_name}": {exc.message}',
            ) from exc

        return schema

    def _unwrap_json_schema_envelope(self, schema: dict[str, Any]) -> dict[str, Any]:
        if schema.get("type") != "json_schema":
            return schema

        json_schema = schema.get("json_schema")
        if not isinstance(json_schema, dict):
            return schema

        nested_schema = json_schema.get("schema")
        if isinstance(nested_schema, dict) and nested_schema:
            return deepcopy(nested_schema)
        if json_schema:
            return deepcopy(json_schema)
        return schema

    def _looks_like_json_schema_object(self, schema: dict[str, Any]) -> bool:
        schema_keywords = {
            "$ref",
            "type",
            "properties",
            "required",
            "items",
            "anyOf",
            "allOf",
            "oneOf",
            "enum",
            "const",
            "additionalProperties",
            "patternProperties",
            "not",
        }
        return any(keyword in schema for keyword in schema_keywords)

    def _rewrite_definition_refs(self, node: Any) -> None:
        if isinstance(node, dict):
            ref_value = node.get("$ref")
            if isinstance(ref_value, str) and ref_value.startswith("#/definitions/"):
                node["$ref"] = ref_value.replace("#/definitions/", "#/$defs/", 1)
            for value in node.values():
                self._rewrite_definition_refs(value)
        elif isinstance(node, list):
            for item in node:
                self._rewrite_definition_refs(item)

    def _jsonref_loader(self, uri: str, **kwargs: Any) -> Any:
        raise ValueError(f"External $ref is not allowed: {uri}")

    def _remove_openapi_keywords(self, node: Any) -> None:
        if isinstance(node, dict):
            for key in ["nullable", "discriminator", "example", "examples", "xml", "externalDocs", "deprecated"]:
                node.pop(key, None)
            for value in node.values():
                self._remove_openapi_keywords(value)
        elif isinstance(node, list):
            for item in node:
                self._remove_openapi_keywords(item)

    def _schema_has_ref(self, node: Any) -> bool:
        if isinstance(node, dict):
            if "$ref" in node:
                return True
            return any(self._schema_has_ref(value) for value in node.values())
        if isinstance(node, list):
            return any(self._schema_has_ref(item) for item in node)
        return False

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
