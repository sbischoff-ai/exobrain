#!/usr/bin/env bash
set -euo pipefail

./scripts/local/knowledge-schema-migrate.sh
./scripts/local/knowledge-schema-seed.sh

echo "knowledge_graph_schema initialized, reshaped, and seeded"
