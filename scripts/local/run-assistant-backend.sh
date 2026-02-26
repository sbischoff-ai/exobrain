#!/usr/bin/env bash
set -euo pipefail

export ASSISTANT_DB_DSN=${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db}
export ASSISTANT_CACHE_REDIS_URL=${ASSISTANT_CACHE_REDIS_URL:-redis://localhost:16379/0}
export EXOBRAIN_QDRANT_URL=${EXOBRAIN_QDRANT_URL:-http://localhost:16333}
export EXOBRAIN_MEMGRAPH_URL=${EXOBRAIN_MEMGRAPH_URL:-bolt://localhost:17687}
export EXOBRAIN_NATS_URL=${EXOBRAIN_NATS_URL:-nats://localhost:14222}
export RESHAPE_SCHEMA_QUERY=${RESHAPE_SCHEMA_QUERY:-$(reshape schema-query)}
export MAIN_AGENT_MODEL_PROVIDER_BASE_URL=${MAIN_AGENT_MODEL_PROVIDER_BASE_URL:-http://localhost:8010/v1}
export MAIN_AGENT_MODEL_PROVIDER_API_KEY=${MAIN_AGENT_MODEL_PROVIDER_API_KEY:-model-provider-local}
export MAIN_AGENT_MODEL=${MAIN_AGENT_MODEL:-agent}

if [[ -n "${CODEX_HOME:-}" ]]; then
  export MAIN_AGENT_USE_MOCK=${MAIN_AGENT_USE_MOCK:-true}
fi

cd apps/assistant-backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
