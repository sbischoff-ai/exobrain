#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${ROOT_DIR}/.agent/state"
PID_DIR="${STATE_DIR}/pids"
PG_DATA_DIR="${PG_DATA_DIR:-${STATE_DIR}/postgres}"

find_pg_bin() {
  local dir
  for dir in /usr/lib/postgresql/*/bin; do
    if [[ -x "${dir}/pg_ctl" ]]; then
      printf '%s\n' "${dir}"
      return 0
    fi
  done
  return 1
}

stop_by_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "${pid_file}" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" >/dev/null 2>&1; then
    echo "[agent] stopping ${name} (pid ${pid})"
    kill "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${pid_file}"
}

if pg_bin="$(find_pg_bin)"; then
  if [[ -d "${PG_DATA_DIR}" ]] && "${pg_bin}/pg_ctl" -D "${PG_DATA_DIR}" status >/dev/null 2>&1; then
    echo "[agent] stopping postgres from ${PG_DATA_DIR}"
    "${pg_bin}/pg_ctl" -D "${PG_DATA_DIR}" stop -m fast >/dev/null
  fi
fi

if [[ "${AGENT_STOP_SYSTEM_PG:-0}" == "1" ]] && command -v pg_lsclusters >/dev/null 2>&1 && command -v pg_ctlcluster >/dev/null 2>&1; then
  cluster_line="$(pg_lsclusters | awk 'NR==2 {print $0}')"
  if [[ -n "${cluster_line}" ]]; then
    version="$(awk '{print $1}' <<<"${cluster_line}")"
    name="$(awk '{print $2}' <<<"${cluster_line}")"
    status="$(awk '{print $4}' <<<"${cluster_line}")"
    if [[ "${status}" == "online" ]]; then
      echo "[agent] stopping system postgres cluster ${version}/${name}"
      pg_ctlcluster "${version}" "${name}" stop >/dev/null
    fi
  fi
fi

stop_by_pid_file "nats" "${PID_DIR}/nats.pid"
stop_by_pid_file "qdrant" "${PID_DIR}/qdrant.pid"

echo "[agent] native infra stop attempted"
