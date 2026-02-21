from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI

from app.agents.base import ChatAgent
from app.agents.main_assistant import MainAssistantAgent
from app.agents.tools import TavilyWebTools, build_web_tools
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
_DEFAULT_WEB_TOOLS_MOCK_DATA = {
    "search": {
        "results": [
            {
                "title": "Offline mock result",
                "url": "https://example.com/offline-mock",
                "content": "Offline mock web_search result used for coding-agent environments.",
                "score": 1.0,
                "published_date": "2026-01-01",
            }
        ]
    },
    "extract": {
        "results": [
            {
                "url": "https://example.com/offline-mock",
                "title": "Offline mock fetch",
                "raw_content": "Offline mock content body for web_fetch in agent environments.",
            }
        ]
    },
}


class MockTavilyWebTools(TavilyWebTools):
    """Tavily web tools variant that injects fixture payloads instead of network calls."""

    def __init__(self, *, tavily_api_key: str | None = None, mock_data_file: str | None = None) -> None:
        super().__init__(tavily_api_key=tavily_api_key)
        self._mock_payload = self._load_mock_payload(mock_data_file)

    def _load_mock_payload(self, mock_data_file: str | None) -> dict[str, Any]:
        if not mock_data_file:
            return _DEFAULT_WEB_TOOLS_MOCK_DATA

        payload = json.loads(Path(mock_data_file).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("WEB_TOOLS_MOCK_DATA_FILE must contain a JSON object")
        return payload

    def _search_invoke(self, payload: dict[str, Any], *, max_results: int) -> Any:  # noqa: ARG002
        return self._mock_payload.get("search", {})

    def _extract_invoke(self, payload: dict[str, Any]) -> Any:  # noqa: ARG002
        return self._mock_payload.get("extract", {})


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


def _build_web_tools_dependency(settings: Settings) -> TavilyWebTools:
    if settings.web_tools_use_mock:
        logger.info(
            "using MockTavilyWebTools",
            extra={"mock_data_file": settings.web_tools_mock_data_file},
        )
        return MockTavilyWebTools(
            tavily_api_key=settings.tavily_api_key,
            mock_data_file=settings.web_tools_mock_data_file,
        )

    logger.info("using TavilyWebTools")
    return TavilyWebTools(tavily_api_key=settings.tavily_api_key)


async def build_main_agent(settings: Settings) -> ChatAgent:
    """Create the main assistant agent with real or fake model backends."""

    model = _build_agent_model(settings)
    web_tools_dependency = _build_web_tools_dependency(settings)
    system_prompt = f"{settings.main_agent_system_prompt.strip()}\n{_WEB_TOOL_INSTRUCTIONS.strip()}"
    return await MainAssistantAgent.create(
        model=model,
        system_prompt=system_prompt,
        assistant_db_dsn=settings.assistant_db_dsn,
        tools=build_web_tools(web_tools=web_tools_dependency),
    )
