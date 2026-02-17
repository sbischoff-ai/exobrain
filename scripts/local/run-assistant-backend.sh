#!/usr/bin/env bash
set -euo pipefail

export ASSISTANT_DB_DSN=${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db}
export EXOBRAIN_QDRANT_URL=${EXOBRAIN_QDRANT_URL:-http://localhost:16333}
export EXOBRAIN_MEMGRAPH_URL=${EXOBRAIN_MEMGRAPH_URL:-bolt://localhost:17687}
export EXOBRAIN_NATS_URL=${EXOBRAIN_NATS_URL:-nats://localhost:14222}
export RESHAPE_SCHEMA_QUERY=${RESHAPE_SCHEMA_QUERY:-$(reshape schema-query)}

cd apps/assistant-backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
