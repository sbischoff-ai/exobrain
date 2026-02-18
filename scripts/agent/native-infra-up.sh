#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${ROOT_DIR}/.agent/state"
LOG_DIR="${STATE_DIR}/logs"
PID_DIR="${STATE_DIR}/pids"
ENV_FILE="${STATE_DIR}/native-infra.env"

PG_PORT="${PG_PORT:-15432}"
PG_DATA_DIR="${PG_DATA_DIR:-${STATE_DIR}/postgres}"
PG_SUPERUSER="${PG_SUPERUSER:-exobrain}"
NATS_PORT="${NATS_PORT:-14222}"
NATS_MONITOR_PORT="${NATS_MONITOR_PORT:-18222}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"

mkdir -p "${LOG_DIR}" "${PID_DIR}"

is_port_open() {
  local host="$1"
  local port="$2"
  (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1
}

start_postgres_as_root_cluster() {
  if ! command -v pg_lsclusters >/dev/null 2>&1 || ! command -v pg_ctlcluster >/dev/null 2>&1; then
    return 1
  fi

  local cluster_line version name port status
  cluster_line="$(pg_lsclusters | awk 'NR==2 {print $0}')"
  [[ -n "${cluster_line}" ]] || return 1

  version="$(awk '{print $1}' <<<"${cluster_line}")"
  name="$(awk '{print $2}' <<<"${cluster_line}")"
  port="$(awk '{print $3}' <<<"${cluster_line}")"
  status="$(awk '{print $4}' <<<"${cluster_line}")"

  if [[ "${status}" != "online" ]]; then
    echo "[agent] starting system postgres cluster ${version}/${name}"
    pg_ctlcluster "${version}" "${name}" start >/dev/null
  fi

  PG_PORT="${port}"
  echo "[agent] using system postgres cluster on port ${PG_PORT}"
  return 0
}

find_pg_bin() {
  local dir
  for dir in /usr/lib/postgresql/*/bin; do
    if [[ -x "${dir}/pg_ctl" && -x "${dir}/initdb" ]]; then
      printf '%s\n' "${dir}"
      return 0
    fi
  done

  echo "Unable to find PostgreSQL binaries (pg_ctl/initdb)." >&2
  return 1
}

start_postgres_non_root() {
  local pg_bin
  pg_bin="$(find_pg_bin)"

  if [[ ! -d "${PG_DATA_DIR}" || ! -f "${PG_DATA_DIR}/PG_VERSION" ]]; then
    echo "[agent] initializing PostgreSQL data dir at ${PG_DATA_DIR}"
    mkdir -p "${PG_DATA_DIR}"
    "${pg_bin}/initdb" -D "${PG_DATA_DIR}" -U "${PG_SUPERUSER}" --auth=trust >/dev/null
  fi

  if "${pg_bin}/pg_ctl" -D "${PG_DATA_DIR}" status >/dev/null 2>&1; then
    echo "[agent] postgres already running"
  else
    echo "[agent] starting PostgreSQL on port ${PG_PORT}"
    "${pg_bin}/pg_ctl" -D "${PG_DATA_DIR}" -l "${LOG_DIR}/postgres.log" -o "-p ${PG_PORT}" start >/dev/null
  fi

  for _ in {1..30}; do
    if "${pg_bin}/pg_isready" -h localhost -p "${PG_PORT}" -d postgres >/dev/null 2>&1; then
      echo "[agent] postgres ready"
      return 0
    fi
    sleep 1
  done

  echo "[agent] postgres failed to become ready" >&2
  return 1
}

start_postgres() {
  if [[ "$(id -u)" -eq 0 ]]; then
    if start_postgres_as_root_cluster; then
      return 0
    fi
    echo "[agent] root mode but no cluster tooling found; cannot initdb as root" >&2
    return 1
  fi

  start_postgres_non_root
}

start_nats() {
  if ! command -v nats-server >/dev/null 2>&1; then
    echo "[agent] nats-server not found; skipping"
    return 0
  fi

  if is_port_open localhost "${NATS_PORT}"; then
    echo "[agent] nats already reachable on ${NATS_PORT}"
    return 0
  fi

  echo "[agent] starting NATS on ${NATS_PORT} (monitor ${NATS_MONITOR_PORT})"
  nohup nats-server -p "${NATS_PORT}" -m "${NATS_MONITOR_PORT}" >"${LOG_DIR}/nats.log" 2>&1 &
  echo $! >"${PID_DIR}/nats.pid"
}

start_qdrant() {
  if ! command -v qdrant >/dev/null 2>&1; then
    echo "[agent] qdrant not found; skipping"
    return 0
  fi

  if is_port_open localhost 6333; then
    echo "[agent] qdrant already reachable on 6333"
    return 0
  fi

  echo "[agent] starting Qdrant"
  nohup qdrant >"${LOG_DIR}/qdrant.log" 2>&1 &
  echo $! >"${PID_DIR}/qdrant.pid"
}

write_env_file() {
  cat >"${ENV_FILE}" <<ENV
export POSTGRES_DSN=postgresql://exobrain:exobrain@localhost:${PG_PORT}/postgres?sslmode=disable
export ASSISTANT_DB_DSN=postgresql://assistant_backend:assistant_backend@localhost:${PG_PORT}/assistant_db?sslmode=disable
export EXOBRAIN_POSTGRES_URL=postgresql://exobrain:exobrain@localhost:${PG_PORT}/exobrain?sslmode=disable
export EXOBRAIN_NATS_URL=nats://localhost:${NATS_PORT}
export EXOBRAIN_QDRANT_URL=${QDRANT_URL}
ENV
  echo "[agent] wrote ${ENV_FILE}"
}

start_postgres
start_nats
start_qdrant
write_env_file

echo "[agent] native infra startup attempted"
echo "[agent] logs: ${LOG_DIR}"
echo "[agent] source ${ENV_FILE} before app/db scripts"
