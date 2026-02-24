#!/usr/bin/env bash
set -euo pipefail

POSTGRES_DSN=${POSTGRES_DSN:-postgresql://exobrain:exobrain@localhost:15432/postgres}
KNOWLEDGE_SCHEMA_DSN=${KNOWLEDGE_SCHEMA_DSN:-postgresql://knowledge_schema:knowledge_schema@localhost:15432/knowledge_graph_schema}
MIGRATIONS_DIR=${MIGRATIONS_DIR:-infra/metastore/knowledge-interface/migrations}
BOOTSTRAP_SQL_PATH=${BOOTSTRAP_SQL_PATH:-infra/docker/metastore/init/03-knowledge-schema-db.sql}

psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -f "$BOOTSTRAP_SQL_PATH"

if reshape check --help >/dev/null 2>&1; then
  reshape check --dirs "$MIGRATIONS_DIR"
else
  echo "reshape check is unavailable in this reshape version; skipping migration file validation" >&2
fi

reshape migration start --complete --url "$KNOWLEDGE_SCHEMA_DSN" --dirs "$MIGRATIONS_DIR"

echo "knowledge_graph_schema migrations applied"
