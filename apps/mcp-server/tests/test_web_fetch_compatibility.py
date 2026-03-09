from typing import Any

import pytest

from app.adapters.web_tools import WebFetchAdapter, WebToolError


class FakeWebFetchClient:
    def __init__(self, raw: Any):
        self._raw = raw

    def search(  # pragma: no cover - protocol compatibility only
        self,
        *,
        query: str,
        max_results: int,
        recency_days: int | None,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> Any:
        _ = query, max_results, recency_days, include_domains, exclude_domains
        return []

    def extract(self, *, url: str) -> Any:
        _ = url
        return self._raw


class FailingWebFetchClient(FakeWebFetchClient):
    def extract(self, *, url: str) -> Any:
        _ = url
        raise RuntimeError("boom")


def test_web_fetch_adapter_normalizes_extract_payload() -> None:
    adapter = WebFetchAdapter(
        client=FakeWebFetchClient(
            {
                "results": [
                    {
                        "url": "HTTPS://Example.COM/article#frag",
                        "title": "  Example   article  ",
                        "raw_content": "Line 1\n\nLine 2",
                        "published_at": "2025-01-01T00:00:00Z",
                    }
                ]
            }
        )
    )

    parsed = adapter.web_fetch(url="https://fallback.local", max_chars=120)

    assert parsed == {
        "url": "https://example.com/article",
        "title": "Example article",
        "content_text": "Line 1 Line 2",
        "extracted_at": "2025-01-01T00:00:00Z",
        "content_truncated": False,
    }


def test_web_fetch_adapter_wraps_provider_failures() -> None:
    adapter = WebFetchAdapter(client=FailingWebFetchClient(raw=[]))

    with pytest.raises(WebToolError, match="web_fetch failed: boom"):
        adapter.web_fetch(url="https://example.com", max_chars=500)
