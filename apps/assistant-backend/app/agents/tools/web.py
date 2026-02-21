from __future__ import annotations

from datetime import UTC, datetime
import logging
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RESULTS = 5
_MAX_RESULTS_LIMIT = 10
_DEFAULT_FETCH_CHARS = 8_000
_MAX_FETCH_CHARS = 20_000
_MAX_SNIPPET_CHARS = 320
_DEFAULT_MOCK_DATA = {
    "search": {
        "results": [
            {
                "title": "Offline mock result",
                "url": "https://example.com/offline-mock",
                "content": "Offline mock web_search result used for coding-agent environments.",
                "score": 1.0,
                "published_date": "2026-01-01",
            }
        ]
    },
    "extract": {
        "results": [
            {
                "url": "https://example.com/offline-mock",
                "title": "Offline mock fetch",
                "raw_content": "Offline mock content body for web_fetch in agent environments.",
            }
        ]
    },
}


class WebToolError(RuntimeError):
    """Raised when a web tool request cannot be completed."""


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


def _load_mock_payload(mock_data_file: str | None) -> dict[str, Any]:
    if not mock_data_file:
        return _DEFAULT_MOCK_DATA

    payload = json.loads(Path(mock_data_file).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WebToolError("mock web tool payload must be a JSON object")
    return payload


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


def web_search(
    query: str,
    max_results: int = _DEFAULT_MAX_RESULTS,
    recency_days: int | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    tavily_api_key: str | None = None,
    use_mock: bool = False,
    mock_data_file: str | None = None,
) -> list[dict[str, Any]]:
    """Find candidate web sources for a query."""

    if use_mock:
        payload = _load_mock_payload(mock_data_file)
        return _parse_search_results(payload.get("search", {}))

    TavilySearch, _ = _load_tavily_clients()
    client = TavilySearch(
        max_results=_parse_max_results(max_results),
        topic="general",
        tavily_api_key=tavily_api_key,
    )
    payload: dict[str, Any] = {"query": query}
    if recency_days is not None:
        payload["days"] = max(recency_days, 1)
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    try:
        raw = client.invoke(payload)
    except Exception as exc:  # pragma: no cover
        logger.exception("web_search failed")
        raise WebToolError(f"web_search failed: {exc}") from exc

    return _parse_search_results(raw)


def web_fetch(
    url: str,
    max_chars: int = _DEFAULT_FETCH_CHARS,
    tavily_api_key: str | None = None,
    use_mock: bool = False,
    mock_data_file: str | None = None,
) -> dict[str, Any]:
    """Fetch plain text content for a single URL."""

    _, TavilyExtract = _load_tavily_clients()
    bounded_chars = _parse_max_chars(max_chars)
    if use_mock:
        payload = _load_mock_payload(mock_data_file)
        return _parse_extract_result(payload.get("extract", {}), max_chars=bounded_chars, source_url=url)

    client = TavilyExtract(
        include_images=False,
        extract_depth="advanced",
        tavily_api_key=tavily_api_key,
    )

    try:
        raw = client.invoke({"urls": [url]})
    except Exception as exc:  # pragma: no cover
        logger.exception("web_fetch failed")
        raise WebToolError(f"web_fetch failed: {exc}") from exc

    return _parse_extract_result(raw, max_chars=bounded_chars, source_url=url)


def build_web_tools(
    *, tavily_api_key: str | None = None, use_mock: bool = False, mock_data_file: str | None = None
) -> list[StructuredTool]:
    """Build wrapped Tavily-backed tools with stable contracts."""

    def _web_search_tool(
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        recency_days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return web_search(
            query=query,
            max_results=max_results,
            recency_days=recency_days,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            tavily_api_key=tavily_api_key,
            use_mock=use_mock,
            mock_data_file=mock_data_file,
        )

    def _web_fetch_tool(url: str, max_chars: int = _DEFAULT_FETCH_CHARS) -> dict[str, Any]:
        return web_fetch(
            url=url,
            max_chars=max_chars,
            tavily_api_key=tavily_api_key,
            use_mock=use_mock,
            mock_data_file=mock_data_file,
        )

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
