# Knowledge Interface Rust Implementation Guide

This document is code-oriented: it helps a new contributor quickly navigate the Rust service internals.

## Architecture and directory map

- `src/main.rs`
  - process startup and dependency wiring
  - infrastructure adapter composition
  - root graph bootstrap + gRPC server startup
- `src/application/`
  - `mod.rs`: thin `KnowledgeApplication` orchestrator/facade
  - `use_cases/`: one module per RPC-aligned use case (`entity_search`, `entity_context`, `entity_listing`, `upsert_graph_delta`, `extraction_schema`)
- `src/transport/`
  - `grpc/`: tonic handlers and server bootstrap
  - `mapping/`: proto ↔ domain conversions only
  - `errors.rs`: transport-level error mapping
- `src/domain/`
  - entities, value objects, and validation-centric types
- `src/infrastructure/`
  - `postgres.rs`: `SchemaRepository` adapter (Postgres)
  - `embedding.rs`: embedding provider adapters
  - `qdrant.rs`: vector-store adapter + payload helpers
  - `memgraph.rs`: graph-store + graph repository public exports
  - `legacy.rs`: Memgraph-oriented repository implementation and related query helpers
- `src/ports.rs`
  - application-facing ports (traits) for infrastructure dependencies

## Request/flow walkthrough

### 1) `GetSchema`

1. gRPC handler in `src/transport/grpc/` forwards to `KnowledgeApplication::get_schema`.
2. `src/application/mod.rs` coordinates canonical `node` and `edge` schema loading.
3. use-case helpers in `src/application/use_cases/` provide extraction/schema context shaping.
4. handler maps full canonical schema objects to proto reply.

### 2) `UpsertSchemaType`

1. gRPC handler maps proto payload to domain `SchemaType`.
2. `KnowledgeApplication::upsert_schema_type` (application layer) validates parent/type rules:
   - nodes must inherit from `node.entity` (except `node.entity` itself)
   - single-parent enforcement for node inheritance
   - edge inheritance is rejected
3. schema type, inheritance row, and additive properties are upserted via repository.

### 3) `UpsertGraphDelta`

1. gRPC handler maps proto payload into `GraphDelta`.
2. application orchestrator pre-processes distinct `user_id` values across universes/entities/blocks/edges and initializes missing user starter graphs before continuing; this implicit path deterministically uses `user_id` as `user_name`.
3. `application/use_cases/upsert_graph_delta.rs` validates the delta against canonical schema types/properties/rules.
4. the same use-case extracts block text from typed properties (`text`) and generates embeddings.
5. application passes graph delta + embedded blocks to the graph repository port.
6. infrastructure adapters write Memgraph + Qdrant with transaction/rollback behavior.

### 4) `GetUserInitGraph`

1. gRPC handler validates and forwards `user_id` + `user_name`.
2. `KnowledgeApplication::get_user_init_graph` first checks a durable Memgraph initialization marker keyed by `user_id`.
3. when the marker is absent, the service builds a deterministic starter delta (all seeded nodes/edges with `PRIVATE` visibility) and writes graph + embeddings.
4. after a successful write, the service marks the user graph initialized via an idempotent Memgraph `MERGE` marker write.

### 5) `GetEntityContext`

1. gRPC handler is present and forwards to application service when wired.
2. `KnowledgeApplication::get_entity_context` validates required IDs (`entity_id`, `user_id`) and trims input.
3. service caps `max_block_level` to a safe upper bound before delegating access-aware query semantics to `GraphRepository`.

## Startup root graph seeding

During service startup (`src/main.rs`), `KnowledgeApplication::ensure_common_root_graph` checks Memgraph for the shared Exobrain root graph and seeds it when absent. Seeding uses standard ingestion flow so block embeddings are generated with the configured embedding model. Memgraph connection now sets database name from `MEMGRAPH_DB` (default `memgraph`) to avoid Neo4j-driver defaults targeting `neo4j`.

## Internal architecture pattern

The service follows a layered ports-and-adapters style:

- `KnowledgeApplication` has no direct DB/network code.
- all side effects occur behind traits in `ports.rs`.
- `GraphRepository` is now the single write boundary for Memgraph + Qdrant consistency.

This keeps business logic testable and isolates integration-specific concerns.

## Canonical schema access

`SchemaRepository` and `KnowledgeApplication` expose canonical schema data directly for `GetSchema`:

- inheritance graph (`get_type_inheritance`)
- property catalog (`get_all_properties`)
- edge endpoint rules (`get_edge_endpoint_rules`)

These are surfaced by the current proto contract.

## Where to add new behavior

- New orchestration rule: add in `src/application/` (prefer `use_cases/` module first).
- New integration backend/provider: implement trait in `src/ports.rs`, wire in `src/main.rs`.
- New gRPC method mapping: update `proto`, regenerate, then handler logic in `src/transport/grpc/`.
- New registry SQL shape: add Reshape migration files under
  `infra/metastore/knowledge-interface/migrations` (do not add runtime DDL).

## Test layout

Current unit tests are colocated with modules:

- `main.rs`: startup and wiring behavior tests
- `application/mod.rs` + `application/use_cases/*` + `application/tests.rs`: orchestration/use-case tests
- `transport/grpc/mod.rs` + `transport/grpc/tests.rs`: handler and reply-shape tests
- `infrastructure/legacy.rs`: Memgraph query/repository helper tests (including Cypher validation and Bolt temporal scalar mapping)

When extending logic, prefer adding tests beside the module under change unless shared fixtures justify extraction.

## Presentation module scope

`src/presentation/` is constrained to artifacts that are explicitly returned by the gRPC contract. Prompt-oriented markdown renderers are intentionally excluded from this crate's compiled module tree until/if the proto surface includes them.

## Universe and label semantics (current)

- IDs are expected to be globally unique (not universe-scoped IDs).
- Universes are semantic/contextual only and do not determine access scope.
- Access scope is modeled via `user_id` ownership and `visibility` (`PRIVATE`/`SHARED`).
- Ingestion requires `user_id`/`visibility` on each universe/entity/block/edge in the delta (no request-level scope fields).
- Memgraph writes persist `user_id` + `visibility` on entities, blocks, and edges.
- Qdrant block payloads persist `user_id` + `visibility` for retrieval-time filtering.
- Clients submit schema `type_id` values; the service resolves full inheritance label chains and applies them to Memgraph nodes during writes.
