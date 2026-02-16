#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE=${COMPOSE_FILE:-infra/docker-compose/local-infra.yml}

docker compose -f "$COMPOSE_FILE" down
