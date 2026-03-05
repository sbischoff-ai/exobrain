from __future__ import annotations

import grpc

from app.contracts import KnowledgeUpdatePayload
from app.settings import Settings
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import EntityExtractionResult


def build_json_schema() -> dict[str, object]:
    return core._build_step_two_entity_extraction_json_schema()


def build_system_prompt(entity_schema_context: dict[str, object]) -> str:
    return core._build_step_two_entity_extraction_system_prompt(entity_schema_context)


async def run(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    markdown_document: str,
    settings: Settings,
) -> EntityExtractionResult:
    return await core._run_step_two_entity_extraction(channel, payload, markdown_document, settings)
