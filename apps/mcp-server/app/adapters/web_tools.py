from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from app.contracts import WebSearchResultItem

_MAX_SNIPPET_CHARS = 320


class WebToolError(RuntimeError):
    """Raised when the web tool operation cannot be completed."""


class WebSearchClient(Protocol):
    def search(
        self,
        *,
        query: str,
        max_results: int,
        recency_days: int | None,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> Any: ...

    def extract(
        self,
        *,
        url: str,
    ) -> Any: ...


class WebSearchAdapter:
    def __init__(self, client: WebSearchClient):
        self._client = client

    def web_search(
        self,
        *,
        query: str,
        max_results: int,
        recency_days: int | None,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> list[WebSearchResultItem]:
        try:
            raw = self._client.search(
                query=query,
                max_results=max_results,
                recency_days=recency_days,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
            )
        except Exception as exc:  # pragma: no cover
            raise WebToolError(f"web_search failed: {exc}") from exc

        return _parse_search_results(raw)


class WebFetchAdapter:
    def __init__(self, client: WebSearchClient):
        self._client = client

    def web_fetch(
        self,
        *,
        url: str,
        max_chars: int,
    ) -> dict[str, Any]:
        try:
            raw = self._client.extract(url=url)
        except Exception as exc:  # pragma: no cover
            raise WebToolError(f"web_fetch failed: {exc}") from exc

        return _parse_extract_result(raw, source_url=url, max_chars=max_chars)


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


def _parse_search_results(raw: Any) -> list[WebSearchResultItem]:
    candidates = raw.get("results", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []

    normalized_results: list[WebSearchResultItem] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        score = item.get("score")
        normalized_results.append(
            WebSearchResultItem(
                title=_bound_text(item.get("title"), max_chars=180),
                url=_normalize_url(url),
                snippet=_bound_text(item.get("content") or item.get("snippet"), max_chars=_MAX_SNIPPET_CHARS),
                score=float(score) if isinstance(score, (int, float)) else None,
                published_at=item.get("published_date") or item.get("published_at"),
            )
        )
    return normalized_results


def _parse_extract_result(raw: Any, *, source_url: str, max_chars: int) -> dict[str, Any]:
    candidates = raw.get("results", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []

    result = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    source = result if isinstance(result, dict) else {}

    url = source.get("url") if isinstance(source.get("url"), str) and source.get("url").strip() else source_url
    content = _bound_text(source.get("raw_content") or source.get("content") or source.get("snippet"), max_chars=max_chars)
    title = source.get("title") if isinstance(source.get("title"), str) else None
    published = source.get("published_date") or source.get("published_at")

    return {
        "url": _normalize_url(url),
        "title": _bound_text(title, max_chars=180) if title else None,
        "content_text": content,
        "extracted_at": published if isinstance(published, str) else None,
        "content_truncated": len(content) >= max_chars and bool(content),
    }


class StaticWebSearchClient:
    """Default local client to keep the service deterministic in tests/dev."""

    def search(
        self,
        *,
        query: str,
        max_results: int,
        recency_days: int | None,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> list[dict[str, Any]]:
        _ = recency_days, include_domains, exclude_domains
        now_iso = datetime.now(tz=UTC).isoformat()
        return [
            {
                "title": f"Result for {query}",
                "url": "https://example.com/search",
                "snippet": f"Top result for query: {query}",
                "score": 1.0,
                "published_at": now_iso,
            }
        ][:max_results]

    def extract(self, *, url: str) -> list[dict[str, Any]]:
        now_iso = datetime.now(tz=UTC).isoformat()
        return [
            {
                "url": url,
                "title": "Example fetched page",
                "raw_content": f"Readable content for {url}",
                "published_at": now_iso,
            }
        ]
