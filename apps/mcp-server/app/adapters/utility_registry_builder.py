from __future__ import annotations

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, input_parser, schema_metadata
from app.contracts import AddToolInput, EchoToolInput


def build_utility_tool_registrations(adapters: ToolAdapterRegistry) -> list[ToolRegistration]:
    return [
        ToolRegistration(
            name="echo",
            category="utility",
            metadata_provider=schema_metadata("echo", "Return the input text.", EchoToolInput),
            invocation_parser=input_parser(EchoToolInput),
            handler=adapters.invoke_echo,
            feature_flag="enable_utility_tools",
        ),
        ToolRegistration(
            name="add",
            category="utility",
            metadata_provider=schema_metadata("add", "Add two integers.", AddToolInput),
            invocation_parser=input_parser(AddToolInput),
            handler=adapters.invoke_add,
            feature_flag="enable_utility_tools",
        ),
    ]
