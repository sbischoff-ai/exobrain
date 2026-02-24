# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG ingestion and schema management.

## What this service now provides

- Dynamic graph schema metadata in PostgreSQL (`knowledge_graph_schema` database).
- gRPC API for:
  - schema introspection (`GetSchema`)
  - schema upsert (`UpsertSchemaType`)
  - unified graph delta ingestion (`IngestGraphDelta`) for entities, edges, and blocks.
- Pluggable adapters behind traits for:
  - graph store (Neo4j/Memgraph via `neo4rs`)
  - vector store (Qdrant via `qdrant-client`)
  - embedding model provider (OpenAI embeddings API)

Retrieval/query over the graph is intentionally out of scope in this increment.

## gRPC methods

- `Health`
- `GetSchema`
- `UpsertSchemaType`
- `IngestGraphDelta`

See `proto/knowledge.proto` for payload details.

## Runtime dependencies

Required environment variables:

- `MEMGRAPH_BOLT_ADDR` (example: `bolt://localhost:17687`)
- `QDRANT_ADDR` (example: `http://localhost:16333`)
- `OPENAI_API_KEY`

Database environment variables:

- `KNOWLEDGE_SCHEMA_DSN` preferred (example: `postgresql://knowledge_schema:knowledge_schema@localhost:15432/knowledge_graph_schema`)
- falls back to `METASTORE_DSN`

Optional:

- `OPENAI_EMBEDDING_MODEL` (default: `text-embedding-3-small`)

## Local build and run

From the repository root:

```bash
./scripts/local/build-knowledge-interface.sh
./scripts/local/run-knowledge-interface.sh
```

Notes:
- Re-run the build script after source changes; Rust binaries must be recompiled.
- `cargo build --locked` reuses incremental artifacts and recompiles only what changed.

## Local environment endpoints

- Knowledge interface gRPC: `localhost:50051`
- PostgreSQL: `localhost:15432`
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)

## Related docs

- Repository docs hub: [`../../docs/README.md`](../../docs/README.md)
- Local setup workflow: [`../../docs/development/local-setup.md`](../../docs/development/local-setup.md)
- k3d workflow: [`../../docs/development/k3d-workflow.md`](../../docs/development/k3d-workflow.md)
- Architecture overview: [`../../docs/architecture/architecture-overview.md`](../../docs/architecture/architecture-overview.md)
