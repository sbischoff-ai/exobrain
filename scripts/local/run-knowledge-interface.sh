#!/usr/bin/env bash
set -euo pipefail

cd apps/knowledge-interface

if [[ -f .env ]]; then
  echo "Loading environment from apps/knowledge-interface/.env"
  set -a
  source .env
  set +a
fi

export APP_ENV=${APP_ENV:-local}
export METASTORE_DSN=${METASTORE_DSN:-postgresql://exobrain:exobrain@localhost:15432/exobrain}
export KNOWLEDGE_SCHEMA_DSN=${KNOWLEDGE_SCHEMA_DSN:-postgresql://knowledge_schema:knowledge_schema@localhost:15432/knowledge_graph_schema}
export QDRANT_ADDR=${QDRANT_ADDR:-http://localhost:16333}
export MEMGRAPH_BOLT_ADDR=${MEMGRAPH_BOLT_ADDR:-bolt://localhost:17687}
export MODEL_PROVIDER_BASE_URL=${MODEL_PROVIDER_BASE_URL:-http://localhost:8010/v1}
export MODEL_PROVIDER_API_KEY=${MODEL_PROVIDER_API_KEY:-model-provider-local}
export MODEL_PROVIDER_EMBEDDING_ALIAS=${MODEL_PROVIDER_EMBEDDING_ALIAS:-all-purpose}

cargo run
