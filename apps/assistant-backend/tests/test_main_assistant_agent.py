from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.agents.main_assistant import MainAssistantAgent
from app.agents.tools.web import WebSearchStreamMapper


class _Chunk:
    def __init__(self, content):
        self.content = content


class _ToolMessage:
    type = "tool"

    def __init__(self, *, tool_call_id: str, content: str, artifact: object = None, status: str = "success") -> None:
        self.tool_call_id = tool_call_id
        self.content = content
        self.artifact = artifact
        self.status = status


class FakeCompiledAgent:
    async def astream(self, *_args, **_kwargs) -> AsyncIterator[tuple[str, object]]:
        yield "updates", {
            "model": {
                "messages": [
                    type(
                        "ModelMsg",
                        (),
                        {
                            "tool_calls": [
                                {
                                    "id": "tc-1",
                                    "name": "web_search",
                                    "args": {"query": "news"},
                                }
                            ]
                        },
                    )()
                ]
            }
        }
        yield "messages", (_Chunk([{"type": "text", "text": "hello"}]), {"langgraph_node": "model"})
        yield "updates", {
            "tools": {
                "messages": [
                    _ToolMessage(
                        tool_call_id="tc-1",
                        content="ok",
                        artifact=[{"title": "x"}],
                    )
                ]
            }
        }
        yield "messages", (_Chunk([{"type": "text", "text": " world"}]), {"langgraph_node": "model"})


@pytest.mark.asyncio
async def test_astream_yields_message_and_tool_events() -> None:
    agent = MainAssistantAgent(
        compiled_agent=FakeCompiledAgent(),
        tool_event_mappers={"web_search": WebSearchStreamMapper()},
    )

    events = [chunk async for chunk in agent.astream(message="hi", conversation_id="conv-1")]

    assert events[0] == {
        "type": "tool_call",
        "data": {
            "tool_call_id": "tc-1",
            "title": "Web search",
            "description": "Searching the web for news",
        },
    }
    assert events[1] == {"type": "message_chunk", "data": {"text": "hello"}}
    assert events[2] == {
        "type": "tool_response",
        "data": {"tool_call_id": "tc-1", "message": "Found 1 candidate source"},
    }
    assert events[3] == {"type": "message_chunk", "data": {"text": " world"}}


class FakeCompiledAgentWithStringResult:
    async def astream(self, *_args, **_kwargs) -> AsyncIterator[tuple[str, object]]:
        yield "updates", {
            "model": {
                "messages": [
                    type(
                        "ModelMsg",
                        (),
                        {
                            "tool_calls": [
                                {
                                    "id": "tc-1",
                                    "name": "web_search",
                                    "args": {"query": "news"},
                                }
                            ]
                        },
                    )()
                ]
            }
        }
        yield "updates", {
            "tools": {
                "messages": [
                    _ToolMessage(
                        tool_call_id="tc-1",
                        content='{"results": [{"url": "https://a"}, {"url": "https://b"}]}'
                    )
                ]
            }
        }


@pytest.mark.asyncio
async def test_astream_tool_response_counts_sources_from_string_payload() -> None:
    agent = MainAssistantAgent(
        compiled_agent=FakeCompiledAgentWithStringResult(),
        tool_event_mappers={"web_search": WebSearchStreamMapper()},
    )

    events = [chunk async for chunk in agent.astream(message="hi", conversation_id="conv-1")]

    assert events[1] == {
        "type": "tool_response",
        "data": {"tool_call_id": "tc-1", "message": "Found 2 candidate sources"},
    }

def test_extract_update_events_parses_content_tool_calls_and_tool_errors() -> None:
    mapper = WebSearchStreamMapper()
    agent = MainAssistantAgent(compiled_agent=FakeCompiledAgent(), tool_event_mappers={"web_search": mapper})
    pending: dict[str, tuple[WebSearchStreamMapper, dict[str, object]]] = {}

    tool_call_message = type(
        "ModelMsg",
        (),
        {
            "content": [
                {
                    "type": "tool_call",
                    "id": "tc-42",
                    "name": "web_search",
                    "args": {"query": "model contract"},
                }
            ]
        },
    )()
    tool_error_message = _ToolMessage(tool_call_id="tc-42", content="upstream timeout", status="error")

    events = agent._extract_update_events(
        {"model": {"messages": [tool_call_message]}, "tools": {"messages": [tool_error_message]}},
        pending,
    )

    assert events == [
        {
            "type": "tool_call",
            "data": {
                "tool_call_id": "tc-42",
                "title": "Web search",
                "description": "Searching the web for model contract",
            },
        },
        {
            "type": "error",
            "data": {
                "tool_call_id": "tc-42",
                "message": "Couldn't complete web search for model contract: upstream timeout",
            },
        },
    ]


def test_extract_update_events_ignores_tool_results_without_matching_call() -> None:
    mapper = WebSearchStreamMapper()
    agent = MainAssistantAgent(compiled_agent=FakeCompiledAgent(), tool_event_mappers={"web_search": mapper})

    events = agent._extract_update_events(
        {"tools": {"messages": [_ToolMessage(tool_call_id="missing", content="ok")]}},
        pending_mappers={},
    )

    assert events == []


class FakeCompiledAgentWithToolError:
    async def astream(self, *_args, **_kwargs) -> AsyncIterator[tuple[str, object]]:
        yield "updates", {
            "model": {
                "messages": [
                    type(
                        "ModelMsg",
                        (),
                        {
                            "tool_calls": [
                                {
                                    "id": "tc-err-1",
                                    "name": "web_search",
                                    "args": {"query": "failing query"},
                                }
                            ]
                        },
                    )()
                ]
            }
        }
        yield "updates", {
            "tools": {
                "messages": [
                    _ToolMessage(tool_call_id="tc-err-1", content="upstream 401", status="error")
                ]
            }
        }


@pytest.mark.asyncio
async def test_astream_emits_error_event_for_failed_tool_with_tool_call_id() -> None:
    agent = MainAssistantAgent(
        compiled_agent=FakeCompiledAgentWithToolError(),
        tool_event_mappers={"web_search": WebSearchStreamMapper()},
    )

    events = [chunk async for chunk in agent.astream(message="hi", conversation_id="conv-1")]

    assert events == [
        {
            "type": "tool_call",
            "data": {
                "tool_call_id": "tc-err-1",
                "title": "Web search",
                "description": "Searching the web for failing query",
            },
        },
        {
            "type": "error",
            "data": {
                "tool_call_id": "tc-err-1",
                "message": "Couldn't complete web search for failing query: upstream 401",
            },
        },
    ]
