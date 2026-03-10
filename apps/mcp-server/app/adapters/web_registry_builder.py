from __future__ import annotations

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, input_parser, schema_metadata
from app.contracts import WebFetchToolInput, WebSearchToolInput


def build_web_tool_registrations(adapters: ToolAdapterRegistry) -> list[ToolRegistration]:
    return [
        ToolRegistration(
            name="web_search",
            category="web",
            metadata_provider=schema_metadata(
                "web_search",
                "Search the web for candidate sources and return normalized title/url/snippet metadata.",
                WebSearchToolInput,
            ),
            invocation_parser=input_parser(WebSearchToolInput),
            handler=adapters.invoke_web_search,
            error_code="WEB_SEARCH_FAILED",
            feature_flag="enable_web_tools",
            dependencies=("web_search_provider",),
        ),
        ToolRegistration(
            name="web_fetch",
            category="web",
            metadata_provider=schema_metadata(
                "web_fetch",
                "Fetch readable plaintext from a URL and return normalized content metadata.",
                WebFetchToolInput,
            ),
            invocation_parser=input_parser(WebFetchToolInput),
            handler=adapters.invoke_web_fetch,
            error_code="WEB_FETCH_FAILED",
            feature_flag="enable_web_tools",
            dependencies=("web_search_provider",),
        ),
    ]
