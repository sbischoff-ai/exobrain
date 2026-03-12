from __future__ import annotations

from typing import Any

from app.adapters.entity_context_markdown_formatter import render_entity_context_markdown
from app.adapters.knowledge_interface_client import KnowledgeInterfaceClient
from app.adapters.web_tools import WebFetchAdapter, WebSearchAdapter
from app.contracts import (
    AddToolInput,
    AddToolOutput,
    EchoToolInput,
    EchoToolOutput,
    GetEntityContextRelatedEntityItem,
    GetEntityContextToolInput,
    GetEntityContextToolOutput,
    ResolveEntitiesInputItem,
    ResolveEntitiesOutputItem,
    ResolveEntitiesToolInput,
    ResolveEntitiesToolOutput,
    ResolveEntityExpectedExistence,
    ResolveEntityMatchStatus,
    WebFetchToolInput,
    WebFetchToolOutput,
    WebSearchToolInput,
    WebSearchToolOutput,
)


_KI_DEFAULT_MAX_BLOCK_LEVEL = 3
_KI_MAX_BLOCK_LEVEL_CAP = 32


class ToolAdapterRegistry:
    def __init__(
        self,
        web_search_adapter: WebSearchAdapter,
        web_fetch_adapter: WebFetchAdapter,
        knowledge_interface_client: KnowledgeInterfaceClient | None = None,
        knowledge_interface_user_id: str = "mcp-server",
    ):
        self._web_search_adapter = web_search_adapter
        self._web_fetch_adapter = web_fetch_adapter
        self._knowledge_interface_client = knowledge_interface_client
        self._knowledge_interface_user_id = knowledge_interface_user_id

    def invoke_echo(self, args: EchoToolInput) -> EchoToolOutput:
        return EchoToolOutput(text=args.text)

    def invoke_add(self, args: AddToolInput) -> AddToolOutput:
        return AddToolOutput(sum=args.a + args.b)

    def invoke_web_search(self, args: WebSearchToolInput) -> WebSearchToolOutput:
        return WebSearchToolOutput(
            results=self._web_search_adapter.web_search(
                query=args.query,
                max_results=args.max_results,
                recency_days=args.recency_days,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
            )
        )

    def invoke_web_fetch(self, args: WebFetchToolInput) -> WebFetchToolOutput:
        return WebFetchToolOutput.model_validate(
            self._web_fetch_adapter.web_fetch(
                url=args.url,
                max_chars=args.max_chars,
            )
        )

    def invoke_get_entity_context(self, args: GetEntityContextToolInput) -> GetEntityContextToolOutput:
        if self._knowledge_interface_client is None:
            raise RuntimeError("knowledge_interface_client is required for get_entity_context")

        max_block_level = _clamp_max_block_level(args.depth)
        response = self._knowledge_interface_client.get_entity_context(
            entity_id=args.entity_id,
            user_id=self._knowledge_interface_user_id,
            max_block_level=max_block_level,
        )
        type_name_by_id = _build_entity_type_name_map(
            self._knowledge_interface_client.get_schema()
        )
        related_entities = _map_related_entities(
            top_level_neighbors=response.get("neighbors"),
            blocks=response.get("blocks"),
            type_name_by_id=type_name_by_id,
        )

        return GetEntityContextToolOutput(
            context_markdown=render_entity_context_markdown(
                response=response,
                related_entities=related_entities,
                focus=args.focus,
            ),
            related_entities=related_entities,
        )

    def invoke_resolve_entities(self, args: ResolveEntitiesToolInput) -> ResolveEntitiesToolOutput:
        # TODO: replace this placeholder once Knowledge Interface entity resolution is wired in.
        def _normalize_name(entity: ResolveEntitiesInputItem) -> str:
            return " ".join(entity.name.split())

        def _placeholder_aliases(entity: ResolveEntitiesInputItem, canonical_name: str) -> list[str]:
            if entity.name == canonical_name:
                return []
            return [entity.name]

        def _entity_type(entity: ResolveEntitiesInputItem) -> str:
            if entity.type_hint is None:
                return "unknown"
            normalized_hint = entity.type_hint.strip()
            return normalized_hint or "unknown"

        results = []
        for index, entity in enumerate(args.entities, start=1):
            canonical_name = _normalize_name(entity)
            safe_name = canonical_name.lower().replace(" ", "-")

            results.append(
                ResolveEntitiesOutputItem(
                    entity_id=f"placeholder-entity-{index:03d}-{safe_name}",
                    name=canonical_name,
                    aliases=_placeholder_aliases(entity, canonical_name),
                    entity_type=_entity_type(entity),
                    description=entity.description_hint or "Placeholder resolution result.",
                    status=ResolveEntityMatchStatus.UNRESOLVED,
                    confidence=0.2,
                    # Temporary heuristic: infer creation intent from expected existence until integrated.
                    newly_created=entity.expected_existence == ResolveEntityExpectedExistence.NEW,
                )
            )

        return ResolveEntitiesToolOutput(results=results)


def _clamp_max_block_level(depth: int | None) -> int:
    if depth is None:
        return _KI_DEFAULT_MAX_BLOCK_LEVEL
    return max(0, min(depth, _KI_MAX_BLOCK_LEVEL_CAP))


def _map_related_entities(
    *,
    top_level_neighbors: Any,
    blocks: Any,
    type_name_by_id: dict[str, str],
) -> list[GetEntityContextRelatedEntityItem]:
    related_entities_by_id: dict[str, GetEntityContextRelatedEntityItem] = {}

    for neighbor in _iter_neighbors(top_level_neighbors):
        _upsert_related_entity(
            related_entities_by_id,
            neighbor=neighbor,
            type_name_by_id=type_name_by_id,
        )

    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for neighbor in _iter_neighbors(block.get("neighbors")):
                _upsert_related_entity(
                    related_entities_by_id,
                    neighbor=neighbor,
                    type_name_by_id=type_name_by_id,
                )

    return list(related_entities_by_id.values())


def _iter_neighbors(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [neighbor for neighbor in value if isinstance(neighbor, dict)]


def _upsert_related_entity(
    related_entities_by_id: dict[str, GetEntityContextRelatedEntityItem],
    *,
    neighbor: dict[str, Any],
    type_name_by_id: dict[str, str],
) -> None:
    related = neighbor.get("other_entity") if isinstance(neighbor.get("other_entity"), dict) else {}
    entity_id = _coerce_text(related.get("id"))
    if not entity_id:
        return

    type_id = _coerce_text(related.get("type_id"))
    entity_type = type_name_by_id.get(type_id or "")
    if entity_type is None:
        # Fallback: preserve KI type_id when schema lookup misses or KI schema call omits the id.
        entity_type = type_id or "unknown"

    description = _coerce_text(related.get("description"))
    if description is None:
        # Fallback keeps output non-empty for resolve-compatible shape even when KI omits description.
        description = f"Related entity {(_coerce_text(related.get('name')) or entity_id)}"

    related_entities_by_id.setdefault(
        entity_id,
        GetEntityContextRelatedEntityItem(
            entity_id=entity_id,
            name=_coerce_text(related.get("name")) or entity_id,
            aliases=_coerce_list(related.get("aliases")),
            entity_type=entity_type,
            description=description,
        ),
    )


def _build_entity_type_name_map(raw_schema: Any) -> dict[str, str]:
    if not isinstance(raw_schema, dict):
        return {}

    node_types = raw_schema.get("node_types")
    if not isinstance(node_types, list):
        return {}

    mapping: dict[str, str] = {}
    for node_type in node_types:
        if not isinstance(node_type, dict):
            continue
        schema_type = node_type.get("type")
        if not isinstance(schema_type, dict):
            continue
        type_id = _coerce_text(schema_type.get("id"))
        type_name = _coerce_text(schema_type.get("name"))
        if type_id and type_name:
            mapping[type_id] = type_name
    return mapping


def _coerce_text(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _coerce_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _coerce_text(item)
        if text:
            items.append(text)
    return items
