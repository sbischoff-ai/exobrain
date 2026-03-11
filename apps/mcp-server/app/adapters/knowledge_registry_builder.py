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
                "Resolve input entities against the knowledge graph and create missing entities when intent indicates creation.",
                ResolveEntitiesToolInput,
            ),
            invocation_parser=input_parser(ResolveEntitiesToolInput),
            handler=adapters.invoke_resolve_entities,
            feature_flag="enable_knowledge_tools",
            dependencies=("knowledge_interface_client",),
        )
    ]
