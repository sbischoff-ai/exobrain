from __future__ import annotations

import argparse
import asyncio
import sys

import grpc

from app.contracts import JobEnvelope, KnowledgeUpdatePayload
from app.settings import get_settings
from app.worker.jobs.knowledge_update import core
from app.worker.jobs.knowledge_update.schemas import validate_upsert_graph_delta_payload
from app.worker.jobs.knowledge_update.steps import (
    step01_graph_seed,
    step02_entity_extraction,
    step03_candidate_matching,
    step04_entity_context,
    step05_entity_resolution,
    step06_relationship_extraction,
    step07_relationship_match,
    step08_entity_graph,
    step09_merge_graph,
    step10_mentions,
)

KnowledgeUpdateStepError = core.KnowledgeUpdateStepError
_call_with_retry = core._call_with_retry
_build_batch_document = core._build_batch_document
_step_two_store_batch_document = core._step_two_store_batch_document
_format_exception_for_stderr = core._format_exception_for_stderr

_build_upsert_graph_delta_step_one = step01_graph_seed.run
_build_step_two_entity_extraction_json_schema = step02_entity_extraction.build_json_schema
_build_step_two_entity_extraction_system_prompt = step02_entity_extraction.build_system_prompt
_run_step_two_entity_extraction = step02_entity_extraction.run
_classify_candidate_matches = step03_candidate_matching.classify_candidate_matches
_run_step_three_entity_candidate_matching = step03_candidate_matching.run
_build_step_four_entity_context_schema = step04_entity_context.build_json_schema
_run_step_four_create_entity_contexts = step04_entity_context.run
_build_step_five_comparison_schema = step05_entity_resolution.build_json_schema
_extract_matched_entity_id = step05_entity_resolution.extract_matched_entity_id
_resolve_step_five_decision = core._resolve_step_five_decision
_run_step_five_detailed_comparison = step05_entity_resolution.run
_build_step_six_relationship_extraction_schema = step06_relationship_extraction.build_json_schema
_deduplicate_entity_pairs = step06_relationship_extraction.deduplicate_entity_pairs
_run_step_six_relationship_extraction = step06_relationship_extraction.run
_build_step_seven_relationship_match_schema = step07_relationship_match.build_json_schema
_build_edge_extraction_schema_context_request = core._build_edge_extraction_schema_context_request
_run_step_seven_match_relationship_type_and_score = step07_relationship_match.run
_build_step_eight_final_entity_context_graph_schema = step08_entity_graph.build_json_schema
_assert_step_eight_required_entity_fields = core._assert_step_eight_required_entity_fields
_run_step_eight_build_final_entity_context_graphs = step08_entity_graph.run
_build_step_nine_merge_graph_delta = step09_merge_graph.run
_build_step_ten_mentions_schema = step10_mentions.build_json_schema
_run_step_ten_finalize_graph_delta = step10_mentions.run
_validate_upsert_graph_delta_payload = validate_upsert_graph_delta_payload
_preflight_validate_graph_delta_entities = core._preflight_validate_graph_delta_entities


async def run(job: JobEnvelope) -> None:
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

        step_zero_graph_delta = await step01_graph_seed.run(channel, payload)
        validate_upsert_graph_delta_payload("step zero", step_zero_graph_delta)
        step_one_markdown_document = core._step_two_store_batch_document(payload)
        step_two_extraction = await step02_entity_extraction.run(channel, payload, step_one_markdown_document, settings)
        step_three_candidate_matching = await step03_candidate_matching.run(channel, payload, step_two_extraction)
        step_four_entity_contexts = await step04_entity_context.run(step_two_extraction, step_one_markdown_document, settings)
        step_five_resolved_entities = await step05_entity_resolution.run(
            channel,
            payload,
            step_three_candidate_matching,
            step_four_entity_contexts,
            settings,
        )
        step_six_entity_pairs = await step06_relationship_extraction.run(
            step_five_resolved_entities,
            step_one_markdown_document,
            settings,
        )
        step_seven_relationships = await step07_relationship_match.run(
            channel,
            payload,
            step_five_resolved_entities,
            step_four_entity_contexts,
            step_six_entity_pairs,
            settings,
        )
        step_eight_final_entity_context_graphs = await step08_entity_graph.run(
            channel,
            payload,
            step_five_resolved_entities,
            step_four_entity_contexts,
            settings,
        )
        step_nine_merged_graph_delta = step09_merge_graph.run(
            payload,
            step_zero_graph_delta,
            step_two_extraction,
            step_seven_relationships,
            step_eight_final_entity_context_graphs,
        )
        validate_upsert_graph_delta_payload("step nine", step_nine_merged_graph_delta)
        step_ten_final_graph_delta = await step10_mentions.run(
            step_nine_merged_graph_delta,
            settings,
            payload.requested_by_user_id,
        )
        await core._preflight_validate_graph_delta_entities(
            channel,
            step_ten_final_graph_delta,
            payload.requested_by_user_id,
        )

        upsert_graph_delta = channel.unary_unary(
            "/exobrain.knowledge.v1.KnowledgeInterface/UpsertGraphDelta",
            request_serializer=core.knowledge_pb2.UpsertGraphDeltaRequest.SerializeToString,
            response_deserializer=core.knowledge_pb2.UpsertGraphDeltaReply.FromString,
        )
        upsert_request = validate_upsert_graph_delta_payload("step ten", step_ten_final_graph_delta)
        upsert_reply = await core._call_with_retry(
            step_name="step eleven",
            operation="UpsertGraphDelta",
            call=lambda: upsert_graph_delta(upsert_request),
        )
        core.logger.info(
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
        print(core._format_exception_for_stderr(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
