# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG ingestion and canonical KG schema registry access.

## What this service is

- Provides schema introspection (`GetSchema`) and schema type upsert (`UpsertSchemaType`).
- Accepts schema-driven graph writes through `IngestGraphDelta`.
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

## Ingestion semantics and current limitations

- Graph writes happen before vector upserts to Qdrant.
- IDs are globally unique across universes; cross-universe graph edges are intentional.
- `labels` are forward-compatible inputs and currently not applied in Memgraph writes.

## Related docs

- Service notes: [`./docs/implementation.md`](./docs/implementation.md)
- Graph schema reference: [`../../docs/knowledge/graph-schema.md`](../../docs/knowledge/graph-schema.md)
- Docs hub: [`../../docs/README.md`](../../docs/README.md)
