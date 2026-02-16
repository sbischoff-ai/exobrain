#!/usr/bin/env bash
set -euo pipefail

export EXOBRAIN_POSTGRES_URL=${EXOBRAIN_POSTGRES_URL:-postgresql://exobrain:exobrain@localhost:15432/exobrain}
export EXOBRAIN_QDRANT_URL=${EXOBRAIN_QDRANT_URL:-http://localhost:16333}
export EXOBRAIN_MEMGRAPH_URL=${EXOBRAIN_MEMGRAPH_URL:-bolt://localhost:17687}
export EXOBRAIN_NATS_URL=${EXOBRAIN_NATS_URL:-nats://localhost:14222}

cd apps/assistant-backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
