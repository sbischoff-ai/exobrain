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
  - canonical schema orchestration (`node`/`edge` schema kinds)
  - full-schema aggregation for `GetSchema` (types + properties + inheritance + edge rules)
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
3. `service.rs` loads inheritance, property contracts, and edge rules.
4. handler maps full canonical schema objects to proto reply.

### 2) `UpsertSchemaType`

1. gRPC handler maps proto payload to domain `SchemaType`.
2. `KnowledgeApplication::upsert_schema_type` validates parent/type rules:
   - nodes must inherit from `node.entity` (except `node.entity` itself)
   - single-parent enforcement for node inheritance
   - edge inheritance is rejected
3. schema type, inheritance row, and additive properties are upserted via repository.

### 3) `IngestGraphDelta`

1. gRPC handler maps proto payload into `GraphDelta`.
2. service writes entities/blocks/edges to graph store.
3. service extracts block text from typed properties (`text`) and generates embeddings.
4. service writes block vectors + payload metadata to Qdrant.
5. note: this is currently sequential (graph then vectors), not yet outbox-orchestrated.

## Internal architecture pattern

The service follows a ports-and-adapters style:

- `KnowledgeApplication` has no direct DB/network code.
- all side effects occur behind traits in `ports.rs`.
- adapter implementations are swappable without changing orchestration logic.

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
- Cross-universe relationships are allowed and used for semantic modeling.
- Universes are intended mainly for filtering and implicit context semantics.
- `labels` fields on entity/block payloads are currently parsed and preserved in domain DTOs, but not yet consumed by graph-write Cypher.
