#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "${ROOT_DIR}"
./scripts/agent/native-infra-up.sh
./scripts/agent/native-infra-health.sh
./scripts/agent/assistant-db-setup-native.sh

echo "[agent] infra + db setup completed"
echo "[agent] start backend (offline): ./scripts/agent/run-assistant-backend-offline.sh"
echo "[agent] start frontend (mock-only): ./scripts/agent/run-assistant-frontend-mock.sh"
echo "[agent] start frontend (integrated): ./scripts/local/run-assistant-frontend.sh"
