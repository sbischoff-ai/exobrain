from app.agents.tools.contracts import StreamEventMapper
from app.agents.tools.mcp_tooling import build_mcp_tools
from app.agents.tools.web import WebFetchStreamMapper, WebSearchStreamMapper


def default_stream_event_mappers() -> dict[str, StreamEventMapper]:
    mappers: list[StreamEventMapper] = [WebSearchStreamMapper(), WebFetchStreamMapper()]
    return {mapper.tool_name: mapper for mapper in mappers}


__all__ = [
    "StreamEventMapper",
    "build_mcp_tools",
    "default_stream_event_mappers",
]
