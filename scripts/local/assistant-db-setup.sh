#!/usr/bin/env bash
set -euo pipefail

./scripts/local/assistant-db-migrate.sh
./scripts/local/assistant-db-seed.sh

echo "assistant_db initialized, reshaped, and seeded with test user"
