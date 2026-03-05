from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage

from app.services.model_provider_chat_model import ModelProviderChatModel


@pytest.mark.asyncio
async def test_model_provider_chat_model_posts_to_internal_chat_messages_path() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat_1",
                "model": "architect",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
                "finish_reason": "stop",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    model = ModelProviderChatModel(model="architect", base_url="http://test/v1", async_http_client=client)

    response = await model.ainvoke([HumanMessage(content="hello")])

    assert response.content == "ok"
    assert captured["path"] == "/v1/internal/chat/messages"
