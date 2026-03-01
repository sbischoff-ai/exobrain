#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
"${ROOT_DIR}/scripts/agent/doctor.sh" --workflow run-assistant-backend-offline


if [[ -f "${ROOT_DIR}/.agent/state/native-infra.env" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/.agent/state/native-infra.env"
fi

export MAIN_AGENT_USE_MOCK=${MAIN_AGENT_USE_MOCK:-true}
export WEB_TOOLS_USE_MOCK=${WEB_TOOLS_USE_MOCK:-true}
export WEB_TOOLS_MOCK_DATA_FILE=${WEB_TOOLS_MOCK_DATA_FILE:-${ROOT_DIR}/apps/assistant-backend/mock-data/web-tools.mock.json}

cd "${ROOT_DIR}"
./scripts/local/run-assistant-backend.sh
