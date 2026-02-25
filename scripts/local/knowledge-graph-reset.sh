#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-infra/docker-compose/local-infra.yml}
DEFAULT_PROJECT=$(basename "$(dirname "$COMPOSE_FILE")")
PROJECT=${COMPOSE_PROJECT_NAME:-$DEFAULT_PROJECT}

echo "[knowledge-graph-reset] using compose project: ${PROJECT}"

echo "[knowledge-graph-reset] stopping memgraph + qdrant + memgraph-lab"
docker compose -f "$COMPOSE_FILE" stop memgraph qdrant memgraph-lab >/dev/null 2>&1 || true

echo "[knowledge-graph-reset] removing volumes"
docker volume rm "${PROJECT}_exobrain_memgraph_data" >/dev/null 2>&1 || true
docker volume rm "${PROJECT}_exobrain_qdrant_data" >/dev/null 2>&1 || true

echo "[knowledge-graph-reset] restarting memgraph + qdrant + memgraph-lab"
docker compose -f "$COMPOSE_FILE" up -d memgraph qdrant memgraph-lab

echo "[knowledge-graph-reset] done"
