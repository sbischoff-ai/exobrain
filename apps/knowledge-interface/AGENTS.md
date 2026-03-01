# AGENTS.md (knowledge-interface scope)

Applies to `apps/knowledge-interface/**`.

## Local run expectations

- Load `apps/knowledge-interface/.env` for local development.
- Keep gRPC reflection local-only (`APP_ENV=local`) so local tooling (for example `grpcui`) works without exposing reflection in deployed environments.
- In local multi-service runs without mock models, start `model-provider` before `knowledge-interface` and use model aliases.

## Ingestion and schema guardrails

- This gRPC surface is pre-launch and may take clean breaking changes; prefer schema-driven property payloads over hard-coded entity/event fields.
- `UpsertGraphDelta` block/entity linkage is edge-based:
  - `BlockNode` does not carry `root_entity_id`
  - clients send `DESCRIBED_BY` edges when needed
- Qdrant block metadata uses `block_level` (0 for `DESCRIBED_BY` root blocks, +1 per `SUMMARIZES` hop) and should not include legacy relationship ID arrays.
- Edge writes may allow `PRIVATE` relationships targeting `SHARED` nodes for the same user; keep node matching semantics aligned.
- Universe semantics:
  - IDs are globally unique across universes
  - universes are semantic/context signals, not ownership scope
  - enforce ownership via `user_id` + `visibility`
- `UpsertGraphDelta` carries `universes[]`; entities may omit `universe_id` and default to Real World UUID `9d7f0fa5-78c1-4805-9efb-3f8f16090d7f`.

## Startup/bootstrap and runtime config

- Startup ensures a shared Exobrain root graph (`universe.real_world` + `concept.exobrain`); keep bootstrap IDs/ownership stable (`exobrain`, `SHARED`).
- For Memgraph-backed runs, set `MEMGRAPH_DB=memgraph` (or deployed DB name) instead of relying on `neo4rs` default (`neo4j`).
- For Qdrant, `QDRANT_ADDR` should be a gRPC endpoint URL (`http://localhost:6334`, etc.), not bare host:port and not REST port `6333`.
- For local `qdrant/qdrant:v1.9.2`, keep Rust `qdrant-client` on a compatible minor line (for example `1.10.x`).
- For offline embedding runs, set `EMBEDDING_USE_MOCK=true`.
