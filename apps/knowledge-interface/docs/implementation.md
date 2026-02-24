# Knowledge Interface Implementation Notes

## Responsibilities

- Expose gRPC ingestion APIs for schema and graph deltas.
- Persist schema type metadata in PostgreSQL.
- Write graph structures to Memgraph.
- Generate embeddings and upsert block vectors into Qdrant.

## Adapter boundaries

The service keeps infrastructure behind traits:

- `SchemaRepository`
- `GraphStore`
- `Embedder`
- `VectorStore`

Concrete adapters live in `src/adapters.rs`.

## Local development behavior

- Config is loaded from `apps/knowledge-interface/.env` (if present).
- gRPC reflection is enabled only when `APP_ENV=local`.
- Docker/cluster runs use non-local `APP_ENV`, so reflection remains disabled.

## Starter schema seed

Use:

```bash
./scripts/local/knowledge-schema-seed.sh
```

Seed SQL source:
- `infra/metastore/knowledge-interface/seeds/001_starter_schema_types.sql`
