from __future__ import annotations

import logging
from typing import Any, Protocol

from app.adapters.tools.web_constants import _DEFAULT_FETCH_CHARS, _DEFAULT_MAX_RESULTS
from app.adapters.tools.web_parsing import parse_extract_result, parse_max_chars, parse_max_results, parse_search_results
from app.contracts.tools import (
    ToolExecutionError,
    ToolInvocationEnvelope,
    ToolInvocationCorrelation,
    ToolMetadata,
    ToolResultEnvelope,
)

logger = logging.getLogger(__name__)


class WebToolError(RuntimeError):
    """Raised when a web tool request cannot be completed."""


class TavilySearchClient(Protocol):
    def invoke(self, payload: dict[str, Any]) -> Any: ...


class TavilyExtractClient(Protocol):
    def invoke(self, payload: dict[str, Any]) -> Any: ...


class WebToolsAdapter(Protocol):
    """Adapter contract for web-search/fetch providers."""

    def web_search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        recency_days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    def web_fetch(self, *, url: str, max_chars: int = _DEFAULT_FETCH_CHARS) -> dict[str, Any]: ...


def load_tavily_clients() -> tuple[type[Any], type[Any]]:
    try:
        from langchain_tavily import TavilyExtract, TavilySearch
    except ImportError as exc:  # pragma: no cover
        raise WebToolError("web tools unavailable: install langchain-tavily") from exc
    return TavilySearch, TavilyExtract


def web_tool_metadata() -> tuple[ToolMetadata, ToolMetadata]:
    return (
        ToolMetadata(
            name="web_search",
            description=(
                "Search the web for candidate sources. Use for citations, current events, or "
                "specialized facts. Returns title, normalized url, snippet, score, and published_at."
            ),
            json_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1},
                    "recency_days": {"type": "integer", "minimum": 1},
                    "include_domains": {"type": "array", "items": {"type": "string"}},
                    "exclude_domains": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["query"],
            },
        ),
        ToolMetadata(
            name="web_fetch",
            description=(
                "Fetch readable plaintext from a single URL. Use after web_search or on a URL the user "
                "explicitly provided. Returns url, title, content_text, extracted_at, and content_truncated."
            ),
            json_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "minLength": 1},
                    "max_chars": {"type": "integer", "minimum": 256},
                },
                "required": ["url"],
            },
        ),
    )


class TavilyWebAdapter(WebToolsAdapter):
    """Tavily-backed web adapter with tool invocation/result envelopes."""

    def __init__(self, *, tavily_api_key: str | None = None) -> None:
        self._tavily_api_key = tavily_api_key

    def _build_search_client(self, *, max_results: int) -> TavilySearchClient:
        TavilySearch, _ = load_tavily_clients()
        return TavilySearch(
            max_results=parse_max_results(max_results),
            topic="general",
            tavily_api_key=self._tavily_api_key,
        )

    def _build_extract_client(self) -> TavilyExtractClient:
        _, TavilyExtract = load_tavily_clients()
        return TavilyExtract(
            include_images=False,
            extract_depth="advanced",
            tavily_api_key=self._tavily_api_key,
        )

    def _search_invoke(self, payload: dict[str, Any], *, max_results: int) -> Any:
        return self._build_search_client(max_results=max_results).invoke(payload)

    def _extract_invoke(self, payload: dict[str, Any]) -> Any:
        return self._build_extract_client().invoke(payload)

    def _invoke_web_search(
        self,
        *,
        query: str,
        max_results: int,
        recency_days: int | None,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> ToolResultEnvelope[list[dict[str, Any]]]:
        payload: dict[str, Any] = {"query": query}
        if recency_days is not None:
            payload["days"] = max(recency_days, 1)
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        _ = ToolInvocationEnvelope(
            tool_name="web_search",
            args=payload,
            correlation=ToolInvocationCorrelation(request_id="internal-web-search"),
        )

        try:
            raw = self._search_invoke(payload, max_results=max_results)
            return ToolResultEnvelope(status="ok", result=parse_search_results(raw))
        except Exception as exc:  # pragma: no cover
            logger.exception("web_search failed")
            return ToolResultEnvelope(
                status="error",
                error=ToolExecutionError(code="web_search_failed", message=str(exc), retryable=True),
            )

    def _invoke_web_fetch(self, *, url: str, max_chars: int) -> ToolResultEnvelope[dict[str, Any]]:
        bounded_chars = parse_max_chars(max_chars)
        payload: dict[str, Any] = {"urls": [url]}
        _ = ToolInvocationEnvelope(
            tool_name="web_fetch",
            args=payload,
            correlation=ToolInvocationCorrelation(request_id="internal-web-fetch"),
        )

        try:
            raw = self._extract_invoke(payload)
            parsed = parse_extract_result(raw, max_chars=bounded_chars, source_url=url)
            return ToolResultEnvelope(status="ok", result=parsed)
        except Exception as exc:  # pragma: no cover
            logger.exception("web_fetch failed")
            return ToolResultEnvelope(
                status="error",
                error=ToolExecutionError(code="web_fetch_failed", message=str(exc), retryable=True),
            )

    def web_search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        recency_days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        result = self._invoke_web_search(
            query=query,
            max_results=max_results,
            recency_days=recency_days,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )
        if result.status == "error":
            raise WebToolError(f"web_search failed: {result.error.message}")
        return result.result or []

    def web_fetch(self, *, url: str, max_chars: int = _DEFAULT_FETCH_CHARS) -> dict[str, Any]:
        result = self._invoke_web_fetch(url=url, max_chars=max_chars)
        if result.status == "error":
            raise WebToolError(f"web_fetch failed: {result.error.message}")
        return result.result or {}
