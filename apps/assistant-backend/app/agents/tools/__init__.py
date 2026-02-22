from app.agents.tools.contracts import StreamEventMapper
from app.agents.tools.web import (
    TavilyWebTools,
    WebFetchStreamMapper,
    WebSearchStreamMapper,
    WebTools,
    build_web_tools,
)


def default_stream_event_mappers() -> dict[str, StreamEventMapper]:
    mappers: list[StreamEventMapper] = [WebSearchStreamMapper(), WebFetchStreamMapper()]
    return {mapper.tool_name: mapper for mapper in mappers}


__all__ = [
    "WebTools",
    "TavilyWebTools",
    "build_web_tools",
    "StreamEventMapper",
    "default_stream_event_mappers",
]
