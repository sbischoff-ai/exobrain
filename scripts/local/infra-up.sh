#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-infra/docker-compose/local-infra.yml}

docker compose -f "$COMPOSE_FILE" up -d

echo "Local infrastructure services are starting."
echo "PostgreSQL: localhost:15432"
echo "Qdrant:    localhost:16333 (HTTP), localhost:16334 (gRPC)"
echo "Memgraph:  localhost:17687 (Bolt), localhost:17444 (HTTP)"
echo "NATS:      localhost:14222 (client), localhost:18222 (monitoring)"
echo "Redis:     localhost:16379"
