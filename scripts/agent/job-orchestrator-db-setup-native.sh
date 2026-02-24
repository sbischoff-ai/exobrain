#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.agent/state/native-infra.env"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

JOB_ORCHESTRATOR_DB_DSN="${JOB_ORCHESTRATOR_DB_DSN:-postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db?sslmode=disable}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-${ROOT_DIR}/infra/metastore/job-orchestrator/migrations}"
BOOTSTRAP_SQL_PATH="${BOOTSTRAP_SQL_PATH:-${ROOT_DIR}/infra/docker/metastore/init/01-assistant-db.sql}"

if [[ "$(id -u)" -eq 0 ]]; then
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -f "${BOOTSTRAP_SQL_PATH}" postgres
else
  POSTGRES_DSN="${POSTGRES_DSN:-postgresql://exobrain:exobrain@localhost:15432/postgres?sslmode=disable}"
  psql "${POSTGRES_DSN}" -v ON_ERROR_STOP=1 -f "${BOOTSTRAP_SQL_PATH}"
fi

if reshape check --help >/dev/null 2>&1; then
  reshape check --dirs "${MIGRATIONS_DIR}"
fi

reshape migration start --complete --url "${JOB_ORCHESTRATOR_DB_DSN}" --dirs "${MIGRATIONS_DIR}"

echo "job_orchestrator_db initialized and reshaped"
