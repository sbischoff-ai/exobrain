from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import AliasConfig, ModelsConfig, load_models_config
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
    merged["model"] = alias_config.upstream_model
    return merged


def _format_stream_error(exc: Exception, *, alias: str, provider: str) -> str:
    mapped = map_provider_error(exc, alias=alias, provider=provider)
    detail = mapped.detail if isinstance(mapped.detail, str) else "streaming error"
    payload = {"error": {"message": detail, "type": "provider_error", "code": mapped.status_code}}
    import json

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


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, x_request_id: str | None = Header(default=None)) -> Response:
    request_id = x_request_id or str(uuid.uuid4())
    payload = await request.json()
    alias = payload.get("model")
    if not alias:
        raise HTTPException(status_code=400, detail="model is required")
    alias_config, provider_client = registry.resolve(alias)
    merged_payload = merge_payload(alias_config, payload)
    stream = bool(payload.get("stream"))
    start = time.perf_counter()

    try:
        if stream:
            async def event_stream() -> AsyncIterator[str]:
                try:
                    async for chunk in provider_client.chat_completions_stream(merged_payload):
                        yield chunk
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "chat completion stream provider error",
                        extra={"request_id": request_id, "alias": alias, "provider": alias_config.provider},
                    )
                    yield _format_stream_error(exc, alias=alias, provider=alias_config.provider)
                    yield "data: [DONE]\n\n"

            headers = {"x-request-id": request_id, "Cache-Control": "no-cache"}
            return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)

        response_payload = await provider_client.chat_completions(merged_payload)
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
    except Exception as exc:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
        raise map_provider_error(exc, alias=alias, provider=alias_config.provider) from exc
