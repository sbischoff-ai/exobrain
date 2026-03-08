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
