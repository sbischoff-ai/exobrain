from __future__ import annotations

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, input_parser, schema_metadata
from app.contracts import AddToolInput, EchoToolInput


def build_utility_tool_registrations(adapters: ToolAdapterRegistry) -> list[ToolRegistration]:
    return [
        ToolRegistration(
            name="echo",
            category="utility",
            metadata_provider=schema_metadata(
                "echo",
                "Use this for lightweight diagnostics to confirm tool invocation wiring or argument shaping. "
                "It returns exactly the provided text (no transformation, enrichment, or side effects), so treat output as a transport check rather than new information.",
                EchoToolInput,
            ),
            invocation_parser=input_parser(EchoToolInput),
            handler=lambda args, context: adapters.invoke_echo(args, context),
            feature_flag="enable_utility_tools",
        ),
        ToolRegistration(
            name="add",
            category="utility",
            metadata_provider=schema_metadata(
                "add",
                "Use this for deterministic arithmetic checks inside a tool-using flow. "
                "Inputs are integers only and output is a single sum field; no units, rounding, or persistence are applied.",
                AddToolInput,
            ),
            invocation_parser=input_parser(AddToolInput),
            handler=lambda args, context: adapters.invoke_add(args, context),
            feature_flag="enable_utility_tools",
        ),
    ]
