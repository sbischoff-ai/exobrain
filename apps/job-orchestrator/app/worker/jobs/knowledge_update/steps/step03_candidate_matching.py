from __future__ import annotations

import grpc

from app.contracts import KnowledgeUpdatePayload
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.types import CandidateMatchResult, EntityExtractionResult


def classify_candidate_matches(candidates: list[dict[str, object]]) -> dict[str, object]:
    return core._classify_candidate_matches(candidates)


async def run(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    extraction: EntityExtractionResult,
) -> list[CandidateMatchResult]:
    return await core._run_step_three_entity_candidate_matching(channel, payload, extraction)
