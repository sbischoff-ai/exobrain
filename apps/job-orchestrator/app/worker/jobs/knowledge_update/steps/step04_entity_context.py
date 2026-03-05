from __future__ import annotations

from app.settings import Settings
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import EntityExtractionResult


def build_json_schema() -> dict[str, object]:
    return core._build_step_four_entity_context_schema()


async def run(extraction: EntityExtractionResult, markdown_document: str, settings: Settings) -> list[str]:
    return await core._run_step_four_create_entity_contexts(extraction, markdown_document, settings)
