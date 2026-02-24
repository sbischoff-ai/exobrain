#!/usr/bin/env bash
set -euo pipefail

if [ -f apps/job-orchestrator/.env ]; then
  set -a
  source apps/job-orchestrator/.env
  set +a
fi

export JOB_ORCHESTRATOR_DB_DSN=${JOB_ORCHESTRATOR_DB_DSN:-postgresql://job_orchestrator:job_orchestrator@localhost:15432/job_orchestrator_db}
export EXOBRAIN_NATS_URL=${EXOBRAIN_NATS_URL:-nats://localhost:14222}
export RESHAPE_SCHEMA_QUERY=${RESHAPE_SCHEMA_QUERY:-$(reshape schema-query)}

cd apps/job-orchestrator
uv run python -m app.main_worker
