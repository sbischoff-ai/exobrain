from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI

from app.agents.base import ChatAgent
from app.agents.main_assistant import MainAssistantAgent
from app.agents.tools import build_web_tools
from app.core.settings import Settings

logger = logging.getLogger(__name__)

_MOCK_MESSAGE_DELIMITER = "\n\n--- message ---\n\n"
_WEB_TOOL_INSTRUCTIONS = """

Web research tool policy:
- Use web_search when the user asks for sources, current events, niche facts, or claims likely to be wrong without citation.
- Use web_fetch only on URLs returned by web_search or URLs explicitly provided by the user.
- Prefer fetching only the top 1-3 sources to control latency and context size.
- Never fabricate quotes. Only quote text that appears in web_fetch output.
"""


def _load_mock_messages(messages_file: str) -> list[str]:
    path = Path(messages_file)
    raw_content = path.read_text(encoding="utf-8")
    parsed_messages = [chunk.strip() for chunk in raw_content.split(_MOCK_MESSAGE_DELIMITER)]
    messages = [message for message in parsed_messages if message]
    if not messages:
        raise ValueError(
            f"No mock messages found in {path}. Use delimiter {_MOCK_MESSAGE_DELIMITER!r} between messages."
        )
    return messages


def _build_agent_model(settings: Settings) -> BaseChatModel:
    if settings.main_agent_use_mock:
        fake_responses = _load_mock_messages(messages_file=settings.main_agent_mock_messages_file)
        logger.info("using FakeListChatModel assistant agent", extra={"responses_count": len(fake_responses)})
        return FakeListChatModel(responses=fake_responses)

    logger.info("using OpenAI assistant agent", extra={"model": settings.main_agent_model})
    return ChatOpenAI(
        model=settings.main_agent_model,
        temperature=settings.main_agent_temperature,
        streaming=True,
    )


async def build_main_agent(settings: Settings) -> ChatAgent:
    """Create the main assistant agent with real or fake model backends."""

    model = _build_agent_model(settings)
    system_prompt = f"{settings.main_agent_system_prompt.strip()}\n{_WEB_TOOL_INSTRUCTIONS.strip()}"
    return await MainAssistantAgent.create(
        model=model,
        system_prompt=system_prompt,
        assistant_db_dsn=settings.assistant_db_dsn,
        tools=build_web_tools(
            tavily_api_key=settings.tavily_api_key,
            use_mock=settings.web_tools_use_mock,
            mock_data_file=settings.web_tools_mock_data_file,
        ),
    )
