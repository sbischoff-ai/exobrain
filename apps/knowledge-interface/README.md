# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG ingestion and canonical KG schema registry access.

## What this service is

- Provides schema introspection (`GetSchema`) and schema type upsert (`UpsertSchemaType`).
- Accepts schema-driven graph writes through `IngestGraphDelta`.
- Exposes `InitializeUserGraph` to seed a new user-scoped starter subgraph.
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
```

Inspect gRPC APIs locally:

```bash
grpcui -plaintext localhost:50051
```

## Configuration

- Copy env template: `cp apps/knowledge-interface/.env.example apps/knowledge-interface/.env`
- `APP_ENV=local` enables local gRPC reflection.
- `LOG_LEVEL` defaults to `DEBUG` for local and `INFO` otherwise.
- `MEMGRAPH_DB` defaults to `memgraph`; set it explicitly if your Memgraph uses a different database name.


## Built-in graph bootstrapping

On startup, the service checks whether the shared root graph exists in Memgraph and seeds it if missing. The seed is written through the normal Rust ingestion path (including embeddings/Qdrant upsert), and includes:

- Universe: `universe.real_world`
- Concept entity: `concept.exobrain` (owned by `exobrain`, `SHARED`)
- Single descriptive block attached to the concept

## InitializeUserGraph gRPC

`InitializeUserGraph` accepts `user_id` + `user_name` and creates a shared starter subgraph for that user:

- person entity (`person.<user_id>`) with aliases `me`, `I`, `myself`
- object entity (`assistant.<user_id>`) named `Exobrain Assistant`
- one descriptive assistant block (embedded + upserted to Qdrant)
- `ASSISTS` edge from assistant -> person

## Ingestion semantics and current limitations

- Graph writes happen before vector upserts to Qdrant.
- IDs are globally unique across universes.
- Ingestion is access-scoped with `user_id` and `visibility` (`PRIVATE` or `SHARED`) on request + entities + blocks + edges.
- `PRIVATE` and `SHARED` data are explicitly persisted onto Memgraph nodes/edges and Qdrant payloads.
- `labels` are forward-compatible inputs and currently not applied in Memgraph writes.

## Related docs

- Service notes: [`./docs/implementation.md`](./docs/implementation.md)
- Graph schema reference: [`../../docs/knowledge/graph-schema.md`](../../docs/knowledge/graph-schema.md)
- Docs hub: [`../../docs/README.md`](../../docs/README.md)

## Memgraph Lab (optional local inspection)

```bash
docker pull memgraph/lab:latest
docker run -d -p 3000:3000 --name lab memgraph/lab
```
