from __future__ import annotations

from app.adapters.web_tools import WebSearchAdapter
from app.contracts import (
    AddToolInput,
    AddToolOutput,
    EchoToolInput,
    EchoToolOutput,
    ToolMetadata,
    WebSearchToolInput,
    WebSearchToolOutput,
)


class ToolAdapterRegistry:
    def __init__(self, web_search_adapter: WebSearchAdapter):
        self._web_search_adapter = web_search_adapter

    def list_tools(self) -> list[ToolMetadata]:
        return [
            ToolMetadata(
                name="echo",
                description="Return the input text.",
                input_schema=EchoToolInput.model_json_schema(),
            ),
            ToolMetadata(
                name="add",
                description="Add two integers.",
                input_schema=AddToolInput.model_json_schema(),
            ),
            ToolMetadata(
                name="web_search",
                description=(
                    "Search the web for candidate sources and return normalized title/url/snippet metadata."
                ),
                input_schema=WebSearchToolInput.model_json_schema(),
            ),
        ]

    def invoke_echo(self, args: EchoToolInput) -> EchoToolOutput:
        return EchoToolOutput(text=args.text)

    def invoke_add(self, args: AddToolInput) -> AddToolOutput:
        return AddToolOutput(sum=args.a + args.b)

    def invoke_web_search(self, args: WebSearchToolInput) -> WebSearchToolOutput:
        return WebSearchToolOutput(
            results=self._web_search_adapter.web_search(
                query=args.query,
                max_results=args.max_results,
                recency_days=args.recency_days,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
            )
        )
