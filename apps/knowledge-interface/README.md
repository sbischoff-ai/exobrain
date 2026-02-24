# Exobrain Knowledge Interface

Rust + tonic gRPC service for GraphRAG ingestion and canonical KG schema registry access.

## API status

This API is **breaking-change friendly** right now (pre-launch). It is optimized for clean schema-driven ingestion rather than compatibility shims.

## What this service provides

- Canonical knowledge schema registry in PostgreSQL (`knowledge_graph_schema`), including:
  - schema types (node/edge)
  - type inheritance/subtyping
  - per-type property contracts
  - edge endpoint rules (domain/range guidance)
- gRPC API for:
  - schema introspection (`GetSchema`) including types + properties + inheritance + edge rules
  - schema type upsert (`UpsertSchemaType`)
  - schema-driven graph delta ingestion (`IngestGraphDelta`) using typed property values

## Key protocol design choices

- No separate `block_types` surface in schema response.
- `IngestGraphDelta` uses generic typed properties on entities, blocks, and edges.
- Event/task fields like `start`, `end`, `due` are modeled as schema properties, not hardcoded proto fields.

## gRPC inspection tips (grpcui)

The service listens with **plaintext gRPC** in local development (no TLS).

```bash
grpcui -plaintext localhost:50051
```

## Environment configuration

Create local env file:

```bash
cp apps/knowledge-interface/.env.example apps/knowledge-interface/.env
```

## Schema migrations and seed

```bash
./scripts/local/knowledge-schema-migrate.sh
./scripts/local/knowledge-schema-seed.sh
```

## Local build and run

```bash
./scripts/local/build-knowledge-interface.sh
./scripts/local/run-knowledge-interface.sh
```

## Related docs

- Service implementation notes: [`./docs/implementation.md`](./docs/implementation.md)
- System-wide graph schema: [`../../docs/knowledge/graph-schema.md`](../../docs/knowledge/graph-schema.md)
- Repository docs hub: [`../../docs/README.md`](../../docs/README.md)
