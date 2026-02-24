#!/usr/bin/env bash
set -euo pipefail

KNOWLEDGE_SCHEMA_DSN=${KNOWLEDGE_SCHEMA_DSN:-postgresql://knowledge_schema:knowledge_schema@localhost:15432/knowledge_graph_schema}
SEED_SQL=${SEED_SQL:-infra/metastore/knowledge-interface/seeds/001_starter_schema_types.sql}

echo "Seeding starter schema types into knowledge_graph_schema_types"
psql "$KNOWLEDGE_SCHEMA_DSN" -v ON_ERROR_STOP=1 -f "$SEED_SQL"
