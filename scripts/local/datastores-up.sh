#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-infra/docker-compose/local-datastores.yml}

docker compose -f "$COMPOSE_FILE" up -d

echo "Local datastores are starting."
echo "PostgreSQL: localhost:15432"
echo "Qdrant:    localhost:16333 (HTTP), localhost:16334 (gRPC)"
echo "Memgraph:  localhost:17687 (Bolt), localhost:17444 (HTTP)"
