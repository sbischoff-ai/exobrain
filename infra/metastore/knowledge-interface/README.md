# Knowledge Interface Metastore SQL Assets

This directory contains canonical knowledge graph schema registry assets for `knowledge_graph_schema`.

- `migrations/`: Reshape migrations for registry tables.
- `seeds/`: ordered idempotent seed SQL for canonical node/edge types and constraints.

## Local usage

```bash
./scripts/local/knowledge-schema-migrate.sh
./scripts/local/knowledge-schema-seed.sh
```

## Migration validation

```bash
reshape check --dirs infra/metastore/knowledge-interface/migrations
```
