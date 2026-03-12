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
                "Use this when you need candidate external sources before answering. "
                "Set max_results (1-10) to control recall; snippets are normalized summaries capped to ~320 chars and "
                "the provider may still return fewer results than requested. Interpret each result as discovery metadata "
                "(title/url/snippet/optional score+published_at), not verified facts; follow up with web_fetch on promising URLs.",
                WebSearchToolInput,
            ),
            invocation_parser=input_parser(WebSearchToolInput),
            handler=lambda args, context: adapters.invoke_web_search(args, context),
            error_code="WEB_SEARCH_FAILED",
            feature_flag="enable_web_tools",
            dependencies=("web_search_provider",),
        ),
        ToolRegistration(
            name="web_fetch",
            category="web",
            metadata_provider=schema_metadata(
                "web_fetch",
                "Use this when you already have a URL and need readable page text for grounding or quoting. "
                "max_chars is required output bounding (100-20000); returned content_text is normalized plaintext and "
                "may omit markup or non-readable sections. content_truncated=true means text hit max_chars and you should "
                "raise max_chars or fetch another source for full context.",
                WebFetchToolInput,
            ),
            invocation_parser=input_parser(WebFetchToolInput),
            handler=lambda args, context: adapters.invoke_web_fetch(args, context),
            error_code="WEB_FETCH_FAILED",
            feature_flag="enable_web_tools",
            dependencies=("web_search_provider",),
        ),
    ]
