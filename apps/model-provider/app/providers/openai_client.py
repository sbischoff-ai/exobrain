from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.providers.base import ProviderClient


class OpenAIProviderClient(ProviderClient):
    def __init__(self, api_key: str, timeout_seconds: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    async def chat_completions_stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        async with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield f"{line}\n\n"

    async def embeddings(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        return response.json()
