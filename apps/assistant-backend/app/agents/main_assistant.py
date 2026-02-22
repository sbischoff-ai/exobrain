from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agents.base import ChatAgent
from app.agents.tools.contracts import StreamEventMapper
from app.services.chat_stream import ChatStreamEvent

logger = logging.getLogger(__name__)


class MainAssistantAgent(ChatAgent):
    """LangGraph-based assistant agent with Postgres-backed conversation memory."""

    def __init__(
        self,
        *,
        compiled_agent: Any,
        tool_event_mappers: dict[str, StreamEventMapper] | None = None,
        checkpointer_cm: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None,
    ) -> None:
        self._compiled_agent = compiled_agent
        self._tool_event_mappers = tool_event_mappers or {}
        self._checkpointer_cm = checkpointer_cm

    @classmethod
    async def create(
        cls,
        *,
        model: BaseChatModel,
        system_prompt: str,
        assistant_db_dsn: str,
        tools: list[BaseTool] | None = None,
        tool_event_mappers: dict[str, StreamEventMapper] | None = None,
    ) -> MainAssistantAgent:
        checkpointer_cm = AsyncPostgresSaver.from_conn_string(assistant_db_dsn)
        checkpointer = await checkpointer_cm.__aenter__()
        await checkpointer.setup()

        compiled_agent = create_agent(
            model=model,
            tools=tools or [],
            system_prompt=system_prompt,
            checkpointer=checkpointer,
        )
        return cls(
            compiled_agent=compiled_agent,
            tool_event_mappers=tool_event_mappers,
            checkpointer_cm=checkpointer_cm,
        )

    async def astream(self, message: str, conversation_id: str) -> AsyncIterator[ChatStreamEvent]:
        logger.debug(
            "streaming response from main assistant",
            extra={"message_length": len(message), "conversation_id": conversation_id},
        )
        pending_mappers: dict[str, tuple[StreamEventMapper, dict[str, Any]]] = {}
        async for mode, payload in self._compiled_agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            stream_mode=["messages", "updates"],
            config={"configurable": {"thread_id": conversation_id}},
        ):
            if mode == "messages":
                chunk, metadata = payload
                if metadata.get("langgraph_node") != "model":
                    continue
                for text in self._extract_message_chunks(chunk):
                    yield {"type": "message_chunk", "data": {"text": text}}
                continue

            if mode != "updates":
                continue

            for event in self._extract_update_events(payload, pending_mappers):
                yield event

    def _extract_message_chunks(self, chunk: Any) -> list[str]:
        chunk_content = getattr(chunk, "content", chunk)
        if isinstance(chunk_content, str):
            return [chunk_content] if chunk_content else []

        if not isinstance(chunk_content, list):
            return []

        parsed: list[str] = []
        for item in chunk_content:
            item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
            if item_type != "text":
                continue
            text = item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
            if text:
                parsed.append(text)
        return parsed

    def _extract_update_events(
        self,
        update_payload: Any,
        pending_mappers: dict[str, tuple[StreamEventMapper, dict[str, Any]]],
    ) -> list[ChatStreamEvent]:
        events: list[ChatStreamEvent] = []
        if not isinstance(update_payload, dict):
            return events

        for node_update in update_payload.values():
            if not isinstance(node_update, dict):
                continue
            messages = node_update.get("messages", [])
            for message in messages:
                tool_calls = self._message_tool_calls(message)
                for tool_call in tool_calls:
                    tool_name = str(tool_call.get("name") or "")
                    mapper = self._tool_event_mappers.get(tool_name)
                    if mapper is None:
                        continue
                    tool_id = str(tool_call.get("id") or "")
                    args = tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {}
                    if tool_id:
                        pending_mappers[tool_id] = (mapper, args)
                    events.append(mapper.map_tool_call(args=args))

                if getattr(message, "type", None) != "tool":
                    continue

                mapper_tuple = pending_mappers.pop(str(getattr(message, "tool_call_id", "")), None)
                if mapper_tuple is None:
                    continue
                mapper, args = mapper_tuple

                status = str(getattr(message, "status", "") or "")
                artifact = getattr(message, "artifact", None)
                if status == "error":
                    events.append(mapper.map_tool_error(args=args, error=str(getattr(message, "content", "error"))))
                    continue

                events.append(mapper.map_tool_response(args=args, result=artifact if artifact is not None else getattr(message, "content", None)))

        return events

    def _message_tool_calls(self, message: Any) -> list[dict[str, Any]]:
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            return [call for call in tool_calls if isinstance(call, dict)]

        content = getattr(message, "content", None)
        if not isinstance(content, list):
            return []

        parsed_calls: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_call":
                continue
            parsed_calls.append(item)
        return parsed_calls

    async def aclose(self) -> None:
        if self._checkpointer_cm is None:
            return
        await self._checkpointer_cm.__aexit__(None, None, None)
        self._checkpointer_cm = None
