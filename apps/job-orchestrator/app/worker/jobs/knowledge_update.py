from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import traceback
from uuid import uuid5, NAMESPACE_URL

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict

from app.contracts import JobEnvelope, KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _format_exception_for_stderr(exc: BaseException) -> str:
    return "".join(traceback.format_exception(exc)).rstrip()


def _message_entity_name(journal_reference: str, sequence_number: int) -> str:
    return f"{journal_reference} message {sequence_number}"


def _require_created_at(created_at: str | None, sequence_number: int) -> str:
    if created_at:
        return created_at
    raise ValueError(f"knowledge.update message at sequence {sequence_number} missing created_at")


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
                    knowledge_pb2.PropertyValue(key="name", string_value=_message_entity_name(payload.journal_reference, sequence_number)),
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

    return MessageToDict(request, preserving_proto_field_name=True)


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
    logger.info("knowledge.update step two batch document:\n%s", batch_document)
    return batch_document


def _merge_upsert_graph_delta_requests(
    left: dict[str, object],
    right: dict[str, object],
) -> dict[str, object]:
    return {
        "universes": [*(left.get("universes", []) or []), *(right.get("universes", []) or [])],
        "entities": [*(left.get("entities", []) or []), *(right.get("entities", []) or [])],
        "blocks": [*(left.get("blocks", []) or []), *(right.get("blocks", []) or [])],
        "edges": [*(left.get("edges", []) or []), *(right.get("edges", []) or [])],
    }


def _find_property_value(node: dict[str, object], key: str) -> str:
    properties = node.get("properties")
    if not isinstance(properties, list):
        return ""
    for prop in properties:
        if not isinstance(prop, dict) or prop.get("key") != key:
            continue
        for value_key in ("string_value", "datetime_value", "json_value"):
            value = prop.get(value_key)
            if isinstance(value, str):
                return value
    return ""


def _build_step_four_router_prompt(
    step_one_graph_delta: dict[str, object],
    step_three_graph_delta: dict[str, object],
) -> str:
    step_one_blocks = [
        {
            "block_id": block.get("id", ""),
            "text": _find_property_value(block, "text"),
        }
        for block in (step_one_graph_delta.get("blocks", []) or [])
        if isinstance(block, dict)
    ]
    step_three_entities = [
        {
            "entity_id": entity.get("id", ""),
            "type_id": entity.get("type_id", ""),
            "name": _find_property_value(entity, "name"),
            "described_by_text": _find_property_value(entity, "described_by_text"),
        }
        for entity in (step_three_graph_delta.get("entities", []) or [])
        if isinstance(entity, dict)
    ]

    return json.dumps(
        {
            "chat_blocks": step_one_blocks,
            "extracted_entities": step_three_entities,
            "chat_graph_delta": step_one_graph_delta,
            "extracted_graph_delta": step_three_graph_delta,
        },
        ensure_ascii=False,
    )


def _build_step_four_router_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "block_id": {"type": "string"},
                        "entity_id": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                    "required": ["block_id", "entity_id", "confidence"],
                },
            }
        },
        "required": ["mappings"],
    }


async def _run_step_four_router_agent(
    step_one_graph_delta: dict[str, object],
    step_three_graph_delta: dict[str, object],
    settings: Settings,
) -> list[dict[str, object]]:
    from langchain.agents import create_agent
    from app.services.model_provider_chat_model import ModelProviderChatModel

    model = ModelProviderChatModel(
        model="router",
        base_url=settings.model_provider_base_url,
        temperature=0,
    )
    response_schema = _build_step_four_router_json_schema()
    prompt = _build_step_four_router_prompt(step_one_graph_delta, step_three_graph_delta)
    compiled_agent = create_agent(
        model=model,
        tools=[],
        system_prompt=(
            "You map chat message blocks to extracted entities. "
            "Return only high-confidence links for MENTIONS edges with calibrated confidence scores in [0,1]."
        ),
        response_format={"type": "json_schema", "json_schema": response_schema},
    )
    reply = await compiled_agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("knowledge.update step four router agent returned no structured_response")
    mappings = structured.get("mappings")
    if not isinstance(mappings, list):
        raise RuntimeError("knowledge.update step four router agent returned invalid mappings")
    return [item for item in mappings if isinstance(item, dict)]


def _append_mentions_edges(
    merged_graph_delta: dict[str, object],
    step_one_graph_delta: dict[str, object],
    step_three_graph_delta: dict[str, object],
    mappings: list[dict[str, object]],
    user_id: str,
) -> None:
    block_ids = {
        str(block.get("id"))
        for block in (step_one_graph_delta.get("blocks", []) or [])
        if isinstance(block, dict) and block.get("id")
    }
    entity_ids = {
        str(entity.get("id"))
        for entity in (step_three_graph_delta.get("entities", []) or [])
        if isinstance(entity, dict) and entity.get("id")
    }

    mentions_edges: list[dict[str, object]] = []
    for mapping in mappings:
        block_id = mapping.get("block_id")
        entity_id = mapping.get("entity_id")
        confidence = mapping.get("confidence")
        if not isinstance(block_id, str) or block_id not in block_ids:
            continue
        if not isinstance(entity_id, str) or entity_id not in entity_ids:
            continue
        if not isinstance(confidence, (float, int)):
            continue
        mentions_edges.append(
            {
                "from_id": block_id,
                "to_id": entity_id,
                "edge_type": "MENTIONS",
                "user_id": user_id,
                "visibility": "PRIVATE",
                "properties": [{"key": "confidence", "float_value": float(confidence)}],
            }
        )

    merged_graph_delta["edges"] = [*(merged_graph_delta.get("edges", []) or []), *mentions_edges]


def _build_step_three_system_prompt(
    entity_extraction_schema_context: dict[str, object],
    upsert_graph_delta_json_schema: str,
) -> str:
    return "\n\n".join(
        [
            "You are the knowledge.update extraction architect.",
            (
                "Extract entities, relationship edges, universes, and evidence blocks from chat-markdown input. "
                "Output MUST validate against the provided JSON schema."
            ),
            (
                "Workflow: (1) use the provided entity extraction schema context to choose candidate entity "
                "types and universe usage; (2) deduplicate entities with find_entity_candidates and inspect "
                "matches with get_entity_context; (3) validate entity properties with "
                "get_entity_type_property_context; (4) for each candidate related entity pair, call "
                "get_edge_extraction_schema_context with "
                "source_entity_type_id and target_entity_type_id before creating edges; "
                "(5) emit only edges allowed by the returned edge context and direction."
            ),
            (
                "Graph model notes: Block nodes contain markdown text and are connected with DESCRIBED_BY to up to "
                "one entity. Blocks can summarize additional blocks via SUMMARIZES edges, forming an entity-focused "
                "tree. Limit your output to block_level <= 2."
            ),
            (
                "Universe handling: detect fictional context when entities are not from the real world. Upsert "
                "Universe nodes as needed and set entity universe_id accordingly. Real-world entities should remain "
                "in the default Real World universe unless explicitly fictional."
            ),
            (
                "Relevance policy: prioritize entities relevant to the user from this conversation. Assistant "
                "suggestions must be ignored unless the user approved or confirmed them."
            ),
            "Entity extraction schema context (JSON):\n" + json.dumps(entity_extraction_schema_context, sort_keys=True),
            "Output JSON schema:\n" + upsert_graph_delta_json_schema,
        ]
    )


async def _run_step_three_extraction_agent(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    markdown_document: str,
    settings: Settings,
) -> dict[str, object]:
    from langchain.agents import create_agent
    from langchain_core.tools import tool
    from app.services.model_provider_chat_model import ModelProviderChatModel

    get_entity_extraction_schema_context_rpc = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityExtractionSchemaContext",
        request_serializer=knowledge_pb2.GetEntityExtractionSchemaContextRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetEntityExtractionSchemaContextReply.FromString,
    )
    get_upsert_graph_delta_json_schema = channel.unary_unary(
        "/exobrain.knowledge.v1.KnowledgeInterface/GetUpsertGraphDeltaJsonSchema",
        request_serializer=knowledge_pb2.GetUpsertGraphDeltaJsonSchemaRequest.SerializeToString,
        response_deserializer=knowledge_pb2.GetUpsertGraphDeltaJsonSchemaReply.FromString,
    )

    entity_schema_context_reply = await get_entity_extraction_schema_context_rpc(
        knowledge_pb2.GetEntityExtractionSchemaContextRequest(user_id=payload.requested_by_user_id)
    )
    entity_schema_context = MessageToDict(
        entity_schema_context_reply, preserving_proto_field_name=True
    )
    json_schema_reply = await get_upsert_graph_delta_json_schema(
        knowledge_pb2.GetUpsertGraphDeltaJsonSchemaRequest()
    )

    @tool
    async def get_edge_extraction_schema_context(
        source_entity_type_id: str,
        target_entity_type_id: str,
        include_inactive: bool = False,
    ) -> dict[str, object]:
        """Get edge rules/directions for one source-target entity type pair."""

        rpc = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/GetEdgeExtractionSchemaContext",
            request_serializer=knowledge_pb2.GetEdgeExtractionSchemaContextRequest.SerializeToString,
            response_deserializer=knowledge_pb2.GetEdgeExtractionSchemaContextReply.FromString,
        )
        reply = await rpc(
            knowledge_pb2.GetEdgeExtractionSchemaContextRequest(
                source_entity_type_id=source_entity_type_id,
                target_entity_type_id=target_entity_type_id,
                include_inactive=include_inactive,
                user_id=payload.requested_by_user_id,
            )
        )
        return MessageToDict(reply, preserving_proto_field_name=True)

    @tool
    async def find_entity_candidates(
        names: list[str],
        potential_type_ids: list[str] | None = None,
        short_description: str = "",
        limit: int = 10,
    ) -> dict[str, object]:
        """Find candidate entities already in graph for deduplication."""

        rpc = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/FindEntityCandidates",
            request_serializer=knowledge_pb2.FindEntityCandidatesRequest.SerializeToString,
            response_deserializer=knowledge_pb2.FindEntityCandidatesReply.FromString,
        )
        reply = await rpc(
            knowledge_pb2.FindEntityCandidatesRequest(
                names=names,
                potential_type_ids=potential_type_ids or [],
                short_description=short_description,
                user_id=payload.requested_by_user_id,
                limit=limit,
            )
        )
        return MessageToDict(reply, preserving_proto_field_name=True)

    @tool
    async def get_entity_context(entity_id: str, max_block_level: int = 2) -> dict[str, object]:
        """Get detailed context for one existing entity."""

        rpc = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityContext",
            request_serializer=knowledge_pb2.GetEntityContextRequest.SerializeToString,
            response_deserializer=knowledge_pb2.GetEntityContextReply.FromString,
        )
        reply = await rpc(
            knowledge_pb2.GetEntityContextRequest(
                entity_id=entity_id,
                user_id=payload.requested_by_user_id,
                max_block_level=max_block_level,
            )
        )
        return MessageToDict(reply, preserving_proto_field_name=True)

    @tool
    async def get_entity_type_property_context(type_id: str) -> dict[str, object]:
        """Inspect writable/readable property schema for an entity type."""

        rpc = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/GetEntityTypePropertyContext",
            request_serializer=knowledge_pb2.GetEntityTypePropertyContextRequest.SerializeToString,
            response_deserializer=knowledge_pb2.GetEntityTypePropertyContextReply.FromString,
        )
        reply = await rpc(
            knowledge_pb2.GetEntityTypePropertyContextRequest(
                type_id=type_id,
                user_id=payload.requested_by_user_id,
                include_inherited=True,
            )
        )
        return MessageToDict(reply, preserving_proto_field_name=True)

    system_prompt = _build_step_three_system_prompt(
        entity_extraction_schema_context=entity_schema_context,
        upsert_graph_delta_json_schema=json_schema_reply.json_schema,
    )

    model = ModelProviderChatModel(
        model=settings.knowledge_update_extraction_model,
        base_url=settings.model_provider_base_url,
        temperature=0,
    )

    compiled_agent = create_agent(
        model=model,
        tools=[
            get_edge_extraction_schema_context,
            find_entity_candidates,
            get_entity_context,
            get_entity_type_property_context,
        ],
        system_prompt=system_prompt,
        response_format={
            "type": "json_schema",
            "json_schema": json.loads(json_schema_reply.json_schema),
        },
    )

    reply = await compiled_agent.ainvoke({"messages": [{"role": "user", "content": markdown_document}]})
    structured = reply.get("structured_response") if isinstance(reply, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("knowledge.update step three agent returned no structured_response")
    return structured


async def _step_three_extract_graph_delta(
    channel: grpc.aio.Channel,
    payload: KnowledgeUpdatePayload,
    markdown_document: str,
    settings: Settings,
) -> dict[str, object]:
    graph_delta = await _run_step_three_extraction_agent(channel, payload, markdown_document, settings)
    logger.info(
        "knowledge.update step three extracted graph delta",
        extra={
            "entities": len(graph_delta.get("entities", []) or []),
            "blocks": len(graph_delta.get("blocks", []) or []),
            "edges": len(graph_delta.get("edges", []) or []),
            "universes": len(graph_delta.get("universes", []) or []),
        },
    )
    return graph_delta


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

        task_results: dict[str, dict[str, object] | str] = {}

        async def _task_one_step_one() -> None:
            task_results["step_one_graph_delta"] = await _build_upsert_graph_delta_step_one(channel, payload)

        async def _task_two_step_two_and_three() -> None:
            markdown_document = _step_two_store_batch_document(payload)
            task_results["step_two_markdown"] = markdown_document
            task_results["step_three_graph_delta"] = await _step_three_extract_graph_delta(
                channel,
                payload,
                markdown_document,
                settings,
            )

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(_task_one_step_one())
            task_group.create_task(_task_two_step_two_and_three())

        step_one_graph_delta = task_results["step_one_graph_delta"]
        step_three_graph_delta = task_results["step_three_graph_delta"]
        if not isinstance(step_one_graph_delta, dict) or not isinstance(step_three_graph_delta, dict):
            raise RuntimeError("knowledge.update missing task results for step four graph delta merge")

        merged_graph_delta = _merge_upsert_graph_delta_requests(step_one_graph_delta, step_three_graph_delta)
        mentions_mappings = await _run_step_four_router_agent(
            step_one_graph_delta,
            step_three_graph_delta,
            settings,
        )
        _append_mentions_edges(
            merged_graph_delta,
            step_one_graph_delta,
            step_three_graph_delta,
            mentions_mappings,
            payload.requested_by_user_id,
        )

        logger.info(
            "knowledge.update step four merged graph delta",
            extra={
                "entities": len(merged_graph_delta["entities"]),
                "blocks": len(merged_graph_delta["blocks"]),
                "edges": len(merged_graph_delta["edges"]),
                "universes": len(merged_graph_delta["universes"]),
                "mentions_edges_added": len(mentions_mappings),
            },
        )

        upsert_graph_delta = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/UpsertGraphDelta",
            request_serializer=knowledge_pb2.UpsertGraphDeltaRequest.SerializeToString,
            response_deserializer=knowledge_pb2.UpsertGraphDeltaReply.FromString,
        )
        upsert_request = ParseDict(merged_graph_delta, knowledge_pb2.UpsertGraphDeltaRequest())
        upsert_reply = await upsert_graph_delta(upsert_request)
        logger.info(
            "knowledge.update step five upserted merged graph delta",
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
