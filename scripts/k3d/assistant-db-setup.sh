#!/usr/bin/env bash
set -euo pipefail

./scripts/k3d/assistant-db-migrate.sh
./scripts/k3d/assistant-db-seed.sh

echo "assistant-backend metastore migrations and seed jobs completed"
