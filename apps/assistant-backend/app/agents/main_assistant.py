from collections.abc import AsyncIterator
import logging

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.agents.base import ChatAgent

logger = logging.getLogger(__name__)


class MainAssistantAgent(ChatAgent):
    """Default single-agent implementation backed by ChatOpenAI."""

    def __init__(self, model_name: str, temperature: float = 0.0) -> None:
        self._llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            streaming=True,
        )

    async def stream(self, message: str) -> AsyncIterator[str]:
        logger.debug("streaming response from main assistant", extra={"message_length": len(message)})
        async for chunk in self._llm.astream([HumanMessage(content=message)]):
            chunk_content = chunk.content
            if isinstance(chunk_content, str):
                if chunk_content:
                    yield chunk_content
            elif isinstance(chunk_content, list):
                for item in chunk_content:
                    text = getattr(item, "text", "")
                    if text:
                        yield text
