#!/usr/bin/env bash
set -euo pipefail

ASSISTANT_DB_DSN=${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db}

psql "$ASSISTANT_DB_DSN" -v ON_ERROR_STOP=1 <<'SQL'
TRUNCATE TABLE
  messages,
  conversations,
  identities,
  users
RESTART IDENTITY CASCADE;
SQL

./scripts/local/assistant-db-seed.sh

echo "assistant_db reset and reseeded"
