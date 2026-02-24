# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG ingestion and schema management.

## What this service provides

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

## Environment configuration

Create local env file:

```bash
cp apps/knowledge-interface/.env.example apps/knowledge-interface/.env
```

`OPENAI_API_KEY` is intentionally not stored in `.env`.

Reflection behavior:
- `APP_ENV=local`: gRPC reflection enabled (useful for `grpcui`).
- non-local env (for example `cluster`): reflection disabled.

## Local build and run

From repository root:

```bash
./scripts/local/build-knowledge-interface.sh
./scripts/local/run-knowledge-interface.sh
```

Seed starter schema types:

```bash
./scripts/local/knowledge-schema-seed.sh
```

## Local environment endpoints

- Knowledge interface gRPC: `localhost:50051`
- PostgreSQL: `localhost:15432`
- Qdrant: `localhost:16333` (HTTP), `localhost:16334` (gRPC)
- Memgraph: `localhost:17687` (Bolt), `localhost:17444` (HTTP)
- NATS: `localhost:14222` (client), `localhost:18222` (monitoring)

## Related docs

- Service implementation notes: [`./docs/implementation.md`](./docs/implementation.md)
- System-wide graph schema: [`../../docs/knowledge/graph-schema.md`](../../docs/knowledge/graph-schema.md)
- Repository docs hub: [`../../docs/README.md`](../../docs/README.md)
