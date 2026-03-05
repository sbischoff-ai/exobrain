from __future__ import annotations

from google.protobuf.json_format import ParseError, ParseDict

from app.services.grpc import knowledge_pb2


def extract_parse_dict_field_path(exc: ParseError) -> str:
    import re

    pattern = re.compile(r"Failed to parse (?P<field>[A-Za-z_][A-Za-z0-9_]*) field")
    parts = pattern.findall(str(exc))
    return ".".join(parts) if parts else "<unknown>"


def validate_upsert_graph_delta_payload(step_name: str, payload: dict[str, object]) -> knowledge_pb2.UpsertGraphDeltaRequest:
    try:
        return ParseDict(payload, knowledge_pb2.UpsertGraphDeltaRequest())
    except ParseError as exc:
        field_path = extract_parse_dict_field_path(exc)
        raise RuntimeError(f"knowledge.update {step_name} validation failed at '{field_path}': {exc}") from exc
