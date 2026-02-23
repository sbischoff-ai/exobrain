from __future__ import annotations

import json
from typing import Any

from app.agents.tools.contracts import StreamEventMapper
from app.services.chat_stream import ChatStreamEvent


class WebSearchStreamMapper(StreamEventMapper):
    tool_name = "web_search"

    def map_tool_call(self, *, tool_call_id: str, args: dict[str, Any]) -> ChatStreamEvent:
        query = str(args.get("query") or "the web")
        return {
            "type": "tool_call",
            "data": {
                "tool_call_id": tool_call_id,
                "title": "Web search",
                "description": f"Searching the web for {query}",
            },
        }

    def map_tool_response(self, *, tool_call_id: str, args: dict[str, Any], result: Any) -> ChatStreamEvent:
        count = self._count_sources(result)
        return {
            "type": "tool_response",
            "data": {
                "tool_call_id": tool_call_id,
                "message": f"Found {count} candidate source{'s' if count != 1 else ''}",
            },
        }

    def _count_sources(self, result: Any) -> int:
        if isinstance(result, list):
            return len(result)

        if isinstance(result, dict):
            nested = result.get("results")
            return len(nested) if isinstance(nested, list) else 0

        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except json.JSONDecodeError:
                return 0
            return self._count_sources(parsed)

        return 0

    def map_tool_error(self, *, tool_call_id: str, args: dict[str, Any], error: str) -> ChatStreamEvent:
        query = str(args.get("query") or "requested query")
        return {
            "type": "error",
            "data": {
                "tool_call_id": tool_call_id,
                "message": f"Couldn't complete web search for {query}: {error}",
            },
        }


class WebFetchStreamMapper(StreamEventMapper):
    tool_name = "web_fetch"

    def map_tool_call(self, *, tool_call_id: str, args: dict[str, Any]) -> ChatStreamEvent:
        url = str(args.get("url") or "web content")
        return {
            "type": "tool_call",
            "data": {
                "tool_call_id": tool_call_id,
                "title": "Web fetch",
                "description": f"Looking at {url}",
            },
        }

    def map_tool_response(self, *, tool_call_id: str, args: dict[str, Any], result: Any) -> ChatStreamEvent:
        title = result.get("title") if isinstance(result, dict) else None
        descriptor = str(title or args.get("url") or "web content")
        return {
            "type": "tool_response",
            "data": {
                "tool_call_id": tool_call_id,
                "message": f"Summarized {descriptor}",
            },
        }

    def map_tool_error(self, *, tool_call_id: str, args: dict[str, Any], error: str) -> ChatStreamEvent:
        url = str(args.get("url") or "website")
        return {
            "type": "error",
            "data": {
                "tool_call_id": tool_call_id,
                "message": f"Couldn't reach {url}: {error}",
            },
        }
