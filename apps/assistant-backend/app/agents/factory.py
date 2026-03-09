from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI

from app.agents.base import ChatAgent
from app.agents.main_assistant import MainAssistantAgent
from app.agents.model_provider_chat_model import ModelProviderChatModel
from app.agents.tools import build_mcp_tools, default_stream_event_mappers
from app.core.settings import Settings
from app.services.contracts import MCPClientProtocol

logger = logging.getLogger(__name__)

_MOCK_MESSAGE_DELIMITER = "\n\n--- message ---\n\n"
_WEB_TOOL_INSTRUCTIONS = """

Web research tool policy:
- Use web_search when the user asks for sources, current events, niche facts, or claims likely to be wrong without citation.
- Use web_fetch only on URLs returned by web_search or URLs explicitly provided by the user.
- Prefer fetching only the top 1-3 sources to control latency and context size.
- Never fabricate quotes. Only quote text that appears in web_fetch output.
"""

_FORMATTING_INSTRUCTIONS = """

Response formatting policy:
- Use markdown that renders correctly in Streamdown.
- Inline math must use KaTeX delimiters: $...$.
- Display math must use KaTeX delimiters: $$...$$.
- Never place $$...$$ inside a sentence. Display math must be on its own lines with a blank line before and after.
- For multi-step equations, prefer display math over inline math.
- When drawing a diagram, output a fenced Mermaid code block with the `mermaid` language tag.
- Prefer concise Mermaid diagrams when explaining processes, flows, systems, or relationships.
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

    use_openai_compat = (
        settings.main_agent_model_contract_mode == "legacy_openai_compatible"
        or settings.main_agent_use_openai_fallback
    )
    logger.info(
        "building assistant model",
        extra={
            "model_alias": settings.main_agent_model,
            "contract_mode": settings.main_agent_model_contract_mode,
            "openai_fallback": settings.main_agent_use_openai_fallback,
            "using_openai_compat": use_openai_compat,
        },
    )
    if use_openai_compat:
        return ChatOpenAI(
            model=settings.main_agent_model,
            base_url=settings.model_provider_base_url,
            api_key="model-provider",
            streaming=True,
        )

    return ModelProviderChatModel(
        model=settings.main_agent_model,
        base_url=settings.model_provider_base_url,
    )


async def build_main_agent(settings: Settings, *, mcp_client: MCPClientProtocol) -> ChatAgent:
    """Create the main assistant agent with real or fake model backends."""

    model = _build_agent_model(settings)
    tools = None if settings.main_agent_use_mock else await build_mcp_tools(mcp_client=mcp_client)
    system_prompt = "\n".join(
        [
            settings.main_agent_system_prompt.strip(),
            _FORMATTING_INSTRUCTIONS.strip(),
            _WEB_TOOL_INSTRUCTIONS.strip(),
        ]
    )
    return await MainAssistantAgent.create(
        model=model,
        system_prompt=system_prompt,
        assistant_db_dsn=settings.assistant_db_dsn,
        tools=tools,
        tool_event_mappers=default_stream_event_mappers(),
    )
