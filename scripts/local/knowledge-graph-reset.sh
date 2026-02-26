#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-infra/docker-compose/local-infra.yml}
DEFAULT_PROJECT=$(basename "$(dirname "$COMPOSE_FILE")")
PROJECT=${COMPOSE_PROJECT_NAME:-$DEFAULT_PROJECT}
SERVICES=(memgraph qdrant memgraph-lab)

echo "[knowledge-graph-reset] using compose project: ${PROJECT}"

was_running=false
if docker compose -f "$COMPOSE_FILE" ps --status running --services 2>/dev/null | grep -Eq '^(memgraph|qdrant|memgraph-lab)$'; then
  was_running=true
fi

echo "[knowledge-graph-reset] stopping graph services"
docker compose -f "$COMPOSE_FILE" stop "${SERVICES[@]}" >/dev/null 2>&1 || true

echo "[knowledge-graph-reset] removing graph service containers"
docker compose -f "$COMPOSE_FILE" rm -f -s "${SERVICES[@]}" >/dev/null 2>&1 || true

echo "[knowledge-graph-reset] removing volumes"
docker volume rm "${PROJECT}_exobrain_memgraph_data" >/dev/null 2>&1 || true
docker volume rm "${PROJECT}_exobrain_qdrant_data" >/dev/null 2>&1 || true

if [ "$was_running" = true ]; then
  echo "[knowledge-graph-reset] graph services were running before reset; starting them again"
  docker compose -f "$COMPOSE_FILE" up -d "${SERVICES[@]}"
else
  echo "[knowledge-graph-reset] graph services were not running before reset; leaving infra down"
fi

echo "[knowledge-graph-reset] done"
