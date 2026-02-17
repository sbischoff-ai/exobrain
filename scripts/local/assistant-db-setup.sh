#!/usr/bin/env bash
set -euo pipefail

POSTGRES_DSN=${POSTGRES_DSN:-postgresql://exobrain:exobrain@localhost:15432/postgres}
ASSISTANT_DB_DSN=${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db}
MIGRATIONS_DIR=${MIGRATIONS_DIR:-infra/metastore/assistant-backend/migrations}

psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -f infra/docker/metastore/init/01-assistant-db.sql

if reshape check --help >/dev/null 2>&1; then
  reshape check --dirs "$MIGRATIONS_DIR"
else
  echo "reshape check is unavailable in this reshape version; skipping migration file validation" >&2
fi

reshape migration start --complete --url "$ASSISTANT_DB_DSN" --dirs "$MIGRATIONS_DIR"
psql "$ASSISTANT_DB_DSN" -v ON_ERROR_STOP=1 -f infra/metastore/assistant-backend/seeds/001_test_user.sql

echo "assistant_db initialized, reshaped, and seeded with test user"
