#!/usr/bin/env bash
set -euo pipefail

ASSISTANT_DB_DSN=${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db}
SEED_SQL_PATH=${SEED_SQL_PATH:-infra/metastore/assistant-backend/seeds/001_test_user.sql}

psql "$ASSISTANT_DB_DSN" -v ON_ERROR_STOP=1 -f "$SEED_SQL_PATH"

echo "assistant_db seed applied"
