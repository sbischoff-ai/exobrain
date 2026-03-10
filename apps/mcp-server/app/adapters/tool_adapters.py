from __future__ import annotations

from app.adapters.web_tools import WebFetchAdapter, WebSearchAdapter
from app.contracts import (
    AddToolInput,
    AddToolOutput,
    EchoToolInput,
    EchoToolOutput,
    WebFetchToolInput,
    WebFetchToolOutput,
    WebSearchToolInput,
    WebSearchToolOutput,
)


class ToolAdapterRegistry:
    def __init__(self, web_search_adapter: WebSearchAdapter, web_fetch_adapter: WebFetchAdapter):
        self._web_search_adapter = web_search_adapter
        self._web_fetch_adapter = web_fetch_adapter

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

    def invoke_web_fetch(self, args: WebFetchToolInput) -> WebFetchToolOutput:
        return WebFetchToolOutput.model_validate(
            self._web_fetch_adapter.web_fetch(
                url=args.url,
                max_chars=args.max_chars,
            )
        )
