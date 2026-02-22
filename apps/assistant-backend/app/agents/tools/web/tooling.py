from __future__ import annotations

from langchain_core.tools import StructuredTool

from app.agents.tools.web.constants import _DEFAULT_FETCH_CHARS, _DEFAULT_MAX_RESULTS
from app.agents.tools.web.provider import WebTools


def build_web_tools(*, web_tools: WebTools) -> list[StructuredTool]:
    """Build wrapped web tools with stable contracts."""

    def _web_search_tool(
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        recency_days: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, object]]:
        return web_tools.web_search(
            query=query,
            max_results=max_results,
            recency_days=recency_days,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )

    def _web_fetch_tool(url: str, max_chars: int = _DEFAULT_FETCH_CHARS) -> dict[str, object]:
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
