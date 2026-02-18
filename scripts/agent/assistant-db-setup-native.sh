#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.agent/state/native-infra.env"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

ASSISTANT_DB_DSN="${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db?sslmode=disable}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-${ROOT_DIR}/infra/metastore/assistant-backend/migrations}"
BOOTSTRAP_SQL_PATH="${BOOTSTRAP_SQL_PATH:-${ROOT_DIR}/infra/docker/metastore/init/01-assistant-db.sql}"
SEED_SQL_PATH="${SEED_SQL_PATH:-${ROOT_DIR}/infra/metastore/assistant-backend/seeds/001_test_user.sql}"

if [[ "$(id -u)" -eq 0 ]]; then
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -f "${BOOTSTRAP_SQL_PATH}" postgres
else
  POSTGRES_DSN="${POSTGRES_DSN:-postgresql://exobrain:exobrain@localhost:15432/postgres?sslmode=disable}"
  psql "${POSTGRES_DSN}" -v ON_ERROR_STOP=1 -f "${BOOTSTRAP_SQL_PATH}"
fi

if reshape check --help >/dev/null 2>&1; then
  reshape check --dirs "${MIGRATIONS_DIR}"
fi

reshape migration start --complete --url "${ASSISTANT_DB_DSN}" --dirs "${MIGRATIONS_DIR}"
psql "${ASSISTANT_DB_DSN}" -v ON_ERROR_STOP=1 -f "${SEED_SQL_PATH}"

echo "assistant_db initialized, reshaped, and seeded with test user"
