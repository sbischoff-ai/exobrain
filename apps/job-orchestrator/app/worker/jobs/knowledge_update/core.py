from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import sys
import traceback
from typing import Awaitable, Callable, TypeVar
from uuid import NAMESPACE_URL, uuid4, uuid5

import grpc
from google.protobuf.json_format import ParseError
from google.protobuf.json_format import MessageToDict, ParseDict
from pydantic import BaseModel, ValidationError

from app.contracts import JobEnvelope, KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.settings import Settings, get_settings
from app.worker.jobs.knowledge_update_types import (
    CandidateMatchResult,
    EntityExtractionResult,
    FinalEntityContextGraph,
    MatchedRelationship,
    RelationshipPair,
    ResolvedEntity,
)

logger = logging.getLogger(__name__)


_MATCH_DECISION_PATTERN = re.compile(r"^MATCH\((?P<entity_id>[^)]+)\)$")
_PARSE_DICT_FIELD_PATTERN = re.compile(r"Failed to parse (?P<field>[A-Za-z_][A-Za-z0-9_]*) field")
_ModelT = TypeVar("_ModelT", bound=BaseModel)
_ResultT = TypeVar("_ResultT")


class KnowledgeUpdateStepError(RuntimeError):
    def __init__(
        self,
        *,
        step_name: str,
        operation: str,
        original_exception: BaseException,
        detail: str | None = None,
    ) -> None:
        self.step_name = step_name
        self.operation = operation
        self.original_exception_class = type(original_exception).__name__
        rendered_detail = detail if isinstance(detail, str) and detail else str(original_exception)
        message = (
            "knowledge.update step failed"
            f" step_name={step_name}"
            f" operation={operation}"
            f" original_exception_class={self.original_exception_class}"
            f" detail={rendered_detail}"
        )
        super().__init__(message)


def _exception_detail(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    status_code = getattr(exc, "status_code", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)

    detail = str(exc)
    if response is None:
        return detail

    response_text = getattr(response, "text", None)
    if callable(response_text):
        try:
            response_text = response_text()
        except Exception:  # noqa: BLE001
            response_text = None

    if not isinstance(response_text, str):
        return detail

    response_text = response_text.strip()
    if not response_text:
        return detail

    max_length = 800
    if len(response_text) > max_length:
        response_text = f"{response_text[:max_length]}…"

    status_prefix = f" status_code={status_code}" if isinstance(status_code, int) else ""
    return f"{detail}{status_prefix} response_body={response_text}"


def _is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, grpc.RpcError)):
        if isinstance(exc, grpc.aio.AioRpcError):
            return exc.code() in {
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.INTERNAL,
            }
        return True

    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        return True

    transient_http_error_names = {
        "TimeoutException",
        "TransportError",
        "ReadTimeout",
        "ConnectTimeout",
        "RemoteProtocolError",
    }
    return type(exc).__name__ in transient_http_error_names


async def _call_with_retry(
    *,
    step_name: str,
    operation: str,
    call: Callable[[], Awaitable[_ResultT]],
    max_attempts: int = 3,
    base_delay_seconds: float = 0.2,
    max_delay_seconds: float = 2.0,
) -> _ResultT:
    for attempt in range(1, max_attempts + 1):
        try:
            return await call()
        except Exception as exc:  # noqa: BLE001
            if not _is_transient_error(exc) or attempt >= max_attempts:
                logger.error(
                    "knowledge.update step operation failed",
                    extra={
                        "step_name": step_name,
                        "operation": operation,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "exception_class": type(exc).__name__,
                    },
                )
                raise KnowledgeUpdateStepError(
                    step_name=step_name,
                    operation=operation,
                    original_exception=exc,
                    detail=_exception_detail(exc),
                ) from exc

            backoff = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            jitter = random.uniform(0.0, backoff * 0.2)
            delay_seconds = backoff + jitter
            logger.warning(
                "knowledge.update retrying transient failure",
                extra={
                    "step_name": step_name,
                    "operation": operation,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "delay_seconds": delay_seconds,
                    "exception_class": type(exc).__name__,
                },
            )
            await asyncio.sleep(delay_seconds)

    raise RuntimeError("knowledge.update retry loop exhausted")


def _compact_validation_summary(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
        for err in exc.errors()[:3]
    )


def _validate_model(step_name: str, model: type[_ModelT], payload: object) -> _ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        summary = _compact_validation_summary(exc)
        raise RuntimeError(f"knowledge.update {step_name} validation failed: {summary}") from exc


def _extract_parse_dict_field_path(exc: ParseError) -> str:
    parts = _PARSE_DICT_FIELD_PATTERN.findall(str(exc))
    if parts:
        return ".".join(parts)
    return "<unknown>"


def _validate_upsert_graph_delta_payload(step_name: str, payload: dict[str, object]) -> knowledge_pb2.UpsertGraphDeltaRequest:
    try:
        return ParseDict(payload, knowledge_pb2.UpsertGraphDeltaRequest())
    except ParseError as exc:
        field_path = _extract_parse_dict_field_path(exc)
        raise RuntimeError(
            f"knowledge.update {step_name} validation failed at '{field_path}': {exc}"
        ) from exc


class _StepFiveComparisonDecision(BaseModel):
    model_config = {"extra": "forbid"}

    decision: str


class _StepFourEntityContextResult(BaseModel):
    model_config = {"extra": "forbid"}

    focused_markdown: str


class _StepSixRelationshipExtractionResult(BaseModel):
    model_config = {"extra": "forbid"}

    entity_pairs: list[RelationshipPair]


class _StepSevenRelationshipMatchResult(BaseModel):
    model_config = {"extra": "forbid"}

    from_entity_id: str
    to_entity_id: str
    edge_type: str
    confidence: float


class _StepTenMention(BaseModel):
    model_config = {"extra": "forbid"}

    block_id: str
    entity_id: str
    confidence: float


class _StepTenMentionsResult(BaseModel):
    model_config = {"extra": "forbid"}

    mentions: list[_StepTenMention]


class _RpcMessageDict(BaseModel):
    model_config = {"extra": "forbid"}

    payload: dict[str, object]


def _format_exception_for_stderr(exc: BaseException) -> str:
    return "".join(traceback.format_exception(exc)).rstrip()


def _message_entity_name(journal_reference: str, sequence_number: int) -> str:
    return f"{journal_reference} message {sequence_number}"


def _require_created_at(created_at: str | None, sequence_number: int) -> str:
    if created_at:
        return created_at
    raise ValueError(f"knowledge.update message at sequence {sequence_number} missing created_at")


def _message_to_dict(reply: object, *, rpc_name: str) -> dict[str, object]:
    if reply is None:
        raise RuntimeError(f"knowledge.update received empty response from {rpc_name}")
    raw_payload = MessageToDict(reply, preserving_proto_field_name=True)
    return _validate_model(f"{rpc_name} gRPC response", _RpcMessageDict, {"payload": raw_payload}).payload


async def _build_upsert_graph_delta_step_one(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
) -> dict[str, object]:
    get_user_init_graph = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetUserInitGraph",
        request_serializer=knowledge_pb2.GetUserInitGraphRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetUserInitGraphReply.FromString,
    )
    init_graph = await _call_with_retry(
        step_name="step zero",
        operation="GetUserInitGraph",
        call=lambda: get_user_init_graph(
            knowledge_pb2.GetUserInitGraphRequest(
                user_id=payload.requested_by_user_id,
                user_name=payload.requested_by_user_id,
            )
        ),
    )

    request = knowledge_pb2.UpsertGraphDeltaRequest()
    for sequence_number, message in enumerate(payload.messages, start=1):
        created_at = _require_created_at(message.created_at, sequence_number)
        message_entity_id = str(uuid5(NAMESPACE_URL, f"{payload.journal_reference}:message:{sequence_number}"))
        message_block_id = str(uuid5(NAMESPACE_URL, f"{payload.journal_reference}:block:{sequence_number}"))

        request.entities.append(
            knowledge_pb2.EntityNode(
                id=message_entity_id,
                type_id="node.chat_message",
                user_id=payload.requested_by_user_id,
                visibility=knowledge_pb2.PRIVATE,
                properties=[
                    knowledge_pb2.PropertyValue(
                        key="name", string_value=_message_entity_name(payload.journal_reference, sequence_number)
                    ),
                    knowledge_pb2.PropertyValue(key="start", datetime_value=created_at),
                    knowledge_pb2.PropertyValue(key="end", datetime_value=created_at),
                ],
            )
        )
        request.blocks.append(
            knowledge_pb2.BlockNode(
                id=message_block_id,
                type_id="node.block",
                user_id=payload.requested_by_user_id,
                visibility=knowledge_pb2.PRIVATE,
                properties=[
                    knowledge_pb2.PropertyValue(key="text", string_value=message.content or ""),
                ],
            )
        )
        request.edges.extend(
            [
                knowledge_pb2.GraphEdge(
                    from_id=message_entity_id,
                    to_id=init_graph.person_entity_id,
                    edge_type="SENT_TO",
                    user_id=payload.requested_by_user_id,
                    visibility=knowledge_pb2.PRIVATE,
                ),
                knowledge_pb2.GraphEdge(
                    from_id=message_entity_id,
                    to_id=init_graph.assistant_entity_id,
                    edge_type="SENT_BY",
                    user_id=payload.requested_by_user_id,
                    visibility=knowledge_pb2.PRIVATE,
                ),
                knowledge_pb2.GraphEdge(
                    from_id=message_entity_id,
                    to_id=message_block_id,
                    edge_type="DESCRIBED_BY",
                    user_id=payload.requested_by_user_id,
                    visibility=knowledge_pb2.PRIVATE,
                ),
            ]
        )

    return _message_to_dict(request, rpc_name="UpsertGraphDeltaRequest")


def _canonicalize_speaker(role: str | None) -> str:
    if not role:
        return "UNKNOWN"
    normalized = "_".join(role.strip().split()).replace("-", "_")
    return normalized.upper() or "UNKNOWN"


def _build_batch_document(payload: KnowledgeUpdatePayload, include_header: bool = True) -> str:
    available_timestamps = [message.created_at for message in payload.messages if message.created_at]
    start = min(available_timestamps) if available_timestamps else "unknown"
    end = max(available_timestamps) if available_timestamps else "unknown"

    lines: list[str] = []

    if include_header:
        lines.extend(
            [
                "=== BATCH DOCUMENT ===",
                f"conversation_id: {payload.journal_reference}",
                f"user_id: {payload.requested_by_user_id}",
                f"time_range_start: {start}",
                f"time_range_end: {end}",
                "",
            ]
        )

    for index, message in enumerate(payload.messages, start=1):
        turn_label = message.sequence if message.sequence is not None else index
        lines.extend(
            [
                f"--- TURN {turn_label} ---",
                f"speaker: {_canonicalize_speaker(message.role)}",
                f"timestamp: {message.created_at or 'unknown'}",
                "content:",
                message.content or "",
                "",
            ]
        )

    return "\n".join(lines).rstrip()


def _step_two_store_batch_document(payload: KnowledgeUpdatePayload) -> str:
    batch_document = _build_batch_document(payload)
    logger.info("knowledge.update step one batch document:\n%s", batch_document)
    return batch_document


def _build_step_two_entity_extraction_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "extracted_entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "node_type": {"type": "string", "minLength": 1},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "short_description": {"type": "string"},
                        "universe_id": {"type": "string"},
                    },
                    "required": ["name", "node_type", "aliases", "short_description"],
                },
            },
            "extracted_universes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "description": {"type": "string", "minLength": 1},
                    },
                    "required": ["name", "description"],
                },
            },
        },
        "required": ["extracted_entities", "extracted_universes"],
    }


def _build_step_two_entity_extraction_system_prompt(entity_schema_context: dict[str, object]) -> str:
    from app.worker.jobs.knowledge_update.prompts import build_step_two_entity_extraction_system_prompt

    return build_step_two_entity_extraction_system_prompt(entity_schema_context)


async def _run_step_two_entity_extraction(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    markdown_document: str,
    settings: Settings,
) -> EntityExtractionResult:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format

    get_entity_extraction_schema_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityExtractionSchemaContext",
        request_serializer=knowledge_pb2.GetEntityExtractionSchemaContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEntityExtractionSchemaContextReply.FromString,
    )
    context_reply = await _call_with_retry(
        step_name="step two",
        operation="GetEntityExtractionSchemaContext",
        call=lambda: get_entity_extraction_schema_context_rpc(
            knowledge_pb2.GetEntityExtractionSchemaContextRequest(
                user_id=payload.requested_by_user_id,
            )
        ),
    )
    context_dict = _message_to_dict(context_reply, rpc_name="GetEntityExtractionSchemaContext")

    compiled_agent = create_agent(
        model=ModelProviderChatModel(
            model=settings.knowledge_update_extraction_model,
            base_url=settings.model_provider_base_url,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=_build_step_two_entity_extraction_system_prompt(context_dict),
        response_format=build_strict_response_format(_build_step_two_entity_extraction_json_schema()),
    )
    reply = await _call_with_retry(
        step_name="step two",
        operation="entity_extraction_agent.ainvoke",
        call=lambda: compiled_agent.ainvoke({"messages": [{"role": "user", "content": markdown_document}]}),
    )
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("knowledge.update step two validation failed: missing structured_response")
    return _validate_model("step two", EntityExtractionResult, structured)


def _classify_candidate_matches(candidates: list[dict[str, object]]) -> dict[str, object]:
    scored = [candidate for candidate in candidates if isinstance(candidate.get("score"), (float, int))]
    over_01 = [candidate for candidate in scored if float(candidate["score"]) > 0.1]
    if not over_01:
        return {"status": "new_entity", "candidate_entity_ids": []}

    over_06 = [candidate for candidate in over_01 if float(candidate["score"]) > 0.6]
    if len(over_06) == 1 and isinstance(over_06[0].get("entity_id"), str):
        return {
            "status": "matched",
            "candidate_entity_ids": [],
            "matched_entity_id": over_06[0]["entity_id"],
        }

    detailed_candidates = [
        candidate
        for candidate in scored
        if float(candidate["score"]) > 0.15 and isinstance(candidate.get("entity_id"), str)
    ]
    if not detailed_candidates:
        return {"status": "new_entity", "candidate_entity_ids": []}

    return {
        "status": "needs_detailed_comparison",
        "candidate_entity_ids": [candidate["entity_id"] for candidate in detailed_candidates],
    }


async def _run_step_three_entity_candidate_matching(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    extraction: EntityExtractionResult,
) -> list[CandidateMatchResult]:
    find_candidates_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/FindEntityCandidates",
        request_serializer=knowledge_pb2.FindEntityCandidatesRequest.SerializeToString,
        response_deserializer=knowledge_pb2.FindEntityCandidatesReply.FromString,
    )

    results: list[CandidateMatchResult] = []
    for index, extracted_entity in enumerate(extraction.extracted_entities):
        alias_names = [alias for alias in extracted_entity.aliases if isinstance(alias, str)]
        entity_name = extracted_entity.name
        names = [name for name in [entity_name, *alias_names] if name]
        node_type = extracted_entity.node_type
        short_description = extracted_entity.short_description

        candidates_reply = await _call_with_retry(
            step_name="step three",
            operation="FindEntityCandidates",
            call=lambda: find_candidates_rpc(
                knowledge_pb2.FindEntityCandidatesRequest(
                    names=names,
                    potential_type_ids=[node_type] if node_type else [],
                    short_description=short_description,
                    user_id=payload.requested_by_user_id,
                )
            ),
        )
        candidate_dicts = _message_to_dict(candidates_reply, rpc_name="FindEntityCandidates").get("candidates", [])
        classification = _classify_candidate_matches(
            [candidate for candidate in candidate_dicts if isinstance(candidate, dict)]
        )
        result_payload = {
            "entity_index": index,
            "extracted_entity": extracted_entity.model_dump(),
            "candidate_matches": [item for item in candidate_dicts if isinstance(item, dict)],
            **classification,
        }
        results.append(_validate_model("step three", CandidateMatchResult, result_payload))

    return results


def _build_step_four_entity_context_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "focused_markdown": {"type": "string", "minLength": 1},
        },
        "required": ["focused_markdown"],
    }


async def _run_step_four_create_entity_contexts(
    extraction: EntityExtractionResult,
    markdown_document: str,
    settings: Settings,
) -> list[str]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format

    system_prompt = "\n\n".join(
        [
            "You are the knowledge.update context reasoner.",
            (
                "For each extracted entity, filter the conversation markdown to only relevant details and produce "
                "a focused markdown document."
            ),
            (
                "Format requirements: use markdown headings with depth at most 2 (# and ## only), and split content "
                "into semantically bounded paragraphs or lists of 30 to 80 words."
            ),
            "Return strict JSON only with focused_markdown.",
        ]
    )

    compiled_agent = create_agent(
        model=ModelProviderChatModel(
            model="reasoner",
            base_url=settings.model_provider_base_url,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=system_prompt,
        response_format=build_strict_response_format(_build_step_four_entity_context_schema()),
    )

    documents: list[str] = []
    for extracted_entity in extraction.extracted_entities:
        prompt = json.dumps(
            {
                "entity": extracted_entity.model_dump(),
                "markdown_batch_document": markdown_document,
            },
            ensure_ascii=False,
        )
        reply = await _call_with_retry(
            step_name="step four",
            operation="entity_context_agent.ainvoke",
            call=lambda: compiled_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}),
        )
        structured = reply.get("structured_response") if isinstance(reply, dict) else None
        if not isinstance(structured, dict) or not isinstance(structured.get("focused_markdown"), str):
            raise RuntimeError("knowledge.update step four reasoner returned invalid focused_markdown")
        parsed = _validate_model("step four", _StepFourEntityContextResult, structured)
        documents.append(parsed.focused_markdown)
    return documents


def _build_step_five_comparison_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {"type": "string", "minLength": 1},
        },
        "required": ["decision"],
    }


def _extract_matched_entity_id(decision: str) -> str | None:
    if decision == "NEW_ENTITY":
        return None
    match = _MATCH_DECISION_PATTERN.match(decision)
    if not match:
        return None
    return match.group("entity_id")


async def _run_step_five_detailed_comparison(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    candidate_matching: list[CandidateMatchResult],
    entity_context_documents: list[str],
    settings: Settings,
) -> list[ResolvedEntity]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format

    get_entity_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityContext",
        request_serializer=knowledge_pb2.GetEntityContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEntityContextReply.FromString,
    )

    comparison_agent = create_agent(
        model=ModelProviderChatModel(
            model="worker",
            base_url=settings.model_provider_base_url,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update detailed comparison worker. "
            "Compare extracted entity context markdown against candidate entity contexts. "
            "Return strict JSON only with decision as MATCH({entity_id}) or NEW_ENTITY."
        ),
        response_format=build_strict_response_format(_build_step_five_comparison_schema()),
    )

    resolved_entities: list[ResolvedEntity] = []
    for match_item in candidate_matching:
        extracted_entity = match_item.extracted_entity

        status = match_item.status
        resolution_status = "new_entity"
        resolved_entity_id: str
        if status == "matched" and match_item.matched_entity_id:
            resolved_entity_id = match_item.matched_entity_id
            resolution_status = "matched"
        elif status == "needs_detailed_comparison":
            entity_index = int(match_item.entity_index)
            focused_markdown = entity_context_documents[entity_index] if 0 <= entity_index < len(entity_context_documents) else ""
            candidate_ids = [item for item in match_item.candidate_entity_ids if isinstance(item, str)]
            candidate_contexts: list[dict[str, object]] = []
            for candidate_id in candidate_ids:
                context_reply = await _call_with_retry(
                    step_name="step five",
                    operation="GetEntityContext",
                    call=lambda: get_entity_context_rpc(
                        knowledge_pb2.GetEntityContextRequest(
                            entity_id=candidate_id,
                            user_id=payload.requested_by_user_id,
                            max_block_level=1,
                        )
                    ),
                )
                candidate_contexts.append(_message_to_dict(context_reply, rpc_name="GetEntityContext"))

            prompt = json.dumps(
                {
                    "extracted_entity": extracted_entity.model_dump(),
                    "extracted_entity_markdown": focused_markdown,
                    "candidate_contexts": candidate_contexts,
                },
                ensure_ascii=False,
            )
            reply = await _call_with_retry(
                step_name="step five",
                operation="detailed_comparison_agent.ainvoke",
                call=lambda: comparison_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}),
            )
            structured = reply.get("structured_response") if isinstance(reply, dict) else None
            if not isinstance(structured, dict):
                raise RuntimeError("knowledge.update step five validation failed: missing structured_response")
            decision_payload = _validate_model("step five", _StepFiveComparisonDecision, structured)
            decision = decision_payload.decision
            matched_entity_id = _extract_matched_entity_id(decision) if isinstance(decision, str) else None
            if matched_entity_id and matched_entity_id in candidate_ids:
                resolved_entity_id = matched_entity_id
                resolution_status = "matched"
            else:
                resolved_entity_id = str(uuid4())
        else:
            resolved_entity_id = str(uuid4())

        resolved_payload = {
            "entity_index": match_item.entity_index,
            "extracted_entity": extracted_entity.model_dump(),
            "resolved_entity_id": resolved_entity_id,
            "resolution_status": resolution_status,
        }
        resolved_entities.append(_validate_model("step five", ResolvedEntity, resolved_payload))

    return resolved_entities


def _build_step_six_relationship_extraction_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "entity_pairs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "entity_id_1": {"type": "string", "minLength": 1},
                        "entity_id_2": {"type": "string", "minLength": 1},
                    },
                    "required": ["entity_id_1", "entity_id_2"],
                },
            }
        },
        "required": ["entity_pairs"],
    }


def _deduplicate_entity_pairs(
    entity_pairs: list[RelationshipPair],
    valid_entity_ids: set[str],
) -> list[RelationshipPair]:
    deduped: list[RelationshipPair] = []
    seen: set[tuple[str, str]] = set()
    skipped_invalid = 0
    for pair in entity_pairs:
        entity_id_1 = pair.entity_id_1
        entity_id_2 = pair.entity_id_2
        if entity_id_1 == entity_id_2:
            skipped_invalid += 1
            continue
        if entity_id_1 not in valid_entity_ids or entity_id_2 not in valid_entity_ids:
            skipped_invalid += 1
            continue
        normalized = tuple(sorted((entity_id_1, entity_id_2)))
        if normalized in seen:
            skipped_invalid += 1
            continue
        seen.add(normalized)
        deduped.append(RelationshipPair(entity_id_1=entity_id_1, entity_id_2=entity_id_2))
    if skipped_invalid:
        logger.warning("knowledge.update step six skipped invalid relationship pairs", extra={"skipped": skipped_invalid})
    return deduped


async def _run_step_six_relationship_extraction(
    resolved_entities: list[ResolvedEntity],
    markdown_document: str,
    settings: Settings,
) -> list[RelationshipPair]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format

    extracted_entities_with_ids = [
        {
            "entity_id": item.resolved_entity_id,
            "name": item.extracted_entity.name,
            "node_type": item.extracted_entity.node_type,
        }
        for item in resolved_entities
    ]
    valid_entity_ids = {
        entity.get("entity_id")
        for entity in extracted_entities_with_ids
        if isinstance(entity.get("entity_id"), str)
    }

    relationship_agent = create_agent(
        model=ModelProviderChatModel(
            model="worker",
            base_url=settings.model_provider_base_url,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update relationship extraction worker. "
            "Identify entity pairs that are related in the markdown batch document. "
            "Return strict JSON only with entity_pairs."
        ),
        response_format=build_strict_response_format(_build_step_six_relationship_extraction_schema()),
    )

    prompt = json.dumps(
        {
            "entities": extracted_entities_with_ids,
            "markdown_batch_document": markdown_document,
        },
        ensure_ascii=False,
    )
    reply = await _call_with_retry(
        step_name="step six",
        operation="relationship_extraction_agent.ainvoke",
        call=lambda: relationship_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}),
    )
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("knowledge.update step six validation failed: missing structured_response")
    pairs_payload = _validate_model("step six", _StepSixRelationshipExtractionResult, structured)
    return _deduplicate_entity_pairs(pairs_payload.entity_pairs, valid_entity_ids)




def _build_edge_extraction_schema_context_request(
    first_entity_type: str,
    second_entity_type: str,
    user_id: str,
) -> knowledge_pb2.GetEdgeExtractionSchemaContextRequest:
    field_names = {
        field.name for field in knowledge_pb2.GetEdgeExtractionSchemaContextRequest.DESCRIPTOR.fields
    }
    payload: dict[str, object] = {"user_id": user_id}
    if {"source_entity_type_id", "target_entity_type_id"}.issubset(field_names):
        payload["source_entity_type_id"] = first_entity_type
        payload["target_entity_type_id"] = second_entity_type
    else:
        payload["first_entity_type"] = first_entity_type
        payload["second_entity_type"] = second_entity_type
    return knowledge_pb2.GetEdgeExtractionSchemaContextRequest(**payload)

def _build_step_seven_relationship_match_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "from_entity_id": {"type": "string", "minLength": 1},
            "to_entity_id": {"type": "string", "minLength": 1},
            "edge_type": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["from_entity_id", "to_entity_id", "edge_type", "confidence"],
    }


async def _run_step_seven_match_relationship_type_and_score(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    resolved_entities: list[ResolvedEntity],
    entity_context_documents: list[str],
    entity_pairs: list[RelationshipPair],
    settings: Settings,
) -> list[MatchedRelationship]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format

    get_edge_extraction_schema_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEdgeExtractionSchemaContext",
        request_serializer=knowledge_pb2.GetEdgeExtractionSchemaContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEdgeExtractionSchemaContextReply.FromString,
    )

    resolution_by_id: dict[str, dict[str, object]] = {}
    for item in resolved_entities:
        entity_id = item.resolved_entity_id
        entity_index = int(item.entity_index)
        focused_markdown = entity_context_documents[entity_index] if 0 <= entity_index < len(entity_context_documents) else ""
        resolution_by_id[entity_id] = {
            "entity_id": entity_id,
            "node_type": item.extracted_entity.node_type,
            "name": item.extracted_entity.name,
            "focused_markdown": focused_markdown,
        }

    relationship_match_agent = create_agent(
        model=ModelProviderChatModel(
            model="worker",
            base_url=settings.model_provider_base_url,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update relationship matching worker. "
            "Given two entities, their focused contexts, and allowed edge schema context, return the best "
            "relationship direction, edge type, and confidence between 0 and 1. "
            "Return strict JSON only."
        ),
        response_format=build_strict_response_format(_build_step_seven_relationship_match_schema()),
    )

    matched_relationships: list[MatchedRelationship] = []
    skipped_invalid = 0
    for pair in entity_pairs:
        entity_id_1 = pair.entity_id_1
        entity_id_2 = pair.entity_id_2
        if entity_id_1 not in resolution_by_id or entity_id_2 not in resolution_by_id:
            skipped_invalid += 1
            continue

        entity_1 = resolution_by_id[entity_id_1]
        entity_2 = resolution_by_id[entity_id_2]
        node_type_1 = entity_1.get("node_type") if isinstance(entity_1.get("node_type"), str) else ""
        node_type_2 = entity_2.get("node_type") if isinstance(entity_2.get("node_type"), str) else ""
        if not node_type_1 or not node_type_2:
            skipped_invalid += 1
            continue

        edge_context_reply = await _call_with_retry(
            step_name="step seven",
            operation="GetEdgeExtractionSchemaContext",
            call=lambda: get_edge_extraction_schema_context_rpc(
                _build_edge_extraction_schema_context_request(
                    first_entity_type=node_type_1,
                    second_entity_type=node_type_2,
                    user_id=payload.requested_by_user_id,
                )
            ),
        )
        edge_context = _message_to_dict(edge_context_reply, rpc_name="GetEdgeExtractionSchemaContext")
        prompt = json.dumps(
            {
                "entity_1": entity_1,
                "entity_2": entity_2,
                "edge_extraction_schema_context": edge_context,
            },
            ensure_ascii=False,
        )

        reply = await _call_with_retry(
            step_name="step seven",
            operation="relationship_match_agent.ainvoke",
            call=lambda: relationship_match_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}),
        )
        structured = reply.get("structured_response") if isinstance(reply, dict) else None
        if not isinstance(structured, dict):
            raise RuntimeError("knowledge.update step seven validation failed: missing structured_response")
        match_result = _validate_model("step seven", _StepSevenRelationshipMatchResult, structured)
        if {match_result.from_entity_id, match_result.to_entity_id} != {entity_id_1, entity_id_2}:
            skipped_invalid += 1
            continue
        matched_relationships.append(
            MatchedRelationship(
                from_entity_id=match_result.from_entity_id,
                to_entity_id=match_result.to_entity_id,
                edge_type=match_result.edge_type,
                confidence=float(match_result.confidence),
            )
        )

    if skipped_invalid:
        logger.warning("knowledge.update step seven skipped invalid relationship matches", extra={"skipped": skipped_invalid})

    return matched_relationships


def _build_step_eight_final_entity_context_graph_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "entity": {"type": "object", "additionalProperties": True},
            "blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "block_id": {"type": "string", "minLength": 1},
                        "parent_block_id": {"type": "string"},
                        "text": {"type": "string", "minLength": 1},
                    },
                    "required": ["block_id", "text"],
                },
            },
        },
        "required": ["entity", "blocks"],
    }


def _normalize_step_eight_structured_response(
    structured: dict[str, object],
    resolved: ResolvedEntity,
) -> dict[str, object]:
    normalized = dict(structured)
    raw_entity = normalized.get("entity")
    entity = dict(raw_entity) if isinstance(raw_entity, dict) else {}

    extracted = resolved.extracted_entity
    entity.setdefault("entity_id", resolved.resolved_entity_id)
    entity.setdefault("node_type", extracted.node_type)
    entity.setdefault("name", extracted.name)
    entity.setdefault("aliases", extracted.aliases)
    entity.setdefault("short_description", extracted.short_description)
    if extracted.universe_id:
        entity.setdefault("universe_id", extracted.universe_id)

    if entity != raw_entity:
        logger.warning(
            "knowledge.update step eight repaired entity payload from fallback context",
            extra={
                "entity_id": resolved.resolved_entity_id,
                "resolution_status": resolved.resolution_status,
                "had_entity": isinstance(raw_entity, dict),
            },
        )

    normalized["entity"] = entity
    return normalized


async def _run_step_eight_build_final_entity_context_graphs(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    resolved_entities: list[ResolvedEntity],
    entity_context_documents: list[str],
    settings: Settings,
) -> list[FinalEntityContextGraph]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format

    get_entity_type_property_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityTypePropertyContext",
        request_serializer=knowledge_pb2.GetEntityTypePropertyContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEntityTypePropertyContextReply.FromString,
    )
    get_entity_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityContext",
        request_serializer=knowledge_pb2.GetEntityContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEntityContextReply.FromString,
    )

    schema = _build_step_eight_final_entity_context_graph_schema()
    final_graphs: list[FinalEntityContextGraph] = []

    for resolved in resolved_entities:
        extracted = resolved.extracted_entity.model_dump()
        entity_id = resolved.resolved_entity_id
        node_type = resolved.extracted_entity.node_type
        if not node_type:
            raise RuntimeError(f"knowledge.update step eight validation failed: missing node_type for entity {entity_id}")

        type_context_reply = await _call_with_retry(
            step_name="step eight",
            operation="GetEntityTypePropertyContext",
            call=lambda: get_entity_type_property_context_rpc(
                knowledge_pb2.GetEntityTypePropertyContextRequest(
                    type_id=node_type,
                    user_id=payload.requested_by_user_id,
                    include_inherited=True,
                )
            ),
        )
        type_context = _message_to_dict(type_context_reply, rpc_name="GetEntityTypePropertyContext")

        resolution_status = resolved.resolution_status
        entity_index = resolved.entity_index
        focused_markdown = entity_context_documents[entity_index] if 0 <= entity_index < len(entity_context_documents) else ""

        existing_entity_context: dict[str, object] | None = None
        model_name = "worker"
        system_prompt = (
            "You are the knowledge.update final entity context graph worker. "
            "Given focused markdown and writable property context, build an entity payload and block tree. "
            "Return strict JSON only with entity and blocks."
        )

        if resolution_status == "matched":
            model_name = "reasoner"
            context_reply = await _call_with_retry(
                step_name="step eight",
                operation="GetEntityContext",
                call=lambda: get_entity_context_rpc(
                    knowledge_pb2.GetEntityContextRequest(
                        entity_id=entity_id,
                        user_id=payload.requested_by_user_id,
                        max_block_level=2,
                    )
                ),
            )
            existing_entity_context = _message_to_dict(context_reply, rpc_name="GetEntityContext")
            system_prompt = (
                "You are the knowledge.update final entity context graph reasoner. "
                "Given existing entity context and focused markdown, propose minimal updates/additions to entity "
                "properties and block tree. Amending existing blocks should be rare. "
                "Return strict JSON only with entity and blocks."
            )

        compiled_agent = create_agent(
            model=ModelProviderChatModel(
                model=model_name,
                base_url=settings.model_provider_base_url,
                timeout=settings.knowledge_update_model_provider_timeout_seconds,
            ),
            tools=[],
            system_prompt=system_prompt,
            response_format=build_strict_response_format(schema),
        )
        prompt = json.dumps(
            {
                "entity_id": entity_id,
                "resolution_status": resolution_status,
                "extracted_entity": extracted,
                "focused_markdown": focused_markdown,
                "entity_type_property_context": type_context,
                "existing_entity_context": existing_entity_context,
            },
            ensure_ascii=False,
        )
        reply = await _call_with_retry(
            step_name="step eight",
            operation="final_entity_graph_agent.ainvoke",
            call=lambda: compiled_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}),
        )
        structured = reply.get("structured_response") if isinstance(reply, dict) else None
        if not isinstance(structured, dict):
            raise RuntimeError("knowledge.update step eight validation failed: missing structured_response")
        normalized = _normalize_step_eight_structured_response(structured, resolved)
        final_graphs.append(_validate_model("step eight", FinalEntityContextGraph, normalized))

    return final_graphs


def _to_property_value_dict(key: str, value: object) -> dict[str, object] | None:
    if isinstance(value, bool):
        return {"key": key, "bool_value": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"key": key, "int_value": value}
    if isinstance(value, float):
        return {"key": key, "float_value": value}
    if isinstance(value, str):
        return {"key": key, "string_value": value}
    if isinstance(value, (list, dict)):
        return {"key": key, "json_value": json.dumps(value, ensure_ascii=False)}
    return None


def _build_step_nine_merge_graph_delta(
    payload: KnowledgeUpdatePayload,
    step_zero_graph_delta: dict[str, object],
    step_two_extraction: EntityExtractionResult,
    step_seven_relationships: list[MatchedRelationship],
    step_eight_final_entity_context_graphs: list[FinalEntityContextGraph],
) -> dict[str, object]:
    merged = {
        "universes": list(step_zero_graph_delta.get("universes", []) or []),
        "entities": list(step_zero_graph_delta.get("entities", []) or []),
        "blocks": list(step_zero_graph_delta.get("blocks", []) or []),
        "edges": list(step_zero_graph_delta.get("edges", []) or []),
    }

    universe_id_by_name: dict[str, str] = {}
    for universe in step_two_extraction.extracted_universes:
        universe_name = universe.name
        if not universe_name:
            raise RuntimeError("knowledge.update step nine validation failed: extracted universe missing name")
        universe_id = str(uuid4())
        universe_id_by_name[universe_name] = universe_id
        merged["universes"].append(
            {
                "id": universe_id,
                "name": universe_name,
                "user_id": payload.requested_by_user_id,
                "visibility": "PRIVATE",
            }
        )

    for item in step_eight_final_entity_context_graphs:
        entity_payload = item.entity
        entity_id = entity_payload.get("entity_id")
        node_type = entity_payload.get("node_type")
        if not isinstance(entity_id, str) or not isinstance(node_type, str):
            raise RuntimeError("knowledge.update step nine validation failed: final entity payload missing entity_id/node_type")

        universe_id = entity_payload.get("universe_id")
        if not isinstance(universe_id, str):
            universe_name = entity_payload.get("universe_name")
            if isinstance(universe_name, str):
                universe_id = universe_id_by_name.get(universe_name)

        properties: list[dict[str, object]] = []
        for key, value in entity_payload.items():
            if key in {"entity_id", "node_type", "universe_id", "universe_name"}:
                continue
            property_value = _to_property_value_dict(key, value)
            if property_value is not None:
                properties.append(property_value)

        entity_node: dict[str, object] = {
            "id": entity_id,
            "type_id": node_type,
            "user_id": payload.requested_by_user_id,
            "visibility": "PRIVATE",
            "properties": properties,
        }
        if isinstance(universe_id, str) and universe_id:
            entity_node["universe_id"] = universe_id
        merged["entities"].append(entity_node)

        blocks = item.blocks

        id_map: dict[str, str] = {}
        for block in blocks:
            raw_id = block.block_id
            if not raw_id:
                raise RuntimeError(f"knowledge.update step nine validation failed: entity {entity_id} has block without block_id")
            if raw_id.startswith("NEW_BLOCK_"):
                id_map[raw_id] = str(uuid4())
            else:
                id_map[raw_id] = raw_id

        has_root = False
        for block in blocks:
            raw_id = block.block_id
            if raw_id not in id_map:
                raise RuntimeError(f"knowledge.update step nine validation failed: entity {entity_id} references unknown block_id")
            block_id = id_map[raw_id]
            text = block.text
            merged["blocks"].append(
                {
                    "id": block_id,
                    "type_id": "node.block",
                    "user_id": payload.requested_by_user_id,
                    "visibility": "PRIVATE",
                    "properties": [{"key": "text", "string_value": text}],
                }
            )
            parent_raw = block.parent_block_id
            parent_id = id_map.get(parent_raw) if isinstance(parent_raw, str) else None
            if parent_id:
                merged["edges"].append(
                    {
                        "from_id": parent_id,
                        "to_id": block_id,
                        "edge_type": "SUMMARIZES",
                        "user_id": payload.requested_by_user_id,
                        "visibility": "PRIVATE",
                    }
                )
            else:
                has_root = True
                merged["edges"].append(
                    {
                        "from_id": entity_id,
                        "to_id": block_id,
                        "edge_type": "DESCRIBED_BY",
                        "user_id": payload.requested_by_user_id,
                        "visibility": "PRIVATE",
                    }
                )
        if not has_root:
            logger.warning("knowledge.update step nine entity has no root block", extra={"entity_id": entity_id})

    for relationship in step_seven_relationships:
        from_id = relationship.from_entity_id
        to_id = relationship.to_entity_id
        edge_type = relationship.edge_type
        confidence = relationship.confidence
        merged["edges"].append(
            {
                "from_id": from_id,
                "to_id": to_id,
                "edge_type": edge_type,
                "user_id": payload.requested_by_user_id,
                "visibility": "PRIVATE",
                "properties": [
                    {"key": "confidence", "float_value": float(confidence)},
                    {"key": "status", "string_value": "asserted"},
                ],
            }
        )

    logger.info(
        "knowledge.update step nine merged graph delta",
        extra={
            "universes": len(merged["universes"]),
            "entities": len(merged["entities"]),
            "blocks": len(merged["blocks"]),
            "edges": len(merged["edges"]),
        },
    )
    return merged


def _build_step_ten_mentions_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mentions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "block_id": {"type": "string", "minLength": 1},
                        "entity_id": {"type": "string", "minLength": 1},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["block_id", "entity_id", "confidence"],
                },
            }
        },
        "required": ["mentions"],
    }


async def _run_step_ten_finalize_graph_delta(
    merged_graph_delta: dict[str, object],
    settings: Settings,
    requesting_user_id: str,
) -> dict[str, object]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel, build_strict_response_format

    blocks = [
        {
            "block_id": block.get("id"),
            "text": next((p.get("string_value") for p in (block.get("properties") or []) if isinstance(p, dict) and p.get("key") == "text"), ""),
        }
        for block in (merged_graph_delta.get("blocks") or [])
        if isinstance(block, dict)
    ]
    entities = [
        {
            "entity_id": entity.get("id"),
            "name": next((p.get("string_value") for p in (entity.get("properties") or []) if isinstance(p, dict) and p.get("key") == "name"), ""),
        }
        for entity in (merged_graph_delta.get("entities") or [])
        if isinstance(entity, dict)
    ]
    valid_block_ids = {item["block_id"] for item in blocks if isinstance(item.get("block_id"), str)}
    valid_entity_ids = {item["entity_id"] for item in entities if isinstance(item.get("entity_id"), str)}

    agent = create_agent(
        model=ModelProviderChatModel(
            model="worker",
            base_url=settings.model_provider_base_url,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update graph finalizer worker. "
            "Identify which blocks mention which entities. Return strict JSON only."
        ),
        response_format=build_strict_response_format(_StepTenMentionsResult),
    )
    prompt = json.dumps({"blocks": blocks, "entities": entities}, ensure_ascii=False)
    reply = await _call_with_retry(
        step_name="step ten",
        operation="graph_finalizer_agent.ainvoke",
        call=lambda: agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}),
    )
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("knowledge.update step ten validation failed: missing structured_response")
    mentions = _validate_model("step ten", _StepTenMentionsResult, structured).mentions

    mentions_edges: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    skipped_invalid = 0
    for mention in mentions:
        block_id = mention.block_id
        entity_id = mention.entity_id
        confidence = mention.confidence
        if block_id not in valid_block_ids:
            skipped_invalid += 1
            continue
        if entity_id not in valid_entity_ids:
            skipped_invalid += 1
            continue
        key = (block_id, entity_id)
        if key in seen:
            skipped_invalid += 1
            continue
        seen.add(key)
        mentions_edges.append(
            {
                "from_id": block_id,
                "to_id": entity_id,
                "edge_type": "MENTIONS",
                "user_id": requesting_user_id,
                "visibility": "PRIVATE",
                "properties": [
                    {"key": "confidence", "float_value": float(confidence)},
                    {"key": "status", "string_value": "asserted"},
                ],
            }
        )

    if skipped_invalid:
        logger.warning("knowledge.update step ten skipped invalid mentions", extra={"skipped": skipped_invalid})

    merged_graph_delta["edges"] = [*(merged_graph_delta.get("edges", []) or []), *mentions_edges]
    logger.info(
        "knowledge.update step ten finalized graph delta",
        extra={"mentions_edges_added": len(mentions_edges), "total_edges": len(merged_graph_delta.get("edges", []) or [])},
    )
    return merged_graph_delta


async def run(job: JobEnvelope) -> None:
    """Run knowledge.update worker steps."""

    settings = get_settings()
    target = settings.knowledge_interface_grpc_target
    payload = KnowledgeUpdatePayload.model_validate(job.payload)

    async with grpc.aio.insecure_channel(target) as channel:
        try:
            await asyncio.wait_for(
                channel.channel_ready(),
                timeout=settings.knowledge_interface_connect_timeout_seconds,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                "knowledge-interface connection timed out "
                f"for target '{target}' after "
                f"{settings.knowledge_interface_connect_timeout_seconds}s"
            ) from exc

        step_zero_graph_delta = await _build_upsert_graph_delta_step_one(channel, payload)
        _validate_upsert_graph_delta_payload("step zero", step_zero_graph_delta)
        step_one_markdown_document = _step_two_store_batch_document(payload)
        step_two_extraction = await _run_step_two_entity_extraction(
            channel,
            payload,
            step_one_markdown_document,
            settings,
        )
        step_three_candidate_matching = await _run_step_three_entity_candidate_matching(
            channel,
            payload,
            step_two_extraction,
        )
        step_four_entity_contexts = await _run_step_four_create_entity_contexts(
            step_two_extraction,
            step_one_markdown_document,
            settings,
        )
        step_five_resolved_entities = await _run_step_five_detailed_comparison(
            channel,
            payload,
            step_three_candidate_matching,
            step_four_entity_contexts,
            settings,
        )
        step_six_entity_pairs = await _run_step_six_relationship_extraction(
            step_five_resolved_entities,
            step_one_markdown_document,
            settings,
        )
        step_seven_relationships = await _run_step_seven_match_relationship_type_and_score(
            channel,
            payload,
            step_five_resolved_entities,
            step_four_entity_contexts,
            step_six_entity_pairs,
            settings,
        )
        step_eight_final_entity_context_graphs = await _run_step_eight_build_final_entity_context_graphs(
            channel,
            payload,
            step_five_resolved_entities,
            step_four_entity_contexts,
            settings,
        )
        step_nine_merged_graph_delta = _build_step_nine_merge_graph_delta(
            payload,
            step_zero_graph_delta,
            step_two_extraction,
            step_seven_relationships,
            step_eight_final_entity_context_graphs,
        )
        _validate_upsert_graph_delta_payload("step nine", step_nine_merged_graph_delta)
        step_ten_final_graph_delta = await _run_step_ten_finalize_graph_delta(
            step_nine_merged_graph_delta,
            settings,
            payload.requested_by_user_id,
        )

        upsert_graph_delta = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/UpsertGraphDelta",
            request_serializer=knowledge_pb2.UpsertGraphDeltaRequest.SerializeToString,
            response_deserializer=knowledge_pb2.UpsertGraphDeltaReply.FromString,
        )
        upsert_request = _validate_upsert_graph_delta_payload("step ten", step_ten_final_graph_delta)
        upsert_reply = await _call_with_retry(
            step_name="step eleven",
            operation="UpsertGraphDelta",
            call=lambda: upsert_graph_delta(upsert_request),
        )
        logger.info(
            "knowledge.update step eleven upserted final graph delta",
            extra={
                "entities_upserted": upsert_reply.entities_upserted,
                "blocks_upserted": upsert_reply.blocks_upserted,
                "edges_upserted": upsert_reply.edges_upserted,
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run knowledge.update worker job")
    parser.add_argument("--job-envelope", required=True, help="Serialized JobEnvelope JSON payload")
    args = parser.parse_args()

    job = JobEnvelope.model_validate_json(args.job_envelope)

    try:
        asyncio.run(run(job))
    except Exception as exc:  # noqa: BLE001
        print(_format_exception_for_stderr(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
