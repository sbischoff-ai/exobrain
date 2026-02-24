#!/usr/bin/env bash
set -euo pipefail

POSTGRES_DSN=${POSTGRES_DSN:-postgresql://exobrain:exobrain@localhost:15432/postgres}
JOB_ORCHESTRATOR_DB_DSN=${JOB_ORCHESTRATOR_DB_DSN:-postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db}
MIGRATIONS_DIR=${MIGRATIONS_DIR:-infra/metastore/job-orchestrator/migrations}
BOOTSTRAP_SQL_PATH=${BOOTSTRAP_SQL_PATH:-infra/docker/metastore/init/02-job-orchestrator-db.sql}

psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -f "$BOOTSTRAP_SQL_PATH"

if reshape check --help >/dev/null 2>&1; then
  reshape check --dirs "$MIGRATIONS_DIR"
else
  echo "reshape check is unavailable in this reshape version; skipping migration file validation" >&2
fi

reshape migration start --complete --url "$JOB_ORCHESTRATOR_DB_DSN" --dirs "$MIGRATIONS_DIR"

echo "job_orchestrator_db migrations applied"
