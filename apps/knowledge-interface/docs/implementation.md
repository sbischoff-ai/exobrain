# Knowledge Interface Implementation Notes

## Responsibilities

- Expose gRPC ingestion APIs for schema and graph deltas.
- Read/write canonical schema registry data from PostgreSQL.
- Write graph structures to Memgraph.
- Generate embeddings and upsert block vectors into Qdrant.

## Canonical schema registry model

The registry is centered on node/edge schema types and companion metadata tables:

- `knowledge_graph_schema_types`
- `knowledge_graph_schema_type_inheritance`
- `knowledge_graph_schema_type_properties`
- `knowledge_graph_schema_edge_rules`

Blocks are canonical **node types** (`node.block`, `node.quote`), not a separate kind.

## `GetSchema` compatibility behavior

The proto is unchanged, so the service provides a compatibility view:

- `node_types`: full canonical node types (including `node.block`, `node.quote`)
- `edge_types`: canonical edge types
- `block_types`: compatibility subset derived from node types (`node.block`, `node.quote`)

## Migrations

Schema DDL is managed through Reshape migrations under:

- `infra/metastore/knowledge-interface/migrations`

Local migration helper:

```bash
./scripts/local/knowledge-schema-migrate.sh
```

Seed helper:

```bash
./scripts/local/knowledge-schema-seed.sh
```

## Local development behavior

- Config is loaded from `apps/knowledge-interface/.env` (if present).
- gRPC reflection is enabled only when `APP_ENV=local`.
- Docker/cluster runs set `APP_ENV=cluster` (reflection disabled).
