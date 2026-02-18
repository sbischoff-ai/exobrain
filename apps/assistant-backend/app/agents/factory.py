import logging

from app.agents.base import ChatAgent
from app.agents.main_assistant import MainAssistantAgent
from app.agents.mock_assistant import MockAssistantAgent
from app.core.settings import Settings

logger = logging.getLogger(__name__)


def build_main_agent(settings: Settings) -> ChatAgent:
    """Create the main assistant agent.

    This factory isolates construction so we can later swap providers,
    wire tool-enabled agents, or build multi-agent setups.
    """

    if settings.main_agent_use_mock:
        logger.info("using mock assistant agent")
        return MockAssistantAgent(messages_file=settings.main_agent_mock_messages_file)

    logger.info("using OpenAI assistant agent", extra={"model": settings.main_agent_model})
    return MainAssistantAgent(
        model_name=settings.main_agent_model,
        temperature=settings.main_agent_temperature,
    )
