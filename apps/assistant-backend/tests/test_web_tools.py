from __future__ import annotations

from app.agents.tools.web import TavilyWebTools, WebSearchStreamMapper, build_web_tools, parse_extract_result, parse_search_results


class _StubWebTools(TavilyWebTools):
    def __init__(self) -> None:
        super().__init__(tavily_api_key="test-key")

    def _search_invoke(self, payload, *, max_results):  # noqa: ANN001, ARG002
        return {
            "results": [
                {
                    "title": "Mock",
                    "url": "https://Example.com/path#frag",
                    "content": "hello",
                }
            ]
        }

    def _extract_invoke(self, payload):  # noqa: ANN001, ARG002
        return {
            "results": [
                {
                    "url": "https://example.com/offline-mock",
                    "title": "Offline mock fetch",
                    "raw_content": "Offline mock content body for web_fetch in agent environments.",
                }
            ]
        }


def testparse_search_results_normalizes_url_and_bounds_snippet() -> None:
    results = parse_search_results(
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


def testparse_extract_result_returns_plain_payload() -> None:
    parsed = parse_extract_result(
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
    tools = build_web_tools(web_tools=_StubWebTools())

    assert [tool.name for tool in tools] == ["web_search", "web_fetch"]


def test_build_web_tools_uses_provider_for_search_and_fetch() -> None:
    tools = build_web_tools(web_tools=_StubWebTools())

    results = tools[0].invoke({"query": "test"})
    fetched = tools[1].invoke({"url": "https://unused.local"})

    assert results == [
        {
            "title": "Mock",
            "url": "https://example.com/path",
            "snippet": "hello",
            "score": None,
            "published_at": None,
        }
    ]
    assert fetched["url"] == "https://example.com/offline-mock"
    assert "Offline mock" in (fetched["title"] or "")


def test_web_search_stream_mapper_counts_list_results() -> None:
    mapper = WebSearchStreamMapper()

    event = mapper.map_tool_response(args={"query": "x"}, result=[{"url": "https://example.com"}])

    assert event["type"] == "tool_response"
    assert event["data"]["message"] == "Found 1 candidate source"


def test_web_search_stream_mapper_counts_json_string_results() -> None:
    mapper = WebSearchStreamMapper()

    event = mapper.map_tool_response(
        args={"query": "x"},
        result='{"results": [{"url": "https://a"}, {"url": "https://b"}]}'
    )

    assert event["data"]["message"] == "Found 2 candidate sources"
