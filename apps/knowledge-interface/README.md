# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG ingestion and canonical KG schema registry access.

## What this service provides

- Canonical knowledge schema registry in PostgreSQL (`knowledge_graph_schema`), including:
  - schema types (node/edge)
  - type inheritance/subtyping
  - per-type property contracts
  - edge endpoint rules (domain/range guidance)
- gRPC API for:
  - schema introspection (`GetSchema`)
  - schema upsert (`UpsertSchemaType`)
  - unified graph delta ingestion (`IngestGraphDelta`) for entities, edges, and blocks.
- Pluggable adapters behind traits for graph store, vector store, and embeddings.

Retrieval/query over the graph remains out of scope.

## gRPC compatibility note (`block_types`)

Canonical storage does **not** use a separate block kind. Blocks are node types (`node.block`, `node.quote`).

For proto compatibility:
- `node_types` includes canonical block node types.
- `block_types` is returned as a compatibility view containing `node.block` and `node.quote` (with `kind=block` in response payload only).

## Environment configuration

Create local env file:

```bash
cp apps/knowledge-interface/.env.example apps/knowledge-interface/.env
```

`OPENAI_API_KEY` is intentionally not stored in `.env`.

Reflection behavior:
- `APP_ENV=local`: gRPC reflection enabled (`grpcui` friendly).
- non-local env (for example `cluster`): reflection disabled.

## Schema migrations and seed

Knowledge schema is managed by **Reshape migrations** (service startup does not run DDL).

Apply migrations:

```bash
./scripts/local/knowledge-schema-migrate.sh
```

Apply starter schema seed:

```bash
./scripts/local/knowledge-schema-seed.sh
```

## Local build and run

From repository root:

```bash
./scripts/local/build-knowledge-interface.sh
./scripts/local/run-knowledge-interface.sh
```


## gRPC inspection tips (grpcui)

The service listens with **plaintext gRPC** in local development (no TLS).

Use:

```bash
grpcui -plaintext localhost:50051
```

If you omit `-plaintext`, grpcui attempts TLS and you will see:

`tls: first record does not look like a TLS handshake`

### About the Memgraph compatibility warning

You may see this on startup:

`Failed to obtain server version. Unable to check client-server compatibility...`

This comes from the Neo4j driver compatibility check path when used against Memgraph. It is noisy but non-fatal; the service can still run and serve gRPC if dependencies are reachable.

## Related docs

- Service implementation notes: [`./docs/implementation.md`](./docs/implementation.md)
- System-wide graph schema: [`../../docs/knowledge/graph-schema.md`](../../docs/knowledge/graph-schema.md)
- Repository docs hub: [`../../docs/README.md`](../../docs/README.md)
