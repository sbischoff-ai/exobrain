#!/usr/bin/env bash
set -euo pipefail

ASSISTANT_DB_DSN=${ASSISTANT_DB_DSN:-postgresql://assistant_backend:assistant_backend@localhost:15432/assistant_db}
SEED_SQL_DIR=${SEED_SQL_DIR:-infra/metastore/assistant-backend/seeds}
SEED_SQL_PATH=${SEED_SQL_PATH:-}

if [[ -n "${SEED_SQL_PATH}" ]]; then
  psql "$ASSISTANT_DB_DSN" -v ON_ERROR_STOP=1 -f "$SEED_SQL_PATH"
  echo "assistant_db seed applied from ${SEED_SQL_PATH}"
  exit 0
fi

mapfile -t seed_files < <(find "$SEED_SQL_DIR" -maxdepth 1 -type f -name '*.sql' | sort)

if [[ ${#seed_files[@]} -eq 0 ]]; then
  echo "No seed SQL files found in ${SEED_SQL_DIR}" >&2
  exit 1
fi

for seed_file in "${seed_files[@]}"; do
  echo "Applying seed file: ${seed_file}"
  psql "$ASSISTANT_DB_DSN" -v ON_ERROR_STOP=1 -f "$seed_file"
done

echo "assistant_db seed applied from ${SEED_SQL_DIR}"
