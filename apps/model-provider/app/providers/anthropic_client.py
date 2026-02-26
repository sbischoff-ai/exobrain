from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator

import httpx

from app.providers.base import ProviderClient


class AnthropicProviderClient(ProviderClient):
    def __init__(self, api_key: str, timeout_seconds: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=timeout_seconds,
        )

    def _to_messages_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        mapped = dict(payload)
        mapped["max_tokens"] = mapped.get("max_tokens", 1024)
        return mapped

    def _to_openai_response(self, payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        text = "".join(block.get("text", "") for block in response.get("content", []) if block.get("type") == "text")
        return {
            "id": response.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": response.get("stop_reason", "stop")}],
            "usage": {
                "prompt_tokens": response.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": response.get("usage", {}).get("output_tokens", 0),
                "total_tokens": response.get("usage", {}).get("input_tokens", 0)
                + response.get("usage", {}).get("output_tokens", 0),
            },
        }

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = self._to_messages_payload(payload)
        response = await self._client.post("/v1/messages", json=upstream_payload)
        response.raise_for_status()
        return self._to_openai_response(payload, response.json())

    async def chat_completions_stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        upstream_payload = self._to_messages_payload(payload)
        upstream_payload["stream"] = True
        async with self._client.stream("POST", "/v1/messages", json=upstream_payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    yield "data: [DONE]\n\n"
                    continue
                payload_json = json.loads(data)
                delta_text = ""
                if payload_json.get("type") == "content_block_delta":
                    delta_text = payload_json.get("delta", {}).get("text", "")
                if delta_text:
                    chunk = {
                        "id": payload_json.get("message", {}).get("id", f"chatcmpl-{uuid.uuid4().hex}"),
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": payload["model"],
                        "choices": [{"index": 0, "delta": {"content": delta_text}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

    async def embeddings(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise httpx.HTTPStatusError(
            message="Anthropic embeddings are not configured",
            request=httpx.Request("POST", "https://api.anthropic.com/v1/embeddings"),
            response=httpx.Response(400),
        )
