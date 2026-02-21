from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RESULTS = 5
_MAX_RESULTS_LIMIT = 10
_DEFAULT_FETCH_CHARS = 8_000
_MAX_FETCH_CHARS = 20_000
_MAX_SNIPPET_CHARS = 320


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


def _normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), fragment="")
    return urlunsplit(normalized)


def _bound_text(value: str | None, *, max_chars: int) -> str:
    if not value:
        return ""
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 1].rstrip()}…"


def _parse_max_results(max_results: int) -> int:
    if max_results < 1:
        return 1
    return min(max_results, _MAX_RESULTS_LIMIT)


def _parse_max_chars(max_chars: int) -> int:
    if max_chars < 256:
        return 256
    return min(max_chars, _MAX_FETCH_CHARS)


def _load_tavily_clients() -> tuple[Any, Any]:
    try:
        from langchain_tavily import TavilyExtract, TavilySearch
    except ImportError as exc:  # pragma: no cover
        raise WebToolError("web tools unavailable: install langchain-tavily") from exc
    return TavilySearch, TavilyExtract


def _parse_search_results(raw: Any) -> list[dict[str, Any]]:
    candidates = raw.get("results", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []

    normalized_results: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        normalized_results.append(
            {
                "title": _bound_text(item.get("title"), max_chars=180),
                "url": _normalize_url(url),
                "snippet": _bound_text(item.get("content") or item.get("snippet"), max_chars=_MAX_SNIPPET_CHARS),
                "score": item.get("score"),
                "published_at": item.get("published_date") or item.get("published_at"),
            }
        )
    return normalized_results


def _parse_extract_result(raw: Any, *, max_chars: int, source_url: str) -> dict[str, Any]:
    candidates = raw.get("results", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    first = candidates[0] if candidates and isinstance(candidates[0], dict) else {}

    raw_content = str(first.get("raw_content") or first.get("content") or "")
    compact_raw = " ".join(raw_content.split())
    content_text = _bound_text(raw_content, max_chars=max_chars)

    return {
        "url": _normalize_url(str(first.get("url") or source_url)),
        "title": _bound_text(first.get("title"), max_chars=240) or None,
        "content_text": content_text,
        "extracted_at": datetime.now(tz=UTC).isoformat(),
        "content_truncated": len(compact_raw) > len(content_text),
    }


class TavilyWebTools(WebTools):
    """Tavily-backed web tools implementation."""

    def __init__(self, *, tavily_api_key: str | None = None) -> None:
        self._tavily_api_key = tavily_api_key

    def _search_invoke(self, payload: dict[str, Any], *, max_results: int) -> Any:
        TavilySearch, _ = _load_tavily_clients()
        client = TavilySearch(
            max_results=_parse_max_results(max_results),
            topic="general",
            tavily_api_key=self._tavily_api_key,
        )
        return client.invoke(payload)

    def _extract_invoke(self, payload: dict[str, Any]) -> Any:
        _, TavilyExtract = _load_tavily_clients()
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

        return _parse_search_results(raw)

    def web_fetch(self, *, url: str, max_chars: int = _DEFAULT_FETCH_CHARS) -> dict[str, Any]:
        bounded_chars = _parse_max_chars(max_chars)

        try:
            raw = self._extract_invoke({"urls": [url]})
        except Exception as exc:  # pragma: no cover
            logger.exception("web_fetch failed")
            raise WebToolError(f"web_fetch failed: {exc}") from exc

        return _parse_extract_result(raw, max_chars=bounded_chars, source_url=url)


def build_web_tools(*, web_tools: WebTools) -> list[StructuredTool]:
    """Build wrapped web tools with stable contracts."""

    def _web_search_tool(
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        recency_days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return web_tools.web_search(
            query=query,
            max_results=max_results,
            recency_days=recency_days,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )

    def _web_fetch_tool(url: str, max_chars: int = _DEFAULT_FETCH_CHARS) -> dict[str, Any]:
        return web_tools.web_fetch(url=url, max_chars=max_chars)

    return [
        StructuredTool.from_function(
            func=_web_search_tool,
            name="web_search",
            description=(
                "Search the web for candidate sources. Use for citations, current events, or "
                "specialized facts. Returns title, normalized url, snippet, score, and published_at."
            ),
        ),
        StructuredTool.from_function(
            func=_web_fetch_tool,
            name="web_fetch",
            description=(
                "Fetch readable plaintext from a single URL. Use after web_search or on a URL the user "
                "explicitly provided. Returns url, title, content_text, extracted_at, and content_truncated."
            ),
        ),
    ]
