from __future__ import annotations

import grpc

from app.contracts import KnowledgeUpdatePayload
from app.settings import Settings
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import CandidateMatchResult, ResolvedEntity


def build_json_schema() -> dict[str, object]:
    return core._build_step_five_comparison_schema()


def extract_matched_entity_id(decision: str) -> str | None:
    return core._extract_matched_entity_id(decision)


async def run(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    candidate_matching: list[CandidateMatchResult],
    entity_context_documents: list[str],
    settings: Settings,
) -> list[ResolvedEntity]:
    return await core._run_step_five_detailed_comparison(
        channel,
        payload,
        candidate_matching,
        entity_context_documents,
        settings,
    )
