#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.agent/state/native-infra.env"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

ASSISTANT_DB_DSN="${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db?sslmode=disable}"

psql "${ASSISTANT_DB_DSN}" -v ON_ERROR_STOP=1 <<'SQL'
TRUNCATE TABLE
  messages,
  conversations,
  identities,
  users
RESTART IDENTITY CASCADE;
SQL

"${ROOT_DIR}/scripts/agent/assistant-db-setup-native.sh"

echo "assistant_db reset and reseeded (native)"
