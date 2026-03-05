from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import traceback
from uuid import NAMESPACE_URL, uuid5

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
        response_format={"type": "json_schema", "json_schema": _build_step_two_entity_extraction_json_schema()},
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


def _step_three_placeholder(extraction: dict[str, object]) -> None:
    logger.info(
        "knowledge.update step three placeholder reached",
        extra={
            "extracted_entities": len(extraction.get("extracted_entities", []) or []),
            "extracted_universes": len(extraction.get("extracted_universes", []) or []),
        },
    )


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
        _step_three_placeholder(step_two_extraction)

        upsert_graph_delta = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/UpsertGraphDelta",
            request_serializer=knowledge_pb2.UpsertGraphDeltaRequest.SerializeToString,
            response_deserializer=knowledge_pb2.UpsertGraphDeltaReply.FromString,
        )
        upsert_request = ParseDict(step_zero_graph_delta, knowledge_pb2.UpsertGraphDeltaRequest())
        upsert_reply = await upsert_graph_delta(upsert_request)
        logger.info(
            "knowledge.update step four upserted chat message graph delta",
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
