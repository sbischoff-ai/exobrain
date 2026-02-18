#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.agent/state/native-infra.env"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

PG_PORT="${PG_PORT:-${POSTGRES_PORT:-15432}}"
if [[ -n "${POSTGRES_DSN:-}" ]]; then
  dsn_port="$(sed -nE 's#.*:([0-9]+)/.*#\1#p' <<<"${POSTGRES_DSN}" | head -n1)"
  if [[ -n "${dsn_port}" ]]; then PG_PORT="${dsn_port}"; fi
fi
QDRANT_URL="${QDRANT_URL:-${EXOBRAIN_QDRANT_URL:-http://localhost:6333}}"
NATS_MONITOR_URL="${NATS_MONITOR_URL:-http://localhost:18222/healthz}"

status=0

if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -h localhost -p "${PG_PORT}" -d postgres >/dev/null 2>&1; then
    echo "[health] postgres: ok (localhost:${PG_PORT})"
  else
    echo "[health] postgres: not ready (localhost:${PG_PORT})" >&2
    status=1
  fi
else
  echo "[health] postgres: pg_isready unavailable"
fi

if command -v curl >/dev/null 2>&1; then
  if curl -fsS "${QDRANT_URL}/healthz" >/dev/null 2>&1; then
    echo "[health] qdrant: ok (${QDRANT_URL})"
  elif curl -fsS "${QDRANT_URL}/" >/dev/null 2>&1; then
    echo "[health] qdrant: reachable (${QDRANT_URL})"
  else
    echo "[health] qdrant: unreachable (${QDRANT_URL})" >&2
    status=1
  fi

  if curl -fsS "${NATS_MONITOR_URL}" >/dev/null 2>&1; then
    echo "[health] nats monitor: ok (${NATS_MONITOR_URL})"
  else
    echo "[health] nats monitor: unreachable (${NATS_MONITOR_URL})" >&2
    status=1
  fi
else
  echo "[health] curl unavailable; skipping HTTP checks"
fi

exit "${status}"
