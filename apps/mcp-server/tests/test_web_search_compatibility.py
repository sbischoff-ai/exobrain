from typing import Any

from app.adapters.web_tools import WebSearchAdapter


class FakeWebSearchClient:
    def __init__(self, raw: Any):
        self._raw = raw

    def search(
        self,
        *,
        query: str,
        max_results: int,
        recency_days: int | None,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
    ) -> Any:
        _ = query, max_results, recency_days, include_domains, exclude_domains
        return self._raw


def test_web_search_adapter_matches_existing_normalization_behavior() -> None:
    raw = {
        "results": [
            {
                "title": "  Example   Title  ",
                "url": "HTTPS://Example.COM/path?a=1#fragment",
                "content": "line 1\nline2",
                "score": 0.91,
                "published_date": "2025-01-01",
            },
            {"title": "missing url"},
        ]
    }

    adapter = WebSearchAdapter(client=FakeWebSearchClient(raw))
    parsed = adapter.web_search(
        query="example",
        max_results=5,
        recency_days=None,
        include_domains=None,
        exclude_domains=None,
    )

    assert len(parsed) == 1
    assert parsed[0].model_dump() == {
        "title": "Example Title",
        "url": "https://example.com/path?a=1",
        "snippet": "line 1 line2",
        "score": 0.91,
        "published_at": "2025-01-01",
    }
