from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.agents.main_assistant import MainAssistantAgent


class _Chunk:
    def __init__(self, content):
        self.content = content


class FakeCompiledAgent:
    async def astream(self, *_args, **_kwargs) -> AsyncIterator[tuple[_Chunk, dict[str, str]]]:
        yield _Chunk([{"type": "tool_call", "name": "web_search"}]), {"langgraph_node": "model"}
        yield _Chunk([{"type": "text", "text": "hello"}]), {"langgraph_node": "model"}
        yield _Chunk("ignored"), {"langgraph_node": "tools"}
        yield _Chunk([{"type": "text", "text": " world"}]), {"langgraph_node": "model"}


@pytest.mark.asyncio
async def test_astream_only_yields_model_text_content() -> None:
    agent = MainAssistantAgent(compiled_agent=FakeCompiledAgent())

    chunks = [chunk async for chunk in agent.astream(message="hi", conversation_id="conv-1")]

    assert chunks == ["hello", " world"]
