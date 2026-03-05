from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import AliasConfig, ModelsConfig, load_models_config
from app.contracts.native_chat import (
    AssistantMessage,
    CompletionFrame,
    NativeChatRequest,
    NativeChatResponse,
    StreamFrame,
    StructuredOutputIntent,
    TextBlock,
    TextDeltaFrame,
    ToolCallBlock,
    ToolCallFrame,
    ToolChoiceAny,
    ToolChoiceAuto,
    ToolChoiceNone,
    ToolChoicePolicy,
    ToolChoiceTool,
    ToolResultBlock,
    Usage,
    UsageFrame,
)
from app.providers.anthropic_client import AnthropicProviderClient
from app.providers.base import ProviderClient, ProviderClientError
from app.providers.openai_client import OpenAIProviderClient
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self, settings: Settings, models_config: ModelsConfig) -> None:
        self._settings = settings
        self._models_config = models_config
        self._clients: dict[str, ProviderClient] = {}
        providers = {alias.provider for alias in models_config.aliases.values()}
        if "openai" in providers:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY required for configured OpenAI aliases")
            self._clients["openai"] = OpenAIProviderClient(settings.openai_api_key, settings.provider_timeout_seconds)
        if "anthropic" in providers:
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY required for configured Anthropic aliases")
            self._clients["anthropic"] = AnthropicProviderClient(settings.anthropic_api_key, settings.provider_timeout_seconds)

    def resolve(self, alias: str) -> tuple[AliasConfig, ProviderClient]:
        config = self._models_config.aliases.get(alias)
        if not config:
            raise HTTPException(status_code=404, detail=f"Unknown model alias '{alias}'")
        client = self._clients.get(config.provider)
        if not client:
            raise HTTPException(status_code=500, detail=f"No provider client registered for {config.provider}")
        return config, client


def merge_payload(alias_config: AliasConfig, payload: dict[str, Any]) -> dict[str, Any]:
    merged = {**alias_config.defaults, **payload}
    response_format = _normalize_structured_output_payload(payload)
    if response_format is not None:
        merged["response_format"] = response_format
    merged["model"] = alias_config.upstream_model
    return merged


def _normalize_structured_output_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    response_format = payload.get("response_format")
    if response_format is None:
        return None
    if not isinstance(response_format, dict):
        raise HTTPException(status_code=400, detail="response_format must be an object")

    if response_format.get("type") != "json_schema":
        raise HTTPException(status_code=400, detail="response_format.type must be 'json_schema'")

    json_schema = response_format.get("json_schema")
    if not isinstance(json_schema, dict) or not json_schema:
        raise HTTPException(status_code=400, detail="response_format.json_schema must be a non-empty object")

    return {"type": "json_schema", "json_schema": json_schema}


def _to_native_request(payload: dict[str, Any], alias_config: AliasConfig) -> NativeChatRequest:
    messages = []
    for message in payload.get("messages", []):
        role = message.get("role")
        content_blocks = []
        if role == "tool":
            content_blocks.append(
                ToolResultBlock(tool_call_id=message.get("tool_call_id", "tool_call"), content=message.get("content", ""))
            )
            role = "user"
        else:
            content = message.get("content")
            if isinstance(content, str) and content:
                content_blocks.append(TextBlock(text=content))
            for tool_call in message.get("tool_calls", []) or []:
                function = tool_call.get("function", {})
                arguments = function.get("arguments", "{}")
                parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
                content_blocks.append(
                    ToolCallBlock(
                        id=tool_call.get("id", f"call_{uuid.uuid4().hex}"),
                        name=function.get("name", "tool"),
                        arguments=parsed if isinstance(parsed, dict) else {"value": parsed},
                    )
                )
        if role in {"system", "user", "assistant"}:
            messages.append({"role": role, "content": content_blocks})

    tools = []
    for tool in payload.get("tools", []) or []:
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            function = tool["function"]
            tools.append(
                {
                    "type": "function",
                    "name": function.get("name", "tool"),
                    "description": function.get("description"),
                    "parameters": function.get("parameters") or {},
                }
            )

    tool_choice: ToolChoicePolicy | None = None
    tool_choice_payload = payload.get("tool_choice")
    if tool_choice_payload == "auto":
        tool_choice = ToolChoiceAuto()
    elif tool_choice_payload == "none":
        tool_choice = ToolChoiceNone()
    elif tool_choice_payload == "required":
        tool_choice = ToolChoiceAny()
    elif isinstance(tool_choice_payload, dict) and tool_choice_payload.get("type") == "function":
        function = tool_choice_payload.get("function", {})
        if function.get("name"):
            tool_choice = ToolChoiceTool(name=function["name"])

    structured_output = None
    response_format = _normalize_structured_output_payload(payload)
    if response_format:
        json_schema = response_format["json_schema"]
        schema = json_schema.get("schema", json_schema)
        structured_output = StructuredOutputIntent(
            name=json_schema.get("name"),
            schema=schema,
            strict=bool(json_schema.get("strict", False)),
        )

    return NativeChatRequest(
        model=alias_config.upstream_model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        structured_output=structured_output,
        stream=bool(payload.get("stream", False)),
        temperature=payload.get("temperature"),
        max_tokens=payload.get("max_tokens") or alias_config.defaults.get("max_tokens"),
    )


def _native_to_openai_response(response: NativeChatResponse, alias: str) -> dict[str, Any]:
    text = ""
    tool_calls = []
    for block in response.message.content:
        if block.type == "text":
            text += block.text
        elif block.type == "tool_call":
            tool_calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {"name": block.name, "arguments": json.dumps(block.arguments)},
                }
            )

    message: dict[str, Any] = {"role": "assistant", "content": text}
    if tool_calls:
        message["tool_calls"] = tool_calls

    return {
        "id": response.id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": alias,
        "choices": [{"index": 0, "message": message, "finish_reason": response.finish_reason}],
        "usage": {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


def _openai_stream_frame(frame: StreamFrame, *, model: str, message_id: str) -> str:
    if isinstance(frame, TextDeltaFrame):
        payload = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"content": frame.text}, "finish_reason": None}],
        }
        return f"data: {json.dumps(payload)}\n\n"
    if isinstance(frame, ToolCallFrame):
        payload = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "id": frame.id,
                                "type": "function",
                                "function": {"name": frame.name, "arguments": json.dumps(frame.arguments)},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        }
        return f"data: {json.dumps(payload)}\n\n"
    if isinstance(frame, CompletionFrame):
        payload = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": frame.finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n"
    if isinstance(frame, UsageFrame):
        payload = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            "usage": {
                "prompt_tokens": frame.usage.input_tokens,
                "completion_tokens": frame.usage.output_tokens,
                "total_tokens": frame.usage.total_tokens,
            },
        }
        return f"data: {json.dumps(payload)}\n\n"
    return ""


def _format_stream_error(exc: Exception, *, alias: str, provider: str) -> str:
    mapped = map_provider_error(exc, alias=alias, provider=provider)
    detail = mapped.detail if isinstance(mapped.detail, str) else "streaming error"
    payload = {"error": {"message": detail, "type": "provider_error", "code": mapped.status_code}}
    return f"data: {json.dumps(payload)}\n\n"


def map_provider_error(exc: Exception, *, alias: str, provider: str) -> HTTPException:
    if isinstance(exc, ProviderClientError):
        return HTTPException(
            status_code=exc.status_code,
            detail=f"Provider error provider={provider} alias={alias}: {exc.message}",
        )
    return HTTPException(status_code=502, detail=f"Unexpected provider error provider={provider} alias={alias}")


settings = get_settings()
logging.basicConfig(level=settings.effective_log_level)
models_config = load_models_config(settings.model_provider_config_path)
registry = ProviderRegistry(settings, models_config)
app = FastAPI(title="model-provider", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models() -> dict[str, list[dict[str, str]]]:
    return {
        "object": "list",
        "data": [
            {"id": alias.alias, "object": "model", "owned_by": "model-provider"}
            for alias in models_config.aliases.values()
        ],
    }


@app.post("/v1/internal/chat/messages", response_model=NativeChatResponse)
async def internal_chat_messages(request: NativeChatRequest, x_request_id: str | None = Header(default=None)) -> Response:
    request_id = x_request_id or str(uuid.uuid4())
    alias_config, provider_client = registry.resolve(request.model)

    request_payload = request.model_copy(update={"model": alias_config.upstream_model})
    start = time.perf_counter()

    try:
        if request.stream:
            async def event_stream() -> AsyncIterator[str]:
                try:
                    async for frame in provider_client.native_chat_stream(request_payload):
                        yield f"data: {frame.model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as exc:
                    logger.warning(
                        "native chat stream provider error",
                        extra={"request_id": request_id, "alias": request.model, "provider": alias_config.provider},
                    )
                    yield _format_stream_error(exc, alias=request.model, provider=alias_config.provider)
                    yield "data: [DONE]\n\n"

            headers = {"x-request-id": request_id, "Cache-Control": "no-cache"}
            return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)

        response_payload = await provider_client.native_chat(request_payload)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "native chat",
            extra={
                "request_id": request_id,
                "alias": request.model,
                "provider": alias_config.provider,
                "upstream_model": alias_config.upstream_model,
                "latency_ms": latency_ms,
            },
        )
        response_with_alias = response_payload.model_copy(update={"model": request.model})
        return JSONResponse(content=response_with_alias.model_dump(mode="json"), headers={"x-request-id": request_id})
    except HTTPException:
        raise
    except Exception as exc:
        raise map_provider_error(exc, alias=request.model, provider=alias_config.provider) from exc


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, x_request_id: str | None = Header(default=None)) -> Response:
    request_id = x_request_id or str(uuid.uuid4())
    payload = await request.json()
    alias = payload.get("model")
    if not alias:
        raise HTTPException(status_code=400, detail="model is required")
    alias_config, provider_client = registry.resolve(alias)
    start = time.perf_counter()

    try:
        native_request = _to_native_request(payload, alias_config)
        if native_request.stream:
            message_id = f"chatcmpl-{uuid.uuid4().hex}"

            async def event_stream() -> AsyncIterator[str]:
                try:
                    async for frame in provider_client.native_chat_stream(native_request):
                        chunk = _openai_stream_frame(frame, model=alias, message_id=message_id)
                        if chunk:
                            yield chunk
                    yield "data: [DONE]\n\n"
                except Exception as exc:
                    logger.warning(
                        "chat completion stream provider error",
                        extra={"request_id": request_id, "alias": alias, "provider": alias_config.provider},
                    )
                    yield _format_stream_error(exc, alias=alias, provider=alias_config.provider)
                    yield "data: [DONE]\n\n"

            headers = {"x-request-id": request_id, "Cache-Control": "no-cache"}
            return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)

        native_response = await provider_client.native_chat(native_request)
        response_payload = _native_to_openai_response(native_response, alias)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "chat completion",
            extra={
                "request_id": request_id,
                "alias": alias,
                "provider": alias_config.provider,
                "upstream_model": alias_config.upstream_model,
                "latency_ms": latency_ms,
            },
        )
        return JSONResponse(content=response_payload, headers={"x-request-id": request_id})
    except HTTPException:
        raise
    except Exception as exc:
        raise map_provider_error(exc, alias=alias, provider=alias_config.provider) from exc


@app.post("/v1/embeddings")
async def embeddings(request: Request, x_request_id: str | None = Header(default=None)) -> Response:
    request_id = x_request_id or str(uuid.uuid4())
    payload = await request.json()
    alias = payload.get("model")
    if not alias:
        raise HTTPException(status_code=400, detail="model is required")
    alias_config, provider_client = registry.resolve(alias)
    merged_payload = merge_payload(alias_config, payload)

    try:
        response_payload = await provider_client.embeddings(merged_payload)
        return JSONResponse(content=response_payload, headers={"x-request-id": request_id})
    except Exception as exc:
        raise map_provider_error(exc, alias=alias, provider=alias_config.provider) from exc
