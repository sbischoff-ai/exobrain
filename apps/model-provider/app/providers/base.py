from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.contracts.native_chat import NativeChatRequest, NativeChatResponse, StreamFrame


@dataclass
class ProviderClientError(Exception):
    status_code: int
    message: str


class ProviderClient(ABC):
    @abstractmethod
    async def native_chat(self, request: NativeChatRequest) -> NativeChatResponse:
        raise NotImplementedError

    @abstractmethod
    async def native_chat_stream(self, request: NativeChatRequest) -> AsyncIterator[StreamFrame]:
        raise NotImplementedError

    @abstractmethod
    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def chat_completions_stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        raise NotImplementedError

    @abstractmethod
    async def embeddings(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
