from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from uuid import uuid5, NAMESPACE_URL

import grpc
from google.protobuf.json_format import MessageToDict

from app.contracts import JobEnvelope, KnowledgeUpdatePayload
from app.services.grpc import knowledge_pb2
from app.settings import get_settings

logger = logging.getLogger(__name__)


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


def _step_two_placeholder_log(request_body: dict[str, object]) -> None:
    logger.info("knowledge.update step two placeholder: %s", request_body)


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

        step_one_request_body = await _build_upsert_graph_delta_step_one(channel, payload)
        _step_two_placeholder_log(step_one_request_body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run knowledge.update worker job")
    parser.add_argument("--job-envelope", required=True, help="Serialized JobEnvelope JSON payload")
    args = parser.parse_args()

    job = JobEnvelope.model_validate_json(args.job_envelope)

    try:
        asyncio.run(run(job))
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
