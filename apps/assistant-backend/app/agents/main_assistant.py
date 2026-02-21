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

logger = logging.getLogger(__name__)


class MainAssistantAgent(ChatAgent):
    """LangGraph-based assistant agent with Postgres-backed conversation memory."""

    def __init__(
        self,
        *,
        compiled_agent: Any,
        checkpointer_cm: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None,
    ) -> None:
        self._compiled_agent = compiled_agent
        self._checkpointer_cm = checkpointer_cm

    @classmethod
    async def create(
        cls,
        *,
        model: BaseChatModel,
        system_prompt: str,
        assistant_db_dsn: str,
        tools: list[BaseTool] | None = None,
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
        return cls(compiled_agent=compiled_agent, checkpointer_cm=checkpointer_cm)

    async def astream(self, message: str, conversation_id: str) -> AsyncIterator[str]:
        logger.debug(
            "streaming response from main assistant",
            extra={"message_length": len(message), "conversation_id": conversation_id},
        )
        async for event in self._compiled_agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            stream_mode="messages",
            config={"configurable": {"thread_id": conversation_id}},
        ):
            metadata = event[1] if len(event) > 1 else {}
            if metadata.get("langgraph_node") != "model":
                continue

            chunk = event[0]
            chunk_content = chunk.content
            if isinstance(chunk_content, str):
                if chunk_content:
                    yield chunk_content
            elif isinstance(chunk_content, list):
                for item in chunk_content:
                    item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
                    if item_type != "text":
                        continue
                    text = item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
                    if text:
                        yield text

    async def aclose(self) -> None:
        if self._checkpointer_cm is None:
            return
        await self._checkpointer_cm.__aexit__(None, None, None)
        self._checkpointer_cm = None
