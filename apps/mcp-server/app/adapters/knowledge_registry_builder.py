from __future__ import annotations

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration


def build_knowledge_tool_registrations(adapters: ToolAdapterRegistry) -> list[ToolRegistration]:
    del adapters
    return []
