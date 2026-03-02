# Knowledge Interface Rust Implementation Guide

This document is code-oriented: it helps a new contributor quickly navigate the Rust service internals.

## Source map

- `src/main.rs`
  - process startup
  - environment loading
  - adapter wiring
  - startup root-graph bootstrap check
  - gRPC server + reflection toggle
- `src/service.rs`
  - application orchestration (`KnowledgeApplication`)
  - canonical schema orchestration (`node`/`edge` schema kinds)
  - full-schema aggregation for `GetSchema` (types + properties + inheritance + edge rules)
- `src/adapters.rs`
  - infrastructure integrations:
    - Postgres schema registry repository (`sqlx`)
    - Memgraph + Qdrant coordinated graph repository (`neo4rs` + `qdrant-client`)
    - OpenAI embedding client (`reqwest`)
    - deterministic mock embedder for offline dev
- `src/ports.rs`
  - service-facing trait contracts for repositories/stores/providers
- `src/domain.rs`
  - DTOs used across service/adapters

## Request/flow walkthrough

### 1) `GetSchema`

1. gRPC handler in `main.rs` forwards to `KnowledgeApplication::get_schema`.
2. `service.rs` loads canonical `node` and `edge` types from repository.
3. `service.rs` loads inheritance, property contracts, and edge rules.
4. handler maps full canonical schema objects to proto reply.

### 2) `UpsertSchemaType`

1. gRPC handler maps proto payload to domain `SchemaType`.
2. `KnowledgeApplication::upsert_schema_type` validates parent/type rules:
   - nodes must inherit from `node.entity` (except `node.entity` itself)
   - single-parent enforcement for node inheritance
   - edge inheritance is rejected
3. schema type, inheritance row, and additive properties are upserted via repository.

### 3) `UpsertGraphDelta`

1. gRPC handler maps proto payload into `GraphDelta`.
2. service pre-processes distinct `user_id` values across universes/entities/blocks/edges and initializes missing user starter graphs before continuing; this implicit path deterministically uses `user_id` as `user_name`.
3. service validates the delta against canonical schema types/properties/rules.
4. service extracts block text from typed properties (`text`) and generates embeddings.
5. service hands both graph delta and embedded blocks to one repository call.
6. adapter layer writes Memgraph + Qdrant with transaction/rollback behavior.

### 4) `InitializeUserGraph`

1. gRPC handler validates and forwards `user_id` + `user_name`.
2. `KnowledgeApplication::initialize_user_graph` first checks a durable Memgraph initialization marker keyed by `user_id`.
3. when the marker is absent, the service builds a deterministic starter delta and writes graph + embeddings.
4. after a successful write, the service marks the user graph initialized via an idempotent Memgraph `MERGE` marker write.

## Startup root graph seeding

During service startup (`main.rs`), `KnowledgeApplication::ensure_common_root_graph` checks Memgraph for the shared Exobrain root graph and seeds it when absent. Seeding uses standard ingestion flow so block embeddings are generated with the configured embedding model. Memgraph connection now sets database name from `MEMGRAPH_DB` (default `memgraph`) to avoid Neo4j-driver defaults targeting `neo4j`.

## Internal architecture pattern

The service follows a ports-and-adapters style:

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

- New orchestration rule: add in `service.rs`.
- New integration backend/provider: implement trait in `ports.rs`, wire in `main.rs`.
- New gRPC method mapping: update `proto`, regenerate, then handler logic in `main.rs`.
- New registry SQL shape: add Reshape migration files under
  `infra/metastore/knowledge-interface/migrations` (do not add runtime DDL).

## Test layout

Current unit tests are colocated with modules:

- `main.rs`: config/reflection behavior tests
- `service.rs`: schema/orchestration tests
- `adapters.rs`: Cypher edge type validation tests

When extending logic, prefer adding tests beside the module under change unless shared fixtures justify extraction.

## Universe and label semantics (current)

- IDs are expected to be globally unique (not universe-scoped IDs).
- Universes are semantic/contextual only and do not determine access scope.
- Access scope is modeled via `user_id` ownership and `visibility` (`PRIVATE`/`SHARED`).
- Ingestion requires `user_id`/`visibility` on each universe/entity/block/edge in the delta (no request-level scope fields).
- Memgraph writes persist `user_id` + `visibility` on entities, blocks, and edges.
- Qdrant block payloads persist `user_id` + `visibility` for retrieval-time filtering.
- Clients submit schema `type_id` values; the service resolves full inheritance label chains and applies them to Memgraph nodes during writes.
