#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="${ROOT_DIR}/.agent/state"
LOG_DIR="${STATE_DIR}/logs"
PID_DIR="${STATE_DIR}/pids"
WORKFLOW="${1:-generic}"
if [[ "${1:-}" == "--workflow" ]]; then
  WORKFLOW="${2:-generic}"
fi

critical_remediations=()
warning_remediations=()
info_remediations=()

add_critical() {
  critical_remediations+=("$1")
}

add_warning() {
  warning_remediations+=("$1")
}

add_info() {
  info_remediations+=("$1")
}

check_binary() {
  local bin="$1"
  local optional="${2:-false}"

  if command -v "${bin}" >/dev/null 2>&1; then
    echo "[doctor] ✅ binary '${bin}' found"
    return 0
  fi

  if [[ "${optional}" == "true" ]]; then
    echo "[doctor] ⚠️  optional binary '${bin}' not found"
    add_info "Install '${bin}' if your workflow needs it (native infra checks/startup may skip otherwise)."
  else
    echo "[doctor] ❌ required binary '${bin}' not found"
    add_critical "Install '${bin}' and rerun: missing required tool blocks agent workflows."
  fi
}

port_owner() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN -Fpctn 2>/dev/null | paste -sd' ' -
    return 0
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "( sport = :${port} )" 2>/dev/null | awk 'NR>1 {print $0; exit}'
    return 0
  fi

  return 1
}

check_port() {
  local label="$1"
  local port="$2"
  local expected_pattern="$3"
  local owner

  owner="$(port_owner "${port}" || true)"
  if [[ -z "${owner}" ]]; then
    echo "[doctor] ✅ port ${port} (${label}) is free"
    return 0
  fi

  if [[ -n "${expected_pattern}" && "${owner}" =~ ${expected_pattern} ]]; then
    echo "[doctor] ✅ port ${port} (${label}) in use by expected process: ${owner}"
    return 0
  fi

  echo "[doctor] ⚠️  port ${port} (${label}) already in use: ${owner}"
  add_warning "Free port ${port} (${label}) or align env vars before running '${WORKFLOW}'."
}

check_writable_dir() {
  local dir="$1"

  mkdir -p "${dir}"
  if [[ ! -w "${dir}" ]]; then
    echo "[doctor] ❌ directory not writable: ${dir}"
    add_critical "Ensure '${dir}' is writable (chmod/chown) for pid/log/state files."
    return 1
  fi

  local probe="${dir}/.doctor-write-test"
  if ! : >"${probe}" 2>/dev/null; then
    echo "[doctor] ❌ failed write probe in ${dir}"
    add_critical "Fix filesystem permissions for '${dir}' and retry."
    return 1
  fi
  rm -f "${probe}"
  echo "[doctor] ✅ writable directory: ${dir}"
}

print_env_expectation() {
  local key="$1"
  local default="$2"
  local required="$3"
  local value="${!key:-$default}"
  local source="default"

  if [[ -n "${!key:-}" ]]; then
    source="env"
  fi

  printf '[doctor] env %-28s = %-40s (source=%s)\n' "${key}" "${value}" "${source}"

  if [[ "${required}" == "true" && -z "${value}" ]]; then
    add_critical "Set env var '${key}' (no usable value inferred)."
  fi
}

echo "[doctor] running preflight checks (workflow=${WORKFLOW})"

# 1) Binaries.
check_binary psql
check_binary reshape
check_binary uv
check_binary npm
check_binary qdrant true
check_binary nats-server true
check_binary redis-server true

# 2) Ports/processes.
PG_PORT="${PG_PORT:-15432}"
NATS_PORT="${NATS_PORT:-14222}"
NATS_MONITOR_PORT="${NATS_MONITOR_PORT:-18222}"
REDIS_PORT="${REDIS_PORT:-16379}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

check_port postgres "${PG_PORT}" 'postgres'
check_port nats "${NATS_PORT}" 'nats-server'
check_port nats-monitor "${NATS_MONITOR_PORT}" 'nats-server'
check_port redis "${REDIS_PORT}" 'redis-server'
check_port qdrant "${QDRANT_PORT}" 'qdrant'
check_port assistant-backend "${BACKEND_PORT}" 'python|uvicorn'
check_port assistant-frontend "${FRONTEND_PORT}" 'node|vite'

# 3) Writable state/log dirs.
check_writable_dir "${STATE_DIR}"
check_writable_dir "${LOG_DIR}"
check_writable_dir "${PID_DIR}"

# 4) Env vars + inferred defaults.
print_env_expectation PG_PORT 15432 false
print_env_expectation NATS_PORT 14222 false
print_env_expectation NATS_MONITOR_PORT 18222 false
print_env_expectation QDRANT_URL http://localhost:6333 false
print_env_expectation ASSISTANT_CACHE_REDIS_URL redis://localhost:16379/0 false
print_env_expectation MAIN_AGENT_USE_MOCK true false
print_env_expectation WEB_TOOLS_USE_MOCK true false
print_env_expectation WEB_TOOLS_MOCK_DATA_FILE "${ROOT_DIR}/apps/assistant-backend/mock-data/web-tools.mock.json" false
print_env_expectation E2E_USE_EXISTING_SERVER false false
print_env_expectation E2E_FORCE_REINSTALL false false

# 5) Remediations grouped by severity.
echo
echo "[doctor] remediation summary"
if [[ ${#critical_remediations[@]} -eq 0 ]]; then
  echo "- CRITICAL: none"
else
  echo "- CRITICAL:"
  for item in "${critical_remediations[@]}"; do
    echo "  - ${item}"
  done
fi

if [[ ${#warning_remediations[@]} -eq 0 ]]; then
  echo "- WARNING: none"
else
  echo "- WARNING:"
  for item in "${warning_remediations[@]}"; do
    echo "  - ${item}"
  done
fi

if [[ ${#info_remediations[@]} -eq 0 ]]; then
  echo "- INFO: none"
else
  echo "- INFO:"
  for item in "${info_remediations[@]}"; do
    echo "  - ${item}"
  done
fi

if [[ ${#critical_remediations[@]} -gt 0 ]]; then
  exit 1
fi

exit 0
