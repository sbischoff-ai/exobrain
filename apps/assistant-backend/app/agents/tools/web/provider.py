from __future__ import annotations

import logging
from typing import Any, Protocol

from app.agents.tools.web.constants import _DEFAULT_FETCH_CHARS, _DEFAULT_MAX_RESULTS
from app.agents.tools.web.parsing import parse_extract_result, parse_max_chars, parse_max_results, parse_search_results

logger = logging.getLogger(__name__)


class WebToolError(RuntimeError):
    """Raised when a web tool request cannot be completed."""


class WebTools(Protocol):
    """Protocol for web-search/fetch providers."""

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


def load_tavily_clients() -> tuple[Any, Any]:
    try:
        from langchain_tavily import TavilyExtract, TavilySearch
    except ImportError as exc:  # pragma: no cover
        raise WebToolError("web tools unavailable: install langchain-tavily") from exc
    return TavilySearch, TavilyExtract


class TavilyWebTools(WebTools):
    """Tavily-backed web tools implementation."""

    def __init__(self, *, tavily_api_key: str | None = None) -> None:
        self._tavily_api_key = tavily_api_key

    def _search_invoke(self, payload: dict[str, Any], *, max_results: int) -> Any:
        TavilySearch, _ = load_tavily_clients()
        client = TavilySearch(
            max_results=parse_max_results(max_results),
            topic="general",
            tavily_api_key=self._tavily_api_key,
        )
        return client.invoke(payload)

    def _extract_invoke(self, payload: dict[str, Any]) -> Any:
        _, TavilyExtract = load_tavily_clients()
        client = TavilyExtract(
            include_images=False,
            extract_depth="advanced",
            tavily_api_key=self._tavily_api_key,
        )
        return client.invoke(payload)

    def web_search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        recency_days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"query": query}
        if recency_days is not None:
            payload["days"] = max(recency_days, 1)
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        try:
            raw = self._search_invoke(payload, max_results=max_results)
        except Exception as exc:  # pragma: no cover
            logger.exception("web_search failed")
            raise WebToolError(f"web_search failed: {exc}") from exc

        return parse_search_results(raw)

    def web_fetch(self, *, url: str, max_chars: int = _DEFAULT_FETCH_CHARS) -> dict[str, Any]:
        bounded_chars = parse_max_chars(max_chars)

        try:
            raw = self._extract_invoke({"urls": [url]})
        except Exception as exc:  # pragma: no cover
            logger.exception("web_fetch failed")
            raise WebToolError(f"web_fetch failed: {exc}") from exc

        return parse_extract_result(raw, max_chars=bounded_chars, source_url=url)
