#!/usr/bin/env bash
set -euo pipefail

KNOWLEDGE_SCHEMA_DSN=${KNOWLEDGE_SCHEMA_DSN:-postgresql://knowledge_schema:knowledge_schema@localhost:15432/knowledge_graph_schema}

echo "[knowledge-schema-reset] truncating schema tables"
psql "$KNOWLEDGE_SCHEMA_DSN" -v ON_ERROR_STOP=1 <<'SQL'
TRUNCATE TABLE
  knowledge_graph_schema_edge_rules,
  knowledge_graph_schema_type_properties,
  knowledge_graph_schema_type_inheritance,
  knowledge_graph_schema_types
RESTART IDENTITY CASCADE;
SQL

./scripts/local/knowledge-schema-migrate.sh
./scripts/local/knowledge-schema-seed.sh

echo "[knowledge-schema-reset] done"
