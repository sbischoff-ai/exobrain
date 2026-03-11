# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG ingestion and canonical KG schema registry access.

## What this service is

- Provides full schema introspection (`GetSchema`) and extraction-focused schema projections (`GetEntityExtractionSchemaContext`, `GetEdgeExtractionSchemaContext`).
- Provides schema type upsert (`UpsertSchemaType`) with type-vector sync to Qdrant collections by schema kind (`schema_node_types`/`schema_edge_types`).
- Accepts schema-driven graph writes through `UpsertGraphDelta`.
- Exposes `GetUserInitGraph` to seed a new user-scoped starter subgraph.
- Exposes `GetEntityContext` to read an entity's typed context graph payload for grounded lookups during extraction/deduplication.
- Exposes `ListEntitiesByType` for paginated, visibility-aware entity browsing by type.
- Uses typed property payloads instead of hardcoded event/task fields.

## Quick start

Use shared startup docs for infra and multi-service runs:

- [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- [`../../docs/development/process-orchestration.md`](../../docs/development/process-orchestration.md)

Service-only build/run:

```bash
./scripts/local/build-knowledge-interface.sh
./scripts/local/run-knowledge-interface.sh
```

## Common commands

```bash
./scripts/local/knowledge-schema-migrate.sh
./scripts/local/knowledge-schema-seed.sh
./scripts/local/knowledge-schema-reset-and-seed.sh
./scripts/local/knowledge-graph-reset.sh
```

`knowledge-graph-reset.sh` now restores graph services only if they were running before reset; if infra was down, it stays down.

Inspect gRPC APIs locally:

```bash
grpcui -plaintext localhost:50051
```

Run static checks + tests together:

```bash
cd apps/knowledge-interface && ./scripts/verify.sh
```

## Service module layout

- `src/application/mod.rs` is the public application facade (`KnowledgeApplication`) and delegates feature logic to use-case modules under `src/application/use_cases/`.
- `src/transport/grpc/mod.rs` contains tonic RPC handlers.
- `src/transport/mapping/mod.rs` contains proto ↔ domain mapper functions.
- `src/infrastructure/` holds concrete adapter implementations (`postgres.rs`, `memgraph.rs`, `qdrant.rs`, `embedding.rs`).
- `src/ports.rs` defines repository/embedder traits consumed by `KnowledgeApplication`.
- `src/presentation/upsert_delta_json_schema.rs` is a transport-facing helper for `GetUpsertGraphDeltaJsonSchema` payload generation.

### RPC layer map

| gRPC method | Transport handler | Application / use case | Port trait(s) | Infrastructure adapter(s) |
| --- | --- | --- | --- | --- |
| `GetSchema` | `src/transport/grpc/mod.rs::get_schema` | `src/application/mod.rs::KnowledgeApplication::get_schema` | `SchemaRepository` | `src/infrastructure/postgres.rs` |
| `UpsertSchemaType` | `src/transport/grpc/mod.rs::upsert_schema_type` | `src/application/mod.rs::KnowledgeApplication::upsert_schema_type` | `SchemaRepository` | `src/infrastructure/postgres.rs` |
| `UpsertGraphDelta` | `src/transport/grpc/mod.rs::upsert_graph_delta` | `KnowledgeApplication::upsert_graph_delta` + `src/application/use_cases/upsert_graph_delta.rs::upsert_graph_delta_internal` | `GraphRepository`, `SchemaRepository`, `Embedder` | `src/infrastructure/memgraph.rs`, `src/infrastructure/postgres.rs`, `src/infrastructure/embedding.rs`, `src/infrastructure/qdrant.rs` |
| `GetEntityExtractionSchemaContext` / `GetEdgeExtractionSchemaContext` | `src/transport/grpc/mod.rs` context handlers | `KnowledgeApplication` extraction methods + `src/application/use_cases/extraction_schema.rs` | `SchemaRepository`, `GraphRepository` | `src/infrastructure/postgres.rs`, `src/infrastructure/memgraph.rs` |
| `FindEntityCandidates` | `src/transport/grpc/mod.rs::find_entity_candidates` | `KnowledgeApplication::find_entity_candidates` + `src/application/use_cases/entity_search.rs` | `GraphRepository`, `Embedder` | `src/infrastructure/memgraph.rs`, `src/infrastructure/embedding.rs` |
| `ListEntitiesByType` | `src/transport/grpc/mod.rs::list_entities_by_type` | `KnowledgeApplication::list_entities_by_type` + `src/application/use_cases/entity_listing.rs` | `GraphRepository` | `src/infrastructure/memgraph.rs` |
| `GetEntityContext` | `src/transport/grpc/mod.rs::get_entity_context` | `KnowledgeApplication::get_entity_context` + `src/application/use_cases/entity_context.rs` | `GraphRepository` | `src/infrastructure/memgraph.rs` |
| `GetUserInitGraph` | `src/transport/grpc/mod.rs::get_user_init_graph` | `KnowledgeApplication::get_user_init_graph` | `GraphRepository` (+ shared upsert path uses `SchemaRepository`/`Embedder`) | `src/infrastructure/memgraph.rs` (+ shared upsert dependencies above) |

## Domain typing boundaries

Schema kind values are represented internally via `SchemaKind` (`Node`/`Edge`) and converted to/from wire/database strings only in:

- `src/transport/mapping/mod.rs` (proto boundary)
- `src/infrastructure/postgres.rs` (database boundary)

High-risk IDs now have lightweight primitives (`TypeId`, `EntityId`, `UniverseId`) for service-level validation paths to reduce accidental ID mixups.

## Configuration

- Copy env template: `cp apps/knowledge-interface/.env.example apps/knowledge-interface/.env`
- `APP_ENV=local` enables local gRPC reflection.
- `LOG_LEVEL` defaults to `DEBUG` for local and `INFO` otherwise.
- `MEMGRAPH_DB` defaults to `memgraph`; set it explicitly if your Memgraph uses a different database name.
- If `EMBEDDING_USE_MOCK=true`, embeddings are generated by a deterministic mock embedder for offline/agent development.
- Otherwise embeddings are routed through model-provider via `MODEL_PROVIDER_BASE_URL` and alias `MODEL_PROVIDER_EMBEDDING_ALIAS` (default `all-purpose`).

## Built-in graph bootstrapping

On startup, the service checks whether the shared root graph exists in Memgraph and seeds it if missing. The seed is written through the same validated ingestion pipeline used by gRPC requests, including Qdrant projection updates.
Qdrant uses separate collections for block embeddings (`blocks`) and schema type embeddings (`schema_node_types`, `schema_edge_types`), each configured with 3072-dimension cosine vectors.

For `UpsertSchemaType`, the service embeds canonical type text (`entity type: ...` / `relationship type: ...`) via the same `Embedder` path used elsewhere, then upserts the vector to kind-specific Qdrant collections. Inactive schema types remain indexed with `active=false` payload for query-time filtering. If vector sync fails after DB upsert, the schema type DB write is rolled back and the request returns a contextual error.

`KnowledgeApplication::ensure_common_root_graph` is startup-only support logic, not an RPC. It exists to satisfy runtime preconditions for the RPC contract (shared `universe.real_world` and `concept.exobrain` roots) before requests are served.

Internal Memgraph timestamp triggers are ensured idempotently during startup by checking `SHOW TRIGGERS` and creating only missing triggers, so pre-existing triggers are treated as already-initialized state instead of a fatal error.
Update triggers target Memgraph update-event payloads (`event.vertex` / `event.edge`) to avoid invalid property writes during node or edge updates.

## Write consistency guarantees

All graph writes now flow through a single application path (`KnowledgeApplication::upsert_graph_delta`) that:

1. Ensures each distinct `user_id` in the incoming delta has starter graph initialization; when this path must initialize implicitly and no richer profile exists, it deterministically uses `user_id` as `user_name`.
2. Validates the delta against schema type/property/rule contracts.
3. Generates embeddings for `node.block` nodes.
4. Writes to Memgraph and Qdrant as one coordinated operation.

During `UpsertGraphDelta`, all schema-defined properties provided on entities, blocks, and edges are written through to Memgraph properties (for example `email`, `phone`, `lat`, `lon`), in addition to core system fields.

The Memgraph write is held in a transaction until Qdrant upserts complete. If Qdrant fails, Memgraph is rolled back. If Memgraph commit fails after Qdrant upsert, the new Qdrant points are deleted as compensation.

## GetUserInitGraph gRPC

`GetUserInitGraph` accepts `user_id` + `user_name`; it initializes the user starter graph if missing, otherwise returns persisted starter node ids and syncs the person name when changed:

- person entity (UUID id) with aliases `me`, `I`, `myself`
- AI agent entity (`node.ai_agent`, UUID id) named `Exobrain Assistant`
- one descriptive assistant block (embedded + upserted to Qdrant)
- `RELATED_TO` edge from assistant -> person
- all seeded user-init nodes/edges are created with `PRIVATE` visibility


## ListEntitiesByType gRPC

`ListEntitiesByType` returns entities filtered by the requested type label (including subtype entities that inherit that label) and requester visibility (`user_id` private + shared), with cursor pagination via `next_page_token`.
On Memgraph query failures, the service logs `user_id`, `type_id`, and pagination parameters to make production debugging actionable.

## FindEntityCandidates gRPC

`FindEntityCandidates` helps resolve user-provided entity mentions to known graph entities.

Example request payload:

```json
{
  "names": ["Ada", "Ada Lovelace"],
  "potential_type_ids": ["node.person"],
  "short_description": "mathematician known for analytical engine notes",
  "user_id": "user-123",
  "limit": 5
}
```

How to interpret scores:

- Score composition is implemented in the application use case (`src/application/use_cases/entity_search.rs`) so ranking policy is adapter-independent.
- Current deterministic weights are `0.55` lexical + `0.45` semantic similarity.
- Semantic similarity is weighted by block depth so root description blocks count more before composition.
- Higher score means stronger overall confidence.
- Candidates are sorted descending by score and capped by `limit`.


## Choosing between GetSchema and extraction context RPCs

- Use `GetSchema` when clients need the canonical, lossless schema model (types, properties, inheritance, and edge rules) for admin tooling, migrations, or schema UIs.
- Use `GetEntityExtractionSchemaContext` when clients need only universe + entity-type context for entity extraction.
- Use `GetEdgeExtractionSchemaContext` when clients need edge options for one specific entity-type pair (input order does not matter).

## GetUpsertGraphDeltaJsonSchema for LLM structured output

Use `GetUpsertGraphDeltaJsonSchema` when clients need a machine-consumable schema for generating `UpsertGraphDelta` payloads.

- **Primary use case:** pass the returned `json_schema` to LLM structured output configuration so generated payloads match request shape.
- **Artifact semantics:** `json_schema` is deterministic JSON Schema Draft 2020-12 and uses proto field naming (`snake_case`) aligned with `UpsertGraphDeltaRequest`.
- **Limitation:** schema validation only checks request shape. Ingestion still enforces server-side semantic validations (`type/property/rule/cardinality`) at `UpsertGraphDelta` runtime.

Minimal usage pattern:

```text
GetUpsertGraphDeltaJsonSchema() -> { json_schema }
LLM.generate(structured_output_schema=json_schema) -> upsert_payload
UpsertGraphDelta(upsert_payload)
```

## Graph delta constraints for clients

See detailed contract docs here:

- [`./docs/grpc-api.md`](./docs/grpc-api.md)
- [`../../docs/knowledge/graph-schema.md`](../../docs/knowledge/graph-schema.md)

## Local UIs

- Memgraph Lab (via local compose): `http://localhost:13000`
- Qdrant dashboard: `http://localhost:16333/dashboard`

## Related docs

- Service notes: [`./docs/implementation.md`](./docs/implementation.md)
- Graph schema reference: [`../../docs/knowledge/graph-schema.md`](../../docs/knowledge/graph-schema.md)
- Docs hub: [`../../docs/README.md`](../../docs/README.md)
