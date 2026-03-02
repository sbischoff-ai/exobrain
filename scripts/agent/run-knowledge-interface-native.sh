#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.agent/state/native-infra.env"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

export APP_ENV=${APP_ENV:-local}
export LOG_LEVEL=${LOG_LEVEL:-DEBUG}
export EMBEDDING_USE_MOCK=${EMBEDDING_USE_MOCK:-true}
export METASTORE_DSN=${METASTORE_DSN:-postgresql://knowledge_schema:knowledge_schema@localhost:5432/knowledge_graph_schema?sslmode=disable}
export KNOWLEDGE_SCHEMA_DSN=${KNOWLEDGE_SCHEMA_DSN:-postgresql://knowledge_schema:knowledge_schema@localhost:5432/knowledge_graph_schema?sslmode=disable}
export QDRANT_ADDR=${QDRANT_ADDR:-http://localhost:6333}
export MEMGRAPH_BOLT_ADDR=${MEMGRAPH_BOLT_ADDR:-bolt://127.0.0.1:17687}
export MEMGRAPH_DB=${MEMGRAPH_DB:-memgraph}

if ! command -v grpcurl >/dev/null 2>&1; then
  echo "warning: grpcurl not found; you can still run the service but health checks are manual" >&2
fi

if ! (echo >/dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
  echo "error: postgres is not reachable on localhost:5432" >&2
  echo "hint: run ./scripts/agent/native-infra-up.sh" >&2
  exit 1
fi

if ! (echo >/dev/tcp/127.0.0.1/6333) >/dev/null 2>&1; then
  echo "error: qdrant is not reachable on localhost:6333" >&2
  echo "hint: run ./scripts/agent/native-infra-up.sh" >&2
  exit 1
fi

if [[ "${MEMGRAPH_BOLT_ADDR}" =~ ^bolt://([^:/]+):([0-9]+)$ ]]; then
  memgraph_host="${BASH_REMATCH[1]}"
  memgraph_port="${BASH_REMATCH[2]}"
  if ! (echo >"/dev/tcp/${memgraph_host}/${memgraph_port}") >/dev/null 2>&1; then
    echo "error: memgraph is not reachable at ${MEMGRAPH_BOLT_ADDR}" >&2
    echo "hint: native-infra-up does not start Memgraph; start Memgraph separately and retry" >&2
    exit 1
  fi
else
  echo "warning: unable to parse MEMGRAPH_BOLT_ADDR=${MEMGRAPH_BOLT_ADDR}; skipping Memgraph connectivity preflight" >&2
fi

cd "${ROOT_DIR}/apps/knowledge-interface"
cargo run
