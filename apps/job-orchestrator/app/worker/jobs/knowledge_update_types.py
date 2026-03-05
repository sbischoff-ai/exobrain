from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractedUniverse(BaseModel):
    name: str
    description: str


class ExtractedEntity(BaseModel):
    name: str
    node_type: str
    aliases: list[str]
    short_description: str
    universe_id: str | None = None


class EntityExtractionResult(BaseModel):
    extracted_entities: list[ExtractedEntity]
    extracted_universes: list[ExtractedUniverse]


class CandidateMatchResult(BaseModel):
    entity_index: int
    extracted_entity: ExtractedEntity
    candidate_matches: list[dict[str, object]] = Field(default_factory=list)
    status: Literal["new_entity", "matched", "needs_detailed_comparison"]
    candidate_entity_ids: list[str] = Field(default_factory=list)
    matched_entity_id: str | None = None


class ResolvedEntity(BaseModel):
    entity_index: int
    extracted_entity: ExtractedEntity
    resolved_entity_id: str
    resolution_status: Literal["new_entity", "matched"]


class RelationshipPair(BaseModel):
    entity_id_1: str
    entity_id_2: str


class MatchedRelationship(BaseModel):
    from_entity_id: str
    to_entity_id: str
    edge_type: str
    confidence: float


class FinalEntityContextBlock(BaseModel):
    block_id: str
    parent_block_id: str | None = None
    text: str


class FinalEntityContextGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: dict[str, object]
    blocks: list[FinalEntityContextBlock]
