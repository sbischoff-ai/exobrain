from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import traceback
from uuid import NAMESPACE_URL, uuid4, uuid5

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict

from app.contracts import JobEnvelope, KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


_MATCH_DECISION_PATTERN = re.compile(r"^MATCH\((?P<entity_id>[^)]+)\)$")


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
    return MessageToDict(reply, preserving_proto_field_name=True)


async def _build_upsert_graph_delta_step_one(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
) -> dict[str, object]:
    get_user_init_graph = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetUserInitGraph",
        request_serializer=knowledge_pb2.GetUserInitGraphRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetUserInitGraphReply.FromString,
    )
    init_graph = await get_user_init_graph(
        knowledge_pb2.GetUserInitGraphRequest(
            user_id=payload.requested_by_user_id,
            user_name=payload.requested_by_user_id,
        )
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
    return "\n\n".join(
        [
            "You are the knowledge.update entity extraction worker.",
            (
                "Extract named entities from the markdown batch document and map each entity to the most specific "
                "knowledge node type using the schema context."
            ),
            (
                "Return strict JSON only: extracted_entities and extracted_universes. "
                "Do not include markdown, prose, or extra fields."
            ),
            (
                "Universe handling: if an entity is fictional and no matching universe exists in context, add an "
                "entry to extracted_universes and reference it from extracted_entities[].universe_id when possible."
            ),
            "Entity extraction schema context (JSON):\n" + json.dumps(entity_schema_context, sort_keys=True),
        ]
    )


async def _run_step_two_entity_extraction(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    markdown_document: str,
    settings: Settings,
) -> dict[str, object]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel

    get_entity_extraction_schema_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityExtractionSchemaContext",
        request_serializer=knowledge_pb2.GetEntityExtractionSchemaContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEntityExtractionSchemaContextReply.FromString,
    )
    context_reply = await get_entity_extraction_schema_context_rpc(
        knowledge_pb2.GetEntityExtractionSchemaContextRequest(
            user_id=payload.requested_by_user_id,
        )
    )
    context_dict = _message_to_dict(context_reply, rpc_name="GetEntityExtractionSchemaContext")

    compiled_agent = create_agent(
        model=ModelProviderChatModel(
            model=settings.knowledge_update_extraction_model,
            base_url=settings.model_provider_base_url,
            temperature=0,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=_build_step_two_entity_extraction_system_prompt(context_dict),
        response_format=_build_step_two_entity_extraction_json_schema(),
    )
    reply = await compiled_agent.ainvoke({"messages": [{"role": "user", "content": markdown_document}]})
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("knowledge.update step two agent returned no structured_response")

    entities = structured.get("extracted_entities")
    universes = structured.get("extracted_universes")
    if not isinstance(entities, list) or not isinstance(universes, list):
        raise RuntimeError("knowledge.update step two agent returned invalid extraction payload")
    return {
        "extracted_entities": [item for item in entities if isinstance(item, dict)],
        "extracted_universes": [item for item in universes if isinstance(item, dict)],
    }


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
    extraction: dict[str, object],
) -> list[dict[str, object]]:
    find_candidates_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/FindEntityCandidates",
        request_serializer=knowledge_pb2.FindEntityCandidatesRequest.SerializeToString,
        response_deserializer=knowledge_pb2.FindEntityCandidatesReply.FromString,
    )

    results: list[dict[str, object]] = []
    extracted_entities = extraction.get("extracted_entities", []) or []
    for index, extracted_entity in enumerate(extracted_entities):
        if not isinstance(extracted_entity, dict):
            continue
        aliases = extracted_entity.get("aliases")
        alias_names = [alias for alias in aliases if isinstance(alias, str)] if isinstance(aliases, list) else []
        entity_name = extracted_entity.get("name") if isinstance(extracted_entity.get("name"), str) else ""
        names = [name for name in [entity_name, *alias_names] if name]

        node_type = extracted_entity.get("node_type") if isinstance(extracted_entity.get("node_type"), str) else ""
        short_description = (
            extracted_entity.get("short_description")
            if isinstance(extracted_entity.get("short_description"), str)
            else ""
        )

        candidates_reply = await find_candidates_rpc(
            knowledge_pb2.FindEntityCandidatesRequest(
                names=names,
                potential_type_ids=[node_type] if node_type else [],
                short_description=short_description,
                user_id=payload.requested_by_user_id,
            )
        )
        candidate_dicts = _message_to_dict(candidates_reply, rpc_name="FindEntityCandidates").get("candidates", [])
        classification = _classify_candidate_matches(
            [candidate for candidate in candidate_dicts if isinstance(candidate, dict)]
        )
        results.append(
            {
                "entity_index": index,
                "extracted_entity": extracted_entity,
                "candidate_matches": candidate_dicts,
                **classification,
            }
        )

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
    extraction: dict[str, object],
    markdown_document: str,
    settings: Settings,
) -> list[str]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel

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
            temperature=0,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=system_prompt,
        response_format=_build_step_four_entity_context_schema(),
    )

    documents: list[str] = []
    for extracted_entity in extraction.get("extracted_entities", []) or []:
        if not isinstance(extracted_entity, dict):
            continue
        prompt = json.dumps(
            {
                "entity": extracted_entity,
                "markdown_batch_document": markdown_document,
            },
            ensure_ascii=False,
        )
        reply = await compiled_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        structured = reply.get("structured_response") if isinstance(reply, dict) else None
        if not isinstance(structured, dict) or not isinstance(structured.get("focused_markdown"), str):
            raise RuntimeError("knowledge.update step four reasoner returned invalid focused_markdown")
        documents.append(structured["focused_markdown"])
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
    candidate_matching: list[dict[str, object]],
    entity_context_documents: list[str],
    settings: Settings,
) -> list[dict[str, object]]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel

    get_entity_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityContext",
        request_serializer=knowledge_pb2.GetEntityContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEntityContextReply.FromString,
    )

    comparison_agent = create_agent(
        model=ModelProviderChatModel(
            model="worker",
            base_url=settings.model_provider_base_url,
            temperature=0,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update detailed comparison worker. "
            "Compare extracted entity context markdown against candidate entity contexts. "
            "Return strict JSON only with decision as MATCH({entity_id}) or NEW_ENTITY."
        ),
        response_format=_build_step_five_comparison_schema(),
    )

    resolved_entities: list[dict[str, object]] = []
    for match_item in candidate_matching:
        extracted_entity = match_item.get("extracted_entity")
        if not isinstance(extracted_entity, dict):
            continue

        status = match_item.get("status")
        resolution_status = "new_entity"
        resolved_entity_id: str
        if status == "matched" and isinstance(match_item.get("matched_entity_id"), str):
            resolved_entity_id = match_item["matched_entity_id"]
            resolution_status = "matched"
        elif status == "needs_detailed_comparison":
            entity_index = int(match_item.get("entity_index", -1))
            focused_markdown = entity_context_documents[entity_index] if 0 <= entity_index < len(entity_context_documents) else ""
            candidate_ids = [
                item for item in (match_item.get("candidate_entity_ids") or []) if isinstance(item, str)
            ]
            candidate_contexts: list[dict[str, object]] = []
            for candidate_id in candidate_ids:
                context_reply = await get_entity_context_rpc(
                    knowledge_pb2.GetEntityContextRequest(
                        entity_id=candidate_id,
                        user_id=payload.requested_by_user_id,
                        max_block_level=1,
                    )
                )
                candidate_contexts.append(_message_to_dict(context_reply, rpc_name="GetEntityContext"))

            prompt = json.dumps(
                {
                    "extracted_entity": extracted_entity,
                    "extracted_entity_markdown": focused_markdown,
                    "candidate_contexts": candidate_contexts,
                },
                ensure_ascii=False,
            )
            reply = await comparison_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
            structured = reply.get("structured_response") if isinstance(reply, dict) else None
            decision = structured.get("decision") if isinstance(structured, dict) else None
            matched_entity_id = _extract_matched_entity_id(decision) if isinstance(decision, str) else None
            if matched_entity_id and matched_entity_id in candidate_ids:
                resolved_entity_id = matched_entity_id
                resolution_status = "matched"
            else:
                resolved_entity_id = str(uuid4())
        else:
            resolved_entity_id = str(uuid4())

        resolved_entities.append(
            {
                "entity_index": match_item.get("entity_index"),
                "extracted_entity": extracted_entity,
                "resolved_entity_id": resolved_entity_id,
                "resolution_status": resolution_status,
            }
        )

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
    entity_pairs: list[dict[str, object]],
    valid_entity_ids: set[str],
) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pair in entity_pairs:
        if not isinstance(pair, dict):
            continue
        entity_id_1 = pair.get("entity_id_1")
        entity_id_2 = pair.get("entity_id_2")
        if not isinstance(entity_id_1, str) or not isinstance(entity_id_2, str):
            continue
        if entity_id_1 == entity_id_2:
            continue
        if entity_id_1 not in valid_entity_ids or entity_id_2 not in valid_entity_ids:
            continue
        normalized = tuple(sorted((entity_id_1, entity_id_2)))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append({"entity_id_1": entity_id_1, "entity_id_2": entity_id_2})
    return deduped


async def _run_step_six_relationship_extraction(
    resolved_entities: list[dict[str, object]],
    markdown_document: str,
    settings: Settings,
) -> list[dict[str, str]]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel

    extracted_entities_with_ids = [
        {
            "entity_id": item.get("resolved_entity_id"),
            "name": (item.get("extracted_entity") or {}).get("name") if isinstance(item.get("extracted_entity"), dict) else None,
            "node_type": (item.get("extracted_entity") or {}).get("node_type") if isinstance(item.get("extracted_entity"), dict) else None,
        }
        for item in resolved_entities
        if isinstance(item, dict) and isinstance(item.get("resolved_entity_id"), str)
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
            temperature=0,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update relationship extraction worker. "
            "Identify entity pairs that are related in the markdown batch document. "
            "Return strict JSON only with entity_pairs."
        ),
        response_format=_build_step_six_relationship_extraction_schema(),
    )

    prompt = json.dumps(
        {
            "entities": extracted_entities_with_ids,
            "markdown_batch_document": markdown_document,
        },
        ensure_ascii=False,
    )
    reply = await relationship_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    entity_pairs = structured.get("entity_pairs") if isinstance(structured, dict) else None
    if not isinstance(entity_pairs, list):
        raise RuntimeError("knowledge.update step six relationship extraction returned invalid entity_pairs")

    return _deduplicate_entity_pairs(entity_pairs, valid_entity_ids)


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
    resolved_entities: list[dict[str, object]],
    entity_context_documents: list[str],
    entity_pairs: list[dict[str, str]],
    settings: Settings,
) -> list[dict[str, object]]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel

    get_edge_extraction_schema_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEdgeExtractionSchemaContext",
        request_serializer=knowledge_pb2.GetEdgeExtractionSchemaContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEdgeExtractionSchemaContextReply.FromString,
    )

    resolution_by_id: dict[str, dict[str, object]] = {}
    for item in resolved_entities:
        if not isinstance(item, dict):
            continue
        entity_id = item.get("resolved_entity_id")
        if not isinstance(entity_id, str):
            continue
        entity_index = int(item.get("entity_index", -1)) if isinstance(item.get("entity_index"), int) else -1
        focused_markdown = entity_context_documents[entity_index] if 0 <= entity_index < len(entity_context_documents) else ""
        resolution_by_id[entity_id] = {
            "entity_id": entity_id,
            "node_type": (item.get("extracted_entity") or {}).get("node_type") if isinstance(item.get("extracted_entity"), dict) else "",
            "name": (item.get("extracted_entity") or {}).get("name") if isinstance(item.get("extracted_entity"), dict) else "",
            "focused_markdown": focused_markdown,
        }

    relationship_match_agent = create_agent(
        model=ModelProviderChatModel(
            model="worker",
            base_url=settings.model_provider_base_url,
            temperature=0,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update relationship matching worker. "
            "Given two entities, their focused contexts, and allowed edge schema context, return the best "
            "relationship direction, edge type, and confidence between 0 and 1. "
            "Return strict JSON only."
        ),
        response_format=_build_step_seven_relationship_match_schema(),
    )

    matched_relationships: list[dict[str, object]] = []
    for pair in entity_pairs:
        entity_id_1 = pair.get("entity_id_1")
        entity_id_2 = pair.get("entity_id_2")
        if entity_id_1 not in resolution_by_id or entity_id_2 not in resolution_by_id:
            continue

        entity_1 = resolution_by_id[entity_id_1]
        entity_2 = resolution_by_id[entity_id_2]
        node_type_1 = entity_1.get("node_type") if isinstance(entity_1.get("node_type"), str) else ""
        node_type_2 = entity_2.get("node_type") if isinstance(entity_2.get("node_type"), str) else ""
        if not node_type_1 or not node_type_2:
            continue

        edge_context_reply = await get_edge_extraction_schema_context_rpc(
            knowledge_pb2.GetEdgeExtractionSchemaContextRequest(
                first_entity_type=node_type_1,
                second_entity_type=node_type_2,
                user_id=payload.requested_by_user_id,
            )
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

        reply = await relationship_match_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        structured = reply.get("structured_response") if isinstance(reply, dict) else None
        if not isinstance(structured, dict):
            raise RuntimeError("knowledge.update step seven returned invalid relationship match output")

        from_entity_id = structured.get("from_entity_id")
        to_entity_id = structured.get("to_entity_id")
        edge_type = structured.get("edge_type")
        confidence = structured.get("confidence")
        if not isinstance(from_entity_id, str) or not isinstance(to_entity_id, str):
            continue
        if {from_entity_id, to_entity_id} != {entity_id_1, entity_id_2}:
            continue
        if not isinstance(edge_type, str) or not isinstance(confidence, (float, int)):
            continue

        matched_relationships.append(
            {
                "from_entity_id": from_entity_id,
                "to_entity_id": to_entity_id,
                "edge_type": edge_type,
                "confidence": float(confidence),
            }
        )

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


async def _run_step_eight_build_final_entity_context_graphs(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    resolved_entities: list[dict[str, object]],
    entity_context_documents: list[str],
    settings: Settings,
) -> list[dict[str, object]]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel

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
    final_graphs: list[dict[str, object]] = []

    for resolved in resolved_entities:
        if not isinstance(resolved, dict):
            continue
        extracted = resolved.get("extracted_entity")
        if not isinstance(extracted, dict):
            continue
        entity_id = resolved.get("resolved_entity_id")
        if not isinstance(entity_id, str):
            continue
        node_type = extracted.get("node_type") if isinstance(extracted.get("node_type"), str) else ""
        if not node_type:
            continue

        type_context_reply = await get_entity_type_property_context_rpc(
            knowledge_pb2.GetEntityTypePropertyContextRequest(
                type_id=node_type,
                user_id=payload.requested_by_user_id,
                include_inherited=True,
            )
        )
        type_context = _message_to_dict(type_context_reply, rpc_name="GetEntityTypePropertyContext")

        resolution_status = resolved.get("resolution_status")
        entity_index = resolved.get("entity_index") if isinstance(resolved.get("entity_index"), int) else -1
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
            context_reply = await get_entity_context_rpc(
                knowledge_pb2.GetEntityContextRequest(
                    entity_id=entity_id,
                    user_id=payload.requested_by_user_id,
                    max_block_level=2,
                )
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
                temperature=0,
                timeout=settings.knowledge_update_model_provider_timeout_seconds,
            ),
            tools=[],
            system_prompt=system_prompt,
            response_format=schema,
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
        reply = await compiled_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        structured = reply.get("structured_response") if isinstance(reply, dict) else None
        if not isinstance(structured, dict):
            raise RuntimeError("knowledge.update step eight final context graph returned invalid payload")
        final_graphs.append(structured)

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
    step_two_extraction: dict[str, object],
    step_seven_relationships: list[dict[str, object]],
    step_eight_final_entity_context_graphs: list[dict[str, object]],
) -> dict[str, object]:
    merged = {
        "universes": list(step_zero_graph_delta.get("universes", []) or []),
        "entities": list(step_zero_graph_delta.get("entities", []) or []),
        "blocks": list(step_zero_graph_delta.get("blocks", []) or []),
        "edges": list(step_zero_graph_delta.get("edges", []) or []),
    }

    universe_id_by_name: dict[str, str] = {}
    for universe in step_two_extraction.get("extracted_universes", []) or []:
        if not isinstance(universe, dict):
            continue
        universe_name = universe.get("name")
        if not isinstance(universe_name, str) or not universe_name:
            continue
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
        if not isinstance(item, dict):
            continue
        entity_payload = item.get("entity")
        if not isinstance(entity_payload, dict):
            continue
        entity_id = entity_payload.get("entity_id")
        node_type = entity_payload.get("node_type")
        if not isinstance(entity_id, str) or not isinstance(node_type, str):
            continue

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

        blocks = item.get("blocks")
        if not isinstance(blocks, list):
            continue

        id_map: dict[str, str] = {}
        for block in blocks:
            if not isinstance(block, dict):
                continue
            raw_id = block.get("block_id")
            if not isinstance(raw_id, str) or not raw_id:
                continue
            if raw_id.startswith("NEW_BLOCK_"):
                id_map[raw_id] = str(uuid4())
            else:
                id_map[raw_id] = raw_id

        has_root = False
        for block in blocks:
            if not isinstance(block, dict):
                continue
            raw_id = block.get("block_id")
            if not isinstance(raw_id, str) or raw_id not in id_map:
                continue
            block_id = id_map[raw_id]
            text = block.get("text") if isinstance(block.get("text"), str) else ""
            merged["blocks"].append(
                {
                    "id": block_id,
                    "type_id": "node.block",
                    "user_id": payload.requested_by_user_id,
                    "visibility": "PRIVATE",
                    "properties": [{"key": "text", "string_value": text}],
                }
            )
            parent_raw = block.get("parent_block_id")
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
        if not isinstance(relationship, dict):
            continue
        from_id = relationship.get("from_entity_id")
        to_id = relationship.get("to_entity_id")
        edge_type = relationship.get("edge_type")
        confidence = relationship.get("confidence")
        if not isinstance(from_id, str) or not isinstance(to_id, str) or not isinstance(edge_type, str):
            continue
        if not isinstance(confidence, (int, float)):
            continue
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
    from app.services.model_provider_chat_model import ModelProviderChatModel

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
            temperature=0,
            timeout=settings.knowledge_update_model_provider_timeout_seconds,
        ),
        tools=[],
        system_prompt=(
            "You are the knowledge.update graph finalizer worker. "
            "Identify which blocks mention which entities. Return strict JSON only."
        ),
        response_format=_build_step_ten_mentions_schema(),
    )
    prompt = json.dumps({"blocks": blocks, "entities": entities}, ensure_ascii=False)
    reply = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    mentions = structured.get("mentions") if isinstance(structured, dict) else None
    if not isinstance(mentions, list):
        raise RuntimeError("knowledge.update step ten returned invalid mentions output")

    mentions_edges: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for mention in mentions:
        if not isinstance(mention, dict):
            continue
        block_id = mention.get("block_id")
        entity_id = mention.get("entity_id")
        confidence = mention.get("confidence")
        if not isinstance(block_id, str) or block_id not in valid_block_ids:
            continue
        if not isinstance(entity_id, str) or entity_id not in valid_entity_ids:
            continue
        if not isinstance(confidence, (int, float)):
            continue
        key = (block_id, entity_id)
        if key in seen:
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
        upsert_request = ParseDict(step_ten_final_graph_delta, knowledge_pb2.UpsertGraphDeltaRequest())
        upsert_reply = await upsert_graph_delta(upsert_request)
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
