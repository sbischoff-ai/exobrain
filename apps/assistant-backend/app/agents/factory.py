from app.agents.base import ChatAgent
from app.agents.main_assistant import MainAssistantAgent
from app.core.settings import Settings


def build_main_agent(settings: Settings) -> ChatAgent:
    """Create the main assistant agent.

    This factory isolates construction so we can later swap providers,
    wire tool-enabled agents, or build multi-agent setups.
    """

    return MainAssistantAgent(
        model_name=settings.main_agent_model,
        temperature=settings.main_agent_temperature,
    )
