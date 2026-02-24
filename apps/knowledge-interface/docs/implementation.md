# Knowledge Interface Rust Implementation Guide

This document is code-oriented: it helps a new contributor quickly navigate the Rust service internals.

## Source map

- `src/main.rs`
  - process startup
  - environment loading
  - adapter wiring
  - gRPC server + reflection toggle
- `src/service.rs`
  - application orchestration (`KnowledgeApplication`)
  - canonicalization rules (`block.*` -> `node.*`, `kind=block` -> `kind=node`)
  - compatibility behavior for `GetSchema.block_types`
- `src/adapters.rs`
  - infrastructure integrations:
    - Postgres schema registry repository (`sqlx`)
    - Memgraph writer (`neo4rs`)
    - OpenAI embedding client (`reqwest`)
    - Qdrant upsert client (`qdrant-client`)
- `src/ports.rs`
  - service-facing trait contracts for repositories/stores/providers
- `src/domain.rs`
  - DTOs used across service/adapters

## Request/flow walkthrough

### 1) `GetSchema`

1. gRPC handler in `main.rs` forwards to `KnowledgeApplication::get_schema`.
2. `service.rs` loads canonical `node` and `edge` types from repository.
3. `service.rs` asks repository for block compatibility subset (`node.block`, `node.quote`).
4. handler maps domain objects to proto reply.

### 2) `UpsertSchemaType`

1. gRPC handler maps proto payload to domain `SchemaType`.
2. `KnowledgeApplication::upsert_schema_type` canonicalizes legacy block semantics:
   - `kind=block` becomes `kind=node`
   - `id=block.x` becomes `id=node.x`
3. canonical row is upserted via repository.

### 3) `IngestGraphDelta`

1. gRPC handler maps proto payload into `GraphDelta`.
2. service writes entities/blocks/edges to graph store.
3. service generates embeddings for block text.
4. service writes block vectors + payload metadata to Qdrant.

## Internal architecture pattern

The service follows a ports-and-adapters style:

- `KnowledgeApplication` has no direct DB/network code.
- all side effects occur behind traits in `ports.rs`.
- adapter implementations are swappable without changing orchestration logic.

This keeps business logic testable and isolates integration-specific concerns.

## Canonical schema access helpers (future proto expansion)

`SchemaRepository` and `KnowledgeApplication` already expose internal methods used for planned schema APIs:

- inheritance graph (`get_type_inheritance`)
- inheritance-aware property resolution (`get_properties_for_type`)
- edge endpoint rules (`get_edge_endpoint_rules`)

These are intentionally internal for now; existing proto remains unchanged.

## Where to add new behavior

- New orchestration rule: add in `service.rs`.
- New integration backend/provider: implement trait in `ports.rs`, wire in `main.rs`.
- New gRPC method mapping: update `proto`, regenerate, then handler logic in `main.rs`.
- New registry SQL shape: add Reshape migration files under
  `infra/metastore/knowledge-interface/migrations` (do not add runtime DDL).

## Test layout

Current unit tests are colocated with modules:

- `main.rs`: config/reflection behavior tests
- `service.rs`: canonicalization + orchestration tests
- `adapters.rs`: Cypher edge type validation tests

When extending logic, prefer adding tests beside the module under change unless shared fixtures justify extraction.
