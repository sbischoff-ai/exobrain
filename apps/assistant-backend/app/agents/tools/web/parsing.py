from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.agents.tools.web.constants import _MAX_FETCH_CHARS, _MAX_RESULTS_LIMIT, _MAX_SNIPPET_CHARS


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), fragment="")
    return urlunsplit(normalized)


def bound_text(value: str | None, *, max_chars: int) -> str:
    if not value:
        return ""
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 1].rstrip()}…"


def parse_max_results(max_results: int) -> int:
    if max_results < 1:
        return 1
    return min(max_results, _MAX_RESULTS_LIMIT)


def parse_max_chars(max_chars: int) -> int:
    if max_chars < 256:
        return 256
    return min(max_chars, _MAX_FETCH_CHARS)


def parse_search_results(raw: Any) -> list[dict[str, Any]]:
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
                "title": bound_text(item.get("title"), max_chars=180),
                "url": normalize_url(url),
                "snippet": bound_text(item.get("content") or item.get("snippet"), max_chars=_MAX_SNIPPET_CHARS),
                "score": item.get("score"),
                "published_at": item.get("published_date") or item.get("published_at"),
            }
        )
    return normalized_results


def parse_extract_result(raw: Any, *, max_chars: int, source_url: str) -> dict[str, Any]:
    candidates = raw.get("results", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    first = candidates[0] if candidates and isinstance(candidates[0], dict) else {}

    raw_content = str(first.get("raw_content") or first.get("content") or "")
    compact_raw = " ".join(raw_content.split())
    content_text = bound_text(raw_content, max_chars=max_chars)

    return {
        "url": normalize_url(str(first.get("url") or source_url)),
        "title": bound_text(first.get("title"), max_chars=240) or None,
        "content_text": content_text,
        "extracted_at": datetime.now(tz=UTC).isoformat(),
        "content_truncated": len(compact_raw) > len(content_text),
    }
