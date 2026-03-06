from pathlib import Path


def test_knowledge_pb2_includes_graph_delta_json_schema_messages() -> None:
    pb2_source = Path("apps/job-orchestrator/app/services/grpc/knowledge_pb2.py").read_text()

    assert "GetUpsertGraphDeltaJsonSchemaRequest" in pb2_source
    assert "GetUpsertGraphDeltaJsonSchemaReply" in pb2_source
    assert "GetEntityTypePropertyContextRequest" in pb2_source


def test_knowledge_pb2_matches_current_edge_extraction_contract() -> None:
    pb2_source = Path("apps/job-orchestrator/app/services/grpc/knowledge_pb2.py").read_text()

    assert "GetEdgeExtractionSchemaContextRequest\\x12\\x19\\n\\x11\\x66irst_entity_type" in pb2_source
    assert "\\x1a\\n\\x12second_entity_type" in pb2_source
    assert "GetEdgeExtractionSchemaContextReply" in pb2_source
    assert "ExtractionEdgeType" in pb2_source
    assert "\\n\\nedge_types\\x18\\x03" in pb2_source
