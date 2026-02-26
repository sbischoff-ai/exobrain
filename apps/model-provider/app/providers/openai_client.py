from __future__ import annotations

from typing import Any, AsyncIterator

from openai import APIError, APIStatusError, AsyncOpenAI, APITimeoutError, RateLimitError

from app.providers.base import ProviderClient, ProviderClientError


class OpenAIProviderClient(ProviderClient):
    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 60.0,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.chat.completions.create(**payload)
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
            stream = await self._client.chat.completions.create(**payload)
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
            response = await self._client.embeddings.create(**payload)
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
