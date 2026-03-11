from __future__ import annotations

from typing import Any

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
    RelationshipDirection,
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
        related_entities = _map_related_entities(response.get("neighbors"))

        return GetEntityContextToolOutput(
            context_markdown=_build_context_markdown(response=response, related_entities=related_entities),
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


def _build_context_markdown(*, response: dict[str, Any], related_entities: list[GetEntityContextRelatedEntityItem]) -> str:
    entity = response.get("entity") if isinstance(response.get("entity"), dict) else {}
    entity_name = _coerce_text(entity.get("name")) or _coerce_text(entity.get("id")) or "Entity"
    entity_type = _coerce_text(entity.get("type_id")) or "unknown"

    lines = [f"## {entity_name}", f"- Type: `{entity_type}`"]

    aliases = _coerce_list(entity.get("aliases"))
    if aliases:
        lines.append(f"- Aliases: {', '.join(aliases)}")

    blocks = response.get("blocks") if isinstance(response.get("blocks"), list) else []
    block_snippets: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = _coerce_text(block.get("text"))
        if text:
            block_snippets.append(" ".join(text.split()))

    if block_snippets:
        lines.append("\n### Context")
        for snippet in block_snippets[:3]:
            lines.append(f"- {snippet}")

    if related_entities:
        lines.append("\n### Related")
        for related in related_entities[:5]:
            lines.append(f"- @{related.entity_id}: {related.name} ({related.relationship_type})")

    return "\n".join(lines)


def _map_related_entities(raw_neighbors: Any) -> list[GetEntityContextRelatedEntityItem]:
    neighbors = raw_neighbors if isinstance(raw_neighbors, list) else []
    related_entities: list[GetEntityContextRelatedEntityItem] = []
    for neighbor in neighbors:
        if not isinstance(neighbor, dict):
            continue

        related = neighbor.get("other_entity") if isinstance(neighbor.get("other_entity"), dict) else {}
        entity_id = _coerce_text(related.get("id"))
        if not entity_id:
            continue

        direction_raw = _coerce_text(neighbor.get("direction"))
        direction = RelationshipDirection.OUTGOING
        if direction_raw and direction_raw.upper() == "INCOMING":
            direction = RelationshipDirection.INCOMING

        related_entities.append(
            GetEntityContextRelatedEntityItem(
                entity_id=entity_id,
                name=_coerce_text(related.get("name")) or entity_id,
                aliases=_coerce_list(related.get("aliases")),
                entity_type=_coerce_text(related.get("type_id")) or "unknown",
                description=_coerce_text(related.get("description")) or "",
                relationship_type=_coerce_text(neighbor.get("edge_type")) or "RELATED_TO",
                relationship_direction=direction,
            )
        )

    return related_entities


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
