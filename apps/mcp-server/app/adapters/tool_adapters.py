from __future__ import annotations

from app.adapters.web_tools import WebFetchAdapter, WebSearchAdapter
from app.contracts import (
    AddToolInput,
    AddToolOutput,
    EchoToolInput,
    EchoToolOutput,
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


class ToolAdapterRegistry:
    def __init__(self, web_search_adapter: WebSearchAdapter, web_fetch_adapter: WebFetchAdapter):
        self._web_search_adapter = web_search_adapter
        self._web_fetch_adapter = web_fetch_adapter

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
