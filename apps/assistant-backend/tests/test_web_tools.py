from __future__ import annotations

from app.agents.tools.web import _parse_extract_result, _parse_search_results, build_web_tools


def test_parse_search_results_normalizes_url_and_bounds_snippet() -> None:
    results = _parse_search_results(
        {
            "results": [
                {
                    "title": "Example",
                    "url": "HTTPS://Example.COM/path#frag",
                    "content": "word " * 200,
                    "score": 0.9,
                    "published_date": "2026-01-01",
                }
            ]
        }
    )

    assert results == [
        {
            "title": "Example",
            "url": "https://example.com/path",
            "snippet": results[0]["snippet"],
            "score": 0.9,
            "published_at": "2026-01-01",
        }
    ]
    assert len(results[0]["snippet"]) <= 320


def test_parse_extract_result_returns_plain_payload() -> None:
    parsed = _parse_extract_result(
        {
            "results": [
                {
                    "url": "https://example.com/article",
                    "title": "A title",
                    "raw_content": "Paragraph one\n\nParagraph two",
                }
            ]
        },
        max_chars=500,
        source_url="https://fallback.local",
    )

    assert parsed["url"] == "https://example.com/article"
    assert parsed["title"] == "A title"
    assert parsed["content_text"] == "Paragraph one Paragraph two"
    assert parsed["content_truncated"] is False


def test_build_web_tools_exposes_search_and_fetch_contracts() -> None:
    tools = build_web_tools(tavily_api_key="test-key")

    assert [tool.name for tool in tools] == ["web_search", "web_fetch"]
