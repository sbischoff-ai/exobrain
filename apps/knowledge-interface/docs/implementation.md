# Knowledge Interface Rust Implementation Guide

This guide maps the `KnowledgeInterface` proto contract to the current Rust implementation so contributors can trace behavior end-to-end.

## Source map (current)

- Contract
  - `proto/knowledge.proto`
- Binary/bootstrap
  - `src/main.rs` (dependency wiring, startup bootstrap call, server launch)
  - `src/config.rs` (runtime config/env parsing)
- Application orchestration
  - `src/application/mod.rs` (`KnowledgeApplication` service methods)
  - `src/application/use_cases/` (use-case helpers for search/list/context/upsert/extraction)
- Transport
  - `src/transport/grpc/mod.rs` (all RPC handler implementations)
  - `src/transport/mapping/mod.rs` (proto ↔ domain mapper functions)
  - `src/transport/errors.rs` (transport error mapping)
- Ports and adapters
  - `src/ports.rs` (repository/embedder traits)
  - `src/infrastructure/postgres.rs` (schema repository adapter)
  - `src/infrastructure/memgraph.rs` (graph repository logic)
  - `src/infrastructure/qdrant.rs` (vector store adapter)
  - `src/infrastructure/embedding.rs` (embedder adapters)
- Presentation helpers
  - `src/presentation/upsert_delta_json_schema.rs` (JSON schema payload for `GetUpsertGraphDeltaJsonSchema`)

## RPC implementation map (proto-driven)

### `Health`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::health`
- **Mapper functions:** none
- **Use-case/service function:** inline constant response in handler (no application call)
- **Repository/client calls:** none

### `GetSchema`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::get_schema`
- **Mapper functions:** `to_proto_schema_type`, `to_proto_type_property`, `to_proto_type_inheritance`, `to_proto_edge_endpoint_rule`
- **Use-case/service function:** `application/mod.rs::KnowledgeApplication::get_schema`
- **Repository/client calls:**
  - `SchemaRepository::get_by_kind` (node + edge)
  - `SchemaRepository::get_type_inheritance`
  - `SchemaRepository::get_all_properties`
  - `SchemaRepository::get_edge_endpoint_rules`

### `GetUpsertGraphDeltaJsonSchema`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::get_upsert_graph_delta_json_schema`
- **Mapper functions:** none
- **Use-case/service function:** none (presentation helper only)
- **Repository/client calls:** none (calls `presentation/upsert_delta_json_schema.rs::try_upsert_graph_delta_json_schema_string`)

### `GetEntityExtractionSchemaContext`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::get_entity_extraction_schema_context`
- **Mapper functions:** `to_proto_extraction_entity_type`, `to_proto_extraction_universe`
- **Use-case/service function:**
  - `KnowledgeApplication::get_entity_extraction_schema_types`
  - `KnowledgeApplication::get_extraction_universes`
  - extraction assembly helper: `use_cases/extraction_schema.rs::build_extraction_entity_types_from_input`
- **Response shape note:** returns entity type records only (`type_id`, `name`, `description`, `inheritance_chain`) with no per-type edge expansion. Edge options are intentionally provided only by `GetEdgeExtractionSchemaContext`.
- **Repository/client calls:**
  - `SchemaRepository::get_by_kind` (node)
  - `SchemaRepository::get_type_inheritance`
  - `GraphRepository::get_extraction_universes`

### `GetEdgeExtractionSchemaContext`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::get_edge_extraction_schema_context`
- **Mapper functions:** `to_proto_extraction_edge_type`
- **Use-case/service function:**
  - `KnowledgeApplication::get_edge_extraction_schema_types`
  - extraction assembly helper: `use_cases/extraction_schema.rs::build_extraction_edge_types_from_input`
- **Repository/client calls:**
  - `SchemaRepository::get_by_kind` (node + edge)
  - `SchemaRepository::get_type_inheritance`
  - `SchemaRepository::get_edge_endpoint_rules`

### `GetEntityTypePropertyContext`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::get_entity_type_property_context`
- **Mapper functions:** `to_proto_property_context`
- **Use-case/service function:**
  - `KnowledgeApplication::get_entity_type_property_context`
  - helper: `use_cases/extraction_schema.rs::build_entity_type_property_context`
- **Repository/client calls:** indirect via `KnowledgeApplication::get_schema`:
  - `SchemaRepository::get_by_kind` (node + edge)
  - `SchemaRepository::get_type_inheritance`
  - `SchemaRepository::get_all_properties`
  - `SchemaRepository::get_edge_endpoint_rules`

### `UpsertSchemaType`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::upsert_schema_type`
- **Mapper functions:** inline proto→domain mapping in handler for `UpsertSchemaTypeCommand` / `UpsertSchemaTypePropertyInput`
- **Use-case/service function:** `KnowledgeApplication::upsert_schema_type`
- **Repository/client calls:**
  - `SchemaRepository::get_schema_type`
  - `SchemaRepository::is_descendant_of_entity`
  - `SchemaRepository::get_parent_for_child`
  - `SchemaRepository::upsert`
  - `SchemaRepository::upsert_inheritance` (node subtypes)
  - `SchemaRepository::upsert_type_property`

### `UpsertGraphDelta`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::upsert_graph_delta`
- **Mapper functions:**
  - request mapping: `to_domain_universe_node`, `to_domain_entity_node`, `to_domain_block_node`, `to_domain_graph_edge`, `to_domain_property_value`, `map_visibility`
  - error mapping: `transport/errors.rs::map_ingest_error`
- **Use-case/service function:**
  - `KnowledgeApplication::upsert_graph_delta`
  - `KnowledgeApplication::ensure_users_initialized_for_delta`
  - `use_cases/upsert_graph_delta.rs::upsert_graph_delta_internal`
- **Repository/client calls:**
  - user/bootstrap path:
    - `GraphRepository::user_graph_needs_initialization`
    - `GraphRepository::mark_user_graph_initialized`
  - schema validation path:
    - `SchemaRepository::get_by_kind` (node + edge)
    - `SchemaRepository::get_type_inheritance`
    - `SchemaRepository::get_all_properties`
    - `SchemaRepository::get_edge_endpoint_rules`
  - relationship/context checks:
    - `GraphRepository::get_node_relationship_counts`
    - `GraphRepository::get_existing_block_context`
  - embedding + persistence:
    - `Embedder::embed_texts`
    - `GraphRepository::apply_delta_with_blocks`

### `GetUserInitGraph`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::get_user_init_graph`
- **Mapper functions:** none
- **Use-case/service function:** `KnowledgeApplication::get_user_init_graph`
- **Repository/client calls:**
  - `GraphRepository::user_graph_needs_initialization`
  - `GraphRepository::get_user_init_graph_node_ids`
  - `GraphRepository::update_person_name`
  - initialization write path also uses `GraphRepository::mark_user_graph_initialized` and the `UpsertGraphDelta` internal persistence path

### `FindEntityCandidates`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::find_entity_candidates`
- **Mapper functions:** `to_domain_find_entity_candidates_query`, `to_proto_entity_candidate`
- **Use-case/service function:**
  - `KnowledgeApplication::find_entity_candidates`
  - `use_cases/entity_search.rs::find_entity_candidates`
- **Repository/client calls:**
  - `Embedder::embed_texts` (when `short_description` exists)
  - `GraphRepository::find_entity_candidates`

### `ListEntitiesByType`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::list_entities_by_type`
- **Mapper functions:** `to_domain_list_entities_by_type_query`, `to_proto_list_entities_by_type_reply`, `to_proto_list_entities_by_type_item`
- **Use-case/service function:**
  - `KnowledgeApplication::list_entities_by_type`
  - `use_cases/entity_listing.rs::list_entities_by_type`
- **Repository/client calls:** `GraphRepository::list_entities_by_type`

### `GetEntityContext`
- **Transport handler entrypoint:** `transport/grpc/mod.rs::KnowledgeGrpcService::get_entity_context`
- **Mapper functions:** `to_domain_get_entity_context_query`, `to_proto_get_entity_context_reply`, `to_proto_entity_context_neighbor`
- **Use-case/service function:**
  - `KnowledgeApplication::get_entity_context`
  - `use_cases/entity_context.rs::get_entity_context`
- **Repository/client calls:** `GraphRepository::get_entity_context`


## Testing strategy

Testing is **contract-first** for this service:

- Prioritize table-driven gRPC transport tests in `src/transport/grpc/tests.rs` that assert request/response contracts, field normalization, and transport error-code mapping (`INVALID_ARGUMENT` vs `INTERNAL`) per RPC path.
- Keep helper-level unit tests only for pure, high-risk logic (for example extraction inheritance/rule resolution) where transport tests alone are too indirect for regression detection.
- Avoid standalone tests for trivial transport glue (simple option/default forwarding or struct passthrough mapping) unless the behavior is explicitly contract-significant; cover that behavior through RPC-level assertions instead.

## Startup/bootstrap requirements

`main.rs` bootstraps runtime dependencies, constructs `KnowledgeApplication`, then calls `KnowledgeApplication::ensure_common_root_graph()` before starting tonic via `run_server`. This is startup-only support logic (not an RPC handler) that enforces runtime preconditions for the RPC contract. Root graph seeding uses the same graph-delta ingestion path (including embeddings + repository writes) as normal `UpsertGraphDelta` behavior.

Startup also runs `KnowledgeApplication::sync_all_schema_type_vectors()` before serving traffic. This checks both schema kinds and backfills vectors when Postgres schema rows and Qdrant collections diverge.

## Qdrant collections and projection responsibilities

The service uses three Qdrant collections with distinct roles:

- `blocks`: vector index for `node.block` content used by `FindEntityCandidates` semantic matching.
- `schema_node_types`: vector index for canonical node type metadata used by `FindNodeTypeCandidates`.
- `schema_edge_types`: vector index for canonical edge type metadata used by `FindEdgeTypeCandidates`.

All collections use cosine distance with 3072-d vectors. Block writes happen inside graph-delta persistence (`GraphRepository::apply_delta_with_blocks`), while schema-type writes flow through the type-vector repository (`TypeVectorRepository::upsert_schema_type_vector`).

## Schema type sync lifecycle

Schema type vectors are maintained in two moments:

1. **Startup backfill** (`sync_all_schema_type_vectors`)
   - loads canonical schema types by kind from Postgres
   - compares the expected type-id set to stored Qdrant type-id sets
   - when mismatched, re-embeds and upserts all types for that kind
2. **Per-upsert hook** (`upsert_schema_type`)
   - after DB upsert succeeds, embeds the updated type text and upserts one vector
   - if vector sync fails, rolls back the schema DB write to keep stores consistent

This split keeps cold-start recovery simple (full idempotent reconciliation) while keeping steady-state updates incremental.

## Embedding template consistency

Schema type vectors and type-candidate queries intentionally share canonical prompt templates:

- node type template: `entity type: {name}\n\ndescription:\n{description}`
- edge type template: `relationship type: {name}\n\ndescription:\n{description}`

Because nearest-neighbor search quality depends on query/index vectors living in the same embedding manifold, changing template wording in only one path can silently degrade recall and ranking. Keep indexing and query template changes synchronized and covered by tests.

## Contract-driven development note

For this service, functional behavior should remain traceable to one of two contract anchors:

1. a concrete RPC in `proto/knowledge.proto` and its transport/application/repository call chain, or
2. a startup bootstrap requirement needed to make the RPC surface valid at runtime (for example shared root graph initialization).

When adding logic, prefer attaching it to an RPC flow (or explicit bootstrap path) instead of adding orphan runtime behavior.
