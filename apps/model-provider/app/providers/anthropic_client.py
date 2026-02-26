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
