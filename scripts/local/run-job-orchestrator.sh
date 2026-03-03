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

is_truthy() {
  local value=${1:-}
  case "${value,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

cd apps/job-orchestrator

pids=()

if is_truthy "${JOB_ORCHESTRATOR_API_ENABLED:-true}"; then
  uv run python -m app.main_api &
  pids+=("$!")
fi

if is_truthy "${JOB_ORCHESTRATOR_WORKER_ENABLED:-true}"; then
  uv run python -m app.main_worker &
  pids+=("$!")
fi

if [ "${#pids[@]}" -eq 0 ]; then
  echo "Neither JOB_ORCHESTRATOR_API_ENABLED nor JOB_ORCHESTRATOR_WORKER_ENABLED are enabled." >&2
  exit 1
fi

cleanup() {
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup EXIT INT TERM

set +e
wait -n "${pids[@]}"
status=$?
set -e

exit "$status"
