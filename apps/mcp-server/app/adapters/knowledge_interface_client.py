from __future__ import annotations

from typing import Any, Protocol


class KnowledgeInterfaceClient(Protocol):
    def get_schema(self, *, universe_id: str) -> dict[str, Any]: ...

    def get_entity_context(
        self,
        *,
        entity_id: str,
        user_id: str,
        max_block_level: int,
    ) -> dict[str, Any]: ...
