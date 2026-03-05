from pathlib import Path


def test_knowledge_pb2_includes_graph_delta_json_schema_messages() -> None:
    pb2_source = Path("apps/job-orchestrator/app/services/grpc/knowledge_pb2.py").read_text()

    assert "GetUpsertGraphDeltaJsonSchemaRequest" in pb2_source
    assert "GetUpsertGraphDeltaJsonSchemaReply" in pb2_source
    assert "GetEntityTypePropertyContextRequest" in pb2_source
