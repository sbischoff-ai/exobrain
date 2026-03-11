from __future__ import annotations

from app.adapters.tool_adapters import ToolAdapterRegistry
from app.adapters.tool_registry import ToolRegistration, input_parser, schema_metadata
from app.contracts import ResolveEntitiesToolInput


def build_knowledge_tool_registrations(adapters: ToolAdapterRegistry) -> list[ToolRegistration]:
    return [
        ToolRegistration(
            name="resolve_entities",
            category="knowledge",
            metadata_provider=schema_metadata(
                "resolve_entities",
                "Use this to map user-relevant named entities from the prompt to canonical knowledge-graph nodes before calling get_entity_context. "
                "Send only entities that should exist in this user-scoped graph, and use expected_existence to hint new vs existing when known. "
                "Current local/test behavior is placeholder-only: entity_id is synthetic, status is unresolved, confidence is low, and newly_created is inferred from expected_existence rather than real graph writes.",
                ResolveEntitiesToolInput,
            ),
            invocation_parser=input_parser(ResolveEntitiesToolInput),
            handler=adapters.invoke_resolve_entities,
            feature_flag="enable_knowledge_tools",
            dependencies=("knowledge_interface_client",),
        )
    ]
